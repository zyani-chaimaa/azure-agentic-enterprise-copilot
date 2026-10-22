# Import JSON to create realistic test cache files.
import json

# Import pytest for assertions and expected errors.
import pytest

# Import the figure-selection function under test.
from rag.ingestion.figure_enrichment import select_figure_chunks


# Build a representative cached multimodal chunk.
def make_chunk(chunk_id, document_id, page_number, content_type):

    # Return all fields required by the validated chunk model.
    return {
        "chunk_id": chunk_id,
        "element_id": f"{document_id}-element",
        "document_id": document_id,
        "filename": "example.pdf",
        "source_uri": "https://example.com/example.pdf",
        "page_number": page_number,
        "chunk_index": 0,
        "content_type": content_type,
        "content": "Figure 15.1" if content_type == "figure" else "Example text",
        "asset_uri": (
            "https://example.blob.core.windows.net/figures/example.png"
            if content_type == "figure"
            else None
        ),
        "section_heading": None,
        "extraction_method": "document-intelligence-layout",
    }


# Verify that only figures on the requested page are selected.
def test_selects_only_requested_page_figures(tmp_path):

    # Create a cache containing figures and unrelated text.
    records = [
        make_chunk("doc-p15-figure-1", "doc", 15, "figure"),
        make_chunk("doc-p15-text-1", "doc", 15, "text"),
        make_chunk("doc-p16-figure-2", "doc", 16, "figure"),
        make_chunk("doc-p15-figure-3", "doc", 15, "figure"),
    ]

    # Create an isolated temporary cache path.
    cache_path = tmp_path / "checkpoint.chunks.json"

    # Write a cache matching NEXORA's existing structure.
    cache_path.write_text(
        json.dumps({"document_id": "doc", "fingerprint": "test", "chunks": records}),
        encoding="utf-8",
    )

    # Select figures from page 15 only.
    selected = select_figure_chunks(cache_path, "doc", 15)

    # Verify that exactly two figures were selected.
    assert len(selected) == 2

    # Verify that original chunk IDs and ordering are preserved.
    assert [chunk.chunk_id for chunk in selected] == [
        "doc-p15-figure-1",
        "doc-p15-figure-3",
    ]

    # Verify that the original image reference remains available.
    assert selected[0].asset_uri == records[0]["asset_uri"]


# Verify that another document's cache cannot be selected accidentally.
def test_rejects_wrong_document(tmp_path):

    # Create an isolated cache path.
    cache_path = tmp_path / "checkpoint.chunks.json"

    # Write a cache belonging to another document.
    cache_path.write_text(
        json.dumps({"document_id": "other-doc", "chunks": []}),
        encoding="utf-8",
    )

    # Require an explicit document ID match.
    with pytest.raises(ValueError, match="document_id does not match"):
        select_figure_chunks(cache_path, "doc", 15)


# Verify that invalid page numbers are rejected.
@pytest.mark.parametrize("page_number", [0, -1, True, 1.5])
def test_rejects_invalid_page_numbers(tmp_path, page_number):

    # Reject invalid input before attempting to read the cache.
    with pytest.raises(ValueError, match="page_number"):
        select_figure_chunks(tmp_path / "missing.json", "doc", page_number)


# Verify that a missing cache produces a clear error.
def test_rejects_missing_cache(tmp_path):

    # Attempt to select figures from a nonexistent cache.
    with pytest.raises(FileNotFoundError, match="Chunk cache not found"):
        select_figure_chunks(tmp_path / "missing.json", "doc", 15)


# Verify that malformed cache structures are rejected.
def test_rejects_invalid_cache_structure(tmp_path):

    # Create an isolated cache path.
    cache_path = tmp_path / "checkpoint.chunks.json"

    # Write JSON that lacks the required chunks list.
    cache_path.write_text('{"document_id": "doc"}', encoding="utf-8")

    # Confirm that the cache structure is validated.
    with pytest.raises(ValueError, match="Invalid multimodal chunk cache"):
        select_figure_chunks(cache_path, "doc", 15)
