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
