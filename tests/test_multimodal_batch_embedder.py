# Import lightweight objects for constructing test data.
from types import SimpleNamespace

# Import Mock to simulate the embedding API.
from unittest.mock import Mock

# Import pytest for assertions and exception testing.
import pytest

# Import the module we are testing.
from rag.ingestion import multimodal_embedder

# Import the validated multimodal chunk model.
from rag.models.multimodal_chunk import MultimodalChunk


# Define the exact fields required by our Azure AI Search index.
EXPECTED_FIELDS = {
    "chunk_id",
    "element_id",
    "document_id",
    "filename",
    "source_uri",
    "page_number",
    "chunk_index",
    "content_type",
    "content",
    "asset_uri",
    "section_heading",
    "extraction_method",
    "content_vector",
}


# Build a valid chunk using the model's declared fields.
def make_chunk(index):

    # Create representative document metadata.
    values = {
        "chunk_id": f"chunk-{index}",
        "element_id": f"element-{index}",
        "document_id": "document-1",
        "filename": "example.pdf",
        "source_uri": "https://example.com/example.pdf",
        "page_number": index + 1,
        "chunk_index": index,
        "content_type": "text",
        "content": f"Content for chunk {index}",
        "asset_uri": None,
        "section_heading": "Overview",
        "extraction_method": "test",
    }

    # Validate and return the chunk.
    return MultimodalChunk.model_validate(values)


# Verify that batch embeddings preserve order and metadata.
def test_preserves_metadata_and_vector_matching(monkeypatch):

    # Create three distinct multimodal chunks.
    chunks = [make_chunk(index) for index in range(3)]

    # Give each chunk a distinguishable embedding.
    vectors = [[float(index)] * 1536 for index in range(3)]

    # Replace the Azure embedding call with a mock.
    embed = Mock(return_value=vectors)

    # Patch the function imported inside the batch adapter.
    monkeypatch.setattr(
        "rag.ingestion.embedder.embed_texts",
        embed,
    )

    # Create a mock quota limiter.
    quota_limiter = Mock()

    # Prepare the batch of Azure AI Search documents.
    documents = multimodal_embedder.embed_multimodal_chunks(
        chunks,
        quota_limiter=quota_limiter,
    )

    # Verify one document was produced for every chunk.
    assert len(documents) == 3

    # Verify text order and quota-limiter forwarding.
    embed.assert_called_once_with(
        [chunk.content for chunk in chunks],
        quota_limiter=quota_limiter,
    )

    # Check every generated search document.
    for index, document in enumerate(documents):

        # Preserve the exact index schema.
        assert set(document) == EXPECTED_FIELDS

        # Preserve the correct chunk identifier.
        assert document["chunk_id"] == chunks[index].chunk_id

        # Preserve all metadata from the original chunk.
        for field in EXPECTED_FIELDS - {"content_vector"}:
            assert document[field] == getattr(chunks[index], field)

        # Attach the embedding belonging to this chunk.
        assert document["content_vector"] == vectors[index]


# Verify empty batches are rejected without an API call.
def test_rejects_empty_batch():

    # An empty batch is not a valid embedding request.
    with pytest.raises(ValueError, match="empty"):
        multimodal_embedder.embed_multimodal_chunks([])


# Verify incorrect chunk types are rejected.
def test_rejects_invalid_chunk_type():

    # A dictionary is not a validated MultimodalChunk object.
    with pytest.raises(TypeError, match="MultimodalChunk"):
        multimodal_embedder.embed_multimodal_chunks([{"content": "invalid"}])


# Verify missing embeddings are rejected.
def test_rejects_incomplete_embedding_response(monkeypatch):

    # Create two valid chunks.
    chunks = [make_chunk(0), make_chunk(1)]

    # Simulate Azure returning only one embedding.
    monkeypatch.setattr(
        "rag.ingestion.embedder.embed_texts",
        Mock(return_value=[[0.0] * 1536]),
    )

    # The adapter must reject mismatched counts.
    with pytest.raises(ValueError, match="count"):
        multimodal_embedder.embed_multimodal_chunks(chunks)


# Verify incorrect vector dimensions are rejected.
def test_rejects_wrong_vector_dimensions(monkeypatch):

    # Create one valid chunk.
    chunks = [make_chunk(0)]

    # Simulate an embedding with the wrong dimensions.
    monkeypatch.setattr(
        "rag.ingestion.embedder.embed_texts",
        Mock(return_value=[[0.0] * 100]),
    )

    # Prevent incompatible vectors from reaching Azure AI Search.
    with pytest.raises(ValueError, match="1536"):
        multimodal_embedder.embed_multimodal_chunks(chunks)
