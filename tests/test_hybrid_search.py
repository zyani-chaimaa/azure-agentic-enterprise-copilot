# Import SimpleNamespace to simulate Azure configuration.
from types import SimpleNamespace

# Import Mock and patch to replace external dependencies.
from unittest.mock import Mock, patch

# Import pytest for parameter validation tests.
import pytest

# Import the retrieval module under test.
import rag.retrieval.hybrid_search as retrieval


# Create a reusable mocked search environment.

from rag.retrieval.document_permissions import DocumentPrincipal


def _secured_hybrid_search(*args, **kwargs):
    """Supply a valid test identity to the existing retrieval tests."""
    kwargs.setdefault(
        "principal",
        DocumentPrincipal(
            tenant_id="tenant-test",
            user_id="user-test",
        ),
    )
    return retrieval.hybrid_search(*args, **kwargs)


def test_missing_principal_is_rejected():
    """Production retrieval must reject requests without identity."""
    with pytest.raises(PermissionError):
        retrieval.hybrid_search("confidential document")

@pytest.fixture
def search_mocks():
    # Simulate one Azure Search result with citation metadata.
    document = {
        "chunk_id": "figure-51",
        "document_id": "webshoppers-38-2018",
        "filename": "Webshoppers_38_pt.pdf",
        "source_uri": "test://webshoppers",
        "page_number": 17,
        "content": "Categorias em crescimento",
        "@search.score": 0.03,
        "@search.reranker_score": 2.7,
    }

    # Create a mock Azure Search client.
    client = Mock()

    # Return the simulated result when search is called.
    client.search.return_value = [document]

    # Replace Azure dependencies for an isolated unit test.
    with (
        patch.object(retrieval, "embed_text", return_value=[0.1, 0.2]),
        patch.object(retrieval, "DefaultAzureCredential"),
        patch.object(retrieval, "SearchClient", return_value=client),
        patch.object(retrieval, "VectorizedQuery") as vector_query,
        patch.object(
            retrieval,
            "settings",
            SimpleNamespace(
                azure_search_endpoint="https://example.search.windows.net",
                azure_search_index="enterprise-documents",
                azure_multimodal_search_index="enterprise-documents-v2",
            ),
        ),
    ):
        # Provide the mocks to each test.
        yield client, vector_query


# Verify that existing calls retain hybrid-only behavior.
def test_hybrid_default_is_unchanged(search_mocks):
    # Retrieve the mocked Azure client and vector query.
    client, vector_query = search_mocks

    # Execute the original retrieval mode.
    passages = _secured_hybrid_search("test question", top_k=5)

    # Inspect the Azure Search parameters.
    options = client.search.call_args.kwargs

    # Ensure semantic ranking was not enabled implicitly.
    assert "query_type" not in options

    # Ensure the original candidate count remains unchanged.
    assert vector_query.call_args.kwargs["k_nearest_neighbors"] == 5

    # Ensure citation metadata remains available.
    assert passages[0]["page_number"] == 17


# Verify the optional semantic-ranking configuration.
def test_semantic_retrieval_configuration(search_mocks):
    # Retrieve the mocked Azure client and vector query.
    client, vector_query = search_mocks

    # Execute semantic retrieval against the multimodal index.
    passages = _secured_hybrid_search(
        "category growth",
        top_k=5,
        multimodal=True,
        semantic=True,
    )

    # Inspect the submitted Azure Search options.
    options = client.search.call_args.kwargs

    # Verify semantic ranking was requested.
    assert options["query_type"] == "semantic"

    # Verify the configured semantic profile.
    assert options["semantic_configuration_name"] == "nexora-semantic-v1"

    # Verify the semantic candidate count.
    assert vector_query.call_args.kwargs["k_nearest_neighbors"] == 50

    # Verify the semantic reranker score is preserved.
    assert passages[0]["reranker_score"] == 2.7


# Verify callers can override the vector candidate count.
def test_explicit_vector_k_is_respected(search_mocks):
    # Retrieve the mocked dependencies.
    _, vector_query = search_mocks

    # Execute semantic retrieval with an explicit candidate count.
    _secured_hybrid_search("category growth", semantic=True, vector_k=20)

    # Ensure the explicit value takes precedence.
    assert vector_query.call_args.kwargs["k_nearest_neighbors"] == 20


# Reject invalid retrieval parameters before contacting Azure.
@pytest.mark.parametrize(
    "question,top_k,vector_k",
    [
        ("", 5, None),
        ("test", 0, None),
        ("test", 5, 0),
    ],
)
def test_invalid_parameters(question, top_k, vector_k):
    # Confirm invalid inputs raise a validation error.
    with pytest.raises(ValueError):
        _secured_hybrid_search(question, top_k=top_k, vector_k=vector_k)


# Ensure Azure errors are not silently hidden.
def test_azure_errors_propagate(search_mocks):
    # Retrieve the mocked Azure Search client.
    client, _ = search_mocks

    # Simulate a service error.
    client.search.side_effect = RuntimeError("Azure Search unavailable")

    # Verify the caller receives the original error.
    with pytest.raises(RuntimeError, match="Azure Search unavailable"):
        _secured_hybrid_search("test", semantic=True)
