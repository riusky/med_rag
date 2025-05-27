import base64
import re
import json
import sys
import io
from pathlib import Path
from PIL import Image
import requests

from med_rag_flow.utils.config_loader import ConfigLoader # Added import

class TableImageConverter:
    def __init__(
        self,
        config_path: str = "config/task/image_table_process.yaml", # Changed default config path
    ):
        self.config_loader = ConfigLoader(config_path)
        self.config = self.config_loader.config
        self.base_dir = Path(config_path).parent.parent.resolve() # Added base_dir

        self.api_endpoint = self.config['global']['api_endpoint']
        self.model_name = self.config['global']['model_name']
        self.timeout = self.config['global']['timeout']
        
        # Load prompts from files specified in config
        self.table_conversion_system_prompt = self._load_prompt_content(
            self.config['tasks']['table_conversion']['prompt_file']
        )
        self.image_caption_prompt_template = self._load_prompt_content(
            self.config['tasks']['image_caption']['prompt_file']
        )

    def _load_prompt_content(self, prompt_file: str) -> str:
        """从独立文件加载提示词"""
        try:
            # Resolve prompt_file path relative to the config file's base directory
            prompt_path = self.base_dir / prompt_file
            if not prompt_path.exists():
                raise FileNotFoundError(f"提示词文件不存在: {prompt_path}")
                
            with open(prompt_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            if not content:
                raise ValueError("提示词文件内容为空")
                
            return content
            
        except Exception as e:
            # Consider logging the error here instead of just raising
            raise

    def convert(self, image_path: str, task_name: str = "table_conversion") -> tuple[bool, str]: # Added task_name
        """主转换方法，返回（是否成功，结果/错误信息）"""
        try:
            base64_image = self._validate_and_encode_image(image_path)
            # Pass task_name to _construct_payload
            payload = self._construct_payload(base64_image, task_name=task_name) 
            response = self._send_request(payload)
            # Pass task_name to _process_response if needed, or handle specific logic
            result = self._process_response(response, task_name=task_name) 
            return True, result
        except Exception as e:
            # It's good practice to log the exception here
            # import logging
            # logging.error(f"Conversion failed for {image_path}: {e}", exc_info=True)
            print(str(e)) # Keep print for now as per original code
            return False, str(e)

    def generate_image_description(self, 
                                 image_path: str,
                                 context: str,
                                 task_name: str = "image_caption" # Added task_name
                                 ) -> str:
        """生成单行图片描述"""
        try:
            base64_image = self._validate_and_encode_image(image_path) # Changed from _encode_image
            # Construct payload using the generalized method
            # The user prompt for image caption needs to be constructed with context
            user_prompt_for_caption = self._build_image_prompt(context)
            
            payload = self._construct_payload(
                base64_image,
                task_name=task_name,
                custom_user_prompt=user_prompt_for_caption 
            )
            
            response = self._send_request(payload) # Use the generalized send_request
            
            # Process response using the generalized method, then format
            raw_description = self._process_response(response, task_name=task_name)
            
            return self._format_single_line(raw_description, image_path)
            
        except Exception as e:
            # Log error
            # import logging
            # logging.error(f"Image description generation failed for {image_path}: {e}", exc_info=True)
            return Path(image_path).stem  # 返回文件名作为降级方案

    def _build_image_prompt(self, context: str) -> str:
        """构建单行描述提示词 using the template from config"""
        # The template loaded in __init__ is self.image_caption_prompt_template
        # We need to ensure this template has a placeholder for context if needed,
        # or prepend/append context as per existing logic.
        # Current template seems to be just a generic instruction.
        # The original code prepends context to a fixed string.
        # Let's adapt to use the loaded template and prepend context.
        # This might need adjustment based on actual template content.
        return f"{self.image_caption_prompt_template}\n\n[关联上下文]\n{context.strip()}"

    def _format_single_line(self, text: str, image_path: str) -> str:
        """格式化单行描述"""
        # 清理特殊字符
        cleaned = re.sub(r'[“”‘’]', '', text.strip())
        # 提取有效部分
        match = re.search(r'([🖥️📐📊🔧]) ([\w\u4e00-\u9fa5\- ]+?)( \S+)*$', cleaned)
        
        if match:
            parts = [p for p in match.groups() if p]
            return ' '.join(parts).strip()
        # 降级处理
        return f"🔧 {Path(image_path).stem}"

    def _validate_and_encode_image(self, image_path: str) -> str:
        """统一处理文件验证与编码"""
        path = Path(image_path)
        
        # 基础验证
        if not path.exists():
            # Consider logging
            raise FileNotFoundError(f"文件不存在: {image_path}")
        if not path.is_file():
            raise ValueError(f"路径不是文件: {image_path}")
        
        try:
            # 单次读取操作
            with open(path, "rb") as f:
                file_data = f.read()
            
            # 内存验证
            with Image.open(io.BytesIO(file_data)) as img:
                img.verify()  # 验证图像完整性
                
            # 返回编码结果
            return base64.b64encode(file_data).decode("utf-8")
            
        except PermissionError:
            raise RuntimeError(f"文件访问权限不足: {image_path}")
        except Image.UnidentifiedImageError:
            raise ValueError("无法识别的图像格式")
        except Exception as e:
            raise RuntimeError(f"文件处理异常: {str(e)}")

    # _validate_image and _encode_image are effectively replaced by _validate_and_encode_image
    # We can remove them if they are no longer used internally or externally.
    # For now, I'll keep them commented out in case they were used by other parts not visible yet.
    # def _validate_image(self, image_path: str):
    #     """验证图片有效性（修复版）"""
    #     ...
    # def _encode_image(self, image_path: str) -> str:
    #     """Base64编码（修复版）"""
    #     ...

    def _construct_payload(self, 
                           base64_image: str, 
                           task_name: str, # Expects "table_conversion" or "image_caption"
                           custom_user_prompt: str = None 
                           ) -> dict:
        """动态构建API请求体 based on task_name from config"""
        task_config = self.config['tasks'].get(task_name)
        if not task_config:
            raise ValueError(f"无效的任务名称: {task_name}")

        # Determine system prompt based on task
        if task_name == "table_conversion":
            system_prompt_content = self.table_conversion_system_prompt
        elif task_name == "image_caption":
            # Image captioning might not use a "system" prompt in the same way,
            # or its main prompt is passed as user content.
            # For now, let's assume image_caption's prompt is primarily user-driven
            # and the self.image_caption_prompt_template is part of the user prompt.
            # If a dedicated system prompt for captions is needed, it should be configured.
            system_prompt_content = task_config.get('system_prompt', "") # Allow empty or specific system prompt
        else:
            # Fallback or error for unknown task type
            raise ValueError(f"未知的任务类型 {task_name}，无法确定系统提示词")

        # User prompt: use custom if provided, else from config, else default.
        user_text = custom_user_prompt or task_config.get(
            'user_prompt', 
            "请处理这张图片" # A more generic default
        )
        
        return {
            "model": task_config.get('model_name', self.model_name), # Fallback to global model_name
            "messages": [
                {
                    "role": "system",
                    "content": system_prompt_content
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                    ]
                }
            ],
            "temperature": task_config.get('temperature', 0.1),
            "max_tokens": task_config.get('max_tokens', 9600)
        }

    def _send_request(self, payload: dict) -> requests.Response:
        """发送API请求, uses api_endpoint from config"""
        try:
            response = requests.post(
                self.api_endpoint, # api_endpoint is now from config
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout # timeout is now from config
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"API请求失败: {str(e)}")

    def _process_response(self, response: requests.Response, task_name: str) -> str:
        """处理响应 based on task_name"""
        try:
            response_data = response.json()
            
            # Consider logging response_data for debugging if needed
            # print(response_data) 
            
            if 'choices' not in response_data or not response_data['choices']:
                raise ValueError("API响应无效或为空")
            
            raw_text = response_data['choices'][0]['message']['content']
            
            if task_name == "table_conversion":
                # For table conversion, extract from markdown block and then extract table
                code_block_pattern = r'```(?:markdown)?\n(.*?)\n```'
                code_match = re.search(code_block_pattern, raw_text, re.DOTALL)
                if code_match:
                    raw_text = code_match.group(1)
                return self._extract_markdown_table(raw_text)
            elif task_name == "image_caption":
                # For image caption, the raw_text is likely the description itself
                # No special table extraction needed.
                # Additional cleaning specific to captions could be done here if necessary.
                return raw_text.strip() 
            else:
                raise ValueError(f"未知任务类型 {task_name}，无法处理响应")
        
        except json.JSONDecodeError:
            raise ValueError("无效的JSON格式响应")
        except Exception as e:
            raise ValueError(f"响应处理失败: {str(e)}")

    # This method remains static if it doesn't need instance data (config, etc.)
    # If it might need configuration in the future, it could be non-static.
    @staticmethod
    def _extract_markdown_table(raw_text: str) -> str:
        """修复版表格提取方法，解决末行丢失问题"""
        # 增强正则表达式兼容性
        table_pattern = (
            r'^\s*'                    # 允许起始空白
            r'(\|.*\|)\s*\n'           # 表头行
            r'(\|[-:\s|]+\|)\s*\n'     # 分隔线行
            r'((?:\|.*\|\s*\n?)+)'     # 数据行（包含最后可能没有换行符的情况）
            r'\s*$'                    # 允许结尾空白
        )

        match = re.search(table_pattern, raw_text, re.MULTILINE | re.DOTALL)
        
        if not match:
            # 尝试匹配无分隔线的简单表格
            simple_pattern = r'^(\|.*\|)\s*\n((?:\|.*\|\s*\n?)+)'
            # Python 3.8+ assignment expression `:=`
            simple_match = re.search(simple_pattern, raw_text, re.MULTILINE)
            if simple_match:
                # Consider logging "检测到简单表格结构"
                header = simple_match.group(1)
                rows = simple_match.group(2)
                processed = f"{header}\n{rows}"
            else:
                raise ValueError("未检测到有效的Markdown表格结构")
        else:
            # 合并所有匹配部分
            processed = f"{match.group(1)}\n{match.group(2)}\n{match.group(3)}"

        # 标准化处理流程
        cleaned_table = (
            processed.strip()
            # .replace(' ', '')    # Removing all spaces might be too aggressive for some tables
            .replace('｜', '|')  # 统一竖线符号
            .replace('—', '-')   # 统一分隔线
            .replace('∶', ':')   # 统一冒号
        )
        
        # 分割行并过滤空行
        lines = [line.strip() for line in cleaned_table.splitlines() if line.strip()]
        
        # 验证表格完整性
        if len(lines) < 2: # A table needs at least a header and one row of data (or header + separator)
            raise ValueError("表格行数不足 (至少需要表头和数据行/分隔行)")
        
        # 重新组装表格确保格式正确
        return '\n'.join(lines)

if __name__ == "__main__":
    try:
        # 使用示例
        print("开始表格转换...")
        # 创建转换器实例, assuming config is in the default path relative to this script if run directly
        # This might need adjustment if the script is not in `med-rag-flow/utils/`
        # For testing, provide a relative path from where you run this script,
        # or an absolute path to 'config/task/image_table_process.yaml'
        
        # Determine the project root directory to construct the config path
        # This assumes the script is run from within the project structure.
        current_script_path = Path(__file__).resolve()
        # Example: med-rag-flow/utils/table_image_converter.py -> med-rag-flow
        project_root = current_script_path.parent.parent 
        config_file_path = project_root / "config/task/image_table_process.yaml"
        
        # Ensure test.jpg exists in the same directory as this script, or provide a full path.
        test_image_path = current_script_path.parent / "test.jpg" # Assuming test.jpg is in utils
        # If test.jpg is in med-rag-flow/tasks/llm_task/test.jpg as before:
        # test_image_path = project_root / "tasks/llm_task/test.jpg"


        if not config_file_path.exists():
            print(f"配置文件不存在: {config_file_path}")
            sys.exit(1)
        
        if not test_image_path.exists():
            # Create a dummy test.jpg if it doesn't exist for the sake of running the example
            try:
                print(f"测试图片 {test_image_path} 不存在，尝试创建...")
                from PIL import Image as PILImage, ImageDraw
                img = PILImage.new('RGB', (100, 30), color = 'red')
                d = ImageDraw.Draw(img)
                d.text((10,10), "Test", fill=(255,255,0))
                img.save(test_image_path)
                print(f"虚拟测试图片 {test_image_path} 已创建。")
            except Exception as img_e:
                print(f"无法创建虚拟测试图片: {img_e}")
                sys.exit(1)


        converter = TableImageConverter(config_path=str(config_file_path))

        # 执行转换并获取状态
        # Assuming test.jpg is in a location accessible by the script
        # The original test.jpg was in tasks/llm_task/test.jpg
        status, result = converter.convert(str(test_image_path))


        if status:
            print("转换成功！")
            print("-" * 40)
            print(result)
            print("-" * 40)
        else:
            print(f"转换失败，原因：{result}")

        print("\n开始图片描述生成...")
        # Example context, replace with actual context if available
        example_context = "这是一个关于医疗设备的文档中的图片。"
        description = converter.generate_image_description(str(test_image_path), example_context)
        print(f"图片描述: {description}")

    except Exception as e:
        print(f"\n错误发生: {str(e)}")
        sys.exit(1)

# TODO: Move the following test/demonstration code to proper unit tests under the tests/ directory.
# if __name__ == "__main__":
#     try:
#         # 使用示例
#         print("开始表格转换...")
#         # 创建转换器实例, assuming config is in the default path relative to this script if run directly
#         # This might need adjustment if the script is not in `med-rag-flow/utils/`
#         # For testing, provide a relative path from where you run this script,
#         # or an absolute path to 'config/task/image_table_process.yaml'
        
#         # Determine the project root directory to construct the config path
#         # This assumes the script is run from within the project structure.
#         current_script_path = Path(__file__).resolve()
#         # Example: med-rag-flow/utils/table_image_converter.py -> med-rag-flow
#         project_root = current_script_path.parent.parent 
#         config_file_path = project_root / "config/task/image_table_process.yaml"
        
#         # Ensure test.jpg exists in the same directory as this script, or provide a full path.
#         test_image_path = current_script_path.parent / "test.jpg" # Assuming test.jpg is in utils
#         # If test.jpg is in med-rag-flow/tasks/llm_task/test.jpg as before:
#         # test_image_path = project_root / "tasks/llm_task/test.jpg"


#         if not config_file_path.exists():
#             print(f"配置文件不存在: {config_file_path}")
#             sys.exit(1)
        
#         if not test_image_path.exists():
#             # Create a dummy test.jpg if it doesn't exist for the sake of running the example
#             try:
#                 print(f"测试图片 {test_image_path} 不存在，尝试创建...")
#                 from PIL import Image as PILImage, ImageDraw
#                 img = PILImage.new('RGB', (100, 30), color = 'red')
#                 d = ImageDraw.Draw(img)
#                 d.text((10,10), "Test", fill=(255,255,0))
#                 img.save(test_image_path)
#                 print(f"虚拟测试图片 {test_image_path} 已创建。")
#             except Exception as img_e:
#                 print(f"无法创建虚拟测试图片: {img_e}")
#                 sys.exit(1)


#         converter = TableImageConverter(config_path=str(config_file_path))

#         # 执行转换并获取状态
#         # Assuming test.jpg is in a location accessible by the script
#         # The original test.jpg was in tasks/llm_task/test.jpg
#         status, result = converter.convert(str(test_image_path))


#         if status:
#             print("转换成功！")
#             print("-" * 40)
#             print(result)
#             print("-" * 40)
#         else:
#             print(f"转换失败，原因：{result}")

#         print("\n开始图片描述生成...")
#         # Example context, replace with actual context if available
#         example_context = "这是一个关于医疗设备的文档中的图片。"
#         description = converter.generate_image_description(str(test_image_path), example_context)
#         print(f"图片描述: {description}")

#     except Exception as e:
#         print(f"\n错误发生: {str(e)}")
#         sys.exit(1)