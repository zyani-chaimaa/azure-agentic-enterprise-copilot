# Import a simple object for mocking Azure upload responses.
from types import SimpleNamespace

# Import pytest for assertions and exception testing.
import pytest

# Import the validated multimodal chunk model.
from rag.models.multimodal_chunk import MultimodalChunk

# Import the indexing module so its dependencies can be mocked.
from rag.ingestion import multimodal_index_documents as indexer


# Create a valid multimodal chunk for testing.
def make_chunk(content_type="text"):

    # Build the fields required by the multimodal chunk model.
    data = {
        "chunk_id": "report-p1-c0",
        "element_id": "report-p1",
        "document_id": "report",
        "filename": "report.pdf",
        "source_uri": "documents/report.pdf",
        "page_number": 1,
        "chunk_index": 0,
        "content_type": content_type,
        "content": "Quarterly revenue increased.",
        "section_heading": "Financial Results",
        "extraction_method": "document-intelligence-layout",
    }

    # Figures and charts must retain an asset reference.
    if content_type in ("figure", "chart"):
        data["asset_uri"] = "https://example.com/figure.png"

    # Return a validated chunk.
    return MultimodalChunk(**data)


# Configure mocked Azure dependencies for a test.
def mock_azure(monkeypatch, upload_results=None):

    # Store the Azure Search client arguments and uploaded documents.
    captured = {"uploads": []}

    # Configure the mocked search index names.
    monkeypatch.setattr(
        indexer.settings,
        "azure_search_endpoint",
        "https://example.search.windows.net",
    )

    # Set the original text-only index name.
    monkeypatch.setattr(
        indexer.settings,
        "azure_search_index",
        "enterprise-documents-v1",
    )

    # Set the separate multimodal index name.
    monkeypatch.setattr(
        indexer.settings,
        "azure_multimodal_search_index",
        "enterprise-documents-v2",
    )

    # Replace Azure credential creation with a local object.
    monkeypatch.setattr(
        indexer,
        "DefaultAzureCredential",
        lambda **kwargs: object(),
    )

    # Define a fake Azure Search client.
    class FakeSearchClient:

        # Capture the endpoint, index name, and credential.
        def __init__(self, endpoint, index_name, credential):
            captured["endpoint"] = endpoint
            captured["index_name"] = index_name
            captured["credential"] = credential

        # Simulate uploading documents to Azure AI Search.
        def upload_documents(self, documents):

            # Record the documents sent to the mocked service.
            captured["uploads"].extend(documents)

            # Return the configured result when testing failures.
            if upload_results is not None:
                return upload_results

            # Otherwise simulate a successful Azure upload.
            return [SimpleNamespace(succeeded=True)]

    # Replace the real Azure Search client.
    monkeypatch.setattr(indexer, "SearchClient", FakeSearchClient)

    # Replace embedding generation with a local test document.
    monkeypatch.setattr(
        indexer,
        "embed_multimodal_chunk",
        lambda chunk: {
            **chunk.model_dump(),
            "content_vector": [0.1] * 1536,
        },
    )

    # Return captured data for assertions.
    return captured


# Verify successful indexing into the multimodal v2 index.
def test_indexes_into_v2(monkeypatch):

    # Configure fake Azure dependencies.
    captured = mock_azure(monkeypatch)

    # Index one validated chunk.
    count = indexer.index_multimodal_chunks([make_chunk()])

    # Verify the successful upload count.
    assert count == 1

    # Verify that the original v1 index was not selected.
    assert captured["index_name"] == "enterprise-documents-v2"

    # Verify that one document was uploaded.
    assert len(captured["uploads"]) == 1


# Verify that figure metadata survives indexing.
def test_preserves_figure_metadata(monkeypatch):

    # Configure fake Azure dependencies.
    captured = mock_azure(monkeypatch)

    # Index one figure chunk.
    indexer.index_multimodal_chunks([make_chunk("figure")])

    # Read the uploaded document.
    document = captured["uploads"][0]

    # Verify that the figure type and asset URI are preserved.
    assert document["content_type"] == "figure"
    assert document["asset_uri"] == "https://example.com/figure.png"

    # Verify that the embedding has the correct dimensions.
    assert len(document["content_vector"]) == 1536


# Verify that empty chunk collections are rejected.
def test_rejects_empty_chunks():

    # Ensure no Azure client is needed for empty input.
    with pytest.raises(ValueError, match="No multimodal chunks"):
        indexer.index_multimodal_chunks([])


# Verify that invalid chunk objects are rejected.
def test_rejects_invalid_chunks():

    # Reject a string instead of a validated chunk.
    with pytest.raises(TypeError, match="MultimodalChunk"):
        indexer.index_multimodal_chunks(["invalid"])


# Verify that an Azure endpoint is required.
def test_requires_search_endpoint(monkeypatch):

    # Configure fake Azure dependencies.
    mock_azure(monkeypatch)

    # Remove the endpoint configuration.
    monkeypatch.setattr(indexer.settings, "azure_search_endpoint", "")

    # Verify that indexing cannot continue.
    with pytest.raises(ValueError, match="AZURE_SEARCH_ENDPOINT"):
        indexer.index_multimodal_chunks([make_chunk()])


# Verify that v1 and v2 index names cannot collide.
def test_protects_v1_index(monkeypatch):

    # Configure fake Azure dependencies.
    mock_azure(monkeypatch)

    # Simulate an unsafe configuration.
    monkeypatch.setattr(
        indexer.settings,
        "azure_multimodal_search_index",
        "enterprise-documents-v1",
    )

    # Verify that indexing is blocked.
    with pytest.raises(ValueError, match="must differ"):
        indexer.index_multimodal_chunks([make_chunk()])


# Verify that unsuccessful uploads raise an error.
def test_rejects_failed_upload(monkeypatch):

    # Simulate Azure rejecting the document.
    mock_azure(
        monkeypatch,
        upload_results=[SimpleNamespace(succeeded=False)],
    )

    # Verify that the indexing failure is reported.
    with pytest.raises(RuntimeError, match="Failed to index"):
        indexer.index_multimodal_chunks([make_chunk()])


# Verify that missing Azure upload results are rejected.
def test_rejects_missing_upload_results(monkeypatch):

    # Simulate an empty Azure response.
    mock_azure(monkeypatch, upload_results=[])

    # Verify that an empty response cannot count as success.
    with pytest.raises(RuntimeError, match="Failed to index"):
        indexer.index_multimodal_chunks([make_chunk()])


# Verify that unsupported characters in Azure Search keys are rejected.
@pytest.mark.parametrize(
    "invalid_id",
    [
        "report 2025-p1-c0",
        "report/2025-p1-c0",
        "report:p1:c0",
        "report.p1.c0",
    ],
)
def test_rejects_invalid_chunk_ids(monkeypatch, invalid_id):

    # Configure the mocked Azure services.
    captured = mock_azure(monkeypatch)

    # Create a valid chunk and replace its identifier.
    chunk = make_chunk().model_copy(
        update={"chunk_id": invalid_id}
    )

    # Verify that the invalid key is rejected.
    with pytest.raises(ValueError, match="Invalid Azure AI Search chunk_id"):
        indexer.index_multimodal_chunks([chunk])

    # Verify that no Azure Search client was created.
    assert "index_name" not in captured


# Verify that duplicate chunk IDs cannot overwrite one another.
def test_rejects_duplicate_chunk_ids(monkeypatch):

    # Configure the mocked Azure services.
    captured = mock_azure(monkeypatch)

    # Create two chunks with the same document key.
    first = make_chunk()
    second = make_chunk()

    # Verify that the duplicate is rejected.
    with pytest.raises(ValueError, match="Duplicate multimodal chunk_id"):
        indexer.index_multimodal_chunks([first, second])

    # Verify that indexing stopped before Azure client creation.
    assert "index_name" not in captured


# Verify that supported characters remain valid.
def test_accepts_valid_chunk_ids(monkeypatch):

    # Configure the mocked Azure services.
    captured = mock_azure(monkeypatch)

    # Create a chunk using letters, numbers, underscores, hyphens, and equals.
    chunk = make_chunk().model_copy(
        update={"chunk_id": "Microsoft_2025-p12-table=2-c0"}
    )

    # Index the chunk using mocked Azure services.
    uploaded = indexer.index_multimodal_chunks([chunk])

    # Verify that the document was accepted.
    assert uploaded == 1

    # Verify that the intended key was preserved.
    assert captured["uploads"][0]["chunk_id"] == chunk.chunk_id


# Verify that a temporary Azure service failure can recover on retry.
def test_retries_transient_upload_failure(monkeypatch):

    # Import the Azure exception used for temporary HTTP failures.
    from azure.core.exceptions import HttpResponseError

    # Configure mocked credentials, embeddings, and search settings.
    captured = mock_azure(monkeypatch)

    # Track how many times the upload operation is attempted.
    attempts = []

    # Define a search client that fails temporarily, then succeeds.
    class TransientFailureSearchClient:

        # Record client creation without connecting to Azure.
        def __init__(self, endpoint, index_name, credential):
            captured["index_name"] = index_name

        # Simulate an HTTP 503 error on the first upload.
        def upload_documents(self, documents):

            # Record this upload attempt.
            attempts.append(documents[0]["chunk_id"])

            # Fail the first attempt with a transient service error.
            if len(attempts) == 1:
                raise HttpResponseError(
                    message="Temporary Azure service outage",
                    response=SimpleNamespace(
                        status_code=503,
                        reason="Service Unavailable",
                        headers={},
                    ),
                )

            # Return a successful response on the second attempt.
            return [SimpleNamespace(succeeded=True)]

    # Replace the default fake client with our transient-failure client.
    monkeypatch.setattr(
        indexer,
        "SearchClient",
        TransientFailureSearchClient,
    )

    # Disable retry delays so this test runs quickly.
    monkeypatch.setattr(indexer, "sleep", lambda seconds: None, raising=False)

    # Index one chunk and expect recovery after the temporary failure.
    count = indexer.index_multimodal_chunks([make_chunk()])

    # Confirm the chunk was indexed successfully.
    assert count == 1

    # Confirm that exactly two upload attempts occurred.
    assert attempts == ["report-p1-c0", "report-p1-c0"]


# Verify that repeated temporary failures stop after three attempts.
def test_stops_after_exhausting_upload_retries(monkeypatch):

    # Import the Azure exception used for HTTP service failures.
    from azure.core.exceptions import HttpResponseError

    # Configure mocked Azure settings, credentials, and embeddings.
    mock_azure(monkeypatch)

    # Track the number of attempted uploads.
    attempts = []

    # Simulate an Azure Search service that remains unavailable.
    class AlwaysFailingSearchClient:

        # Accept client configuration without connecting to Azure.
        def __init__(self, endpoint, index_name, credential):
            pass

        # Raise an HTTP 503 error on every upload attempt.
        def upload_documents(self, documents):

            # Record the identifier submitted on this attempt.
            attempts.append(documents[0]["chunk_id"])

            # Simulate a temporary Azure service outage.
            raise HttpResponseError(
                message="Service temporarily unavailable",
                response=SimpleNamespace(
                    status_code=503,
                    reason="Service Unavailable",
                    headers={},
                ),
            )

    # Replace the real Azure client with our failing mock.
    monkeypatch.setattr(
        indexer,
        "SearchClient",
        AlwaysFailingSearchClient,
    )

    # Eliminate waiting during the test.
    monkeypatch.setattr(indexer, "sleep", lambda seconds: None)

    # Verify that the indexing service reports exhausted retries.
    with pytest.raises(RuntimeError, match="after 3 attempts"):
        indexer.index_multimodal_chunks([make_chunk()])

    # Verify that exactly three upload attempts occurred.
    assert attempts == ["report-p1-c0"] * 3


# Verify that permanent HTTP failures are not retried.
@pytest.mark.parametrize("status_code", [400, 403])
def test_does_not_retry_permanent_upload_errors(monkeypatch, status_code):

    # Import the Azure exception used for HTTP failures.
    from azure.core.exceptions import HttpResponseError

    # Configure mocked Azure settings, credentials, and embeddings.
    mock_azure(monkeypatch)

    # Track how many upload attempts are made.
    attempts = []

    # Simulate an Azure Search client returning a permanent error.
    class PermanentFailureSearchClient:

        # Accept configuration without contacting Azure.
        def __init__(self, endpoint, index_name, credential):
            pass

        # Reject every upload with the specified HTTP status.
        def upload_documents(self, documents):

            # Record the chunk submitted to Azure.
            attempts.append(documents[0]["chunk_id"])

            # Simulate an HTTP response from Azure Search.
            raise HttpResponseError(
                message="Permanent upload failure",
                response=SimpleNamespace(
                    status_code=status_code,
                    reason="Permanent Failure",
                    headers={},
                ),
            )

    # Replace the real Azure client with the failing mock.
    monkeypatch.setattr(
        indexer,
        "SearchClient",
        PermanentFailureSearchClient,
    )

    # Fail the test if the implementation attempts to wait before retrying.
    def unexpected_sleep(seconds):
        raise AssertionError("Permanent failures must not be retried.")

    # Replace the retry delay with our assertion.
    monkeypatch.setattr(indexer, "sleep", unexpected_sleep)

    # Verify that the original Azure error is propagated.
    with pytest.raises(HttpResponseError):
        indexer.index_multimodal_chunks([make_chunk()])

    # Confirm that exactly one upload attempt occurred.
    assert attempts == ["report-p1-c0"]
