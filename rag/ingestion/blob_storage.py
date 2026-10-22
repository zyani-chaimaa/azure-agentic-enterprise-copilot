# Import Azure's passwordless credential provider.
from azure.identity import DefaultAzureCredential

# Import the Azure Blob Storage client.
from azure.storage.blob import BlobServiceClient

# Import NEXORA's centralized configuration.
from app.config import settings


# Create an authenticated Azure Blob Storage service client.
def create_blob_service_client() -> BlobServiceClient:

    # Read the storage account endpoint from configuration.
    endpoint = settings.azure_storage_endpoint

    # Reject missing or whitespace-only endpoints.
    if not endpoint or not endpoint.strip():
        raise ValueError(
            "AZURE_STORAGE_ENDPOINT is not configured."
        )

    # Create credentials using Azure CLI locally or Managed Identity in Azure.
    credential = DefaultAzureCredential(
        exclude_interactive_browser_credential=True
    )

    # Configure the client without uploading or downloading anything.
    client = BlobServiceClient(
        account_url=endpoint,
        credential=credential,
    )

    # Return the authenticated storage service client.
    return client


# Import Blob Storage settings for binary image uploads.
from azure.storage.blob import ContentSettings


# Upload an extracted PDF figure to Azure Blob Storage.
def upload_figure_image(
    image_bytes: bytes,
    document_id: str,
    page_number: int,
    figure_id: str,
) -> str:

    # Reject empty or invalid image data.
    if not isinstance(image_bytes, bytes) or not image_bytes:
        raise ValueError("Figure image must contain binary data.")

    # Validate identifiers before using them in a storage path.
    for name, value in (
        ("document_id", document_id),
        ("figure_id", figure_id),
    ):
        # Require nonempty strings without path separators.
        if (
            not isinstance(value, str)
            or not value.strip()
            or value in (".", "..")
            or "/" in value
            or "\\" in value
        ):
            raise ValueError(f"Invalid {name}.")

    # Require a positive, non-boolean page number.
    if type(page_number) is not int or page_number < 1:
        raise ValueError("page_number must be a positive integer.")

    # Read the configured destination container.
    container_name = settings.azure_storage_container

    # Reject missing container configuration.
    if not container_name or not container_name.strip():
        raise ValueError("AZURE_STORAGE_CONTAINER is not configured.")

    # Build a deterministic blob path for the extracted figure.
    blob_name = (
        f"figures/{document_id}/page-{page_number}/{figure_id}.png"
    )

    # Create the authenticated storage service client.
    service_client = create_blob_service_client()

    # Select the configured container and figure path.
    blob_client = service_client.get_blob_client(
        container=container_name,
        blob=blob_name,
    )

    # Upload the image and its searchable source metadata.
    blob_client.upload_blob(
        image_bytes,
        overwrite=True,
        content_settings=ContentSettings(content_type="image/png"),
        metadata={
            "document_id": document_id,
            "page_number": str(page_number),
            "figure_id": figure_id,
        },
    )

    # Return the blob URI without exposing credentials.
    return blob_client.url

# Import URL parsing to validate existing figure asset locations.
from urllib.parse import urlparse, unquote


# Download an existing figure image from NEXORA's Azure Blob Storage.
def download_figure_image(asset_uri: str) -> bytes:

    # Require a nonempty asset URL.
    if not isinstance(asset_uri, str) or not asset_uri.strip():
        raise ValueError("A valid figure asset_uri is required.")

    # Parse the provided figure URL.
    parsed = urlparse(asset_uri)

    # Parse the configured Azure Storage endpoint.
    expected = urlparse(settings.azure_storage_endpoint or "")

    # Reject non-HTTPS URLs, unexpected storage accounts, and URL credentials.
    if (
        parsed.scheme != "https"
        or parsed.netloc != expected.netloc
        or parsed.username is not None
        or parsed.password is not None
        or parsed.query
        or parsed.fragment
    ):
        raise ValueError("Figure URL must belong to the configured Azure Storage account.")

    # Read the configured Blob Storage container.
    container_name = settings.azure_storage_container

    # Require a configured container name.
    if not container_name:
        raise ValueError("AZURE_STORAGE_CONTAINER is not configured.")

    # Decode the URL path into its container and blob components.
    path = unquote(parsed.path).lstrip("/")

    # Require the URL to reference the configured container.
    if not path.startswith(f"{container_name}/"):
        raise ValueError("Figure URL references an unexpected storage container.")

    # Extract the blob name after the container prefix.
    blob_name = path[len(container_name) + 1:]

    # Restrict downloads to the expected figure directory.
    if (
        not blob_name.startswith("figures/")
        or not blob_name.lower().endswith(".png")
        or any(part in ("", ".", "..") for part in blob_name.split("/"))
        or "\\" in blob_name
    ):
        raise ValueError("Invalid figure blob path.")

    # Reuse NEXORA's existing authenticated Blob Storage client.
    service_client = create_blob_service_client()

    # Select the validated figure blob.
    blob_client = service_client.get_blob_client(
        container=container_name,
        blob=blob_name,
    )

    # Download the image without modifying the stored blob.
    image_bytes = blob_client.download_blob().readall()

    # Reject empty image responses.
    if not image_bytes:
        raise ValueError("Azure Blob Storage returned an empty figure image.")

    # Return the original PNG bytes for visual analysis.
    return image_bytes
