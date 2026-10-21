# Import pytest to verify expected errors.
import pytest

# Import patch to replace Azure dependencies with mocks.
from unittest.mock import patch

# Import the function being tested.
from rag.ingestion.figure_extractor import retrieve_figure_image


# Verify that image chunks are combined into complete binary data.
def test_retrieve_figure_image_success():

    # Replace the real Azure client factory with a mock.
    with patch(
        "rag.ingestion.figure_extractor.create_document_intelligence_client"
    ) as mock_factory:

        # Access the simulated Azure client.
        mock_client = mock_factory.return_value

        # Simulate Azure returning an image in multiple chunks.
        mock_client.get_analyze_result_figure.return_value = iter(
            [b"\x89PNG", b"\r\n", b"image-data"]
        )

        # Retrieve the simulated figure.
        image = retrieve_figure_image(
            operation_id="operation-123",
            figure_id="figure-1",
        )

        # Verify that all chunks were combined in the correct order.
        assert image == b"\x89PNG\r\nimage-data"

        # Verify that the correct identifiers were sent to Azure.
        mock_client.get_analyze_result_figure.assert_called_once_with(
            model_id="prebuilt-layout",
            result_id="operation-123",
            figure_id="figure-1",
        )


# Verify that an invalid operation ID is rejected.
@pytest.mark.parametrize("operation_id", ["", "   "])
def test_reject_invalid_operation_id(operation_id):

    # Confirm that invalid identifiers produce a clear error.
    with pytest.raises(ValueError, match="operation ID"):
        retrieve_figure_image(operation_id, "figure-1")


# Verify that an invalid figure ID is rejected.
@pytest.mark.parametrize("figure_id", ["", "   "])
def test_reject_invalid_figure_id(figure_id):

    # Confirm that invalid identifiers produce a clear error.
    with pytest.raises(ValueError, match="figure ID"):
        retrieve_figure_image("operation-123", figure_id)


# Verify that empty image responses are rejected.
def test_reject_empty_figure_image():

    # Replace the real Azure client factory with a mock.
    with patch(
        "rag.ingestion.figure_extractor.create_document_intelligence_client"
    ) as mock_factory:

        # Simulate Azure returning no image data.
        mock_factory.return_value.get_analyze_result_figure.return_value = iter([])

        # Confirm that empty image data is rejected.
        with pytest.raises(ValueError, match="empty figure image"):
            retrieve_figure_image("operation-123", "figure-1")
