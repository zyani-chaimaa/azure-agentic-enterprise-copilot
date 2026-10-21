# Import the tokenizer used by our embedding model.
import tiktoken

# Import the validated multimodal chunk model.
from rag.models.multimodal_chunk import MultimodalChunk


# Define conservative initial batching limits.
DEFAULT_MAX_CHUNKS = 16
DEFAULT_MAX_BATCH_TOKENS = 4000
MAX_CHUNK_TOKENS = 8191


# Group chunks into token-aware embedding batches.
def plan_embedding_batches(
    chunks: list[MultimodalChunk],
    max_chunks: int = DEFAULT_MAX_CHUNKS,
    max_batch_tokens: int = DEFAULT_MAX_BATCH_TOKENS,
) -> list[list[MultimodalChunk]]:

    # Reject invalid chunk-count limits.
    if type(max_chunks) is not int or max_chunks < 1:
        raise ValueError("max_chunks must be a positive integer.")

    # Reject invalid token budgets.
    if type(max_batch_tokens) is not int or max_batch_tokens < 1:
        raise ValueError("max_batch_tokens must be a positive integer.")

    # Prevent a batch budget exceeding our configured token ceiling.
    if max_batch_tokens > 8191:
        raise ValueError("max_batch_tokens cannot exceed 8191.")

    # Load the tokenizer compatible with text-embedding-3-small.
    encoding = tiktoken.encoding_for_model("text-embedding-3-small")

    # Store the planned batches.
    batches = []

    # Store chunks belonging to the current batch.
    current_batch = []

    # Track tokens consumed by the current batch.
    current_tokens = 0

    # Process chunks in their original order.
    for chunk in chunks:

        # Require a validated multimodal chunk.
        if not isinstance(chunk, MultimodalChunk):
            raise TypeError("Every item must be a MultimodalChunk.")

        # Count tokens in the text sent to the embedding model.
        token_count = len(encoding.encode(chunk.content))

        # Reject chunks exceeding the individual input limit.
        if token_count > MAX_CHUNK_TOKENS:
            raise ValueError(
                f"Chunk {chunk.chunk_id} exceeds the embedding token limit."
            )

        # Reject chunks that cannot fit within the configured batch budget.
        if token_count > max_batch_tokens:
            raise ValueError(
                f"Chunk {chunk.chunk_id} exceeds max_batch_tokens."
            )

        # Determine whether adding this chunk would exceed either limit.
        batch_full = (
            len(current_batch) >= max_chunks
            or current_tokens + token_count > max_batch_tokens
        )

        # Finalize the current batch before exceeding its limits.
        if current_batch and batch_full:
            batches.append(current_batch)
            current_batch = []
            current_tokens = 0

        # Add the chunk to the current batch.
        current_batch.append(chunk)

        # Update the current batch's token count.
        current_tokens += token_count

    # Preserve the final nonempty batch.
    if current_batch:
        batches.append(current_batch)

    # Return all batches in their original chunk order.
    return batches
