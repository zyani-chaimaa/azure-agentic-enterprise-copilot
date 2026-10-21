# Import Literal to restrict content types to supported values.
from typing import Literal

# Import Pydantic to validate extracted document elements.
from pydantic import BaseModel, Field, model_validator


# Define the supported types of enterprise document content.
ContentType = Literal["text", "table", "figure", "chart"]


# Represent one traceable element extracted from a PDF.
class MultimodalElement(BaseModel):

    # Unique identifier for this extracted element.
    element_id: str = Field(min_length=1)

    # Identifier linking the element to its original document.
    document_id: str = Field(min_length=1)

    # Original PDF filename used in citations.
    filename: str = Field(min_length=1)

    # Location of the original document.
    source_uri: str = Field(min_length=1)

    # Original PDF page number, starting at one.
    page_number: int = Field(ge=1)

    # Type of content represented by this element.
    content_type: ContentType

    # Extracted text or searchable description of visual content.
    content: str = Field(min_length=1)

    # Optional reference to an extracted image or chart.
    asset_uri: str | None = None

    # Optional heading identifying the document section.
    section_heading: str | None = None

    # Name of the extraction method used for this element.
    extraction_method: str = Field(min_length=1)

    # Validate relationships between fields.
    @model_validator(mode="after")
    def validate_visual_asset(self):

        # Visual elements must reference their original visual evidence.
        if self.content_type in ("figure", "chart") and not self.asset_uri:
            raise ValueError("Figures and charts require an asset_uri.")

        # Return the validated model instance.
        return self
