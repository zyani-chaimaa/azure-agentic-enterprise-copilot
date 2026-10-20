# Import the model used to represent a searchable document chunk.
from rag.models.document import DocumentChunk


# Split extracted PDF pages into overlapping, word-aware text chunks.
def chunk_pages(
    pages: list[dict],
    document_id: str,
    filename: str,
    source_uri: str,
    chunk_size: int = 1000,
    overlap: int = 150,
) -> list[DocumentChunk]:

    # Ensure that every chunk can contain at least one character.
    if chunk_size <= 0:
        raise ValueError("chunk_size must be positive.")

    # Ensure overlap is valid and smaller than the chunk size.
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap must be between 0 and chunk_size.")

    # Store the chunks generated from all PDF pages.
    chunks: list[DocumentChunk] = []

    # Process each PDF page separately to preserve accurate citations.
    for page in pages:

        # Get the original PDF page number.
        page_number = page["page_number"]

        # Get the text extracted from this page.
        text = page["content"].strip()

        # Skip pages that contain no extractable text.
        if not text:
            continue

        # Start reading from the beginning of the page.
        start = 0

        # Number chunks independently within each page.
        chunk_index = 0

        # Continue until all text on this page has been processed.
        while start < len(text):

            # Set the maximum end position for the next chunk.
            end = min(start + chunk_size, len(text))

            # Check whether the chunk would end inside a word.
            if end < len(text) and not text[end].isspace():

                # Find the last whitespace character inside the window.
                boundary = next(
                    (
                        position
                        for position in range(end - 1, start, -1)
                        if text[position].isspace()
                    ),
                    None,
                )

                # Prefer a word boundary when it is reasonably close.
                if boundary is not None and boundary > start + chunk_size // 2:
                    end = boundary

            # Extract the chunk and remove surrounding whitespace.
            content = text[start:end].strip()

            # Store the chunk only when it contains meaningful text.
            if content:

                # Create a unique ID using the document, page, and chunk index.
                chunk_id = f"{document_id}-p{page_number}-c{chunk_index}"

                # Preserve the text and all metadata needed for citations.
                chunks.append(
                    DocumentChunk(
                        chunk_id=chunk_id,
                        document_id=document_id,
                        filename=filename,
                        source_uri=source_uri,
                        page_number=page_number,
                        chunk_index=chunk_index,
                        content=content,
                    )
                )

                # Increment the chunk index for this page.
                chunk_index += 1

            # Stop when we have reached the end of the page.
            if end >= len(text):
                break

            # Move backward to retain overlapping context.
            next_start = max(0, end - overlap)

            # Move forward to the first whitespace boundary at or after
            # the overlap position, avoiding a start inside a word.
            while next_start < end and not text[next_start].isspace():
                next_start += 1

            # Skip whitespace before the beginning of the next chunk.
            while next_start < len(text) and text[next_start].isspace():
                next_start += 1

            # Guarantee forward progress even in unusual text.
            if next_start <= start:
                next_start = end

            # Continue from the adjusted starting position.
            start = next_start

    # Return the complete collection of searchable document chunks.
    return chunks