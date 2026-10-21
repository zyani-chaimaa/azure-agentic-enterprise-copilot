# Import the Azure identity provider for passwordless authentication.
import re
from time import sleep

from azure.core.exceptions import HttpResponseError
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

    # Validate document keys before creating Azure credentials.
    seen_chunk_ids = set()

    # Inspect each chunk identifier for Azure AI Search compatibility.
    for chunk in chunks:

        # Require a key containing only supported characters.
        if not re.fullmatch(r"[A-Za-z0-9_=-]+", chunk.chunk_id):
            raise ValueError(
                f"Invalid Azure AI Search chunk_id: {chunk.chunk_id}"
            )

        # Reject duplicate keys to prevent accidental overwrites.
        if chunk.chunk_id in seen_chunk_ids:
            raise ValueError(
                f"Duplicate multimodal chunk_id: {chunk.chunk_id}"
            )

        # Remember this key for subsequent duplicate detection.
        seen_chunk_ids.add(chunk.chunk_id)

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

        # Allow three attempts for temporary Azure service failures.
        max_attempts = 3

        # Retry only HTTP statuses that can represent transient failures.
        retryable_statuses = {408, 429, 500, 502, 503, 504}

        # Upload the same embedded document on every retry.
        for attempt in range(1, max_attempts + 1):

            # Attempt to upload this chunk to Azure AI Search v2.
            try:
                results = client.upload_documents(
                    documents=[search_document]
                )

            # Handle HTTP failures returned by the Azure SDK.
            except HttpResponseError as exc:

                # Read the HTTP status without assuming a response exists.
                status_code = exc.status_code

                # Propagate permanent failures without retrying.
                if status_code not in retryable_statuses:
                    raise

                # Report an exhausted retry budget with the chunk ID.
                if attempt == max_attempts:
                    raise RuntimeError(
                        f"Failed to index multimodal chunk after "
                        f"{max_attempts} attempts: {chunk.chunk_id}"
                    ) from exc

                # Wait progressively longer before retrying.
                sleep(2 ** (attempt - 1))

                # Continue with the next attempt.
                continue

            # Reject missing or unsuccessful upload results.
            if (
                not results
                or len(results) != 1
                or not results[0].succeeded
            ):
                raise RuntimeError(
                    f"Failed to index multimodal chunk: {chunk.chunk_id}"
                )

            # Stop retrying after a successful upload.
            break

        # Update the successful upload count.
        uploaded += 1

        # Display progress during long ingestion runs.
        print(
            f"Indexed {uploaded}/{len(chunks)}: {chunk.chunk_id}",
            flush=True,
        )

    # Return the total number of successfully uploaded chunks.
    return uploaded
