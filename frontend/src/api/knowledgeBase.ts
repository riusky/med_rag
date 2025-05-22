// src/api/knowledgeBase.ts
import { authClient } from './client'


// 知识库详情类型
export interface KnowledgeBaseDetail {
  id: number
  name: string
  description?: string
  vector_storage_path?: string
  processing_status: 'pending' | 'processing' | 'completed' | 'failed'
  created_at: string
}

// 处理状态更新类型
export interface ProcessingStatusUpdate {
  processing_status: KnowledgeBaseDetail['processing_status']
}

// 知识库基础类型
export interface KnowledgeBase {
  id: number
  name: string
  description?: string
  processing_status: string
  created_at: string
}

// 创建知识库参数
interface CreateKnowledgeBaseParams {
  name: string
  description?: string
}

// 更新知识库参数
interface UpdateKnowledgeBaseParams {
  name?: string
  description?: string
}

// 分页参数
interface PaginationParams {
  limit?: number
  offset?: number
}


// 新增处理流程响应类型
interface ProcessDocumentsResponse {
  message: string
  flow_run_id: string
  parameters: {
    input_dir: string
    output_root: string
    final_output_dir: string
    kb_id: number
    image_path: string
  }
  monitor_url: string
}

export const apiKnowledgeBase = {
  // 获取知识库列表
  getList(params?: PaginationParams) {
    return authClient.get<KnowledgeBase[]>('/knowledge-bases', {
      params: {
        limit: params?.limit || 10,
        offset: params?.offset || 0
      }
    })
  },

  // 创建知识库
  create(payload: CreateKnowledgeBaseParams) {
    return authClient.post<KnowledgeBase>('/knowledge-bases', payload)
  },

  // 获取单个知识库详情
  getDetail(id: number) {
    return authClient.get<KnowledgeBase>(`/knowledge-bases/${id}`)
  },

  // 更新知识库
  update(id: number, payload: UpdateKnowledgeBaseParams) {
    return authClient.put<KnowledgeBase>(`/knowledge-bases/${id}`, payload)
  },

  // 删除知识库
  delete(id: number) {
    return authClient.delete(`/knowledge-bases/${id}`)
  },

    // 新增：触发文档处理流程
  processDocuments(kbId: number) {
    return authClient.post<ProcessDocumentsResponse>(
      `/knowledge-bases/${kbId}/process`,
      null,
    )
  }
}