# Import Python logging for figure-analysis diagnostics.
import logging

# Create a logger for document element conversion.
logger = logging.getLogger(__name__)

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


# Convert extracted PDF figures into traceable multimodal evidence.
def convert_figures(
    result,
    operation_id: str,
    document_id: str,
    filename: str,
    source_uri: str,
) -> list[MultimodalElement]:

    # Import image retrieval only when figure conversion is requested.
    from rag.ingestion.figure_extractor import retrieve_figure_image

    # Import GPT-5.4-mini visual analysis for extracted figures.
    from rag.ingestion.figure_analyzer import analyze_figure_image

    # Import the Azure Blob Storage upload function.
    from rag.ingestion.blob_storage import upload_figure_image

    # Collect the validated figure evidence.
    elements = []

    # Process each figure identified by Document Intelligence.
    for index, figure in enumerate(result.figures or []):

        # Read the figure's unique Azure identifier.
        figure_id = getattr(figure, "id", None)

        # Skip figures without a retrievable identifier.
        if not figure_id:
            continue

        # Retrieve the figure's original page references.
        regions = figure.bounding_regions or []

        # Skip figures without a reliable source page.
        if not regions:
            continue

        # Collect distinct, valid source page numbers.
        page_numbers = sorted({
            region.page_number
            for region in regions
            if isinstance(region.page_number, int)
            and not isinstance(region.page_number, bool)
            and region.page_number >= 1
        })

        # Skip figures with no valid source page.
        if not page_numbers:
            continue

        # Read the caption when Azure provides one.
        caption = getattr(figure, "caption", None)

        # Extract caption text without assuming a caption exists.
        caption_text = (
            (getattr(caption, "content", None) or "").strip()
        )

        # Use a neutral description when no caption is available.
        content = caption_text or f"Figure {figure_id}"

        # Retrieve the image only once for this figure.
        image_bytes = retrieve_figure_image(
            operation_id=operation_id,
            figure_id=figure_id,
        )

        # Analyze the extracted figure before creating searchable evidence.
        try:
            # Ask the vision model to describe the visual content.
            visual_description = analyze_figure_image(image_bytes)

            # Preserve the original caption alongside the visual description.
            content = (
                f"{caption_text}\n\n{visual_description}"
                if caption_text
                else visual_description
            )

        # Keep ingestion functional if visual analysis fails.
        except Exception:
            # Record the failure with its source document and figure identifier.
            logger.exception(
                "Vision analysis failed for document_id=%s figure_id=%s; "
                "using caption fallback",
                document_id,
                figure_id,
            )

            # Preserve the original caption or neutral figure identifier.
            content = caption_text or f"Figure {figure_id}"

        # Associate the image with its first referenced page.
        primary_page = page_numbers[0]

        # Upload the image to the configured private storage container.
        asset_uri = upload_figure_image(
            image_bytes=image_bytes,
            document_id=document_id,
            page_number=primary_page,
            figure_id=figure_id,
        )

        # Create evidence for each page referenced by the figure.
        for page_number in page_numbers:

            # Build a stable, page-specific evidence identifier.
            element_id = (
                f"{document_id}-p{page_number}-figure-{index}"
            )

            # Validate the extracted figure against NEXORA's model.
            element = MultimodalElement(
                element_id=element_id,
                document_id=document_id,
                filename=filename,
                source_uri=source_uri,
                page_number=page_number,
                content_type="figure",
                content=content,
                asset_uri=asset_uri,
                extraction_method="document-intelligence-layout",
            )

            # Add the figure evidence to the collection.
            elements.append(element)

    # Return the converted figure evidence.
    return elements
