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
    """根据部署名称获取 Prefect 部署ID"""
    try:
        async with httpx.AsyncClient() as client:
            # 构造带版本号的API路径
            api_path = f"{settings.PREFECT_API_URL}/deployments/name/pdf_to_markdown/{deployment_name}"
            
            print(api_path)
            
            response = await client.get(
                api_path,
                timeout=15.0
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Prefect API 错误: {response.text}"
                )

            deployment_data = response.json()
            return deployment_data["id"]

    except httpx.RequestError as e:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"无法连接 Prefect 服务: {str(e)}"
        )


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
  
MEDICAL_PROMPT_TEMPLATE = """[角色设定]
您是 GE Healthcare 认证的医疗设备专家，需严格遵循如下标准回答用户问题。

[知识片段]
{context}

[用户问题]
{question}

[回答规范]
0. 如果知识片段中包含markdown格式的图片，则需要将图片也回复出来(保持markdown的语法)
1. 操作步骤用❶❷❸标记关键节点
2. 技术参数需表格化对比
3. 安全警示添加⚠️ 标识, eg:在涉及高风险操作（如除颤器使用）时，提示词插入⚠️标识符：
4. 若手册未涵盖该问题，回复“根据当前手册，暂未提供此问题的解决方案”。
5. 将手册章节标题（如“安全注意事项”“清洁步骤”）作为分隔符插入提示词，例如：
[安全警告] 检0索到的安全条款 
[操作步骤] 相关操作流程
6. 回复使用和用户问题相同的语言 eg: 用户使用中文提问，则回复也用中文
7. 如果知识片段中包含markdown格式的表格，则需要回复完整的表格
8. 如果知识片段和用户问题不相关，则直接回复根据检索到的文档无法回到该问题，并提示用户优化问题
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
                      search_type="similarity_score_threshold",
                      search_kwargs={"k": 3, "score_threshold": 0.7}
                  ),
                  return_source_documents=True,
                  chain_type_kwargs={"prompt": qa_prompt},
              )
    except Exception as e:
        logger.error(f"创建问答链失败: {str(e)}")
        raise