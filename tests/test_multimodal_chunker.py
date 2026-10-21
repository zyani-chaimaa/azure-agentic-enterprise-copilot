# Import pytest for parameterized tests and exception checks.
import pytest

# Import the source evidence model.
from rag.models.multimodal import MultimodalElement

# Import the new multimodal chunking function.
from rag.ingestion.multimodal_chunker import chunk_multimodal_elements


# Create reusable source evidence for testing.
def make_element(content_type="text", content="Example content", **overrides):

    # Define valid source metadata.
    data = {
        "element_id": "REPORT-001-p2-element-0",
        "document_id": "REPORT-001",
        "filename": "annual_report.pdf",
        "source_uri": "documents/annual_report.pdf",
        "page_number": 2,
        "content_type": content_type,
        "content": content,
        "section_heading": "Financial Results",
        "extraction_method": "document-intelligence-layout",
    }

    # Provide an image URI for visual evidence.
    if content_type in ("figure", "chart"):
        data["asset_uri"] = "https://example.com/figure.png"

    # Apply custom test values.
    data.update(overrides)

    # Return validated source evidence.
    return MultimodalElement(**data)


# Verify that short text remains in one chunk.
def test_short_text_remains_one_chunk():

    # Chunk a short paragraph.
    chunks = chunk_multimodal_elements([make_element()])

    # Verify that its content is preserved.
    assert len(chunks) == 1
    assert chunks[0].content == "Example content"
    assert chunks[0].chunk_index == 0


# Verify that long text is split into smaller chunks.
def test_long_text_is_split():

    # Create a paragraph containing multiple words.
    element = make_element(content="alpha beta gamma delta epsilon zeta")

    # Use a small chunk size to force splitting.
    chunks = chunk_multimodal_elements(
        [element],
        chunk_size=12,
        overlap=3,
    )

    # Verify that multiple chunks are generated.
    assert len(chunks) > 1

    # Verify that each chunk respects the character limit.
    assert all(len(chunk.content) <= 12 for chunk in chunks)

    # Verify that each chunk receives a unique identifier.
    assert len({chunk.chunk_id for chunk in chunks}) == len(chunks)


# Verify that overlap preserves context between adjacent chunks.
def test_text_overlap():

    # Create predictable text with clear word boundaries.
    element = make_element(content="alpha beta gamma delta epsilon")

    # Generate overlapping chunks.
    chunks = chunk_multimodal_elements(
        [element],
        chunk_size=16,
        overlap=8,
    )

    # Verify that adjacent chunks share at least one word.
    shared_words = set(chunks[0].content.split()) & set(
        chunks[1].content.split()
    )

    # Ensure the overlap is meaningful.
    assert shared_words


# Verify that document metadata survives chunking.
def test_preserves_source_metadata():

    # Chunk evidence from a known PDF page.
    chunks = chunk_multimodal_elements([make_element()])

    # Inspect the resulting chunk.
    chunk = chunks[0]

    # Verify that citation metadata is retained.
    assert chunk.document_id == "REPORT-001"
    assert chunk.page_number == 2
    assert chunk.filename == "annual_report.pdf"
    assert chunk.source_uri == "documents/annual_report.pdf"
    assert chunk.section_heading == "Financial Results"
    assert chunk.element_id == "REPORT-001-p2-element-0"


# Verify that tables remain complete logical elements.
def test_table_remains_one_chunk():

    # Create table evidence longer than the configured chunk size.
    element = make_element(
        content_type="table",
        content="Revenue table with multiple rows and columns.",
    )

    # Chunk with a deliberately small character limit.
    chunks = chunk_multimodal_elements(
        [element],
        chunk_size=10,
        overlap=2,
    )

    # Verify that the table remains intact.
    assert len(chunks) == 1
    assert chunks[0].content == element.content
    assert chunks[0].content_type == "table"


# Verify that visual evidence preserves its image URI.
@pytest.mark.parametrize("content_type", ["figure", "chart"])
def test_visual_evidence_preserves_asset_uri(content_type):

    # Create a figure or chart with an image reference.
    element = make_element(
        content_type=content_type,
        content="Revenue by quarter",
    )

    # Convert the visual evidence into a searchable chunk.
    chunks = chunk_multimodal_elements([element])

    # Verify that the original image remains linked.
    assert len(chunks) == 1
    assert chunks[0].asset_uri == element.asset_uri
    assert chunks[0].content_type == content_type


# Verify that an empty collection produces no chunks.
def test_empty_elements():

    # Process an empty evidence collection.
    chunks = chunk_multimodal_elements([])

    # Verify that no chunks are generated.
    assert chunks == []


# Verify that invalid chunking parameters are rejected.
@pytest.mark.parametrize(
    "chunk_size,overlap",
    [
        (0, 0),
        (-1, 0),
        (10, -1),
        (10, 10),
        (10, 11),
        (True, 0),
        (10, False),
    ],
)
def test_invalid_chunking_parameters(chunk_size, overlap):

    # Ensure invalid configurations raise an error.
    with pytest.raises(ValueError):
        chunk_multimodal_elements(
            [make_element()],
            chunk_size=chunk_size,
            overlap=overlap,
        )


# Verify that unsupported input objects are rejected.
def test_rejects_invalid_element_type():

    # Attempt to chunk a string instead of extracted evidence.
    with pytest.raises(TypeError):
        chunk_multimodal_elements(["invalid-element"])


# Verify that chunking does not lose words across chunk boundaries.
def test_chunking_preserves_all_original_words():

    # Generate 100 uniquely identifiable words.
    words = [f"word{i:03d}" for i in range(100)]

    # Combine the words into one long paragraph.
    original_text = " ".join(words)

    # Create validated source evidence containing the paragraph.
    element = make_element(content=original_text)

    # Split the paragraph into overlapping chunks.
    chunks = chunk_multimodal_elements(
        [element],
        chunk_size=50,
        overlap=15,
    )

    # Collect every word found in the resulting chunks.
    recovered_words = set()

    # Inspect each generated chunk.
    for chunk in chunks:

        # Add the chunk's words to the recovered collection.
        recovered_words.update(chunk.content.split())

    # Identify original words missing from all chunks.
    missing_words = set(words) - recovered_words

    # Ensure that no original words disappeared.
    assert missing_words == set()


# Verify that ordinary words are not unnecessarily split.
def test_preserves_word_boundaries_when_possible():

    # Use words that fit individually within the chunk size.
    element = make_element(
        content="alpha beta gamma delta epsilon zeta"
    )

    # Generate chunks with enough space for individual words.
    chunks = chunk_multimodal_elements(
        [element],
        chunk_size=12,
        overlap=3,
    )

    # Collect all generated words.
    recovered = [
        word
        for chunk in chunks
        for word in chunk.content.split()
    ]

    # Ensure every generated word exists in the original text.
    assert set(recovered).issubset(set(element.content.split()))

    # Ensure every original word is represented.
    assert set(element.content.split()).issubset(set(recovered))


# Verify that long unbroken text is not lost.
def test_long_unbroken_text_is_preserved():

    # Create a string without spaces.
    original = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"

    # Split the string into small chunks.
    chunks = chunk_multimodal_elements(
        [make_element(content=original)],
        chunk_size=10,
        overlap=3,
    )

    # Verify that the complete original string can be reconstructed.
    assert "".join(chunk.content for chunk in chunks) == original


# Verify overlap between adjacent chunks when feasible.
def test_adjacent_chunks_share_context():

    # Create a paragraph with enough words for overlapping chunks.
    element = make_element(
        content="alpha beta gamma delta epsilon zeta eta theta iota"
    )

    # Request a substantial overlap.
    chunks = chunk_multimodal_elements(
        [element],
        chunk_size=20,
        overlap=10,
    )

    # Ensure multiple chunks are generated.
    assert len(chunks) > 1

    # Inspect every adjacent pair of chunks.
    for previous, current in zip(chunks, chunks[1:]):

        # Find words appearing in both chunks.
        shared = set(previous.content.split()) & set(
            current.content.split()
        )

        # Require some shared context between adjacent chunks.
        assert shared, (
            f"No overlap between {previous.content!r} "
            f"and {current.content!r}"
        )


# Verify that repeated whitespace does not eliminate useful overlap.
def test_repeated_whitespace_preserves_overlap():

    # Reproduce the scenario where the current chunker loses overlap.
    element = make_element(
        content="alpha   beta   gamma   delta   epsilon"
    )

    # Request overlapping chunks with a small character limit.
    chunks = chunk_multimodal_elements(
        [element],
        chunk_size=12,
        overlap=4,
    )

    # Verify that every original word remains searchable.
    original_words = set(element.content.split())

    # Collect the words present across all generated chunks.
    recovered_words = {
        word
        for chunk in chunks
        for word in chunk.content.split()
    }

    # Ensure that chunking has not lost any words.
    assert original_words.issubset(recovered_words)

    # Check whether adjacent chunks share context.
    shared_context = [
        set(previous.content.split()) & set(current.content.split())
        for previous, current in zip(chunks, chunks[1:])
    ]

    # Require at least one adjacent pair to preserve whole-word overlap.
    assert any(shared_context), (
        "The chunker discarded all whole-word overlap "
        "when processing repeated whitespace."
    )
