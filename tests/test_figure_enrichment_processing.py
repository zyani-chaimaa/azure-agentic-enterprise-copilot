# Import pytest to verify successful behavior and expected failures.
import pytest

# Import the validated multimodal chunk model.
from rag.models.multimodal_chunk import MultimodalChunk

# Import the module under test so external services can be mocked.
from rag.ingestion import figure_enrichment


# Create a representative figure chunk with original source metadata.
def make_figure_chunk():

    # Return a validated chunk matching NEXORA's existing schema.
    return MultimodalChunk(
        chunk_id="webshoppers-38-2018-p15-figure-40-c0",
        element_id="webshoppers-38-2018-p15-figure-40",
        document_id="webshoppers-38-2018",
        filename="Webshoppers_38_pt.pdf",
        source_uri="https://example.com/Webshoppers_38_pt.pdf",
        page_number=15,
        chunk_index=0,
        content_type="figure",
        content="Figure 15.1",
        asset_uri="https://example.blob.core.windows.net/figures/chart.png",
        section_heading=None,
        extraction_method="document-intelligence-layout",
    )


# Verify successful enrichment preserves all original metadata.
def test_enrich_figure_preserves_metadata(monkeypatch):

    # Create an existing figure chunk.
    original = make_figure_chunk()

    # Record inputs passed to mocked Azure services.
    calls = {}

    # Replace the real Blob Storage download with a fake image.
    def fake_download(asset_uri):

        # Record the image URL requested by the enrichment function.
        calls["asset_uri"] = asset_uri

        # Return representative image bytes without contacting Azure.
        return b"fake-chart-image"

    # Replace the real vision model with a deterministic description.
    def fake_analyze(image_bytes):

        # Record the image bytes passed to the vision analyzer.
        calls["image_bytes"] = image_bytes

        # Return a known description for verification.
        return "Free shipping increased from 30% to 40%."

    # Prevent real Azure Blob Storage requests.
    monkeypatch.setattr(
        figure_enrichment,
        "download_figure_image",
        fake_download,
    )

    # Prevent real Azure OpenAI requests.
    monkeypatch.setattr(
        figure_enrichment,
        "analyze_figure_image",
        fake_analyze,
    )

    # Produce an enriched copy of the original figure.
    enriched = figure_enrichment.enrich_figure_chunk(original)

    # Verify that the original chunk remains unchanged.
    assert original.content == "Figure 15.1"

    # Verify that the original caption remains in the enriched content.
    assert enriched.content.startswith("Figure 15.1")

    # Verify that the visual description is searchable text.
    assert "Free shipping increased from 30% to 40%." in enriched.content

    # Verify that all original metadata is preserved exactly.
    for field, value in original.model_dump().items():

        # The content field is the only permitted modification.
        if field != "content":
            assert getattr(enriched, field) == value

    # Verify that the original image URL was used.
    assert calls["asset_uri"] == original.asset_uri

    # Verify that the downloaded image reached the vision analyzer.
    assert calls["image_bytes"] == b"fake-chart-image"


# Verify that text chunks cannot be processed as figures.
def test_enrich_rejects_non_figure_chunks():

    # Create a valid figure chunk.
    original = make_figure_chunk()

    # Convert it into a valid text chunk for this test.
    text_chunk = MultimodalChunk.model_validate(
        original.model_copy(
            update={"content_type": "text", "asset_uri": None}
        ).model_dump()
    )

    # Confirm that the enrichment function rejects text.
    with pytest.raises(ValueError, match="Only figure chunks"):
        figure_enrichment.enrich_figure_chunk(text_chunk)


# Verify that invalid inputs are rejected.
def test_enrich_rejects_invalid_object():

    # Require a validated MultimodalChunk instance.
    with pytest.raises(TypeError, match="Expected a MultimodalChunk"):
        figure_enrichment.enrich_figure_chunk({"content": "Figure"})


# Verify that empty model responses cannot become indexed content.
@pytest.mark.parametrize("description", ["", "   "])
def test_enrich_rejects_empty_description(monkeypatch, description):

    # Create an existing figure chunk.
    original = make_figure_chunk()

    # Replace the image download with a deterministic fake.
    monkeypatch.setattr(
        figure_enrichment,
        "download_figure_image",
        lambda asset_uri: b"fake-chart-image",
    )

    # Replace the vision model with an empty or whitespace response.
    monkeypatch.setattr(
        figure_enrichment,
        "analyze_figure_image",
        lambda image_bytes: description,
    )

    # Confirm that empty descriptions are rejected.
    with pytest.raises(ValueError, match="empty description"):
        figure_enrichment.enrich_figure_chunk(original)
