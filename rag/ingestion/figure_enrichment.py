# Import JSON to read existing multimodal chunk caches.
import json

# Import Path to locate cached chunk files.
from pathlib import Path

# Import the validated multimodal chunk model.
from rag.models.multimodal_chunk import MultimodalChunk


# Select existing figure chunks for a specific document and page.
def select_figure_chunks(
    cache_path: str | Path,
    document_id: str,
    page_number: int,
) -> list[MultimodalChunk]:

    # Reject missing document identifiers.
    if not isinstance(document_id, str) or not document_id.strip():
        raise ValueError("A valid document_id is required.")

    # Require a positive page number and reject booleans.
    if type(page_number) is not int or page_number < 1:
        raise ValueError("page_number must be a positive integer.")

    # Resolve the existing chunk cache location.
    path = Path(cache_path)

    # Require the cache to exist before reading it.
    if not path.is_file():
        raise FileNotFoundError(f"Chunk cache not found: {path}")

    # Load the cached JSON without modifying the file.
    cache = json.loads(path.read_text(encoding="utf-8"))

    # Require the expected cache structure.
    if not isinstance(cache, dict) or not isinstance(cache.get("chunks"), list):
        raise ValueError("Invalid multimodal chunk cache structure.")

    # Prevent selecting records from an unexpected document.
    if cache.get("document_id") != document_id:
        raise ValueError("Chunk cache document_id does not match.")

    # Collect validated figure chunks for the requested page.
    selected = []

    # Inspect each cached chunk.
    for record in cache["chunks"]:

        # Skip non-dictionary cache entries.
        if not isinstance(record, dict):
            raise ValueError("Invalid chunk record in cache.")

        # Ignore records outside the requested page or content type.
        if record.get("page_number") != page_number or record.get("content_type") != "figure":
            continue

        # Validate the original chunk and all its source metadata.
        chunk = MultimodalChunk.model_validate(record)

        # Reject inconsistent document identifiers.
        if chunk.document_id != document_id:
            raise ValueError("Figure chunk belongs to an unexpected document.")

        # Preserve the original chunk for later enrichment.
        selected.append(chunk)

    # Return figure chunks in their original cached order.
    return selected


# Import the existing secure Azure Blob figure downloader.
from rag.ingestion.blob_storage import download_figure_image

# Import NEXORA's tested GPT-5.4-mini figure analyzer.
from rag.ingestion.figure_analyzer import analyze_figure_image


# Enrich one figure chunk without modifying the original chunk or search index.
def enrich_figure_chunk(chunk: MultimodalChunk) -> MultimodalChunk:

    # Require a validated multimodal chunk.
    if not isinstance(chunk, MultimodalChunk):
        raise TypeError("Expected a MultimodalChunk.")

    # Restrict this operation to figure chunks.
    if chunk.content_type != "figure":
        raise ValueError("Only figure chunks can be enriched.")

    # Require an existing image reference.
    if not chunk.asset_uri:
        raise ValueError("Figure chunk must have an asset_uri.")

    # Download the previously extracted image from Azure Blob Storage.
    image_bytes = download_figure_image(chunk.asset_uri)

    # Generate a searchable description of the actual visual content.
    description = analyze_figure_image(image_bytes)

    # Reject empty or whitespace-only descriptions.
    if not isinstance(description, str) or not description.strip():
        raise ValueError("Figure analysis returned an empty description.")

    # Preserve the original figure caption alongside the new description.
    enriched_content = f"{chunk.content}\n\nVisual description:\n{description.strip()}"

    # Create a new validated chunk while preserving all original metadata.
    enriched_chunk = chunk.model_copy(
        update={"content": enriched_content}
    )

    # Revalidate the updated content and all inherited metadata.
    enriched_chunk = MultimodalChunk.model_validate(
        enriched_chunk.model_dump()
    )

    # Return the enriched chunk without embedding or indexing it.
    return enriched_chunk
