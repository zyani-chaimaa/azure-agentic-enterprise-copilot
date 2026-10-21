# Import SimpleNamespace to simulate Azure SDK response objects.
from types import SimpleNamespace

# Import the paragraph converter we want to test.
from rag.ingestion.layout_converter import convert_paragraphs


# Build a simulated Azure paragraph with optional page information.
def make_paragraph(content, page_number=1, role=None):

    # Create a page reference when a page number is provided.
    regions = (
        [SimpleNamespace(page_number=page_number)]
        if page_number is not None
        else []
    )

    # Return a simulated paragraph containing Azure's expected fields.
    return SimpleNamespace(
        content=content,
        role=role,
        bounding_regions=regions,
    )


# Convert a list of simulated paragraphs into NEXORA elements.
def convert_test_paragraphs(paragraphs):

    # Simulate the overall Azure Document Intelligence response.
    result = SimpleNamespace(paragraphs=paragraphs)

    # Call the converter with consistent document metadata.
    return convert_paragraphs(
        result=result,
        document_id="REPORT-001",
        filename="annual_report.pdf",
        source_uri="documents/annual_report.pdf",
    )


# Verify that ordinary paragraphs preserve their source metadata.
def test_convert_regular_paragraph():

    # Simulate a paragraph found on page five.
    elements = convert_test_paragraphs([
        make_paragraph("Revenue increased by 12%.", page_number=5)
    ])

    # Verify that one searchable text element was produced.
    assert len(elements) == 1

    # Verify that its text and original page are preserved.
    assert elements[0].content == "Revenue increased by 12%."
    assert elements[0].page_number == 5
    assert elements[0].content_type == "text"
    assert elements[0].document_id == "REPORT-001"


# Verify that section headings are attached to following paragraphs.
def test_convert_section_heading():

    # Simulate a heading followed by an ordinary paragraph.
    elements = convert_test_paragraphs([
        make_paragraph("Financial Performance", role="sectionHeading"),
        make_paragraph("Total revenue increased."),
    ])

    # Verify that the second paragraph inherits the heading.
    assert elements[1].section_heading == "Financial Performance"


# Verify that empty paragraphs are ignored.
def test_skip_empty_paragraph():

    # Simulate whitespace-only extracted content.
    elements = convert_test_paragraphs([
        make_paragraph("   "),
    ])

    # Empty content must not become a searchable element.
    assert elements == []


# Verify that paragraphs without page references are excluded.
def test_skip_paragraph_without_page():

    # Simulate content without a reliable source page.
    elements = convert_test_paragraphs([
        make_paragraph("Unlocated content", page_number=None),
    ])

    # Avoid creating evidence with an unsupported citation.
    assert elements == []


# Import the new table conversion function.
from rag.ingestion.layout_converter import convert_tables


# Build a simulated Azure table cell.
def make_cell(row, column, content, row_span=1, column_span=1):

    # Return the cell with its position and merged-cell dimensions.
    return SimpleNamespace(
        row_index=row,
        column_index=column,
        content=content,
        row_span=row_span,
        column_span=column_span,
    )


# Convert simulated Azure tables into NEXORA elements.
def convert_test_tables(tables):

    # Create a simulated Document Intelligence analysis result.
    result = SimpleNamespace(tables=tables)

    # Convert the tables using consistent document metadata.
    return convert_tables(
        result=result,
        document_id="REPORT-001",
        filename="annual_report.pdf",
        source_uri="documents/annual_report.pdf",
    )


# Verify that financial table values retain their row and column positions.
def test_convert_financial_table():

    # Create a two-row financial table on page seven.
    table = SimpleNamespace(
        row_count=2,
        column_count=2,
        cells=[
            make_cell(0, 0, "Year"),
            make_cell(0, 1, "Revenue"),
            make_cell(1, 0, "2025"),
            make_cell(1, 1, "$15M"),
        ],
        bounding_regions=[SimpleNamespace(page_number=7)],
    )

    # Convert the simulated table.
    elements = convert_test_tables([table])

    # Verify that one table element is produced on the correct page.
    assert len(elements) == 1
    assert elements[0].content_type == "table"
    assert elements[0].page_number == 7

    # Verify that the financial value retains its exact cell position.
    assert "Row 2, Column 2, Row span 1, Column span 1: $15M" in elements[0].content


# Verify that merged table cells preserve their spans.
def test_convert_merged_cell():

    # Create a table with a heading spanning two columns.
    table = SimpleNamespace(
        row_count=1,
        column_count=2,
        cells=[make_cell(0, 0, "Financial Results", column_span=2)],
        bounding_regions=[SimpleNamespace(page_number=3)],
    )

    # Convert the merged-cell table.
    elements = convert_test_tables([table])

    # Verify that the merged column span is preserved.
    assert "Column span 2: Financial Results" in elements[0].content


# Verify that tables without source pages are not indexed.
def test_skip_table_without_page():

    # Create a table with no reliable page reference.
    table = SimpleNamespace(
        row_count=1,
        column_count=1,
        cells=[make_cell(0, 0, "Revenue")],
        bounding_regions=[],
    )

    # Attempt to convert the table.
    elements = convert_test_tables([table])

    # Avoid producing evidence with an unsupported citation.
    assert elements == []


# Import patch to simulate image retrieval and storage.
from unittest.mock import patch

# Import the figure converter being tested.
from rag.ingestion.layout_converter import convert_figures


# Build a simulated Document Intelligence figure.
def make_figure(figure_id="1.1", pages=(1,), caption="Revenue chart"):

    # Create the figure's source-page references.
    regions = [
        SimpleNamespace(page_number=page)
        for page in pages
    ]

    # Create a caption object when caption text is available.
    caption_object = (
        SimpleNamespace(content=caption)
        if caption is not None
        else None
    )

    # Return simulated Azure figure metadata.
    return SimpleNamespace(
        id=figure_id,
        bounding_regions=regions,
        caption=caption_object,
    )


# Convert figures while replacing Azure operations with mocks.
def convert_test_figures(figures):

    # Simulate the document analysis result.
    result = SimpleNamespace(figures=figures)

    # Replace the actual figure download with a mock.
    with patch(
        "rag.ingestion.figure_extractor.retrieve_figure_image",
        return_value=b"image-data",
    ) as mock_retrieve:

        # Replace the actual Blob Storage upload with a mock.
        with patch(
            "rag.ingestion.blob_storage.upload_figure_image",
            return_value="https://example.blob.core.windows.net/figure.png",
        ) as mock_upload:

            # Convert the simulated figures.
            elements = convert_figures(
                result=result,
                operation_id="operation-123",
                document_id="REPORT-001",
                filename="annual_report.pdf",
                source_uri="documents/annual_report.pdf",
            )

            # Return evidence and mocks for verification.
            return elements, mock_retrieve, mock_upload


# Verify that a captioned figure becomes searchable evidence.
def test_convert_captioned_figure():

    # Convert a figure from page five.
    elements, retrieve, upload = convert_test_figures([
        make_figure(pages=(5,), caption="Revenue increased by 12%.")
    ])

    # Verify the figure's searchable caption and source page.
    assert len(elements) == 1
    assert elements[0].content_type == "figure"
    assert elements[0].content == "Revenue increased by 12%."
    assert elements[0].page_number == 5

    # Verify that the stored image URI is preserved.
    assert elements[0].asset_uri.endswith("figure.png")

    # Verify that image retrieval uses the Azure identifiers.
    retrieve.assert_called_once_with(
        operation_id="operation-123",
        figure_id="1.1",
    )

    # Verify that the original image is uploaded with source metadata.
    upload.assert_called_once_with(
        image_bytes=b"image-data",
        document_id="REPORT-001",
        page_number=5,
        figure_id="1.1",
    )


# Verify that figures without captions remain traceable.
def test_convert_figure_without_caption():

    # Convert a figure with no caption.
    elements, _, _ = convert_test_figures([
        make_figure(caption=None)
    ])

    # Verify that a neutral searchable description is provided.
    assert len(elements) == 1
    assert elements[0].content == "Figure 1.1"


# Verify that multi-page figures are downloaded and uploaded only once.
def test_convert_multipage_figure():

    # Convert one figure referencing pages three and four.
    elements, retrieve, upload = convert_test_figures([
        make_figure(pages=(4, 3, 4))
    ])

    # Verify that evidence references both distinct pages.
    assert [element.page_number for element in elements] == [3, 4]

    # Verify that the image is retrieved and uploaded only once.
    retrieve.assert_called_once()
    upload.assert_called_once()


# Verify that invalid figure metadata does not trigger Azure operations.
def test_convert_figures_with_invalid_metadata():

    # Supply figures without an ID or valid page reference.
    elements, retrieve, upload = convert_test_figures([
        make_figure(figure_id=None),
        make_figure(pages=()),
        make_figure(pages=(0, -1)),
    ])

    # Verify that no unsupported evidence is produced.
    assert elements == []

    # Verify that invalid figures do not trigger Azure requests.
    retrieve.assert_not_called()
    upload.assert_not_called()
