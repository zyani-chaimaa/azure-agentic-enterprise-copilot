# Import pytest for exception testing.
import pytest

# Import mock utilities to isolate external Azure dependencies.
from unittest.mock import patch, sentinel

# Import the client factory we want to test.
from rag.ingestion.layout_extractor import create_document_intelligence_client


# Verify that a missing Azure endpoint produces a clear error.
def test_missing_document_intelligence_endpoint():

    # Simulate an environment without a configured endpoint.
    with patch(
        "rag.ingestion.layout_extractor.settings.azure_document_intelligence_endpoint",
        "",
    ):

        # Confirm that the client factory rejects missing configuration.
        with pytest.raises(ValueError, match="not configured"):
            create_document_intelligence_client()


# Verify that a configured endpoint creates an authenticated client.
def test_document_intelligence_client_configuration():

    # Use a fake endpoint without connecting to Azure.
    endpoint = "https://example.cognitiveservices.azure.com/"

    # Replace the real Azure credential provider with a mock.
    with patch(
        "rag.ingestion.layout_extractor.DefaultAzureCredential"
    ) as mock_credential:

        # Replace the real Azure client with a mock.
        with patch(
            "rag.ingestion.layout_extractor.DocumentIntelligenceClient"
        ) as mock_client:

            # Supply a fake endpoint through our application settings.
            with patch(
                "rag.ingestion.layout_extractor.settings.azure_document_intelligence_endpoint",
                endpoint,
            ):

                # Call the client factory.
                result = create_document_intelligence_client()

                # Verify that interactive browser authentication is disabled.
                mock_credential.assert_called_once_with(
                    exclude_interactive_browser_credential=True
                )

                # Verify that the correct endpoint and credential are used.
                mock_client.assert_called_once_with(
                    endpoint=endpoint,
                    credential=mock_credential.return_value,
                )

                # Verify that the factory returns the created client.
                assert result is mock_client.return_value


# Import the PDF analysis function for validation testing.
from rag.ingestion.layout_extractor import analyze_pdf_layout


# Verify that a nonexistent PDF is rejected.
def test_analyze_pdf_missing_file(tmp_path):

    # Create a path that does not point to an existing file.
    missing_pdf = tmp_path / "missing.pdf"

    # Confirm that analysis fails before contacting Azure.
    with pytest.raises(FileNotFoundError, match="PDF file not found"):
        analyze_pdf_layout(str(missing_pdf))


# Verify that unsupported file formats are rejected.
def test_analyze_pdf_rejects_non_pdf(tmp_path):

    # Create a real text file in pytest's temporary directory.
    text_file = tmp_path / "example.txt"

    # Write sample content into the temporary file.
    text_file.write_text("This is not a PDF.")

    # Confirm that only PDF files are accepted.
    with pytest.raises(ValueError, match="Only PDF files are supported"):
        analyze_pdf_layout(str(text_file))


# Verify that PDF analysis sends the correct request to Azure.
def test_analyze_pdf_success(tmp_path):

    # Create a temporary PDF file for testing.
    pdf_path = tmp_path / "sample.pdf"

    # Write minimal test bytes without requiring a real PDF parser.
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")

    # Replace the Azure client factory with a mock.
    with patch(
        "rag.ingestion.layout_extractor.create_document_intelligence_client"
    ) as mock_factory:

        # Obtain the simulated Azure client.
        mock_client = mock_factory.return_value

        # Configure the simulated analysis result.
        expected_result = sentinel.analysis_result

        # Make the simulated poller return that result.
        mock_client.begin_analyze_document.return_value.result.return_value = (
            expected_result
        )

        # Analyze the temporary PDF using our function.
        result = analyze_pdf_layout(str(pdf_path))

        # Verify that Azure analysis was requested exactly once.
        mock_client.begin_analyze_document.assert_called_once()

        # Inspect the arguments passed to the Azure SDK.
        request = mock_client.begin_analyze_document.call_args

        # Verify that NEXORA uses the configured layout model.
        assert request.kwargs["model_id"] == "prebuilt-layout"

        # Verify that the PDF content type is correctly specified.
        assert request.kwargs["content_type"] == "application/pdf"

        # Verify that Azure is asked to generate extractable figure images.
        assert request.kwargs["output"] == ["figures"]

        # Verify that the PDF file was supplied as binary input.
        assert request.kwargs["body"].mode == "rb"

        # Verify that the PDF file is closed after analysis.
        assert request.kwargs["body"].closed

        # Verify that the function returns the Azure analysis result.
        assert result is expected_result


# Verify that callers can retrieve the Azure analysis operation ID.
def test_analyze_pdf_returns_operation_id(tmp_path):

    # Create a temporary PDF for the mocked analysis.
    pdf_path = tmp_path / "report.pdf"

    # Write minimal PDF-like bytes; Azure is mocked in this test.
    pdf_path.write_bytes(b"%PDF-1.4\n%%EOF")

    # Replace the real Azure client factory with a mock.
    with patch(
        "rag.ingestion.layout_extractor.create_document_intelligence_client"
    ) as mock_factory:

        # Access the simulated Azure client.
        mock_client = mock_factory.return_value

        # Access the simulated long-running operation poller.
        mock_poller = mock_client.begin_analyze_document.return_value

        # Define the expected analysis result.
        expected_result = sentinel.analysis_result

        # Make the simulated poller return our analysis result.
        mock_poller.result.return_value = expected_result

        # Simulate Azure's operation metadata.
        mock_poller.details = {"operation_id": "azure-operation-123"}

        # Request both the analysis result and operation ID.
        result, operation_id = analyze_pdf_layout(
            str(pdf_path),
            include_operation_id=True,
        )

        # Verify that the original analysis result is preserved.
        assert result is expected_result

        # Verify that the correct Azure operation ID is returned.
        assert operation_id == "azure-operation-123"

        # Verify that Azure was asked to generate figure images.
        assert mock_client.begin_analyze_document.call_args.kwargs[
            "output"
        ] == ["figures"]
