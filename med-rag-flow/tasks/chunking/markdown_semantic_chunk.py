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


@task(name="split_markdown_semantic")
def split_markdown_semantic(
    base_docs: List[Document],
    # 字符级分块参数
    final_chunk_size: int = 1000,
    final_chunk_overlap: int = 150,
    # 语义分块参数
    semantic_threshold_type: str = "percentile",  # 可选：percentile/standard_deviation/interquartile/gradient
    semantic_threshold: float = 0.85,             # 根据类型对应不同数值范围
    semantic_window_size: int = 3,                 # 上下文分析窗口
    # 通用参数
    keep_markdown_format: bool = True,
    final_min_size: int = 150,
    # Ollama参数
    ollama_model: str = "linux6200/bge-reranker-v2-m3:latest",       # 本地部署的嵌入模型名称
    ollama_base_url: str = "http://localhost:11434"
) -> List[Document]:
    """
    全参数语义分块任务（集成标题分块功能）
    
    |‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾‾|
    | 实现策略：                                                    |
    | 1. 标题分块 → 2. 子标题优化 → 3. 语义合并 → 4. 最终精调        |
    |______________________________________________________________|
    
    Args:
        # 语义分块参数
        semantic_threshold_type: 相似度阈值类型（默认percentile）
            percentile: 百分位阈值（0-100）
            standard_deviation: 标准差倍数（建议1.5-3）
            interquartile: 四分位距倍数（建议1.5-2）
            gradient: 梯度变化百分位（0-100）
        semantic_threshold: 对应类型的阈值量（默认0.85）
        semantic_window_size: 上下文分析窗口大小（默认3句）
        # 通用参数
        keep_markdown_format: 保留Markdown格式符号（默认True）
        final_min_size: 最终最小块大小（默认150）
        # Ollama参数
        ollama_model: 本地Ollama服务部署的嵌入模型名称（默认nomic-embed-text）
        ollama_base_url: Ollama服务地址（默认http://localhost:11434）

    Returns:
        List[Document]: 结构化分块结果，每个块包含：
        - page_content: 文本内容（保留段落结构）
        - metadata: 层级标题元数据（示例：{"H1": "标题", "H2": "子标题"}）
    """
    logger = get_run_logger()
    
    try:
        logger.info(f"初始块数: {len(base_docs)}")

        # 阶段2：初始化Ollama嵌入模型
        logger.info("初始化Ollama嵌入模型...")
        embeddings = OllamaEmbeddings(
            model=ollama_model,
            base_url=ollama_base_url,
        )

        # 阶段3：语义分块
        semantic_chunker = SemanticChunker(
            embeddings=embeddings,
            buffer_size=semantic_window_size,
            breakpoint_threshold_type=semantic_threshold_type,
            breakpoint_threshold_amount=semantic_threshold,
            min_chunk_size=final_min_size
        )
        semantic_docs = semantic_chunker.split_documents(base_docs)
        logger.info(f"语义分块完成 ➔ 块数: {len(semantic_docs)}")

        # 阶段4：最终分块优化
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
        
        # 智能合并过小分块（而不是直接过滤）
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
                    # 合并内容并保留所有元数据
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
