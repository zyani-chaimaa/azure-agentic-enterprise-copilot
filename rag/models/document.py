# Import the Pydantic base class for validated data structures.
from pydantic import BaseModel, Field


# Describe an original document before splitting it into chunks.
class Document(BaseModel):

    # Unique identifier assigned to the document.
    document_id: str = Field(min_length=1)

    # Original filename, such as return_policy.pdf.
    filename: str = Field(min_length=1)

    # Storage reference for the original document.
    source_uri: str = Field(min_length=1)

    # Number of pages in the original PDF.
    page_count: int = Field(ge=1)


# Describe one searchable passage extracted from a document.
class DocumentChunk(BaseModel):

    # Unique identifier for this individual chunk.
    chunk_id: str = Field(min_length=1)

    # Identifier linking the chunk to its original document.
    document_id: str = Field(min_length=1)

    # Original filename for human-readable citations.
    filename: str = Field(min_length=1)

    # Original document location for evidence tracing.
    source_uri: str = Field(min_length=1)

    # PDF page number, starting at 1 for human readability.
    page_number: int = Field(ge=1)

    # Position of the chunk within its source page.
    chunk_index: int = Field(ge=0)

    # Actual extracted text used for retrieval and grounding.
    content: str = Field(min_length=1)
