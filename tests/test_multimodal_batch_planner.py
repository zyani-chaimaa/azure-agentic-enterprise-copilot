# Import pytest for test assertions.
import pytest

# Import the tokenizer used by the planner.
import tiktoken

# Import the batch planner and its token limit.
from rag.ingestion.multimodal_batch_planner import (
    MAX_CHUNK_TOKENS,
    plan_embedding_batches,
)

# Reuse our existing validated chunk factory.
from test_multimodal_index_documents import make_chunk


# Create a chunk with unique identification and specified content.
def make_test_chunk(index, content):
    # Start with an existing valid chunk.
    chunk = make_chunk()

    # Replace its ID, position, and text content.
    return chunk.model_copy(
        update={
            "chunk_id": f"report-p1-c{index}",
            "chunk_index": index,
            "content": content,
        }
    )


# Verify that the planner respects token budgets.
def test_groups_by_token_budget():
    # Create three chunks containing one token each.
    chunks = [
        make_test_chunk(i, "hello")
        for i in range(3)
    ]

    # Allow only two tokens per batch.
    batches = plan_embedding_batches(
        chunks,
        max_chunks=16,
        max_batch_tokens=2,
    )

    # Expect two chunks in the first batch and one in the second.
    assert [len(batch) for batch in batches] == [2, 1]


# Verify that the planner respects maximum batch size.
def test_groups_by_chunk_count():
    # Create five small chunks.
    chunks = [
        make_test_chunk(i, "hello")
        for i in range(5)
    ]

    # Allow no more than two chunks per batch.
    batches = plan_embedding_batches(
        chunks,
        max_chunks=2,
        max_batch_tokens=100,
    )

    # Expect batches containing two, two, and one chunk.
    assert [len(batch) for batch in batches] == [2, 2, 1]


# Verify that the planner preserves the original chunk order.
def test_preserves_chunk_order():
    # Create chunks with distinct IDs.
    chunks = [
        make_test_chunk(i, f"Document section {i}")
        for i in range(6)
    ]

    # Divide the chunks into small batches.
    batches = plan_embedding_batches(
        chunks,
        max_chunks=2,
    )

    # Flatten the planned batches.
    flattened = [
        chunk.chunk_id
        for batch in batches
        for chunk in batch
    ]

    # Verify that no chunks were reordered or lost.
    assert flattened == [chunk.chunk_id for chunk in chunks]


# Verify that oversized individual chunks are rejected.
def test_rejects_oversized_chunk():
    # Load the tokenizer used by the embedding model.
    encoding = tiktoken.encoding_for_model("text-embedding-3-small")

    # Create text that exceeds the per-input token limit.
    content = "hello " * (MAX_CHUNK_TOKENS + 10)

    # Confirm the test input really exceeds the limit.
    assert len(encoding.encode(content)) > MAX_CHUNK_TOKENS

    # Create a validated chunk containing the oversized text.
    chunk = make_test_chunk(0, content)

    # Verify that the planner rejects it.
    with pytest.raises(ValueError, match="embedding token limit"):
        plan_embedding_batches([chunk])


# Verify that invalid batch limits are rejected.
@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_chunks": 0},
        {"max_chunks": True},
        {"max_batch_tokens": 0},
        {"max_batch_tokens": True},
        {"max_batch_tokens": 8192},
    ],
)
def test_rejects_invalid_limits(kwargs):
    # Create one valid chunk.
    chunk = make_test_chunk(0, "hello")

    # Verify that invalid limits raise an error.
    with pytest.raises(ValueError):
        plan_embedding_batches([chunk], **kwargs)


# Verify that empty input produces no batches.
def test_empty_input():
    # No chunks should produce no batches.
    assert plan_embedding_batches([]) == []
