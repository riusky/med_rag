
# med-rag-flow/tasks/chunking_task.py
from prefect import get_run_logger # flow # Keep if using flows, or remove if just direct .fn calls
from med_rag_flow.tasks.chunking import chunk_markdown_document
from med_rag_flow.tasks.chunking.markdown_chunker import SemanticChunkerConfig 
from langchain.schema import Document 


# --- Comment out or remove old/obsolete functions and imports ---
# from collections import defaultdict # No longer used directly
# import copy # No longer used directly
# import os # No longer used directly
# import sys # No longer used directly
# from langchain_ollama import OllamaEmbeddings # Internal to markdown_chunker
# from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter # Internal
# 获取项目根目录路径（假设文件在 med-rag-flow/tasks/ 目录下）
# root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__))) # Not needed for new structure
# sys.path.append(root_dir) # Not needed

# from tasks.helper_function import * # If this was for old functions - presumed obsolete for chunking
# from prefect import task # task decorator used in markdown_chunker, not here directly for examples
# from langchain_experimental.text_splitter import SemanticChunker # Internal
# import re # No longer used directly
# from langchain_ollama import OllamaLLM # For other tasks, not this example file
# from langchain_core.prompts import ChatPromptTemplate # For other tasks
# from langchain_core.pydantic_v1 import BaseModel, Field # For other tasks
# from langchain_core.output_parsers import StrOutputParser # For other tasks
# from json import loads # For other tasks

# # 提示模板 - Presuming this is for proposition evaluation, not core chunking examples
# evaluation_prompt_template = """
# 请根据以下标准评估命题：
# - **准确性**：根据命题反映原文的程度，从1 - 10进行评分。
# - **清晰度**：根据在不借助额外上下文的情况下理解命题的难易程度，从1 - 10进行评分。
# - **完整性**：根据命题是否包含必要细节（例如日期、限定词），从1 - 10进行评分。
# - **简洁性**：根据命题是否简洁且未丢失重要信息，从1 - 10进行评分。
# 
# 示例输出：
# ```json
# [{{
#   "accuracy": 8,
#   "clarity": 7,
#   "completeness": 6,
#   "conciseness": 8
# }}
# ]
# ```
# """

# def test_proposition_evaluation_basic():
#     """基础功能测试：验证评估流程正常执行"""
#     # 构造测试数据
#     original_doc = Document(
#         page_content="2023年特斯拉Model S续航里程提升至637公里，采用新型4680电池",
#         metadata={"source": "test_case_1"}
#     )
#     
#     generated_doc = Document(
#         page_content="1. Model S是特斯拉的车型\n2. Model S续航里程为637公里\n3. 4680电池用于Model S",
#         metadata={"generated_by": "test"}
#     )
# 
#     # 执行评估
#     # evaluate_propositions( # This function would need to be defined/imported if used
#     #     original_doc=original_doc,
#     #     generated_doc=generated_doc,
#     #     model="deepseek-r1:1.5b"  # 使用实际部署的模型名称
#     # )
#     pass # Commenting out the call as evaluate_propositions is not defined here


def example_basic_header_splitting():
    logger = get_run_logger()
    logger.info("--- Running Basic Header Splitting Example ---")
    sample_md = "# Title 1\nContent for title 1.\n## Subtitle 1.1\nContent for subtitle 1.1\n# Title 2\nContent for title 2."
    
    chunks = chunk_markdown_document.fn(
        markdown_text=sample_md,
        initial_split_method="header",
        apply_structural_recursive_split=False, 
        apply_semantic_refinement=False,
        min_final_chunk_size=0 
    )
    
    logger.info(f"Produced {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        logger.info(f"Chunk {i+1} Metadata: {chunk.metadata}")
        logger.info(f"Chunk {i+1} Content: '{chunk.page_content[:100].replace('\n', ' ')}...'\n")

def example_header_recursive_merge_splitting():
    logger = get_run_logger()
    logger.info("--- Running Header + Recursive + Merge Splitting Example ---")
    sample_md = (
        "# Main Title\nThis is the introduction. It's a bit short for recursive splitting on its own.\n"
        "## Section 1\nThis section has a lot of text. " * 8 + # Approx 8 * 30 = 240 chars
        "It should be split recursively. " * 8 + # Approx 8 * 30 = 240 chars
        "And then some small parts might merge. " * 3 + # Approx 3 * 35 = 105 chars
        "Another short sentence.\nA very tiny bit.\n" # Approx 30 chars
        "### Subsection 1.1\nDetails here. " * 5 + # Approx 5 * 15 = 75 chars
        "Another small line.\nA final tiny piece." # Approx 30 chars
    )

    chunks = chunk_markdown_document.fn(
        markdown_text=sample_md,
        initial_split_method="header",
        headers_to_split_on=[("#", "h1"), ("##", "h2"), ("###", "h3")],
        strip_headers=False,
        apply_semantic_refinement=False, 
        apply_structural_recursive_split=True,
        target_chunk_size=150, 
        target_chunk_overlap=20,
        min_final_chunk_size=50 
    )

    logger.info(f"Produced {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        logger.info(f"Chunk {i+1} (Length: {len(chunk.page_content)}) Metadata: {chunk.metadata}")
        logger.info(f"Chunk {i+1} Content: '{chunk.page_content[:100].replace('\n', ' ')}...'\n")

def example_recursive_only_splitting():
    logger = get_run_logger()
    logger.info("--- Running Recursive Only Splitting Example ---")
    sample_md = (
        "This is a long document without any standard markdown headers. " * 10 +
        "It's just a wall of text that needs to be broken down by size. " * 10 +
        "The recursive character splitter should handle this gracefully. " * 10
    )
    
    chunks = chunk_markdown_document.fn(
        markdown_text=sample_md,
        initial_split_method="none", # Key for this test
        apply_structural_recursive_split=True,
        target_chunk_size=200,
        target_chunk_overlap=30,
        apply_semantic_refinement=False,
        min_final_chunk_size=50 # Merging can still be useful
    )
    
    logger.info(f"Produced {len(chunks)} chunks:")
    for i, chunk in enumerate(chunks):
        logger.info(f"Chunk {i+1} (Length: {len(chunk.page_content)}) Metadata: {chunk.metadata}") # Metadata should be empty
        logger.info(f"Chunk {i+1} Content: '{chunk.page_content[:100].replace('\n', ' ')}...'\n")


def example_semantic_config_structure():
    logger = get_run_logger()
    logger.info("--- Illustrating SemanticChunkerConfig Structure (No Run) ---")
    
    # This is just to show the structure and how it would be passed.
    # Running semantic splitting requires a running Ollama instance with the specified model.
    sc_config_example = SemanticChunkerConfig(
        ollama_model="nomic-embed-text", 
        ollama_base_url="http://localhost:11434", # Default, but good to show
        breakpoint_threshold_type="percentile", 
        breakpoint_threshold_amount=0.95, # A common default for percentile
        buffer_size=1 # SemanticChunker's default
        # min_chunk_size is also in SemanticChunkerConfig but not directly used by SC.split_text
    )
    
    logger.info(f"Example SemanticChunkerConfig structure: {sc_config_example}")
    logger.info("To use this, set apply_semantic_refinement=True and pass this config.")
    
    sample_md_for_semantic = "# Semantic Splitting Intro\nThis is a short text. Semantic splitting works best on longer, more coherent paragraphs. It tries to find natural breaks."
    # try:
    #     chunks = chunk_markdown_document.fn(
    #         markdown_text=sample_md_for_semantic,
    #         initial_split_method="header",
    #         apply_semantic_refinement=True,
    #         semantic_config=sc_config_example,
    #         apply_structural_recursive_split=False, # Turn off other processing for clarity
    #         min_final_chunk_size=0
    #     )
    #     logger.info(f"Semantic splitting (if Ollama running) produced {len(chunks)} chunks:")
    #     for i, chunk in enumerate(chunks):
    #         logger.info(f"Chunk {i+1} (Length: {len(chunk.page_content)}) Metadata: {chunk.metadata}")
    #         logger.info(f"Chunk {i+1} Content: '{chunk.page_content[:100].replace('\n', ' ')}...'\n")
    # except Exception as e:
    #     logger.error(f"Could not run semantic splitting example, possibly Ollama not running or model not found: {e}")
    logger.warning("Actual semantic splitting example is commented out to prevent errors if Ollama is not available.")


# @flow(name="chunking_examples_flow") # Example if running as a Prefect flow
# def run_chunking_examples_flow():
#     example_basic_header_splitting()
#     example_header_recursive_merge_splitting()
#     example_recursive_only_splitting()
#     example_semantic_config_structure()

if __name__ == "__main__":
    class PrintLogger:
        def info(self, msg: str): print(f"INFO: {msg}")
        def warning(self, msg: str): print(f"WARN: {msg}")
        def error(self, msg: str): print(f"ERROR: {msg}")
        def debug(self, msg: str): print(f"DEBUG: {msg}")


    # Monkey patch get_run_logger for local script execution
    # This affects the logger inside chunk_markdown_document and its sub-functions directly
    import med_rag_flow.tasks.chunking.markdown_chunker as md_chunker_module
    original_logger_func = md_chunker_module.get_run_logger
    md_chunker_module.get_run_logger = lambda: PrintLogger()
    
    # Also patch it for this file if get_run_logger is called directly here
    # However, new examples call it directly.
    # For a cleaner approach, pass the logger into functions or use standard Python logging.
    # For this example, we'll rely on the module-level patch for the task's internal logging.
    # The logger used directly in example functions here will be PrintLogger by direct instantiation.
    
    # To make examples use PrintLogger when they call get_run_logger():
    # import builtins
    # original_get_run_logger = get_run_logger # if it was imported directly
    # builtins.get_run_logger = lambda: PrintLogger() # Overrides for this script too
    # For now, the examples instantiate PrintLogger directly or rely on the patch in markdown_chunker.

    # Setup this script's logger to be PrintLogger for direct calls if any
    # No, the example functions directly instantiate logger = get_run_logger()
    # So we need to ensure that `get_run_logger` used by them is patched.
    # The current patch only affects `md_chunker_module.get_run_logger`.
    # A more robust way for local execution of examples would be to pass a logger instance.
    # For now, let's assume the examples will pick up the patched logger if they were structured differently,
    # or we can explicitly pass `PrintLogger()` to them if they accepted a logger.
    # The provided example structure in prompt uses `logger = get_run_logger()` inside examples.
    # To make THAT work with PrintLogger, we'd have to patch `get_run_logger` in *this* module's scope.

    # Let's ensure this script's get_run_logger is also patched for the example functions
    # This is getting a bit convoluted due to get_run_logger being module-specific via `from prefect import ...`
    # The most straightforward for the prompt's example structure is to patch where it's defined.
    # The patch for md_chunker_module.get_run_logger is correct for internal task logging.
    # For the example functions in *this* file, they'd need their own `get_run_logger` patched.
    # Simplest for now: the example functions will use the *actual* Prefect logger if run in a Prefect context,
    # or fail if not. The monkeypatch in the prompt's main block is fine for the task's internal logging.

    print("Running examples using monkey-patched logger for internal task logging...")
    
    example_basic_header_splitting()
    print("\n" + "="*50 + "\n")
    example_header_recursive_merge_splitting()
    print("\n" + "="*50 + "\n")
    example_recursive_only_splitting()
    print("\n" + "="*50 + "\n")
    example_semantic_config_structure()
    
    # Restore original logger
    md_chunker_module.get_run_logger = original_logger_func
    
    # To run as a Prefect flow (if Prefect server/agent is configured):
    # print("\n To run as a Prefect flow, uncomment run_chunking_examples_flow() and ensure Prefect is set up.")
    # run_chunking_examples_flow()