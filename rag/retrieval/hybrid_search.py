# Import Azure credentials for passwordless authentication.
from azure.identity import DefaultAzureCredential

# Import the Azure AI Search document client.
from azure.search.documents import SearchClient

# Import the vector query configuration.
from azure.search.documents.models import VectorizedQuery

# Import our Azure application settings.
from app.config import settings

# Import the embedding function we have already tested.
from rag.ingestion.embedder import embed_text


# Search indexed enterprise documents using keywords and vectors.
def hybrid_search(question: str, top_k: int = 5) -> list[dict]:

    # Reject questions that are empty or contain only spaces.
    if not question or not question.strip():
        raise ValueError("The search question cannot be empty.")

    # Ensure the requested number of results is valid.
    if top_k < 1:
        raise ValueError("top_k must be at least 1.")

    # Convert the question into an embedding vector.
    question_vector = embed_text(question)

    # Obtain Azure credentials from the local CLI or Managed Identity.
    credential = DefaultAzureCredential(
        exclude_interactive_browser_credential=True
    )

    # Connect to our existing Azure AI Search index.
    client = SearchClient(
        endpoint=settings.azure_search_endpoint,
        index_name=settings.azure_search_index,
        credential=credential,
    )

    # Define a vector search against our content_vector field.
    vector_query = VectorizedQuery(
        vector=question_vector,
        k_nearest_neighbors=top_k,
        fields="content_vector",
    )

    # Execute hybrid search using text and vector similarity.
    results = client.search(
        search_text=question,
        vector_queries=[vector_query],
        top=top_k,
        select=[
            "chunk_id",
            "document_id",
            "filename",
            "source_uri",
            "page_number",
            "content",
        ],
    )

    # Prepare a list to store retrieved passages.
    passages = []

    # Read each search result returned by Azure.
    for result in results:

        # Preserve the source information needed for citations.
        passages.append(
            {
                "chunk_id": result["chunk_id"],
                "document_id": result["document_id"],
                "filename": result["filename"],
                "source_uri": result["source_uri"],
                "page_number": result["page_number"],
                "content": result["content"],
                "score": result.get("@search.score"),
            }
        )

    # Return the ranked passages.
    return passages