# Import pytest for validating expected errors.
import pytest

# Import the application configuration.
from app.config import settings

# Import the multimodal index builder and creator.
from rag.retrieval.multimodal_search_index import (
    EMBEDDING_DIMENSIONS,
    build_multimodal_search_index,
    create_multimodal_search_index,
)


# Define the complete set of expected index fields.
EXPECTED_FIELDS = {
    "chunk_id",
    "element_id",
    "document_id",
    "filename",
    "source_uri",
    "page_number",
    "chunk_index",
    "content_type",
    "content",
    "asset_uri",
    "section_heading",
    "extraction_method",
    "content_vector",
}


# Verify that the schema uses the configured multimodal index name.
def test_multimodal_index_name():

    # Build the schema locally without contacting Azure.
    index = build_multimodal_search_index()

    # Check that the v2 index name is used.
    assert index.name == settings.azure_multimodal_search_index


# Verify that every required multimodal field exists.
def test_multimodal_index_fields():

    # Build the schema.
    index = build_multimodal_search_index()

    # Collect the names of its fields.
    field_names = {field.name for field in index.fields}

    # Compare against the expected schema.
    assert field_names == EXPECTED_FIELDS


# Verify that chunk_id is the unique document key.
def test_multimodal_index_key():

    # Build the schema.
    index = build_multimodal_search_index()

    # Find fields configured as keys.
    keys = [field for field in index.fields if field.key]

    # Require exactly one key field.
    assert len(keys) == 1

    # Verify the correct field is the key.
    assert keys[0].name == "chunk_id"


# Verify that the embedding vector has the expected dimensions.
def test_multimodal_vector_dimensions():

    # Build the schema.
    index = build_multimodal_search_index()

    # Find the vector field.
    vector = next(
        field for field in index.fields
        if field.name == "content_vector"
    )

    # Check compatibility with the existing embedding model.
    assert vector.vector_search_dimensions == EMBEDDING_DIMENSIONS
    assert EMBEDDING_DIMENSIONS == 1536

    # Verify the vector field is searchable.
    assert vector.searchable is True

    # Verify its vector search profile.
    assert vector.vector_search_profile_name == "multimodal-vector-profile"


# Verify that important metadata supports filtering.
@pytest.mark.parametrize(
    "field_name",
    [
        "document_id",
        "element_id",
        "page_number",
        "content_type",
        "extraction_method",
    ],
)
def test_multimodal_filterable_metadata(field_name):

    # Build the schema.
    index = build_multimodal_search_index()

    # Find the requested metadata field.
    field = next(
        field for field in index.fields
        if field.name == field_name
    )

    # Verify that Azure Search filtering is enabled.
    assert field.filterable is True


# Verify that content_type supports faceted navigation.
def test_content_type_is_facetable():

    # Build the schema.
    index = build_multimodal_search_index()

    # Find the content type field.
    field = next(
        field for field in index.fields
        if field.name == "content_type"
    )

    # Verify faceting is enabled.
    assert field.facetable is True


# Verify that textual evidence supports keyword search.
@pytest.mark.parametrize(
    "field_name",
    ["content", "filename", "section_heading"],
)
def test_multimodal_searchable_text(field_name):

    # Build the schema.
    index = build_multimodal_search_index()

    # Find the searchable text field.
    field = next(
        field for field in index.fields
        if field.name == field_name
    )

    # Verify keyword search is supported.
    assert field.searchable is True


# Verify that the vector profile references the configured algorithm.
def test_multimodal_vector_profile():

    # Build the schema.
    index = build_multimodal_search_index()

    # Inspect the configured vector search profile.
    profile = index.vector_search.profiles[0]

    # Verify the profile name.
    assert profile.name == "multimodal-vector-profile"

    # Verify its HNSW algorithm reference.
    assert profile.algorithm_configuration_name == "multimodal-hnsw"


# Verify that missing endpoint configuration prevents Azure calls.
def test_missing_endpoint_rejected(monkeypatch):

    # Temporarily remove the configured endpoint.
    monkeypatch.setattr(settings, "azure_search_endpoint", "")

    # Verify the function rejects the missing configuration.
    with pytest.raises(ValueError, match="AZURE_SEARCH_ENDPOINT"):
        create_multimodal_search_index()


# Verify that the multimodal index cannot reuse the existing v1 index name.
def test_multimodal_index_cannot_overwrite_v1(monkeypatch):

    # Temporarily configure the multimodal index with the v1 index name.
    monkeypatch.setattr(
        settings,
        "azure_multimodal_search_index",
        settings.azure_search_index,
    )

    # Ensure the schema builder rejects the conflicting configuration.
    with pytest.raises(ValueError, match="must differ"):
        build_multimodal_search_index()
