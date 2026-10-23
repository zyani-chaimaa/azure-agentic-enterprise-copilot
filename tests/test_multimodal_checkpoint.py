# Import the checkpoint functions we are going to implement.
from rag.ingestion.multimodal_checkpoint import (
    load_checkpoint,
    save_checkpoint,
)


# Verify that completed chunk IDs survive a simulated restart.
def test_checkpoint_persists_completed_chunks(tmp_path):

    # Create a temporary checkpoint path managed by pytest.
    checkpoint_path = tmp_path / "report-checkpoint.json"

    # Identify the document being processed.
    document_id = "report"

    # Record two chunks that have already been indexed.
    completed_chunk_ids = ["report-p1-c0", "report-p1-c1"]

    # Save the document's indexing progress to disk.
    save_checkpoint(
        checkpoint_path,
        document_id,
        completed_chunk_ids,
    )

    # Reload the checkpoint, simulating a new application run.
    recovered = load_checkpoint(checkpoint_path, document_id)

    # Confirm that both completed chunks were recovered.
    assert recovered == set(completed_chunk_ids)


# Verify that a checkpoint cannot be reused for another document.
def test_rejects_checkpoint_for_different_document(tmp_path):

    # Create an isolated checkpoint file for this test.
    checkpoint_path = tmp_path / "checkpoint.json"

    # Save progress belonging to the original document.
    save_checkpoint(
        checkpoint_path,
        "report-2025",
        ["report-2025-p1-c0"],
    )

    # Import pytest to verify the expected exception.
    import pytest

    # Attempt to load the checkpoint for a different document.
    with pytest.raises(ValueError, match="document_id does not match"):

        # The checkpoint must reject the incorrect document identity.
        load_checkpoint(checkpoint_path, "report-2026")


# Verify that corrupted checkpoint data cannot be silently accepted.
def test_rejects_corrupted_checkpoint(tmp_path):

    # Import pytest to verify the expected error.
    import pytest

    # Create an isolated checkpoint file.
    checkpoint_path = tmp_path / "corrupted-checkpoint.json"

    # Write deliberately invalid JSON to simulate file corruption.
    checkpoint_path.write_text(
        "{invalid-json",
        encoding="utf-8",
    )

    # Confirm that loading corrupted data raises an error.
    with pytest.raises(ValueError, match="Invalid checkpoint"):

        # Attempt to recover indexing progress from the corrupted file.
        load_checkpoint(checkpoint_path, "report")


# Verify that valid JSON with an invalid structure is rejected.
def test_rejects_invalid_checkpoint_structure(tmp_path):

    # Import JSON serialization to construct a malformed checkpoint.
    import json

    # Import pytest to verify the expected error.
    import pytest

    # Create an isolated checkpoint path.
    checkpoint_path = tmp_path / "invalid-structure.json"

    # Create a checkpoint with an invalid completed_chunk_ids type.
    invalid_checkpoint = {
        "document_id": "report",
        "completed_chunk_ids": "report-p1-c0",
    }

    # Write syntactically valid JSON containing the invalid structure.
    checkpoint_path.write_text(
        json.dumps(invalid_checkpoint),
        encoding="utf-8",
    )

    # Require the loader to reject malformed checkpoint data.
    with pytest.raises(ValueError, match="Invalid checkpoint"):

        # Attempt to recover progress from the malformed checkpoint.
        load_checkpoint(checkpoint_path, "report")


# Verify that different PDF contents produce different fingerprints.
def test_document_fingerprint_changes_with_content(tmp_path):

    # Import the fingerprint function we will implement next.
    from rag.ingestion.multimodal_checkpoint import compute_document_fingerprint

    # Create a temporary PDF for the test.
    pdf_path = tmp_path / "report.pdf"

    # Write the first version of the document.
    pdf_path.write_bytes(b"First PDF version")

    # Calculate the first fingerprint using the PDF and chunk settings.
    first = compute_document_fingerprint(pdf_path, chunk_size=1000, overlap=150)

    # Replace the document contents while preserving its filename.
    pdf_path.write_bytes(b"Updated PDF version")

    # Calculate the fingerprint again using identical settings.
    second = compute_document_fingerprint(pdf_path, chunk_size=1000, overlap=150)

    # Different document contents must produce different fingerprints.
    assert first != second


# Verify that changing chunking settings changes the fingerprint.
def test_document_fingerprint_changes_with_chunking_settings(tmp_path):

    # Import the function responsible for calculating fingerprints.
    from rag.ingestion.multimodal_checkpoint import compute_document_fingerprint

    # Create a temporary PDF path for this test.
    pdf_path = tmp_path / "report.pdf"

    # Write identical document contents for all fingerprint calculations.
    pdf_path.write_bytes(b"Sample financial report")

    # Calculate the fingerprint using the original chunking configuration.
    original = compute_document_fingerprint(
        pdf_path, chunk_size=1000, overlap=150
    )

    # Calculate another fingerprint with a different chunk size.
    different_size = compute_document_fingerprint(
        pdf_path, chunk_size=500, overlap=150
    )

    # Calculate another fingerprint with a different overlap.
    different_overlap = compute_document_fingerprint(
        pdf_path, chunk_size=1000, overlap=100
    )

    # Changing chunk size must produce a different fingerprint.
    assert original != different_size

    # Changing overlap must also produce a different fingerprint.
    assert original != different_overlap


# Verify that checkpoints cannot be reused after document changes.
def test_rejects_checkpoint_with_different_fingerprint(tmp_path):

    # Import pytest to check the expected validation error.
    import pytest

    # Create an isolated checkpoint file.
    checkpoint_path = tmp_path / "report-checkpoint.json"

    # Represent the original document's SHA-256 fingerprint.
    original_fingerprint = "a" * 64

    # Represent the updated document's different fingerprint.
    updated_fingerprint = "b" * 64

    # Save progress associated with the original document version.
    save_checkpoint(
        checkpoint_path,
        "report",
        ["report-p1-c0"],
        fingerprint=original_fingerprint,
    )

    # Require the checkpoint loader to reject the updated document.
    with pytest.raises(ValueError, match="fingerprint"):

        # Attempt to resume using a different document fingerprint.
        load_checkpoint(
            checkpoint_path,
            "report",
            fingerprint=updated_fingerprint,
        )


# Verify that a checkpoint without a fingerprint cannot satisfy a fingerprinted recovery.
def test_rejects_missing_checkpoint_fingerprint(tmp_path):

    # Import pytest to verify the expected rejection.
    import pytest

    # Create a temporary checkpoint file.
    checkpoint_path = tmp_path / "legacy-checkpoint.json"

    # Save progress without a fingerprint, simulating an older checkpoint.
    save_checkpoint(
        checkpoint_path,
        "report",
        ["report-p1-c0"],
    )

    # Require a fingerprint when attempting to resume safely.
    with pytest.raises(ValueError, match="fingerprint"):

        # Reject the old checkpoint rather than trusting its completed chunks.
        load_checkpoint(
            checkpoint_path,
            "report",
            fingerprint="a" * 64,
        )


# Verify that processing-pipeline changes invalidate old fingerprints.
def test_document_fingerprint_changes_with_processing_version(tmp_path):

    # Import the document fingerprint function.
    from rag.ingestion.multimodal_checkpoint import compute_document_fingerprint

    # Create a temporary document.
    pdf_path = tmp_path / "report.pdf"

    # Write fixed content so only the processing version changes.
    pdf_path.write_bytes(b"Sample financial report")

    # Calculate the fingerprint using processing pipeline version 1.
    first = compute_document_fingerprint(
        pdf_path,
        chunk_size=1000,
        overlap=150,
        processing_version="v1",
    )

    # Calculate the fingerprint using processing pipeline version 2.
    second = compute_document_fingerprint(
        pdf_path,
        chunk_size=1000,
        overlap=150,
        processing_version="v2",
    )

    # Different processing versions must not share checkpoints.
    assert first != second
