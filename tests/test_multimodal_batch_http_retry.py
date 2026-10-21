# Import a lightweight object for simulated Azure responses.
from types import SimpleNamespace

# Import Mock to track embedding and retry behavior.
from unittest.mock import Mock

# Import pytest for test assertions.
import pytest

# Import Azure's HTTP exception class.
from azure.core.exceptions import HttpResponseError

# Import the indexing module.
from rag.ingestion import multimodal_index_documents as indexer

# Import the checkpoint reader.
from rag.ingestion.multimodal_checkpoint import load_checkpoint

# Reuse our existing test helpers.
from test_multimodal_index_documents import make_chunk, mock_azure


# Verify that an entire batch is retried after a temporary HTTP failure.
def test_batch_retries_http_503_without_reembedding(monkeypatch, tmp_path):

    # Configure fake Azure credentials and settings.
    mock_azure(monkeypatch)

    # Create three distinct chunks from the same document.
    chunks = [
        make_chunk().model_copy(
            update={"chunk_id": f"report-p1-c{i}"}
        )
        for i in range(3)
    ]

    # Create an isolated checkpoint path.
    checkpoint_path = tmp_path / "http-retry-checkpoint.json"

    # Use a fixed fingerprint for the document version.
    fingerprint = "a" * 64

    # Track how often embeddings are generated.
    # Simulate one embedding request for the entire chunk batch.
    embed = Mock(
        side_effect=lambda batch, quota_limiter=None: [
            {
                **chunk.model_dump(),
                "content_vector": [0.1] * 1536,
            }
            for chunk in batch
        ]
    )

    # Replace real embedding generation with our mock.
    monkeypatch.setattr(indexer, "embed_multimodal_chunks", embed)

    # Record retry delays without actually sleeping.
    sleep = Mock()

    # Replace the sleep function used by the indexer.
    monkeypatch.setattr(indexer, "sleep", sleep)

    # Track every Azure Search upload request.
    requests = []

    # Simulate Azure returning HTTP 503 on the first request.
    class FakeSearchClient:

        # Accept Azure client configuration without connecting.
        def __init__(self, endpoint, index_name, credential):
            pass

        # Simulate an HTTP failure followed by success.
        def upload_documents(self, documents):

            # Record the IDs submitted in this request.
            ids = [document["chunk_id"] for document in documents]

            # Preserve the request history.
            requests.append(ids)

            # Raise a temporary error on the first request.
            if len(requests) == 1:
                # Simulate the HTTP response supplied by Azure's SDK.
                response = SimpleNamespace(
                    status_code=503,
                    reason="Service Unavailable",
                    headers={},
                    request=SimpleNamespace(
                        method="POST",
                        url="https://example.search.windows.net",
                    ),
                )

                # Raise an Azure error associated with HTTP 503.
                raise HttpResponseError(
                    message="Service temporarily unavailable",
                    response=response,
                )

            # Confirm success for every submitted document.
            return [
                SimpleNamespace(
                    key=chunk_id,
                    succeeded=True,
                    status_code=200,
                )
                for chunk_id in ids
            ]

    # Replace the real Azure Search client.
    monkeypatch.setattr(indexer, "SearchClient", FakeSearchClient)

    # Index the batch using the new execution path.
    uploaded = indexer.index_multimodal_chunks(
        chunks,
        checkpoint_path=checkpoint_path,
        fingerprint=fingerprint,
        batch_size=3,
    )

    # All three chunks must eventually succeed.
    assert uploaded == 3

    # The batch should be submitted exactly twice.
    assert requests == [
        [chunk.chunk_id for chunk in chunks],
        [chunk.chunk_id for chunk in chunks],
    ]

    # Each chunk should be embedded only once.
    # Azure Search retries must reuse the existing batch embeddings.
    # Verify that the batch was embedded exactly once.
    embed.assert_called_once()

    # Confirm that the original chunks were passed to the adapter.
    assert embed.call_args.args == (chunks,)

    # Verify that the indexer supplied a real shared quota limiter.
    from rag.ingestion.embedding_rate_limiter import EmbeddingQuotaLimiter
    assert isinstance(
        embed.call_args.kwargs["quota_limiter"],
        EmbeddingQuotaLimiter,
    )

    # The retry should wait for two seconds after attempt one.
    sleep.assert_called_once_with(1)

    # Only confirmed successes should appear in the checkpoint.
    assert load_checkpoint(
        checkpoint_path,
        "report",
        fingerprint=fingerprint,
    ) == {chunk.chunk_id for chunk in chunks}
