# Import pytest to verify validation errors.
import pytest

# Import Pydantic's validation exception.
from pydantic import ValidationError

# Import the multimodal document model.
from rag.models.multimodal import MultimodalElement


# Create valid example data for a document element.
def sample_element(**overrides):

    # Define the required fields for a text element.
    data = {
        "element_id": "DOC-001-p3-e1",
        "document_id": "DOC-001",
        "filename": "annual_report.pdf",
        "source_uri": "documents/annual_report.pdf",
        "page_number": 3,
        "content_type": "text",
        "content": "Annual revenue increased.",
        "extraction_method": "document-intelligence-layout",
    }

    # Apply any field changes requested by the test.
    data.update(overrides)

    # Return the example data.
    return data


# Verify that all supported content types are accepted.
@pytest.mark.parametrize("content_type", ["text", "table", "figure", "chart"])
def test_supported_content_types(content_type):

    # Visual elements require a reference to their original image.
    asset_uri = "figures/example.png" if content_type in ("figure", "chart") else None

    # Construct the element with the selected content type.
    element = MultimodalElement(
        **sample_element(content_type=content_type, asset_uri=asset_uri)
    )

    # Confirm that the model preserves the content type and page.
    assert element.content_type == content_type
    assert element.page_number == 3


# Verify that a chart cannot lose its original visual evidence.
def test_chart_requires_asset_uri():

    # A chart without an image reference must fail validation.
    with pytest.raises(ValidationError):
        MultimodalElement(**sample_element(content_type="chart"))


# Verify that invalid page numbers are rejected.
def test_page_number_must_be_positive():

    # PDF page references must start at page one.
    with pytest.raises(ValidationError):
        MultimodalElement(**sample_element(page_number=0))


# Verify that unsupported content types are rejected.
def test_unsupported_content_type():

    # Only our four explicitly supported content types are valid.
    with pytest.raises(ValidationError):
        MultimodalElement(**sample_element(content_type="audio"))
