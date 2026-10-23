# Import Base64 to encode images for the model API.
import base64

# Import the standard logging system for operational diagnostics.
import logging

# Import NEXORA's existing authenticated model client.
from app.model_client import create_model_client

# Import the configured Azure OpenAI deployment.
from app.config import settings


# Create a logger for this module.
logger = logging.getLogger(__name__)


# Define reusable instructions for interpreting enterprise figures.
FIGURE_ANALYSIS_PROMPT = """
You are analyzing a figure extracted from an enterprise PDF.

Describe the visual content accurately for document search and question answering.

For charts:
- Identify the title, axes, units, legend, and data series.
- Extract readable numerical values with their correct labels.
- Preserve dates, categories, and relationships between series.
- Describe important trends and comparisons.

For diagrams:
- Identify components, labels, connections, and directional relationships.

For photographs and illustrations:
- Describe visible objects, actions, and relevant details.

General requirements:
- Do not invent values or labels that are not visible.
- Explicitly identify uncertain or unreadable information.
- Preserve the original language of important labels.
- Produce a detailed, self-contained description suitable for semantic search.
- Return plain text, not Markdown or JSON.
"""


# Analyze a figure using NEXORA's configured vision-capable model.
def analyze_figure_image(
    image_bytes: bytes,
    mime_type: str = "image/png",
) -> str:

    # Reject empty images before making an API request.
    if not image_bytes:
        raise ValueError("Figure image must not be empty.")

    # Restrict image formats to supported MIME types.
    if mime_type not in ("image/png", "image/jpeg", "image/webp"):
        raise ValueError(f"Unsupported figure MIME type: {mime_type}")

    # Encode the image into Base64 text.
    encoded_image = base64.b64encode(image_bytes).decode("ascii")

    # Construct the image data URL.
    image_url = f"data:{mime_type};base64,{encoded_image}"

    # Reuse the authenticated Azure model client.
    client = create_model_client()

    # Send the image to the configured vision model.
    response = client.responses.create(
        model=settings.azure_openai_deployment,
        input=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": FIGURE_ANALYSIS_PROMPT,
                    },
                    {
                        "type": "input_image",
                        "image_url": image_url,
                        "detail": "high",
                    },
                ],
            }
        ],
    )

    # Extract and normalize the model's description.
    description = (response.output_text or "").strip()

    # Reject empty responses rather than indexing meaningless content.
    if not description:
        raise ValueError("Vision model returned an empty figure description.")

    # Log successful analysis without logging the document image.
    logger.info("Figure analyzed successfully using %s", settings.azure_openai_deployment)

    # Return the searchable visual description.
    return description
