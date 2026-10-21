# Import lightweight objects for mocked Azure responses.
from types import SimpleNamespace

# Import Mock to track embedding calls.
from unittest.mock import Mock

# Import the multimodal indexer under test.
from rag.ingestion import multimodal_index_documents as indexer

# Import the quota-limiter class for type verification.
from rag.ingestion.embedding_rate_limiter import EmbeddingQuotaLimiter

# Reuse the validated chunk fixture and Azure configuration helper.
from tests.test_multimodal_batch_resume import make_chunk, mock_azure


# Verify that successive batches share one quota limiter.
def test_multiple_batches_share_quota_limiter(monkeypatch):

    # Configure fake Azure credentials and settings.
    mock_azure(monkeypatch)

    # Create five distinct chunks from the same document.
    chunks = [
        make_chunk().model_copy(
            update={"chunk_id": f"report-p1-c{i}"}
        )
        for i in range(5)
    ]

    # Record the chunk IDs uploaded in each request.
    uploaded_batches = []

    # Simulate Azure AI Search without making network requests.
    class FakeSearchClient:

        # Accept the expected Azure Search constructor arguments.
        def __init__(self, endpoint, index_name, credential):
            pass

        # Confirm successful indexing of each submitted document.
        def upload_documents(self, documents):

            # Record the identifiers submitted together.
            ids = [document["chunk_id"] for document in documents]

            # Preserve the upload history.
            uploaded_batches.append(ids)

            # Return one successful result per document.
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

    # Simulate batch embedding while preserving document metadata.
    embed = Mock(
        side_effect=lambda batch, quota_limiter=None: [
            {
                **chunk.model_dump(),
                "content_vector": [0.1] * 1536,
            }
            for chunk in batch
        ]
    )

    # Replace actual embedding generation with the mock.
    monkeypatch.setattr(indexer, "embed_multimodal_chunks", embed)

    # Index five chunks with a maximum of two per batch.
    uploaded = indexer.index_multimodal_chunks(
        chunks,
        batch_size=2,
    )

    # All five chunks should be indexed successfully.
    assert uploaded == 5

    # The planner should produce three embedding batches.
    assert embed.call_count == 3

    # Verify the chunk grouping and original order.
    expected_batches = [
        chunks[0:2],
        chunks[2:4],
        chunks[4:5],
    ]

    # Extract the actual chunk groups sent for embedding.
    actual_batches = [
        call.args[0]
        for call in embed.call_args_list
    ]

    # Compare planned groups with actual groups.
    assert actual_batches == expected_batches

    # Collect the quota limiter passed to every embedding batch.
    limiters = [
        call.kwargs["quota_limiter"]
        for call in embed.call_args_list
    ]

    # Every batch must receive a real quota limiter.
    assert all(
        isinstance(limiter, EmbeddingQuotaLimiter)
        for limiter in limiters
    )

    # Every batch must receive the exact same limiter instance.
    assert all(limiter is limiters[0] for limiter in limiters)

    # Azure Search should receive the same three groups.
    assert uploaded_batches == [
        [chunk.chunk_id for chunk in batch]
        for batch in expected_batches
    ]
