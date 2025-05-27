from pathlib import Path
from prefect import get_run_logger, task, flow
import requests # Keep for type hint if send_api_request_task returns Response object
from typing import Optional, Tuple, Any # Added Tuple, Any
import base64 # Keep if validate_and_encode_image_task still returns base64 string directly
# import re # No longer needed here
# from PIL import Image # No longer needed here
# import io # No longer needed here
# import json # No longer needed here
# import yaml # No longer needed here

# Import the refactored TableImageConverter
from med_rag_flow.utils.table_image_converter import TableImageConverter
from med_rag_flow.utils.config_loader import ConfigLoader


class TableImageConverterTasks:
    def __init__(self, config_path: str = "config/task/image_table_process.yaml"): # Adjusted default path
        # ConfigLoader might not be strictly needed here if TableImageConverter handles all config loading
        # However, if tasks themselves have specific configs or need to pass config path, keep it.
        # self.config_loader = ConfigLoader(config_path) # This loads the config
        # self.config = self.config_loader.config # This holds the loaded config data
        
        # Instantiate the core converter, passing the config path
        self.converter = TableImageConverter(config_path=config_path)
        self.logger = get_run_logger() # Initialize logger once

    @task(
        name="validate-and-encode-image",
        description="图片验证与Base64编码任务",
        tags=["image-processing", "validation"],
    )
    def validate_and_encode_image_task(self, image_path: str) -> str:
        """执行图片验证和Base64编码 using TableImageConverter"""
        self.logger.info(f"Starting validation and encoding for: {image_path}")
        try:
            # The core logic is now in TableImageConverter's _validate_and_encode_image
            # This method is protected; consider making it public or adding a public wrapper in TableImageConverter
            # For now, let's assume we call it directly for simplicity in this refactoring step.
            # Or, we can call the public `convert` or `generate_image_description` which internally call it.
            # However, tasks are often chained, so having a dedicated task for encoding might be intended.
            # Let's assume TableImageConverter._validate_and_encode_image can be called.
            encoded_image = self.converter._validate_and_encode_image(image_path)
            self.logger.info(f"✅ 图片验证成功: {image_path}")
            return encoded_image
        except Exception as e:
            self.logger.error(f"图片处理失败 in task: {image_path}, Error: {str(e)}")
            raise

    @task(
        name="construct-api-payload",
        description="构建API请求体任务",
        tags=["api", "payload"]
    )
    def construct_payload_task(
        self, 
        base64_image: str, 
        task_name: str = "table_conversion",
        custom_user_prompt: Optional[str] = None
    ) -> dict:
        """动态构建API请求体 using TableImageConverter"""
        self.logger.info(f"Constructing payload for task: {task_name}")
        try:
            # Core logic is in TableImageConverter._construct_payload
            payload = self.converter._construct_payload(
                base64_image, 
                task_name, 
                custom_user_prompt
            )
            self.logger.info(f"✅ Payload constructed for task: {task_name}")
            return payload
        except Exception as e:
            self.logger.error(f"Payload construction failed for task {task_name}: {str(e)}")
            raise

    @task(
        name="send-api-request",
        description="发送API请求任务",
        tags=["api", "communication"],
    )
    def send_api_request_task(self, payload: dict) -> Any: # Return type can be requests.Response
        """处理API通信及基础响应验证 using TableImageConverter"""
        self.logger.info("Sending API request")
        try:
            # Core logic is in TableImageConverter._send_request
            response = self.converter._send_request(payload)
            self.logger.info("✅ API请求成功")
            return response # requests.Response object
        except Exception as e:
            self.logger.error(f"API通信失败 in task: {str(e)}")
            raise 

    @task(
        name="process-api-response-table", # Renamed for clarity
        description="处理表格转换API响应任务",
        tags=["response", "processing", "table"]
    )
    def process_api_response_table_task(self, response: Any) -> str: # response is requests.Response
        """处理表格转换API响应 using TableImageConverter"""
        self.logger.info("Processing API response for table conversion")
        try:
            # Core logic is in TableImageConverter._process_response
            # We need to specify the task_name for context
            processed_text = self.converter._process_response(response, task_name="table_conversion")
            self.logger.info(f"✅ Table conversion response processed. Length: {len(processed_text)}")
            return processed_text
        except Exception as e:
            self.logger.error(f"Table conversion response processing failed: {str(e)}")
            raise

    @task(
        name="process-api-response-caption", # Renamed for clarity
        description="处理图片描述API响应任务",
        tags=["response", "processing", "caption"]
    )
    def process_api_response_caption_task(self, response: Any) -> str: # response is requests.Response
        """处理图片描述API响应 using TableImageConverter"""
        self.logger.info("Processing API response for image caption")
        try:
            # Core logic is in TableImageConverter._process_response
            processed_text = self.converter._process_response(response, task_name="image_caption")
            self.logger.info(f"✅ Image caption response processed. Length: {len(processed_text)}")
            return processed_text
        except Exception as e:
            self.logger.error(f"Image caption response processing failed: {str(e)}")
            raise

    # The `generate_markdown_table_task` was specific to extracting table from text.
    # This logic is now part of `_process_response` when task_name="table_conversion" in TableImageConverter.
    # So, this specific task might be redundant if `process_api_response_table_task` returns the final table.
    # If `_extract_markdown_table` needs to be a separate step *after* initial text extraction,
    # then TableImageConverter._extract_markdown_table (which is static) can be called.

    # Let's assume `process_api_response_table_task` now directly returns the Markdown table string.
    # If further formatting or a distinct step is needed, we can add:
    # @task(name="format-markdown-table", ...)
    # def format_markdown_table_task(self, raw_markdown_text: str) -> str:
    #     self.logger.info("Formatting text to Markdown table")
    #     try:
    #         # This assumes _extract_markdown_table is still relevant and public/static
    #         table = TableImageConverter._extract_markdown_table(raw_markdown_text)
    #         self.logger.info("✅ Markdown table formatted.")
    #         return table
    #     except Exception as e:
    #         self.logger.error(f"Markdown table formatting failed: {str(e)}")
    #         raise

    # Removed _load_prompt_content, _enhanced_response_cleaning, _structured_table_extraction
    # as their functionalities are now in TableImageConverter.

# ------------------ Flow构建 (Example Usage) ------------------
# Note: The flow demonstrates how these tasks might be chained.
# The actual implementation of calling convert() or generate_image_description()
# from the TableImageConverter might simplify the flow further,
# as those methods encapsulate multiple steps.

@flow
def table_conversion_flow(
    image_path: str, 
    config_path: str = "config/task/image_table_process.yaml" # Ensure path is correct from flow context
):
    """Prefect flow for table conversion using refactored tasks."""
    tasks = TableImageConverterTasks(config_path=config_path)
    logger = get_run_logger()
    
    logger.info(f"Starting table conversion flow for: {image_path}")
    
    encoded_image = tasks.validate_and_encode_image_task(image_path)
    
    table_payload = tasks.construct_payload_task(
        base64_image=encoded_image, 
        task_name="table_conversion"
    )
    table_response = tasks.send_api_request_task(table_payload)
    
    # This task now directly returns the final markdown table.
    table_result = tasks.process_api_response_table_task(table_response)
    
    logger.info(f"Table conversion flow completed. Result:\n{table_result}")
    return table_result

@flow
def image_captioning_flow(
    image_path: str, 
    context: str, # Context for image captioning
    config_path: str = "config/task/image_table_process.yaml" # Ensure path is correct
):
    """Prefect flow for image captioning using refactored tasks."""
    tasks = TableImageConverterTasks(config_path=config_path)
    logger = get_run_logger()

    logger.info(f"Starting image captioning flow for: {image_path}")

    encoded_image = tasks.validate_and_encode_image_task(image_path)
    
    # For image captioning, the user prompt is constructed including context.
    # The TableImageConverter._build_image_prompt method does this.
    # We can either call it via the converter instance if made public,
    # or replicate its logic here if custom_user_prompt is simpler.
    # For now, let's assume custom_user_prompt is built before calling construct_payload_task.
    
    # This logic is inside TableImageConverter.generate_image_description -> _build_image_prompt
    # To use it directly:
    # user_prompt_for_caption = tasks.converter._build_image_prompt(context) 
    # This requires _build_image_prompt to be accessible.
    # Alternative: the task `construct_payload_task` could be enhanced
    # to take `context` and call `_build_image_prompt` internally for "image_caption" task.
    
    # Let's assume for now that the `generate_image_description` method from the core converter
    # is what we want to use as a single "task" or that the flow is more granular.
    # The `custom_user_prompt` in `construct_payload_task` is designed for this.
    
    # Replicating the prompt building logic for clarity in the flow:
    # (Ideally, this logic should be part of the converter or a helper accessible to the flow)
    caption_prompt_template = tasks.converter.image_caption_prompt_template # Access from converter
    custom_caption_prompt = f"{caption_prompt_template}\n\n[关联上下文]\n{context.strip()}"

    caption_payload = tasks.construct_payload_task(
        base64_image=encoded_image,
        task_name="image_caption",
        custom_user_prompt=custom_caption_prompt
    )
    caption_response = tasks.send_api_request_task(caption_payload)
    
    # This task now directly returns the final caption.
    caption_result = tasks.process_api_response_caption_task(caption_response)
    
    logger.info(f"Image captioning flow completed. Result: {caption_result}")
    return caption_result

# Simplified flow using the main methods of TableImageConverter if they were tasks
@task(name="convert-image-to-table-direct", retries=2, retry_delay_seconds=5)
def convert_image_to_table_task(
    converter_instance: TableImageConverter, 
    image_path: str
) -> str:
    logger = get_run_logger()
    logger.info(f"Direct table conversion for {image_path}")
    success, result = converter_instance.convert(image_path, task_name="table_conversion")
    if not success:
        logger.error(f"Direct table conversion failed for {image_path}: {result}")
        raise Exception(f"Table conversion failed: {result}")
    logger.info(f"✅ Direct table conversion successful for {image_path}")
    return result

@task(name="generate-image-caption-direct", retries=2, retry_delay_seconds=5)
def generate_image_caption_task(
    converter_instance: TableImageConverter,
    image_path: str,
    context: str
) -> str:
    logger = get_run_logger()
    logger.info(f"Direct image captioning for {image_path}")
    # generate_image_description itself handles exceptions and returns filename on failure
    caption = converter_instance.generate_image_description(image_path, context, task_name="image_caption")
    # Could add more robust error checking here if needed, e.g., if caption is just filename
    if caption == Path(image_path).stem:
         logger.warning(f"Image captioning for {image_path} might have fallen back to filename.")
    logger.info(f"✅ Direct image captioning successful for {image_path}")
    return caption


@flow
def unified_conversion_flow(
    image_path: str, 
    context_for_caption: str,
    config_path: str = "config/task/image_table_process.yaml",
    do_table_conversion: bool = True,
    do_image_captioning: bool = True,
):
    """
    Demonstrates using the direct task wrappers around TableImageConverter methods.
    This is a more streamlined way if the sub-steps (encode, payload, etc.)
    don't need to be individual Prefect tasks.
    """
    logger = get_run_logger()
    converter_instance = TableImageConverter(config_path=config_path) # Instantiated once
    
    table_result = None
    caption_result = None

    if do_table_conversion:
        logger.info(f"Starting direct table conversion sub-flow for {image_path}")
        table_result = convert_image_to_table_task.submit( # .submit for concurrency if desired
            converter_instance, 
            image_path
        ).result() # .result() if running sequentially or need result before next step
        logger.info(f"Table conversion result: {table_result}")

    if do_image_captioning:
        logger.info(f"Starting direct image captioning sub-flow for {image_path}")
        caption_result = generate_image_caption_task.submit( # .submit for concurrency
            converter_instance,
            image_path,
            context_for_caption
        ).result()
        logger.info(f"Image caption result: {caption_result}")
        
    return {"table": table_result, "caption": caption_result}


if __name__ == "__main__":
    # This example assumes the config file is accessible relative to this script's execution path
    # or an absolute path is provided.
    # Adjust "test.jpg" path and context as needed.
    
    # Path to a test image (IMPORTANT: ensure this image exists or change the path)
    # Assuming 'test.jpg' is in 'med-rag-flow/tasks/llm_task/' like in original structure
    current_script_dir = Path(__file__).parent
    test_image_relative_path = "test.jpg" # if test.jpg is in the same dir as this script
    # If test.jpg is in med-rag-flow/tasks/llm_task/test.jpg
    # project_root = current_script_dir.parent.parent 
    # test_image_path_obj = project_root / "tasks/llm_task/test.jpg"
    # For simplicity, let's assume test.jpg is in the same directory as base_task.py
    test_image_path_obj = current_script_dir / test_image_relative_path

    if not test_image_path_obj.exists():
        print(f"Error: Test image not found at {test_image_path_obj}")
        print("Please create a dummy 'test.jpg' in the same directory as this script or provide a valid path.")
        # Create a dummy one if it doesn't exist for testing
        try:
            from PIL import Image as PILImage, ImageDraw
            print(f"Attempting to create a dummy test image at {test_image_path_obj}...")
            img = PILImage.new('RGB', (200, 50), color = 'blue')
            d = ImageDraw.Draw(img)
            d.text((10,10), "Dummy Test Image", fill=(255,255,255))
            img.save(test_image_path_obj)
            print(f"Dummy test image created at {test_image_path_obj}")
        except Exception as e_img:
            print(f"Could not create dummy test image: {e_img}")
            exit(1) # Exit if no image can be found/created.

    test_image_path_str = str(test_image_path_obj)
    
    # Config path - relative to the project root (med-rag-flow)
    # If running this script directly from `med-rag-flow/tasks/llm_task/`
    # then `config/...` should be `../../config/...`
    # For `unified_conversion_flow` default: "config/task/image_table_process.yaml"
    # This implies the flow is run from project root or paths are adjusted.
    # Let's calculate relative path from this script to project's config folder
    project_root_config = current_script_dir.parent.parent / "config/task/image_table_process.yaml"

    print(f"Using config file: {project_root_config}")
    print(f"Using test image: {test_image_path_str}")

    # Example using the unified flow:
    flow_results = unified_conversion_flow(
        image_path=test_image_path_str,
        context_for_caption="Sample context for describing the image.",
        config_path=str(project_root_config),
        do_table_conversion=True,
        do_image_captioning=True
    )
    print(f"\n--- Unified Flow Results ---")
    if flow_results["table"]:
        print("\nTable Conversion Output:\n", flow_results["table"])
    if flow_results["caption"]:
        print("\nImage Caption Output:\n", flow_results["caption"])

    # Example using the more granular (original-style) flows:
    # print("\n--- Granular Table Conversion Flow ---")
    # table_output = table_conversion_flow(
    #     image_path=test_image_path_str, 
    #     config_path=str(project_root_config)
    # )
    # print("Table output:\n", table_output)

    # print("\n--- Granular Image Captioning Flow ---")
    # caption_output = image_captioning_flow(
    #     image_path=test_image_path_str, 
    #     context="This is a test context for the image.",
    #     config_path=str(project_root_config)
    # )
    # print("Caption output:\n", caption_output)

# TODO: Move the following test/demonstration code to proper unit tests under the tests/ directory.
# if __name__ == "__main__":
    # This example assumes the config file is accessible relative to this script's execution path
    # or an absolute path is provided.
    # Adjust "test.jpg" path and context as needed.
    
    # Path to a test image (IMPORTANT: ensure this image exists or change the path)
    # Assuming 'test.jpg' is in 'med-rag-flow/tasks/llm_task/' like in original structure
    # current_script_dir = Path(__file__).parent
    # test_image_relative_path = "test.jpg" # if test.jpg is in the same dir as this script
    # If test.jpg is in med-rag-flow/tasks/llm_task/test.jpg
    # project_root = current_script_dir.parent.parent 
    # test_image_path_obj = project_root / "tasks/llm_task/test.jpg"
    # For simplicity, let's assume test.jpg is in the same directory as base_task.py
    # test_image_path_obj = current_script_dir / test_image_relative_path

    # if not test_image_path_obj.exists():
    #     print(f"Error: Test image not found at {test_image_path_obj}")
    #     print("Please create a dummy 'test.jpg' in the same directory as this script or provide a valid path.")
        # Create a dummy one if it doesn't exist for testing
    #     try:
    #         from PIL import Image as PILImage, ImageDraw
    #         print(f"Attempting to create a dummy test image at {test_image_path_obj}...")
    #         img = PILImage.new('RGB', (200, 50), color = 'blue')
    #         d = ImageDraw.Draw(img)
    #         d.text((10,10), "Dummy Test Image", fill=(255,255,255))
    #         img.save(test_image_path_obj)
    #         print(f"Dummy test image created at {test_image_path_obj}")
    #     except Exception as e_img:
    #         print(f"Could not create dummy test image: {e_img}")
    #         exit(1) # Exit if no image can be found/created.

    # test_image_path_str = str(test_image_path_obj)
    
    # Config path - relative to the project root (med-rag-flow)
    # If running this script directly from `med-rag-flow/tasks/llm_task/`
    # then `config/...` should be `../../config/...`
    # For `unified_conversion_flow` default: "config/task/image_table_process.yaml"
    # This implies the flow is run from project root or paths are adjusted.
    # Let's calculate relative path from this script to project's config folder
    # project_root_config = current_script_dir.parent.parent / "config/task/image_table_process.yaml"

    # print(f"Using config file: {project_root_config}")
    # print(f"Using test image: {test_image_path_str}")

    # Example using the unified flow:
    # flow_results = unified_conversion_flow(
    #     image_path=test_image_path_str,
    #     context_for_caption="Sample context for describing the image.",
    #     config_path=str(project_root_config),
    #     do_table_conversion=True,
    #     do_image_captioning=True
    # )
    # print(f"\n--- Unified Flow Results ---")
    # if flow_results["table"]:
    #     print("\nTable Conversion Output:\n", flow_results["table"])
    # if flow_results["caption"]:
    #     print("\nImage Caption Output:\n", flow_results["caption"])

    # Example using the more granular (original-style) flows:
    # print("\n--- Granular Table Conversion Flow ---")
    # table_output = table_conversion_flow(
    #     image_path=test_image_path_str, 
    #     config_path=str(project_root_config)
    # )
    # print("Table output:\n", table_output)

    # print("\n--- Granular Image Captioning Flow ---")
    # caption_output = image_captioning_flow(
    #     image_path=test_image_path_str, 
    #     context="This is a test context for the image.",
    #     config_path=str(project_root_config)
    # )
    # print("Caption output:\n", caption_output)