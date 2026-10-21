# Import lightweight objects for simulated Azure responses.
from types import SimpleNamespace

# Import Mock to track API calls and quota reservations.
from unittest.mock import Mock

# Import pytest for parameterized testing.
import pytest

# Import the real OpenAI rate-limit exception.
from openai import RateLimitError

# Import the embedding module under test.
from rag.ingestion import embedder


# Test quota acquisition for single and batch embedding.
@pytest.mark.parametrize(
    "function_name, embedding_input",
    [
        ("embed_text", "Example document text"),
        ("embed_texts", ["Example document text", "Another document"]),
    ],
)
def test_quota_acquired_on_every_attempt(
    monkeypatch, function_name, embedding_input
):

    # Create a simulated HTTP 429 response.
    response = Mock()
    response.status_code = 429
    response.headers = {"retry-after": "75"}

    # Construct the actual exception used by the OpenAI SDK.
    rate_limit_error = RateLimitError(
        "Azure rate limit exceeded",
        response=response,
        body=None,
    )

    # Determine how many embeddings the successful response needs.
    input_count = (
        1 if function_name == "embed_text"
        else len(embedding_input)
    )

    # Build a successful response with valid embedding dimensions.
    successful_response = SimpleNamespace(
        data=[
            SimpleNamespace(
                index=index,
                embedding=[float(index)] * 1536,
            )
            for index in range(input_count)
        ]
    )

    # Simulate one rate-limit failure followed by success.
    create = Mock(
        side_effect=[rate_limit_error, successful_response]
    )

    # Create a fake authenticated Azure client.
    client = SimpleNamespace(
        embeddings=SimpleNamespace(create=create)
    )

    # Prevent real Azure client creation.
    monkeypatch.setattr(
        embedder,
        "create_model_client",
        lambda: client,
    )

    # Prevent real waiting during the retry.
    sleep = Mock()
    monkeypatch.setattr(embedder.time, "sleep", sleep)

    # Create a mock quota limiter.
    quota_limiter = Mock()

    # Call the embedding function with quota management enabled.
    result = getattr(embedder, function_name)(
        embedding_input,
        quota_limiter=quota_limiter,
    )

    # Verify that Azure was called twice.
    assert create.call_count == 2

    # Verify that quota was acquired before both attempts.
    assert quota_limiter.acquire.call_count == 2

    # Read the token counts reserved on each attempt.
    reserved_tokens = [
        call.args[0]
        for call in quota_limiter.acquire.call_args_list
    ]

    # Both attempts must reserve the same positive token count.
    assert reserved_tokens[0] > 0
    assert reserved_tokens[0] == reserved_tokens[1]

    # Verify that the batch reserves more tokens than the single input.
    if function_name == "embed_texts":
        assert reserved_tokens[0] > 3

    # Verify that Azure's retry delay was respected.
    sleep.assert_called_once_with(75.0)

    # Verify that the final embedding result is valid.
    assert len(result) == 1536 if function_name == "embed_text" else len(result) == 2
