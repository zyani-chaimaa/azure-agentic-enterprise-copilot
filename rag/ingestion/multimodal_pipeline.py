# Import Path to inspect the source document filename.
from pathlib import Path

# Import the validated model for multimodal evidence.
from rag.models.multimodal import MultimodalElement

# Import the Azure Document Intelligence PDF analyzer.
from rag.ingestion.layout_extractor import analyze_pdf_layout

# Import the converters for text, tables, and figures.
from rag.ingestion.layout_converter import (
    convert_paragraphs,
    convert_tables,
    convert_figures,
)


# Coordinate multimodal extraction for one PDF document.
def ingest_multimodal_pdf(
    file_path: str,
    document_id: str,
    source_uri: str,
    strict_vision: bool = False,
) -> list[MultimodalElement]:

    # Require a meaningful document identifier.
    if not isinstance(document_id, str) or not document_id.strip():
        raise ValueError("A valid document_id is required.")

    # Require a meaningful reference to the source PDF.
    if not isinstance(source_uri, str) or not source_uri.strip():
        raise ValueError("A valid source_uri is required.")

    # Require a valid path string.
    if not isinstance(file_path, str) or not file_path.strip():
        raise ValueError("A valid PDF file_path is required.")

    # Extract the filename for future source citations.
    filename = Path(file_path).name

    # Analyze the PDF and retain the operation ID for figure retrieval.
    result, operation_id = analyze_pdf_layout(
        file_path=file_path,
        include_operation_id=True,
    )

    # Convert PDF paragraphs into structured text evidence.
    paragraphs = convert_paragraphs(
        result=result,
        document_id=document_id,
        filename=filename,
        source_uri=source_uri,
    )

    # Convert PDF tables into structured table evidence.
    tables = convert_tables(
        result=result,
        document_id=document_id,
        filename=filename,
        source_uri=source_uri,
    )

    # Convert PDF figures and store their original images.
    figures = convert_figures(
        result=result,
        operation_id=operation_id,
        document_id=document_id,
        filename=filename,
        source_uri=source_uri,
        strict_vision=strict_vision,
    )

    # Combine the evidence from all supported content types.
    elements = paragraphs + tables + figures

    # Validate every element before allowing downstream indexing.
    validated_elements = []

    # Inspect each extracted record independently.
    for index, element in enumerate(elements):

        # Reject unexpected object types instead of silently accepting them.
        if not isinstance(element, MultimodalElement):
            raise TypeError(
                f"Invalid evidence at position {index}: "
                "expected MultimodalElement."
            )

        # Revalidate the object's current fields against its Pydantic schema.
        validated = MultimodalElement.model_validate(
            element.model_dump()
        )

        # Prevent evidence from another document entering this ingestion.
        if validated.document_id != document_id:
            raise ValueError(
                f"Evidence {validated.element_id} belongs to "
                "a different document."
            )

        # Preserve the validated evidence.
        validated_elements.append(validated)

    # Return only validated evidence for downstream indexing.
    return validated_elements
