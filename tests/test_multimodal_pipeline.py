# Import SimpleNamespace to simulate Azure analysis results.
from types import SimpleNamespace

# Import patch to replace Azure operations with mocks.
from unittest.mock import patch

# Import pytest for assertions about expected exceptions.
import pytest

# Import the function being tested.
from rag.ingestion.multimodal_pipeline import ingest_multimodal_pdf


# Verify that all extracted evidence is combined correctly.
def test_ingest_combines_all_content_types():

    # Simulate the result returned by Document Intelligence.
    result = SimpleNamespace()

    # Replace the PDF analyzer with a predictable response.
    with patch(
        "rag.ingestion.multimodal_pipeline.analyze_pdf_layout",
        return_value=(result, "operation-123"),
    ) as analyze:

        # Simulate paragraph conversion.
        with patch(
            "rag.ingestion.multimodal_pipeline.convert_paragraphs",
            return_value=["paragraph-evidence"],
        ) as paragraphs:

            # Simulate table conversion.
            with patch(
                "rag.ingestion.multimodal_pipeline.convert_tables",
                return_value=["table-evidence"],
            ) as tables:

                # Simulate figure conversion.
                with patch(
                    "rag.ingestion.multimodal_pipeline.convert_figures",
                    return_value=["figure-evidence"],
                ) as figures:

                    # Run the complete ingestion workflow.
                    elements = ingest_multimodal_pdf(
                        file_path="reports/annual.pdf",
                        document_id="REPORT-001",
                        source_uri="documents/annual.pdf",
                    )

    # Verify that all three evidence collections are included.
    assert elements == [
        "paragraph-evidence",
        "table-evidence",
        "figure-evidence",
    ]

    # Verify that PDF analysis requests an operation ID.
    analyze.assert_called_once_with(
        file_path="reports/annual.pdf",
        include_operation_id=True,
    )

    # Verify that the original filename is preserved.
    assert paragraphs.call_args.kwargs["filename"] == "annual.pdf"
    assert tables.call_args.kwargs["filename"] == "annual.pdf"

    # Verify that figure conversion receives the operation ID.
    assert figures.call_args.kwargs["operation_id"] == "operation-123"


# Verify that documents without figures can still be ingested.
def test_ingest_document_without_figures():

    # Simulate an analyzed PDF without figures.
    result = SimpleNamespace(figures=[])

    # Replace PDF analysis with a mock.
    with patch(
        "rag.ingestion.multimodal_pipeline.analyze_pdf_layout",
        return_value=(result, "operation-123"),
    ):

        # Replace paragraph conversion with a mock.
        with patch(
            "rag.ingestion.multimodal_pipeline.convert_paragraphs",
            return_value=["text-evidence"],
        ):

            # Replace table conversion with a mock.
            with patch(
                "rag.ingestion.multimodal_pipeline.convert_tables",
                return_value=[],
            ):

                # Replace figure conversion with a mock.
                with patch(
                    "rag.ingestion.multimodal_pipeline.convert_figures",
                    return_value=[],
                ):

                    # Ingest the simulated PDF.
                    elements = ingest_multimodal_pdf(
                        "report.pdf",
                        "REPORT-002",
                        "documents/report.pdf",
                    )

    # Verify that text-only evidence is returned.
    assert elements == ["text-evidence"]


# Reject invalid inputs before starting Azure analysis.
@pytest.mark.parametrize(
    "file_path,document_id,source_uri",
    [
        ("", "REPORT-001", "documents/report.pdf"),
        ("report.pdf", "", "documents/report.pdf"),
        ("report.pdf", "REPORT-001", ""),
        (None, "REPORT-001", "documents/report.pdf"),
    ],
)
def test_ingest_rejects_invalid_inputs(
    file_path,
    document_id,
    source_uri,
):

    # Ensure Azure analysis is never called for invalid inputs.
    with patch(
        "rag.ingestion.multimodal_pipeline.analyze_pdf_layout"
    ) as analyze:

        # Verify that input validation raises an error.
        with pytest.raises(ValueError):
            ingest_multimodal_pdf(
                file_path,
                document_id,
                source_uri,
            )

    # Confirm that no Azure analysis was attempted.
    analyze.assert_not_called()


# Verify that figure processing errors are not silently ignored.
def test_ingest_propagates_figure_failure():

    # Simulate a successfully analyzed PDF.
    result = SimpleNamespace()

    # Replace the Azure analysis operation.
    with patch(
        "rag.ingestion.multimodal_pipeline.analyze_pdf_layout",
        return_value=(result, "operation-123"),
    ):

        # Simulate successful paragraph conversion.
        with patch(
            "rag.ingestion.multimodal_pipeline.convert_paragraphs",
            return_value=[],
        ):

            # Simulate successful table conversion.
            with patch(
                "rag.ingestion.multimodal_pipeline.convert_tables",
                return_value=[],
            ):

                # Simulate a failure when processing figures.
                with patch(
                    "rag.ingestion.multimodal_pipeline.convert_figures",
                    side_effect=RuntimeError("Figure upload failed"),
                ):

                    # Verify that the failure reaches the caller.
                    with pytest.raises(
                        RuntimeError,
                        match="Figure upload failed",
                    ):
                        ingest_multimodal_pdf(
                            "report.pdf",
                            "REPORT-003",
                            "documents/report.pdf",
                        )


# Verify that the pipeline preserves validated multimodal evidence.
def test_ingest_returns_validated_multimodal_elements():

    # Import the actual evidence model.
    from rag.models.multimodal import MultimodalElement

    # Create realistic, validated text evidence.
    text_element = MultimodalElement(
        element_id="REPORT-004-p1-paragraph-0",
        document_id="REPORT-004",
        filename="report.pdf",
        source_uri="documents/report.pdf",
        page_number=1,
        content_type="text",
        content="Annual revenue increased.",
        extraction_method="document-intelligence-layout",
    )

    # Create realistic, validated figure evidence.
    figure_element = MultimodalElement(
        element_id="REPORT-004-p2-figure-0",
        document_id="REPORT-004",
        filename="report.pdf",
        source_uri="documents/report.pdf",
        page_number=2,
        content_type="figure",
        content="Annual revenue chart",
        asset_uri="https://example.blob.core.windows.net/figure.png",
        extraction_method="document-intelligence-layout",
    )

    # Simulate the analyzed document.
    result = SimpleNamespace()

    # Mock PDF analysis and each conversion component.
    with patch(
        "rag.ingestion.multimodal_pipeline.analyze_pdf_layout",
        return_value=(result, "operation-456"),
    ), patch(
        "rag.ingestion.multimodal_pipeline.convert_paragraphs",
        return_value=[text_element],
    ), patch(
        "rag.ingestion.multimodal_pipeline.convert_tables",
        return_value=[],
    ), patch(
        "rag.ingestion.multimodal_pipeline.convert_figures",
        return_value=[figure_element],
    ):

        # Run the unified ingestion workflow.
        elements = ingest_multimodal_pdf(
            "report.pdf",
            "REPORT-004",
            "documents/report.pdf",
        )

    # Verify that the original validated objects are preserved.
    assert elements == [text_element, figure_element]

    # Verify that every returned item uses the evidence model.
    assert all(isinstance(item, MultimodalElement) for item in elements)

    # Verify that figure evidence retains its image reference.
    assert elements[1].asset_uri == figure_element.asset_uri

    # Verify that both original PDF page references survive.
    assert [item.page_number for item in elements] == [1, 2]
