// src/api/document.ts
import { authClient } from './client'

// 文档基础类型
interface KnowledgeDocument {
  id: number
  kb_id: number
  file_name: string
  file_path: string
  chunk_method: string
  chunk_params: {
    chunk_size: number
    overlap: number
  }
  upload_time: string
  parsing_status: 'pending' | 'processing' | 'completed' | 'failed'
  is_active: boolean
}

// 分页参数
interface PaginationParams {
  limit?: number
  offset?: number
}

export const apiDocument = {
  // 创建文档
  create(formData: FormData) {
    return authClient.post<KnowledgeDocument>('/document', formData, {
      headers: {
        'Content-Type': 'multipart/form-data'
      }
    })
  },

  // 获取知识库文档列表
  getByKb(kb_id: number, params?: PaginationParams) {
    return authClient.get<KnowledgeDocument[]>(`/document/knowledge_base/${kb_id}`, {
      params: {
        limit: params?.limit || 10,
        offset: params?.offset || 0
      }
    })
  },

  // 更新文档
  update(id: number, params: URLSearchParams, payload: any) {
    return authClient.put<KnowledgeDocument>(`/document/${id}?${params.toString()}`, payload, {
      headers: {
        'Content-Type': 'application/json' // 明确指定JSON格式
      }
    })
  },

  // 删除文档
  delete(id: number) {
    return authClient.delete(`/document/${id}`)
  }
}