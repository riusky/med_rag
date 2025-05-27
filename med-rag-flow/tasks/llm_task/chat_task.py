import json
from pathlib import Path
import time
from typing import Dict, List # Removed sys as it's unused

from prefect import get_run_logger, task
# TableImageConverter from utils is the core logic, not directly used here anymore for tasks
# from utils.table_image_converter import TableImageConverter 

# Import the new task-based functions from base_task
from med_rag_flow.tasks.llm_task.base_task import (
    convert_image_to_table_task, 
    generate_image_caption_task,
    TableImageConverter # Import the core class for instantiation
)
# ------------------------ 新增批量处理任务 ------------------------
def handle_text(item: Dict) -> str:
    """处理文本类型元素"""
    if 'text_level' in item:
        return f"{'#' * item['text_level']} {item['text']}\n\n"
    return f"{item['text']}\n\n"

@task(
     name="handle_table_chat_task", # Renamed for clarity to distinguish from base_task tasks
     description="生成表格图片的markdown格式文字表述 (chat_task wrapper)",
     tags=["image", "table", "llm", "chat_task"]
)
def handle_table(item: Dict, data: List[Dict], index: int, config_path_str: str) -> str: # Added config_path_str
    """带完整日志的表格处理方法, using new unified tasks"""
    logger = get_run_logger()
    item.setdefault('conversion_success', False)
    item['markdown_table'] = ""
    item['error_message'] = ""
    try:
        if not (img_path := item.get('img_path')):
            raise ValueError("Missing img_path in table item")

        logger.info(f"Handling table for image: {img_path} using config: {config_path_str}")
        
        # Instantiate the core converter, which is needed by the new tasks
        # The tasks `convert_image_to_table_task` and `generate_image_caption_task`
        # expect an instance of TableImageConverter.
        core_converter = TableImageConverter(config_path=config_path_str)

        # Call the unified task from base_task.py
        # .submit().result() is used if running within a Prefect flow and needing to resolve futures.
        # If this task itself is part of a larger flow, direct call or .submit() might be appropriate.
        # For simplicity, let's assume direct call if this task is awaited,
        # or .submit().result() if we want to mimic previous behavior of resolving submitted tasks.
        table_result = convert_image_to_table_task.with_options(
            name="convert_image_to_table_from_chat_handle_table" # Dynamic task name
        ).submit(
            converter_instance=core_converter,
            image_path=img_path
        ).result()
        
        item.update({
            'markdown_table': table_result,
            'conversion_success': True
        })
        logger.info(f"Table conversion successful for {img_path}")
        return f"\n{table_result}\n"
    except Exception as e:
        logger.error(f"Table conversion failed for {img_path}: {str(e)}", exc_info=True)
        item.update({
            'type': "image", # This seems to be a fallback type
            'conversion_success': False,
            'error_message': str(e)
        })
        # Return the original table caption as fallback
        return f"\n{item.get('table_caption','')}\n"

@task(
     name="handle_image_chat_task", # Renamed
     description="生成图片的解释文字 (chat_task wrapper)",
     tags=["image", "llm", "chat_task"]
)
def handle_image(
    item: Dict,
    data: List[Dict], # context data
    index: int, # index in data
    config_path_str: str, # Added config_path_str
    image_base_url: str = None,
    output_root: str = None
) -> str:
    """带完整日志的图片处理方法（新增路径替换功能）, using new unified tasks"""
    logger = get_run_logger()
    item.setdefault('conversion_success', False)
    item['image_description'] = ""
    item['error_message'] = ""
    
    start_time = time.time()
    img_path = item.get('img_path') # Get img_path early for logging and fallback

    try:
        if not img_path:
            raise ValueError("Missing img_path in image item")

        logger.info(f"Handling image: {img_path} using config: {config_path_str}")
        
        core_converter = TableImageConverter(config_path=config_path_str)

        # Collect context for image description
        # The collect_context function seems to expect `item` to be the image item itself.
        image_context_json = collect_context(data, index, item)
        
        desc_processed = generate_image_caption_task.with_options(
            name="generate_image_caption_from_chat_handle_image"
        ).submit(
            converter_instance=core_converter,
            image_path=img_path,
            context=image_context_json # Pass collected context
        ).result()
        
        # Path replacement logic (remains the same)
        processed_img_path = img_path # Initialize with original path
        if image_base_url and output_root:
            try:
                rel_path = Path(img_path).resolve().relative_to(Path(output_root).resolve())
                new_path = f"{image_base_url}/{rel_path.as_posix()}"
                logger.debug(f"路径替换成功: {img_path} → {new_path}")
                processed_img_path = new_path # Update path for use in markdown
            except ValueError as ve: # Specific error for relative_to if base path is not an ancestor
                logger.warning(f"路径替换失败（路径非子孙）: {img_path}, Base: {output_root}. Error: {str(ve)}")
            except Exception as e_path:
                logger.error(f"路径替换异常 for {img_path}: {str(e_path)}", exc_info=True)
        
        item['img_path'] = processed_img_path # Update item metadata with potentially new path
        item.update({
            'conversion_success': True,
            'image_description': desc_processed
        })
        
        logger.info(f"Image description successful for {img_path}. Description: {desc_processed[:50]}...")
        return f"\n![{desc_processed}]({processed_img_path})\n\n"
    
    except Exception as e:
        elapsed = time.time() - start_time
        error_msg = f"Image processing failed for {img_path} in {elapsed:.2f}s: {str(e)}"
        logger.error(error_msg, exc_info=True)
        
        # Fallback logic (remains the same, uses potentially modified img_path if path replacement happened before error)
        # Ensure 'img_path' in item is the one to be used for fallback URL
        fallback_img_path = item.get('img_path', img_path) # Use path from item if updated, else original
        caption = ' '.join(item.get('img_caption', [])) or (Path(img_path).stem if img_path else "image")

        item.update({
            'error_message': error_msg,
            # Ensure image_description is empty or reflects failure if needed by downstream
            'image_description': item.get('image_description', '') # Keep existing if partial success, or empty
        })
        return f"\n![{caption}]({fallback_img_path})\n\n"


def handle_equation(item: Dict) -> str:
    """处理公式类型元素"""
    equation = item['text'].replace('\n', ' ').strip()
    return f"\n{equation}\n\n"
  
  
def collect_context(data: List[Dict], index: int, item: Dict) -> str: # Added type hint for item
    """精准收集相邻text元素 for image caption context"""
    # This function is designed to create a JSON string of the item itself
    # and its immediate text neighbors.
    context_items = []
    
    # Previous item if text
    if index > 0:
        prev_item = data[index-1]
        if prev_item.get('type') == 'text':
            context_items.append(prev_item)
            
    # Current item (the image item itself)
    # The original `generate_image_description` in `TableImageConverter` took `context: str`.
    # The `_build_image_prompt` then prepended this context to a fixed prompt string.
    # The `image_caption_prompt_template` is now loaded from config.
    # If `item` (the image dict) is part of the context, include it.
    # Based on the original `_build_image_prompt`, the context was external text, not the item itself.
    # Let's assume the context should be the surrounding text, not the image item dict.
    # However, the current `collect_context` appends `item`.
    # If the prompt expects item details, this is fine. If it expects surrounding text, adjust.
    # For now, keeping existing logic of `collect_context`.
    context_items.append(item) 
    
    # Next item if text
    if index < len(data)-1:
        next_item = data[index+1]
        if next_item.get('type') == 'text':
            context_items.append(next_item)
    
    # Generate compact JSON string of these items
    return json.dumps(context_items, ensure_ascii=False, separators=(',', ':'))

# Example of how these tasks might be called within a flow in this file (if any)
# For instance, if there's a higher-level task or flow defined in chat_task.py:
#
# from prefect import flow
#
# @flow(name="process_document_elements_chat_flow")
# def process_document_elements_flow(document_data: List[Dict], output_config: Dict):
#     logger = get_run_logger()
#     processed_markdown = []
#
#     # Resolve config path relative to this script's location if necessary
#     # Assuming this script is in med-rag-flow/tasks/llm_task/
#     # So, ../../config/task/image_table_process.yaml would be correct if run from project root
#     # Or, if this flow is called from somewhere else, config_path might need to be absolute
#     # or carefully constructed.
#     script_dir = Path(__file__).parent
#     default_config_path = str((script_dir / "../../config/task/image_table_process.yaml").resolve())
#     final_config_path = output_config.get("converter_config_path", default_config_path)
#     logger.info(f"Using TableImageConverter config path: {final_config_path}")
#
#     for i, item_data in enumerate(document_data):
#         item_type = item_data.get("type")
#         if item_type == "text":
#             processed_markdown.append(handle_text(item_data))
#         elif item_type == "table" or (item_type == "image" and item_data.get("is_table")): # Example condition
#             # Ensure handle_table is called with .submit().result() if it's a sub-flow task run
#             processed_markdown.append(handle_table.submit(
#                                           item_data, 
#                                           document_data, 
#                                           i, 
#                                           config_path_str=final_config_path
#                                       ).result())
#         elif item_type == "image":
#             processed_markdown.append(handle_image.submit(
#                                           item_data, 
#                                           document_data, 
#                                           i,
#                                           config_path_str=final_config_path,
#                                           image_base_url=output_config.get("image_base_url"),
#                                           output_root=output_config.get("output_root_dir")
#                                       ).result())
#         elif item_type == "equation":
#             processed_markdown.append(handle_equation(item_data))
#         # ... other types
#
#     return "".join(processed_markdown)
#
# if __name__ == "__main__":
#     # Dummy data for testing process_document_elements_flow
#     # Ensure paths are correct if running this directly
#     dummy_doc_data = [
#         {"type": "text", "text": "Introduction to the document."},
#         # {"type": "table", "img_path": "path/to/your/table_image.jpg", "table_caption": "Table 1 Data"},
#         # {"type": "image", "img_path": "path/to/your/figure_image.jpg", "img_caption": ["Figure 1 Diagram"]},
#     ]
#     dummy_output_config = {
#         "image_base_url": "http://localhost/images",
#         "output_root_dir": "/app/output_files", # Example, needs to match where images are stored
#         # "converter_config_path": "/app/med-rag-flow/config/task/image_table_process.yaml" # Absolute if needed
#     }
#     # result_md = process_document_elements_flow(dummy_doc_data, dummy_output_config)
#     # print("\n--- Processed Markdown Output ---")
#     # print(result_md)
#
#     # Direct test of handle_table or handle_image (requires Prefect context or running as script)
#     # For direct script execution, tasks might not run as expected without `serve` or `run`
#     # This is more for illustrating the structure.
#     pass