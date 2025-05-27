
from collections import defaultdict
import copy
import os
import sys
from langchain.schema import Document
from typing import List, Tuple, Optional, Dict, Any
from langchain_ollama import OllamaEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter, MarkdownHeaderTextSplitter
# 获取项目根目录路径（假设文件在 med-rag-flow/tasks/ 目录下）
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

# Updated imports:
from med_rag_flow.utils.str_utils import replace_t_with_space 
from med_rag_flow.utils.file_utils import extract_text_from_markdown
from med_rag_flow.utils.config_loader import ConfigLoader # Added ConfigLoader
# from tasks.helper_function import * # Original import removed

# Import the refactored tasks
from med_rag_flow.tasks.chunking.markdown_semantic_chunk import split_markdown_by_headers, split_markdown_semantic
from med_rag_flow.tasks.chunking.markdown_propositions_chunk import propositions as generate_propositions, evaluate_propositions
# Assuming query transformation functions might be here or need similar treatment if used in main block
# from med_rag_flow.tasks.query_transformations import rewrite_query, generate_step_back_query, decompose_query


from prefect import task, get_run_logger
from langchain_experimental.text_splitter import SemanticChunker
import re
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from prefect import task, get_run_logger
from langchain_core.output_parsers import StrOutputParser
from json import loads

# 提示模板
evaluation_prompt_template = """
请根据以下标准评估命题：
- **准确性**：根据命题反映原文的程度，从1 - 10进行评分。
- **清晰度**：根据在不借助额外上下文的情况下理解命题的难易程度，从1 - 10进行评分。
- **完整性**：根据命题是否包含必要细节（例如日期、限定词），从1 - 10进行评分。
- **简洁性**：根据命题是否简洁且未丢失重要信息，从1 - 10进行评分。

示例输出：
```json
[{{
  "accuracy": 8,
  "clarity": 7,
  "completeness": 6,
  "conciseness": 8
}}
]
```

"""
def test_split_markdown_semantic():
    """测试全流程分块逻辑"""
    # 测试用例配置
    # 定义Markdown文件路径
    md_path = "../data/output/markdown/test01/RevolutionMaximaUserManualCN453-454.md"

    # 调用函数提取文本
    test_content = extract_text_from_markdown(md_path)
    
    # 场景1：基础标题分块
    basic_chunks = _run_test_case(
        content=test_content,
        headers_to_split_on=[("#", "H1"), ("##", "H2")],
        enable_subheader_split=False,
        # ollama_model parameter removed, will default to None in _run_test_case
        # allowing split_markdown_semantic to load from its config.
        semantic_threshold_type="percentile",
        semantic_threshold=90
    )
    
    # 结果分析
    for doc in basic_chunks:
        print(f"长度: {len(doc.page_content)}")
        print(f"元数据: {doc.metadata}\n")

def _run_test_case(
    content: str = None,
    headers_to_split_on: List[tuple] = [("#", "H1"), ("##", "H2")],
    header_chunk_size: int = 1200,
    header_chunk_overlap: int = 200,
    header_min_chunk_size: int = 100,
    enable_subheader_split: bool = True,
    sub_headers: List[tuple] = [("###", "H3")],
    sub_split_threshold: int = 800,
    final_chunk_size: int = 1000,
    final_chunk_overlap: int = 150,
    semantic_threshold_type: str = "percentile",
    semantic_threshold: float = 0.85,
    semantic_window_size: int = 3,
    strip_headers: bool = False,
    keep_markdown_format: bool = True,
    final_min_size: int = 150,
    ollama_model: Optional[str] = None, # Default to None
    ollama_base_url: Optional[str] = None # Default to None
) -> List[Document]:
    """测试用例执行器"""
    # split_markdown_by_headers does not require ollama_model or ollama_base_url directly
    base_docs = split_markdown_by_headers( 
        content=content,
        headers_to_split_on=headers_to_split_on,
        sub_headers=sub_headers,
        chunk_size=header_chunk_size,
        min_chunk_size=header_min_chunk_size,
        sub_split_threshold=sub_split_threshold,
    )
    
    return split_markdown_semantic(
        base_docs = base_docs,
        final_chunk_size=final_chunk_size,
        final_chunk_overlap=final_chunk_overlap,
        semantic_threshold_type=semantic_threshold_type,
        semantic_threshold=semantic_threshold,
        semantic_window_size=semantic_window_size,
        keep_markdown_format=keep_markdown_format,
        final_min_size=final_min_size,
        embedding_model_name=ollama_model, # Pass None or specific model
        ollama_base_url=ollama_base_url    # Pass None or specific URL
    )
    
    
    
def test_proposition_evaluation_basic():
    """基础功能测试：验证评估流程正常执行"""
    # 构造测试数据
    original_doc = Document(
        page_content="2023年特斯拉Model S续航里程提升至637公里，采用新型4680电池",
        metadata={"source": "test_case_1"}
    )
    
    generated_doc = Document(
        page_content="1. Model S是特斯拉的车型\n2. Model S续航里程为637公里\n3. 4680电池用于Model S",
        metadata={"generated_by": "test"}
    )

    # 执行评估 - model_name and ollama_base_url will be loaded from config by the task
    evaluate_propositions(
        original_doc=original_doc,
        generated_doc=generated_doc
        # model parameter removed
    )

    
# ------------------------ 执行入口 ------------------------
if __name__ == "__main__":
    # Initialize ConfigLoader for the main block
    # Assuming this script is in med-rag-flow/tasks/
    # So config is at ../config/settings.yaml relative to this script if it's in tasks/
    # Or more robustly, define a project root or use absolute paths for config in such scripts.
    # For now, let's assume a relative path that works if script is run from `tasks` dir
    # or if the `ConfigLoader` handles path resolution well.
    # A better practice for scripts is to make config_path an argument or environment variable.
    
    # Robust config path determination assuming this script is in med-rag-flow/tasks/chunking_task.py
    current_script_path = Path(__file__).resolve()
    project_root = current_script_path.parent.parent # Moves up two levels: tasks -> med-rag-flow
    default_config_path = str(project_root / "config/settings.yaml")
    
    print(f"Loading configuration from: {default_config_path}")
    cfg = ConfigLoader(config_path=default_config_path)
    
    ollama_base_url_from_config = cfg.get_config("services.ollama.base_url", "http://localhost:11434") # Default if not in config
    default_prop_model_from_config = cfg.get_config("services.ollama.default_proposition_model", "deepseek-r1:1.5b")
    # semantic_chunker_model_from_config = cfg.get_config("services.ollama.semantic_chunker_embedding_model", "nomic-embed-text")

    print(f"Using Ollama Base URL: {ollama_base_url_from_config}")
    print(f"Using Default Proposition Model: {default_prop_model_from_config}")

    # Example: test_split_markdown_semantic (if uncommented)
    # print("\n--- Testing Semantic Split ---")
    # test_split_markdown_semantic() # This will now use None for model/URL in _run_test_case, letting tasks load from config

    # Example: test_proposition_evaluation_basic (if uncommented)
    # print("\n--- Testing Proposition Evaluation ---")
    # test_proposition_evaluation_basic() # This will now use configured defaults in evaluate_propositions

    # Example: generate_propositions (if uncommented)
    # print("\n--- Testing Generate Propositions ---")
    # md_path_example = project_root / "data/output/markdown/test01/RevolutionMaximaUserManualCN453-454.md" # Example path
    # if md_path_example.exists():
    #     test_content_example = extract_text_from_markdown(md_path_example)
    #     base_docs_example = split_markdown_by_headers( # This task does not require LLM config
    #         content=test_content_example,
    #         headers_to_split_on=[("#", "H1"), ("##", "H2")],
    #         sub_headers=[("###", "H3")],
    #         chunk_size=1500,
    #         min_chunk_size=100,
    #         sub_split_threshold=2000,
    #     )
    #     # generate_propositions will use configured model and URL
    #     results_propositions = generate_propositions(chunks=base_docs_example) 
    #     for res_prop in results_propositions:
    #         print(f"Generated Proposition Content: {res_prop.page_content[:100]}...")
    #         print(f"Metadata: {res_prop.metadata}\n")
    # else:
    #     print(f"Markdown file for proposition test not found: {md_path_example}")


    # The query transformation functions (rewrite_query, generate_step_back_query, decompose_query)
    # are not specified as part of this refactoring subtask for internal ConfigLoader integration.
    # However, their calls in this __main__ block can be updated to use configured models if they accept model_name.
    # Assuming they are imported and accept 'model' and 'base_url' (or just 'model' if base_url is fixed/globally set for them)
    
    # Example for decompose_query, assuming it's imported and takes model parameter
    # from med_rag_flow.tasks.query_transformations import decompose_query # Placeholder import
    
    # print("\n--- Testing Decompose Query ---")
    # try:
    #     # This part is tricky as decompose_query itself is not refactored yet to use ConfigLoader for its *internal* defaults
    #     # We are just changing how it's *called* in this example script.
    #     # If decompose_query has a hardcoded model or URL internally, that won't change here.
    #     # This assumes decompose_query takes 'model' as a parameter.
    #     decomposed_queries = decompose_query(
    #         "如何构建抗通胀投资组合？",
    #         model=default_prop_model_from_config # Using a configured model for the call
    #     )
    #     for i, q_d in enumerate(decomposed_queries, 1):
    #         print(f"{i}. {q_d}")
    # except NameError:
    #     print("decompose_query not imported or defined, skipping test.")
    # except Exception as e_dq:
    #     print(f"Error in decompose_query example: {e_dq}")

    # print("\nChunking task script main block finished.")

# TODO: Move the following test/demonstration code to proper unit tests under the tests/ directory.
# if __name__ == "__main__":
    # Initialize ConfigLoader for the main block
    # Assuming this script is in med-rag-flow/tasks/
    # So config is at ../config/settings.yaml relative to this script if it's in tasks/
    # Or more robustly, define a project root or use absolute paths for config in such scripts.
    # For now, let's assume a relative path that works if script is run from `tasks` dir
    # or if the `ConfigLoader` handles path resolution well.
    # A better practice for scripts is to make config_path an argument or environment variable.
    
    # Robust config path determination assuming this script is in med-rag-flow/tasks/chunking_task.py
    # current_script_path = Path(__file__).resolve()
    # project_root = current_script_path.parent.parent # Moves up two levels: tasks -> med-rag-flow
    # default_config_path = str(project_root / "config/settings.yaml")
    
    # print(f"Loading configuration from: {default_config_path}")
    # cfg = ConfigLoader(config_path=default_config_path)
    
    # ollama_base_url_from_config = cfg.get_config("services.ollama.base_url", "http://localhost:11434") # Default if not in config
    # default_prop_model_from_config = cfg.get_config("services.ollama.default_proposition_model", "deepseek-r1:1.5b")
    # semantic_chunker_model_from_config = cfg.get_config("services.ollama.semantic_chunker_embedding_model", "nomic-embed-text")

    # print(f"Using Ollama Base URL: {ollama_base_url_from_config}")
    # print(f"Using Default Proposition Model: {default_prop_model_from_config}")

    # Example: test_split_markdown_semantic (if uncommented)
    # print("\n--- Testing Semantic Split ---")
    # test_split_markdown_semantic() # This will now use None for model/URL in _run_test_case, letting tasks load from config

    # Example: test_proposition_evaluation_basic (if uncommented)
    # print("\n--- Testing Proposition Evaluation ---")
    # test_proposition_evaluation_basic() # This will now use configured defaults in evaluate_propositions

    # Example: generate_propositions (if uncommented)
    # print("\n--- Testing Generate Propositions ---")
    # md_path_example = project_root / "data/output/markdown/test01/RevolutionMaximaUserManualCN453-454.md" # Example path
    # if md_path_example.exists():
    #     test_content_example = extract_text_from_markdown(md_path_example)
    #     base_docs_example = split_markdown_by_headers( # This task does not require LLM config
    #         content=test_content_example,
    #         headers_to_split_on=[("#", "H1"), ("##", "H2")],
    #         sub_headers=[("###", "H3")],
    #         chunk_size=1500,
    #         min_chunk_size=100,
    #         sub_split_threshold=2000,
    #     )
    #     # generate_propositions will use configured model and URL
    #     results_propositions = generate_propositions(chunks=base_docs_example) 
    #     for res_prop in results_propositions:
    #         print(f"Generated Proposition Content: {res_prop.page_content[:100]}...")
    #         print(f"Metadata: {res_prop.metadata}\n")
    # else:
    #     print(f"Markdown file for proposition test not found: {md_path_example}")


    # The query transformation functions (rewrite_query, generate_step_back_query, decompose_query)
    # are not specified as part of this refactoring subtask for internal ConfigLoader integration.
    # However, their calls in this __main__ block can be updated to use configured models if they accept model_name.
    # Assuming they are imported and accept 'model' and 'base_url' (or just 'model' if base_url is fixed/globally set for them)
    
    # Example for decompose_query, assuming it's imported and takes model parameter
    # from med_rag_flow.tasks.query_transformations import decompose_query # Placeholder import
    
    # print("\n--- Testing Decompose Query ---")
    # try:
    #     # This part is tricky as decompose_query itself is not refactored yet to use ConfigLoader for its *internal* defaults
    #     # We are just changing how it's *called* in this example script.
    #     # If decompose_query has a hardcoded model or URL internally, that won't change here.
    #     # This assumes decompose_query takes 'model' as a parameter.
    #     decomposed_queries = decompose_query(
    #         "如何构建抗通胀投资组合？",
    #         model=default_prop_model_from_config # Using a configured model for the call
    #     )
    #     for i, q_d in enumerate(decomposed_queries, 1):
    #         print(f"{i}. {q_d}")
    # except NameError:
    #     print("decompose_query not imported or defined, skipping test.")
    # except Exception as e_dq:
    #     print(f"Error in decompose_query example: {e_dq}")

    # print("\nChunking task script main block finished.")