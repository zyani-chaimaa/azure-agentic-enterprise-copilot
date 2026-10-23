# Import SimpleNamespace to simulate Azure API response objects.
from types import SimpleNamespace

# Import pytest for exception testing.
import pytest

# Import the embedding module so we can replace its Azure client.
from rag.ingestion import embedder


# Build a simulated Azure embedding response.
def make_response(items):
    # Wrap the supplied embedding items in a response object.
    return SimpleNamespace(data=items)


# Build one simulated embedding result.
def make_item(index, value=0.1, dimensions=1536):
    # Return the position and vector expected from Azure.
    return SimpleNamespace(
        index=index,
        embedding=[value] * dimensions,
    )


# Replace the real Azure client with a predictable local mock.
def mock_client(monkeypatch, response):
    # Record the embedding requests made by our function.
    calls = []

    # Simulate the Azure embeddings.create method.
    def fake_create(model, input):
        # Save the model and input for verification.
        calls.append((model, input))

        # Return the predefined response without contacting Azure.
        return response

    # Build an object matching the Azure client's structure.
    client = SimpleNamespace(
        embeddings=SimpleNamespace(create=fake_create)
    )

    # Replace client creation inside our embedding module.
    monkeypatch.setattr(
        embedder,
        "create_model_client",
        lambda: client,
    )

    # Return recorded requests to the test.
    return calls


# Verify multiple texts are embedded in one API request.
def test_batch_embeddings_use_one_request(monkeypatch):
    # Simulate two valid embedding vectors.
    response = make_response([
        make_item(0, 0.1),
        make_item(1, 0.2),
    ])

    # Install the local mock.
    calls = mock_client(monkeypatch, response)

    # Generate embeddings for two texts.
    vectors = embedder.embed_texts(["First text", "Second text"])

    # Confirm the input was sent as one batch.
    assert len(calls) == 1
    assert calls[0][1] == ["First text", "Second text"]

    # Confirm both vectors are returned correctly.
    assert vectors == [[0.1] * 1536, [0.2] * 1536]


# Verify that Azure response order cannot mix up documents.
def test_batch_embeddings_preserve_input_order(monkeypatch):
    # Simulate Azure returning the second embedding first.
    response = make_response([
        make_item(1, 0.2),
        make_item(0, 0.1),
    ])

    # Install the local mock.
    mock_client(monkeypatch, response)

    # Request two embeddings.
    vectors = embedder.embed_texts(["First text", "Second text"])

    # Confirm vectors follow input order, not response order.
    assert vectors[0] == [0.1] * 1536
    assert vectors[1] == [0.2] * 1536


# Verify that empty batches are rejected.
@pytest.mark.parametrize("texts", [[], ["   "], ["Valid", ""]])
def test_batch_embeddings_reject_empty_inputs(texts):
    # Ensure invalid inputs are rejected before Azure calls.
    with pytest.raises(ValueError):
        embedder.embed_texts(texts)


# Verify that missing embedding results are rejected.
def test_batch_embeddings_reject_missing_result(monkeypatch):
    # Simulate Azure returning only one of two embeddings.
    mock_client(monkeypatch, make_response([make_item(0)]))

    # Confirm incomplete batches cannot be indexed.
    with pytest.raises(ValueError, match="incomplete"):
        embedder.embed_texts(["First", "Second"])


# Verify that duplicate result positions are rejected.
def test_batch_embeddings_reject_duplicate_index(monkeypatch):
    # Simulate two embeddings pointing to the same input.
    mock_client(
        monkeypatch,
        make_response([make_item(0), make_item(0)]),
    )

    # Confirm duplicate positions are rejected.
    with pytest.raises(ValueError, match="duplicate"):
        embedder.embed_texts(["First", "Second"])


# Verify that unexpected vector dimensions are rejected.
def test_batch_embeddings_reject_wrong_dimensions(monkeypatch):
    # Simulate an incompatible three-dimensional vector.
    mock_client(
        monkeypatch,
        make_response([make_item(0, dimensions=3)]),
    )

    # Confirm the vector cannot enter our search index.
    with pytest.raises(ValueError, match="1536"):
        embedder.embed_texts(["First"])
