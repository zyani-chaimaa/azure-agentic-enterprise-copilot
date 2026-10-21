# Import Azure credentials for passwordless authentication.
from azure.identity import DefaultAzureCredential

# Import the client used to analyze document layouts.
from azure.ai.documentintelligence import DocumentIntelligenceClient

# Import NEXORA's centralized Azure configuration.
from app.config import settings


# Create an authenticated Azure Document Intelligence client.
def create_document_intelligence_client() -> DocumentIntelligenceClient:

    # Read the endpoint from our environment-based configuration.
    endpoint = settings.azure_document_intelligence_endpoint

    # Stop with a clear error if the Azure resource is not configured.
    if not endpoint:
        raise ValueError(
            "AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT is not configured."
        )

    # Use Azure CLI credentials locally or Managed Identity in Azure.
    credential = DefaultAzureCredential(
        exclude_interactive_browser_credential=True
    )

    # Create the client without sending an analysis request.
    client = DocumentIntelligenceClient(
        endpoint=endpoint,
        credential=credential,
    )

    # Return the client for use by our document extraction functions.
    return client


# Analyze a local PDF using Azure AI Document Intelligence.
def analyze_pdf_layout(file_path: str):

    # Import Path to validate the supplied file location.
    from pathlib import Path

    # Convert the supplied filename into a filesystem path.
    path = Path(file_path)

    # Reject missing files and directories.
    if not path.is_file():
        raise FileNotFoundError(f"PDF file not found: {path}")

    # Reject unsupported file extensions.
    if path.suffix.lower() != ".pdf":
        raise ValueError("Only PDF files are supported.")

    # Create the authenticated Azure Document Intelligence client.
    client = create_document_intelligence_client()

    # Open the PDF as binary data and close it automatically afterward.
    with path.open("rb") as pdf_file:

        # Submit the document to the configured layout analysis model.
        poller = client.begin_analyze_document(
            model_id=settings.azure_document_intelligence_model,
            body=pdf_file,
            content_type="application/pdf",
        )

        # Wait for Azure to complete the document analysis.
        result = poller.result()

    # Return the structured analysis result for further processing.
    return result
