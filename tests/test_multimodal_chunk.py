# Import pytest to verify expected validation errors.
import pytest

# Import Pydantic's validation exception.
from pydantic import ValidationError

# Import the multimodal chunk model.
from rag.models.multimodal_chunk import MultimodalChunk


# Create a reusable valid chunk for testing.
def make_chunk(**overrides):

    # Define the required fields for a text chunk.
    data = {
        "chunk_id": "REPORT-001-p1-text-0",
        "element_id": "REPORT-001-p1-paragraph-0",
        "document_id": "REPORT-001",
        "filename": "annual_report.pdf",
        "source_uri": "documents/annual_report.pdf",
        "page_number": 1,
        "chunk_index": 0,
        "content_type": "text",
        "content": "Annual revenue increased by 12%.",
        "extraction_method": "document-intelligence-layout",
    }

    # Apply modifications requested by an individual test.
    data.update(overrides)

    # Construct and validate the chunk.
    return MultimodalChunk(**data)


# Verify that valid text chunks are accepted.
def test_valid_text_chunk():

    # Create a standard text chunk.
    chunk = make_chunk()

    # Verify its content type and source page.
    assert chunk.content_type == "text"
    assert chunk.page_number == 1


# Verify that valid table chunks are accepted.
def test_valid_table_chunk():

    # Create a structured table chunk.
    chunk = make_chunk(
        content_type="table",
        content="Row 1, Column 1: Revenue",
    )

    # Verify that the table content is preserved.
    assert chunk.content_type == "table"


# Verify that visual chunks retain their image references.
@pytest.mark.parametrize("content_type", ["figure", "chart"])
def test_valid_visual_chunk(content_type):

    # Create a visual chunk with its original image URI.
    chunk = make_chunk(
        content_type=content_type,
        asset_uri="https://example.com/figure.png",
    )

    # Verify that the image reference is preserved.
    assert chunk.asset_uri is not None


# Verify that figures and charts require an image reference.
@pytest.mark.parametrize("content_type", ["figure", "chart"])
def test_visual_chunk_requires_asset_uri(content_type):

    # Attempt to create visual evidence without an image.
    with pytest.raises(ValidationError, match="asset_uri"):
        make_chunk(content_type=content_type)


# Verify that page numbers must be positive.
def test_rejects_invalid_page_number():

    # Page zero is not a valid PDF page reference.
    with pytest.raises(ValidationError):
        make_chunk(page_number=0)


# Verify that chunk positions cannot be negative.
def test_rejects_negative_chunk_index():

    # Negative chunk positions are invalid.
    with pytest.raises(ValidationError):
        make_chunk(chunk_index=-1)


# Verify that unsupported content types are rejected.
def test_rejects_unsupported_content_type():

    # Audio is not currently supported by this pipeline.
    with pytest.raises(ValidationError):
        make_chunk(content_type="audio")


# Verify that searchable content cannot be empty.
def test_rejects_empty_content():

    # Every indexed chunk needs searchable content.
    with pytest.raises(ValidationError):
        make_chunk(content="")
