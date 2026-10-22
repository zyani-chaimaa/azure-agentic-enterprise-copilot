# Import Path to work with files and directories.
from pathlib import Path

# Import JSON to read our saved chunk caches and backup.
import json

# Import SHA-256 hashing to identify a specific version of our data.
import hashlib

# Identify the Webshoppers document we are updating.
DOCUMENT_ID = "webshoppers-38-2018"

# Identify the expected Azure AI Search index.
EXPECTED_INDEX = "enterprise-documents-v2"

# Define the directory containing the original extraction.
DATA_DIR = Path("data/documents/multimodal")

# Define the separate directory for the new vision-enriched extraction.
REINGESTION_DIR = DATA_DIR / "reingestion-webshoppers-v2"

# Locate the original chunk cache, which must remain unchanged.
ORIGINAL_CACHE = DATA_DIR / "webshoppers-38.checkpoint.chunks.json"

# Locate the new GPT-5.4-mini-enriched chunk cache.
PREPARED_CACHE = REINGESTION_DIR / "prepared.chunks.json"

# Locate the verified backup of the existing Azure Search records.
BACKUP_PATH = REINGESTION_DIR / "original-search-backup.json"

# Reserve a separate checkpoint for the selective reindexing operation.
CHECKPOINT_PATH = REINGESTION_DIR / "vision-reindex.checkpoint.json"


# Load a JSON file without modifying its contents.
def load_json(path: Path) -> dict:
    # Reject missing files with an explicit error.
    if not path.is_file():
        raise FileNotFoundError(f"Required file is missing: {path}")

    # Open the file using UTF-8 encoding.
    with path.open("r", encoding="utf-8") as file:
        # Parse the JSON and return the resulting Python object.
        return json.load(file)


# Validate a chunk cache and organize its chunks by their unique IDs.
def validate_chunk_cache(cache: dict, cache_name: str) -> dict[str, dict]:

    # Require the cache to be a JSON object.
    if not isinstance(cache, dict):
        raise ValueError(f"{cache_name}: expected a JSON object.")

    # Verify that the cache belongs to the correct document.
    if cache.get("document_id") != DOCUMENT_ID:
        raise ValueError(f"{cache_name}: incorrect document_id.")

    # Read the collection of extracted chunks.
    chunks = cache.get("chunks")

    # Require the chunks collection to be a list.
    if not isinstance(chunks, list):
        raise ValueError(f"{cache_name}: chunks must be a list.")

    # Require exactly 1,588 chunks for this migration.
    if len(chunks) != 1588:
        raise ValueError(
            f"{cache_name}: expected 1588 chunks, found {len(chunks)}."
        )

    # Prepare a dictionary indexed by chunk ID.
    chunks_by_id = {}

    # Inspect every chunk individually.
    for chunk in chunks:

        # Require each chunk to be a JSON object.
        if not isinstance(chunk, dict):
            raise ValueError(f"{cache_name}: invalid chunk object.")

        # Read the unique chunk identifier.
        chunk_id = chunk.get("chunk_id")

        # Reject missing or empty identifiers.
        if not isinstance(chunk_id, str) or not chunk_id.strip():
            raise ValueError(f"{cache_name}: invalid chunk_id.")

        # Reject duplicate identifiers.
        if chunk_id in chunks_by_id:
            raise ValueError(f"{cache_name}: duplicate chunk_id: {chunk_id}")

        # Verify that this chunk belongs to Webshoppers.
        if chunk.get("document_id") != DOCUMENT_ID:
            raise ValueError(
                f"{cache_name}: incorrect document_id for {chunk_id}."
            )

        # Require a nonempty content type.
        if not isinstance(chunk.get("content_type"), str) or not chunk["content_type"]:
            raise ValueError(f"{cache_name}: invalid content_type for {chunk_id}.")

        # Require the extracted content to be text.
        if not isinstance(chunk.get("content"), str):
            raise ValueError(f"{cache_name}: invalid content for {chunk_id}.")

        # Store the validated chunk under its identifier.
        chunks_by_id[chunk_id] = chunk

    # Return the validated collection for efficient comparisons.
    return chunks_by_id


# Select figure chunks whose descriptions changed without changing metadata.
def select_changed_figures(
    original: dict[str, dict],
    prepared: dict[str, dict],
) -> list[dict]:

    # Require both caches to contain exactly the same chunk identifiers.
    if set(original) != set(prepared):
        raise ValueError("Original and prepared chunk IDs do not match.")

    # Collect only the figure chunks that require reindexing.
    changed_figures = []

    # Visit each chunk in a deterministic order.
    for chunk_id in sorted(original):

        # Retrieve the original chunk.
        old_chunk = original[chunk_id]

        # Retrieve the newly prepared chunk.
        new_chunk = prepared[chunk_id]

        # Compare all metadata fields except the description itself.
        old_metadata = {
            key: value
            for key, value in old_chunk.items()
            if key != "content"
        }

        # Extract the prepared chunk's metadata using the same rule.
        new_metadata = {
            key: value
            for key, value in new_chunk.items()
            if key != "content"
        }

        # Stop if any metadata field was added, removed, or changed.
        if old_metadata != new_metadata:
            raise ValueError(f"Metadata changed for chunk: {chunk_id}")

        # Skip chunks whose content has not changed.
        if old_chunk["content"] == new_chunk["content"]:
            continue

        # Refuse changes to text or table chunks.
        if old_chunk["content_type"] != "figure":
            raise ValueError(f"Nonfigure content changed: {chunk_id}")

        # Collect the enriched figure for selective indexing.
        changed_figures.append(new_chunk)

    # Require the exact number established by our earlier validation.
    if len(changed_figures) != 115:
        raise ValueError(
            f"Expected 115 changed figures, found {len(changed_figures)}."
        )

    # Return only the validated figure chunks.
    return changed_figures


# Verify that the Azure Search backup matches the original chunk cache.
def validate_backup(
    backup: dict,
    original: dict[str, dict],
) -> None:

    # Require the backup to be a JSON object.
    if not isinstance(backup, dict):
        raise ValueError("Backup must be a JSON object.")

    # Verify that the backup belongs to the expected search index.
    if backup.get("index_name") != EXPECTED_INDEX:
        raise ValueError("Backup index name does not match.")

    # Verify that the backup belongs to the Webshoppers document.
    if backup.get("document_id") != DOCUMENT_ID:
        raise ValueError("Backup document_id does not match.")

    # Require the expected number of backed-up records.
    if backup.get("record_count") != 1588:
        raise ValueError("Backup record count does not match.")

    # Retrieve the backed-up Azure Search documents.
    documents = backup.get("documents")

    # Require exactly 1,588 documents in a list.
    if not isinstance(documents, list) or len(documents) != 1588:
        raise ValueError("Backup must contain exactly 1588 documents.")

    # Define the fields needed to preserve the original search records.
    required_fields = {
        "chunk_id",
        "element_id",
        "document_id",
        "filename",
        "source_uri",
        "page_number",
        "chunk_index",
        "content_type",
        "content",
        "asset_uri",
        "section_heading",
        "extraction_method",
    }

    # Prepare a set to detect duplicate document identifiers.
    seen_ids = set()

    # Validate each backed-up document.
    for document in documents:

        # Require each document to be a JSON object.
        if not isinstance(document, dict):
            raise ValueError("Invalid backup document.")

        # Require every field needed for recovery.
        if not required_fields.issubset(document):
            raise ValueError("Backup document has missing fields.")

        # Retrieve the unique Azure Search document key.
        chunk_id = document["chunk_id"]

        # Reject missing or duplicate document identifiers.
        if not isinstance(chunk_id, str) or not chunk_id or chunk_id in seen_ids:
            raise ValueError("Invalid or duplicate backup chunk ID.")

        # Record the validated identifier.
        seen_ids.add(chunk_id)

        # Verify that the record belongs to Webshoppers.
        if document["document_id"] != DOCUMENT_ID:
            raise ValueError(f"Backup document identity mismatch: {chunk_id}")

        # Require the record to exist in the original cache.
        if chunk_id not in original:
            raise ValueError(f"Unexpected backup chunk: {chunk_id}")

        # Verify that the original indexed content was preserved.
        if document["content"] != original[chunk_id]["content"]:
            raise ValueError(f"Backup content mismatch: {chunk_id}")

    # Require the backup and original cache to contain identical IDs.
    if seen_ids != set(original):
        raise ValueError("Backup and original cache chunk IDs do not match.")


# Verify that backed-up Azure Search metadata matches the original cache.
def validate_backup_metadata(
    backup: dict,
    original: dict[str, dict],
) -> None:

    # Define the metadata fields shared by the cache and Azure Search.
    metadata_fields = (
        "element_id",
        "document_id",
        "filename",
        "source_uri",
        "page_number",
        "chunk_index",
        "content_type",
        "asset_uri",
        "section_heading",
        "extraction_method",
    )

    # Visit each document in the verified backup.
    for document in backup["documents"]:

        # Read the document's unique search key.
        chunk_id = document["chunk_id"]

        # Retrieve the matching original chunk.
        original_chunk = original[chunk_id]

        # Compare every metadata field independently.
        for field in metadata_fields:

            # Require the field to exist in both records.
            if field not in document or field not in original_chunk:
                raise ValueError(
                    f"Missing metadata field '{field}' for {chunk_id}"
                )

            # Reject differences between original and backed-up metadata.
            if document[field] != original_chunk[field]:
                raise ValueError(
                    f"Backup metadata mismatch: {chunk_id}, field '{field}'"
                )


# Build a validated migration plan without contacting Azure.
def build_migration_plan() -> tuple[list[dict], str]:

    # Read the original chunk cache.
    original_cache = load_json(ORIGINAL_CACHE)

    # Read the newly prepared vision-enriched cache.
    prepared_cache = load_json(PREPARED_CACHE)

    # Read the verified backup of existing Azure Search records.
    backup = load_json(BACKUP_PATH)

    # Validate and organize the original chunks by ID.
    original = validate_chunk_cache(original_cache, "Original cache")

    # Validate and organize the enriched chunks by ID.
    prepared = validate_chunk_cache(prepared_cache, "Prepared cache")

    # Identify exactly the 115 changed figure chunks.
    changed_figures = select_changed_figures(original, prepared)

    # Verify the backup contains the expected original records.
    validate_backup(backup, original)

    # Verify the backed-up metadata matches the original cache.
    validate_backup_metadata(backup, original)

    # Create a SHA-256 calculator for this specific migration.
    digest = hashlib.sha256()

    # Include the target index and document identity in the fingerprint.
    digest.update(
        f"{EXPECTED_INDEX}:{DOCUMENT_ID}:".encode("utf-8")
    )

    # Process the selected figures in a deterministic order.
    for chunk in changed_figures:

        # Serialize the complete chunk, including content and metadata.
        serialized = json.dumps(
            chunk,
            sort_keys=True,
            ensure_ascii=False,
            separators=(",", ":"),
        )

        # Include its byte length to distinguish chunk boundaries.
        encoded = serialized.encode("utf-8")

        # Add the serialized length to the fingerprint.
        digest.update(len(encoded).to_bytes(8, byteorder="big"))

        # Add the complete chunk contents to the fingerprint.
        digest.update(encoded)

    # Produce the final hexadecimal SHA-256 fingerprint.
    fingerprint = digest.hexdigest()

    # Return the selected figures and their version fingerprint.
    return changed_figures, fingerprint


# Import command-line argument parsing.
import argparse


# Execute the selective migration only when explicitly authorized.
def apply_migration(figures: list[dict], fingerprint: str) -> int:

    # Import Azure authentication only when applying the migration.
    from azure.identity import DefaultAzureCredential

    # Import the Azure Search client only when applying the migration.
    from azure.search.documents import SearchClient

    # Import NEXORA's centralized Azure configuration.
    from app.config import settings

    # Import the validated multimodal chunk model.
    from rag.models.multimodal_chunk import MultimodalChunk

    # Import the existing checkpoint-aware indexing function.
    from rag.ingestion.multimodal_index_documents import index_multimodal_chunks

    # Refuse to use an unexpected Azure Search index.
    if settings.azure_multimodal_search_index != EXPECTED_INDEX:
        raise ValueError("Configured Azure Search index does not match migration target.")

    # Refuse indexing if the Azure endpoint is missing.
    if not settings.azure_search_endpoint:
        raise ValueError("Azure Search endpoint is not configured.")

    # Load the verified original backup.
    backup = load_json(BACKUP_PATH)

    # Create Azure credentials using the existing authentication setup.
    credential = DefaultAzureCredential(
        exclude_interactive_browser_credential=True
    )

    # Connect to the exact index being migrated.
    client = SearchClient(
        endpoint=settings.azure_search_endpoint,
        index_name=EXPECTED_INDEX,
        credential=credential,
    )

    # Ensure the live index has the expected total number of records.
    # Count only Webshoppers records, not every document in the shared index.
    matching_records = client.search(
        search_text="*",
        filter=f"document_id eq '{DOCUMENT_ID}'",
        include_total_count=True,
        top=0,
    )

    # Read the count returned by Azure AI Search.
    document_count = matching_records.get_count()

    # Stop if Azure cannot provide a reliable count.
    if document_count is None:
        raise RuntimeError("Azure Search did not return a document count.")

    # Require exactly the 1,588 Webshoppers records in our validated backup.
    if document_count != 1588:
        raise RuntimeError(
            f"Unexpected Webshoppers document count: {document_count}; expected 1588."
        )
        raise ValueError("Live Azure Search document count does not match.")

    # Import checkpoint reading and atomic checkpoint saving.
    from rag.ingestion.multimodal_checkpoint import load_checkpoint, save_checkpoint

    # Load progress only when it matches this document and content fingerprint.
    completed = load_checkpoint(CHECKPOINT_PATH, DOCUMENT_ID, fingerprint)

    # Inspect all selected live figures and recover confirmed successful uploads.
    recovered = reconcile_live_progress(client, figures, backup, completed)

    # Persist recovered progress only after every live figure passes verification.
    if recovered != completed:
        save_checkpoint(
            CHECKPOINT_PATH,
            DOCUMENT_ID,
            sorted(recovered),
            fingerprint=fingerprint,
        )

    # Convert the selected dictionaries into validated chunk models.
    chunks = [MultimodalChunk(**figure) for figure in figures]

    # Reuse the existing indexer with a separate resumable checkpoint.
    return index_multimodal_chunks(
        chunks,
        checkpoint_path=CHECKPOINT_PATH,
        fingerprint=fingerprint,
        batch_size=1,
    )


# Verify the expected live state before starting or resuming indexing.
def verify_resumable_migration(
    search_client,
    figures: list[dict],
    backup: dict,
    completed_ids: set[str],
) -> None:

    # Organize the original backup records by chunk ID.
    originals = {
        document["chunk_id"]: document
        for document in backup["documents"]
    }

    # Organize the enriched figures by chunk ID.
    prepared = {
        figure["chunk_id"]: figure
        for figure in figures
    }

    # Reject checkpoint IDs that are outside this migration.
    if not completed_ids.issubset(prepared):
        raise ValueError("Checkpoint contains unexpected chunk IDs.")

    # Define the fields that must match the expected record.
    fields = (
        "chunk_id",
        "element_id",
        "document_id",
        "filename",
        "source_uri",
        "page_number",
        "chunk_index",
        "content_type",
        "content",
        "asset_uri",
        "section_heading",
        "extraction_method",
    )

    # Check all selected figures before allowing further uploads.
    for chunk_id in sorted(prepared):

        # Retrieve the current Azure Search record.
        live = search_client.get_document(
            key=chunk_id,
            selected_fields=list(fields),
        )

        # Completed figures must match the enriched version.
        if chunk_id in completed_ids:
            expected = prepared[chunk_id]

        # Pending figures must still match the original backup.
        else:
            expected = originals[chunk_id]

        # Compare every protected field against the expected version.
        for field in fields:

            # Reject missing fields or unexpected differences.
            if field not in live or live[field] != expected[field]:
                raise ValueError(
                    f"Unexpected live record state: {chunk_id}, field '{field}'"
                )

    # Report the verified checkpoint progress.
    print(
        f"PASS: {len(completed_ids)} completed and "
        f"{len(prepared) - len(completed_ids)} pending figures verified."
    )


# Reconcile live figure records with checkpoint progress after an interruption.
def reconcile_live_progress(
    search_client,
    figures: list[dict],
    backup: dict,
    completed_ids: set[str],
) -> set[str]:

    # Import the checkpoint writer only when reconciliation runs.
    from rag.ingestion.multimodal_checkpoint import save_checkpoint

    # Organize backed-up original records by their unique IDs.
    originals = {
        document["chunk_id"]: document
        for document in backup["documents"]
    }

    # Organize the enriched figures by their unique IDs.
    prepared = {
        figure["chunk_id"]: figure
        for figure in figures
    }

    # Reject progress belonging to another migration.
    if not completed_ids.issubset(prepared):
        raise ValueError("Checkpoint contains unexpected chunk IDs.")

    # Define all fields that must match the expected document version.
    fields = (
        "chunk_id",
        "element_id",
        "document_id",
        "filename",
        "source_uri",
        "page_number",
        "chunk_index",
        "content_type",
        "content",
        "asset_uri",
        "section_heading",
        "extraction_method",
    )

    # Start with a copy so existing checkpoint progress is preserved.
    recovered = set(completed_ids)

    # Track figures that are still in their original state.
    pending_count = 0

    # Examine every selected figure before changing the checkpoint.
    for chunk_id in sorted(prepared):

        # Retrieve the current record using its exact Azure Search key.
        live = search_client.get_document(
            key=chunk_id,
            selected_fields=list(fields),
        )

        # Retrieve the original version from our verified backup.
        original = originals[chunk_id]

        # Retrieve the enriched version from the prepared cache.
        enriched = prepared[chunk_id]

        # Check whether every protected field matches the original.
        matches_original = all(
            field in live and live[field] == original[field]
            for field in fields
        )

        # Check whether every protected field matches the enriched version.
        matches_enriched = all(
            field in live and live[field] == enriched[field]
            for field in fields
        )

        # Previously checkpointed records must remain enriched.
        if chunk_id in completed_ids and not matches_enriched:
            raise ValueError(
                f"Checkpointed figure no longer matches enriched content: {chunk_id}"
            )

        # Recognize enriched records even if the checkpoint missed them.
        if matches_enriched:
            recovered.add(chunk_id)

        # Leave unchanged original records pending for indexing.
        elif matches_original:
            pending_count += 1

        # Refuse records that match neither expected version.
        else:
            raise ValueError(
                f"Unexpected live record state during recovery: {chunk_id}"
            )

    # Report the number of successful uploads recovered from Azure.
    newly_recovered = len(recovered - completed_ids)

    # Display the verified migration state.
    print(
        f"Verified: {len(recovered)} enriched, "
        f"{pending_count} pending, "
        f"{newly_recovered} recovered."
    )

    # Return verified progress without modifying the checkpoint yet.
    return recovered


# Execute the migration utility through its command-line interface.
def main() -> None:

    # Create a parser for the migration command.
    parser = argparse.ArgumentParser(
        description="Safely reindex Webshoppers vision-enriched figures."
    )

    # Require an explicit flag before performing live Azure writes.
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Verify Azure records and apply the selective reindexing.",
    )

    # Parse the supplied command-line arguments.
    args = parser.parse_args()

    # Validate all local inputs and calculate the migration fingerprint.
    figures, fingerprint = build_migration_plan()

    # Display the target search index.
    print(f"Target index: {EXPECTED_INDEX}")

    # Display the target document.
    print(f"Document ID: {DOCUMENT_ID}")

    # Display the number of selected figure records.
    print(f"Selected figure chunks: {len(figures)}")

    # Display the deterministic content fingerprint.
    print(f"Migration fingerprint: {fingerprint}")

    # Display the isolated checkpoint path.
    print(f"Checkpoint path: {CHECKPOINT_PATH}")

    # Stop safely after validation unless live indexing was requested.
    if not args.apply:
        print("DRY RUN ONLY: no Azure calls, embeddings, or index updates.")
        return

    # Clearly announce that live indexing was explicitly requested.
    print("APPLY MODE: verifying live Azure Search records.")

    # Execute the validated selective migration.
    uploaded = apply_migration(figures, fingerprint)

    # Report the number of records uploaded in this execution.
    print(f"Migration run complete: {uploaded} figure records uploaded.")


# Run the command-line interface only when executed as a module.
if __name__ == "__main__":

    # Invoke the migration command.
    main()
