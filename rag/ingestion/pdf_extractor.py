# Import Path to work with local PDF file paths.
from pathlib import Path

# Import PyMuPDF to read PDF documents.
import pymupdf


# Extract text from a PDF while preserving page numbers.
def extract_pdf_pages(file_path: str) -> list[dict]:

    # Convert the supplied filename into a Path object.
    path = Path(file_path)

    # Check that the file exists and is a regular file.
    if not path.is_file():
        raise FileNotFoundError(f"PDF file not found: {path}")

    # Reject files that do not have a PDF extension.
    if path.suffix.lower() != ".pdf":
        raise ValueError("Only PDF files are supported.")

    # Create a list to hold the extracted page records.
    pages = []

    # Open the PDF and close it automatically after processing.
    with pymupdf.open(path) as pdf:

        # Process each page in its original order.
        for page_index, page in enumerate(pdf):

            # Extract readable text, approximately preserving reading order.
            text = page.get_text("text", sort=True).strip()

            # Skip pages without extractable text.
            if not text:
                continue

            # Store the original page number and extracted text.
            pages.append(
                {
                    "page_number": page_index + 1,
                    "content": text,
                }
            )

    # Return all pages containing extractable text.
    return pages
