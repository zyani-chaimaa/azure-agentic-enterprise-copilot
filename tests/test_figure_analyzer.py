# Import SimpleNamespace to create lightweight mock responses.
from types import SimpleNamespace

# Import pytest for testing exceptions and assertions.
import pytest

# Import the module we want to test.
from rag.ingestion import figure_analyzer


# Test successful figure analysis without calling Azure.
def test_analyze_figure_success(monkeypatch):

    # Collect arguments passed to the mocked model.
    captured = {}

    # Simulate a successful model response.
    def fake_create(**kwargs):

        # Save the request arguments for inspection.
        captured.update(kwargs)

        # Return a realistic response object.
        return SimpleNamespace(
            output_text="Free-shipping chart: TOP 10 is 18% in Q2 2017."
        )

    # Create a fake model client with a Responses API.
    fake_client = SimpleNamespace(
        responses=SimpleNamespace(create=fake_create)
    )

    # Replace the real client factory with our fake client.
    monkeypatch.setattr(
        figure_analyzer,
        "create_model_client",
        lambda: fake_client,
    )

    # Analyze a small sample of image bytes.
    result = figure_analyzer.analyze_figure_image(b"sample-image")

    # Verify that the returned description is preserved.
    assert "TOP 10 is 18%" in result

    # Verify that NEXORA uses its configured model deployment.
    assert captured["model"] == figure_analyzer.settings.azure_openai_deployment

    # Retrieve the model's image input.
    image_input = captured["input"][0]["content"][1]

    # Verify that the image is transmitted as an image input.
    assert image_input["type"] == "input_image"

    # Verify that the model receives the image at high detail.
    assert image_input["detail"] == "high"

    # Verify that the image is encoded as a PNG data URL.
    assert image_input["image_url"].startswith("data:image/png;base64,")


# Test that empty image data is rejected before making an API call.
def test_analyze_figure_rejects_empty_image():

    # Expect a clear validation error.
    with pytest.raises(ValueError, match="must not be empty"):

        # Attempt to analyze an empty image.
        figure_analyzer.analyze_figure_image(b"")


# Test that unsupported image formats are rejected.
def test_analyze_figure_rejects_unsupported_format():

    # Expect an unsupported MIME-type error.
    with pytest.raises(ValueError, match="Unsupported figure MIME type"):

        # Attempt to analyze an image with an unsupported format.
        figure_analyzer.analyze_figure_image(
            b"sample-image",
            mime_type="image/gif",
        )


# Test that empty model descriptions cannot enter the search index.
def test_analyze_figure_rejects_empty_response(monkeypatch):

    # Simulate a model response containing only whitespace.
    fake_client = SimpleNamespace(
        responses=SimpleNamespace(
            create=lambda **kwargs: SimpleNamespace(output_text="   ")
        )
    )

    # Replace the real model client with the fake client.
    monkeypatch.setattr(
        figure_analyzer,
        "create_model_client",
        lambda: fake_client,
    )

    # Expect the analyzer to reject the empty description.
    with pytest.raises(ValueError, match="empty figure description"):

        # Attempt to analyze a sample image.
        figure_analyzer.analyze_figure_image(b"sample-image")
