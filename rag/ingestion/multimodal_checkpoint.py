# Import JSON serialization for checkpoint storage.
import json

# Import filesystem operations for atomic file replacement.
import os

# Import temporary-file creation for safe checkpoint writes.
import tempfile

# Import Path for filesystem path handling.
from pathlib import Path


# Save the completed chunks for one document.
def save_checkpoint(
    checkpoint_path: str | Path,
    document_id: str,
    completed_chunk_ids: list[str],
    fingerprint: str | None = None,
) -> None:

    # Convert the supplied checkpoint location into a Path.
    path = Path(checkpoint_path)

    # Reject an empty document identifier.
    if not isinstance(document_id, str) or not document_id.strip():
        raise ValueError("A valid document_id is required.")

    # Create the parent directory if it does not exist.
    path.parent.mkdir(parents=True, exist_ok=True)

    # Build the checkpoint data that will be stored as JSON.
    checkpoint = {
        "document_id": document_id,
        "completed_chunk_ids": sorted(set(completed_chunk_ids)),
        "fingerprint": fingerprint,
    }

    # Track the temporary file so it can be cleaned up after errors.
    temporary_path = None

    # Write the checkpoint safely before replacing the destination.
    try:

        # Create a temporary file in the destination directory.
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

            # Serialize the checkpoint into readable JSON.
            json.dump(checkpoint, temporary_file, indent=2)

            # Ensure Python's buffered data reaches the operating system.
            temporary_file.flush()

            # Request that the operating system flush the file to disk.
            os.fsync(temporary_file.fileno())

        # Atomically replace the previous checkpoint with the new one.
        os.replace(temporary_path, path)

    # Clean up an unfinished temporary file if anything fails.
    finally:

        # Remove the temporary file if it still exists.
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


# Recover completed chunk IDs for one document.
def load_checkpoint(
    checkpoint_path: str | Path,
    document_id: str,
    fingerprint: str | None = None,
) -> set[str]:

    # Convert the supplied checkpoint location into a Path.
    path = Path(checkpoint_path)

    # Reject an empty document identifier.
    if not isinstance(document_id, str) or not document_id.strip():
        raise ValueError("A valid document_id is required.")

    # Return an empty set when no checkpoint has been saved.
    if not path.exists():
        return set()

    # Attempt to read and deserialize the checkpoint safely.
    try:

        # Open the existing checkpoint using UTF-8 encoding.
        with path.open("r", encoding="utf-8") as checkpoint_file:

            # Deserialize the stored JSON document.
            checkpoint = json.load(checkpoint_file)

    # Translate malformed JSON into a checkpoint-specific error.
    except json.JSONDecodeError as exc:

        # Stop recovery rather than ignoring corrupted progress.
        raise ValueError(
            f"Invalid checkpoint: corrupted JSON in {path}"
        ) from exc

    # Require the checkpoint to be a JSON object.
    if not isinstance(checkpoint, dict):
        raise ValueError("Invalid checkpoint: expected a JSON object.")

    # Read the stored document identity safely.
    stored_document_id = checkpoint.get("document_id")

    # Require a nonempty document identifier.
    if not isinstance(stored_document_id, str) or not stored_document_id.strip():
        raise ValueError("Invalid checkpoint: document_id must be a nonempty string.")

    # Read the stored completed chunk identifiers safely.
    completed_chunk_ids = checkpoint.get("completed_chunk_ids")

    # Require an actual list rather than a string or another type.
    if not isinstance(completed_chunk_ids, list):
        raise ValueError("Invalid checkpoint: completed_chunk_ids must be a list.")

    # Verify that every completed chunk identifier is a nonempty string.
    if any(
        not isinstance(chunk_id, str) or not chunk_id.strip()
        for chunk_id in completed_chunk_ids
    ):
        raise ValueError("Invalid checkpoint: chunk IDs must be nonempty strings.")

    # Prevent accidentally resuming a different document.
    if checkpoint["document_id"] != document_id:
        raise ValueError("Checkpoint document_id does not match.")

    # Verify the fingerprint when the caller provides one.
    if fingerprint is not None:

        # Reject progress belonging to another document version.
        if checkpoint.get("fingerprint") != fingerprint:
            raise ValueError("Checkpoint fingerprint does not match.")

    # Return the identifiers of previously completed chunks.
    return set(checkpoint["completed_chunk_ids"])


# Import SHA-256 hashing for deterministic document fingerprints.
import hashlib


# Calculate a fingerprint from PDF contents and chunking settings.
def compute_document_fingerprint(
    file_path: str | Path,
    chunk_size: int,
    overlap: int,
    processing_version: str = "v1",
) -> str:

    # Convert the supplied PDF location into a filesystem path.
    path = Path(file_path)

    # Require a positive chunk size.
    if not isinstance(chunk_size, int) or isinstance(chunk_size, bool) or chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer.")

    # Require a valid overlap smaller than the chunk size.
    if (
        not isinstance(overlap, int)
        or isinstance(overlap, bool)
        or overlap < 0
        or overlap >= chunk_size
    ):
        raise ValueError("overlap must be between 0 and chunk_size - 1.")

    # Require a nonempty processing-pipeline version.
    if not isinstance(processing_version, str) or not processing_version.strip():
        raise ValueError("processing_version must be a nonempty string.")

    # Create a new SHA-256 hash calculator.
    digest = hashlib.sha256()

    # Read the PDF in blocks to avoid loading large files into memory.
    with path.open("rb") as pdf_file:

        # Continue reading until the end of the file.
        while True:

            # Read up to one megabyte of PDF data.
            block = pdf_file.read(1024 * 1024)

            # Stop when no more bytes remain.
            if not block:
                break

            # Add the current PDF block to the hash calculation.
            digest.update(block)

    # Encode the chunking configuration deterministically.
    configuration = json.dumps(
        {
            "chunk_size": chunk_size,
            "overlap": overlap,
            "processing_version": processing_version,
        },
        sort_keys=True,
    )

    # Include the configuration in the document fingerprint.
    digest.update(configuration.encode("utf-8"))

    # Return the fingerprint as a hexadecimal string.
    return digest.hexdigest()
