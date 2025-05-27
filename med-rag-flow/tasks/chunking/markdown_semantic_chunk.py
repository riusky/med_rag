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
# from tasks.helper_function import * # Original import removed

from prefect import task, get_run_logger
from langchain_experimental.text_splitter import SemanticChunker
import re
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from prefect import task, get_run_logger
from langchain_core.output_parsers import StrOutputParser
from json import loads

from med_rag_flow.utils.config_loader import ConfigLoader # Added ConfigLoader import
from med_rag_flow.tasks.chunking.markdown_hybrid_chunk import MarkdownHeaderTextSplitter # Ensure full path or correct relative


@task(name="split_markdown_by_headers") # This task itself doesn't use LLM directly, so no ollama_base_url needed for its direct operation
def split_markdown_by_headers(
    content: str,
    headers_to_split_on: List[Tuple[str, str]],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    min_chunk_size: Optional[int] = 50,
    strip_headers: bool = False,
    sub_headers: Optional[List[Tuple[str, str]]] = None,
    sub_split_threshold: int = 800
) -> List[Document]:
    """
    基于标题层级的Markdown分块预处理任务
    
    |‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾|
    | 实现多级Markdown文档分块策略：                                                  |
    | 1. 按指定标题层级进行初步分割                                                   |
    | 2. 对长内容启用子标题二次分割                                                   |
    | 3. 最终执行字符级分块控制                                                       |
    | 4. 合并过短文本块                                                              | 
    |_______________________________________________________________________________|
    
    Args:
        content: 原始Markdown文本内容
        headers_to_split_on: 标题配置列表，格式 [(符号, 元数据键), 如("#", "H1")]
        chunk_size: 最终分块最大字符数（默认：1000）
        chunk_overlap: 分块重叠字符数（默认：200）
        min_chunk_size: 最小保留块大小，低于此值将合并（默认：50，None表示禁用）
        strip_headers: 是否移除标题行文本（默认：False保留）
        sub_headers: 子标题配置（如[("###", "H3")]），用于二次分割
        sub_split_threshold: 触发子标题分割的长度阈值（默认：800字符）

    Returns:
        List[Document]: 结构化分块结果，每个块包含：
        - page_content: 文本内容（保留段落结构）
        - metadata: 层级标题元数据（示例：{"H1": "标题", "H2": "子标题"}）

    Example:
        >>> split_markdown_by_headers(
        ...     content="# 标题\\n内容...",
        ...     headers_to_split_on=[("#", "H1")],
        ...     chunk_size=500
        ... )
    """
    logger = get_run_logger()
    try:
        # 元数据统计初始化
        meta_counter = defaultdict(int)
        
        # 记录初始状态
        logger.debug(f"原始内容长度: {len(content)} 字符")
        logger.info("开始标题层级分块处理...")

        # Step 1: 基础标题分割
        logger.debug("执行基础标题分割...")
        header_splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=headers_to_split_on,
            strip_headers=strip_headers
        )
        initial_docs = header_splitter.split_text(content)
        logger.info(f"基础分割完成 ➔ 初始分块数: {len(initial_docs)}")
        _log_metadata_distribution(initial_docs, meta_counter, logger)

        # Step 2: 子标题二次分割
        if sub_headers:
            logger.debug(
                f"启用子标题二次分割 (阈值: {sub_split_threshold}字符)",
                sub_headers=str(sub_headers)
            )
            initial_docs = _split_with_sub_headers(
                initial_docs, sub_headers, sub_split_threshold, 
                strip_headers, headers_to_split_on
            )
            logger.info(f"子标题分割后 ➔ 分块数: {len(initial_docs)}")
            _log_metadata_distribution(initial_docs, meta_counter, logger)

        # Step 3: 动态字符分块
        logger.debug(f"执行字符级分块 (chunk_size={chunk_size}, overlap={chunk_overlap})")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            is_separator_regex=False,
            keep_separator=True
        )
        final_docs = []
        for doc in initial_docs:
            chunks = text_splitter.split_documents([doc])
            final_docs.extend(chunks)
        logger.info(f"字符分块完成 ➔ 总块数: {len(final_docs)}")
        _log_size_distribution(final_docs, logger)

        # Step 4: 处理过短块
        if min_chunk_size is not None:
            original_count = len(final_docs)
            final_docs = _merge_short_chunks(final_docs, min_chunk_size)
            logger.info(
                f"合并短块完成 (阈值: {min_chunk_size}字符) ➔ "
                f"减少块数: {original_count} → {len(final_docs)}"
            )
            _log_size_distribution(final_docs, logger)

        # 最终统计
        logger.info(
            f"✅ 处理完成 ➔ 总输出块数: {len(final_docs)} | "
            f"平均长度: {sum(len(d.page_content) for d in final_docs)//len(final_docs)}字符"
        )
        return final_docs

    except Exception as e:
        logger.error(f"分块处理失败: {str(e)}", exc_info=True)
        raise  # 保持任务状态为失败

def _core_split_markdown_by_headers(
    content: str,
    headers_to_split_on: List[Tuple[str, str]],
    chunk_size: int,
    chunk_overlap: int,
    min_chunk_size: Optional[int],
    strip_headers: bool,
    sub_headers: Optional[List[Tuple[str, str]]],
    sub_split_threshold: int,
    logger
) -> List[Document]:
    """Core logic for splitting markdown by headers."""
    try:
        meta_counter = defaultdict(int)
        logger.debug(f"原始内容长度: {len(content)} 字符")
        logger.info("开始标题层级分块处理...")

        logger.debug("执行基础标题分割...")
        header_splitter = MarkdownHeaderTextSplitter( # Assuming MarkdownHeaderTextSplitter is defined in the same module or imported
            headers_to_split_on=headers_to_split_on,
            strip_headers=strip_headers
        )
        # MarkdownHeaderTextSplitter.split_text is a task, we need to call its core logic
        # For now, let's assume it's refactored to have a _core_split_text or similar
        # If MarkdownHeaderTextSplitter instance is created here, we'd call its core method.
        # This example assumes direct call to a non-task version or that the task itself is fine if it calls a core method.
        # For the purpose of this refactor, if header_splitter.split_text is a task, this indicates
        # _core_split_markdown_by_headers is an orchestrator of tasks rather than pure logic.
        # However, the instruction is to extract *this* function's core logic.
        # So, we'll assume header_splitter.split_text can be treated as a utility call here.
        initial_docs = header_splitter.split_text(content) # If this is a task, this core function is an orchestrator.
                                                            # If it's a non-task method, it's fine.

        logger.info(f"基础分割完成 ➔ 初始分块数: {len(initial_docs)}")
        _log_metadata_distribution(initial_docs, meta_counter, logger)

        if sub_headers:
            logger.debug(
                f"启用子标题二次分割 (阈值: {sub_split_threshold}字符)",
                # sub_headers=str(sub_headers) # Logger does not take sub_headers as kwarg
            )
            initial_docs = _split_with_sub_headers( # This is a local helper, not a task
                initial_docs, sub_headers, sub_split_threshold, 
                strip_headers, headers_to_split_on
            )
            logger.info(f"子标题分割后 ➔ 分块数: {len(initial_docs)}")
            _log_metadata_distribution(initial_docs, meta_counter, logger)

        logger.debug(f"执行字符级分块 (chunk_size={chunk_size}, overlap={chunk_overlap})")
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            length_function=len,
            is_separator_regex=False,
            keep_separator=True
        )
        final_docs = []
        for doc in initial_docs:
            chunks = text_splitter.split_documents([doc])
            final_docs.extend(chunks)
        logger.info(f"字符分块完成 ➔ 总块数: {len(final_docs)}")
        _log_size_distribution(final_docs, logger)

        if min_chunk_size is not None:
            original_count = len(final_docs)
            final_docs = _merge_short_chunks(final_docs, min_chunk_size) # local helper
            logger.info(
                f"合并短块完成 (阈值: {min_chunk_size}字符) ➔ "
                f"减少块数: {original_count} → {len(final_docs)}"
            )
            _log_size_distribution(final_docs, logger)

        logger.info(
            f"✅ 处理完成 ➔ 总输出块数: {len(final_docs)} | "
            f"平均长度: {sum(len(d.page_content) for d in final_docs)//len(final_docs) if final_docs else 0}字符"
        )
        return final_docs
    except Exception as e:
        logger.error(f"分块处理失败: {str(e)}", exc_info=True)
        raise

@task(name="split_markdown_by_headers")
def split_markdown_by_headers(
    content: str,
    headers_to_split_on: List[Tuple[str, str]],
    chunk_size: int = 1000,
    chunk_overlap: int = 200,
    min_chunk_size: Optional[int] = 50,
    strip_headers: bool = False,
    sub_headers: Optional[List[Tuple[str, str]]] = None,
    sub_split_threshold: int = 800
) -> List[Document]:
    logger = get_run_logger()
    return _core_split_markdown_by_headers(
        content, headers_to_split_on, chunk_size, chunk_overlap,
        min_chunk_size, strip_headers, sub_headers, sub_split_threshold, logger
    )

def _core_split_markdown_semantic(
    base_docs: List[Document],
    final_chunk_size: int,
    final_chunk_overlap: int,
    semantic_threshold_type: str,
    semantic_threshold: float,
    semantic_window_size: int,
    keep_markdown_format: bool,
    final_min_size: int,
    embedding_model_name: str, # Changed from ollama_model
    ollama_base_url: str,
    logger
) -> List[Document]:
    """Core logic for semantic markdown splitting."""
    try:
        logger.info(f"初始块数: {len(base_docs)}")

        logger.info(f"初始化Ollama嵌入模型 (Model: {embedding_model_name}, Base URL: {ollama_base_url})...")
        embeddings = OllamaEmbeddings(
            model=embedding_model_name, # Use new parameter name
            base_url=ollama_base_url,   # Use passed base_url
        )

        semantic_chunker = SemanticChunker(
            embeddings=embeddings,
            buffer_size=semantic_window_size,
            breakpoint_threshold_type=semantic_threshold_type,
            breakpoint_threshold_amount=semantic_threshold,
            min_chunk_size=final_min_size
        )
        semantic_docs = semantic_chunker.split_documents(base_docs)
        logger.info(f"语义分块完成 ➔ 块数: {len(semantic_docs)}")

        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=final_chunk_size,
            chunk_overlap=final_chunk_overlap,
            length_function=len,
            is_separator_regex=False,
            keep_separator=keep_markdown_format
        )
        processed_docs = []
        for doc in semantic_docs:
            chunks = text_splitter.split_documents([doc])
            processed_docs.extend(chunks)
        
        final_docs = []
        current_chunk = None
        for doc in processed_docs:
            doc_size = len(doc.page_content)
            if doc_size >= final_min_size:
                if current_chunk:
                    final_docs.append(current_chunk)
                    current_chunk = None
                final_docs.append(doc)
            else:
                if current_chunk:
                    current_chunk.page_content += "\n" + doc.page_content
                    current_chunk.metadata.update(doc.metadata)
                    if len(current_chunk.page_content) >= final_min_size:
                        final_docs.append(current_chunk)
                        current_chunk = None
                else:
                    current_chunk = Document(
                        page_content=doc.page_content,
                        metadata=doc.metadata.copy()
                    )
        if current_chunk:
            final_docs.append(current_chunk)
        return final_docs
    except Exception as e:
        logger.error(f"分块流程异常: {str(e)}", exc_info=True)
        raise

@task(name="split_markdown_semantic")
def split_markdown_semantic(
    base_docs: List[Document],
    final_chunk_size: int = 1000,
    final_chunk_overlap: int = 150,
    semantic_threshold_type: str = "percentile",
    semantic_threshold: float = 0.85,
    semantic_window_size: int = 3,
    keep_markdown_format: bool = True,
    final_min_size: int = 150,
    embedding_model_name: Optional[str] = None, # Changed, allow None
    ollama_base_url: Optional[str] = None,    # Allow None
    config_path: str = "config/settings.yaml" # Path to settings config
) -> List[Document]:
    """
    全参数语义分块任务（集成标题分块功能）
    (Prefect task wrapper)
    """
    logger = get_run_logger()

    cfg_loader = ConfigLoader(config_path)
    _ollama_base_url = ollama_base_url or cfg_loader.get_config("services.ollama.base_url")
    # Use semantic_chunker_embedding_model from config
    _embedding_model_name = embedding_model_name or cfg_loader.get_config("services.ollama.semantic_chunker_embedding_model")

    if not _ollama_base_url:
        raise ValueError("Ollama base URL must be provided or configured in settings.yaml.")
    if not _embedding_model_name:
        raise ValueError("Embedding model name must be provided or configured as semantic_chunker_embedding_model in settings.yaml.")

    return _core_split_markdown_semantic(
        base_docs, final_chunk_size, final_chunk_overlap,
        semantic_threshold_type, semantic_threshold, semantic_window_size,
        keep_markdown_format, final_min_size, 
        embedding_model_name=_embedding_model_name, # Pass resolved name
        ollama_base_url=_ollama_base_url,       # Pass resolved URL
        logger=logger
    )
def _log_metadata_distribution(docs: List[Document], counter: dict, logger):
    """记录元数据层级分布"""
    for doc in docs:
        level = len(doc.metadata)
        counter[level] += 1
    logger.debug(
        "元数据层级分布:\n" + 
        "\n".join([f"  L{level}: {count} 块" for level, count in counter.items()])
    )

def _log_size_distribution(docs: List[Document], logger):
    """记录块大小分布"""
    sizes = [len(d.page_content) for d in docs]
    logger.debug(
        "块大小统计 ➔ "
        f"最小: {min(sizes)} | 最大: {max(sizes)} | 平均: {sum(sizes)//len(sizes)}"
    )


def _split_with_sub_headers(
    docs: List[Document],
    sub_headers: List[Tuple[str, str]],
    threshold: int,
    strip_headers: bool,
    headers_to_split_on: List[Tuple[str, str]]
) -> List[Document]:
    """修复：确保父级标题元数据正确传递"""
    processed = []
    for doc in docs:
        if len(doc.page_content) < threshold:
            processed.append(doc)
            continue

        parent_meta = doc.metadata
        parent_symbols = []
        
        # 通过元数据键反向查找标题符号（例如 H1 -> #）
        for h_symbol, h_key in headers_to_split_on:
            if h_key in parent_meta:
                parent_symbols.append( (h_symbol, h_key) )
        
        # 组合父级标题 + 子标题
        combined_headers = parent_symbols + sub_headers
        
        # 去重并保留顺序（确保层级正确）
        seen = set()
        unique_headers = []
        for h in combined_headers:
            if h[0] not in seen:
                seen.add(h[0])
                unique_headers.append(h)
        
        # 执行分割
        splitter = MarkdownHeaderTextSplitter(
            headers_to_split_on=unique_headers,
            strip_headers=strip_headers
        )
        sub_docs = splitter.split_text(doc.page_content)
        
        # 合并元数据（保留所有父级信息）
        for sub_doc in sub_docs:
            merged_meta = {**parent_meta}
            # 仅添加子级中更底层的元数据
            for k, v in sub_doc.metadata.items():
                if k not in merged_meta or int(k[1:]) > int(list(merged_meta.keys())[-1][1:]):
                    merged_meta[k] = v
            processed.append(Document(
                page_content=sub_doc.page_content,
                metadata=merged_meta
            ))
    
    return processed

def _merge_short_chunks(docs: List[Document], min_size: int) -> List[Document]:
    """修复：仅合并相同层级的短块"""
    processed = []
    buffer = None
    last_hierarchy = None  # 改为记录缓冲区层级

    for doc in docs:
        doc_size = len(doc.page_content)
        current_hierarchy = tuple(sorted(doc.metadata.keys(), key=lambda x: int(x[1:])))  # H1 < H2 < H3
        
        # 核心修复点：只有当层级相同且是短块时才合并
        if buffer is not None:
            if (
                doc_size < min_size 
                and current_hierarchy == last_hierarchy  # 层级相同才合并
            ):
                # 合并内容
                merged_content = buffer.page_content + "\n" + doc.page_content
                # 合并元数据（保留所有层级的原始值）
                merged_meta = {**buffer.metadata, **doc.metadata}
                buffer = Document(
                    page_content=merged_content,
                    metadata=merged_meta
                )
                continue
            else:
                # 提交缓冲区内容
                processed.append(buffer)
                buffer = None
        
        # 新块处理
        if doc_size < min_size:
            buffer = doc
            last_hierarchy = current_hierarchy
        else:
            processed.append(doc)
    
    # 处理最后缓冲区
    if buffer is not None:
        processed.append(buffer)
    
    return processed
