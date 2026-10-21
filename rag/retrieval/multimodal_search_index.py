# Import Azure identity for passwordless authentication.
from azure.identity import DefaultAzureCredential

# Import the Azure AI Search index management client.
from azure.search.documents.indexes import SearchIndexClient

# Import the SDK classes used to define index fields and vector search.
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

# Import centralized Azure configuration.
from app.config import settings


# Match the dimensions produced by the configured embedding deployment.
EMBEDDING_DIMENSIONS = 1536


# Build the multimodal index definition without contacting Azure.
def build_multimodal_search_index() -> SearchIndex:

    # Prevent the multimodal index from overwriting the existing v1 index.
    if settings.azure_multimodal_search_index == settings.azure_search_index:
        raise ValueError(
            "Multimodal index name must differ from the existing v1 index."
        )

    # Define the fields stored for each multimodal chunk.
    fields = [
        # Unique search document key.
        SimpleField(
            name="chunk_id",
            type=SearchFieldDataType.String,
            key=True,
            filterable=True,
        ),

        # Identifier of the original extracted evidence element.
        SimpleField(
            name="element_id",
            type=SearchFieldDataType.String,
            filterable=True,
        ),

        # Identifier of the source PDF document.
        SimpleField(
            name="document_id",
            type=SearchFieldDataType.String,
            filterable=True,
        ),

        # Searchable filename for document identification.
        SearchableField(
            name="filename",
            type=SearchFieldDataType.String,
            filterable=True,
        ),

        # Location of the original PDF.
        SimpleField(
            name="source_uri",
            type=SearchFieldDataType.String,
        ),

        # Source page used for citations and filtering.
        SimpleField(
            name="page_number",
            type=SearchFieldDataType.Int32,
            filterable=True,
        ),

        # Position of this chunk within its source element.
        SimpleField(
            name="chunk_index",
            type=SearchFieldDataType.Int32,
        ),

        # Evidence type used for filtering and result presentation.
        SimpleField(
            name="content_type",
            type=SearchFieldDataType.String,
            filterable=True,
            facetable=True,
        ),

        # Searchable text representation of the evidence.
        SearchableField(
            name="content",
            type=SearchFieldDataType.String,
        ),

        # Optional Azure Blob URI for figures and charts.
        SimpleField(
            name="asset_uri",
            type=SearchFieldDataType.String,
        ),

        # Optional section heading for contextual retrieval.
        SearchableField(
            name="section_heading",
            type=SearchFieldDataType.String,
        ),

        # Method used to extract the source evidence.
        SimpleField(
            name="extraction_method",
            type=SearchFieldDataType.String,
            filterable=True,
        ),

        # Numerical embedding used for semantic vector search.
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(
                SearchFieldDataType.Single
            ),
            searchable=True,
            vector_search_dimensions=EMBEDDING_DIMENSIONS,
            vector_search_profile_name="multimodal-vector-profile",
        ),
    ]

    # Configure approximate nearest-neighbor search using HNSW.
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="multimodal-hnsw",
            )
        ],
        profiles=[
            VectorSearchProfile(
                name="multimodal-vector-profile",
                algorithm_configuration_name="multimodal-hnsw",
            )
        ],
    )

    # Return the complete local index definition.
    return SearchIndex(
        name=settings.azure_multimodal_search_index,
        fields=fields,
        vector_search=vector_search,
    )


# Create or update the multimodal index in Azure AI Search.
def create_multimodal_search_index() -> str:

    # Reject missing Azure Search configuration.
    if not settings.azure_search_endpoint:
        raise ValueError("AZURE_SEARCH_ENDPOINT is not configured.")

    # Authenticate with Microsoft Entra ID.
    credential = DefaultAzureCredential(
        exclude_interactive_browser_credential=True
    )

    # Connect to the Azure AI Search index management API.
    client = SearchIndexClient(
        endpoint=settings.azure_search_endpoint,
        credential=credential,
    )

    # Construct the index schema.
    index = build_multimodal_search_index()

    # Create or update the index using its configured v2 name.
    result = client.create_or_update_index(index)

    # Return the index name confirmed by Azure.
    return result.name
