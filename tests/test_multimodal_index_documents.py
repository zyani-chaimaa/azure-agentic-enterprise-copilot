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
