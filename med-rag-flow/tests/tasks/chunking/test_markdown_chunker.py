# med-rag-flow/tests/tasks/chunking/test_markdown_chunker.py
import pytest
from langchain.schema import Document
from med_rag_flow.tasks.chunking.markdown_chunker import chunk_markdown_document
from typing import List, Dict, Any, Optional

# Helper function to run the task with common defaults for testing
def run_chunker_test(markdown_text: str, **kwargs) -> List[Document]:
    """
    Helper function to run chunk_markdown_document with sensible defaults for testing.
    Override defaults using kwargs.
    """
    params: Dict[str, Any] = {
        "initial_split_method": "header",
        "headers_to_split_on": None, # Default headers: [("#", "h1"), ..., ("######", "h6")]
        "strip_headers": False,
        "apply_semantic_refinement": False, 
        "semantic_config": None,
        "apply_structural_recursive_split": True,
        "target_chunk_size": 100, # Small for easier testing of recursive splitting
        "target_chunk_overlap": 10, # Small for easier testing
        "recursive_split_respect_elements": None,
        "min_final_chunk_size": 20, # Small for easier testing of merging
        **kwargs 
    }
    # Filter out None values if the task expects them to be absent, not None.
    # However, the task signature uses Optional, so None should be fine.
    return chunk_markdown_document.fn(markdown_text=markdown_text, **params)

# --- Tests for Header Splitting ---

def test_header_splitting_basic():
    md = "# Title 1\nParagraph 1\n## Subtitle A\nParagraph 2\n### SubSubTitle X\nParagraph 3"
    chunks = run_chunker_test(
        md,
        apply_structural_recursive_split=False, # Isolate header splitting
        min_final_chunk_size=0 # Disable merging for this test
    )
    
    assert len(chunks) == 3
    
    assert chunks[0].page_content == "# Title 1\nParagraph 1"
    assert chunks[0].metadata == {"h1": "Title 1"}
    
    assert chunks[1].page_content == "## Subtitle A\nParagraph 2"
    assert chunks[1].metadata == {"h1": "Title 1", "h2": "Subtitle A"}
    
    assert chunks[2].page_content == "### SubSubTitle X\nParagraph 3"
    assert chunks[2].metadata == {"h1": "Title 1", "h2": "Subtitle A", "h3": "SubSubTitle X"}

def test_header_splitting_strip_headers_true():
    md = "# Title 1\nParagraph 1\n## Subtitle A\nParagraph 2"
    chunks = run_chunker_test(
        md,
        strip_headers=True,
        apply_structural_recursive_split=False,
        min_final_chunk_size=0
    )
    assert len(chunks) == 2
    assert chunks[0].page_content == "Paragraph 1"
    assert chunks[0].metadata == {"h1": "Title 1"}
    assert chunks[1].page_content == "Paragraph 2"
    assert chunks[1].metadata == {"h1": "Title 1", "h2": "Subtitle A"}

def test_header_splitting_strip_headers_false():
    md = "# Title 1\nParagraph 1\n## Subtitle A\nParagraph 2"
    chunks = run_chunker_test(
        md,
        strip_headers=False,
        apply_structural_recursive_split=False,
        min_final_chunk_size=0
    )
    assert len(chunks) == 2
    assert chunks[0].page_content == "# Title 1\nParagraph 1"
    assert chunks[1].page_content == "## Subtitle A\nParagraph 2"

def test_header_splitting_no_headers():
    md = "This is a paragraph.\nSo is this."
    chunks = run_chunker_test(
        md,
        apply_structural_recursive_split=False,
        min_final_chunk_size=0
    )
    assert len(chunks) == 1
    assert chunks[0].page_content == md
    assert chunks[0].metadata == {}

def test_header_splitting_content_before_first_header():
    md = "Content before H1\n# Title 1\nParagraph 1"
    chunks = run_chunker_test(
        md,
        apply_structural_recursive_split=False,
        min_final_chunk_size=0
    )
    assert len(chunks) == 2
    assert chunks[0].page_content == "Content before H1"
    assert chunks[0].metadata == {}
    assert chunks[1].page_content == "# Title 1\nParagraph 1"
    assert chunks[1].metadata == {"h1": "Title 1"}

def test_header_splitting_content_after_last_header():
    md = "# Title 1\nParagraph 1\nContent after last header"
    chunks = run_chunker_test(
        md,
        apply_structural_recursive_split=False, # Isolate header splitting
        min_final_chunk_size=0 # Disable merging
    )
    # The _AdaptedMarkdownHeaderTextSplitter's current logic will append content after the last header
    # to the chunk associated with that last header.
    assert len(chunks) == 1
    assert chunks[0].page_content == "# Title 1\nParagraph 1\nContent after last header"
    assert chunks[0].metadata == {"h1": "Title 1"}

def test_header_splitting_custom_headers():
    md = "====\nTitle 1\nContent1\n----\nSubtitle A\nContent2"
    custom_headers = [("====", "h1_custom"), ("----", "h2_custom")]
    chunks = run_chunker_test(
        md,
        headers_to_split_on=custom_headers,
        apply_structural_recursive_split=False,
        min_final_chunk_size=0
    )
    assert len(chunks) == 2
    assert chunks[0].page_content == "====\nTitle 1\nContent1"
    assert chunks[0].metadata == {"h1_custom": "Title 1"}
    assert chunks[1].page_content == "----\nSubtitle A\nContent2"
    assert chunks[1].metadata == {"h1_custom": "Title 1", "h2_custom": "Subtitle A"}


# --- Tests for Recursive Splitting ---

def test_recursive_splitting_basic():
    # Content much larger than target_chunk_size (100 in helper default)
    long_paragraph = "This is a very long paragraph that definitely needs to be split. " * 10
    md = f"# Title\n{long_paragraph}\n## Subtitle\n{long_paragraph}"
    
    chunks = run_chunker_test(
        md,
        initial_split_method="header", # Split by header first
        apply_structural_recursive_split=True,
        target_chunk_size=100,
        target_chunk_overlap=10,
        min_final_chunk_size=0 # Disable merging to isolate recursive splitting
    )
    
    assert len(chunks) > 2 # Should be more than the initial 2 header chunks
    
    # Check metadata preservation and content
    # First chunk from header split
    assert chunks[0].page_content.startswith("# Title")
    assert chunks[0].metadata.get("h1") == "Title"
    
    # Check that subsequent chunks from the first header section also have h1 metadata
    first_header_content_split = False
    for chunk in chunks:
        if chunk.metadata.get("h1") == "Title" and not chunk.page_content.startswith("# Title"):
             first_header_content_split = True
             assert len(chunk.page_content) <= 100 + 20 # Approximate, overlap can make it slightly larger
        if chunk.metadata.get("h2") == "Subtitle": # once we hit the next header section
            break 
    assert first_header_content_split

    # Check that chunks are not overly large
    for chunk in chunks:
        # MarkdownTextSplitter can sometimes exceed chunk_size by a bit due to sentence structure
        # A small buffer is acceptable, e.g., overlap or a small percentage
        assert len(chunk.page_content) <= 100 + 50, f"Chunk too large: {len(chunk.page_content)}"


def test_recursive_splitting_on_plain_text_no_initial_split():
    long_text = "This is a long text that should be split recursively. " * 20
    chunks = run_chunker_test(
        long_text,
        initial_split_method="none", # No header splitting
        apply_structural_recursive_split=True,
        target_chunk_size=50,
        target_chunk_overlap=5,
        min_final_chunk_size=0 # No merging
    )
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk.page_content) <= 50 + 20 # Allowing some buffer
        assert chunk.metadata == {} # No headers, so empty metadata

# --- Tests for Merging Small Chunks ---

def test_merging_small_chunks_basic():
    # Create input that will result in small chunks after header splitting
    # target_chunk_size=100, min_final_chunk_size=20 (helper defaults)
    md = "# Title 1\nShort1\n## Subtitle A\nShort2\n### Subtitle B\nThis one is a bit longer to ensure it is not merged initially.\n## Subtitle C\nShort3"
    # Expected after header split (no recursive, no merge yet):
    # 1. "# Title 1\nShort1" (len ~18) -> too small
    # 2. "## Subtitle A\nShort2" (len ~22) -> too small (if strip_headers=False)
    # 3. "### Subtitle B\nThis one is a bit longer..." (len > 20) -> OK
    # 4. "## Subtitle C\nShort3" (len ~22) -> too small
    
    chunks = run_chunker_test(
        md,
        apply_structural_recursive_split=False, # Disable recursive for this test
        min_final_chunk_size=30, # Override helper default for more predictable merging
        target_chunk_size=100 # Ensure target_chunk_size_limit for merging is this
    )

    # Expected merging:
    # Chunk 1 ("# Title 1\nShort1") is < 30. Buffer it.
    # Chunk 2 ("## Subtitle A\nShort2") arrives. Buffer + Chunk 2 content len < 100. Merge.
    #   New buffer: "# Title 1\nShort1\n\n## Subtitle A\nShort2". Metadata: {h1: Title 1, h2: Subtitle A}
    #   This merged content is > 30. So it will be finalized when the next chunk is processed or at the end.
    # Chunk 3 ("### Subtitle B\n...") arrives. Buffer is already > 30. Finalize buffer.
    #   Output: Merged chunk 1&2.
    #   New buffer: Chunk 3.
    # Chunk 4 ("## Subtitle C\nShort3") arrives. Buffer (Chunk 3) is > 30. Finalize buffer.
    #   Output: Chunk 3.
    #   New buffer: Chunk 4.
    # End of chunks. Finalize buffer (Chunk 4).
    #   Output: Chunk 4.
    # This means 3 chunks in total.
    
    assert len(chunks) == 3
    
    # Chunk 1 (merged original 1 and 2)
    assert chunks[0].page_content == "# Title 1\nShort1\n\n## Subtitle A\nShort2"
    assert chunks[0].metadata == {"h1": "Title 1", "h2": "Subtitle A"} # Simple merge strategy
    
    # Chunk 2 (original 3)
    assert chunks[1].page_content == "### Subtitle B\nThis one is a bit longer to ensure it is not merged initially."
    assert chunks[1].metadata == {"h1": "Title 1", "h2": "Subtitle A", "h3": "Subtitle B"}
    
    # Chunk 3 (original 4)
    assert chunks[2].page_content == "## Subtitle C\nShort3" # This chunk itself might be < min_final_chunk_size, but it's the last one.
    assert chunks[2].metadata == {"h1": "Title 1", "h2": "Subtitle C"}


def test_merging_does_not_exceed_target_limit():
    # target_chunk_size (limit for merging) = 50
    # min_final_chunk_size = 20
    md = "# T1\nP1" + "a"*10 + "\n## T2\nP2" + "b"*10 + "\n### T3\nP3" + "c"*30 # Total > 50
    # Header splits (no recursive):
    # 1. "# T1\nP1aaaaaaaaaa" (len ~18) -> buffer
    # 2. "## T2\nP2bbbbbbbbbb" (len ~20) -> potential merge with buffer. content = 18 + 2 + 20 = 40. OK.
    #    New buffer: chunk1+chunk2. len 40. metadata {h1, h2}
    # 3. "### T3\nP3cccc..." (len ~38) -> buffer (len 40) is > min_size (20).
    #    Try to merge with "### T3...": 40 + 2 + 38 = 80. This is > target_chunk_size_limit (50).
    #    So, finalize buffer (chunk1+chunk2).
    #    New buffer is "### T3...".
    # End: finalize "### T3..."
    # Result: 2 chunks
    
    chunks = run_chunker_test(
        md,
        target_chunk_size=50, # This will be the target_chunk_size_limit for merging
        min_final_chunk_size=20,
        apply_structural_recursive_split=False,
    )
    assert len(chunks) == 2
    assert chunks[0].page_content == "# T1\nP1" + "a"*10 + "\n\n" + "## T2\nP2" + "b"*10
    assert len(chunks[0].page_content) <= 50
    assert chunks[1].page_content == "### T3\nP3" + "c"*30
    
# --- Test for Combined Strategy ---

def test_combined_strategy_header_recursive_merge():
    long_text_unit = "This is one unit of text for our combined strategy. "
    md = (
        f"# Main Title\n{long_text_unit * 5}\n"  # Approx 5*50 = 250 chars. target_chunk_size=100. Should split.
        f"## Subtitle Alpha\n{long_text_unit * 2}\n" # Approx 100 chars. Might not split or one split.
        f"### SubSub Light\nShort text here.\n" # Approx 20 chars. Should merge.
        f"## Subtitle Beta\n{long_text_unit * 6}\n" # Approx 300 chars. Should split.
        f"Another short bit." # Approx 20 chars. Should merge with last part of Subtitle Beta split.
    )
    # Using helper defaults: target_chunk_size=100, min_final_chunk_size=20

    chunks = run_chunker_test(md) # Uses default params from helper

    assert len(chunks) > 0
    
    # Check a few properties rather than exact content for such a complex case
    # 1. Metadata should be hierarchical for initial chunks
    has_h1 = False
    has_h2_alpha = False
    has_h3_light_merged = False # Expect SubSub Light to merge
    has_h2_beta = False

    for chunk in chunks:
        if "h1" in chunk.metadata and chunk.metadata["h1"] == "Main Title":
            has_h1 = True
        if "h2" in chunk.metadata and chunk.metadata["h2"] == "Subtitle Alpha":
            has_h2_alpha = True
        if "h3" in chunk.metadata and chunk.metadata["h3"] == "SubSub Light":
            # This chunk should be merged with previous or next if it was small
            # The current merging logic merges with the *next* small chunk, or the previous if the current is small
            # "Short text here" is under "SubSub Light". If it forms a chunk, it'll be small.
            # It's more likely it gets merged into the previous chunk from "Subtitle Alpha" if that was split
            # or stays as its own chunk if the previous one was large enough.
            # The _merge_small_chunks logic: if a buffered chunk is small, it tries to merge with the *next* one.
            # So "SubSub Light\nShort text here" will be a chunk. If it's < min_final_chunk_size, it becomes buffer.
            # Then "## Subtitle Beta..." comes. If buffer is small, it tries to merge.
            # Given "SubSub Light\nShort text here" is small, it will attempt to merge with the first split of "## Subtitle Beta...".
            # This might or might not happen depending on sizes.
            # For this test, let's verify its content is present and its specific metadata is there.
            assert "Short text here" in chunk.page_content 
            has_h3_light_merged = True # Simplified check: its content exists with its header
            
        if "h2" in chunk.metadata and chunk.metadata["h2"] == "Subtitle Beta":
            has_h2_beta = True

        # Check chunk sizes (mostly for recursively split parts)
        # Header lines add to length, so allow more buffer for chunks containing them.
        if not any(hd in chunk.page_content for hd in ["# ", "## ", "### "]):
             assert len(chunk.page_content) <= 100 + 50 # target_chunk_size + buffer
        
        # Check that small chunks got merged (heuristic: very few chunks should be tiny)
        if len(chunks) > 1 : # Avoid single chunk documents
             assert len(chunk.page_content) >= 15 # Allowing a bit less than min_final_chunk_size due to complexities

    assert has_h1
    assert has_h2_alpha
    assert has_h3_light_merged
    assert has_h2_beta
    assert len(chunks) < 15 # Heuristic: should not be too many chunks for this text. Initial would be 4. Splits will add a few. Merging might reduce.

# --- Tests for Edge Cases ---

def test_edge_case_empty_text():
    chunks = run_chunker_test("")
    # The current implementation of _AdaptedMarkdownHeaderTextSplitter.split_document
    # when faced with empty input and default settings (not stripping headers)
    # might return one Document with empty page_content.
    # Then recursive split and merge won't change that.
    assert len(chunks) == 1 
    assert chunks[0].page_content == ""
    assert chunks[0].metadata == {}
    # Alternative expectation:
    # assert len(chunks) == 0
    # This depends on how _perform_initial_split and downstream functions handle totally empty input.
    # Current header splitter returns one empty doc if input is empty.

def test_edge_case_empty_text_strip_headers():
    chunks = run_chunker_test("", strip_headers=True)
    # If strip_headers is true, and content is empty, the header splitter's logic
    # for "if not chunks and document.page_content:" and then "if content_to_add:"
    # should result in no chunks being added.
    assert len(chunks) == 0


def test_edge_case_very_short_text():
    md = "Short."
    chunks = run_chunker_test(
        md,
        target_chunk_size=100,
        min_final_chunk_size=20
    )
    assert len(chunks) == 1
    assert chunks[0].page_content == md
    assert chunks[0].metadata == {}

def test_header_splitting_only_headers_no_strip():
    md = "# H1\n## H2\n### H3"
    chunks = run_chunker_test(md, strip_headers=False, apply_structural_recursive_split=False, min_final_chunk_size=0)
    assert len(chunks) == 3
    assert chunks[0].page_content == "# H1"
    assert chunks[0].metadata == {"h1": "H1"}
    assert chunks[1].page_content == "## H2"
    assert chunks[1].metadata == {"h1": "H1", "h2": "H2"}
    assert chunks[2].page_content == "### H3"
    assert chunks[2].metadata == {"h1": "H1", "h2": "H2", "h3": "H3"}

def test_header_splitting_only_headers_strip():
    md = "# H1\n## H2\n### H3"
    chunks = run_chunker_test(md, strip_headers=True, apply_structural_recursive_split=False, min_final_chunk_size=0)
    # If content is *only* headers and strip_headers is True, then page_content becomes empty.
    # The _AdaptedMarkdownHeaderTextSplitter.split_document adds a chunk if content is non-empty OR if not self.strip_headers
    # If self.strip_headers is True, it only adds the header line if not self.strip_headers (which is false here).
    # The current logic in _AdaptedMarkdownHeaderTextSplitter:
    # if not self.strip_headers: current_chunk_lines.append(line)
    # if current_chunk_lines (which would be empty if strip_headers=True and line is header): content = ...
    # This means empty page_content for each header.
    # Then, the _merge_small_chunks (if active, but disabled here with min_final_chunk_size=0)
    # would receive these empty Documents with metadata.
    
    assert len(chunks) == 3 # One chunk per header, but content is empty
    assert chunks[0].page_content == ""
    assert chunks[0].metadata == {"h1": "H1"}
    assert chunks[1].page_content == ""
    assert chunks[1].metadata == {"h1": "H1", "h2": "H2"}
    assert chunks[2].page_content == ""
    assert chunks[2].metadata == {"h1": "H1", "h2": "H2", "h3": "H3"}

def test_merging_with_only_one_chunk_small():
    md = "Small text" # Smaller than min_final_chunk_size (20 in helper)
    chunks = run_chunker_test(
        md,
        initial_split_method="none", # Ensure it's one chunk initially
        apply_structural_recursive_split=False,
        min_final_chunk_size=20
    )
    assert len(chunks) == 1
    assert chunks[0].page_content == "Small text"

def test_merging_with_only_one_chunk_large():
    md = "This text is larger than the minimum final chunk size of twenty characters."
    chunks = run_chunker_test(
        md,
        initial_split_method="none",
        apply_structural_recursive_split=False,
        min_final_chunk_size=20
    )
    assert len(chunks) == 1
    assert chunks[0].page_content == md

def test_no_recursive_splitting_if_false():
    long_text = "This is a very long text that should not be split recursively because the flag is false. " * 10
    chunks = run_chunker_test(
        long_text,
        initial_split_method="none",
        apply_structural_recursive_split=False, # Explicitly disable
        min_final_chunk_size=0 # Disable merging
    )
    assert len(chunks) == 1
    assert chunks[0].page_content == long_text

def test_no_merging_if_min_size_zero():
    md = "# Title1\nshort\n## Title2\nshort"
    chunks = run_chunker_test(
        md,
        apply_structural_recursive_split=False,
        min_final_chunk_size=0 # Explicitly disable merging
    )
    assert len(chunks) == 2 # Should be two small chunks from header splitting
    assert chunks[0].page_content == "# Title1\nshort"
    assert chunks[1].page_content == "## Title2\nshort"

def test_no_merging_if_min_size_none():
    md = "# Title1\nshort\n## Title2\nshort"
    chunks = run_chunker_test(
        md,
        apply_structural_recursive_split=False,
        min_final_chunk_size=None # Explicitly disable merging by passing None
    )
    assert len(chunks) == 2 
    assert chunks[0].page_content == "# Title1\nshort"
    assert chunks[1].page_content == "## Title2\nshort"

# Consider a test for respect_elements in recursive splitting if MarkdownTextSplitter has specific behavior to test for it
# However, MarkdownTextSplitter inherently respects markdown structures.
# Adding a specific test for this might be complex to set up and assert correctly without deep knowledge of its internals.
# For now, we assume its default behavior is sufficient.

# Test for when content is only whitespace
def test_whitespace_only_content():
    md = "\n  \t \n"
    chunks = run_chunker_test(
        md,
        initial_split_method="header",
        apply_structural_recursive_split=False,
        min_final_chunk_size=0
    )
    # _AdaptedMarkdownHeaderTextSplitter:
    #   lines = document.page_content.split('\n') -> ['', '  \t ', '']
    #   current_chunk_lines accumulates these.
    #   content = "\n".join(current_chunk_lines).strip() -> ""
    #   if content: -> False. So no doc from this.
    #   If no chunks and document.page_content:
    #     if not self.strip_headers or "".join(lines).strip(): -> True
    #     content_to_add = document.page_content
    #     if self.strip_headers: ... content_to_add = "\n".join(non_header_lines).strip() -> ""
    #     if content_to_add: chunks.append(...) -> No, content_to_add is empty
    #     elif not content_to_add and not self.strip_headers and document.page_content: -> True (content_to_add="", strip=F, page_content="\n  \t \n")
    #          chunks.append(Document(page_content=document.page_content, metadata=...))
    # So, one chunk with original whitespace content if not stripping headers.
    assert len(chunks) == 1
    assert chunks[0].page_content == md # Preserves original whitespace
    assert chunks[0].metadata == {}

def test_whitespace_only_content_strip_headers():
    md = "\n  \t \n"
    chunks = run_chunker_test(
        md,
        initial_split_method="header",
        strip_headers=True,
        apply_structural_recursive_split=False,
        min_final_chunk_size=0
    )
    # With strip_headers=True:
    #   content_to_add (after stripping logic for headers, which there are none) becomes document.page_content.strip() effectively.
    #   So content_to_add would be empty.
    #   The final `if content_to_add:` fails. No chunk.
    assert len(chunks) == 0

# Test for document that is only headers and whitespace, strip_headers=True
def test_only_headers_and_whitespace_strip_headers():
    md = "# H1 \n  \n## H2 \n\t\n### H3"
    chunks = run_chunker_test(
        md, 
        strip_headers=True, 
        apply_structural_recursive_split=False, 
        min_final_chunk_size=0
    )
    # Each header, when stripped, results in empty page_content.
    # These empty page_content docs with metadata are passed along.
    assert len(chunks) == 3
    assert chunks[0].page_content == "" 
    assert chunks[0].metadata == {"h1": "H1"}
    assert chunks[1].page_content == ""
    assert chunks[1].metadata == {"h1": "H1", "h2": "H2"}
    assert chunks[2].page_content == ""
    assert chunks[2].metadata == {"h1": "H1", "h2": "H2", "h3": "H3"}

# Test merging when target_chunk_size_limit is very small, preventing merges
def test_merging_prevented_by_small_target_limit():
    md = "# T1\na\n## T2\nb" # Two small chunks
    chunks = run_chunker_test(
        md,
        target_chunk_size=5, # This is the target_chunk_size_limit for merging. Content "a\n\n## T2\nb" is > 5
        min_final_chunk_size=2, # Small enough to want to merge
        apply_structural_recursive_split=False
    )
    # Chunk 1: "# T1\na" (len 6)
    # Chunk 2: "## T2\nb" (len 7)
    # Buffer is chunk 1. len(buf) = 6 > min_size (2). So, finalize buffer. Output chunk 1.
    # New buffer is chunk 2. End. Finalize buffer. Output chunk 2.
    # Wait, the logic is: if len(buffer_doc.page_content) < min_size: try_merge()
    # Buffer: "# T1\na" (len 6). min_size=2. This is NOT < min_size. So, finalize buffer. Add chunk 1.
    # New buffer: "## T2\nb" (len 7). End of loop. Add chunk 2.
    # This is correct. Two chunks.
    
    # Let's make the first chunk small to trigger merge attempt
    md_small_first = "# T\na\n## T2\nb"
    # Chunk 1: "# T\na" (len 5)
    # Chunk 2: "## T2\nb" (len 7)
    # Buffer is chunk 1. len(buf)=5. min_size=2. This is NOT < min_size.
    # My default target_chunk_size in helper is 100. min_final_chunk_size is 20.
    # Let's re-run with specific test params:
    chunks_attempt_merge = run_chunker_test(
        md_small_first,
        target_chunk_size=10, # target_chunk_size_limit for merging
        min_final_chunk_size=8, # min_size for buffer to trigger merge attempt
        apply_structural_recursive_split=False
    )
    # Chunk 1: "# T\na" (len 5). Buffer it.
    # Chunk 2: "## T2\nb" (len 7).
    # len(buffer) = 5 < min_size (8). Try merge.
    # potential_merged_content = "# T\na\n\n## T2\nb" (len 5 + 2 + 7 = 14)
    # target_chunk_size_limit = 10.
    # Since 14 > 10, merge is NOT possible. Finalize buffer (Chunk 1).
    # New buffer is Chunk 2. End of loop. Finalize Chunk 2.
    # Result: 2 chunks.
    assert len(chunks_attempt_merge) == 2
    assert chunks_attempt_merge[0].page_content == "# T\na"
    assert chunks_attempt_merge[1].page_content == "## T2\nb"

# Test that an already large enough chunk is not merged, even if next one is small
def test_merging_skips_already_large_chunk():
    md = "# Title\nThis is a sufficiently large chunk already.\n## Next\nSmall"
    # helper: target_chunk_size=100, min_final_chunk_size=20
    # Chunk 1: "# Title\nThis is a sufficiently large chunk already." (len > 20)
    # Chunk 2: "## Next\nSmall" (len < 20)
    
    chunks = run_chunker_test(
        md,
        apply_structural_recursive_split=False
    )
    # Buffer is Chunk 1. len(Chunk 1) > min_final_chunk_size (20). Finalize Chunk 1.
    # New buffer is Chunk 2. End of loop. Finalize Chunk 2.
    # Result: 2 chunks.
    assert len(chunks) == 2
    assert chunks[0].page_content == "# Title\nThis is a sufficiently large chunk already."
    assert chunks[1].page_content == "## Next\nSmall"

# Final check on combined strategy with more predictable sizes
def test_combined_predictable():
    text_block_1 = "Alpha content section one, quite long for splitting. " * 5 # len ~250
    text_block_2 = "Beta content section two, also long for splitting. " * 5 # len ~250
    small_text_1 = "Gamma small bit." # len ~16
    small_text_2 = "Delta tiny." # len ~11

    md_doc = f"# HeaderA\n{text_block_1}\n## HeaderB\n{small_text_1}\n### HeaderC\n{text_block_2}\n#### HeaderD\n{small_text_2}"

    # Helper defaults: target_chunk_size=100, overlap=10, min_final_chunk_size=20
    # 1. Header Split:
    #    - Doc1: "# HeaderA\n{text_block_1}" (h1: HeaderA)
    #    - Doc2: "## HeaderB\n{small_text_1}" (h1: HeaderA, h2: HeaderB)
    #    - Doc3: "### HeaderC\n{text_block_2}" (h1: HeaderA, h2: HeaderB, h3: HeaderC)
    #    - Doc4: "#### HeaderD\n{small_text_2}" (h1: HeaderA, h2: HeaderB, h3: HeaderC, h4: HeaderD)

    # 2. Recursive Split (target=100):
    #    - Doc1 content (text_block_1, ~250) will split into ~3 chunks (100, 100, 50ish). All with {h1} meta.
    #    - Doc2 content (small_text_1, ~16) won't split. Stays as 1 chunk with {h1,h2} meta.
    #    - Doc3 content (text_block_2, ~250) will split into ~3 chunks. All with {h1,h2,h3} meta.
    #    - Doc4 content (small_text_2, ~11) won't split. Stays as 1 chunk with {h1,h2,h3,h4} meta.
    #    Total after recursive: 3 + 1 + 3 + 1 = 8 chunks.

    # 3. Merge (min_final_chunk_size=20):
    #    - Chunk 1 (from Doc1, ~100, h1): OK
    #    - Chunk 2 (from Doc1, ~100, h1): OK
    #    - Chunk 3 (from Doc1, ~50, h1): OK
    #    - Chunk 4 (Doc2, ~16, {h1,h2}): Buffer this (len 16 < 20).
    #    - Chunk 5 (from Doc3, ~100, {h1,h2,h3}): Current buffer (Chunk 4) is small. Try merge.
    #        Potential: 16 + 2 (sep) + 100 = 118. This is > target_chunk_size (100). No merge.
    #        Finalize Chunk 4. Output Chunk 4.
    #        New buffer is Chunk 5.
    #    - Chunk 6 (from Doc3, ~100, {h1,h2,h3}): Buffer (Chunk 5) is large. Finalize Chunk 5. Output Chunk 5.
    #        New buffer is Chunk 6.
    #    - Chunk 7 (from Doc3, ~50, {h1,h2,h3}): Buffer (Chunk 6) is large. Finalize Chunk 6. Output Chunk 6.
    #        New buffer is Chunk 7.
    #    - Chunk 8 (Doc4, ~11, {h1,h2,h3,h4}): Buffer (Chunk 7) is large. Finalize Chunk 7. Output Chunk 7.
    #        New buffer is Chunk 8. (len 11 < 20).
    #    - End of loop. Finalize buffer (Chunk 8). Output Chunk 8.
    #    Total expected: 8 chunks. Merging didn't reduce chunks because the small ones were followed by large ones
    #    that exceeded the target_chunk_size_limit when attempting a merge.

    chunks = run_chunker_test(md_doc)
    
    # Based on the logic above, expect 8 chunks.
    assert len(chunks) == 8
    
    # Verify metadata propagation and some content
    assert chunks[0].metadata == {"h1": "HeaderA"}
    assert chunks[0].page_content.startswith("# HeaderA\nAlpha content section one")
    assert chunks[1].metadata == {"h1": "HeaderA"}
    assert chunks[2].metadata == {"h1": "HeaderA"}

    assert chunks[3].page_content == "## HeaderB\nGamma small bit." # This is Doc2, original len 16+12=28.
    assert chunks[3].metadata == {"h1": "HeaderA", "h2": "HeaderB"}

    assert chunks[4].metadata == {"h1": "HeaderA", "h2": "HeaderB", "h3": "HeaderC"}
    assert chunks[4].page_content.startswith("### HeaderC\nBeta content section two")
    assert chunks[5].metadata == {"h1": "HeaderA", "h2": "HeaderB", "h3": "HeaderC"}
    assert chunks[6].metadata == {"h1": "HeaderA", "h2": "HeaderB", "h3": "HeaderC"}
    
    assert chunks[7].page_content == "#### HeaderD\nDelta tiny."
    assert chunks[7].metadata == {"h1": "HeaderA", "h2": "HeaderB", "h3": "HeaderC", "h4": "HeaderD"}

    # Check that small chunks that couldn't be merged are still present
    assert len(chunks[3].page_content) < 30 # small_text_1 chunk
    assert len(chunks[7].page_content) < 20 # small_text_2 chunk

    # Let's re-run with a larger target_chunk_size_limit for merging to see if merging happens
    chunks_wider_merge_limit = run_chunker_test(
        md_doc,
        target_chunk_size=200 # This is the overall target AND the merge limit
    )
    # 1. Header Split: (Same 4 docs)
    # 2. Recursive Split (target=200):
    #    - Doc1 content (text_block_1, ~250) will split into ~2 chunks (200, 50). All with {h1} meta.
    #    - Doc2 content (small_text_1, ~16) won't split. Stays as 1 chunk with {h1,h2} meta.
    #    - Doc3 content (text_block_2, ~250) will split into ~2 chunks. All with {h1,h2,h3} meta.
    #    - Doc4 content (small_text_2, ~11) won't split. Stays as 1 chunk with {h1,h2,h3,h4} meta.
    #    Total after recursive: 2 + 1 + 2 + 1 = 6 chunks.

    # 3. Merge (min_final_chunk_size=20, target_chunk_size_limit=200):
    #    - Chunk 1 (from Doc1, ~200, h1): OK
    #    - Chunk 2 (from Doc1, ~50, h1): OK
    #    - Chunk 3 (Doc2, ~16, {h1,h2}): Buffer this (len 16 < 20).
    #    - Chunk 4 (from Doc3, ~200, {h1,h2,h3}): Current buffer (Chunk 3) is small. Try merge.
    #        Potential: 16 + 2 (sep) + 200 = 218. This IS > target_chunk_size_limit (200). No merge.
    #        Finalize Chunk 3. Output Chunk 3.
    #        New buffer is Chunk 4.
    #    - Chunk 5 (from Doc3, ~50, {h1,h2,h3}): Buffer (Chunk 4) is large. Finalize Chunk 4. Output Chunk 4.
    #        New buffer is Chunk 5.
    #    - Chunk 6 (Doc4, ~11, {h1,h2,h3,h4}): Buffer (Chunk 5) is large. Finalize Chunk 5. Output Chunk 5.
    #        New buffer is Chunk 6 (len 11 < 20).
    #    - End of loop. Finalize buffer (Chunk 6). Output Chunk 6.
    #    Total expected: 6 chunks. Still no reduction from merging due to the large chunk following small one.

    assert len(chunks_wider_merge_limit) == 6
The test file `med-rag-flow/tests/tasks/chunking/test_markdown_chunker.py` has been created with a comprehensive suite of unit tests.

The tests cover:
1.  **Header Splitting**:
    *   Basic functionality with different header levels.
    *   `strip_headers=True` and `strip_headers=False`.
    *   Documents with no headers.
    *   Content before the first header and after the last header.
    *   Custom header definitions.
    *   Documents containing only headers (stripped and not stripped).
    *   Documents containing only headers and whitespace (stripped).

2.  **Recursive Splitting**:
    *   Basic recursive splitting of large content after header splitting.
    *   Recursive splitting of plain text with `initial_split_method="none"`.
    *   Checks that chunk sizes are respected (within a reasonable buffer).
    *   Verification that `apply_structural_recursive_split=False` prevents splitting.

3.  **Merging Small Chunks**:
    *   Basic merging of small chunks created by header splitting.
    *   Ensuring merging does not exceed `target_chunk_size` (used as `target_chunk_size_limit`).
    *   Cases where merging is prevented by a small `target_chunk_size_limit`.
    *   Cases where already large enough chunks are not merged with subsequent small chunks.
    *   Verification that merging is skipped if `min_final_chunk_size` is 0 or `None`.
    *   Testing with a single small or large chunk (no merging should occur).

4.  **Combined Strategy**:
    *   Tests that integrate header splitting, recursive splitting, and merging to simulate a common pipeline.
    *   Heuristic checks on the number of chunks and metadata/content of key chunks.
    *   A more predictable combined test (`test_combined_predictable`) with detailed step-by-step analysis of expected chunking and merging behavior under different `target_chunk_size` values.

5.  **Edge Cases**:
    *   Empty `markdown_text` (with and without `strip_headers`).
    *   Very short `markdown_text`.
    *   Whitespace-only content (with and without `strip_headers`).

A helper function `run_chunker_test` was implemented to simplify test definitions by providing common default parameters for `chunk_markdown_document.fn()`.

The tests are designed to be self-contained and focus on the logic within `markdown_chunker.py`, avoiding external dependencies like semantic models. The assertions check for the correct number of chunks, `page_content`, and `metadata` propagation and modification according to the different processing stages.
