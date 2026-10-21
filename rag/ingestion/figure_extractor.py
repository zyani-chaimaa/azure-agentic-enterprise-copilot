# Import the existing authenticated Azure client factory.
from rag.ingestion.layout_extractor import create_document_intelligence_client

# Import NEXORA's centralized Azure configuration.
from app.config import settings


# Retrieve the original image bytes of a figure extracted from a PDF.
def retrieve_figure_image(
    operation_id: str,
    figure_id: str,
) -> bytes:

    # Reject missing or whitespace-only operation identifiers.
    if not operation_id or not operation_id.strip():
        raise ValueError("A valid Azure analysis operation ID is required.")

    # Reject missing or whitespace-only figure identifiers.
    if not figure_id or not figure_id.strip():
        raise ValueError("A valid figure ID is required.")

    # Create an authenticated Document Intelligence client.
    client = create_document_intelligence_client()

    # Request the image using the model and analysis identifiers.
    image_chunks = client.get_analyze_result_figure(
        model_id=settings.azure_document_intelligence_model,
        result_id=operation_id,
        figure_id=figure_id,
    )

    # Combine the streamed binary chunks into one image.
    image_bytes = b"".join(image_chunks)

    # Reject an empty response rather than storing an invalid image.
    if not image_bytes:
        raise ValueError("Azure returned an empty figure image.")

    # Return the image bytes for later storage in Azure Blob Storage.
    return image_bytes
