# Import the credential provider for Microsoft Entra authentication.
from azure.identity import DefaultAzureCredential

# Import the Azure AI Search index management client.
from azure.search.documents.indexes import SearchIndexClient

# Import the Azure AI Search index and field definitions.
from azure.search.documents.indexes.models import (
    SearchIndex,
    SearchField,
    SearchFieldDataType,
    SimpleField,
    SearchableField,
    VectorSearch,
    VectorSearchProfile,
    HnswAlgorithmConfiguration,
)

# Import our existing application configuration.
from app.config import settings


# Define the embedding size produced by text-embedding-3-small.
EMBEDDING_DIMENSIONS = 1536


# Create or update the document search index.
def create_search_index():

    # Stop early if the Azure AI Search endpoint is missing.
    if not settings.azure_search_endpoint:
        raise ValueError("AZURE_SEARCH_ENDPOINT is not configured.")

    # Authenticate using the current Azure identity.
    credential = DefaultAzureCredential()

    # Create a client for managing Azure AI Search indexes.
    client = SearchIndexClient(
        endpoint=settings.azure_search_endpoint,
        credential=credential,
    )

    # Define the fields stored for every document chunk.
    fields = [
        # Unique identifier used as the search document key.
        SimpleField(
            name="chunk_id",
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
        ),

        # Original document identifier for traceability.
        SimpleField(
            name="document_id",
            type=SearchFieldDataType.String,
            filterable=True,
        ),

        # Original PDF filename for citations.
        SearchableField(
            name="filename",
            type=SearchFieldDataType.String,
            filterable=True,
        ),

        # Reference to the original document.
        SimpleField(
            name="source_uri",
            type=SearchFieldDataType.String,
        ),

        # Original PDF page number.
        SimpleField(
            name="page_number",
            type=SearchFieldDataType.Int32,
            filterable=True,
        ),

        # Chunk position within the source page.
        SimpleField(
            name="chunk_index",
            type=SearchFieldDataType.Int32,
        ),

        # Extracted text used for keyword and hybrid search.
        SearchableField(
            name="content",
            type=SearchFieldDataType.String,
        ),

        # Embedding vector used for semantic similarity search.
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(
                SearchFieldDataType.Single
            ),
            searchable=True,
            vector_search_dimensions=EMBEDDING_DIMENSIONS,
            vector_search_profile_name="document-vector-profile",
        ),
    ]

    # Configure approximate nearest-neighbor vector search.
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="document-hnsw",
            )
        ],
        profiles=[
            VectorSearchProfile(
                name="document-vector-profile",
                algorithm_configuration_name="document-hnsw",
            )
        ],
    )

    # Combine the fields and vector configuration into one index.
    index = SearchIndex(
        name=settings.azure_search_index,
        fields=fields,
        vector_search=vector_search,
    )

    # Create the index or update its compatible configuration.
    result = client.create_or_update_index(index)

    # Return the actual index name reported by Azure.
    return result.name


# Allow this module to be executed directly from the project root.
if __name__ == "__main__":

    # Create the index and display the result.
    print("Azure AI Search index:", create_search_index())