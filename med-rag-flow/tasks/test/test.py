from typing import List, Dict, Any
import json
import re
import logging
from tenacity import retry, stop_after_attempt, wait_exponential
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_ollama import OllamaLLM
from prefect import task

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@task(name="optimized_propositional_chunking")
def optimized_propositional_chunking(
    content: str,
    chunk_size: int = 512,
    chunk_overlap: int = 64,
    llm_model: str = "deepseek-r1:1.5b",
    temperature: float = 0.1,  # 降低随机性
    max_length: int = 1024,
    base_url: str = "http://localhost:11434",
    min_confidence: float = 0.7,
    max_retries: int = 3
) -> List[Dict[str, Any]]:
    """
    优化版命题分块任务
    
    主要改进：
    1. 增强提示词约束
    2. 严格响应解析
    3. 强化质量过滤
    """
    try:
        # 初始化带重试机制的Ollama客户端
        @retry(stop=stop_after_attempt(max_retries), 
              wait=wait_exponential(multiplier=1, min=1, max=10))
        def get_llm():
            return OllamaLLM(
                model=llm_model,
                base_url=base_url,
                temperature=temperature,
                num_predict=max_length,
                system="""
                请严格按以下要求处理文本：
                1. 直接输出事实性命题，不要包含任何分析过程
                2. 每个命题必须满足：
                   - 包含完整的主谓宾结构
                   - 以编号列表形式输出(如：1. 命题内容)
                   - 长度10-80字符
                3. 禁止使用JSON或自然语言解释

                示例输入：
                特斯拉Cybertruck续航402英里，0-60mph加速2.6秒。

                示例输出：
                1. 特斯拉Cybertruck续航里程为402英里
                2. Cybertruck的0-60mph加速时间为2.6秒
                """
            )

        llm = get_llm()
        logger.info(f"Initialized model: {llm_model}")

        # 配置分块器
        text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "。", "；", "\n"],  # 优化中文分隔符
            length_function=len,
            is_separator_regex=False
        )

        # 分块处理
        docs = [Document(page_content=content)]
        chunks = text_splitter.split_documents(docs)
        logger.info(f"Split into {len(chunks)} chunks")

        # 处理分块
        propositions = []
        pattern = re.compile(r"^\d+\.\s+(.+)$")  # 匹配编号命题
        
        for chunk_id, chunk in enumerate(chunks, 1):
            chunk_text = chunk.page_content.strip()
            if not chunk_text:
                continue

            try:
                response = llm.invoke(f"输入文本：{chunk_text}")
                
                # 严格解析响应
                valid_props = []
                for line in response.split('\n'):
                    if match := pattern.match(line.strip()):
                        prop_text = match.group(1)
                        if 10 <= len(prop_text) <= 80:
                            valid_props.append(prop_text)

                # 质量过滤
                filtered_props = [
                    p for p in valid_props
                    if not re.search(r"(思考|分析|需要|应该)", p)  # 关键词黑名单
                    and any(c in p for c in ["为", "是", "有"])  # 语法检查
                ]

                # 置信度计算
                for prop in filtered_props:
                    score = min(len(prop)/60 + 0.3, 1.0)  # 基于长度
                    if score >= min_confidence:
                        propositions.append({
                            "text": prop,
                            "source_chunk": chunk_id,
                            "confidence": round(score, 2),
                            "model": llm_model,
                            "length": len(prop)
                        })

            except Exception as e:
                logger.error(f"Chunk {chunk_id} error: {str(e)}")
                continue

        logger.info(f"Generated {len(propositions)} valid propositions")
        return propositions

    except Exception as e:
        logger.error(f"Process failed: {str(e)}")
        return []

if __name__ == "__main__":
    sample_text = """特斯拉Cybertruck于2023年12月1日开始交付，该车型采用Ultra-Hard 30X冷轧不锈钢外壳，
                    单次充电续航里程可达402英里（约647公里）。其0-60mph加速时间仅为2.6秒，
                    最高牵引力达到11,000磅。"""
    
    result = optimized_propositional_chunking(
        sample_text,
        llm_model="deepseek-r1:1.5b",
        chunk_size=300
    )
    
    print("\n优化后的命题：")
    for item in result:
        print(f"[Chunk {item['source_chunk']}] {item['text']}")
        print(f"  Confidence: {item['confidence']} | Length: {item['length']} chars\n")
 