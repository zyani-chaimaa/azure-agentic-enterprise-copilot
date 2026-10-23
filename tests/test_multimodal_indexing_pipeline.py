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


# Verify that the PDF pipeline forwards a fingerprint for resumable indexing.
def test_pipeline_passes_checkpoint_and_fingerprint(monkeypatch, tmp_path):

    # Import the pipeline module so its dependencies can be replaced.
    from rag.ingestion import multimodal_indexing_pipeline as pipeline

    # Create a temporary PDF file without contacting Azure.
    pdf_path = tmp_path / "report.pdf"

    # Write test bytes; the mocked extractor will not parse the file.
    pdf_path.write_bytes(b"Mock PDF contents")

    # Define a checkpoint path for the indexing operation.
    checkpoint_path = tmp_path / "report-checkpoint.json"

    # Capture the arguments passed to the indexing service.
    captured = {}

    # Replace PDF extraction with one simulated evidence element.
    monkeypatch.setattr(
        pipeline,
        "ingest_multimodal_pdf",
        lambda **kwargs: ["mock-element"],
    )

    # Replace chunking with one simulated searchable chunk.
    monkeypatch.setattr(
        pipeline,
        "chunk_multimodal_elements",
        lambda **kwargs: [{
            "chunk_id": "report-p1-paragraph-0-c0",
            "element_id": "report-p1-paragraph-0",
            "document_id": "report",
            "filename": "report.pdf",
            "source_uri": "documents/report.pdf",
            "page_number": 1,
            "chunk_index": 0,
            "content_type": "text",
            "content": "Sample report content.",
            "extraction_method": "mock-extractor",
        }],
    )

    # Define a fake indexing service that records its arguments.
    def fake_index(chunks, **kwargs):

        # Remember the chunks and recovery configuration.
        captured["chunks"] = chunks
        captured.update(kwargs)

        # Simulate one successful upload.
        return 1

    # Replace the real indexing service with our fake.
    monkeypatch.setattr(pipeline, "index_multimodal_chunks", fake_index)

    # Execute the PDF pipeline with checkpoint recovery enabled.
    uploaded = pipeline.index_multimodal_pdf(
        file_path=str(pdf_path),
        document_id="report",
        source_uri="documents/report.pdf",
        checkpoint_path=checkpoint_path,
    )

    # Verify that one chunk was reported as uploaded.
    assert uploaded == 1

    # Verify that the checkpoint location was forwarded.
    assert captured["checkpoint_path"] == checkpoint_path

    # Verify that a SHA-256 fingerprint was provided.
    assert isinstance(captured["fingerprint"], str)

    # SHA-256 hexadecimal fingerprints contain 64 characters.
    assert len(captured["fingerprint"]) == 64
