# Import the validated model used to represent extracted evidence.
from rag.models.multimodal import MultimodalElement


# Convert Azure Document Intelligence paragraphs into NEXORA elements.
def convert_paragraphs(
    result,
    document_id: str,
    filename: str,
    source_uri: str,
) -> list[MultimodalElement]:

    # Store the converted paragraphs in their original reading order.
    elements = []

    # Remember the latest section heading for subsequent paragraphs.
    current_heading = None

    # Process every paragraph returned by Azure Document Intelligence.
    for index, paragraph in enumerate(result.paragraphs or []):

        # Remove surrounding whitespace from the extracted text.
        content = (paragraph.content or "").strip()

        # Ignore paragraphs that contain no meaningful text.
        if not content:
            continue

        # Identify section headings using Azure's semantic role.
        if paragraph.role == "sectionHeading":
            current_heading = content

        # Retrieve the paragraph's page-location information.
        regions = paragraph.bounding_regions or []

        # Skip paragraphs without a reliable page reference.
        if not regions:
            continue

        # Preserve every distinct page covered by the paragraph.
        page_numbers = sorted({region.page_number for region in regions})

        # Create one traceable element for each referenced page.
        for page_number in page_numbers:

            # Build a stable identifier from the document and paragraph position.
            element_id = f"{document_id}-p{page_number}-paragraph-{index}"

            # Convert the paragraph into our validated multimodal model.
            element = MultimodalElement(
                element_id=element_id,
                document_id=document_id,
                filename=filename,
                source_uri=source_uri,
                page_number=page_number,
                content_type="text",
                content=content,
                section_heading=current_heading,
                extraction_method="document-intelligence-layout",
            )

            # Add the converted paragraph to the result collection.
            elements.append(element)

    # Return all converted paragraphs.
    return elements


# Convert Azure Document Intelligence tables into searchable elements.
def convert_tables(
    result,
    document_id: str,
    filename: str,
    source_uri: str,
) -> list[MultimodalElement]:

    # Collect the converted tables.
    elements = []

    # Process each table returned by Document Intelligence.
    for table_index, table in enumerate(result.tables or []):

        # Read the original page references for this table.
        regions = table.bounding_regions or []

        # Skip tables without a reliable source page.
        if not regions:
            continue

        # Collect distinct page numbers in ascending order.
        page_numbers = sorted({region.page_number for region in regions})

        # Describe the table dimensions.
        lines = [
            f"Table with {table.row_count} rows and "
            f"{table.column_count} columns."
        ]

        # Process cells in row-major order.
        cells = sorted(
            table.cells,
            key=lambda cell: (cell.row_index, cell.column_index),
        )

        # Preserve each cell's position, content, and merged-cell spans.
        for cell in cells:

            # Remove unnecessary surrounding whitespace.
            value = (cell.content or "").strip()

            # Record how many rows and columns the cell occupies.
            row_span = cell.row_span or 1
            column_span = cell.column_span or 1

            # Build a searchable description of the cell.
            lines.append(
                f"Row {cell.row_index + 1}, "
                f"Column {cell.column_index + 1}, "
                f"Row span {row_span}, "
                f"Column span {column_span}: {value}"
            )

        # Combine the cell descriptions into searchable text.
        content = "\n".join(lines)

        # Create a traceable element for every referenced page.
        for page_number in page_numbers:

            # Identify the original table and its source page.
            element_id = f"{document_id}-p{page_number}-table-{table_index}"

            # Construct a validated multimodal table element.
            element = MultimodalElement(
                element_id=element_id,
                document_id=document_id,
                filename=filename,
                source_uri=source_uri,
                page_number=page_number,
                content_type="table",
                content=content,
                extraction_method="document-intelligence-layout",
            )

            # Add the table element to our collection.
            elements.append(element)

    # Return all converted tables.
    return elements
