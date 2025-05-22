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
        
        
        
# 剂量调整因数 - 使用 Auto/Smart mA 时的噪声指数调整方法
## 例如，若要计算基于已选 ASiR-V 级别的噪声指数 (NI) 的剂量减少，可将下表用于标准重建算法。
11-1 中的 “噪声指数调整因数”，旨在使用 AutomA 和 SmartmA 时帮助您输入 “噪声指数值”。这些因数来自带过滤的背面投影 (FBP) 和带较大 SFOV 的 0.625mm 厚度和 25 cm DFOV 带来的 20cm 水模型上 ASiR-V 之间测量噪声标准差 (SD) 之相对差，如下所示:
![The image displays a mathematical formula representing the Noise Index Factor, calculated as the ratio of σFB/P to σASIR.](E:\MySpeace\GE_MED_CHAT_BOT\med-rag-flow\data\processed\test01\images_RevolutionMaximaUserManualCN453-454/2757984ce0cada112a2b73dd8dd7cdd11ddebdb146b8176e895a16a161ed2bdf.jpg)
|ASiR-V级别|噪声指数因子|
|:---------|:----------|
|10%|1.09|
|20%|1.21|
|30%|1.34|
|40%|1.50|
|50%|1.70|
|60%|1.95|
|70%|2.26|
|80%|2.68|
|90%|3.25|
|100%|4.02|
例如，如果选择 $40 \%$ ASiR-V，将 mA 控制屏幕上显示的噪声指数数值乘以 1.50，如 11-1 所示，以获得使用ASiR-V 时协议的新噪声指数。需要在 mA 控制屏幕上的噪声指数 (NI) 字段输入此数值。
剂量调整因数 - 手动 mA 方法
例如，若要计算基于已选 ASiR-V 级别的 mA 的剂量减少，可将下表用于标准重建算法。11-2 中的 “mA 调整因数”，旨在帮助您在手动 mA 协议中输入 “噪声指数值”。这些因数基于 11-1 中的方形NI 调整因数的简单反转计算，如下所述:
方程 11-2: mA 因数