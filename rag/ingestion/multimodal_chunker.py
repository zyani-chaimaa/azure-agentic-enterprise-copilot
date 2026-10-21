# Import the regular-expression library for identifying text tokens.
import re

# Import the original extracted evidence model.
from rag.models.multimodal import MultimodalElement

# Import the validated searchable chunk model.
from rag.models.multimodal_chunk import MultimodalChunk


# Split text while preserving words and useful overlapping context.
def _split_text(text: str, chunk_size: int, overlap: int) -> list[str]:

    # Normalize whitespace so repeated spaces do not consume the chunk budget.
    normalized = " ".join(text.split())

    # Return no chunks for empty text.
    if not normalized:
        return []

    # Extract words, including words longer than the configured chunk size.
    words = re.findall(r"\S+", normalized)

    # Store the resulting text chunks.
    result: list[str] = []

    # Track the next word that has not yet been fully processed.
    position = 0

    # Continue until every word has been processed.
    while position < len(words):

        # Start a new chunk with no content.
        current: list[str] = []

        # Remember the first new word in this chunk.
        start_position = position

        # Add complete words while they fit.
        while position < len(words):

            # Read the next word.
            word = words[position]

            # Calculate the length after adding the word.
            candidate = " ".join(current + [word])

            # Accept the word when it fits.
            if len(candidate) <= chunk_size:
                current.append(word)
                position += 1
                continue

            # Stop when the current chunk already contains words.
            if current:
                break

            # Split a single oversized word into bounded fragments.
            fragments = [
                word[index:index + chunk_size]
                for index in range(0, len(word), chunk_size)
            ]

            # Store each fragment without losing characters.
            result.extend(fragments)

            # Advance beyond the oversized word.
            position += 1
            break

        # Skip normal chunk creation if an oversized word was handled.
        if not current:
            continue

        # Store the completed chunk.
        result.append(" ".join(current))

        # Stop if all words have been processed.
        if position >= len(words):
            break

        # Skip overlap when the caller requests none.
        if overlap == 0:
            continue

        # Start looking backward from the end of the current chunk.
        overlap_start = len(current)

        # Track the length of the overlapping words.
        overlap_length = 0

        # Select trailing words up to the requested overlap target.
        while overlap_start > 0:

            # Consider one more word from the previous chunk.
            candidate_word = current[overlap_start - 1]

            # Include the separating space when appropriate.
            additional_length = len(candidate_word) + (
                1 if overlap_length else 0
            )

            # Stop when the requested overlap budget would be exceeded.
            if overlap_length + additional_length > overlap:
                break

            # Include this word in the overlap.
            overlap_start -= 1
            overlap_length += additional_length

        # When feasible, preserve at least one complete word.
        if overlap_start == len(current) and len(current[-1]) <= overlap:
            overlap_start -= 1

        # Avoid repeating an entire chunk without introducing new words.
        if overlap_start == 0 and len(current) == 1:
            continue

        # Determine which previous words could be carried forward.
        carried = current[overlap_start:]

        # Include only words that leave room for the next new word.
        while carried and len(
            " ".join(carried + [words[position]])
        ) > chunk_size:
            carried.pop(0)

        # Insert retained context before the next unprocessed word.
        if carried:
            words[position:position] = carried

    # Return the complete collection of text chunks.
    return result


# Transform extracted multimodal evidence into searchable chunks.
def chunk_multimodal_elements(
    elements: list[MultimodalElement],
    chunk_size: int = 1000,
    overlap: int = 150,
) -> list[MultimodalChunk]:

    # Reject invalid chunk sizes, including booleans.
    if type(chunk_size) is not int or chunk_size <= 0:
        raise ValueError("chunk_size must be a positive integer.")

    # Require an integer overlap smaller than the chunk size.
    if type(overlap) is not int or not 0 <= overlap < chunk_size:
        raise ValueError("overlap must be between 0 and chunk_size.")

    # Store all validated searchable chunks.
    chunks: list[MultimodalChunk] = []

    # Process each extracted element independently.
    for element in elements:

        # Reject unsupported input objects.
        if not isinstance(element, MultimodalElement):
            raise TypeError("Expected a MultimodalElement.")

        # Revalidate the source evidence.
        element = MultimodalElement.model_validate(element.model_dump())

        # Normalize surrounding whitespace.
        content = element.content.strip()

        # Split paragraphs but preserve structured and visual evidence.
        contents = (
            _split_text(content, chunk_size, overlap)
            if element.content_type == "text"
            else [content]
        )

        # Create one validated chunk for each content segment.
        for chunk_index, chunk_content in enumerate(contents):

            # Preserve the complete source metadata.
            chunks.append(
                MultimodalChunk(
                    chunk_id=f"{element.element_id}-c{chunk_index}",
                    element_id=element.element_id,
                    document_id=element.document_id,
                    filename=element.filename,
                    source_uri=element.source_uri,
                    page_number=element.page_number,
                    chunk_index=chunk_index,
                    content_type=element.content_type,
                    content=chunk_content,
                    asset_uri=element.asset_uri,
                    section_heading=element.section_heading,
                    extraction_method=element.extraction_method,
                )
            )

    # Return all searchable chunks.
    return chunks
