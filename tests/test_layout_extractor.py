# Import pytest for exception testing.
import pytest

# Import mock utilities to isolate external Azure dependencies.
from unittest.mock import patch, sentinel

# Import the client factory we want to test.
from rag.ingestion.layout_extractor import create_document_intelligence_client


# Verify that a missing Azure endpoint produces a clear error.
def test_missing_document_intelligence_endpoint():

    # Simulate an environment without a configured endpoint.
    with patch(
        "rag.ingestion.layout_extractor.settings.azure_document_intelligence_endpoint",
        "",
    ):

        # Confirm that the client factory rejects missing configuration.
        with pytest.raises(ValueError, match="not configured"):
            create_document_intelligence_client()


# Verify that a configured endpoint creates an authenticated client.
def test_document_intelligence_client_configuration():

    # Use a fake endpoint without connecting to Azure.
    endpoint = "https://example.cognitiveservices.azure.com/"

    # Replace the real Azure credential provider with a mock.
    with patch(
        "rag.ingestion.layout_extractor.DefaultAzureCredential"
    ) as mock_credential:

        # Replace the real Azure client with a mock.
        with patch(
            "rag.ingestion.layout_extractor.DocumentIntelligenceClient"
        ) as mock_client:

            # Supply a fake endpoint through our application settings.
            with patch(
                "rag.ingestion.layout_extractor.settings.azure_document_intelligence_endpoint",
                endpoint,
            ):

                # Call the client factory.
                result = create_document_intelligence_client()

                # Verify that interactive browser authentication is disabled.
                mock_credential.assert_called_once_with(
                    exclude_interactive_browser_credential=True
                )

                # Verify that the correct endpoint and credential are used.
                mock_client.assert_called_once_with(
                    endpoint=endpoint,
                    credential=mock_credential.return_value,
                )

                # Verify that the factory returns the created client.
                assert result is mock_client.return_value
