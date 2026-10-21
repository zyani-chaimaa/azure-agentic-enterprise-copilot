# Import the Azure identity provider for passwordless authentication.
from azure.identity import DefaultAzureCredential

# Import the Azure AI Search document upload client.
from azure.search.documents import SearchClient

# Import centralized Azure configuration.
from app.config import settings

# Import the validated multimodal chunk model.
from rag.models.multimodal_chunk import MultimodalChunk

# Import our tested multimodal embedding adapter.
from rag.ingestion.multimodal_embedder import embed_multimodal_chunk


# Embed and index validated multimodal chunks in Azure AI Search v2.
def index_multimodal_chunks(chunks: list[MultimodalChunk]) -> int:

    # Reject an empty collection before connecting to Azure.
    if not chunks:
        raise ValueError("No multimodal chunks were provided.")

    # Verify every input before making any Azure requests.
    for chunk in chunks:

        # Reject objects that are not validated multimodal chunks.
        if not isinstance(chunk, MultimodalChunk):
            raise TypeError("Every item must be a MultimodalChunk.")

    # Require a configured Azure AI Search endpoint.
    if not settings.azure_search_endpoint:
        raise ValueError("AZURE_SEARCH_ENDPOINT is not configured.")

    # Protect the existing text-only search index.
    if settings.azure_multimodal_search_index == settings.azure_search_index:
        raise ValueError(
            "Multimodal index must differ from the existing v1 index."
        )

    # Create credentials using Azure CLI or Managed Identity.
    credential = DefaultAzureCredential(
        exclude_interactive_browser_credential=True
    )

    # Connect exclusively to the multimodal v2 index.
    client = SearchClient(
        endpoint=settings.azure_search_endpoint,
        index_name=settings.azure_multimodal_search_index,
        credential=credential,
    )

    # Track successfully indexed chunks.
    uploaded = 0

    # Process chunks individually to respect embedding quotas.
    for chunk in chunks:

        # Generate an embedding and preserve all source metadata.
        search_document = embed_multimodal_chunk(chunk)

        # Upload one document to Azure AI Search v2.
        results = client.upload_documents(
            documents=[search_document]
        )

        # Reject missing or unsuccessful upload results.
        if (
            not results
            or len(results) != 1
            or not results[0].succeeded
        ):
            raise RuntimeError(
                f"Failed to index multimodal chunk: {chunk.chunk_id}"
            )

        # Update the successful upload count.
        uploaded += 1

        # Display progress during long ingestion runs.
        print(
            f"Indexed {uploaded}/{len(chunks)}: {chunk.chunk_id}",
            flush=True,
        )

    # Return the total number of successfully uploaded chunks.
    return uploaded
