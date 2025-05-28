
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

from tasks.helper_function import *
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
        ollama_model="nomic-embed-text",  # 使用本地轻量模型
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
    ollama_model: str = "nomic-embed-text",
    ollama_base_url: str = "http://localhost:11434"
) -> List[Document]:
    """测试用例执行器"""
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
        ollama_model=ollama_model,
        ollama_base_url=ollama_base_url
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

    # 执行评估
    evaluate_propositions(
        original_doc=original_doc,
        generated_doc=generated_doc,
        model="deepseek-r1:1.5b"  # 使用实际部署的模型名称
    )

    
# ------------------------ 执行入口 ------------------------
if __name__ == "__main__":
    # 测试简单分块
    # test_split_markdown_by_headers()
  
  
    # 测试语义分块
    # test_split_markdown_semantic()
    
    
    # 测试时模拟Prefect环境
    # from prefect import flow
    # @flow
    # def test_flow():
    #     return prefect_logger_proposition_chunking("测试文本...")
    
    # test_flow()
    # md_path = "../data/output/markdown/test01/RevolutionMaximaUserManualCN453-454.md"

    # test_content = extract_text_from_markdown(md_path)
    
    # base_docs = split_markdown_by_headers(
    #     content=test_content,
    #     headers_to_split_on=[("#", "H1"), ("##", "H2")],
    #     sub_headers=[("###", "H3")],
    #     chunk_size=1500,
    #     min_chunk_size=100,
    #     sub_split_threshold=2000,
    # )
    # results = generate_propositions(chunks = base_docs)
    
    
    # 测试命题生成
    # original = Document(page_content="2025年特斯拉Model S续航达1000公里，采用固态电池技术")
    # generated = Document(page_content="1. Model S是特斯拉旗舰车型\n2. 2025款续航突破1000公里")

    # # 执行评估
    # results = evaluate_propositions(original, generated)
    
    # print(results)




# 测试重写查询
    # custom_template = """你是一名专业的搜索查询优化专家。你需要扩展并阐明以下搜索查询，同时保持其原始意图：

    # 原始查询：{original_query}

    # 直接输出优化后的版本，不要有分析等解释性文字"""
    
    # # 创建重写器实例
    # query_rewriter = rewrite_query(
    #     original_query="气候变化的影响",
    #     query_template=custom_template,
    #     model="deepseek-r1:14b",

    # )
    
    # # 使用重写器
    # print(query_rewriter)
    
    # test_query = "气候变化对环境的直接影响有哪些？"
    
    # # 生成回溯查询（自动适配中文场景）
    # broader_query = generate_step_back_query(
    #     test_query,
    #     # model="deepseek-r1:14b",
    #     model="deepseek-r1:8b",
    # )
    
    # print(f"原始查询：{test_query}")
    # print(f"广义查询：{broader_query}")
    
    
    
    # 传入自定义模板
    queries = decompose_query(
        "如何构建抗通胀投资组合？",
        model="deepseek-r1:1.5b"
    )
    
    for i, q in enumerate(queries, 1):
        print(f"{i}. {q}")