# Import time to handle temporary Azure rate limits.
import time

# Count tokens using the embedding model's tokenizer.
import tiktoken

# Apply both token and request quotas when requested.
from rag.ingestion.embedding_rate_limiter import EmbeddingQuotaLimiter

# Import the OpenAI exception raised when a request is rate-limited.
from openai import APIConnectionError, RateLimitError

# Import our existing authenticated Microsoft Foundry client.
from app.model_client import create_model_client

# Import our centralized application settings.
from app.config import settings


# Convert text into a numerical embedding vector.
def embed_text(
    text: str,
    quota_limiter: EmbeddingQuotaLimiter | None = None,
) -> list[float]:

    # Reject empty text before making a paid API request.
    if not text or not text.strip():
        raise ValueError("Cannot generate an embedding for empty text.")

    # Reuse the existing Microsoft Entra-authenticated model client.
    # Count input tokens once before making any embedding attempts.
    token_count = (
        len(tiktoken.encoding_for_model("text-embedding-3-small").encode(text))
        if quota_limiter is not None else None
    )

    client = create_model_client()

    # Attempt the embedding request up to five times.
    for attempt in range(5):

        # Handle temporary rate-limit errors without losing progress.
        try:

            # Request an embedding from our deployed Azure model.
            # Reserve quota for this API attempt, including retries.
            if quota_limiter is not None:
                quota_limiter.acquire(token_count)

            response = client.embeddings.create(
                model=settings.azure_embedding_deployment,
                input=text,
            )

            # Extract the embedding vector from the model response.
            vector = response.data[0].embedding

            # Ensure its size matches our Azure AI Search index.
            if len(vector) != 1536:
                raise ValueError(
                    f"Expected 1536 dimensions, received {len(vector)}."
                )

            # Return the embedding vector.
            return vector

        # Catch temporary Azure connection failures and rate limits.
        except RateLimitError as error:
            # Stop after the final unsuccessful attempt.
            if attempt == 4:
                raise

            # Respect Azure's requested retry delay.
            time.sleep(get_rate_limit_delay(error))

        except APIConnectionError:

            # Raise the error after the final unsuccessful attempt.
            if attempt == 4:
                raise

            # Wait progressively longer before retrying.
            time.sleep(15 * (attempt + 1))

    # This should never be reached but makes failure explicit.
    raise RuntimeError("Embedding generation failed.")


# Generate multiple embedding vectors in one Azure request.
def embed_texts(
    texts: list[str],
    quota_limiter: EmbeddingQuotaLimiter | None = None,
) -> list[list[float]]:

    # Reject an empty batch.
    if not texts:
        raise ValueError("Cannot embed an empty batch.")

    # Reject empty or whitespace-only inputs.
    if any(not isinstance(text, str) or not text.strip() for text in texts):
        raise ValueError("Every embedding input must contain nonempty text.")

    # Create the existing authenticated Azure model client.
    # Count the total tokens submitted in this embedding batch.
    token_count = (
        sum(
            len(tiktoken.encoding_for_model("text-embedding-3-small").encode(text))
            for text in texts
        )
        if quota_limiter is not None else None
    )

    client = create_model_client()

    # Attempt the batch request up to five times.
    for attempt in range(5):

        # Catch temporary Azure connection and rate-limit failures.
        try:

            # Send all texts in one embedding API request.
            # Reserve quota for this batch attempt, including retries.
            if quota_limiter is not None:
                quota_limiter.acquire(token_count)

            response = client.embeddings.create(
                model=settings.azure_embedding_deployment,
                input=texts,
            )

            # Allocate one result position per input text.
            vectors = [None] * len(texts)

            # Process every embedding returned by Azure.
            for item in response.data:

                # Read the original input position.
                index = item.index

                # Reject invalid or duplicate response positions.
                if (
                    not isinstance(index, int)
                    or isinstance(index, bool)
                    or index < 0
                    or index >= len(texts)
                    or vectors[index] is not None
                ):
                    raise ValueError("Invalid or duplicate embedding index.")

                # Reject vectors incompatible with Azure AI Search.
                if len(item.embedding) != 1536:
                    raise ValueError(
                        f"Expected 1536 dimensions, received {len(item.embedding)}."
                    )

                # Preserve the association between text and embedding.
                vectors[index] = item.embedding

            # Ensure Azure returned an embedding for every input.
            if any(vector is None for vector in vectors):
                raise ValueError("Azure returned an incomplete embedding batch.")

            # Return vectors in the original input order.
            return vectors

        # Retry temporary Azure service failures.
        except RateLimitError as error:
            # Stop after the final unsuccessful attempt.
            if attempt == 4:
                raise

            # Respect Azure's requested retry delay.
            time.sleep(get_rate_limit_delay(error))

        except APIConnectionError:

            # Propagate the error after the final attempt.
            if attempt == 4:
                raise

            # Apply the existing progressive retry delay.
            time.sleep(15 * (attempt + 1))

    # Explicitly report an unexpected retry-loop exit.
    raise RuntimeError("Batch embedding generation failed.")


# Determine how long to wait after an Azure rate-limit response.
def get_rate_limit_delay(error: RateLimitError) -> float:

    # Start with a conservative 60-second delay.
    delay = 60.0

    # Access the HTTP response associated with the error.
    response = getattr(error, "response", None)

    # Read response headers safely when available.
    headers = getattr(response, "headers", {}) or {}

    # Azure may express the retry delay in milliseconds.
    retry_ms = headers.get("retry-after-ms")

    # Azure may alternatively use the standard Retry-After header.
    retry_seconds = headers.get("retry-after")

    # Prefer the millisecond header when present and valid.
    if retry_ms is not None:
        try:
            delay = max(delay, float(retry_ms) / 1000)
        except (TypeError, ValueError):
            pass

    # Otherwise inspect the delay expressed in seconds.
    elif retry_seconds is not None:
        try:
            delay = max(delay, float(retry_seconds))
        except (TypeError, ValueError):
            pass

    # Return the delay without sleeping inside this helper.
    return delay
