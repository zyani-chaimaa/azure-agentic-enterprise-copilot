# Import Path to locate the PDF in our project.
from pathlib import Path

# Import the Azure identity provider for passwordless authentication.
from azure.identity import DefaultAzureCredential

# Import the client used to upload documents into Azure AI Search.
from azure.search.documents import SearchClient

# Import our centralized Azure configuration.
from app.config import settings

# Import our existing PDF extraction function.
from rag.ingestion.pdf_extractor import extract_pdf_pages

# Import our tested word-aware chunking function.
from rag.ingestion.chunker import chunk_pages

# Import our Microsoft Foundry embedding function.
from rag.ingestion.embedder import embed_text


# Extract, embed, and index one PDF document.
def index_pdf(file_path: str, document_id: str) -> int:

    # Convert the provided file location into a Path object.
    path = Path(file_path)

    # Extract readable text from the PDF, preserving page numbers.
    pages = extract_pdf_pages(str(path))

    # Split pages into searchable passages with source metadata.
    chunks = chunk_pages(
        pages=pages,
        document_id=document_id,
        filename=path.name,
        source_uri=str(path),
    )

    # Stop if the PDF has no extractable text.
    if not chunks:
        raise ValueError("No extractable PDF text was found.")

    # Create a credential using Azure CLI locally or Managed Identity.
    credential = DefaultAzureCredential(
        exclude_interactive_browser_credential=True
    )

    # Connect to our existing Azure AI Search index.
    client = SearchClient(
        endpoint=settings.azure_search_endpoint,
        index_name=settings.azure_search_index,
        credential=credential,
    )

    # Count successfully uploaded chunks.
    uploaded = 0

    # Process chunks individually to respect our small embedding quota.
    for chunk in chunks:

        # Generate a vector for the current chunk using Microsoft Foundry.
        vector = embed_text(chunk.content)

        # Build the search document using our index field names.
        search_document = {
            "chunk_id": chunk.chunk_id,
            "document_id": chunk.document_id,
            "filename": chunk.filename,
            "source_uri": chunk.source_uri,
            "page_number": chunk.page_number,
            "chunk_index": chunk.chunk_index,
            "content": chunk.content,
            "content_vector": vector,
        }

        # Upload the current chunk into Azure AI Search.
        results = client.upload_documents(documents=[search_document])

        # Verify that Azure accepted this document.
        if not results or not results[0].succeeded:
            raise RuntimeError(
                f"Failed to index chunk: {chunk.chunk_id}"
            )

        # Increase the successful upload count.
        uploaded += 1

        # Show progress so we can track long ingestion runs.
        print(f"Indexed {uploaded}/{len(chunks)}: {chunk.chunk_id}", flush=True)

    # Return the number of successfully indexed chunks.
    return uploaded


# Run ingestion when this module is executed directly.
if __name__ == "__main__":

    # Locate our first synthetic enterprise policy PDF.
    pdf_path = (
        "data/documents/Synthetic_Returns_Refunds_Policy_v1.pdf"
    )

    # Index the PDF using its stable document identifier.
    total = index_pdf(
        file_path=pdf_path,
        document_id="DEMO-RET-001",
    )

    # Display the final ingestion result.
    print(f"Successfully indexed {total} chunks.")