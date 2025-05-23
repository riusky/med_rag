# med-rag-flow/tasks/chunking/markdown_chunker.py
"""
Provides a comprehensive Prefect task for chunking Markdown text.

This module defines `chunk_markdown_document`, a Prefect task that splits
Markdown text into manageable `Document` objects using a configurable pipeline
of strategies. This includes initial structural splitting (e.g., by headers),
optional semantic refinement, recursive splitting of oversized chunks, and
merging of undersized chunks.
"""
from prefect import task, get_run_logger
from typing import List, Tuple, Optional, Dict, Any, Literal, TypedDict
from langchain.schema import Document
import re # For custom_delimiter_regex if used later
import copy # For deepcopying metadata

# --- Langchain specific imports ---
from langchain_experimental.text_splitter import SemanticChunker
from langchain.text_splitter import MarkdownTextSplitter # Added for recursive split
from langchain_ollama import OllamaEmbeddings


# --- Type Definitions ---
InitialSplitMethod = Literal["none", "header", "paragraph", "metadata_sections", "custom_delimiter"]
RespectableElement = Literal["list", "table", "code_block"]

class SemanticChunkerConfig(TypedDict, total=False):
    """
    Configuration for the SemanticChunker.

    Specifies parameters for initializing and using Langchain's `SemanticChunker`
    if semantic refinement is applied. `total=False` allows for optional keys.
    """
    ollama_model: Optional[str]
    """Name of the Ollama embedding model to use (e.g., "nomic-embed-text")."""
    ollama_base_url: Optional[str]
    """Base URL for the Ollama service (e.g., "http://localhost:11434")."""
    breakpoint_threshold_type: Optional[str]
    """Type of threshold for determining breakpoints (e.g., "percentile", "standard_deviation")."""
    breakpoint_threshold_amount: Optional[float]
    """Value for the breakpoint threshold."""
    buffer_size: Optional[int]
    """Number of sentences to buffer around breakpoints for semantic chunking."""
    min_chunk_size: Optional[int]
    """Minimum size for chunks produced by semantic splitting (note: `SemanticChunker.split_text`
    might not directly use this; behavior can vary)."""

class _AdaptedMarkdownHeaderTextSplitter:
    """
    A Markdown splitter that groups text under specific headers.

    This splitter is adapted from Langchain's `MarkdownHeaderTextSplitter`
    to operate on `Document` objects and integrate into the chunking pipeline.
    It splits a single `Document` into multiple `Document` objects based on
    Markdown header occurrences, propagating and augmenting metadata.
    It does not perform secondary splitting by size.
    """
    def __init__(self, 
                 headers_to_split_on: Optional[List[Tuple[str, str]]] = None, 
                 strip_headers: bool = False):
        """
        Initializes the _AdaptedMarkdownHeaderTextSplitter.

        Args:
            headers_to_split_on: A list of (header_prefix, header_name) tuples
                that define which headers to split on. Defaults to standard
                Markdown headers H1-H6 (e.g., [("#", "h1"), ("##", "h2")]).
                Sorted by prefix length descending to ensure correct matching.
            strip_headers: If True, header lines are removed from the content
                of the resulting chunks. Otherwise, they are included.
        """
        self.strip_headers = strip_headers
        if headers_to_split_on is None or not headers_to_split_on:
            self.headers_to_split_on = [
                ("#", "h1"), ("##", "h2"), ("###", "h3"),
                ("####", "h4"), ("#####", "h5"), ("######", "h6"),
            ]
        else:
            # Sort by length of header prefix in descending order
            self.headers_to_split_on = sorted(
                headers_to_split_on, key=lambda split: len(split[0]), reverse=True
            )

    def split_document(self, document: Document) -> List[Document]:
        """
        Splits a Markdown Document by headers.

        Parses the `document.page_content` and creates new `Document` objects
        for text sections under identified headers. Metadata from the input
        `document` is copied to each new chunk, and header information
        (e.g., {"h1": "Title Text", "h2": "Subtitle Text"}) is added based
        on the current header stack for that chunk.

        Args:
            document: The input `Document` to be split.

        Returns:
            A list of `Document` objects, each representing a chunk of text
            grouped under its respective headers. If no headers are found,
            a single Document containing the original content (or stripped
            content if strip_headers is True and headers existed) is returned.
        """
        # prefect.get_run_logger() might not be available or suitable here
        # if logging is needed inside, consider passing a logger or using standard print for debugging by worker
        
        lines = document.page_content.split('\n') # Or document.page_content.splitlines()
        
        chunks: List[Document] = []
        current_lines: List[str] = []
        # current_header_metadata for the content being collected in current_lines
        current_header_metadata: Dict[str, str] = {} 
        header_stack: List[Dict[str, Any]] = [] 

        # Determine the numeric level for each header type defined in headers_to_split_on
        # This helps in comparing header levels correctly.
        # We will use sep.count("#") for level if headers are like "#", "##", etc.
        # For more generic headers, a mapping or explicit level in headers_to_split_on would be needed.
        # The provided code uses sep.count("#"), so we adapt to that.

        for line_num, line in enumerate(lines): # line_num is not used in the provided logic, can be removed if not needed later
            stripped_line = line.lstrip() # lstrip() for header detection, original line for content
            found_header_info = None # Tuple: (level, name, data)

            for sep, name in self.headers_to_split_on:
                if stripped_line.startswith(sep) and \
                   (len(stripped_line) == len(sep) or stripped_line[len(sep)] == " "):
                    # Assuming standard markdown headers like "#", "##" for level calculation
                    # For more abstract headers, level would need to be part of `headers_to_split_on`
                    header_level = sep.count("#") 
                    if sep.count("#") == 0: # Handle cases where header is not # based e.g. ("Title:", "h1")
                        # find its index in headers_to_split_on as a proxy for level
                        # This makes it crucial that headers_to_split_on is ordered by hierarchy
                        for i, (s, _) in enumerate(self.headers_to_split_on):
                            if s == sep:
                                header_level = i + 1 # 1-based level
                                break
                    
                    header_data = stripped_line[len(sep):].lstrip() # Use lstrip for header_data too
                    found_header_info = (header_level, name, header_data)
                    break # Stop after finding the most specific header (due to sort order of headers_to_split_on)
            
            if found_header_info:
                # Finalize previous chunk if any content exists
                page_content_str = "\n".join(current_lines).strip()
                if page_content_str:
                    combined_metadata = document.metadata.copy() 
                    combined_metadata.update(current_header_metadata)
                    chunks.append(Document(page_content=page_content_str, metadata=combined_metadata))
                
                current_lines = [] # Reset for the new section

                # Update header stack and current_header_metadata for the new header
                header_level, name, data = found_header_info
                
                # Pop headers from the stack that are of the same or lower hierarchy (higher or equal numeric level value)
                while header_stack and header_stack[-1]["level"] >= header_level:
                    header_stack.pop()
                
                new_header_on_stack = {"level": header_level, "name": name, "data": data}
                header_stack.append(new_header_on_stack)
                current_header_metadata = {h["name"]: h["data"] for h in header_stack}

                if not self.strip_headers:
                    current_lines.append(line) # Add the original line
            else: # Not a header line
                current_lines.append(line) # Preserve internal empty lines by adding all non-header lines

        # Add any remaining content as the last chunk
        final_page_content_str = "\n".join(current_lines).strip()
        if final_page_content_str:
            final_combined_metadata = document.metadata.copy()
            final_combined_metadata.update(current_header_metadata) # Use the last state of current_header_metadata
            chunks.append(Document(page_content=final_page_content_str, metadata=final_combined_metadata))
        
        # Handle case: empty input document OR document with only headers that are stripped
        if not chunks and not document.page_content.strip():
             pass # Return empty list if input was empty or effectively empty after stripping
        elif not chunks and document.page_content.strip():
            # Input document had content, but no headers were found (or all content was stripped)
            # If strip_headers is True and doc was e.g. "# Header only", final_page_content_str would be empty.
            # If strip_headers is False, or if content exists that isn't a header,
            # then final_page_content_str would not be empty and handled above.
            # This specific case is if the document had content, no headers were found,
            # so all content is in current_lines, and the above block for final_page_content_str
            # should have created a chunk. This implies this condition might indicate an issue
            # or an edge case like a document with only whitespace lines after potential stripping.
            # However, the .strip() on page_content_str should handle this.
            # If the document consists only of headers and strip_headers=True, then chunks will be empty.
            # This is the correct behavior.

            # If the document has content but no headers from `headers_to_split_on` were found,
            # the entire document content should become a single chunk.
            # The logic after the loop already handles this by processing `current_lines`.
            # This `elif` might be redundant if the post-loop block is robust.
            # It's only an issue if `final_page_content_str` was empty but `document.page_content.strip()` wasn't.
            # This could happen if `strip_headers` is true, and the document *only* contained headers.
            # In that case, `current_lines` would contain nothing at the end, `final_page_content_str` would be empty,
            # and `chunks` would be empty, which is correct.
            pass


        return chunks


def _perform_initial_split(
    initial_doc: Document, 
    method: InitialSplitMethod, 
    headers_to_split_on: Optional[List[Tuple[str, str]]] = None, 
    strip_headers: bool = False, 
    custom_delimiter_regex: Optional[str] = None, # Not used in this step
    metadata_section_key: Optional[str] = None   # Not used in this step
) -> List[Document]:
    """
    Performs the initial structural split on the input document.

    Based on the chosen `method`, this function applies a first-pass splitting
    strategy to the `initial_doc`. For example, if `method` is "header",
    it uses `_AdaptedMarkdownHeaderTextSplitter`. Other methods like
    "paragraph" or "custom_delimiter" would be handled here (though currently
    only "header" is fully implemented, others raise NotImplementedError).

    Args:
        initial_doc: The single `Document` object to be split.
        method: The primary strategy for the initial split (e.g., "header", "none").
        headers_to_split_on: Configuration for header splitting if `method` is "header".
        strip_headers: Configuration for header splitting if `method` is "header".
        custom_delimiter_regex: Regex for "custom_delimiter" method (not implemented).
        metadata_section_key: Key for YAML frontmatter section splitting (not implemented).

    Returns:
        A list of `Document` objects resulting from the initial split. If the method
        is "none" or not recognized, returns the `initial_doc` as a single-element list.
    """
    logger = get_run_logger()
    if method == "header":
        logger.info("Performing initial split by headers.")
        splitter = _AdaptedMarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
            strip_headers=strip_headers
        )
        chunks = splitter.split_document(initial_doc)
        logger.info(f"Header split resulted in {len(chunks)} chunks.")
        return chunks
    elif method == "paragraph":
        raise NotImplementedError("_perform_initial_split for 'paragraph' not yet implemented.")
    # Add other methods later
    else:
        logger.warning(f"Initial split method '{method}' not recognized or supported. Returning original document.")
        return [initial_doc]


@task(name="chunk_markdown_document")
def chunk_markdown_document(
    markdown_text: str,
    initial_split_method: InitialSplitMethod = "header",
    headers_to_split_on: Optional[List[Tuple[str, str]]] = None,
    strip_headers: bool = False,
    # Parameters from later subtasks that should be documented
    custom_delimiter_regex: Optional[str] = None,
    metadata_section_key: Optional[str] = None,
    apply_semantic_refinement: bool = False,
    semantic_config: Optional[SemanticChunkerConfig] = None,
    apply_structural_recursive_split: bool = True,
    target_chunk_size: int = 1000,
    target_chunk_overlap: int = 200,
    recursive_split_respect_elements: Optional[List[RespectableElement]] = None,
    min_final_chunk_size: Optional[int] = 100
) -> List[Document]:
    """
    Chunks Markdown text into a list of Document objects using a configurable pipeline.

    This Prefect task takes raw Markdown text and processes it through several
    optional stages:
    1.  Initial Structural Split: Divides the text based on a chosen method like
        Markdown headers (`initial_split_method="header"`), paragraphs, or custom
        delimiters. If "none", the entire document is treated as one initial chunk.
    2.  Semantic Refinement (Optional): If `apply_semantic_refinement` is True,
        the chunks from the previous stage are further split using a semantic
        chunker (Langchain's `SemanticChunker` with Ollama embeddings). This
        aims to break text at points of semantic shift.
    3.  Structural Recursive Splitting (Optional): If `apply_structural_recursive_split`
        is True, any chunks exceeding `target_chunk_size` are recursively split
        using a Markdown-aware text splitter (`MarkdownTextSplitter`). This helps
        ensure that chunks do not exceed a specified character length while trying
        to respect Markdown structures.
    4.  Merging Small Chunks (Optional): If `min_final_chunk_size` is set, chunks
        smaller than this threshold are merged with adjacent chunks, provided the
        merged chunk does not exceed `target_chunk_size`.

    Args:
        markdown_text: The raw Markdown string to be chunked.
        initial_split_method: The primary strategy for the initial division of the
            text. Common options: "header" (split by Markdown headers),
            "paragraph" (split by paragraphs, not yet implemented),
            "custom_delimiter" (split by a regex, not yet implemented),
            "metadata_sections" (split by sections in YAML frontmatter, not yet implemented),
            "none" (treat the whole document as a single chunk before later steps).
            Defaults to "header".
        headers_to_split_on: A list of (header_prefix, header_name) tuples, e.g.,
            [("#", "h1"), ("##", "h2")], used when `initial_split_method="header"`.
            If None, defaults to H1-H6.
        strip_headers: If True and `initial_split_method="header"`, the header
            lines themselves are removed from the content of the chunks.
            Defaults to False.
        custom_delimiter_regex: Regular expression string for splitting if
            `initial_split_method="custom_delimiter"`. Not fully implemented.
            Defaults to None.
        metadata_section_key: Key in YAML frontmatter to guide splitting if
            `initial_split_method="metadata_sections"`. Not fully implemented.
            Defaults to None.
        apply_semantic_refinement: If True, applies semantic chunking after the
            initial split. Requires `semantic_config` to be provided and a
            running Ollama instance. Defaults to False.
        semantic_config: Configuration for the semantic chunker, as a
            `SemanticChunkerConfig` dictionary. See `SemanticChunkerConfig`
            docstring for details on its fields. Used if `apply_semantic_refinement` is True.
            Defaults to None.
        apply_structural_recursive_split: If True, splits chunks that are larger
            than `target_chunk_size` using a Markdown-aware recursive splitter.
            Defaults to True.
        target_chunk_size: The target maximum size (in characters) for chunks.
            Used by the recursive splitter and as a limit when merging small chunks.
            Defaults to 1000.
        target_chunk_overlap: The character overlap between chunks created by the
            recursive splitter. Defaults to 200.
        recursive_split_respect_elements: A list of element types (e.g., "table",
            "list", "code_block") that the recursive splitter should attempt to
            keep intact. Relies on `MarkdownTextSplitter`'s capabilities.
            Defaults to None.
        min_final_chunk_size: If set to a positive integer, chunks smaller than this
            size (in characters) will be merged with adjacent chunks, provided the
            merged chunk does not exceed `target_chunk_size`. Set to 0 or None
            to disable merging. Defaults to 100.

    Returns:
        A list of `langchain.schema.Document` objects, where each Document
        represents a chunk of the original Markdown text with associated metadata
        (including any header information if applicable).
    """
    logger = get_run_logger()
    logger.info(
        f"Starting Markdown chunking with initial_split_method='{initial_split_method}', "
        f"target_size='{target_chunk_size}', min_final_size='{min_final_chunk_size}', "
        f"semantic_refinement='{apply_semantic_refinement}', recursive_split='{apply_structural_recursive_split}'"
    )

    # For now, assumes markdown_text is the full content and base_metadata is empty
    # In a real scenario, base_metadata might come from an input Document object
    current_doc = Document(page_content=markdown_text, metadata={})

    # 1. Initial structural split (e.g., by headers)
    processed_chunks = _perform_initial_split(
        initial_doc=current_doc,
        method=initial_split_method,
        headers_to_split_on=headers_to_split_on,
        strip_headers=strip_headers,
        custom_delimiter_regex=custom_delimiter_regex,
        metadata_section_key=metadata_section_key
    )
    
    # 2. Optional Semantic Refinement
    if apply_semantic_refinement:
        logger.info("Applying semantic refinement stage.")
        if not semantic_config:
            logger.warning("Semantic refinement requested but no semantic_config provided. Using default semantic settings.")
            config_to_use = {} # Will trigger defaults in _apply_semantic_chunking
        else:
            config_to_use = semantic_config
        
        processed_chunks = _apply_semantic_chunking(
            input_chunks=processed_chunks, 
            config=config_to_use
        )
    else:
        logger.info("Skipping semantic refinement stage.")

    # 3. Optional Structural Recursive Splitting (for size)
    if apply_structural_recursive_split:
        logger.info("Applying structural recursive splitting stage.")
        processed_chunks = _apply_structural_recursive_split(
            input_chunks=processed_chunks,
            target_chunk_size=target_chunk_size,
            target_chunk_overlap=target_chunk_overlap,
            respect_elements=recursive_split_respect_elements 
            # `respect_elements` is passed but MarkdownTextSplitter handles MD structure by default
        )
    else:
        logger.info("Skipping structural recursive splitting stage.")

    # 4. Optional: Merge small final chunks
    if min_final_chunk_size is not None and min_final_chunk_size > 0 :
        logger.info(f"Applying final merge for chunks smaller than {min_final_chunk_size}.")
        processed_chunks = _merge_small_chunks(
            input_chunks=processed_chunks,
            min_size=min_final_chunk_size,
            target_chunk_size_limit=target_chunk_size # Use overall target_chunk_size as limit for merged chunks
        )
    elif min_final_chunk_size is not None and min_final_chunk_size <= 0:
        logger.info("min_final_chunk_size is non-positive, skipping final merge stage.")
    else: # min_final_chunk_size is None
        logger.info("No min_final_chunk_size specified, skipping final merge stage.")

    # 5. Final output
    logger.info(f"Markdown chunking finished. Total chunks produced: {len(processed_chunks)}")
    return processed_chunks

# Example Usage (for testing by the subtask worker if needed):
# if __name__ == "__main__":
#     test_md = "# Title 1\nSome text\n## Subtitle A\nMore text\n# Title 2\nEven more text"
#     # Create a dummy logger for local testing if needed
#     class DummyLogger:
#         def info(self, msg): print(f"INFO: {msg}")
#         def warning(self, msg): print(f"WARN: {msg}")
#     
#     # To make _perform_initial_split and chunk_markdown_document runnable locally for testing:
#     # You might need to temporarily un-@task them or use prefect.context correctly.
#     # For subtask testing, focusing on _AdaptedMarkdownHeaderTextSplitter might be easier.
#
#     # Test _AdaptedMarkdownHeaderTextSplitter
#     splitter = _AdaptedMarkdownHeaderTextSplitter()
#     doc = Document(page_content=test_md, metadata={"source": "test.md"})
#     header_chunks = splitter.split_document(doc)
#     for i, chunk in enumerate(header_chunks):
#         print(f"Chunk {i+1}:")
#         print(f"  Content: '{chunk.page_content[:50]}...'")
#         print(f"  Metadata: {chunk.metadata}")

# --- Chunk Merging Function ---
def _merge_small_chunks(
    input_chunks: List[Document], 
    min_size: int,
    # target_chunk_size_limit is the overall target, useful for not creating overly large merged chunks
    target_chunk_size_limit: Optional[int] = None 
) -> List[Document]:
    """
    Merges small adjacent chunks to avoid overly fragmented text.

    Iterates through `input_chunks` and attempts to merge chunks that are
    smaller than `min_size` (character length) with the subsequent chunk.
    Merging only occurs if the combined chunk does not exceed
    `target_chunk_size_limit`. Metadata is combined by taking all metadata from
    the first chunk and adding any new keys from the second chunk.

    Args:
        input_chunks: A list of `Document` objects to process.
        min_size: The minimum character length for a chunk. Chunks smaller
            than this will be considered for merging with their successor.
        target_chunk_size_limit: An optional maximum character length for a
            merged chunk. If a merge would exceed this, it's not performed.

    Returns:
        A new list of `Document` objects, with small chunks merged.
    """
    logger = get_run_logger()
    if not input_chunks or min_size <= 0:
        # also if min_size is 0 or negative, merging is not meaningful or can lead to infinite loops if not careful
        if min_size <= 0 and input_chunks: # Only log if there are chunks but min_size is invalid
            logger.warning(f"min_size ({min_size}) is not positive. Skipping merging.")
        return input_chunks

    logger.info(f"Merging small chunks (min_size={min_size}) from {len(input_chunks)} input chunks. Target limit: {target_chunk_size_limit}")
    merged_chunks: List[Document] = []
    
    buffer_doc: Optional[Document] = None

    for current_doc in input_chunks:
        if buffer_doc is None:
            buffer_doc = current_doc
            continue

        if len(buffer_doc.page_content) < min_size:
            # Try to merge buffer_doc with current_doc
            # Ensure there's content to merge to avoid just adding newlines between empty docs
            if not buffer_doc.page_content.strip() and not current_doc.page_content.strip():
                # Both are essentially empty, prefer current_doc if it has more specific metadata (e.g. headers)
                # This simple logic just keeps current_doc as the new buffer
                # A more sophisticated approach might try to preserve specific metadata from buffer_doc
                pass # buffer_doc effectively gets replaced by current_doc later if it's empty
            
            potential_merged_content = buffer_doc.page_content + "\n\n" + current_doc.page_content
            
            if target_chunk_size_limit is None or len(potential_merged_content) <= target_chunk_size_limit:
                # Merge is possible
                new_metadata = buffer_doc.metadata.copy()
                # Simple metadata merge: add keys from current_doc if not in buffer_doc's meta
                for key, value in current_doc.metadata.items():
                    if key not in new_metadata: # Prioritize buffer_doc's existing keys
                        new_metadata[key] = value
                    # More complex: if key exists, decide which to keep (e.g. more specific header)
                    # For now, this is fine.
                
                buffer_doc = Document(page_content=potential_merged_content, metadata=new_metadata)
            else:
                # Merge would make it too large, so finalize buffer_doc
                merged_chunks.append(buffer_doc)
                buffer_doc = current_doc # current_doc becomes the new buffer
        else:
            # buffer_doc is large enough, finalize it
            merged_chunks.append(buffer_doc)
            buffer_doc = current_doc # current_doc becomes the new buffer

    # Add the last buffered document
    if buffer_doc is not None:
        # Final check: if the very last buffered doc is still too small (but couldn't be merged)
        # it should still be added. The min_size is a "soft" target for merging, not a hard filter.
        merged_chunks.append(buffer_doc)
        
    logger.info(f"Merging small chunks resulted in {len(merged_chunks)} chunks.")
    return merged_chunks

# --- Structural Recursive Splitting Function ---
def _apply_structural_recursive_split(
    input_chunks: List[Document], 
    target_chunk_size: int, 
    target_chunk_overlap: int,
    respect_elements: Optional[List[RespectableElement]] = None # Parameter noted, but specific handling deferred
) -> List[Document]:
    """
    Applies structural recursive splitting to oversized chunks.

    Uses Langchain's `MarkdownTextSplitter` to split any `Document` in
    `input_chunks` whose page content exceeds `target_chunk_size`.
    This splitter is designed to respect Markdown syntax.

    Args:
        input_chunks: The list of `Document` objects to process.
        target_chunk_size: The desired maximum size for each chunk.
        target_chunk_overlap: The overlap between recursively split chunks.
        respect_elements: (Currently noted but relies on `MarkdownTextSplitter`'s
            inherent behavior) A list of Markdown element types that the
            splitter should try to keep intact.

    Returns:
        A new list of `Document` objects, where oversized chunks have been
        split. Chunks already within the size limit are passed through unchanged.
    """
    logger = get_run_logger()
    if not input_chunks:
        return []

    logger.info(f"Applying structural recursive splitting to {len(input_chunks)} input chunks with target size {target_chunk_size}.")
    processed_chunks_result: List[Document] = []

    # Initialize the splitter once if its parameters are static for all chunks
    # MarkdownTextSplitter is good at handling markdown structures.
    markdown_splitter = MarkdownTextSplitter(
        chunk_size=target_chunk_size,
        chunk_overlap=target_chunk_overlap,
        # length_function=len # Default
    )

    for doc_chunk in input_chunks:
        # A common practice is to only split if significantly larger, e.g., > 10-20% of target_chunk_size
        # For simplicity here, we'll split if it's just greater.
        if len(doc_chunk.page_content) > target_chunk_size:
            try:
                split_texts = markdown_splitter.split_text(doc_chunk.page_content)
                for text_part in split_texts:
                    if text_part.strip(): # Ensure non-empty content
                        new_doc = Document(
                            page_content=text_part,
                            metadata=doc_chunk.metadata.copy() # Inherit metadata
                        )
                        processed_chunks_result.append(new_doc)
                    elif doc_chunk.page_content.strip() == "" and not text_part.strip() and len(split_texts) == 1:
                        # If the original chunk was only whitespace and resulted in one empty split part, retain it.
                        processed_chunks_result.append(Document(page_content="", metadata=doc_chunk.metadata.copy()))


            except Exception as e:
                logger.error(f"Error during Markdown splitting of a chunk: {e}. Adding original chunk instead.")
                processed_chunks_result.append(doc_chunk)
        else:
            # Chunk is small enough, keep as is
            processed_chunks_result.append(doc_chunk)
            
    logger.info(f"Structural recursive splitting resulted in {len(processed_chunks_result)} chunks.")
    return processed_chunks_result

# --- Semantic Chunking Function ---
def _apply_semantic_chunking(
    input_chunks: List[Document], 
    config: SemanticChunkerConfig
) -> List[Document]:
    """
    Applies semantic chunking to a list of existing Document chunks.

    Uses Langchain's `SemanticChunker` with Ollama embeddings to further
    split each input chunk based on semantic breakpoints. This aims to create
    chunks that are more thematically coherent.

    Args:
        input_chunks: The list of `Document` objects to be refined.
        config: A `SemanticChunkerConfig` dictionary containing parameters
            for the `OllamaEmbeddings` and `SemanticChunker`.

    Returns:
        A new list of `Document` objects, potentially with more numerous but
        semantically distinct chunks. If embedding initialization or chunking
        fails for a document, the original document is typically returned in its place.
    """
    logger = get_run_logger()
    if not input_chunks:
        return []
    
    logger.info(f"Applying semantic chunking to {len(input_chunks)} input chunks.")
    semantic_chunks_result: List[Document] = []

    # Default values from config or global defaults
    ollama_model_name = config.get("ollama_model", "nomic-embed-text")
    ollama_service_url = config.get("ollama_base_url", "http://localhost:11434")
    threshold_type = config.get("breakpoint_threshold_type", "percentile")
    # Default for percentile is often 0.95, for standard_deviation 1.5 etc.
    # SemanticChunker's default for percentile is 0.95.
    threshold_amount = config.get("breakpoint_threshold_amount", 0.95) 
    buffer_size = config.get("buffer_size", 1) # SemanticChunker default is 1. Original code used 3. Let's use SC default for now.
    # min_semantic_chunk_size = config.get("min_chunk_size") # Not directly used by SC constructor with split_text

    try:
        embeddings = OllamaEmbeddings(
            model=ollama_model_name,
            base_url=ollama_service_url
        )
    except Exception as e:
        logger.error(f"Failed to initialize OllamaEmbeddings with model '{ollama_model_name}' at '{ollama_service_url}': {e}. Skipping semantic chunking.")
        return input_chunks # Return original chunks if embeddings fail

    # Initialize SemanticChunker
    # Note: SemanticChunker does not take min_chunk_size directly in constructor for split_text.
    # It's more relevant for create_documents or split_documents.
    # Size filtering is deferred to later pipeline stages.
    semantic_chunker_instance = SemanticChunker(
        embeddings=embeddings,
        breakpoint_threshold_type=threshold_type,
        breakpoint_threshold_amount=threshold_amount,
        buffer_size=buffer_size 
        # add_start_index=False # This is a default for SemanticChunker
    )

    for doc_chunk in input_chunks:
        if not doc_chunk.page_content.strip(): # Skip empty or whitespace-only documents
            if doc_chunk.metadata: # Keep chunks that are empty but have metadata
                 semantic_chunks_result.append(doc_chunk)
            continue

        try:
            # SemanticChunker's split_text is expected to work on single strings.
            single_doc_semantic_texts = semantic_chunker_instance.split_text(doc_chunk.page_content)
            
            for text_part in single_doc_semantic_texts:
                if text_part.strip(): # Ensure non-empty content after split
                    new_doc = Document(
                        page_content=text_part,
                        metadata=doc_chunk.metadata.copy() # Inherit metadata
                    )
                    semantic_chunks_result.append(new_doc)
                elif not text_part.strip() and doc_chunk.page_content.strip():
                    # Original content was not empty, but a part became empty. Log this.
                    logger.debug(f"A part of a chunk became empty after semantic splitting. Original content length: {len(doc_chunk.page_content)}")
            
            if not single_doc_semantic_texts and doc_chunk.page_content.strip():
                # If split_text returns empty list for a non-empty document, add original back
                logger.warning("SemanticChunker returned no splits for a non-empty chunk. Reverting to original chunk.")
                semantic_chunks_result.append(doc_chunk)

        except Exception as e:
            logger.error(f"Error during semantic splitting of a chunk (source: {doc_chunk.metadata.get('source', 'N/A')}, current_header: {doc_chunk.metadata.get('current_header', 'N/A')}): {e}. Adding original chunk instead.")
            # Add the original chunk back if processing failed for it
            semantic_chunks_result.append(doc_chunk)
            
    logger.info(f"Semantic chunking resulted in {len(semantic_chunks_result)} chunks.")
    return semantic_chunks_result
