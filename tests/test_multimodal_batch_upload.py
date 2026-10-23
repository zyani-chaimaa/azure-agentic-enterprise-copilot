# Import lightweight objects to simulate Azure responses.
from types import SimpleNamespace

# Import Mock to simulate the Azure Search client.
from unittest.mock import Mock

# Import pytest for exception assertions.
import pytest

# Import the batch upload helper.
from rag.ingestion.multimodal_batch_upload import upload_multimodal_batch


# Build a simulated Azure Search indexing result.
def result(chunk_id, succeeded=True, status_code=200):
    return SimpleNamespace(
        key=chunk_id,
        succeeded=succeeded,
        status_code=status_code,
    )


# Build three sample documents with unique Azure Search keys.
def documents():
    return [
        {"chunk_id": f"report-p1-c{i}", "content": f"Text {i}"}
        for i in range(3)
    ]


# Verify results are matched by key rather than response position.
def test_accepts_reordered_successful_results():
    client = Mock()
    client.upload_documents.return_value = [
        result("report-p1-c2"),
        result("report-p1-c0"),
        result("report-p1-c1"),
    ]

    succeeded, failed = upload_multimodal_batch(client, documents())

    assert succeeded == {
        "report-p1-c0",
        "report-p1-c1",
        "report-p1-c2",
    }
    assert failed == {}
    client.upload_documents.assert_called_once_with(documents=documents())


# Verify individual failures do not erase successful results.
def test_preserves_partial_success():
    client = Mock()
    client.upload_documents.return_value = [
        result("report-p1-c2", succeeded=False, status_code=400),
        result("report-p1-c0"),
        result("report-p1-c1"),
    ]

    succeeded, failed = upload_multimodal_batch(client, documents())

    assert succeeded == {"report-p1-c0", "report-p1-c1"}
    assert failed == {"report-p1-c2": 400}


# Verify that missing result keys are rejected.
def test_rejects_missing_results():
    client = Mock()
    client.upload_documents.return_value = [
        result("report-p1-c0"),
        result("report-p1-c1"),
    ]

    with pytest.raises(RuntimeError, match="incomplete"):
        upload_multimodal_batch(client, documents())


# Verify duplicate response keys are rejected.
def test_rejects_duplicate_results():
    client = Mock()
    client.upload_documents.return_value = [
        result("report-p1-c0"),
        result("report-p1-c0"),
        result("report-p1-c2"),
    ]

    with pytest.raises(RuntimeError, match="duplicate"):
        upload_multimodal_batch(client, documents())


# Verify unknown response keys are rejected.
def test_rejects_unknown_results():
    client = Mock()
    client.upload_documents.return_value = [
        result("report-p1-c0"),
        result("report-p1-c1"),
        result("unknown-chunk"),
    ]

    with pytest.raises(RuntimeError, match="Invalid"):
        upload_multimodal_batch(client, documents())


# Verify empty batches are rejected before Azure is contacted.
def test_rejects_empty_batches():
    client = Mock()

    with pytest.raises(ValueError, match="empty batch"):
        upload_multimodal_batch(client, [])

    client.upload_documents.assert_not_called()
