from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Tuple
from prefect import task, get_run_logger
from pathlib import Path
from typing import Any, Dict, List, Tuple
from prefect import flow, task, get_run_logger
from utils.file_utils import (
    validate_input_directory,
    cleanup_empty_directories,
    get_first_level_subdirectories
)

# ------------------------ 基础任务 ------------------------
@task(
    name="analyze-batch-results",
    description="批量处理结果统计分析（精简版）",
    tags=["analysis", "reporting"],
)
def analyze_results(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """PDF批量处理结果分析（移除了性能监控模块）
    
    输入参数格式:
    [{
        "original_path": Path,      # 原始目录路径
        "output_path": Path,        # 中间输出目录路径  
        "final_output_path": Path,  # 最终输出目录路径
        "processed_files": List[Dict],  # 成功文件列表
        "failed_files": List[Dict]      # 失败文件列表
    }]

    返回结构:
    {
        "directory_stats": 目录级统计,
        "file_stats": 文件级统计,
        "failure_analysis": 失败分析,
        "output_structure": 输出路径样本
    }
    """
    logger = get_run_logger()
    logger.info("📊 开始精简版结果分析...")

    try:
        # ================= 目录级统计 =================
        dir_stats = {
            "total_directories": len(results),
            "fully_successful_dirs": sum(1 for r in results if not r["failed_files"]),
            "partial_success_dirs": sum(1 for r in results if r["failed_files"] and r["processed_files"]),
            "fully_failed_dirs": sum(1 for r in results if not r["processed_files"] and r["failed_files"]),
            "success_rate": f"{sum(1 for r in results if not r['failed_files']) / len(results) * 100:.1f}%" 
                          if results else "0%"
        }

        # ================= 文件级统计 ================= 
        total_files = sum(len(r["processed_files"]) + len(r["failed_files"]) for r in results)
        success_files = sum(len(r["processed_files"]) for r in results)
        
        file_stats = {
            "total_files": total_files,
            "success_files": success_files,
            "failed_files": total_files - success_files,
            "success_rate": f"{success_files / total_files * 100:.1f}%" if total_files else "0%"
        }

        # ================= 失败分析 =================
        failure_analysis = {}
        if total_files > success_files:
            all_failures = [f for r in results for f in r["failed_files"]]
            error_types = Counter(
                f.get("error", "unknown").split(":")[0].strip() 
                for f in all_failures
            )
            
            failure_analysis = {
                "top_error_types": dict(error_types.most_common(3)),
                "most_affected_directory": max(
                    results,
                    key=lambda x: len(x["failed_files"]),
                    default={"original_path": Path("N/A")}
                )["original_path"].name,
                "failure_examples": [
                    {"file": f["pdf_stem"], "error": f.get("error")} 
                    for f in all_failures[:3]
                ]
            }

        # ================= 构建报告 =================
        report = {
            "directory_stats": dir_stats,
            "file_stats": file_stats,
            "failure_analysis": failure_analysis,
            "output_structure": {
                "input_root": str(results[0]["original_path"].parent) if results else None,
                "output_root": str(results[0]["output_path"].parent) if results else None
            }
        }

        logger.info(
            f"✅ 分析完成 | 目录成功率: {dir_stats['success_rate']} | "
            f"文件成功率: {file_stats['success_rate']}"
        )
        logger.debug("关键指标:\n" + "\n".join(
            f"{k}: {v}" for k,v in report.items() 
            if k != "failure_examples"
        ))

        return report

    except Exception as e:
        logger.error(f"分析异常: {str(e)}")
        return {
            "error": str(e),
            "partial_results": {
                "processed_files": sum(len(r["processed_files"]) for r in results),
                "failed_files": sum(len(r["failed_files"]) for r in results)
            } if results else None
        }
    
@task(
    name="prepare-output-path",
    description="生成保留原始目录结构的输出路径",
    tags=["path-processing"]
)
def prepare_output_path(input_dir: Path, pdf_file: Path, output_root: Path) -> Path:
    """构建与原始目录结构匹配的输出路径
    
    Args:
        input_dir: 原始输入根目录
        pdf_file: 当前处理的PDF文件路径
        output_root: 输出根目录
        
    Returns:
        对应输入结构的输出子目录路径
        
    Raises:
        ValueError: 当文件不在输入目录下时
        PermissionError: 目录创建权限不足时
    """
    logger = get_run_logger()
    logger.info(f"📂 开始构建输出路径 | 输入文件: {pdf_file}")
    
    try:
        # 计算相对路径
        relative_path = pdf_file.relative_to(input_dir).parent
        logger.debug(f"原始路径解构成功 | 相对路径: {relative_path}")
        
        # 构建输出路径
        output_path = output_root / relative_path
        logger.info(f"目标输出路径: {output_path}")
        
        # 创建目录（包含权限验证）
        output_path.mkdir(parents=True, exist_ok=True)
        if not output_path.exists():
            raise PermissionError(f"目录创建失败: {output_path}")
            
        logger.info(f"✅ 输出路径准备完成: {output_path}")
        return output_path
        
    except ValueError as ve:
        logger.critical(f"路径计算错误: {pdf_file} 不在输入目录 {input_dir} 下")
        raise ValueError(f"文件路径越界: {pdf_file}") from ve
    except PermissionError as pe:
        logger.error(f"权限不足无法创建目录: {output_path} | 错误: {str(pe)}")
        raise
    except Exception as e:
        logger.error(f"未知路径处理错误: {str(e)}", exc_info=True)
        raise RuntimeError(f"输出路径生成失败: {pdf_file}") from e

@task(
    name="perform-cleanup",
    description="清理空目录任务",
    tags=["maintenance"]
)
def perform_cleanup(output_root: Path) -> None:
    """安全清理输出目录中的空目录
    
    Args:
        output_root: 需要清理的根目录路径
        
    Raises:
        RuntimeError: 清理过程中发生不可恢复错误时
    """
    logger = get_run_logger()
    logger.info(f"🧹 开始清理目录: {output_root}")
    
    try:
        removed_dirs = cleanup_empty_directories(output_root)
        logger.info(f"清理完成 | 移除空目录数: {len(removed_dirs)}")
        
        if removed_dirs:
            logger.debug("被清理的目录列表:\n" + "\n".join([str(p) for p in removed_dirs]))
            
    except PermissionError as pe:
        logger.error(f"目录清理权限不足: {output_root} | 错误: {str(pe)}")
    except FileNotFoundError as fnf:
        logger.warning(f"目录不存在: {output_root} | 错误: {str(fnf)}")
    except Exception as e:
        logger.error(f"清理过程发生未知错误: {str(e)}", exc_info=True)
        raise RuntimeError("目录清理失败") from e

@task(
    name="validate-input-directory",
    description="验证输入目录有效性（修复版）",
    tags=["validation"]
)
def validate_input_dir(input_dir: Path) -> Path:
    """验证输入目录是否合法可用
    
    Args:
        input_dir: 待验证的目录路径
        
    Returns:
        解析后的绝对路径
        
    Raises:
        FileNotFoundError: 目录不存在时
        NotADirectoryError: 路径不是目录时
    """
    logger = get_run_logger()
    logger.info(f"🔍 开始验证输入目录: {input_dir}")
    
    try:
        # 先解析路径确保是有效的Path对象
        input_path = Path(input_dir).resolve()
        
        # 验证目录有效性（假设validate_input_directory返回布尔值）
        if not validate_input_directory(input_path):
            raise NotADirectoryError(f"无效的目录路径: {input_path}")
            
        logger.info(f"✅ 验证通过 | 有效目录: {input_path}")
        return input_path
        
    except FileNotFoundError as fnf:
        logger.error(f"目录不存在: {input_dir}")
        raise
    except NotADirectoryError as nde:
        logger.error(f"路径不是有效目录: {input_dir}")
        raise
    except Exception as e:
        logger.error(f"目录验证异常: {str(e)}", exc_info=True)
        raise

@task(
    name="get-subdirectories",
    description="获取有效子目录列表",
    tags=["directory-processing"]
)
def get_subdirectories(parent_dir: Path) -> List[Path]:
    """获取一级有效子目录列表
    
    Args:
        parent_dir: 父目录路径
        
    Returns:
        子目录路径列表（可能为空）
        
    Raises:
        FileNotFoundError: 父目录不存在时
    """
    logger = get_run_logger()
    logger.info(f"📂 扫描子目录: {parent_dir}")
    
    try:
        dirs = get_first_level_subdirectories(parent_dir)
        
        if not dirs:
            logger.warning(f"未找到有效子目录: {parent_dir}")
        else:
            logger.info(f"找到 {len(dirs)} 个子目录 | 首个子目录: {dirs[0].name}")
            
        return dirs
        
    except FileNotFoundError as fnf:
        logger.error(f"父目录不存在: {parent_dir}")
        raise
    except Exception as e:
        logger.error(f"获取子目录失败: {str(e)}", exc_info=True)
        raise

@task(
    name="convert-paths",
    description="路径格式转换任务",
    tags=["path-processing"]
)
def convert_paths(input_dir: str, output_root: str) -> Tuple[Path, Path]:
    """将字符串路径转换为Path对象
    
    Args:
        input_dir: 输入目录字符串路径
        output_root: 输出根目录字符串路径
        
    Returns:
        (输入目录Path对象, 输出目录Path对象)
        
    Raises:
        ValueError: 路径无效时
    """
    logger = get_run_logger()
    logger.info(f"🔄 开始路径转换 | 输入: {input_dir} → 输出: {output_root}")
    
    try:
        input_path = Path(input_dir).expanduser().resolve()
        output_path = Path(output_root).expanduser().resolve()
        
        logger.debug(f"解析后路径 | 输入: {input_path} | 输出: {output_path}")
        
        if not input_path.exists():
            raise FileNotFoundError(f"输入路径不存在: {input_path}")
            
        if not output_path.exists():
            logger.warning(f"输出路径不存在，将自动创建: {output_path}")
            output_path.mkdir(parents=True, exist_ok=True)
            
        return input_path, output_path
        
    except FileNotFoundError as fnf:
        logger.error(f"路径不存在: {str(fnf)}")
        raise
    except Exception as e:
        logger.error(f"路径转换异常: {str(e)}", exc_info=True)
        raise ValueError("路径转换失败") from e

@task(
    name="collect-all-pdfs",
    description="聚合PDF文件任务",
    tags=["file-processing"],
)
def collect_all_pdf_files(subdirs: List[Path]) -> List[Dict[str, Any]]:
    """分布式收集所有PDF文件
    
    Args:
        subdirs: 待扫描的子目录列表
        
    Returns:
        结构化收集结果列表，每个元素包含：
        {
            "path": 子目录路径,
            "files": PDF文件列表,
            "count": 文件数量
        }
    """
    logger = get_run_logger()
    logger.info(f"🔍 开始全局PDF文件收集 | 待扫描目录数: {len(subdirs)}")
    
    results = []
    total_files = 0
    
    try:
        for idx, subdir in enumerate(subdirs, 1):
            logger.debug(f"正在扫描 ({idx}/{len(subdirs)}) ➔ {subdir.name}")
            
            files = collect_pdf_files(subdir)
            file_count = len(files)
            total_files += file_count
            
            results.append({
                "path": subdir,
                "files": files,
                "count": file_count
            })
            
            logger.debug(f"扫描完成 | 目录: {subdir.name} | 文件数: {file_count}")
            
        logger.info(f"✅ 文件收集完成 | 总文件数: {total_files} | 有效目录数: {len(results)}")
        return results
        
    except Exception as e:
        logger.error(f"文件收集过程异常: {str(e)}", exc_info=True)
        raise

@task(
    name="collect-pdfs",
    description="PDF文件收集子任务",
    tags=["file-processing"],
)
def collect_pdf_files(subdir: Path, pattern: str = "*.pdf") -> List[Path]:
    """扫描指定目录获取PDF文件列表
    
    Args:
        subdir: 目标目录
        pattern: 文件匹配模式（默认*.pdf）
        
    Returns:
        按名称排序的PDF文件路径列表
    """
    logger = get_run_logger()
    logger.info(f"📂 开始扫描目录: {subdir}")
    
    try:
        if not subdir.is_dir():
            raise NotADirectoryError(f"路径不是目录: {subdir}")
            
        files = sorted([f for f in subdir.glob(pattern) if f.is_file()])
        valid_files = []
        
        # 文件有效性检查
        for f in files:
            if f.stat().st_size == 0:
                logger.warning(f"跳过空文件: {f.name}")
                continue
            valid_files.append(f)
            
        logger.info(f"找到 {len(valid_files)} 个有效PDF文件 | 目录: {subdir.name}")
        return valid_files
        
    except NotADirectoryError as nde:
        logger.error(f"路径不是目录: {subdir}")
        raise
    except PermissionError as pe:
        logger.error(f"目录访问权限不足: {subdir}")
        raise
    except Exception as e:
        logger.error(f"文件扫描异常: {str(e)}", exc_info=True)
        raise