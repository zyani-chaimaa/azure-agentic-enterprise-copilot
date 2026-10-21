# Import pytest to test expected errors.
import pytest

# Import patch to mock Azure dependencies.
from unittest.mock import patch

# Import the Blob Storage client factory.
from rag.ingestion.blob_storage import create_blob_service_client


# Verify that missing storage configuration is rejected.
@pytest.mark.parametrize("endpoint", ["", "   "])
def test_blob_storage_rejects_missing_endpoint(endpoint):

    # Simulate an empty or whitespace-only storage endpoint.
    with patch(
        "rag.ingestion.blob_storage.settings.azure_storage_endpoint",
        endpoint,
    ):

        # Verify that the client factory raises a clear error.
        with pytest.raises(ValueError, match="AZURE_STORAGE_ENDPOINT"):
            create_blob_service_client()


# Verify that the client uses Azure identity authentication.
def test_blob_storage_client_configuration():

    # Define a simulated Azure Storage account endpoint.
    endpoint = "https://example.blob.core.windows.net"

    # Replace the real Azure credential provider with a mock.
    with patch(
        "rag.ingestion.blob_storage.DefaultAzureCredential"
    ) as mock_credential:

        # Replace the real Blob Storage client with a mock.
        with patch(
            "rag.ingestion.blob_storage.BlobServiceClient"
        ) as mock_client:

            # Supply the simulated storage endpoint.
            with patch(
                "rag.ingestion.blob_storage.settings.azure_storage_endpoint",
                endpoint,
            ):

                # Create the simulated Blob Storage client.
                result = create_blob_service_client()

                # Verify that interactive browser authentication is disabled.
                mock_credential.assert_called_once_with(
                    exclude_interactive_browser_credential=True
                )

                # Verify that the correct endpoint and credential are used.
                mock_client.assert_called_once_with(
                    account_url=endpoint,
                    credential=mock_credential.return_value,
                )

                # Verify that the factory returns the created client.
                assert result is mock_client.return_value


# Import the new figure upload function.
from rag.ingestion.blob_storage import upload_figure_image


# Verify that a figure is uploaded with its source metadata.
def test_upload_figure_image_success():

    # Replace the real storage client factory with a mock.
    with patch(
        "rag.ingestion.blob_storage.create_blob_service_client"
    ) as mock_factory:

        # Access the simulated Azure Storage client.
        mock_service = mock_factory.return_value

        # Access the simulated blob client.
        mock_blob = mock_service.get_blob_client.return_value

        # Provide a fake private blob URI.
        mock_blob.url = (
            "https://example.blob.core.windows.net/"
            "enterprise-documents/figures/REPORT-001/page-5/figure-1.png"
        )

        # Upload simulated PNG image data.
        uri = upload_figure_image(
            image_bytes=b"\x89PNG\r\nimage-data",
            document_id="REPORT-001",
            page_number=5,
            figure_id="figure-1",
        )

        # Verify that the expected container and path were selected.
        mock_service.get_blob_client.assert_called_once_with(
            container="enterprise-documents",
            blob="figures/REPORT-001/page-5/figure-1.png",
        )

        # Verify that the image was uploaded exactly once.
        mock_blob.upload_blob.assert_called_once()

        # Inspect the upload parameters.
        args, kwargs = mock_blob.upload_blob.call_args

        # Verify that the original binary image was uploaded.
        assert args[0] == b"\x89PNG\r\nimage-data"

        # Verify that repeated uploads replace the same figure.
        assert kwargs["overwrite"] is True

        # Verify that the uploaded image has the correct MIME type.
        assert kwargs["content_settings"].content_type == "image/png"

        # Verify that source metadata is preserved.
        assert kwargs["metadata"] == {
            "document_id": "REPORT-001",
            "page_number": "5",
            "figure_id": "figure-1",
        }

        # Verify that the storage URI is returned.
        assert uri == mock_blob.url


# Verify that empty image data is rejected.
@pytest.mark.parametrize("image_bytes", [b"", None, "not-bytes"])
def test_upload_rejects_invalid_image_data(image_bytes):

    # Invalid image data must fail before contacting Azure.
    with pytest.raises(ValueError, match="binary data"):
        upload_figure_image(image_bytes, "REPORT-001", 1, "figure-1")


# Verify that unsafe document and figure identifiers are rejected.
@pytest.mark.parametrize(
    "document_id,figure_id",
    [
        ("", "figure-1"),
        ("REPORT-001", ""),
        ("../report", "figure-1"),
        ("REPORT-001", "../figure"),
        ("REPORT-001", r"folder\figure"),
    ],
)
def test_upload_rejects_invalid_identifiers(document_id, figure_id):

    # Invalid identifiers must not become blob paths.
    with pytest.raises(ValueError, match="Invalid"):
        upload_figure_image(
            b"image-data",
            document_id,
            1,
            figure_id,
        )


# Verify that page numbers must be positive integers.
@pytest.mark.parametrize("page_number", [0, -1, True, 1.5])
def test_upload_rejects_invalid_page_number(page_number):

    # Invalid page numbers must fail before contacting Azure.
    with pytest.raises(ValueError, match="page_number"):
        upload_figure_image(
            b"image-data",
            "REPORT-001",
            page_number,
            "figure-1",
        )


# Verify that a missing destination container is rejected.
def test_upload_rejects_missing_container():

    # Simulate an unconfigured Azure Storage container.
    with patch(
        "rag.ingestion.blob_storage.settings.azure_storage_container",
        "",
    ):

        # Confirm that the function reports the configuration problem.
        with pytest.raises(ValueError, match="AZURE_STORAGE_CONTAINER"):
            upload_figure_image(
                b"image-data",
                "REPORT-001",
                1,
                "figure-1",
            )
