import json
from pathlib import Path
import time
from typing import Dict, List
import sys

from prefect import get_run_logger, task
from utils.table_image_converter import TableImageConverter
from tasks.llm_task.base_task import TableImageConverterTasks
# ------------------------ 新增批量处理任务 ------------------------
def handle_text(item: Dict) -> str:
    """处理文本类型元素"""
    if 'text_level' in item:
        return f"{'#' * item['text_level']} {item['text']}\n\n"
    return f"{item['text']}\n\n"

@task(
     name="handle_table",
     description="生成表格图片的markdown格式文字表述",
     tags=["image", "table", "llm"]
)
def handle_table(item: Dict, data: List[Dict], index: int) -> str:
    """带完整日志的表格处理方法"""
    item.setdefault('conversion_success', False)
    item['markdown_table'] = ""
    item['error_message'] = ""
    try:
        if not (img_path := item.get('img_path')):
            raise ValueError("Missing img_path in table item")

        converter = TableImageConverterTasks(config_path="../config/task/image_table_process.yaml")
        
        # 公共处理流程
        encoded_image = converter.validate_and_encode_image_task.submit(img_path).result()
        
        # 表格转换子流程
        table_payload = converter.construct_payload_task.submit(encoded_image, task_name="table_conversion").result()
        table_response = converter.send_api_request_task.submit(table_payload).result()
        processed_text = converter.process_api_response_task.submit(table_response).result()
        table_result = converter.generate_markdown_table_task.submit(processed_text).result()
        item.update({
            'markdown_table': table_result,
            'conversion_success': True
        })
        return f"\n{table_result}\n"
    except Exception as e:
        item.update({
            'type': "image",
            'conversion_success': False
        })
        return f"\n{item.get('table_caption','')}\n"

@task(
     name="handle_image",
     description="生成图片的解释文字",
     tags=["image", "llm"]
)
def handle_image(
    item: Dict,
    data: List[Dict],
    index: int,
    image_base_url: str = None,
    output_root: str = None
) -> str:
    """带完整日志的图片处理方法（新增路径替换功能）"""
    logger = get_run_logger()
    item.setdefault('conversion_success', False)
    item['image_description'] = ""
    item['error_message'] = ""
    
    start_time = time.time()
    try:
        # 基础验证
        if not (img_path := item.get('img_path')):
            raise ValueError("Missing img_path in image item")
        # 原有图片处理流程
        converter = TableImageConverterTasks(config_path="../config/task/image_table_process.yaml")
        encoded_image = converter.validate_and_encode_image_task.submit(img_path).result()
        desc_payload = converter.construct_payload_task.submit(encoded_image, task_name="image_caption").result()
        desc_response = converter.send_api_request_task.submit(desc_payload).result()
        desc_processed = converter.process_caption_response.submit(desc_response).result()
        # 新增路径替换逻辑
        if image_base_url and output_root:
            try:
                # 转换为相对路径
                rel_path = Path(img_path).resolve().relative_to(Path(output_root).resolve())
                new_path = f"{image_base_url}/{rel_path.as_posix()}"
                logger.debug(f"路径替换成功: {img_path} → {new_path}")
                item['img_path'] = new_path  # 更新元数据中的路径
            except ValueError as ve:
                logger.warning(f"路径替换失败（超出根目录）: {img_path} | {str(ve)}")
            except Exception as e:
                logger.error(f"路径替换异常: {str(e)}", exc_info=True)
        # 更新元数据
        item.update({
            'conversion_success': True,
            'image_description': desc_processed
        })
        
        return f"\n![{desc_processed}]({item['img_path']})\n\n"
    
    except Exception as e:
        # 异常处理（保持路径替换结果）
        elapsed = time.time() - start_time
        error_msg = f"Image processing failed in {elapsed:.2f}s: {str(e)}"
        
        # 降级方案（使用替换后的路径）
        caption = ' '.join(item.get('img_caption', [])) or Path(img_path).stem
        item.update({
            'error_message': error_msg
        })
        return f"\n![{caption}]({item['img_path']})\n\n"


def handle_equation(item: Dict) -> str:
    """处理公式类型元素"""
    equation = item['text'].replace('\n', ' ').strip()
    return f"\n{equation}\n\n"
  
  
def collect_context(data: List[Dict], index: int,item: Dict) -> str:
    """精准收集相邻text元素"""
    context = []
    
    # 前向检查（仅检查index-1）
    if index > 0:
        prev_item = data[index-1]
        if prev_item.get('type') == 'text':
            context.append(prev_item)
    context.append(item)
    # 后向检查（仅检查index+1）
    if index < len(data)-1:
        next_item = data[index+1]
        if next_item.get('type') == 'text':
            context.append(next_item)
    
    # 生成紧凑型Markdown
    return json.dumps(context, ensure_ascii=False, separators=(',', ':'))