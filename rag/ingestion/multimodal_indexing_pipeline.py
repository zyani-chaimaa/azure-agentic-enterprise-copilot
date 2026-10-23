# Import Path to validate the input PDF location.
from pathlib import Path

# Import our existing multimodal PDF extraction orchestrator.
from rag.ingestion.multimodal_pipeline import ingest_multimodal_pdf

# Import our tested multimodal chunking function.
from rag.ingestion.multimodal_chunker import chunk_multimodal_elements

# Import our tested Azure AI Search v2 indexing service.
from rag.ingestion.multimodal_index_documents import index_multimodal_chunks

# Import deterministic PDF fingerprint generation.
from rag.ingestion.multimodal_checkpoint import compute_document_fingerprint

# Import persistent caching for extracted multimodal chunks.
from rag.ingestion.multimodal_chunk_cache import load_chunk_cache, save_chunk_cache


# Extract, chunk, embed, and index one multimodal PDF.
def index_multimodal_pdf(
    file_path: str,
    document_id: str,
    source_uri: str,
    chunk_size: int = 1000,
    overlap: int = 150,
    checkpoint_path: str | Path | None = None,
) -> int:

    # Require a nonempty PDF path.
    if not isinstance(file_path, str) or not file_path.strip():
        raise ValueError("A valid PDF file_path is required.")

    # Require a nonempty document identifier.
    if not isinstance(document_id, str) or not document_id.strip():
        raise ValueError("A valid document_id is required.")

    # Require a nonempty source reference.
    if not isinstance(source_uri, str) or not source_uri.strip():
        raise ValueError("A valid source_uri is required.")

    # Convert the PDF location into a filesystem path.
    path = Path(file_path)

    # Require an existing regular file.
    if not path.is_file():
        raise FileNotFoundError(f"PDF file not found: {file_path}")

    # Require a PDF extension.
    if path.suffix.lower() != ".pdf":
        raise ValueError("Only PDF files are supported.")

    # Calculate a fingerprint only when checkpoint recovery is enabled.
    fingerprint = (
        compute_document_fingerprint(
            path,
            chunk_size=chunk_size,
            overlap=overlap,
            processing_version="v1",
        )
        if checkpoint_path is not None else None
    )

    # Derive the cache path from the existing checkpoint path.
    cache_path = (
        Path(checkpoint_path).with_suffix(".chunks.json")
        if checkpoint_path is not None
        else None
    )

    # Try to restore previously extracted chunks.
    chunks = (
        load_chunk_cache(cache_path, document_id, fingerprint)
        if cache_path is not None
        else None
    )

    # Perform document extraction only when no cache exists.
    if chunks is None:

        # Extract validated text, tables, and figure evidence.
        elements = ingest_multimodal_pdf(
            file_path=str(path),
            document_id=document_id,
            source_uri=source_uri,
        )

        # Reject PDFs that produce no searchable evidence.
        if not elements:
            raise ValueError("No multimodal evidence was extracted.")

        # Convert extracted evidence into searchable chunks.
        chunks = chunk_multimodal_elements(
            elements=elements,
            chunk_size=chunk_size,
            overlap=overlap,
        )

        # Reject PDFs that produce no searchable chunks.
        if not chunks:
            raise ValueError("No multimodal chunks were generated.")

        # Save the chunks before starting potentially lengthy indexing.
        if cache_path is not None:
            save_chunk_cache(
                cache_path,
                document_id,
                fingerprint,
                chunks,
            )

    # Embed and upload chunks exclusively to Azure AI Search v2.
    if checkpoint_path is not None:

        # Enable checkpoint recovery with the verified PDF fingerprint.
        uploaded = index_multimodal_chunks(
            chunks,
            checkpoint_path=checkpoint_path,
            fingerprint=fingerprint,
        )
    else:

        # Preserve the original behavior when recovery is disabled.
        uploaded = index_multimodal_chunks(chunks)

    # Return the number of successfully indexed chunks.
    return uploaded
