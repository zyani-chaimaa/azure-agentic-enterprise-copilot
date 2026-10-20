
# Import a helper for constructing filesystem paths.
from pathlib import Path

# Import configuration utilities that can read environment variables.
from pydantic_settings import BaseSettings, SettingsConfigDict

# Find the root directory of our repository.
PROJECT_ROOT = Path(__file__).resolve().parent.parent


# Define all configurable application settings.
class Settings(BaseSettings):
    # Store the Azure Foundry model inference endpoint.
    azure_openai_endpoint: str = (
        "https://enterprise-copilot-dev-resource.services.ai.azure.com/openai/v1/"
    )

    # Store the name of the model deployment.
    azure_openai_deployment: str = "gpt-5.4-mini"

        # Name of the embedding model deployment in Azure Foundry.
    azure_embedding_deployment: str = "text-embedding-3-small"

    # Azure AI Search service endpoint, configured through .env.
    azure_search_endpoint: str = ""

    # Name of the search index containing our document chunks.
    azure_search_index: str = "enterprise-documents-v1"

    # Azure Blob Storage account endpoint, configured through .env.
    azure_storage_endpoint: str = ""

    # Container holding original enterprise documents.
    azure_storage_container: str = "enterprise-documents"

    # Store the location of our development database.
    database_path: Path = PROJECT_ROOT / "data" / "business.db"

    # Azure SQL server hosting our Olist business dataset.
    azure_sql_server: str = "sql-enterprise-copilot-dev.database.windows.net"

    # Azure SQL database containing our eight Olist tables.
    azure_sql_database: str = "sqldb-enterprise-copilot-dev"

    # Allow settings to be overridden using a local .env file.
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )


# Create one settings object for the application.
settings = Settings()
