from datetime import datetime
import logging
import os
from fastapi import APIRouter, HTTPException, Depends, status
from typing import List

import httpx
from langchain_ollama import OllamaEmbeddings
from med_rag_server.db.dao.knowledge_base_dao import KnowledgeBaseDAO
from med_rag_server.web.api.knowledge_base.schema import (
    KnowledgeBaseDTO,
    KnowledgeBaseInputDTO,
    KnowledgeBaseUpdateDTO,
    ProcessingStatusUpdateDTO,
    VectorPathUpdateDTO
)
from med_rag_server.settings import settings
from langchain_community.vectorstores import FAISS
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA
from fastapi import Request
router = APIRouter()

logger = logging.getLogger(__name__)


async def get_prefect_deployment_id(deployment_name: str) -> str:
    try:
        async with httpx.AsyncClient() as client:
            api_path = f"{settings.PREFECT_API_URL}/deployments/name/pdf_to_markdown/{deployment_name}"
            print(f"Requesting URL: {api_path}")  # 调试日志
            
            response = await client.get(api_path, timeout=15.0)
            response.raise_for_status()  # 自动处理4xx/5xx错误
            return response.json().get("id")
            
    except httpx.HTTPStatusError as e:
        print(f"HTTP error: {e.response.status_code} - {e.response.text}")
    except httpx.RequestError as e:
        print(f"Request failed: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
    return None


@router.post("/{kb_id}/process", status_code=status.HTTP_202_ACCEPTED)
async def trigger_document_processing(
    kb_id: int,
    dao: KnowledgeBaseDAO = Depends(),
):
    """触发文档处理流程（动态部署ID版本）"""
    try:
        # 1. 获取部署ID
        deployment_id = await get_prefect_deployment_id("pdf_to_markdown-deployment")
        
        # 2. 获取知识库元数据
        kb = await dao.get_kb_by_id(kb_id)
        if not kb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="知识库不存在"
            )
        kb = await dao.update_processing_info(
            kb_id=kb_id,
            processing_status='processing'
        )

        # 3. 构建路径参数（根据实际业务调整）
        processing_params = {
            "input_dir": f"{settings.RAW_DOCS_ROOT}/{kb_id}",
            "output_root": f"{settings.PROCESSED_ROOT}/{kb_id}",
            "final_output_dir": f"{settings.OUTPUT_ROOT}/{kb_id}",
            "kb_id": kb_id,
            "image_path": f"{settings.STATIC_ROOT}/{kb_id}"
        }

        # 4. 调用 Prefect 运行接口
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{settings.PREFECT_API_URL}/deployments/{deployment_id}/create_flow_run",
                json={
                    "parameters": processing_params,
                    "state": {
                        "type": "SCHEDULED",
                        "message": "由 MedRAG 系统触发",
                        "state_details": {}
                    },
                    "enforce_parameter_schema": True
                },
                headers={
                    # "Authorization": f"Bearer {settings.PREFECT_API_KEY}",
                    "Content-Type": "application/json"
                },
                timeout=10.0
            )

            if response.status_code != 201:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"流程触发失败: {response.text}"
                )

            flow_run_data = response.json()

        # # 5. 记录处理任务
        # await dao.create_processing_task(
        #     kb_id=kb_id,
        #     prefect_flow_run_id=flow_run_data["id"],
        #     parameters=processing_params
        # )

        return {
            "message": "文档处理流程已启动",
            "flow_run_id": flow_run_data["id"],
            "parameters": processing_params,
            "monitor_url": f"{settings.PREFECT_UI_URL}/runs/flow-run/{flow_run_data['id']}"
        }

    except HTTPException as he:
        raise he
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"系统内部错误: {str(e)}"
        )

@router.get("/", response_model=List[KnowledgeBaseDTO])
async def get_all_knowledge_bases(
    limit: int = 10,
    offset: int = 0,
    dao: KnowledgeBaseDAO = Depends(),
):
    """获取所有知识库（分页）"""
    return await dao.get_all_kbs(limit, offset)

@router.post("/", response_model=KnowledgeBaseDTO, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    data: KnowledgeBaseInputDTO,
    dao: KnowledgeBaseDAO = Depends(),
):
    """创建知识库"""
    return await dao.create_kb(
        name=data.name,
        description=data.description
    )


def get_embeddings() -> OllamaEmbeddings:
    """获取嵌入模型实例"""
    return OllamaEmbeddings(
        model=settings.MODELSNAME,
        base_url="http://host.docker.internal:11434"
    )

@router.patch("/{kb_id}/processing-status", response_model=KnowledgeBaseDTO)
async def update_processing_status(
    kb_id: int,
    request: Request,
    status_data: ProcessingStatusUpdateDTO,
    dao: KnowledgeBaseDAO = Depends(),
):
    """更新处理状态（专用端点）"""
    kb = await dao.update_processing_info(
        kb_id=kb_id,
        processing_status=status_data.processingStatus
    )
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    kb = await dao.get_kb_by_id(kb_id)  
    # 当状态变为 completed 时初始化 QA Chain
    if status_data.processingStatus == "completed":
        # 获取向量存储路径
        vector_path = f"{settings.VECTORSTORAGE_ROOT}/{kb.vector_storage_path}"
        if not vector_path or not os.path.exists(vector_path):
            raise HTTPException(
                status_code=400,
                detail="Invalid vector storage path"
            )

        try:
            # 加载向量存储
            embeddings = get_embeddings()
            vectorstore = FAISS.load_local(
                folder_path=vector_path,
                embeddings=embeddings,
                allow_dangerous_deserialization=True
            )
            
            # 创建 QA Chain
            qa_chain = create_qa_chain(
                vectorstore=vectorstore,
                llm=request.app.state.llm
            )
            
            # 存储到应用状态
            request.app.state.qa_chains[kb_id] = qa_chain
            logger.info(f"Initialized QA chain for KB {kb_id}")

        except Exception as e:
            logger.error(f"QA chain initialization failed: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"QA chain initialization failed: {str(e)}"
            )

    return kb
  
@router.patch("/{kb_id}/vector-path", response_model=KnowledgeBaseDTO)
async def update_vector_path(
    kb_id: int,
    data: VectorPathUpdateDTO,
    dao: KnowledgeBaseDAO = Depends(),
):
    """更新向量存储路径"""
    kb = await dao.update_vector_path(
        kb_id=kb_id,
        vector_path=data.vectorStoragePath
    )
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return kb

@router.get("/{kb_id}", response_model=KnowledgeBaseDTO)
async def get_knowledge_base(
    kb_id: int,
    dao: KnowledgeBaseDAO = Depends(),
):
    """获取知识库详情"""
    kb = await dao.get_kb_by_id(kb_id)
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return kb

@router.put("/{kb_id}", response_model=KnowledgeBaseDTO)
async def update_knowledge_base(
    kb_id: int,
    data: KnowledgeBaseUpdateDTO,
    dao: KnowledgeBaseDAO = Depends(),
):
    """更新知识库元信息"""
    kb = await dao.update_kb(
        kb_id=kb_id,
        name=data.name,
        description=data.description
    )
    if not kb:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return kb

@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    kb_id: int,
    dao: KnowledgeBaseDAO = Depends(),
):
    """删除知识库"""
    success = await dao.delete_kb(kb_id)
    if not success:
        raise HTTPException(status_code=404, detail="Knowledge base not found")
    return None
  
MEDICAL_PROMPT_TEMPLATE = """# GE医疗设备专业问答规范

## █ 角色定位
您是由GE Healthcare认证的资深设备技术专家，需确保回答符合以下标准：
✅ 基于官方技术文档的精确解读
✅ 满足临床工程师的深度技术需求

## █ 知识处理规范
〖多源信息整合〗
├─ 技术参数 → 对比表格呈现(含单位/范围/版本差异)
├─ 操作流程 → 分步标记关键节点(❶❷❸)
├─ 安全规范 → 附加⚠️警示标识
└─ 图表数据 → 保留原始markdown格式(含图片链接和表格结构)

〖信息缺失处理〗
当检索内容与问题相关性＜40%时：
1. 明确声明：当前知识库(v2024Q2)未覆盖该问题
2. 智能引导：
   生成3个语义相近的标准问题建议

## █ 响应标准流程
结构化输出：
[技术摘要] 
   设备型号▸技术特性▸适用场景
   
[操作规范]
   ❶ 准备阶段 → ❷ 执行要点 → ❸ 结果验证

[安全公示] 
   ⚠️ 风险项▸防护要求▸应急方案

[技术参数] 
   | 指标项 | 标准值 | 允许偏差 | 测量条件 |
   |--------|--------|----------|----------|

跨文档整合：
当涉及多文档参数时→创建对比维度表

## █ 特殊场景处理
► 临床案例咨询：
   追加"典型故障案例参考"(2019-2023年维保数据)
   
► 参数对比需求：
   生成设备代际升级对比矩阵(含性能提升百分比)

► 安全规范咨询：
   添加"近三年同类设备不良事件统计"(国家药监局数据)

## █ 质量控制要求
1. 自我验证流程：
   ⇢ 技术参数二次核对
   ⇢ 安全条款版本验证
   ⇢ 图表序号连续性检查

2. 引用标注：
   在每项技术说明后标注来源文档编号(如：<TS-DF-023>)

3. 版本声明：
   文末添加：△基于GE Healthcare 2025技术文档库
   
   
[知识片段]
{context}

[用户问题]
{question}
"""



def create_qa_chain(vectorstore, llm):
    """创建医疗问答链"""
    try:
        qa_prompt = PromptTemplate(
            template=MEDICAL_PROMPT_TEMPLATE,
            input_variables=["context", "question"],
            partial_variables={
                "current_date": datetime.now().strftime("%Y-%m-%d")
            }
        )
        
        return RetrievalQA.from_chain_type(
                  llm=llm,
                  chain_type="stuff",
                  retriever=vectorstore.as_retriever(
                      search_type="mmr",
                      search_kwargs={"k": 5,"fetch_k":15, "lambda_mult": 0.25}
                  ),
                  return_source_documents=True,
                  chain_type_kwargs={"prompt": qa_prompt},
              )
    except Exception as e:
        logger.error(f"创建问答链失败: {str(e)}")
        raise