# Import pytest for automated tests and exception assertions.
import pytest

# Import the orchestration module so its dependencies can be mocked.
from rag.ingestion import multimodal_indexing_pipeline as pipeline


# Create a temporary PDF and configure fake pipeline components.
def prepare_pipeline(tmp_path, monkeypatch):

    # Create a temporary file with a PDF extension.
    pdf = tmp_path / "report.pdf"

    # Write placeholder bytes; the mocked extractor never reads them.
    pdf.write_bytes(b"%PDF-1.4\n")

    # Record calls between pipeline components.
    captured = {}

    # Replace real Azure Document Intelligence extraction.
    def fake_ingest(file_path, document_id, source_uri):
        captured["ingest"] = (file_path, document_id, source_uri)
        return ["extracted-evidence"]

    # Replace real multimodal chunking.
    def fake_chunk(elements, chunk_size, overlap):
        captured["chunk"] = (elements, chunk_size, overlap)
        return ["searchable-chunk"]

    # Replace real embedding and Azure Search indexing.
    def fake_index(chunks):
        captured["index"] = chunks
        return len(chunks)

    # Install the mocked components.
    monkeypatch.setattr(pipeline, "ingest_multimodal_pdf", fake_ingest)
    monkeypatch.setattr(pipeline, "chunk_multimodal_elements", fake_chunk)
    monkeypatch.setattr(pipeline, "index_multimodal_chunks", fake_index)

    # Return the temporary PDF and captured calls.
    return pdf, captured


# Verify the complete orchestration and parameter forwarding.
def test_indexes_pdf_end_to_end(tmp_path, monkeypatch):

    # Prepare a temporary PDF and mocked services.
    pdf, captured = prepare_pipeline(tmp_path, monkeypatch)

    # Execute the pipeline without contacting Azure.
    uploaded = pipeline.index_multimodal_pdf(
        file_path=str(pdf),
        document_id="report-2025",
        source_uri="https://example.com/report.pdf",
        chunk_size=800,
        overlap=100,
    )

    # Verify the reported upload count.
    assert uploaded == 1

    # Verify that extraction received the correct document metadata.
    assert captured["ingest"] == (
        str(pdf),
        "report-2025",
        "https://example.com/report.pdf",
    )

    # Verify that chunking received the extracted evidence and settings.
    assert captured["chunk"] == (
        ["extracted-evidence"],
        800,
        100,
    )

    # Verify that the indexing service received the generated chunks.
    assert captured["index"] == ["searchable-chunk"]


# Verify rejection of missing or blank metadata.
@pytest.mark.parametrize(
    "field",
    ["file_path", "document_id", "source_uri"],
)
def test_rejects_blank_inputs(field):

    # Define valid input values.
    arguments = {
        "file_path": "report.pdf",
        "document_id": "report",
        "source_uri": "documents/report.pdf",
    }

    # Replace one required field with an empty string.
    arguments[field] = ""

    # Confirm validation rejects the empty field.
    with pytest.raises(ValueError):
        pipeline.index_multimodal_pdf(**arguments)


# Verify that a nonexistent PDF cannot be indexed.
def test_rejects_missing_pdf(tmp_path):

    # Construct a path that does not exist.
    missing = tmp_path / "missing.pdf"

    # Confirm the pipeline stops before extraction.
    with pytest.raises(FileNotFoundError):
        pipeline.index_multimodal_pdf(
            str(missing),
            "missing",
            "documents/missing.pdf",
        )


# Verify that unsupported file extensions are rejected.
def test_rejects_non_pdf(tmp_path):

    # Create an existing text file.
    document = tmp_path / "report.txt"
    document.write_text("Not a PDF.")

    # Confirm only PDF files are accepted.
    with pytest.raises(ValueError, match="Only PDF"):
        pipeline.index_multimodal_pdf(
            str(document),
            "report",
            "documents/report.txt",
        )


# Verify that extraction must produce evidence.
def test_rejects_empty_extraction(tmp_path, monkeypatch):

    # Prepare a PDF and mocked pipeline.
    pdf, _ = prepare_pipeline(tmp_path, monkeypatch)

    # Simulate a PDF with no extracted evidence.
    monkeypatch.setattr(
        pipeline,
        "ingest_multimodal_pdf",
        lambda **kwargs: [],
    )

    # Confirm indexing stops before chunking.
    with pytest.raises(ValueError, match="No multimodal evidence"):
        pipeline.index_multimodal_pdf(
            str(pdf),
            "report",
            "documents/report.pdf",
        )


# Verify that chunking must produce searchable chunks.
def test_rejects_empty_chunks(tmp_path, monkeypatch):

    # Prepare a PDF and mocked pipeline.
    pdf, _ = prepare_pipeline(tmp_path, monkeypatch)

    # Simulate chunking that returns no chunks.
    monkeypatch.setattr(
        pipeline,
        "chunk_multimodal_elements",
        lambda **kwargs: [],
    )

    # Confirm indexing stops without uploading.
    with pytest.raises(ValueError, match="No multimodal chunks"):
        pipeline.index_multimodal_pdf(
            str(pdf),
            "report",
            "documents/report.pdf",
        )


# Verify that indexing failures are not hidden.
def test_propagates_indexing_failure(tmp_path, monkeypatch):

    # Prepare a PDF and mocked pipeline.
    pdf, _ = prepare_pipeline(tmp_path, monkeypatch)

    # Simulate an Azure Search indexing failure.
    def failing_index(chunks):
        raise RuntimeError("Azure Search upload failed.")

    # Replace the indexing service with the failing mock.
    monkeypatch.setattr(
        pipeline,
        "index_multimodal_chunks",
        failing_index,
    )

    # Confirm the error propagates to the caller.
    with pytest.raises(RuntimeError, match="Azure Search upload failed"):
        pipeline.index_multimodal_pdf(
            str(pdf),
            "report",
            "documents/report.pdf",
        )
