# Import pytest for assertions and exception testing.
import pytest

# Import the validated multimodal chunk model.
from rag.models.multimodal_chunk import MultimodalChunk

# Import the module so its embedding function can be mocked.
from rag.ingestion import multimodal_embedder


# Create reusable test chunks with valid metadata.
def make_chunk(content_type="text", **overrides):

    # Define the fields required by the chunk model.
    data = {
        "chunk_id": "report-p2-element-0-c0",
        "element_id": "report-p2-element-0",
        "document_id": "report",
        "filename": "report.pdf",
        "source_uri": "documents/report.pdf",
        "page_number": 2,
        "chunk_index": 0,
        "content_type": content_type,
        "content": "Quarterly revenue increased.",
        "section_heading": "Financial Results",
        "extraction_method": "document-intelligence-layout",
    }

    # Visual evidence requires an image reference.
    if content_type in ("figure", "chart"):
        data["asset_uri"] = "https://example.com/figure.png"

    # Apply any values specific to the test.
    data.update(overrides)

    # Return a validated multimodal chunk.
    return MultimodalChunk(**data)


# Verify that a text chunk becomes a complete search document.
def test_embeds_text_chunk(monkeypatch):

    # Create a valid embedding with 1,536 dimensions.
    expected_vector = [0.1] * 1536

    # Replace the real Azure embedding function with a local mock.
    monkeypatch.setattr(
        multimodal_embedder,
        "embed_text",
        lambda text: expected_vector,
    )

    # Convert a text chunk into a search document.
    document = multimodal_embedder.embed_multimodal_chunk(
        make_chunk()
    )

    # Verify that the embedding is preserved.
    assert document["content_vector"] == expected_vector

    # Verify the main source metadata.
    assert document["document_id"] == "report"
    assert document["page_number"] == 2
    assert document["content_type"] == "text"
    assert document["section_heading"] == "Financial Results"

    # Verify compatibility with the 13-field search schema.
    assert len(document) == 13


# Verify that the original chunk content is sent for embedding.
def test_embeds_original_content(monkeypatch):

    # Record the content passed to the mocked embedding function.
    received = []

    # Define a local embedding replacement.
    def fake_embed(text):

        # Record the embedding input.
        received.append(text)

        # Return a valid vector.
        return [0.2] * 1536

    # Replace the Azure embedding function.
    monkeypatch.setattr(
        multimodal_embedder,
        "embed_text",
        fake_embed,
    )

    # Prepare a chunk with known content.
    chunk = make_chunk(content="Important policy statement.")

    # Generate its search document.
    multimodal_embedder.embed_multimodal_chunk(chunk)

    # Confirm that the correct content was embedded.
    assert received == ["Important policy statement."]


# Verify that tables, figures, and charts are supported.
@pytest.mark.parametrize(
    "content_type",
    ["table", "figure", "chart"],
)
def test_embeds_multimodal_content(monkeypatch, content_type):

    # Replace the Azure embedding request with a valid vector.
    monkeypatch.setattr(
        multimodal_embedder,
        "embed_text",
        lambda text: [0.3] * 1536,
    )

    # Prepare evidence of the requested type.
    chunk = make_chunk(content_type=content_type)

    # Generate its search document.
    document = multimodal_embedder.embed_multimodal_chunk(chunk)

    # Verify the evidence type.
    assert document["content_type"] == content_type

    # Verify that visual evidence retains its image URI.
    if content_type in ("figure", "chart"):
        assert document["asset_uri"] == chunk.asset_uri


# Verify that unexpected embedding dimensions are rejected.
def test_rejects_wrong_vector_dimensions(monkeypatch):

    # Simulate an embedding model returning only three values.
    monkeypatch.setattr(
        multimodal_embedder,
        "embed_text",
        lambda text: [0.1, 0.2, 0.3],
    )

    # Verify that the adapter rejects the incompatible vector.
    with pytest.raises(ValueError, match="1536"):
        multimodal_embedder.embed_multimodal_chunk(
            make_chunk()
        )


# Verify that unsupported input types are rejected.
def test_rejects_invalid_chunk():

    # Pass a string instead of a validated chunk.
    with pytest.raises(TypeError):
        multimodal_embedder.embed_multimodal_chunk(
            "invalid-chunk"
        )


# Verify that embedding failures propagate to the caller.
def test_propagates_embedding_failure(monkeypatch):

    # Simulate an Azure embedding service failure.
    def failing_embed(text):

        # Raise an error instead of returning an embedding.
        raise RuntimeError("Embedding service unavailable.")

    # Replace the real embedding function.
    monkeypatch.setattr(
        multimodal_embedder,
        "embed_text",
        failing_embed,
    )

    # Ensure the adapter does not silently ignore the failure.
    with pytest.raises(
        RuntimeError,
        match="Embedding service unavailable",
    ):
        multimodal_embedder.embed_multimodal_chunk(
            make_chunk()
        )
