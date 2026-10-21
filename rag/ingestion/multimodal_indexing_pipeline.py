# Import Path to validate the input PDF location.
from pathlib import Path

# Import our existing multimodal PDF extraction orchestrator.
from rag.ingestion.multimodal_pipeline import ingest_multimodal_pdf

# Import our tested multimodal chunking function.
from rag.ingestion.multimodal_chunker import chunk_multimodal_elements

# Import our tested Azure AI Search v2 indexing service.
from rag.ingestion.multimodal_index_documents import index_multimodal_chunks


# Extract, chunk, embed, and index one multimodal PDF.
def index_multimodal_pdf(
    file_path: str,
    document_id: str,
    source_uri: str,
    chunk_size: int = 1000,
    overlap: int = 150,
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

    # Extract validated text, tables, and figure evidence.
    elements = ingest_multimodal_pdf(
        file_path=str(path),
        document_id=document_id,
        source_uri=source_uri,
    )

    # Reject PDFs that produce no searchable evidence.
    if not elements:
        raise ValueError("No multimodal evidence was extracted.")

    # Convert the extracted evidence into searchable chunks.
    chunks = chunk_multimodal_elements(
        elements=elements,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    # Reject PDFs that produce no searchable chunks.
    if not chunks:
        raise ValueError("No multimodal chunks were generated.")

    # Embed and upload chunks exclusively to Azure AI Search v2.
    uploaded = index_multimodal_chunks(chunks)

    # Return the number of successfully indexed chunks.
    return uploaded
