# Import SimpleNamespace to simulate Azure Document Intelligence objects.
from types import SimpleNamespace

# Import pytest's monkeypatch fixture through the test function arguments.
import pytest

# Import the figure-conversion function we are testing.
from rag.ingestion.layout_converter import convert_figures

# Import the existing image retrieval module for mocking.
from rag.ingestion import figure_extractor

# Import the existing Blob Storage module for mocking.
from rag.ingestion import blob_storage

# Import the new GPT-5.4-mini vision module for mocking.
from rag.ingestion import figure_analyzer


# Build a fake Document Intelligence result with one figure.
def make_document_result():

    # Create a figure referencing two source pages.
    figure = SimpleNamespace(
        id="1.1",
        caption=SimpleNamespace(content="Free-shipping trends"),
        bounding_regions=[
            SimpleNamespace(page_number=15),
            SimpleNamespace(page_number=16),
        ],
    )

    # Return a result containing this figure.
    return SimpleNamespace(figures=[figure])


# Test successful visual analysis and preservation of source metadata.
def test_figure_vision_success(monkeypatch):

    # Track how often the model analyzes the image.
    calls = []

    # Replace Azure image retrieval with local fake image bytes.
    monkeypatch.setattr(
        figure_extractor,
        "retrieve_figure_image",
        lambda **kwargs: b"fake-png",
    )

    # Replace Azure Blob Storage upload with a fake asset reference.
    monkeypatch.setattr(
        blob_storage,
        "upload_figure_image",
        lambda **kwargs: "https://example.com/figure.png",
    )

    # Define a fake visual-analysis function.
    def fake_analyze(image_bytes):

        # Record the supplied image bytes.
        calls.append(image_bytes)

        # Return a representative chart description.
        return "In Q2 2017, TOP 10 was 18% and Mercado Geral was 36%."

    # Replace the real GPT-5.4-mini call with the fake function.
    monkeypatch.setattr(
        figure_analyzer,
        "analyze_figure_image",
        fake_analyze,
    )

    # Convert the simulated figure into NEXORA evidence.
    elements = convert_figures(
        result=make_document_result(),
        operation_id="test-operation",
        document_id="test-document",
        filename="test.pdf",
        source_uri="https://example.com/test.pdf",
    )

    # Verify that both source pages are represented.
    assert len(elements) == 2

    # Verify that the visual description becomes searchable.
    assert all("Mercado Geral was 36%" in item.content for item in elements)

    # Verify that the original caption is preserved.
    assert all("Free-shipping trends" in item.content for item in elements)

    # Verify that the original image reference is preserved.
    assert all(item.asset_uri == "https://example.com/figure.png" for item in elements)

    # Verify that source page references remain accurate.
    assert [item.page_number for item in elements] == [15, 16]

    # Verify that visual analysis runs only once per figure.
    assert calls == [b"fake-png"]


# Test that a vision-model failure does not stop ingestion.
def test_figure_vision_failure_fallback(monkeypatch):

    # Replace Azure image retrieval with fake image bytes.
    monkeypatch.setattr(
        figure_extractor,
        "retrieve_figure_image",
        lambda **kwargs: b"fake-png",
    )

    # Replace Azure Blob Storage upload with a fake asset reference.
    monkeypatch.setattr(
        blob_storage,
        "upload_figure_image",
        lambda **kwargs: "https://example.com/figure.png",
    )

    # Define a fake model function that raises an error.
    def failing_analyze(image_bytes):

        # Simulate a temporary model service failure.
        raise RuntimeError("Vision service unavailable")

    # Replace the real model call with the failing function.
    monkeypatch.setattr(
        figure_analyzer,
        "analyze_figure_image",
        failing_analyze,
    )

    # Convert the figure despite the simulated model failure.
    elements = convert_figures(
        result=make_document_result(),
        operation_id="test-operation",
        document_id="test-document",
        filename="test.pdf",
        source_uri="https://example.com/test.pdf",
    )

    # Verify that ingestion still produces both figure elements.
    assert len(elements) == 2

    # Verify that the original caption is used as the fallback.
    assert all(item.content == "Free-shipping trends" for item in elements)

    # Verify that the original image reference is retained.
    assert all(item.asset_uri == "https://example.com/figure.png" for item in elements)
