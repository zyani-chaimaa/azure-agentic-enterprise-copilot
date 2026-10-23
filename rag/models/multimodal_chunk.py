# Import Pydantic to validate multimodal search chunks.
from pydantic import BaseModel, Field, model_validator

# Reuse the supported content types from our evidence model.
from rag.models.multimodal import ContentType


# Represent one searchable chunk of multimodal document evidence.
class MultimodalChunk(BaseModel):

    # Unique identifier used when indexing this chunk.
    chunk_id: str = Field(min_length=1)

    # Identifier of the original extracted document element.
    element_id: str = Field(min_length=1)

    # Identifier of the original PDF document.
    document_id: str = Field(min_length=1)

    # Original PDF filename used in citations.
    filename: str = Field(min_length=1)

    # Location of the original PDF document.
    source_uri: str = Field(min_length=1)

    # Original PDF page number, starting at one.
    page_number: int = Field(ge=1)

    # Position of this chunk within its source element.
    chunk_index: int = Field(ge=0)

    # Distinguish text, tables, figures, and charts.
    content_type: ContentType

    # Searchable text that will later be embedded.
    content: str = Field(min_length=1)

    # Optional location of the original visual evidence.
    asset_uri: str | None = None

    # Optional document section heading for additional context.
    section_heading: str | None = None

    # Name of the method used to extract the original evidence.
    extraction_method: str = Field(min_length=1)

    # Validate relationships between chunk fields.
    @model_validator(mode="after")
    def validate_visual_asset(self):

        # Every visual chunk must reference its original image.
        if self.content_type in ("figure", "chart") and not self.asset_uri:
            raise ValueError("Figures and charts require an asset_uri.")

        # Return the validated chunk.
        return self
