"""
PDF文档批量处理系统 - 核心工作流脚本

功能特性:
1. 基于Prefect的分布式任务调度
2. 支持多级目录结构自动处理
3. 集成PDF解析与Markdown生成
4. 完善的错误处理与日志追踪
5. 并发控制与资源管理
"""

# ------------------------ 标准库导入 ------------------------
from pathlib import Path
from datetime import datetime
import re
import shutil
from typing import Dict
import sys

# ------------------------ 第三方库导入 ------------------------
import requests
from prefect import flow, get_run_logger
from prefect.task_runners import ConcurrentTaskRunner
# ------------------------ 编码强制设置 ------------------------
import sys
import os

# 启用Python UTF-8模式（兼容性最佳方案）
os.environ["PYTHONUTF8"] = "1"
os.environ["PYTHONIOENCODING"] = "utf-8"

# 重载标准输出流的编码配置
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
# ------------------------ 本地模块导入 ------------------------
# 添加项目根目录到系统路径（兼容测试环境）
current_dir = Path(__file__).parent
src_dir = current_dir.parent if current_dir.name == 'flows' else current_dir
sys.path.append(str(src_dir))

from utils.str_utils import optimize_str
from tasks.doc_task.base_task import convert_paths, validate_input_dir, collect_all_pdf_files, analyze_results, perform_cleanup, get_subdirectories # Specific imports
from tasks.doc_task.process_pdf_task import process_pdf_file # Assuming mineru_process_pdf_flow is intended to be process_pdf_file or similar
from utils.file_utils import ensure_directory
from flows.embed_vectorstorage_flow import process_and_store_directory
# from flows.test_flow import my_flow # Assuming my_flow is not used, remove if not
from med_rag_flow.utils.config_loader import ConfigLoader # Import ConfigLoader

# ------------------------ 全局配置 (Removed, will be loaded from config or passed as params) ------------------------
# DEFAULT_INPUT_DIR = Path("data/raw/pdf")
# DEFAULT_OUTPUT_DIR = Path("data/processed")
# FINAL_OUTPUT_DIR = Path("data/output/markdown")
# MAX_CONCURRENCY = 4 # Will be loaded from config if needed by a component
# SAFE_MODE = True    # Will be loaded from config if needed by a component


# ------------------------ 主工作流 ------------------------
@flow(
    name="pdf_to_markdown",
    description="PDF批量处理主流程｜含多级目录支持与智能重试机制",
    # task_runner=ConcurrentTaskRunner() # Example: if MAX_CONCURRENCY was for this flow
)
def pdf_to_markdown(
    input_dir: str,
    output_root: str,
    final_output_dir: str,
    kb_id: int,
    image_path: str, # This is for storing extracted images from PDFs, to be served
    config_file_path: str = "config/settings.yaml" # Allow overriding config path
) -> Dict:
    """
    PDF文档处理全流程控制器
    """
    logger = get_run_logger()
    cfg_loader = ConfigLoader(config_file_path)

    # Load configurations
    # safe_mode = cfg_loader.get_config("flows.document_processing.safe_mode", True) # Example if SAFE_MODE was used
    # max_concurrency could be used to configure a task runner if needed
    # max_concurrency_val = cfg_loader.get_config("flows.document_processing.max_concurrency", 4) # Example
    
    frontend_base_url = cfg_loader.get_config("services.frontend_app.base_url", "http://localhost:9090")
    ollama_base_url = cfg_loader.get_config("services.ollama.base_url", "http://localhost:11434")
    default_embedding_model = cfg_loader.get_config("services.ollama.default_embedding_model", "bge-m3:latest")
    vector_store_base_path = cfg_loader.get_config("data_paths.vector_store_base", "/app/server/med_rag_server/vectorstorage")


    try:
        # ====================== 前置清理阶段 ======================
        logger.info("🧹 初始化目录清理...")
        dirs_to_clean = [
            Path(output_root),
            Path(final_output_dir),
            Path(image_path)
        ]
        
        for dir_path in dirs_to_clean:
            if dir_path.exists():
                logger.warning(f"⚠️ 正在强制清理目录: {dir_path}")
                shutil.rmtree(dir_path, ignore_errors=False)
                dir_path.mkdir(parents=True, exist_ok=True)
                logger.debug(f"✅ 已重建目录: {dir_path}")
            else:
                logger.debug(f"⏩ 目录不存在无需清理: {dir_path}")

        # ====================== 阶段0：路径预处理 ======================
        logger.debug("🔄 正在规范化路径结构...")
        input_path, output_path = convert_paths(input_dir, output_root)
        final_output_path = Path(final_output_dir).resolve()
        
        # ====================== 阶段0_1：目录验证 ======================
        logger.info("🔍 执行目录完整性检查...")
        validated_dir = validate_input_dir(input_path)
        ensure_directory(output_path)
        ensure_directory(final_output_path)
        
        # ====================== 阶段3：文件收集 ======================
        logger.debug("📂 扫描目录结构...")
        # subdirs = get_subdirectories(validated_dir)
        subdirs = [validated_dir]
        pdf_files = collect_all_pdf_files(subdirs)
        logger.info(f"✅ 发现 {len(pdf_files)} 个待处理文件")
        
        # ====================== 阶段4：并行处理 ======================
        logger.info("🚀 启动文档处理引擎...")
        processing_results = mineru_process_pdf_flow(
            pdf_files, 
            validated_dir, 
            output_path,
            final_output_path
        )
        
        # ====================== 阶段5：结果分析 ======================
        logger.info("📊 生成处理报告...")
        result_stats = analyze_results(processing_results)
        
        # ====================== 阶段6：资源清理 ======================
        # Example of using a loaded config value, if SAFE_MODE was used by this flow's logic
        # safe_mode_for_cleanup = cfg_loader.get_config("flows.document_processing.safe_mode", True)
        # if not safe_mode_for_cleanup:
        #     logger.warning("⚠️ 安全模式已关闭，执行清理操作")
        #     perform_cleanup(output_path) # perform_cleanup needs to be defined or imported
            
        # ====================== 阶段7：复制图片目录到服务器 ======================
        logger.info("🖼️ 开始复制图片目录到服务器...")
        image_subdirs = get_subdirectories(validate_input_dir(output_root))
        copied_dirs = []
        error_logs = []

        # 确保目标目录存在
        ensure_directory(Path(image_path))

        for src_dir in image_subdirs:
            dest_dir = Path(image_path) / src_dir.name
            try:
                # 覆盖式复制目录（需要Python 3.8+）
                shutil.copytree(
                    src_dir, 
                    dest_dir,
                    dirs_exist_ok=True
                )
                copied_dirs.append(str(dest_dir))
                logger.debug(f"✅ 成功复制目录: {src_dir.name} -> {dest_dir}")
            except Exception as e:
                error_msg = f"目录复制失败 [{src_dir.name}]: {str(e)}"
                error_logs.append(error_msg)
                logger.error(error_msg, exc_info=True)

        logger.info(f"📦 完成目录复制：{len(copied_dirs)}成功 / {len(error_logs)}失败")
        
        # Use configured frontend_base_url
        image_base_url_for_markdown = f'{frontend_base_url}/static/images/{kb_id}'
        for md_file in final_output_path.rglob('*.md'):
            try:
                replace_image_paths(md_file, image_base_url_for_markdown) # replace_image_paths needs to be defined/imported
            except Exception as e:
                logger.error(f"文件处理失败 [{md_file.name}]: {str(e)}", exc_info=True)
      
        # ====================== 阶段8：分块文档并得到嵌入数据库 ======================
        logger.info("🧠 启动知识库嵌入流程...")
        try:
            # 配置向量存储参数 using loaded configurations
            embed_config = {
                "models": {
                    "name": default_embedding_model, # Use loaded default
                    "base_url": ollama_base_url      # Use loaded default
                },
                "vector_store": {
                    "base_path": vector_store_base_path, # Use loaded default
                    "naming_template": f"kb_{kb_id}_" + "{model_hash}_{doc_hash}"
                }
            }

            # 执行嵌入流程
            vector_manager = process_and_store_directory(
                content_source=final_output_path,
                config=embed_config,
                processor_type="header_hybrid",
                processor_params={
                    "chunk_size": 1500,
                    "semantic_threshold": 0.85
                },
                recursive=True
            )

            # 结果处理与状态更新
            if vector_manager and vector_manager.is_ready:
                logger.info(f"📚 知识库构建成功 ➔ {vector_manager.get_store_info()}")
                result_stats["vector_store"] = {
                    "base_path": vector_manager.vector_store_path,
                    "model": embed_config["models"]["name"],
                    "doc_count": len(vector_manager.docs)
                }
                process_status = "completed"
                vector_path = vector_manager.vector_store_path  # 获取实际存储路径
            else:
                logger.error("知识库构建失败")
                result_stats["vector_store"] = None
                process_status = "failed"
                vector_path = None

            # 调用双接口更新（新增部分）
            # Use configured frontend_base_url for api_base
            api_base_url_for_kb = f"{frontend_base_url}/api/knowledge-bases"
            headers = {"Content-Type": "application/json"}
            
            try:
                # 第一步：更新处理状态
                status_response = requests.patch(
                    f"{api_base_url_for_kb}/{kb_id}/processing-status",
                    json={"processing_status": process_status},
                    headers=headers,
                    timeout=10 # Consider making timeout configurable
                )
                
                if status_response.status_code != 200:
                    logger.error(f"状态更新失败: {status_response.text}")

                # 第二步：成功时更新路径
                if process_status == "completed" and vector_manager.vector_store_path_name:
                    path_response = requests.patch(
                        f"{api_base_url_for_kb}/{kb_id}/vector-path",
                        json={"vector_storage_path": vector_manager.vector_store_path_name},
                        headers=headers,
                        timeout=20 # Consider making timeout configurable
                    )
                    
                    if path_response.status_code == 200:
                        logger.info(f"✅ 向量路径更新成功: {vector_manager.vector_store_path_name}")
                    else:
                        logger.error(f"路径更新失败: {path_response.text}")

            except Exception as api_error:
                logger.error(f"API通信异常: {str(api_error)}", exc_info=True)

        except Exception as e:
            logger.error(f"向量存储创建失败: {str(e)}", exc_info=True)
            result_stats["vector_store"] = None
            
            # 异常情况仅更新状态
            # Ensure api_base_url_for_kb is defined in this scope for exception handling too
            api_base_url_for_kb_exc = f"{frontend_base_url}/api/knowledge-bases"
            try:
                requests.patch(
                    f"{api_base_url_for_kb_exc}/{kb_id}/processing-status", # Use defined var
                    json={"processingStatus": "failed"}, # Ensure consistent key ("processing_status" vs "processingStatus")
                    headers=headers, # headers should be defined
                    timeout=5 # Consider making timeout configurable
                )
            except Exception as ex:
                logger.error(f"异常状态更新失败: {str(ex)}")

        finally:
            # 最终资源清理（可选）
            pass
        
        
    except Exception as e:
        logger.critical(f"‼️ 关键系统故障: {type(e).__name__}", exc_info=True)
        raise RuntimeError("批处理流程异常终止") from e

@task
def replace_image_paths(md_file: Path, replace_path: str) -> bool:
    """
    安全替换单个Markdown文件的图片路径
    :param md_file: Markdown文件路径
    :param replace_path: 替换的基础URL
    :return: 是否成功替换
    """
    logger = get_run_logger()
    
    try:
        # 读取文件内容
        with open(md_file, 'r', encoding='utf-8') as f:
            content = f.read()
        
        modified = False
        new_lines = []
        
        for line in content.split('\n'):
            # 仅处理包含图片的行
            if line.startswith('![') and 'images_' in line:
                # 定位关键分隔符
                bracket_pos = line.find('](')
                images_pos = line.find('images_')
                
                if bracket_pos != -1 and images_pos > bracket_pos:
                    # 提取图片描述和文件名
                    desc_part = line[:bracket_pos+2]
                    file_part = line[images_pos:]
                    
                    # 构建新路径（确保URL格式正确）
                    new_url = f"{replace_path.rstrip('/')}/{file_part}"
                    new_line = f"{desc_part}{new_url}"
                    
                    new_lines.append(new_line)
                    modified = True
                    logger.debug(f"替换成功 | 文件: {md_file.name}")
                    continue
            
            new_lines.append(line)
        
        # 写回修改内容
        if modified:
            with open(md_file, 'w', encoding='utf-8') as f:
                f.write('\n'.join(new_lines))
            return True
        return False
        
    except Exception as e:
        logger.error(f"文件处理失败 [{md_file.name}]: {str(e)}", exc_info=True)
        return False


# ------------------------ MinerU 处理PDF的流程 ------------------------
@flow(name="mineru_process_pdf_flow")
def mineru_process_pdf_flow(
    pdf_file_groups: List[Dict[str, Any]], 
    input_dir: Path, 
    output_root: Path,
    final_output_path: Path
) -> List[Dict]:
    """批量文件处理任务（结构化版本）
    
    参数:
        pdf_file_groups: 结构化PDF文件列表，每个元素包含:
            {
                "path": 原始子目录路径,
                "files": 该目录下的PDF文件列表
            }
        input_dir: 输入根目录
        output_root: 中间输出根目录
        final_output_path: 最终输出根目录
        
    返回:
        处理结果列表，每个元素包含:
            {
                "original_path": 原始子目录路径,
                "output_path": 输出子目录路径,
                "final_output_path": 最终输出子目录路径,
                "processed_files": 处理成功的文件列表,
                "failed_files": 处理失败的文件列表
            }
    """
    logger = get_run_logger()
    try:
        results = []
        for group in pdf_file_groups:
            original_subdir = group["path"]
            files = group["files"]
            
            # 计算对应的输出子目录路径
            relative_path = original_subdir.relative_to(input_dir)
            output_subdir = output_root / relative_path
            final_output_subdir = final_output_path / relative_path
            
            processed = []
            failed = []
            
            for pdf in files:
                try:
                    result = process_pdf_file.submit(
                        pdf_file=pdf,
                        input_dir=input_dir,
                        output_root=output_root,
                        final_output_dir=final_output_subdir
                    ).result()
                    processed.append(result)
                except Exception as e:
                    logger.warning(f"文件处理失败: {pdf} - {str(e)}")
                    failed.append({
                        "file": pdf,
                        "error": str(e)
                    })
            
            results.append({
                "original_path": original_subdir,
                "output_path": output_subdir,
                "final_output_path": final_output_subdir,
                "processed_files": processed,
                "failed_files": failed
            })
            
            logger.info(
                f"处理完成 - 原始目录: {original_subdir}\n"
                f"中间输出: {output_subdir}\n"
                f"最终输出: {final_output_subdir}\n"
                f"成功: {len(processed)}, 失败: {len(failed)}"
            )
        
        return results
    except Exception as e:
        logger.error(f"批量处理失败: {str(e)}")
        raise




# ------------------------ 执行入口 ------------------------
# Entry point for serving the Prefect flow.
if __name__ == "__main__":
    """
    本地调试模式启动命令:
    python -m flows.doc_processing \
        --input_dir=data/raw/pdf \
        --output_root=data/processed \
        --final_output_dir=data/output/markdown
    """
    # 创建部署对象

    # 部署这个flow
    pdf_to_markdown.serve(name="pdf_to_markdown-deployment")
    # 原始Markdown内容示例
    # original_content = """![方程 11-1: 噪声指数因数](E:\MySpeace\med_rag\med-rag-flow\data\processed\test01\images_RevolutionMaximaUserManualCN452-454/efee5da2e6ab47efb1e95387366050513a90bebf5b164318b8b9c7b03864502c.jpg)
    # """
    # final_output_path = Path('../data/output/markdown/test01').resolve()
    # image_base_url = f'http://10.20.92.21/static/123'
    # for md_file in final_output_path.rglob('*.md'):
    #         replace_image_paths(md_file,image_base_url)
    # 替换路径前缀
    # new_content = replace_image_paths(original_content, "replace_path")
    # print(new_content)
    # result = pdf_to_markdown(
    #     input_dir="../data/raw/pdf",
    #     output_root="../data/processed",
    #     final_output_dir="../data/output/markdown"
    # )