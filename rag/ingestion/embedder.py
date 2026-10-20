# Import time to handle temporary Azure rate limits.
import time

# Import the OpenAI exception raised when a request is rate-limited.
from openai import RateLimitError

# Import our existing authenticated Microsoft Foundry client.
from app.model_client import create_model_client

# Import our centralized application settings.
from app.config import settings


# Convert text into a numerical embedding vector.
def embed_text(text: str) -> list[float]:

    # Reject empty text before making a paid API request.
    if not text or not text.strip():
        raise ValueError("Cannot generate an embedding for empty text.")

    # Reuse the existing Microsoft Entra-authenticated model client.
    client = create_model_client()

    # Attempt the embedding request up to five times.
    for attempt in range(5):

        # Handle temporary rate-limit errors without losing progress.
        try:

            # Request an embedding from our deployed Azure model.
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

        # Catch Azure's rate-limit response.
        except RateLimitError:

            # Raise the error after the final unsuccessful attempt.
            if attempt == 4:
                raise

            # Wait progressively longer before retrying.
            time.sleep(15 * (attempt + 1))

    # This should never be reached but makes failure explicit.
    raise RuntimeError("Embedding generation failed.")
