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
