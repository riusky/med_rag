import base64
import re
import json
import sys
import io
from pathlib import Path
from PIL import Image
import requests

class TableImageConverter:
    def __init__(
        self,
        api_endpoint: str = "http://localhost:11434/v1/chat/completions",
        model_name: str = "gemma3:12b",
        system_prompt: str = None,
        timeout: int = 60
    ):
        self.api_endpoint = api_endpoint
        self.model_name = model_name
        self.timeout = timeout
        self.system_prompt = system_prompt or self._default_system_prompt()
        
        # 设置统一编码
        # sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

    def _default_system_prompt(self):
        return """作为专业表格转换专家，请严格遵守以下规则：
1. 【表格识别】
- 仅当图片包含表格结构时进行处理，否则返回固定语句："[非表格内容]"
- 精确识别行列结构，保持原始行列顺序
2. 【数据规范】
- 保留原始文本内容，包括标点符号和数字格式
- 缺失数据单元格统一用 ▁ 符号填充
- 转义Markdown特殊符号：| [ 等，其他符号保持原样
3. 【格式要求】
- 生成标准Markdown表格，格式要求：
| 列标题1      | 列标题2      |
|--------------|--------------|
| 内容对齐      | 自动换行      |

- 列宽对齐规则：
* 文字列使用左对齐 ：| :-------- |
* 数字列使用右对齐：| --------: |
* 混合列使用居中：| :-------: |
4. 【输出限制】
- 表格中不要出现图片格式 如果有有则用 '-' 代替
- 禁止添加任何说明性文字
- 表格行数必须与源数据完全一致
- 每行的列数必须与表头列数严格一致
5. 【异常处理】
- 模糊不清的文字标注为（模糊）
- 损坏的单元格标注为（损坏）
- 跨页表格保持连续，用 > 标记续表：| 续上表 > |
"""

    def convert(self, image_path: str) -> tuple[bool, str]:
        """主转换方法，返回（是否成功，结果/错误信息）"""
        try:
            # base64_image = self._encode_image(image_path)
            base64_image = self._validate_and_encode_image(image_path)
            payload = self._construct_payload(base64_image)
            response = self._send_request(payload)
            result = self._process_response(response)
            return True, result
        except Exception as e:
            print(str(e))
            return False, str(e)

    def generate_image_description(self, 
                                 image_path: str,
                                 context: str) -> str:
        """生成单行图片描述"""
        try:
            base64_image = self._encode_image(image_path)
            prompt = self._build_image_prompt(context)
            
            response = requests.post(
                self.api_endpoint,
                json={
                    "model": self.model_name,
                    "messages": [{
                        "role": "user",
                        "content": [
                            {"type": "text", "text": prompt},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_image}"
                                }
                            }
                        ]
                    }],
                    "temperature": 0.1,
                    "max_tokens": 1200
                },
                timeout=60
            )
            response.raise_for_status()
            
            return self._format_single_line(
                response.json()['choices'][0]['message']['content'],
                image_path
            )
            
        except Exception as e:
            return Path(image_path).stem  # 返回文件名作为降级方案

    def _build_image_prompt(self, context: str) -> str:
        """构建单行描述提示词"""
        return f"""请根据技术文档生成单行图片描述：

[关联上下文]
{context.strip()}

生成规则：
1. 结构：类型符号 + 标题/描述 + 关键参数（没有则不要填写）
2. 符号系统：
   🖥️=界面 📐=示意图 📊=数据图表 🔧=结构图
3. 参数格式： 没有则不要填写 数值(单位) 例：28.5mSv 
4. 示例：
   🖥️ 剂量设置 当前28.5mSv/上限35mSv
   📐 扫描床机械结构示意

输出要求：
- 严格单行（不要换行）
- 中文短语（不要完整句子）
- 字数≤100"""

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
            print("文件不存在")
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

    def _validate_image(self, image_path: str):
        """验证图片有效性（修复版）"""
        if not Path(image_path).exists():
            raise FileNotFoundError(f"图片文件不存在: {image_path}")
        
        try:
            # 直接读取文件内容至内存，避免文件句柄残留
            with open(image_path, "rb") as f:
                image_data = f.read()
            
            # 从内存加载验证图片，不依赖文件句柄
            with Image.open(io.BytesIO(image_data)) as img:
                img.verify()
        except Exception as e:
            raise ValueError(f"无效的图片文件: {str(e)}")

    def _encode_image(self, image_path: str) -> str:
        """Base64编码（修复版）"""
        self._validate_image(image_path)
        
        try:
            # 独立打开文件，确保句柄有效性
            with open(image_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
        except IOError as e:
            raise RuntimeError(f"文件读取失败: {image_path}, 错误: {str(e)}")

    def _construct_payload(self, base64_image: str) -> dict:
        """构建API请求体"""
        return {
            "model": self.model_name,
            "messages": [
                {
                    "role": "system",
                    "content": self.system_prompt
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "请将此表格图片转换为规范的Markdown格式文档"},
                        {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}},
                    ]
                }
            ],
            "temperature": 0.1,
            "max_tokens": 9600
        }

    def _send_request(self, payload: dict) -> requests.Response:
        """发送API请求"""
        try:
            response = requests.post(
                self.api_endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=self.timeout
            )
            response.raise_for_status()
            return response
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"API请求失败: {str(e)}")

    def _process_response(self, response: requests.Response) -> str:
        """处理响应（修改后抛出异常）"""
        try:
            response_data = response.json()

            print(response_data)
            
            # 校验响应结构
            if 'choices' not in response_data:
                raise ValueError("API响应缺少choices字段")
            if not response_data['choices']:
                raise ValueError("空响应内容")
            
            # 提取原始文本
            raw_text = response_data['choices'][0]['message']['content']
            
            # 处理代码块包裹的情况
            code_block_pattern = r'```(?:markdown)?\n(.*?)\n```'
            code_match = re.search(code_block_pattern, raw_text, re.DOTALL)
            
            # 如果包含代码块则提取内容
            if code_match:
                raw_text = code_match.group(1)
            
            # 调用表格提取方法
            return self._extract_markdown_table(raw_text)
        
        except json.JSONDecodeError:
            raise ValueError("无效的JSON格式响应")
        except Exception as e:
            raise ValueError(f"响应处理失败: {str(e)}")

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

if __name__ == "__main__":
    try:
        # 使用示例
        print("开始表格转换...")
        # 创建转换器实例
        converter = TableImageConverter()

        # 执行转换并获取状态
        status, result = converter.convert("test.jpg")

        if status:
            print("转换成功！")
            print("-" * 40)
            print(result)
            print("-" * 40)
        else:
            print(f"转换失败，原因：{result}")
    except Exception as e:
        print(f"\n错误发生: {str(e)}")
        sys.exit(1)