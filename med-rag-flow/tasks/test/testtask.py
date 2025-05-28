# 混合分块 (Hybrid Chunking)

# 首先尝试基于文档结构（如 Markdown 标题）进行高级别分割，
# 然后在这些较大的分割块内部，如果它们仍然超过了目标大小，
# 再使用递归字符分块或句子分块进行细粒度的切分。

from prefect import task, get_run_logger
from tasks.core import register_task

# ------------------------ 核心处理任务 ------------------------
@register_task(
    key="text_upper",
    description="单文件处理的task",
)
@task(name="print_text_task")
def text_upper(text: str) -> str:
    """返回处理后的文本"""
    processed = f"{text.upper()}"
    print(f"处理结果: {processed}")
    return processed
  
@register_task(
    key="text_lower",
    description="单文件处理的task",
)
@task(name="print_text_task")
def text_lower(text: str) -> str:
    """返回处理后的文本"""
    processed = f"{text.lower()}"
    print(f"处理结果: {processed}")
    return processed