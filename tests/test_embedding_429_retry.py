# Import SimpleNamespace to create mock Azure responses.
from types import SimpleNamespace

# Import Mock to simulate Azure's embedding client.
from unittest.mock import Mock

# Import pytest for parameterized testing.
import pytest

# Import the real OpenAI exception type.
from openai import RateLimitError

# Import the module under test.
from rag.ingestion import embedder


# Test both single-text and batch embedding functions.
@pytest.mark.parametrize(
    "function_name, embedding_input",
    [
        ("embed_text", "Example document text"),
        ("embed_texts", ["Example document text"]),
    ],
)
def test_embedding_retries_after_azure_429(
    monkeypatch, function_name, embedding_input
):
    # Create an HTTP response reporting Azure's retry delay.
    response = Mock()
    response.status_code = 429
    response.headers = {"retry-after": "75"}

    # Construct the real exception raised by the OpenAI SDK.
    rate_limit_error = RateLimitError(
        "Azure embedding rate limit exceeded",
        response=response,
        body=None,
    )

    # Create a successful 1,536-dimensional embedding result.
    successful_response = SimpleNamespace(
        data=[
            SimpleNamespace(
                index=0,
                embedding=[0.1] * 1536,
            )
        ]
    )

    # Simulate a 429 response followed by success.
    create = Mock(
        side_effect=[rate_limit_error, successful_response]
    )

    # Build a mock embedding client.
    client = SimpleNamespace(
        embeddings=SimpleNamespace(create=create)
    )

    # Replace Azure client creation with our mock.
    monkeypatch.setattr(
        embedder,
        "create_model_client",
        lambda: client,
    )

    # Record retry delays without actually sleeping.
    sleep = Mock()

    # Replace time.sleep inside the embedding module.
    monkeypatch.setattr(embedder.time, "sleep", sleep)

    # Run the selected embedding function.
    result = getattr(embedder, function_name)(embedding_input)

    # Verify that the function retried exactly once.
    assert create.call_count == 2

    # Verify that it respected Azure's 75-second retry header.
    sleep.assert_called_once_with(75.0)

    # Verify that the successful embedding was returned.
    if function_name == "embed_text":
        assert result == [0.1] * 1536
    else:
        assert result == [[0.1] * 1536]
