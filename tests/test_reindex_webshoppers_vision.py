# Import SHA-256 hashing to independently verify fingerprint behavior.
import hashlib

# Import JSON for creating an independent copy of test data.
import json

# Import unittest.mock to replace filesystem reads during testing.
from unittest.mock import patch

# Import pytest for assertions and test execution.
import pytest

# Import the module we are testing.
from rag.ingestion import reindex_webshoppers_vision as migration


# Verify that the migration planner selects the expected figure records.
def test_migration_plan_selects_115_figures():

    # Execute the read-only migration planner against our validated local files.
    figures, fingerprint = migration.build_migration_plan()

    # Require exactly 115 selected figures.
    assert len(figures) == 115

    # Require every selected chunk to be a figure.
    assert all(chunk["content_type"] == "figure" for chunk in figures)

    # Require all selected chunks to have unique identifiers.
    assert len({chunk["chunk_id"] for chunk in figures}) == 115

    # Require the fingerprint to contain 64 hexadecimal characters.
    assert len(fingerprint) == 64

    # Verify that the fingerprint uses the expected SHA-256 format.
    assert all(character in "0123456789abcdef" for character in fingerprint)


# Verify that changing enriched content produces a different fingerprint.
def test_fingerprint_changes_when_figure_content_changes():

    # Generate the original migration fingerprint.
    _, original_fingerprint = migration.build_migration_plan()

    # Load the prepared cache into an independent in-memory object.
    prepared = json.loads(
        json.dumps(migration.load_json(migration.PREPARED_CACHE))
    )

    # Find the first figure in the prepared cache.
    figure = next(
        chunk
        for chunk in prepared["chunks"]
        if chunk["content_type"] == "figure"
    )

    # Modify its description in memory without changing the actual cache file.
    figure["content"] += " Test-only description change."

    # Keep the real JSON loader so the other files remain unchanged.
    original_loader = migration.load_json

    # Return the modified in-memory cache only when the prepared path is read.
    def modified_loader(path):

        # Substitute our test data for the prepared cache.
        if path == migration.PREPARED_CACHE:
            return prepared

        # Load every other file normally.
        return original_loader(path)

    # Temporarily replace the loader for this test only.
    with patch.object(migration, "load_json", side_effect=modified_loader):

        # Generate a fingerprint from the modified in-memory content.
        _, modified_fingerprint = migration.build_migration_plan()

    # Require the modified fingerprint to differ from the original.
    assert modified_fingerprint != original_fingerprint


# Verify that modifying a text chunk is rejected.
def test_rejects_nonfigure_content_change():

    # Load and validate the original cache.
    original = migration.validate_chunk_cache(
        migration.load_json(migration.ORIGINAL_CACHE), "Original"
    )

    # Load and validate the prepared cache.
    prepared = migration.validate_chunk_cache(
        migration.load_json(migration.PREPARED_CACHE), "Prepared"
    )

    # Copy the prepared chunks so the real cache stays untouched.
    modified = json.loads(json.dumps(prepared))

    # Find a text chunk that was originally unchanged.
    chunk_id = next(
        key for key, chunk in modified.items()
        if chunk["content_type"] == "text"
    )

    # Introduce an unauthorized content change.
    modified[chunk_id]["content"] += " Unauthorized test change."

    # Require the selector to reject the modified text chunk.
    with pytest.raises(ValueError, match="Nonfigure content changed"):
        migration.select_changed_figures(original, modified)


# Verify that changing a figure's metadata is rejected.
def test_rejects_figure_metadata_change():

    # Load the original cache and organize its chunks by ID.
    original = migration.validate_chunk_cache(
        migration.load_json(migration.ORIGINAL_CACHE), "Original"
    )

    # Load the prepared cache and organize its chunks by ID.
    prepared = migration.validate_chunk_cache(
        migration.load_json(migration.PREPARED_CACHE), "Prepared"
    )

    # Make an independent copy of the prepared chunks.
    modified = json.loads(json.dumps(prepared))

    # Identify one figure chunk.
    chunk_id = next(
        key for key, chunk in modified.items()
        if chunk["content_type"] == "figure"
    )

    # Change its page number to simulate corrupted metadata.
    modified[chunk_id]["page_number"] += 1

    # Require the selector to reject the metadata change.
    with pytest.raises(ValueError, match="Metadata changed"):
        migration.select_changed_figures(original, modified)


# Verify that a backup with corrupted original content is rejected.
def test_rejects_backup_content_mismatch():

    # Load and validate the original cache.
    original = migration.validate_chunk_cache(
        migration.load_json(migration.ORIGINAL_CACHE), "Original"
    )

    # Load an independent in-memory copy of the backup.
    backup = json.loads(
        json.dumps(migration.load_json(migration.BACKUP_PATH))
    )

    # Corrupt the content of the first backed-up document.
    backup["documents"][0]["content"] += " Corrupted backup content."

    # Require backup validation to detect the mismatch.
    with pytest.raises(ValueError, match="Backup content mismatch"):
        migration.validate_backup(backup, original)


# Verify that corrupted backup metadata prevents the migration.
def test_rejects_backup_metadata_mismatch():

    # Load and validate the original Webshoppers chunk cache.
    original = migration.validate_chunk_cache(
        migration.load_json(migration.ORIGINAL_CACHE),
        "Original",
    )

    # Create an independent in-memory copy of the Azure Search backup.
    backup = json.loads(
        json.dumps(migration.load_json(migration.BACKUP_PATH))
    )

    # Select the first backed-up search document.
    document = backup["documents"][0]

    # Replace its page number with an incorrect value.
    document["page_number"] = document["page_number"] + 1

    # Require metadata validation to reject the corrupted backup.
    with pytest.raises(ValueError, match="Backup metadata mismatch"):

        # Run the validation against the modified in-memory backup.
        migration.validate_backup_metadata(backup, original)


# Verify that unchanged Azure Search records pass preflight verification.
def test_live_verification_accepts_unchanged_records():

    # Import Mock to simulate an Azure Search client.
    from unittest.mock import Mock

    # Load the original backup from disk.
    backup = migration.load_json(migration.BACKUP_PATH)

    # Select one backed-up figure to keep this test small.
    figure = next(
        document
        for document in backup["documents"]
        if document["content_type"] == "figure"
    )

    # Create a simulated Azure Search client.
    client = Mock()

    # Make the simulated client return the original record.
    client.get_document.return_value = figure.copy()

    # Verify the record without raising an error.
    migration.reconcile_live_progress(client, [figure], backup, set())

    # Confirm that Azure was queried exactly once.
    client.get_document.assert_called_once()


# Verify that modified live content prevents the migration.
def test_live_verification_rejects_content_drift():

    # Import Mock to simulate Azure Search.
    from unittest.mock import Mock

    # Load the original backup.
    backup = migration.load_json(migration.BACKUP_PATH)

    # Select one original figure record.
    figure = next(
        document
        for document in backup["documents"]
        if document["content_type"] == "figure"
    )

    # Copy the record so the original backup remains unchanged.
    modified = figure.copy()

    # Simulate a description changed by another indexing process.
    modified["content"] += " Unexpected live modification."

    # Create a simulated Azure Search client.
    client = Mock()

    # Return the modified record when queried.
    client.get_document.return_value = modified

    # Require the verification to reject the unexpected change.
    with pytest.raises(ValueError, match="Unexpected live record state during recovery"):

        # Check the simulated live record against the backup.
        migration.reconcile_live_progress(client, [figure], backup, set())


# Verify that missing metadata in a live record is rejected.
def test_live_verification_rejects_missing_metadata():

    # Import Mock to simulate Azure Search.
    from unittest.mock import Mock

    # Load the original backup.
    backup = migration.load_json(migration.BACKUP_PATH)

    # Select one backed-up figure record.
    figure = next(
        document
        for document in backup["documents"]
        if document["content_type"] == "figure"
    )

    # Copy the record without modifying the backup.
    modified = figure.copy()

    # Remove a required field to simulate an incomplete live record.
    modified.pop("page_number")

    # Create a simulated Azure Search client.
    client = Mock()

    # Make the client return the incomplete record.
    client.get_document.return_value = modified

    # Require the verification to reject the missing field.
    with pytest.raises(ValueError, match="Unexpected live record state during recovery"):

        # Check the incomplete record against the backup.
        migration.reconcile_live_progress(client, [figure], backup, set())


# Verify that recovery recognizes an enriched figure missing from the checkpoint.
def test_recovery_recognizes_uploaded_figure():

    # Import Mock to simulate Azure AI Search without network requests.
    from unittest.mock import Mock

    # Load the original Azure Search backup.
    backup = migration.load_json(migration.BACKUP_PATH)

    # Build the validated migration plan.
    figures, fingerprint = migration.build_migration_plan()

    # Select one enriched figure for this test.
    enriched_figure = figures[0]

    # Create a simulated Azure Search client.
    client = Mock()

    # Simulate Azure already containing the enriched figure.
    client.get_document.return_value = enriched_figure.copy()

    # Start with an empty checkpoint, simulating interrupted progress.
    completed = set()

    # Reconcile the simulated live record against the backup.
    recovered = migration.reconcile_live_progress(
        client,
        [enriched_figure],
        backup,
        completed,
    )

    # Require the already-enriched figure to be recognized as completed.
    assert recovered == {enriched_figure["chunk_id"]}

    # Ensure reconciliation does not mutate the supplied checkpoint set.
    assert completed == set()

    # Confirm that Azure was queried once and no upload was attempted.
    client.get_document.assert_called_once()
    client.upload_documents.assert_not_called()


# Verify that apply mode uses the existing indexer safely.
def test_apply_migration_uses_selective_indexer(monkeypatch):

    # Import Mock for simulated Azure operations.
    from unittest.mock import Mock

    # Import the modules whose Azure dependencies will be replaced.
    import azure.identity
    import azure.search.documents

    # Import the existing multimodal indexing module.
    from rag.ingestion import multimodal_index_documents

    # Import the application's Azure configuration.
    from app.config import settings

    # Build the validated plan containing 115 enriched figures.
    figures, fingerprint = migration.build_migration_plan()

    # Load the original backup for simulated live records.
    backup = migration.load_json(migration.BACKUP_PATH)

    # Index original backup records by their unique IDs.
    originals = {
        document["chunk_id"]: document
        for document in backup["documents"]
    }

    # Create a simulated Azure Search client.
    client = Mock()

    # Simulate the expected number of indexed documents.
    client.search.return_value.get_count.return_value = 1588

    # Return the original record for each requested figure ID.
    client.get_document.side_effect = lambda key, selected_fields: originals[key]

    # Replace the Azure client constructor with our mock.
    monkeypatch.setattr(
        azure.search.documents,
        "SearchClient",
        Mock(return_value=client),
    )

    # Replace Azure authentication to avoid obtaining real credentials.
    monkeypatch.setattr(
        azure.identity,
        "DefaultAzureCredential",
        Mock(return_value=Mock()),
    )

    # Configure the expected index for this isolated test.
    monkeypatch.setattr(
        settings,
        "azure_multimodal_search_index",
        migration.EXPECTED_INDEX,
    )

    # Provide a dummy endpoint without connecting to Azure.
    monkeypatch.setattr(
        settings,
        "azure_search_endpoint",
        "https://example.search.windows.net",
    )

    # Simulate an empty checkpoint without reading saved progress.
    monkeypatch.setattr(
        "rag.ingestion.multimodal_checkpoint.load_checkpoint",
        Mock(return_value=set()),
    )

    # Replace the real indexer with a mock that reports 115 uploads.
    indexer = Mock(return_value=115)

    # Prevent actual embedding generation and document uploads.
    monkeypatch.setattr(
        multimodal_index_documents,
        "index_multimodal_chunks",
        indexer,
    )

    # Execute the apply workflow using only mocked dependencies.
    uploaded = migration.apply_migration(figures, fingerprint)

    # Confirm the simulated indexer returned its upload count.
    assert uploaded == 115

    # Require exactly one invocation of the indexing pipeline.
    indexer.assert_called_once()

    # Inspect the arguments passed to the indexer.
    args, kwargs = indexer.call_args

    # Require exactly the 115 selected figures.
    assert len(args[0]) == 115

    # Require the isolated checkpoint.
    assert kwargs["checkpoint_path"] == migration.CHECKPOINT_PATH

    # Require the validated content fingerprint.
    assert kwargs["fingerprint"] == fingerprint

    # Confirm that no actual upload was performed by the mocked client.
    client.upload_documents.assert_not_called()


# Verify that a completed checkpoint does not trigger another indexing run.
def test_completed_checkpoint_prevents_duplicate_uploads(monkeypatch):

    # Import Mock to simulate external dependencies.
    from unittest.mock import Mock

    # Import the checkpoint module used by the indexer.
    from rag.ingestion import multimodal_checkpoint

    # Import the existing multimodal indexing module.
    from rag.ingestion import multimodal_index_documents

    # Import the validated multimodal chunk model.
    from rag.models.multimodal_chunk import MultimodalChunk

    # Import the application's Azure configuration.
    from app.config import settings

    # Build the validated migration plan.
    figures, fingerprint = migration.build_migration_plan()

    # Convert the enriched figures into validated chunk models.
    chunks = [MultimodalChunk(**figure) for figure in figures]

    # Collect the IDs of all 115 completed figures.
    completed_ids = {chunk.chunk_id for chunk in chunks}

    # Simulate a checkpoint containing every selected figure.
    monkeypatch.setattr(
        multimodal_index_documents,
        "load_checkpoint",
        Mock(return_value=completed_ids),
    )

    # Replace Azure credentials with a mock.
    monkeypatch.setattr(
        multimodal_index_documents,
        "DefaultAzureCredential",
        Mock(return_value=Mock()),
    )

    # Replace the Azure Search client with a mock.
    client = Mock()

    # Prevent any real Azure Search connection.
    monkeypatch.setattr(
        multimodal_index_documents,
        "SearchClient",
        Mock(return_value=client),
    )

    # Prevent embedding generation and track unexpected calls.
    embedder = Mock()

    # Replace the real embedding function.
    monkeypatch.setattr(
        multimodal_index_documents,
        "embed_multimodal_chunk",
        embedder,
    )

    # Configure a simulated Azure Search endpoint.
    monkeypatch.setattr(
        settings,
        "azure_search_endpoint",
        "https://example.search.windows.net",
    )

    # Configure the expected multimodal index.
    monkeypatch.setattr(
        settings,
        "azure_multimodal_search_index",
        migration.EXPECTED_INDEX,
    )

    # Ensure the existing v1 index remains distinct.
    monkeypatch.setattr(
        settings,
        "azure_search_index",
        "enterprise-documents",
    )

    # Execute the existing indexer against the completed checkpoint.
    uploaded = multimodal_index_documents.index_multimodal_chunks(
        chunks,
        checkpoint_path=migration.CHECKPOINT_PATH,
        fingerprint=fingerprint,
        batch_size=1,
    )

    # Require zero new uploads.
    assert uploaded == 0

    # Require zero embedding requests.
    embedder.assert_not_called()

    # Require zero document upload requests.
    client.upload_documents.assert_not_called()
