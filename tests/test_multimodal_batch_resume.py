# Import a lightweight object for simulated Azure responses.
from types import SimpleNamespace

# Import pytest for expected failure assertions.
import pytest

# Import the indexing module we are testing.
from rag.ingestion import multimodal_index_documents as indexer

# Import our existing checkpoint reader.
from rag.ingestion.multimodal_checkpoint import load_checkpoint

# Reuse existing chunk and Azure mock helpers.
from test_multimodal_index_documents import make_chunk, mock_azure


# Verify partial batch success is preserved across recovery.
def test_batch_resume_after_partial_success(monkeypatch, tmp_path):

    # Configure mocked Azure settings and credentials.
    mock_azure(monkeypatch)

    # Prevent batch embedding from contacting Azure during this unit test.
    def fake_embed_multimodal_chunks(chunks, quota_limiter=None):
        # Preserve every chunk and attach a deterministic 1536-dimensional vector.
        return [
            {**chunk.model_dump(), "content_vector": [0.1] * 1536}
            for chunk in chunks
        ]

    # Replace the actual batch embedding function used by the indexer.
    monkeypatch.setattr(
        indexer,
        "embed_multimodal_chunks",
        fake_embed_multimodal_chunks,
    )

    # Create three distinct chunks belonging to one document.
    chunks = [
        make_chunk().model_copy(
            update={"chunk_id": f"report-p1-c{i}"}
        )
        for i in range(3)
    ]

    # Use a temporary checkpoint that cannot affect real ingestion.
    checkpoint_path = tmp_path / "batch-checkpoint.json"

    # Identify the document version for checkpoint validation.
    fingerprint = "a" * 64

    # Record which chunk IDs are submitted in each upload request.
    requests = []

    # Simulate an initial failure of the third chunk.
    fail_third = True

    # Define a fake Azure Search client.
    class FakeSearchClient:

        # Accept the usual Azure client configuration.
        def __init__(self, endpoint, index_name, credential):
            pass

        # Simulate a batch upload with individual results.
        def upload_documents(self, documents):

            # Capture every chunk ID in the request.
            ids = [document["chunk_id"] for document in documents]

            # Record the request for later assertions.
            requests.append(ids)

            # Return results in reverse order to test ID matching.
            return [
                SimpleNamespace(
                    key=chunk_id,
                    succeeded=not (
                        fail_third and chunk_id == "report-p1-c2"
                    ),
                    status_code=(
                        400
                        if fail_third and chunk_id == "report-p1-c2"
                        else 200
                    ),
                )
                for chunk_id in reversed(ids)
            ]

    # Replace the real Search client with our local fake.
    monkeypatch.setattr(indexer, "SearchClient", FakeSearchClient)

    # The first run must report the permanent failure.
    with pytest.raises(RuntimeError, match="Failed to index"):
        indexer.index_multimodal_chunks(
            chunks,
            checkpoint_path=checkpoint_path,
            fingerprint=fingerprint,
            batch_size=3,
        )

    # All three chunks must have been uploaded together.
    assert requests == [[chunk.chunk_id for chunk in chunks]]

    # Only confirmed successes may enter the checkpoint.
    assert load_checkpoint(
        checkpoint_path,
        "report",
        fingerprint=fingerprint,
    ) == {"report-p1-c0", "report-p1-c1"}

    # Simulate Azure recovering before the next run.
    fail_third = False

    # Clear previous request history.
    requests.clear()

    # Resume using the same checkpoint.
    uploaded = indexer.index_multimodal_chunks(
        chunks,
        checkpoint_path=checkpoint_path,
        fingerprint=fingerprint,
        batch_size=3,
    )

    # Exactly one previously failed chunk must be uploaded.
    assert uploaded == 1

    # Completed chunks must not be uploaded again.
    assert requests == [["report-p1-c2"]]

    # The checkpoint must now contain all three chunks.
    assert load_checkpoint(
        checkpoint_path,
        "report",
        fingerprint=fingerprint,
    ) == {chunk.chunk_id for chunk in chunks}
