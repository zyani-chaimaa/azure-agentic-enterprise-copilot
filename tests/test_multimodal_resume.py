# Import pytest for mocking dependencies.
import pytest

# Import the indexing module that we want to test.
from rag.ingestion import multimodal_index_documents as indexer

# Reuse the existing test chunk and mocked Azure services.
from test_multimodal_index_documents import make_chunk, mock_azure

# Import our tested checkpoint functions.
from rag.ingestion.multimodal_checkpoint import (
    load_checkpoint,
    save_checkpoint,
)


# Verify that recovery skips chunks already recorded as completed.
def test_resume_skips_completed_chunk(monkeypatch, tmp_path):

    # Configure mocked Azure services without making real requests.
    captured = mock_azure(monkeypatch)

    # Create an isolated checkpoint file.
    checkpoint_path = tmp_path / "report-checkpoint.json"

    # Use a fixed fingerprint representing the document version.
    fingerprint = "a" * 64

    # Create one validated chunk.
    chunk = make_chunk()

    # Record that this chunk was indexed during an earlier run.
    save_checkpoint(
        checkpoint_path,
        "report",
        [chunk.chunk_id],
        fingerprint=fingerprint,
    )

    # Verify that the checkpoint contains our completed chunk.
    assert load_checkpoint(
        checkpoint_path,
        "report",
        fingerprint=fingerprint,
    ) == {chunk.chunk_id}

    # Fail the test if embedding is attempted for the completed chunk.
    def unexpected_embedding(chunk):
        raise AssertionError("Completed chunks must not be embedded again.")

    # Replace the embedding function with our assertion.
    monkeypatch.setattr(
        indexer,
        "embed_multimodal_chunk",
        unexpected_embedding,
    )

    # Resume indexing using the existing checkpoint.
    uploaded = indexer.index_multimodal_chunks(
        [chunk],
        checkpoint_path=checkpoint_path,
        fingerprint=fingerprint,
    )

    # No new chunks should have been uploaded.
    assert uploaded == 0

    # Azure Search should not receive any document uploads.
    assert captured["uploads"] == []


# Verify recovery after two successful uploads and one failed upload.
def test_resume_after_partial_upload_failure(monkeypatch, tmp_path):

    # Import a simple object for simulated Azure responses.
    from types import SimpleNamespace

    # Configure mocked Azure credentials, settings, and embeddings.
    captured = mock_azure(monkeypatch)

    # Create three chunks with distinct Azure AI Search keys.
    chunks = [
        make_chunk().model_copy(update={"chunk_id": f"report-p1-c{i}"})
        for i in range(3)
    ]

    # Create an isolated checkpoint for the document.
    checkpoint_path = tmp_path / "report-checkpoint.json"

    # Identify the document version used for this test.
    fingerprint = "a" * 64

    # Track uploads across the initial run and recovery.
    attempts = []

    # Control whether the simulated Azure service should fail.
    fail_third_chunk = True

    # Simulate Azure AI Search without making network requests.
    class FakeSearchClient:

        # Accept client configuration without contacting Azure.
        def __init__(self, endpoint, index_name, credential):
            pass

        # Return success except for the third chunk during the first run.
        def upload_documents(self, documents):

            # Read the chunk ID submitted for indexing.
            chunk_id = documents[0]["chunk_id"]

            # Record each attempted upload.
            attempts.append(chunk_id)

            # Simulate a permanent failure for the third chunk.
            if fail_third_chunk and chunk_id == "report-p1-c2":
                return [SimpleNamespace(succeeded=False, status_code=400)]

            # Otherwise confirm successful indexing.
            return [SimpleNamespace(succeeded=True)]

    # Replace the Azure Search client with our simulated service.
    monkeypatch.setattr(indexer, "SearchClient", FakeSearchClient)

    # The first run must stop when the third chunk fails.
    with pytest.raises(RuntimeError, match="Failed to index"):
        indexer.index_multimodal_chunks(
            chunks,
            checkpoint_path=checkpoint_path,
            fingerprint=fingerprint,
        )

    # Verify that only the first two chunks were checkpointed.
    assert load_checkpoint(
        checkpoint_path,
        "report",
        fingerprint=fingerprint,
    ) == {"report-p1-c0", "report-p1-c1"}

    # Simulate Azure recovering before the next indexing run.
    fail_third_chunk = False

    # Clear the upload history to observe recovery separately.
    attempts.clear()

    # Resume indexing using the existing checkpoint.
    uploaded = indexer.index_multimodal_chunks(
        chunks,
        checkpoint_path=checkpoint_path,
        fingerprint=fingerprint,
    )

    # Exactly one new chunk should be indexed.
    assert uploaded == 1

    # Previously completed chunks must not be uploaded again.
    assert attempts == ["report-p1-c2"]

    # All three chunks should now be recorded as completed.
    assert load_checkpoint(
        checkpoint_path,
        "report",
        fingerprint=fingerprint,
    ) == {chunk.chunk_id for chunk in chunks}


# Verify that resumable indexing rejects chunks from different documents.
def test_resume_rejects_mixed_document_batch(monkeypatch, tmp_path):

    # Configure mocked Azure services without making network requests.
    captured = mock_azure(monkeypatch)

    # Create a valid chunk belonging to the first document.
    first = make_chunk()

    # Create a chunk belonging to another document with a unique key.
    second = make_chunk().model_copy(
        update={
            "document_id": "another-report",
            "chunk_id": "another-report-p1-c0",
        }
    )

    # Create a temporary checkpoint location.
    checkpoint_path = tmp_path / "report-checkpoint.json"

    # Require rejection before attempting any Azure operations.
    with pytest.raises(ValueError, match="same document"):
        indexer.index_multimodal_chunks(
            [first, second],
            checkpoint_path=checkpoint_path,
            fingerprint="a" * 64,
        )

    # Verify that no Azure Search client was created.
    assert "index_name" not in captured

    # Verify that no checkpoint was written.
    assert not checkpoint_path.exists()
