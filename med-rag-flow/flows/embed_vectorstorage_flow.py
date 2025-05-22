from pathlib import Path
from datetime import datetime
from typing import Dict, List
import sys

from prefect import flow, get_run_logger, task
# ------------------------ 本地模块导入 ------------------------
# 添加项目根目录到系统路径（兼容测试环境）
current_dir = Path(__file__).parent
src_dir = current_dir.parent if current_dir.name == 'flows' else current_dir
sys.path.append(str(src_dir))

from tasks.chunking.markdown_hybrid_chunk import MarkdownHeaderTextSplitter
from tasks.chunking.markdown_hybrid_chunk import Chunk
from tasks.embedding.embed_task import VectorStoreManager
from typing import Dict, List, Optional, Union
from langchain.schema import Document

from tasks.chunking.markdown_semantic_chunk import split_markdown_by_headers, split_markdown_semantic
from tasks.chunking.markdown_propositions_chunk import propositions

from pathlib import Path
from typing import Union, List, Dict, Optional


@flow(name="process_and_store_directory")
def process_and_store_directory(
    content_source: Union[str, Path, List[Document]],
    config: Dict,
    processor_type: str = "header",
    processor_params: Optional[Dict] = None,
    recursive: bool = True,
    file_extensions: List[str] = [".md", ".markdown"],
    **kwargs
) -> Optional[VectorStoreManager]:
    """
    增强版文档处理与存储管道（支持目录输入）
    
    Args:
        content_source: 输入源，支持以下类型：
            - str/Path: 文件路径或目录路径
            - List[Document]: 预处理文档列表
        config: 向量存储配置
        processor_type: 处理器类型（header/semantic/custom）
        processor_params: 分块处理器专用参数
        recursive: 是否递归搜索子目录（默认True）
        file_extensions: 处理的文件扩展名（默认[.md, .markdown]）
        ​**kwargs: 通用参数（chunk_size等）

    Returns:
        VectorStoreManager实例或None
    """
    logger = get_run_logger()
    processor_params = processor_params or {}
    
    try:
        # 输入处理
        if isinstance(content_source, (str, Path)):
            path = Path(content_source)
            
            if path.is_dir():
                logger.info(f"开始处理目录: {path.resolve()}")
                docs = _load_markdown_from_directory(
                    path, 
                    recursive=recursive,
                    extensions=file_extensions
                )
                if not docs:
                    logger.error("目录中未找到Markdown文件")
                    return None
            elif path.is_file():
                logger.info(f"处理单个文件: {path.name}")
                docs = _load_single_file(path)
            else:
                raise ValueError(f"路径不存在: {path}")
        elif isinstance(content_source, list):
            logger.info(f"接收预处理文档: {len(content_source)} 个")
            docs = content_source
        else:
            raise TypeError("不支持的输入类型")

        # 分块处理
        processed_docs = _dispatch_processor(
            docs,
            processor_type,
            {**processor_params, **kwargs}
        )

        # 存储处理
        if not processed_docs:
            logger.error("分块结果为空")
            return None

        manager = VectorStoreManager(config, processed_docs)
        logger.info(f"存储成功 ➔ {manager.get_store_info()}")
        return manager

    except Exception as e:
        logger.error(f"处理失败: {str(e)}", exc_info=True)
        return None
      
@task
def _load_single_file(file_path: Path) -> List[Document]:
    """加载单个文件"""
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()
    return [Document(
        page_content=content,
        metadata={"source": str(file_path)}
    )]

@task
def _load_markdown_from_directory(
    dir_path: Path,
    recursive: bool = True,
    extensions: List[str] = [".md", ".markdown"]
) -> List[Document]:
    """从目录加载所有Markdown文件（最终修复版）"""
    logger = get_run_logger()
    docs = []
    
    # 验证目录有效性
    if not dir_path.exists():
        logger.error(f"目录不存在: {dir_path.resolve()}")
        return docs
    if not dir_path.is_dir():
        logger.error(f"路径不是目录: {dir_path.resolve()}")
        return docs
    
    # 预处理扩展名（去重+小写+补点）
    processed_exts = list({
        f".{ext.strip('.').lower()}"  # 统一为小写带点格式
        for ext in extensions if ext.strip()
    })
    logger.info(f"开始扫描: {dir_path.resolve()} | 扩展名: {processed_exts} | 递归: {recursive}")

    try:
        # 使用正确的递归方法
        if recursive:
            all_files = dir_path.rglob("*")  # 递归遍历所有文件
        else:
            all_files = dir_path.glob("*")   # 仅当前目录

        # 过滤目标文件
        matched_files = (
            f for f in all_files
            if f.is_file() 
            and f.suffix.lower() in processed_exts
        )

        # 处理文件
        file_count = 0
        for file_path in matched_files:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content = f.read()
                    docs.append(Document(
                        page_content=content,
                        metadata={
                            "source": str(file_path.resolve()),
                            "filename": file_path.name,
                            "extension": file_path.suffix,
                            "last_modified": file_path.stat().st_mtime
                        }
                    ))
                    file_count += 1
                    logger.debug(f"已加载: {file_path.name}")
            except UnicodeDecodeError:
                logger.warning(f"解码失败（可能为二进制文件）: {file_path}")
            except Exception as e:
                logger.warning(f"文件读取错误: {file_path} - {str(e)}")

        # 结果报告
        logger.info(f"扫描完成 ➔ 找到 {file_count} 个匹配文件")
        if file_count == 0:
            logger.warning("未找到文件可能原因:"
                          "\n1. 文件扩展名未在列表中（当前允许: {})"
                          "\n2. 文件权限不足"
                          "\n3. 目录为空".format(processed_exts))
        return docs

    except Exception as e:
        logger.error(f"目录遍历失败: {str(e)}")
        return []

def _dispatch_processor(
    docs: List[Document],
    processor_type: str,
    params: Dict
) -> List[Document]:
    """分块处理器路由"""
    processor_map = {
        "header": _process_header_based,
        "semantic": _process_semantic_base,
        "header_hybrid": _process_header_hybrid,
        "header_hybrid_semantic": _process_header_hybrid_semantic,
        "propositions": _process_propositions,
    }
    
    if processor_type not in processor_map:
        raise ValueError(f"未知处理器类型: {processor_type}")
    
    return processor_map[processor_type](docs, params)

def _process_header_based(
    docs: List[Document],
    params: Dict
) -> List[Document]:
    """标题分块处理管道"""
    processed_docs = []
    
    # 独立处理每个文档
    for doc in docs:
        # 保留原始元数据
        original_meta = doc.metadata.copy()
        
        # 执行分块处理
        chunks = split_markdown_by_headers(
            content=doc.page_content,
            headers_to_split_on=params.get("headers_to_split_on", [("#", "H1"),("##", "H2"),("###", "H3")]),
            chunk_size=params.get("chunk_size", 1000),
            chunk_overlap=params.get("chunk_overlap", 200),
            sub_headers=params.get("sub_headers", [("####", "H4")]),
            sub_split_threshold=params.get("sub_split_threshold", 800)
        )
        
        # 正确合并：分块元数据优先，原始元数据作为补充
        for chunk in chunks:
            chunk.metadata = {**original_meta, **chunk.metadata}
        
        processed_docs.extend(chunks)
    
    return processed_docs

def _process_semantic(
    docs: List[Document],
    params: Dict
) -> List[Document]:
    """语义分块处理管道"""
    return split_markdown_semantic(
        base_docs=docs,
        final_chunk_size=params.get("chunk_size", 1000),
        final_chunk_overlap=params.get("chunk_overlap", 150),
        semantic_threshold_type=params.get("semantic_threshold_type", "percentile"),
        semantic_threshold=params.get("semantic_threshold", 0.85),
        ollama_model=params.get("ollama_model", "bge-m3:latest")
    )

def _process_semantic_base(
    docs: List[Document],
    params: Dict
) -> List[Document]:
    """混合分块处理管道"""
    # 第一级：标题分块
    header_docs = _process_header_based(docs, params)
    
    # 第二级：语义优化
    return _process_semantic(header_docs, params)


def _process_header_hybrid_semantic(
    docs: List[Document],
    params: Dict
) -> List[Document]:
    """混合分块处理管道"""
    # 第一级：标题分块
    header_docs = _process_header_hybrid(docs, params)
    
    # 第二级：语义优化
    return _process_semantic(header_docs, params)
  
  
def _process_propositions(
    docs: List[Document],
    params: Dict
) -> List[Document]:
    """混合分块处理管道"""
    # 第一级：标题分块
    header_docs = _process_header_hybrid(docs, params)
    
    # 第二级：语义优化
    return propositions(header_docs,model=params.get("ollama_model", "deepseek-r1:1.5b"))

  
def _process_header_hybrid(
    docs: List[Document],
    params: Dict
) -> List[Document]:
    """混合分块处理管道"""
    
    """标题分块处理管道"""
    processed_docs = []
    
    # 独立处理每个文档
    for doc in docs:
        # 保留原始元数据
        original_meta = doc.metadata.copy()
        
        # 执行分块处理
        splitter = MarkdownHeaderTextSplitter(
            chunk_size=params.get("chunk_size", 1000),
        )
        chunks = splitter.split_text(doc.page_content)
        
        # 转换文档格式
        documents = Chunk.chunks_to_documents(chunks)
        
        # 正确合并：分块元数据优先，原始元数据作为补充
        for chunk in documents:
            chunk.metadata = {**original_meta, **chunk.metadata}
        
        processed_docs.extend(documents)
    
    return processed_docs


if __name__ == '__main__':
    # 配置参数
    CONFIG = {
        "models": {
            "name": "bge-m3:latest",
            "base_url": "http://127.0.0.1:11434"
        },
        "vector_store": {
            "base_path": "../data/vectorstorage",
            "naming_template": "vec_{model_hash}_{doc_hash}"
        }
    }

    # 测试案例配置
    TEST_CASES = [
        {
            "path": "../data/output/markdown/test01/RevolutionMaximaUserManualCN453-454.md",  # 单个文件测试
            "processor_type": "header",
            "params": {
                "headers_to_split_on": [("#", "H1"), ("##", "H2")],
                "chunk_size": 800
            }
        },
        {
            "path": "./",  # 目录测试
            "processor_type": "semantic",
            "params": {
                "chunk_size": 1000,
                "semantic_threshold": 0.9
            }
        },
        {
            "path": "../data/output/markdown/test02",  # 目录测试
            "processor_type": "header_hybrid",
            "params": {
                "chunk_size": 1000,
                "semantic_threshold": 0.9
            }
        },
        {
            "path": "../data/output/markdown/test02",  # 目录测试
            "processor_type": "header_hybrid_semantic",
            "params": {
                "chunk_size": 1000,
                "semantic_threshold": 0.9
            }
        }
    ]

    for case in TEST_CASES:
        print(f"\n{'='*40}\n测试案例: {case['path']} ({case['processor_type']})\n{'='*40}")
        
        try:
            # 执行处理流程
            manager = process_and_store_directory(
                content_source=case["path"],
                config=CONFIG,
                processor_type=case["processor_type"],
                processor_params=case["params"]
            )

            # 验证结果
            if manager and manager.is_ready:
                print(f"✅ 测试成功")
                print("存储信息:", manager.get_store_info())
                print("示例文档:")
                for doc in manager.docs[:2]:
                    print(f"  - {doc.page_content[:50]}... (元数据: {doc.metadata})")
            else:
                print("❌ 测试失败：未生成有效存储")

        except Exception as e:
            print(f"❌ 测试异常: {str(e)}")
            # 特殊处理常见错误
            if "ConnectionError" in str(e):
                print("请确认 Ollama 服务已启动并运行在 127.0.0.1:11434")