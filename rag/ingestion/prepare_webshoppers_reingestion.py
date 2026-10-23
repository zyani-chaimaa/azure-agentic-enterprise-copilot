# Import Path to manage input and output files.
from pathlib import Path

# Import JSON to save an extraction validation report.
import json

# Import NEXORA's existing PDF extraction orchestrator.
from rag.ingestion.multimodal_pipeline import ingest_multimodal_pdf

# Import NEXORA's existing multimodal chunker.
from rag.ingestion.multimodal_chunker import chunk_multimodal_elements

# Import the existing chunk-cache writer.
from rag.ingestion.multimodal_chunk_cache import save_chunk_cache


# Identify the original Webshoppers PDF.
PDF_PATH = Path("data/documents/multimodal/Webshoppers_38_pt.pdf")

# Identify the isolated workspace for the new extraction.
OUTPUT_DIR = Path("data/documents/multimodal/reingestion-webshoppers-v2")

# Preserve the existing document identity.
DOCUMENT_ID = "webshoppers-38-2018"

# Preserve the original PDF source reference.
SOURCE_URI = "https://iabbrasil.com.br/wp-content/uploads/2018/09/Webshoppers_38_pt.pdf"


# Prepare new multimodal chunks without modifying Azure AI Search.
def main() -> None:

    # Verify that the original PDF exists.
    if not PDF_PATH.is_file():
        raise FileNotFoundError(f"PDF not found: {PDF_PATH}")

    # Ensure the isolated output directory exists.
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Run Document Intelligence extraction and GPT-5.4-mini figure analysis.
    elements = ingest_multimodal_pdf(
        file_path=str(PDF_PATH),
        document_id=DOCUMENT_ID,
        source_uri=SOURCE_URI,
        strict_vision=True,
    )

    # Reject an extraction that produces no evidence.
    if not elements:
        raise RuntimeError("PDF extraction returned no evidence.")

    # Convert all extracted evidence into searchable chunks.
    chunks = chunk_multimodal_elements(
        elements=elements,
        chunk_size=1000,
        overlap=150,
    )

    # Reject an extraction that produces no chunks.
    if not chunks:
        raise RuntimeError("PDF extraction returned no chunks.")

    # Select figure elements for quality inspection.
    figures = [
        element for element in elements
        if element.content_type == "figure"
    ]

    # Reject an extraction that contains no figure evidence.
    if not figures:
        raise RuntimeError(
            "No figures were extracted; refusing to approve this preparation."
        )

    # Create a report summarizing the extraction.
    report = {
        "document_id": DOCUMENT_ID,
        "total_elements": len(elements),
        "total_chunks": len(chunks),
        "figure_elements": len(figures),
        "figure_pages": sorted({
            figure.page_number for figure in figures
        }),
        "figure_element_ids": [
            figure.element_id for figure in figures
        ],
    }

    # Save the new chunks in the isolated workspace.
    save_chunk_cache(
        cache_path=OUTPUT_DIR / "prepared.chunks.json",
        document_id=DOCUMENT_ID,
        fingerprint="webshoppers-vision-v2-preparation",
        chunks=chunks,
    )

    # Save the extraction report for review.
    (OUTPUT_DIR / "validation_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    # Display the extraction summary.
    print(json.dumps(report, indent=2, ensure_ascii=False))


# Execute extraction only when this file is run directly.
if __name__ == "__main__":
    main()
