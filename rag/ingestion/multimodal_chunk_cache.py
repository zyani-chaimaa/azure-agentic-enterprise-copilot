# Import JSON for storing extracted chunks.
import json

# Import operating-system functions for safe file replacement.
import os

# Import temporary-file creation.
import tempfile

# Import Path for filesystem operations.
from pathlib import Path

# Import our validated multimodal chunk model.
from rag.models.multimodal_chunk import MultimodalChunk


# Save extracted chunks so future retries can skip PDF extraction.
def save_chunk_cache(
    cache_path: str | Path,
    document_id: str,
    fingerprint: str,
    chunks: list[MultimodalChunk],
) -> None:

    # Convert the destination into a filesystem path.
    path = Path(cache_path)

    # Ensure the destination directory exists.
    path.parent.mkdir(parents=True, exist_ok=True)

    # Validate every chunk before writing it.
    validated_chunks = [
        MultimodalChunk.model_validate(chunk) for chunk in chunks
    ]

    # Ensure all chunks belong to the requested document.
    if any(chunk.document_id != document_id for chunk in validated_chunks):
        raise ValueError("Chunk cache document_id does not match.")

    # Build the JSON cache with its identity and fingerprint.
    payload = {
        "document_id": document_id,
        "fingerprint": fingerprint,
        "chunks": [
            chunk.model_dump(mode="json") for chunk in validated_chunks
        ],
    }

    # Track the temporary file for cleanup.
    temporary_path = None

    # Write the cache safely before replacing the destination.
    try:

        # Create a temporary file in the same directory.
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as temporary_file:

            # Remember the temporary file's location.
            temporary_path = Path(temporary_file.name)

            # Write the cache as readable JSON.
            json.dump(payload, temporary_file, ensure_ascii=False)

            # Flush Python's buffered data.
            temporary_file.flush()

            # Flush the data to disk.
            os.fsync(temporary_file.fileno())

        # Atomically replace the previous cache.
        os.replace(temporary_path, path)

    # Remove any leftover temporary file.
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


# Load previously extracted chunks if the cache is valid.
def load_chunk_cache(
    cache_path: str | Path,
    document_id: str,
    fingerprint: str,
) -> list[MultimodalChunk] | None:

    # Convert the cache location into a filesystem path.
    path = Path(cache_path)

    # Return None when extraction has not yet been cached.
    if not path.is_file():
        return None

    # Read the cached JSON.
    with path.open("r", encoding="utf-8") as cache_file:
        payload = json.load(cache_file)

    # Require a JSON object.
    if not isinstance(payload, dict):
        raise ValueError("Invalid chunk cache: expected an object.")

    # Reject a cache belonging to a different document.
    if payload.get("document_id") != document_id:
        raise ValueError("Chunk cache document_id does not match.")

    # Reject a cache created from different PDF contents or settings.
    if payload.get("fingerprint") != fingerprint:
        raise ValueError("Chunk cache fingerprint does not match.")

    # Require a nonempty list of chunks.
    stored_chunks = payload.get("chunks")
    if not isinstance(stored_chunks, list) or not stored_chunks:
        raise ValueError("Invalid chunk cache: no chunks found.")

    # Reconstruct and validate each stored chunk.
    chunks = [
        MultimodalChunk.model_validate(chunk) for chunk in stored_chunks
    ]

    # Verify that every reconstructed chunk belongs to this document.
    if any(chunk.document_id != document_id for chunk in chunks):
        raise ValueError("Chunk cache contains another document.")

    # Return the validated chunks without repeating PDF extraction.
    return chunks
