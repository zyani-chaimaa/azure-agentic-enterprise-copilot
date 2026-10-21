# Import the centralized application configuration.
from app.config import settings


# Verify that multimodal RAG has a separate search index.
def test_multimodal_search_index():
    # The new index must not overwrite the existing RAG index.
    assert settings.azure_multimodal_search_index != settings.azure_search_index

    # The new index must have a configured name.
    assert settings.azure_multimodal_search_index


# Verify the Document Intelligence model configuration.
def test_document_intelligence_model():
    # The layout model extracts document structure and tables.
    assert settings.azure_document_intelligence_model == "prebuilt-layout"


# Verify that the Document Intelligence endpoint setting exists.
def test_document_intelligence_endpoint():
    # An empty endpoint is acceptable before Azure provisioning.
    assert isinstance(settings.azure_document_intelligence_endpoint, str)
