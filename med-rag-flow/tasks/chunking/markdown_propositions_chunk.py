
from collections import defaultdict
import copy
import os
import sys
from langchain.schema import Document
from typing import List, Dict, Any

# 获取项目根目录路径（假设文件在 med-rag-flow/tasks/ 目录下）
root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(root_dir)

from tasks.helper_function import *
from prefect import task, get_run_logger
from langchain_experimental.text_splitter import SemanticChunker
import re
from langchain_ollama import OllamaLLM
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.output_parsers import StrOutputParser
from json import loads

# 提示模板
evaluation_prompt_template = """
请根据以下标准评估命题：
- **准确性**：根据命题反映原文的程度，从1 - 10进行评分。
- **清晰度**：根据在不借助额外上下文的情况下理解命题的难易程度，从1 - 10进行评分。
- **完整性**：根据命题是否包含必要细节（例如日期、限定词），从1 - 10进行评分。
- **简洁性**：根据命题是否简洁且未丢失重要信息，从1 - 10进行评分。

示例输出：
```json
[{{
  "accuracy": 8,
  "clarity": 7,
  "completeness": 6,
  "conciseness": 8
}}
]
```

"""


class PropositionQuality(BaseModel):
    """命题质量评分结构"""
    accuracy: int = Field(ge=1, le=10, description="准确性评分")
    clarity: int = Field(ge=1, le=10, description="清晰度评分")
    completeness: int = Field(ge=1, le=10, description="完整度评分")
    conciseness: int = Field(ge=1, le=10, description="简洁性评分")


# ================== 数据结构 ==================
class GeneratedPropositions(BaseModel):
    propositions: List[str]
    metadata: Dict[str, Any]

@task(name="proposition")
def propositions(
    chunks: List[Document],
    model: str = "deepseek-r1:1.5b",
    temperature: float = 0,
    max_retries: int = 3
) -> List[Document]:
    """
    修复版命题生成，兼容未实现with_structured_output的环境
    
    改进点：
    1. 自定义输出解析器
    2. 增强格式容错处理
    3. 保留元数据继承
    """
    logger = get_run_logger()
    all_results = []
    
    # 初始化模型（移除结构化输出依赖）
    llm = OllamaLLM(
        model=model,
        base_url="http://localhost:11434",
        temperature=temperature,
        num_predict=9600,
    )
    
    for chunk in chunks:
        def process_chunk():
            try:
                # 构建上下文提示词
                prompt = f"""
请将以下文本分解为简单、独立的小命题。生成的小命题要包含整个文本的内容。确保每个小命题符合以下标准：

1. 表达单一事实：每个小命题应陈述一个特定的事实或主张。
2. 无需上下文即可理解：小命题应是独立的，即无需额外上下文即可理解。
3. 使用全称而非代词：避免使用代词或含糊的指代；使用完整的实体名称。
4. 包含相关日期/限定词：如适用，包含必要的日期、时间和限定词以使事实精确。
5. 包含一个主谓关系：专注于单一主体及其相应的动作或属性，不使用连词或多个从句。
6. 如果提供的分解文本内容（仅包含页码信息和注释或者其他无法命题分解的内容），无法提取有效的内容进行小命题分解时固定输出：无法提取有效的命题

示例输入：
2020年，XYZ公司生产的CT-2000型CT扫描仪获得FDA认证，该设备采用的低剂量成像技术可减少患者50%的辐射暴露。

示例输出格式：
```markdown
1. CT扫描仪属于医疗成像设备分类
2. XYZ公司是CT-2000型CT扫描仪的生产商
3. CT-2000型CT扫描仪于2020年获得FDA认证
4. CT-2000型CT扫描仪集成低剂量成像技术
5. 低剂量成像技术可使患者辐射暴露减少50%


需要分解的文本:
{chunk.page_content}
"""
                # 生成响应
                response = llm.invoke(prompt)
                # 解析命题
                cleaned_response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
                if not cleaned_response.strip() or "无法提取有效的命题" in cleaned_response:
                    return copy.deepcopy(chunk)
                   
                lines = [line.strip() for line in cleaned_response.splitlines() if line.strip()]
                processed_response = '\n'.join(lines)
                print(processed_response)
                # 克隆文档并更新内容
                new_doc = copy.deepcopy(chunk)
                new_doc.page_content = processed_response
                
                new_doc = evaluate_propositions(chunk,new_doc)
                return new_doc
                
            except Exception as e:
                logger.error(
                    "分块处理异常 - 元数据: %s, 错误: %s", 
                    chunk.metadata, 
                    str(e)
                )
                raise
        all_results.append(process_chunk())
    return all_results


# ================== 质量评估模块 ==================  
@task(name="proposition_evaluation")
def evaluate_propositions(
    original_doc: Document,
    generated_doc: Document,
    model: str = "deepseek-r1:1.5b",
    thresholds: dict = {"accuracy": 7, "clarity": 7, "completeness": 7, "conciseness": 7}
) -> Document:
    """
    全量命题整体评估版本
    功能特点：
    1. 直接对比完整原文和完整生成命题
    2. 单次评估所有命题的整体质量
    3. 阈值判断基于整体评分
    """
    logger = get_run_logger()

    # 初始化Ollama模型
    llm = OllamaLLM(
        model=model,
        base_url="http://localhost:11434",
        temperature=0,
        num_predict=4096,
        format="json",
    )

    # 构建评估提示模板
    evaluation_prompt = ChatPromptTemplate.from_messages([
        ("system", evaluation_prompt_template),
        ("human", """
请整体评估以下命题集合：
{proposition}

对应的原始文本：
{original_text}""")
    ])

    # 评分模型
    class CompositeScores(BaseModel):
        accuracy: int
        clarity: int
        completeness: int
        conciseness: int

    def safe_parse(text: str) -> CompositeScores:
        try:
            data = loads(text)  # 处理单引号问题
            return CompositeScores(**data)
        except Exception as e:
            logger.error(f"解析失败: {str(e)}\n原始响应: {text}")
            raise

    # 构建处理链
    evaluator_chain = (
        evaluation_prompt 
        | llm 
        | StrOutputParser() 
        | safe_parse
    )

    try:
        # 执行整体评估
        scores = evaluator_chain.invoke({
            "proposition": generated_doc.page_content,
            "original_text": original_doc.page_content
        })
        
        # 阈值判断逻辑
        passed = all([
            scores.accuracy >= thresholds["accuracy"],
            scores.clarity >= thresholds["clarity"],
            scores.completeness >= thresholds["completeness"],
            scores.conciseness >= thresholds["conciseness"]
        ])

        # 记录评估结果
        generated_doc.metadata["quality_scores"] = scores.dict()
        generated_doc.metadata["evaluation_passed"] = passed
        
        return generated_doc if passed else original_doc

    except Exception as e:
        logger.error("评估流程异常: %s", str(e))
        original_doc.metadata["evaluation_error"] = str(e)
        return original_doc
