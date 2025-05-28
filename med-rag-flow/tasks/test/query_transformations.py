import re
import traceback
from langchain.prompts import PromptTemplate
from langchain_ollama import ChatOllama, OllamaLLM


def rewrite_query(
    original_query: str,
    query_template: str = """你是一名人工智能助手，负责改写用户查询以改进检索增强生成（RAG）系统中的信息检索。给定原始查询，将其改写得更具体、详细，且更有可能检索到相关信息：
    
原始查询：{original_query}
""",
    model: str = "deepseek-r1:1.5b",
    temperature: float = 0,
    num_predict: int = 4096
) -> str:
    """
    单函数实现查询重写
    
    参数：
    original_query: 需要优化的原始查询
    query_template: 重写模板（必须包含{original_query}占位符）
    model: 使用的Ollama模型名称
    temperature: 生成温度
    num_predict: 最大生成长度
    
    返回：
    优化后的查询字符串
    """
    # 初始化模型
    llm = OllamaLLM(
        model=model,
        base_url="http://localhost:11434",
        temperature=temperature,
        num_predict=num_predict
    )
    
    # 创建处理链
    chain = PromptTemplate.from_template(query_template) | llm
    raw_response = chain.invoke({"original_query": original_query}).strip()
        # 清洗内容：1.去除<think>标签 2.去除空行 3.去除首尾空格
    cleaned_response = re.sub(r'<think>.*?</think>', '', raw_response, flags=re.DOTALL)
    cleaned_response = re.sub(r'\n\s*\n', '\n', cleaned_response).strip()
    
    return cleaned_response




def generate_step_back_query(
    original_query: str,
    model: str = "llama3",
    temperature: float = 0,  # 适当保留多样性
    num_predict: int = 2000,
    step_back_template: str = """你是一个人工智能助手，负责生成更宽泛、更通用的广义查询语句，以提高检索增强生成（RAG）系统中的上下文检索能力。
给定原始查询语句，生成一个广义查询语句，该语句应更宽泛，且有助于检索相关背景信息。

原始查询语句：{original_query}

直接输出广义查询语句。
"""
) -> str:
    """
    生成回溯查询的Ollama实现
    
    参数：
    original_query: 需要扩展的具体查询
    model: 本地模型名称（默认llama3）
    temperature: 生成多样性控制
    num_predict: 最大生成长度
    step_back_template: 回溯查询模板
    
    返回：
    优化后的广义查询
    """
    # 初始化本地模型
    llm = OllamaLLM(
        model=model,
        base_url="http://localhost:11434",
        temperature=temperature,
        num_predict=num_predict
    )
    
    # 构建处理链
    chain = (
        PromptTemplate.from_template(step_back_template) 
        | llm
    )
    raw_response = chain.invoke({"original_query": original_query}).strip()
        # 清洗内容：1.去除<think>标签 2.去除空行 3.去除首尾空格
    cleaned_response = re.sub(r'<think>.*?</think>', '', raw_response, flags=re.DOTALL)
    cleaned_response = re.sub(r'\n\s*\n', '\n', cleaned_response).strip()
    
    return cleaned_response    # 执行查询






def decompose_query(
    original_query: str,
    decomposition_template: str = """作为信息检索专家，请将复杂查询分解为2-4个原子子查询：

原始查询：{original_query}

示例：
输入：气候变化对环境的影响有哪些？
输出：
1. 气候变化如何影响生物多样性？
2. 海洋系统受到气候变化的哪些影响？
3. 气候变化对农业生产的具体作用机制？
4. 极端天气事件与全球变暖的关联性如何？

请为以下查询生成子查询：""",
    model: str = "deepseek-r1:14b",
    temperature: float = 0,
    num_predict: int = 4096
) -> list:
    """
    改进版查询分解方法（模板参数化）
    
    参数：
    original_query: 需要分解的复杂查询
    decomposition_template: 分解模板（必须包含{original_query}占位符）
    model: 本地模型名称
    temperature: 生成多样性
    num_predict: 最大生成长度
    
    返回：
    清理后的子查询列表
    """
    # 模板验证
    if "{original_query}" not in decomposition_template:
        raise ValueError("模板必须包含{original_query}占位符")
    
    # 初始化模型
    llm = OllamaLLM(
        model=model,
        base_url="http://localhost:11434",
        temperature=temperature,
        num_predict=num_predict
    )
    
    # 构建处理链
    chain = (
        PromptTemplate.from_template(decomposition_template)
        | llm
    )
    
    # 执行分解
    response = chain.invoke({"original_query": original_query}).strip()
    
    
    cleaned_response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
    cleaned_response = re.sub(r'\n\s*\n', '\n', cleaned_response).strip()
    # 使用正则表达式提取子查询
    sub_queries = re.findall(
        r'\d+[\.、]?\s*(.+?)(?=\n|$)',  # 匹配编号开头的行
        cleaned_response
    )
    
    return [q for q in sub_queries if len(q.strip()) > 5]
  




from langchain.prompts import PromptTemplate
from typing import Dict, Any, List, Optional

def generate_hypothetical_doc(
    query: str,
    hyde_prompt: str = """基于以下问题生成技术文档用于RAG系统的Hyde：
根据问题：{query} 
生成一份直接回答该问题的假设性文档。该文档应详细且深入。
文档大小约{text_length}个字符，直接输出假设的文档，不要有其他解释性文字
""",
    llm_model: str = "deepseek-r1:1.5b",
    text_length: int = 500,
    temperature: float = 0,
    num_ctx: int = 4096,
    **model_kwargs
) -> str:
    """
    完整参数版假设文档生成方法
    
    参数：
    text_length: 目标文本长度（字符数，用于提示模板）
    max_tokens: 生成的最大token数量（实际控制生成长度）
    其他参数同上...
    """
    
    # 提示模板动态参数
    template_params = {"query": query}
    if "{text_length}" in hyde_prompt:
        template_params["text_length"] = text_length
    
    # 初始化模型
    llm = OllamaLLM(
        model=llm_model,
        base_url="http://localhost:11434",
        temperature=temperature,
        num_predict=num_ctx,
        **model_kwargs
    )
    
    # 生成文档
    final_prompt = hyde_prompt.format(**template_params)
    response = llm.invoke(final_prompt).strip()
    cleaned_response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
    cleaned_response = re.sub(r'\n\s*\n', '\n', cleaned_response).strip()
    return cleaned_response


from langchain_core.output_parsers import StrOutputParser
def generate_hypothetical_questions(
    chunk_text: str,
    model: str = "llama3:8b",
    num_questions: int = 5,
    temperature: float = 0,
    num_ctx: int = 4096,
    prompt_template: str = """
### 要求
请为用户输入的文本生成{num_questions}个用于信息检索的核心问题，每个问题单独占一行的位置，生成的这些问题能够涵盖文本的主要要点，不要带有编号直接输出。

## 示例输出:
太阳能电池转换效率提升的关键方法有哪些？
如何通过材料优化提高太阳能电池的光电转化能力？
结构设计在提升太阳能电池光吸收效率方面的作用是什么？

## 用户输入的文本
{chunk_text}"""
) -> List[str]:
    """
    生成假设性问题字符串的优化版本
    
    参数：
    chunk_text: 输入文本片段
    model: 使用的Ollama模型
    num_questions: 需要生成的问题数量
    prompt_template: 包含{num_questions}和{chunk_text}占位符的提示模板
    """

    llm = ChatOllama(
        model=model,
        base_url="http://localhost:11434",
        temperature=temperature,
        num_ctx=num_ctx
    )

    try:
        # 动态创建提示模板
        prompt = PromptTemplate.from_template(prompt_template)
        
        # 构建处理链
        processing_chain = (
            prompt | llm | StrOutputParser()
        )
        
        # 执行调用
        response = processing_chain.invoke({
            "chunk_text": chunk_text,
            "num_questions": num_questions
        })
        
        print(response)
        
        # 增强清洗逻辑
        cleaned_response = re.sub(r'<think>.*?</think>', '', response, flags=re.DOTALL)
        cleaned_response = re.sub(r'\n\s*\n', '\n', cleaned_response).strip()

        # 强化解析逻辑
        return [
            line
            for line in cleaned_response.split('\n')
            if line.strip() and len(line.strip()) > 2
        ]

    except Exception as e:
        print(f"生成失败: {str(e)}")
        return []






def generate_document_title(
    chunk_text: str,
    model: str = "deepseek-r1:1.5b",
    temperature: float = 0,
    num_ctx: int = 4096,
    prompt_template: str = """
### 要求
请为以下文档生成一个简洁的专业标题，不要包含任何解释、标点或格式符号，直接输出标题。

### 文档内容：
{chunk_text}


"""
) -> Optional[str]:
    """
    生成文档标题的无截断版本
    
    参数：
    chunk_text: 输入文本内容（完整未截断）
    model: 使用的Ollama模型
    temperature: 生成温度
    num_ctx: 模型上下文窗口大小
    """
    try:
        # 初始化模型
        llm = ChatOllama(
            model=model,
            base_url="http://localhost:11434",
            temperature=temperature,
            num_ctx=num_ctx
        )

        # ✅ 保持 PromptTemplate 对象
        prompt = PromptTemplate.from_template(prompt_template)

        # ✅ 正确构建处理链
        processing_chain = prompt | llm | StrOutputParser()
        
        # ✅ 在调用时传递参数
        raw_response = processing_chain.invoke({"chunk_text": chunk_text})
        cleaned_response = re.sub(r'<think>.*?</think>', '', raw_response, flags=re.DOTALL)
        cleaned_response = re.sub(r'\n\s*\n', '\n', cleaned_response).strip()
        return cleaned_response

    except Exception as e:
        print(f"文档标题生成失败: {str(e)}\n完整堆栈：\n{traceback.format_exc()}")
        return None







# ------------------------ 执行入口 ------------------------
if __name__ == "__main__":
  
  
  
    sample_text = ("""ASiR-V 图像重建包括为用于各种应用的参数定义所需的降噪水平。图像重建是将原始图像与 $1 0 0 \%$ 消除噪声的图像按一定百分比混合。混合级别共有 10 种，这些级别是基于完全以原始图像数据重建图像的降噪量。可以为 “重建 1” 回顾性规定 ASiR-V 图像重建，或作为 R2 至 R10 的 PMR1，或在 “回顾重建” 中进行回顾性重建。回顾性重建数据时，应该为应用 ASiR-V 的每个数据重建选择新系列，以便于比较和鉴别有 ASiR-V 的系列。""")
    print(f"{generate_document_title(sample_text)}")
    
    # 测试简单分块
    # test_split_markdown_by_headers()
  
  
    # 测试语义分块
    # test_split_markdown_semantic()
    
    
    # 测试时模拟Prefect环境
    # from prefect import flow
    # @flow
    # def test_flow():
    #     return prefect_logger_proposition_chunking("测试文本...")
    
    # test_flow()
    # md_path = "../data/output/markdown/test01/RevolutionMaximaUserManualCN453-454.md"

    # test_content = extract_text_from_markdown(md_path)
    
    # base_docs = split_markdown_by_headers(
    #     content=test_content,
    #     headers_to_split_on=[("#", "H1"), ("##", "H2")],
    #     sub_headers=[("###", "H3")],
    #     chunk_size=1500,
    #     min_chunk_size=100,
    #     sub_split_threshold=2000,
    # )
    # results = generate_propositions(chunks = base_docs)
    
    
    # 测试命题生成
    # original = Document(page_content="2025年特斯拉Model S续航达1000公里，采用固态电池技术")
    # generated = Document(page_content="1. Model S是特斯拉旗舰车型\n2. 2025款续航突破1000公里")

    # # 执行评估
    # results = evaluate_propositions(original, generated)
    
    # print(results)




# 测试重写查询
    # custom_template = """你是一名专业的搜索查询优化专家。你需要扩展并阐明以下搜索查询，同时保持其原始意图：

    # 原始查询：{original_query}

    # 直接输出优化后的版本，不要有分析等解释性文字"""
    
    # # 创建重写器实例
    # query_rewriter = rewrite_query(
    #     original_query="气候变化的影响",
    #     query_template=custom_template,
    #     model="deepseek-r1:14b",

    # )
    
    # # 使用重写器
    # print(query_rewriter)
    
    # test_query = "气候变化对环境的直接影响有哪些？"
    
    # # 生成回溯查询（自动适配中文场景）
    # broader_query = generate_step_back_query(
    #     test_query,
    #     # model="deepseek-r1:14b",
    #     model="deepseek-r1:8b",
    # )
    
    # print(f"原始查询：{test_query}")
    # print(f"广义查询：{broader_query}")
    
    
    
    # 传入自定义模板
    # queries = decompose_query(
    #     "如何构建抗通胀投资组合？",
    # )
    
    # for i, q in enumerate(queries, 1):
    #     print(f"{i}. {q}")
        
        
    # 精确控制文档长度
    # doc = generate_hypothetical_doc(
    #     query="太阳能电池转换效率提升方法",
    #     # 指定预期字符长度（提示模型控制）
    #     text_length=600,  
    #     # 设置实际token上限（防止过长）
    #     max_tokens=9600,
    #     # 添加中文停止符
    #     # 选择适合中文的模型
    #     llm_model="deepseek-r1:14b"
    # )
    # print(f"生成文档（{len(doc)}字符）：\n{doc}")
    
    
    # 使用示例
    # questions = generate_hypothetical_questions(
    #     chunk_text="""
    #     **一种动态方法，结合了基于检索和基于生成的方法，自适应地决定是否使用检索到的信息以及如何最好地利用它来生成响应。
    #     实施多步骤流程，包括检索决策、文档检索、相关性评估、响应生成、支持评估和实用程序评估，以生成准确、相关和有用的输出。
    #     一种复杂的 RAG 方法，可动态评估和纠正检索过程，结合矢量数据库、Web 搜索和语言模型，以实现高度准确和上下文感知的响应。
    #     集成 Retrieval Evaluator、Knowledge Refinement、Web Search Query Rewriter 和 Response Generator 组件，以创建一个系统，该系统根据相关性分数调整其信息来源策略，并在必要时组合多个来源。
    #     使用 grouse 包根据 GroUSE 框架的 6 个指标使用 GPT-4 评估基于上下文的 LLM 生成，并使用单元测试来评估自定义 Llama 3.1 405B 评估器。""",
    #     model="deepseek-r1:14b",
    #     num_questions=3
    # )
    # print(questions)
    
    