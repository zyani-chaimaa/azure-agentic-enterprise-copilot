# Import pytest to check expected exceptions.
import pytest

# Import the chunking function we want to test.
from rag.ingestion.chunker import chunk_pages


# Verify that chunks preserve source metadata and size limits.
def test_chunk_metadata():

    # Create a sample page with enough text for multiple chunks.
    pages = [{"page_number": 3, "content": "Example sentence. " * 100}]

    # Split the sample page using our current chunking algorithm.
    chunks = chunk_pages(
        pages,
        document_id="TEST-001",
        filename="test_policy.pdf",
        source_uri="documents/test_policy.pdf",
        chunk_size=200,
        overlap=40,
    )

    # Verify that the chunker produced multiple passages.
    assert len(chunks) > 1

    # Verify that every passage retains the original page number.
    assert all(chunk.page_number == 3 for chunk in chunks)

    # Verify that no passage exceeds the configured size.
    assert all(len(chunk.content) <= 200 for chunk in chunks)

    # Verify that each passage has a unique identifier.
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)

    # Verify that the original document reference is preserved.
    assert all(chunk.document_id == "TEST-001" for chunk in chunks)


# Verify that invalid overlap settings are rejected.
def test_invalid_overlap():

    # A chunk cannot overlap itself completely.
    with pytest.raises(ValueError):

        # This must fail because overlap equals chunk_size.
        chunk_pages(
            pages=[{"page_number": 1, "content": "Sample text"}],
            document_id="TEST-001",
            filename="test.pdf",
            source_uri="documents/test.pdf",
            chunk_size=100,
            overlap=100,
        )