from collections import Counter, defaultdict
import os
from pathlib import Path
from typing import Any, Dict, List, Tuple
import json
import fitz
from prefect import flow, task, get_run_logger
from utils.str_utils import optimize_str
from magic_pdf.data.dataset import PymuDocDataset
from magic_pdf.config.enums import SupportedPdfParseMethod
from magic_pdf.model.doc_analyze_by_custom_model import doc_analyze
from magic_pdf.data.data_reader_writer import FileBasedDataWriter, FileBasedDataReader
from tasks.llm_task.chat_task import *
from tasks.doc_task.base_task import prepare_output_path

# ------------------------ 核心处理任务 ------------------------
@task(name="process_pdf_file")
def process_pdf_file(
    pdf_file: Path, 
    input_dir: Path, 
    output_root: Path,
    final_output_dir: Path,
) -> Dict:
    """单个文件处理包装任务"""
    logger = get_run_logger()
    try:
        output_dir = prepare_output_path.submit(input_dir, pdf_file, output_root).result()
        result = process_pdf_workflow.submit(
            pdf_file=pdf_file,
            working_dir=output_dir,
            final_output_dir=final_output_dir
        ).result()
        return result
    except Exception as e:
        logger.error(f"文件处理流程失败: {pdf_file.name} - {str(e)}")
        return {
            "status": "failed", 
            "error": str(e),
            "file": str(pdf_file)
        }

@task
def process_pdf_workflow(pdf_file: Path, 
                       working_dir: Path, 
                       final_output_dir: Path) -> Dict:
    """PDF处理完整工作流"""
    logger = get_run_logger()
    
    try:
        # 1. 提取内容
        extract_result = extract_pdf_content.submit(pdf_file, working_dir).result()
        
        # 2. 生成Markdown
        markdown_result = generate_markdown.submit(pdf_file, extract_result, working_dir, final_output_dir).result()
        
        # 3. 复制到最终位置
        # copy_result = copy_to_final_location.submit(markdown_result, final_output_dir).result()
        copy_result = True
        
        return {
            "status": "success",
            "working_files": extract_result,
            "markdown_result": markdown_result,
            "copy_result": copy_result
        }
        
    except Exception as e:
        logger.error(f"PDF处理工作流失败: {str(e)}", exc_info=True)
        raise


@task(
    name="extract-pdf-content",
    description="PDF文档内容提取任务｜提取文本/图片并生成结构化数据、可视化报告及Markdown文档 | 使用MinerU的实现方式 | 需要注意使用 Mineru 的python环境",
    tags=["pdf-processing", "data-extraction", "ocr", "MinerU"],
    log_prints=True
)
def extract_pdf_content(pdf_file: Path, output_dir: Path) -> Dict:
    """PDF文档内容解析流水线 task
    
    核心功能:
    - 使用 MinerU 解析PDF，得到初版的 markdown
    - 自动检测PDF类型（可编辑文本/扫描图像）
    - 生成结构化数据(JSON)和图片资源
    - 输出可视化分析报告(PDF)
    - 生成带图片引用的Markdown文档

    参数:
        pdf_file (Path): PDF文件路径，支持本地或网络存储路径
        output_dir (Path): 输出目录，建议使用独立目录防止文件覆盖

    返回:
        Dict: 包含生成文件元数据的字典，结构如下:
        {
            "status": "success|error",
            "pdf_stem": "原始文件名",
            "content_list": "内容清单json路径",
            "middleware_data": "中间数据json结构路径",
            "assets_dir": "资源目录路径",
            "visualizations": ["可视化报告路径1", "路径2"]
        }

    异常策略:
        - 错误日志包含完整堆栈跟踪
    """
    logger = get_run_logger()
    flow_tracker = f"[PDF:{pdf_file.name}]"

    try:
        # 预处理阶段
        logger.info(f"🚀 启动PDF解析流程 {flow_tracker}")
        logger.debug(f"📥 输入文件路径: {pdf_file.resolve()}")
        logger.debug(f"📤 输出目录路径: {output_dir.resolve()}")

        pdf_stem = pdf_file.stem
        image_dir = output_dir / f"images_{pdf_stem}"
        logger.info(f"🛠️ 创建资源目录: {image_dir.name}")
        image_dir.mkdir(exist_ok=True)
        logger.debug(f"✅ 目录创建验证: {image_dir.exists()}")
        
        # 初始化读写器
        logger.debug("🔄 初始化文件读写器...")
        image_writer = FileBasedDataWriter(str(image_dir))
        md_writer = FileBasedDataWriter(str(output_dir))
        logger.info(f"📄 读写器配置完成 | 图片目录: {image_dir} | 文档目录: {output_dir}")
        
        # 核心处理流程
        logger.info("🔍 开始解析PDF文件结构...")
        reader = FileBasedDataReader("")
        pdf_bytes = reader.read(str(pdf_file))
        logger.debug(f"📊 PDF字节大小: {len(pdf_bytes)/1024:.2f} KB")
        
        ds = PymuDocDataset(pdf_bytes)
        logger.info(f"🤖 PDF类型检测中...")
        if ds.classify() == SupportedPdfParseMethod.OCR:
            logger.warning("⚠️ 检测到扫描版PDF，启用OCR识别模式")
            infer_result = ds.apply(doc_analyze, ocr=True)
            pipe_result = infer_result.pipe_ocr_mode(image_writer)
            logger.debug("🖼️ OCR模式处理完成，图片提取数量: %d", len(os.listdir(image_dir)))
        else:
            logger.info("✅ 检测到可编辑PDF，使用文本提取模式")
            infer_result = ds.apply(doc_analyze, ocr=False)
            pipe_result = infer_result.pipe_txt_mode(image_writer)
            # logger.debug("📝 文本提取完成",)

        # 生成中间文件
        logger.info("📦 生成结构化数据文件...")
        content_list_path = output_dir / f"{pdf_stem}_content_list.json"
        pipe_result.dump_content_list(md_writer, content_list_path.name, image_dir.resolve())
        logger.debug(f"🗂️ 内容清单文件生成: {content_list_path.stat().st_size} bytes")
        
        middle_json_path = output_dir / f"{pdf_stem}_middle.json"
        pipe_result.dump_middle_json(md_writer, middle_json_path.name)
        logger.debug(f"📊 中间数据文件生成: {middle_json_path.stat().st_size} bytes")

        # 生成可视化结果
        logger.info("🎨 生成可视化分析报告...")
        model_output = output_dir / f"{pdf_stem}_model.pdf"
        infer_result.draw_model(str(model_output))
        logger.debug(f"🖼️ 模型可视化文件: {model_output.stat().st_size} bytes")
        
        layout_output = output_dir / f"{pdf_stem}_layout.pdf"
        pipe_result.draw_layout(str(layout_output))
        logger.debug(f"📐 版面分析文件: {layout_output.stat().st_size} bytes")

        # 生成Markdown内容
        logger.info("📝 生成Markdown文档...")
        md_content = pipe_result.get_markdown(os.path.basename(image_dir))
        md_output = output_dir / f"{pdf_stem}.md"
        with open(md_output, 'w', encoding='utf-8') as f:
            f.write(f"# {pdf_stem}\n\n")
            f.write(md_content)
        logger.debug(f"📄 Markdown文档生成: {md_output.stat().st_size} chars")

        logger.debug(f"🎉 成功完成处理 {flow_tracker}")
        return {
            "status": "success",
            "pdf_stem": pdf_stem,
            "content_list_path": str(content_list_path),
            "middle_json_path": str(middle_json_path),
            "image_dir": str(image_dir),
            "visualization_files": [str(model_output), str(layout_output)]
        }
        
    except Exception as e:
        logger.error(f"❌ 严重错误 {flow_tracker} 类型: {type(e).__name__}", exc_info=True)
        logger.debug(f"🛑 错误发生时的临时文件状态: {[f.name for f in output_dir.glob('*') if f.is_file()]}")
        raise

@task(name="enhance-markdown-generation", description="Markdown生成优化任务｜集成结构化数据清洗与大纲智能匹配｜MinerU增强版")
def generate_markdown(
    pdf_file: Path,
    extract_result: Dict,
    output_dir: Path,
    final_output_dir: Path
) -> Dict:
    """主协调流程"""
    logger = get_run_logger()
    trace_id = f"[{extract_result['pdf_stem']}]"
    
    try:
        # 阶段1：数据加载
        raw_data, content_list_path = load_initial_data.submit(extract_result).result()
        
        # 阶段2：数据清洗
        cleaned_data = clean_text_data.submit(raw_data).result()
        
        # 阶段3：大纲处理
        outline_data, outline_index = process_outline.submit(pdf_file, extract_result['pdf_stem']).result()
        
        # 新增阶段3.5：大纲-数据匹配
        matched_data = match_outline_to_data.submit(cleaned_data, outline_index, extract_result['pdf_stem']).result()
        
        # 阶段4：内容生成
        markdown_content = generate_markdown_content.submit(matched_data).result()
        
        # 阶段5：输出持久化
        output_metadata = persist_output_files(
            extract_result['pdf_stem'],
            matched_data,
            markdown_content,
            output_dir,
            final_output_dir
        )
        
        return {
            "status": "success",
            "pdf_stem": extract_result['pdf_stem'],
            **output_metadata
        }
        
    except Exception as e:
        logger.error(f"❌ 主流程失败 {trace_id}", exc_info=True)
        raise RuntimeError(f"Markdown生成失败: {str(e)}") from e

@task
def copy_to_final_location(markdown_result: Dict, final_output_dir: Path) -> Dict:
    """将Markdown复制到最终位置"""
    logger = get_run_logger()
    try:
        markdown_path = Path(markdown_result["markdown_path"])
        pdf_stem = markdown_result["pdf_stem"]
        
        # 构建目标路径
        target_dir = final_output_dir / markdown_path.parent.name  # 保留子目录结构
        target_path = target_dir / f"{pdf_stem}.md"
        
        # 执行复制
        target_dir.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy(markdown_path, target_path)

        return {
            "status": "success",
            "original_path": str(markdown_path),
            "final_path": str(target_path)
        }
        
    except Exception as e:
        logger.error(f"文件复制失败: {str(e)}", exc_info=True)
        raise
      



@task
def save_output(md_content: str, output_dir: Path, filename: str) -> Path:
    """保存输出文件"""
    logger = get_run_logger()
    try:
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"{filename}.md"
        
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(f"# {filename}\n\n")
            f.write(md_content)
        
        logger.info(f"Saved output to: {output_path}")
        return output_path
    except Exception as e:
        logger.error(f"Failed to save output: {str(e)}")
        raise

@task
def extract_outline(pdf_path):
    """提取PDF大纲结构"""
    doc = fitz.open(pdf_path)
    outline_data = [{
        "level": item[0],
        "title": item[1],
        "page": max(0, item[2] - 1)  # 确保页码非负
    } for item in doc.get_toc()]
    return outline_data




@task(name="match_outline_to_data", description="执行大纲与数据匹配", tags=["data-matching"])
def match_outline_to_data(
    cleaned_data: List[Dict], 
    outline_index: Dict,
    pdf_stem: str
) -> List[Dict]:
    """执行大纲与文本数据的智能匹配
    
    Args:
        cleaned_data: 清洗后的结构化数据
        outline_index: 大纲索引结构
        pdf_stem: 文件标识
        
    Returns:
        带有文本层级信息的数据
    """
    logger = get_run_logger()
    trace_id = f"[{pdf_stem}]"
    total_matches = 0
    total_items = len(outline_index.get(0, {}).items())
    
    try:
        # 构建反向索引加速匹配
        text_index = defaultdict(list)
        for idx, item in enumerate(cleaned_data):
            if item.get('type') == 'text':
                clean_text = optimize_str(item.get('text', ''))
                text_index[clean_text].append(idx)
        # 处理空数据集情况
        if total_items == 0:
            logger.warning(f"⚠️ 检测到空数据集 | 无法执行匹配流程")
            return cleaned_data
          
        for outline in outline_index.get(0, {}).items():  # 假设第一页为大纲基准页
            norm_title, outline_level = outline
            matched_items = text_index.get(norm_title, [])
                        
            # 应用匹配结果
            for idx in matched_items:
                item = cleaned_data[idx]
                item['text_level'] = outline_level
                total_matches += 1
                
        logger.info(f"🔗 匹配完成 | 总匹配: {total_matches}/{total_items} | 准确率: {total_matches/total_items:.1%}")
        return cleaned_data
    except Exception as e:
        logger.error(f"❌ 匹配失败 {trace_id}", exc_info=True)
        raise

@task(name="load_initial_data", description="加载初始数据", tags=["data-loading"])
def load_initial_data(extract_result: Dict) -> Tuple[Dict, Path]:
    """处理原始数据加载
    
    Args:
        extract_result: 提取阶段元数据
        
    Returns:
        清洗前数据和内容列表路径
    """
    logger = get_run_logger()
    trace_id = f"[{extract_result['pdf_stem']}]"
    
    try:
        content_list_path = Path(extract_result["content_list_path"])
        logger.debug(f"📂 加载数据路径: {content_list_path}")
        
        with open(content_list_path, 'r', encoding='utf-8') as f:
            raw_data = json.load(f)
            
        logger.info(f"📥 成功加载 {len(raw_data)} 条原始数据")
        return raw_data, content_list_path
    except Exception as e:
        logger.error(f"❌ 数据加载失败 {trace_id}", exc_info=True)
        raise

@task(name="clean_text_data", description="执行文本清洗", tags=["data-cleaning"])
def clean_text_data(raw_data: List[Dict]) -> List[Dict]:
    """执行结构化数据清洗优化
    
    Args:
        raw_data: 原始提取数据
        
    Returns:
        清洗后的结构化数据
    """
    logger = get_run_logger()
    cleaned_data = []
    text_optimization_stats = {"total": 0, "optimized": 0}
    
    for idx, item in enumerate(raw_data):
        if item.get("type") != "text":
            cleaned_data.append(item)
            continue
            
        logger.debug(f"🔍 处理文本条目 {idx}")
        original_text = item.get('text', '')
        
        # 执行文本优化
        optimized = optimize_str(original_text)
        text_optimization_stats["total"] += 1
        
        if optimized != original_text:
            text_optimization_stats["optimized"] += 1
            item['text'] = optimized
            logger.debug(f"✨ 优化生效: {original_text[:30]}... → {optimized[:30]}...")
            
        # 清理冗余字段
        if 'text_level' in item and item.get('text_level') == 1:
            del item['text_level']
            
        cleaned_data.append(item)
    
    logger.info(f"📊 文本清洗完成 | 总处理: {text_optimization_stats['total']} | 优化率: {text_optimization_stats['optimized']/text_optimization_stats['total']:.1%}")
    return cleaned_data

@task(name="process_outline", description="处理文档大纲", tags=["outline-processing"])
def process_outline(pdf_file: Path, pdf_stem: str) -> Tuple[List[Dict], Dict]:
    """执行大纲处理与匹配
    
    Args:
        pdf_file: PDF文件路径
        pdf_stem: 文件标识
        
    Returns:
        (处理后大纲数据, 大纲索引结构)
    """
    logger = get_run_logger()
    trace_id = f"[{pdf_stem}]"
    
    try:
        # 实际场景应调用真实大纲提取
        outline_data = extract_outline.submit(pdf_file)
        outline_data = [
            {
              "level": 1,
              "title": "剂量调整因数 - 使用 Auto/Smart mA 时的噪声指数调整方法",
              "page": 0
            },
            {
              "level": 2,
              "title": "例如，若要计算基于已选 ASiR-V 级别的噪声指数 (NI) 的剂量减少，可将下表用于标准重建算法。",
              "page": 0
            },
        ]
        
        # 构建大纲索引
        outline_index = {}
        for outline in outline_data:
            page = outline['page']
            norm_title = optimize_str(outline['title'])
            
            if page not in outline_index:
                outline_index[page] = {}
            outline_index[page][norm_title] = outline['level']
                
        logger.info(f"📑 大纲处理完成 | 条目: {len(outline_data)} | 索引页数: {len(outline_index)}")
        return outline_data, outline_index
    except Exception as e:
        logger.error(f"❌ 大纲处理失败 {trace_id}", exc_info=True)
        raise

@task(name="generate_markdown", description="生成Markdown内容", tags=["content-generation"])
def generate_markdown_content(cleaned_data: List[Dict]) -> str:
    """生成最终Markdown文档
    
    Args:
        cleaned_data: 清洗后的结构化数据
        
    Returns:
        格式化后的Markdown字符串
    """
    logger = get_run_logger()
    md_builder = []
    last_page = -1
    
    for idx, item in enumerate(cleaned_data):
        current_page = item.get('page_idx', -1)
        if current_page != last_page:
            md_builder.append(f"\n<!--page-{{{current_page + 1}}}-->\n")
            logger.debug(f"📖 页面切换 → P{current_page+1}")
            last_page = current_page
            
        content_type = item.get('type')
        if content_type == "text":
            processed = handle_text(item)
        elif content_type == "table":
            processed = handle_table.submit(item, cleaned_data, idx).result()
        elif content_type == "image":
            processed = handle_image.submit(item, cleaned_data, idx).result()
        elif content_type == "equation":
            processed = handle_equation(item)
        else:
            processed = ""  # 默认空内容
        
        md_builder.append(processed)
        logger.debug(f"✏️ 内容处理 @条目{idx} | 类型: {content_type} | 长度: {len(processed)}")
        
    return "\n".join(md_builder)

@task(name="persist_outputs", description="持久化输出文件", tags=["output-persistence"])
def persist_output_files(
    pdf_stem: str,
    raw_data: List[Dict],
    markdown: str,
    output_dir: Path,
    final_output_dir: Path
) -> Dict:
    """处理输出文件持久化
    
    Args:
        pdf_stem: 文件标识
        raw_data: 原始数据
        markdown: 生成的MD内容
        output_dir: 中间目录
        final_output_dir: 最终目录
        
    Returns:
        输出文件路径集合
    """
    logger = get_run_logger()
    trace_id = f"[{pdf_stem}]"
    
    try:
        # 构建输出路径
        optimized_json = output_dir / f"{pdf_stem}_optimized.json"
        final_md = final_output_dir / f"{pdf_stem}.md"
        
        # 持久化处理
        with open(optimized_json, 'w', encoding='utf-8') as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False)
        final_md.parent.mkdir(parents=True, exist_ok=True)
        with open(final_md, 'w', encoding='utf-8') as f:
            header = f"# {pdf_stem}\n<!-- Source: {pdf_stem} -->\n\n"
            f.write(header + markdown)
            
        logger.info(f"💾 输出保存完成 | JSON: {optimized_json} | MD: {final_md}")
        return {
            "original_json": str(optimized_json.with_suffix('.json')),
            "optimized_json": str(optimized_json),
            "markdown_path": str(final_md)
        }
    except Exception as e:
        logger.error(f"❌ 输出持久化失败 {trace_id}", exc_info=True)
        raise