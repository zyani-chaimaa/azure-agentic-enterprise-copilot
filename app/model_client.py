
# Import the OpenAI-compatible API client.
from openai import OpenAI

# Import Azure's credential chain and token-provider helper.
from azure.identity import DefaultAzureCredential, get_bearer_token_provider

# Import our centralized application configuration.
from app.config import settings


# Define a factory function for creating authenticated clients.
def create_model_client() -> OpenAI:
    # Use Azure CLI locally and Managed Identity in Azure.
    credential = DefaultAzureCredential(
        exclude_interactive_browser_credential=True
    )

    # Request an access token for Microsoft Foundry inference.
    token_provider = get_bearer_token_provider(
        credential,
        "https://ai.azure.com/.default",
    )

    # Create and return the model API client.
    return OpenAI(
        base_url=settings.azure_openai_endpoint,
        api_key=token_provider,
        timeout=60.0,
        max_retries=1,
    )
