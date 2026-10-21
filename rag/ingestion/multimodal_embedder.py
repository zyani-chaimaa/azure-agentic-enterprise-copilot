# Import the validated multimodal chunk model.
from rag.models.multimodal_chunk import MultimodalChunk

# Import the existing Azure embedding function.
from rag.ingestion.embedder import embed_text


# Define the expected embedding dimensions.
EMBEDDING_DIMENSIONS = 1536


# Convert one multimodal chunk into an embeddable search document.
def embed_multimodal_chunk(chunk: MultimodalChunk) -> dict:

    # Reject objects that are not multimodal chunks.
    if not isinstance(chunk, MultimodalChunk):
        raise TypeError("Expected a MultimodalChunk.")

    # Revalidate the chunk, including its source metadata.
    chunk = MultimodalChunk.model_validate(chunk.model_dump())

    # Generate an embedding from the chunk's textual content.
    # For figures and charts, this embeds their descriptions, not image pixels.
    vector = embed_text(chunk.content)

    # Reject vectors with an unexpected number of dimensions.
    if len(vector) != EMBEDDING_DIMENSIONS:
        raise ValueError(
            f"Expected {EMBEDDING_DIMENSIONS} embedding dimensions, "
            f"received {len(vector)}."
        )

    # Construct the document expected by the multimodal search index.
    search_document = {
        "chunk_id": chunk.chunk_id,
        "element_id": chunk.element_id,
        "document_id": chunk.document_id,
        "filename": chunk.filename,
        "source_uri": chunk.source_uri,
        "page_number": chunk.page_number,
        "chunk_index": chunk.chunk_index,
        "content_type": chunk.content_type,
        "content": chunk.content,
        "asset_uri": chunk.asset_uri,
        "section_heading": chunk.section_heading,
        "extraction_method": chunk.extraction_method,
        "content_vector": vector,
    }

    # Return the prepared document without uploading it to Azure.
    return search_document
