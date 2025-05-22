// src/api/medicalRag.ts

// 类型定义 ------------------------------------------------------------------------
export interface MedicalRagQuery {
  question: string
  kb_id: number
  language?: 'zh' | 'en'
  require_references?: boolean
  safety_warnings?: boolean
}

export interface MedicalRagResponse {
  answer: string
  references: Reference[]
  metadata: {
    doc_count: number
    kb_id: number
    vector_path: string
  }
}

export interface Reference {
  text: string
  source: string
}


export class SSEParser {
  private buffer: string = ''
  
  constructor(
    private config: {
      onMessage: (event: MessageEvent) => void
      onError: (error: string) => void
    }
  ) {}

  feed(chunk: string) {
    this.buffer += chunk
    while (this.processBuffer()) {}
  }

  private processBuffer(): boolean {
    const eventEnd = this.buffer.indexOf('\n\n')
    if (eventEnd === -1) return false

    const eventData = this.buffer.slice(0, eventEnd)
    this.buffer = this.buffer.slice(eventEnd + 2)

    const eventTypeMatch = eventData.match(/^event: (\w+)/m)
    const dataMatch = eventData.match(/^data: (.*)/ms)

    if (eventTypeMatch && dataMatch) {
      try {
        this.config.onMessage({
          type: eventTypeMatch[1],
          data: dataMatch[1]
        } as MessageEvent)
      } catch (error) {
        this.config.onError(`事件处理失败: ${error}`)
      }
    }
    return true
  }
}

// API 方法 ------------------------------------------------------------------------
export const apiMedicalRag = {
  async streamQuery(
    payload: MedicalRagQuery,
    handlers: {
      onData: (chunk: string) => void
      onComplete: (metadata: MedicalRagResponse['metadata'] & { references: Reference[] }) => void
      onError: (error: string) => void
    }
  ) {
    try {

      // 使用 Fetch API
      const response = await fetch(`${import.meta.env.VITE_BASE_URL}/document/medical-search-stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          question: payload.question,
          kb_id: payload.kb_id,
          language: payload.language || 'zh',
          require_references: payload.require_references ?? true,
          safety_warnings: payload.safety_warnings ?? true
        })
      })

      // 处理非200响应
      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.message || '请求失败')
      }

      // 创建流式解析器
      const parser = new SSEParser({
        onMessage: (event: MessageEvent) => {
          try {
            const data = JSON.parse(event.data)
            switch (event.type) {
              case 'data':
                handlers.onData(data.delta)
                break
              case 'complete':
                handlers.onComplete({
                  references: data.references || [],
                  doc_count: data.metadata?.doc_count || 0
                })
                break
              case 'error':
                handlers.onError(data.error || '未知错误')
                break
            }
          } catch (error) {
            handlers.onError('数据解析失败')
          }
        },
        onError: handlers.onError
      })

      // 获取可读流
      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('无法读取数据流')
      }

      // 流式处理
      const decoder = new TextDecoder()
      while (true) {
        const { done, value } = await reader.read()
        if (done) break
        parser.feed(decoder.decode(value))
      }

    } catch (error: any) {
      handlers.onError(
        error.message || 
        error.response?.data?.message || 
        '未知错误'
      )
    }
  }
}
