# Import the Azure AI Search client type.
from azure.search.documents import SearchClient


# Upload a batch and identify individually successful documents.
def upload_multimodal_batch(
    client: SearchClient,
    documents: list[dict],
) -> tuple[set[str], dict[str, int | None]]:

    # Reject empty batches.
    if not documents:
        raise ValueError("Cannot upload an empty batch.")

    # Identify every submitted document by its Azure Search key.
    submitted_ids = [document["chunk_id"] for document in documents]

    # Prevent ambiguous result matching.
    if len(submitted_ids) != len(set(submitted_ids)):
        raise ValueError("Duplicate chunk IDs in upload batch.")

    # Submit all documents in one Azure AI Search request.
    results = client.upload_documents(documents=documents)

    # Reject a missing response.
    if not results:
        raise RuntimeError("Azure Search returned no upload results.")

    # Store successful document IDs.
    succeeded = set()

    # Store unsuccessful document IDs and their HTTP status codes.
    failed = {}

    # Track all response IDs to detect missing or duplicate results.
    seen = set()

    # Inspect every result returned by Azure.
    for result in results:

        # Read the document key associated with this result.
        chunk_id = getattr(result, "key", None)

        # Reject unknown or duplicate response keys.
        if chunk_id not in submitted_ids or chunk_id in seen:
            raise RuntimeError("Invalid or duplicate Azure Search result key.")

        # Record this response key.
        seen.add(chunk_id)

        # Save confirmed successful uploads.
        if result.succeeded:
            succeeded.add(chunk_id)

        # Preserve failed IDs and their status codes.
        else:
            failed[chunk_id] = getattr(result, "status_code", None)

    # Reject incomplete responses instead of guessing outcomes.
    if seen != set(submitted_ids):
        raise RuntimeError("Azure Search returned incomplete batch results.")

    # Return successes and failures separately.
    return succeeded, failed
