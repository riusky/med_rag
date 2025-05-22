from pathlib import Path
from prefect import get_run_logger, task, flow
import requests
from typing import Optional
import base64
import re
from PIL import Image
import io
import json
import yaml

from utils.config_loader import ConfigLoader


class TableImageConverterTasks:
    def __init__(self, config_path: str = "../../config/task/image_table_process.yaml"):
        self.config = ConfigLoader(config_path).config
        self.base_dir = Path(config_path).parent.parent.resolve()

    @task(
        name="validate-and-encode-image",
        description="图片验证与Base64编码任务",
        tags=["image-processing", "validation"],
    )
    def validate_and_encode_image_task(self, image_path: str) -> str:
        """执行图片验证和Base64编码"""
        path = Path(image_path)
        logger = get_run_logger()
        try:
            if not path.exists():
                raise FileNotFoundError(f"文件不存在: {image_path}")
                
            with open(path, "rb") as f:
                file_data = f.read()
                
            with Image.open(io.BytesIO(file_data)) as img:
                img.verify()
                
            logger.info(f"✅ 图片验证成功: {image_path}")
            return base64.b64encode(file_data).decode("utf-8")
            
        except Exception as e:
            logger.error(f"图片处理失败: {str(e)}")
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
        custom_user_prompt: Optional[str] = None  # 新增参数
    ) -> dict:
        """动态构建API请求体"""
        logger = get_run_logger()
        task_config = self.config['tasks'].get(task_name)
        
        if not task_config:
            raise ValueError(f"无效的任务名称: {task_name}")
            
        # 加载提示词文件
        prompt_content = self._load_prompt_content(task_config['prompt_file'])
        
        # 处理用户提示词逻辑
        user_text = custom_user_prompt or task_config.get(
            'user_prompt', 
            "解释这张图片"
        )
        
        payload_template = {
            "model": task_config.get('model_name', 'gemma3:12b'),
            "messages": [
                {
                    "role": "system",
                    "content": prompt_content
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_text},
                        {"type": "image_url", "image_url": {
                            "url": f"data:image/jpeg;base64,{base64_image}"
                        }}
                    ]
                }
            ],
            "temperature": task_config.get('temperature', 0.1),
            "max_tokens": task_config.get('max_tokens', 9600)
        }
        return payload_template

    @task(
        name="send-api-request",
        description="发送API请求任务",
        tags=["api", "communication"],
    )
    def send_api_request_task(self, payload: dict) -> requests.Response:
        """处理API通信及基础响应验证"""
        logger = get_run_logger()
        try:
            response = requests.post(
                self.config['global'].get('api_endpoint', 'http://localhost:11434/v1/chat/completions'),
                json=payload,
                timeout=self.config['global'].get('timeout', 60)
            )
            response.raise_for_status()
            logger.info("✅ API请求成功")
            return response
        except requests.exceptions.RequestException as e:
            logger.error(f"API通信失败: {str(e)}")
            raise e from None

    @task(
        name="process-api-response",
        description="处理API响应任务",
        tags=["response", "processing"]
    )
    def process_api_response_task(self, response: requests.Response) -> str:
        """增强型响应处理管道"""
        logger = get_run_logger()
        try:
            response_data = response.json()
            if 'choices' not in response_data:
                raise ValueError("无效响应结构: 缺少choices字段")
                
            raw_text = response_data['choices'][0]['message']['content']
            
            processed = self._enhanced_response_cleaning(raw_text)
            logger.info(f"✅ 响应处理完成 | 有效内容长度: {len(processed)}")
            logger.info(f"✅ {processed}")
            return processed
            
        except json.JSONDecodeError:
            logger.error("响应解析失败: 非JSON格式")
            raise
        except Exception as e:
            logger.error(f"响应处理异常: {str(e)}")
            raise

    @task(
        name="generate-markdown-table",
        description="生成Markdown表格任务",
        tags=["formatting", "output"]
    )
    def generate_markdown_table_task(self, processed_text: str) -> str:
        """专业的表格格式化引擎"""
        logger = get_run_logger()
        try:
            table = self._structured_table_extraction(processed_text)
            return table
        except ValueError as ve:
            logger.error(f"表格生成失败: {str(ve)}")
            raise
          
    @task(
        name="process_caption_response",
        description="处理图片描述API响应任务",
        tags=["response", "processing"]
    )
    def process_caption_response(self, response: requests.Response) -> str:
        """处理图片描述响应"""
        logger = get_run_logger()
        try:
            response_data = response.json()
            logger.debug(f"原始响应长度: {len(response.text)}")
            
            if 'choices' not in response_data:
                raise ValueError("无效响应结构: 缺少choices字段")
                
            raw_text = response_data['choices'][0]['message']['content']
            return raw_text
            
        except json.JSONDecodeError:
            logger.error("响应解析失败: 非JSON格式")
            raise
        except Exception as e:
            logger.error(f"响应处理异常: {str(e)}")
            raise

    # ------------------ 私有工具方法 ------------------
    def _load_prompt_content(self, prompt_file: str) -> str:
        """从独立文件加载提示词"""
        try:
            prompt_path = self.base_dir / prompt_file
            if not prompt_path.exists():
                raise FileNotFoundError(f"提示词文件不存在: {prompt_path}")
                
            with open(prompt_path, 'r', encoding='utf-8') as f:
                content = f.read().strip()
            if not content:
                raise ValueError("提示词文件内容为空")
                
            return content
            
        except Exception as e:
            raise

    def _enhanced_response_cleaning(self, raw_text: str) -> str:
        """多阶段响应清洗流程"""
            # 处理代码块包裹的情况
        code_block_pattern = r'```(?:markdown)?\n(.*?)\n```'
        code_match = re.search(code_block_pattern, raw_text, re.DOTALL)
        
        # 如果包含代码块则提取内容
        if code_match:
            raw_text = code_match.group(1)
        
        return raw_text

    def _structured_table_extraction(self, raw_text: str) -> str:
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
            if simple_match := re.search(simple_pattern, raw_text, re.MULTILINE):
                print("检测到简单表格结构")
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
            .replace(' ', '')    # 移除汉字间空格
            .replace('｜', '|')  # 统一竖线符号
            .replace('—', '-')   # 统一分隔线
            .replace('∶', ':')   # 统一冒号
        )
        
        # 分割行并过滤空行
        lines = [line.strip() for line in cleaned_table.splitlines() if line.strip()]
        
        # 验证表格完整性
        if len(lines) < 3:
            raise ValueError("表格行数不足")
        
        # 重新组装表格确保格式正确
        return '\n'.join(lines)

# ------------------ Flow构建 ------------------
@flow
def create_flow(config_path: str = "../../config/task/image_table_process.yaml"):
    """创建Prefect工作流"""
    converter = TableImageConverterTasks(config_path)
    
    # 输入参数
    image_path = "test.jpg"
    
    # 公共处理流程
    encoded_image = converter.validate_and_encode_image_task(image_path)
    
    # 表格转换子流程
    table_payload = converter.construct_payload_task(encoded_image, task_name="table_conversion")
    table_response = converter.send_api_request_task(table_payload)
    processed_text = converter.process_api_response_task(table_response)  # 新增处理步骤
    table_result = converter.generate_markdown_table_task(processed_text)  # 修正输入参数
    
    # 图片描述子流程 
    desc_payload = converter.construct_payload_task(encoded_image, task_name="image_caption")
    desc_response = converter.send_api_request_task(desc_payload)
    desc_processed = converter.process_caption_response(desc_response)  # 新增处理步骤
    
if __name__ == "__main__":
    create_flow()