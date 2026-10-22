# Import SimpleNamespace to create lightweight test configuration.
from types import SimpleNamespace

# Import pytest for assertions about expected errors.
import pytest

# Import the Blob Storage module so its dependencies can be mocked.
from rag.ingestion import blob_storage


# Verify that an existing figure can be downloaded successfully.
def test_download_existing_figure(monkeypatch):

    # Define a representative figure URL from NEXORA's storage account.
    asset_uri = (
        "https://example.blob.core.windows.net/multimodal-figures/"
        "figures/webshoppers-38-2018/page-15/15.1.png"
    )

    # Replace Azure configuration with isolated test values.
    monkeypatch.setattr(
        blob_storage,
        "settings",
        SimpleNamespace(
            azure_storage_endpoint="https://example.blob.core.windows.net",
            azure_storage_container="multimodal-figures",
        ),
    )

    # Record which container and blob the function requests.
    requested = {}

    # Simulate an Azure Blob download without network access.
    class FakeBlobClient:

        # Return the fake downloader.
        def download_blob(self):
            return self

        # Return representative image bytes.
        def readall(self):
            return b"fake-png-image"

    # Simulate the authenticated Azure Blob Storage service.
    class FakeServiceClient:

        # Capture the selected container and blob.
        def get_blob_client(self, container, blob):
            requested["container"] = container
            requested["blob"] = blob
            return FakeBlobClient()

    # Replace the real Azure client factory with the fake client.
    monkeypatch.setattr(
        blob_storage,
        "create_blob_service_client",
        lambda: FakeServiceClient(),
    )

    # Download the figure through the function under test.
    result = blob_storage.download_figure_image(asset_uri)

    # Verify that the downloaded bytes are returned unchanged.
    assert result == b"fake-png-image"

    # Verify that the configured container was selected.
    assert requested["container"] == "multimodal-figures"

    # Verify that the original figure path was preserved.
    assert requested["blob"] == "figures/webshoppers-38-2018/page-15/15.1.png"


# Verify that unexpected storage accounts and containers are rejected.
@pytest.mark.parametrize(
    "asset_uri",
    [
        "http://example.blob.core.windows.net/multimodal-figures/figures/doc/page-1/1.png",
        "https://other.blob.core.windows.net/multimodal-figures/figures/doc/page-1/1.png",
        "https://example.blob.core.windows.net/other-container/figures/doc/page-1/1.png",
        "https://example.blob.core.windows.net/multimodal-figures/other/doc/page-1/1.png",
        "https://example.blob.core.windows.net/multimodal-figures/figures/../secret.png",
        "https://example.blob.core.windows.net/multimodal-figures/figures/doc/page-1/1.png?token=abc",
    ],
)
def test_download_rejects_unexpected_urls(monkeypatch, asset_uri):

    # Configure the expected storage account and container.
    monkeypatch.setattr(
        blob_storage,
        "settings",
        SimpleNamespace(
            azure_storage_endpoint="https://example.blob.core.windows.net",
            azure_storage_container="multimodal-figures",
        ),
    )

    # Confirm invalid URLs are rejected before connecting to Azure.
    with pytest.raises(ValueError):
        blob_storage.download_figure_image(asset_uri)


# Verify that Azure returning no image bytes produces a clear error.
def test_download_rejects_empty_image(monkeypatch):

    # Configure an isolated test storage account.
    monkeypatch.setattr(
        blob_storage,
        "settings",
        SimpleNamespace(
            azure_storage_endpoint="https://example.blob.core.windows.net",
            azure_storage_container="multimodal-figures",
        ),
    )

    # Simulate a download returning no data.
    class FakeBlobClient:

        # Return the fake downloader.
        def download_blob(self):
            return self

        # Simulate an empty Azure response.
        def readall(self):
            return b""

    # Simulate a Blob Storage service returning the fake blob.
    class FakeServiceClient:

        # Return the fake blob client.
        def get_blob_client(self, container, blob):
            return FakeBlobClient()

    # Prevent the test from making a real Azure connection.
    monkeypatch.setattr(
        blob_storage,
        "create_blob_service_client",
        lambda: FakeServiceClient(),
    )

    # Confirm an empty image is rejected.
    with pytest.raises(ValueError, match="empty figure image"):
        blob_storage.download_figure_image(
            "https://example.blob.core.windows.net/"
            "multimodal-figures/figures/doc/page-1/1.png"
        )
