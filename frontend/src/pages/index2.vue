<template>
  <ResizablePanelGroup direction="horizontal" class="h-full bg-background border">
    <!-- 左侧历史对话 -->
    <ResizablePanel :default-size="15" :min-size="15" :max-size="25" class="min-w-[150px]">
      <div class="h-full flex flex-col p-4 left_history_chat">
        <h2 class="text-lg font-semibold mb-4 flex-shrink-0">history of conversation</h2>

        <!-- 滚动区域容器 -->
        <div class="flex-1 min-h-0"> <!-- 关键样式 -->
          <ScrollArea class="h-full">
            <div class="space-y-2">
              <div v-for="(convo, index) in conversations" :key="index"
                class="p-3 rounded-lg cursor-pointer transition-colors hover:bg-muted hover:text-foreground"
                :class="{ 'bg-primary text-primary-foreground': activeIndex === index }"
                @click="selectConversation(index)">
                <div class="text-sm font-medium truncate">{{ convo.title }}</div>
                <div class="text-xs opacity-70">{{ formatDate(convo.lastTime) }}</div>
              </div>
            </div>
          </ScrollArea>
        </div>

        <!-- 底部固定按钮 -->
        <Button class="w-full mt-4 flex-shrink-0" @click="newConversation">
          <Plus class="w-4 h-4 mr-2" />
          New Chat
        </Button>
      </div>
    </ResizablePanel>

    <ResizableHandle with-handle />

    <!-- 右侧主区域 -->
    <ResizablePanel>
      <ResizablePanelGroup direction="vertical">
        <!-- 聊天内容区域 -->
        <ResizablePanel :default-size="80">
          <ScrollArea class="h-full p-4">
            <div class="space-y-4 mx-auto">
              <div v-for="(msg, index) in activeMessages" :key="index" class="flex gap-3"
                :class="{ 'flex-row-reverse': msg.role === 'user' }">
                <Avatar class="h-8 w-8 flex-shrink-0">
                  <AvatarImage v-if="msg.role === 'assistant'" :src="currentBotAvatar" />
                  <AvatarFallback>
                    {{ msg.role === 'user' ? 'you' : 'AI' }}
                  </AvatarFallback>
                </Avatar>
           
                  <div class="ml-4 rounded-xl w-full bg-muted" v-if="msg.role === 'assistant'">
                    <Tabs default-value="content">
                      <TabsList class="grid grid-cols-3 w-full">
                        <TabsTrigger value="content" class="text-xs p-2 h-8 border-muted-foreground">
                          reply content
                        </TabsTrigger>
                        <TabsTrigger value="reference" class="text-xs p-2 h-8 border-muted-foreground">
                          document citation
                        </TabsTrigger>
                        <TabsTrigger value="images" class="text-xs p-2 h-8 border-muted-foreground">
                          Original image
                        </TabsTrigger>
                      </TabsList>

                      <!-- 内容标签 -->
                      <TabsContent value="content">
                        <v-md-preview :text="msg.content" :key="`${msg.timestamp}_${msg.content.length}`" class="prose prose-sm max-w-none markdown-body" />
                      </TabsContent>

                      <!-- 文档引用标签 -->
                      <TabsContent value="reference">
                        <div class="space-y-2 text-sm">
                          <div v-if="msg.metadata?.references && msg.metadata.references.length > 0">
                            <div v-for="(ref, index) in msg.metadata.references" :key="index"
                              class="p-3 bg-background rounded-lg">
                              <div class="font-medium text-primary">
                                Reference {{ index + 1 }}: {{ ref.source }}
                              </div>
                              <p class="mt-1 text-muted-foreground break-all" v-if="ref.text && ref.text !== ref.source">
                                {{ ref.text }}
                              </p>
                            </div>
                          </div>
                          <div v-else>
                            <p class="text-muted-foreground">No references provided.</p>
                          </div>
                        </div>
                      </TabsContent>

                      <!-- 图片标签 -->
                      <TabsContent value="images" class="mt-4">
                        <div class="grid grid-cols-2 gap-3">
                          <div v-for="(img, index) in msg.metadata?.images" :key="index"
                            class="aspect-square overflow-hidden rounded-md border">
                            <img :src="img.url" :alt="img.caption || 'reference image'" class="w-full h-full object-cover" />
                          </div>
                        </div>
                      </TabsContent>
                    </Tabs>

                    <!-- 时间戳 -->
                    <div class="text-xs opacity-70 mt-2 mb-2 ml-2">
                      {{ formatTime(msg.timestamp) }}
                    </div>
                  </div>

                  <!-- 用户消息保持原样 -->
                  <template v-else class="text-sm">
                    <span class="max-w-4xl rounded-xl bg-primary text-primary-foreground pl-2 pr-2">
                      {{ msg.content }}
                    </span>
                  </template>

   
                </div>
            </div>
          </ScrollArea>
        </ResizablePanel>

        <ResizableHandle with-handle />

<!-- 输入操作区域 -->
<ResizablePanel :default-size="20" :min-size="15">
  <div class="h-full p-4 bg-background/90 backdrop-blur border-t">
    <!-- 外层容器使用 flex 布局 -->
    <div class="max-w-5xl mx-auto h-full flex flex-col">
      <!-- 文本框容器（占满剩余高度） -->
      <div class="flex-1 min-h-0 mb-3">
        <Textarea 
          ref="textareaRef"
          v-model="inputMessage"
          class="h-full w-full resize-none"
          placeholder="Input message...Press (Shift/Alt/Ctrl) + Enter to create a new line."
          @keydown="handleKeydown"
          :disabled="isLoading"
        />
      </div>

      <!-- 操作按钮行（固定高度） -->
      <div class="flex justify-between items-center h-10">
        <div class="flex gap-2">

          <Select v-model="selectedKbId">
        <SelectTrigger class="w-[200px]">
          <SelectValue>
            <span v-if="!selectedKbId">Select Knowledge Base</span>
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          <template v-if="knowledgeBases.length">
            <SelectItem v-for="kb in knowledgeBases" :key="kb.id" :value="kb.id">
              {{ kb.name }}
            </SelectItem>
          </template>
          <template v-else>
            <SelectItem disabled value="no-data">
              {{ 'No knowledge base available' }}
            </SelectItem>
          </template>
        </SelectContent>
      </Select>


          <Button variant="outline" size="icon">
            <Paperclip class="h-4 w-4" />
          </Button>
          <Button variant="outline" size="icon">
            <Sparkles class="h-4 w-4" />
          </Button>
          <Button variant="outline" size="icon">
            <Settings class="h-4 w-4" />
          </Button>
        </div>

        <Button
          size="default"
          class="h-10 px-4"
          :disabled="!inputMessage.trim() || isLoading"
          @click="sendMessage"
        >
          <template v-if="isLoading">
            <Loader2 class="h-5 w-5 mr-2 animate-spin" />
            Sending...
          </template>
          <template v-else>
            <SendHorizontal class="h-5 w-5 mr-2" />
            Send
          </template>
        </Button>
      </div>
    </div>
  </div>
</ResizablePanel>
      </ResizablePanelGroup>
    </ResizablePanel>
  </ResizablePanelGroup>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, reactive, onMounted, shallowReactive } from 'vue'
import {
  ResizableHandle,
  ResizablePanel,
  ResizablePanelGroup,
} from '@/components/ui/resizable'
import { Button } from '@/components/ui/button'
import { Textarea } from '@/components/ui/textarea'
import { Avatar } from '@/components/ui/avatar'
import { ScrollArea } from '@/components/ui/scroll-area'
import { Plus, Paperclip, Sparkles, Settings, SendHorizontal, Loader2 } from 'lucide-vue-next'
import VMdPreview from '@kangc/v-md-editor/lib/preview'
import '@kangc/v-md-editor/lib/style/preview.css'
import githubTheme from '@kangc/v-md-editor/lib/theme/github'
import '@kangc/v-md-editor/lib/theme/style/github.css'
import hljs from 'highlight.js'
import { setBreadcrumbs } from '@/composables/breadcrumbs'
import { apiKnowledgeBase, type KnowledgeBase } from '@/api/knowledgeBase'

setBreadcrumbs([{ name: 'RAG Dashboard', to: '/' }, { name: 'Chat' }])
// 初始化配置
VMdPreview.use(githubTheme, {
  Hljs: hljs,
  // extend(md: any) {
  //   // 启用代码行号
  //   md.use(require('@kangc/v-md-editor/lib/plugins/line-number/index'))
  //   // 启用复制代码功能
  //   md.use(require('@kangc/v-md-editor/lib/plugins/copy-code/index'), {
  //     buttonText: '复制',
  //     successText: '已复制'
  //   })
  // }
})


// 知识库相关状态
const knowledgeBases = ref<KnowledgeBase[]>([])
const selectedKbId = ref<number>()
const isKbListLoading = ref(false)
const isLoading = ref(false); // Added for loading state



onMounted(() => {
  if (conversations.value.length === 0) {
    newConversation()
  }
  (async () => {
    try {
      isKbListLoading.value = true
      const { data } = await apiKnowledgeBase.getList({ limit: 50 })
      knowledgeBases.value = data
      if (data.length > 0) {
        selectedKbId.value = data[0].id
      }
    } catch (error) {
      console.error('加载知识库失败:', error)
    } finally {
      isKbListLoading.value = false
    }
  })()
})

// 初始化高亮插件
hljs.configure({
  classPrefix: 'hljs-',
  languages: ['javascript', 'python', 'html', 'css']
})

// 历史对话数据
interface Conversation {
  title: string
  lastTime: Date
  messages: Message[]
}

interface Message {
  role: 'user' | 'assistant'
  content: string
  timestamp: Date
  metadata?: {
    references: Reference[]
  }
}

// 初始化默认对话
const conversations = ref<Conversation[]>([{
  title: 'Initial conversation',
  lastTime: new Date(),
  messages: [] // 明确初始化空数组
}])

// 正确类型定义
interface TextareaElement {
  $el: HTMLTextAreaElement
}

const activeIndex = ref(0)
const inputMessage = ref('')
const textareaRef = ref<TextareaElement | null>(null)

const getNativeTextarea = () => {
  return textareaRef.value?.$el // 访问组件内部的原生元素
}

const handleKeydown = async (event: KeyboardEvent) => {
  const textarea = getNativeTextarea()
  if (!textarea) return

  // 获取正确的选区位置
  const startPos = textarea.selectionStart
  const endPos = textarea.selectionEnd

  if (event.key === 'Enter' && !event.isComposing) {
    if (event.ctrlKey || event.metaKey || event.shiftKey) {
      event.preventDefault()
      
      // 插入换行符
      inputMessage.value = 
        inputMessage.value.slice(0, startPos) +
        '\n' +
        inputMessage.value.slice(endPos)

      // 等待DOM更新
      await nextTick()
      
      // 设置新光标位置
      textarea.selectionStart = textarea.selectionEnd = startPos + 1
      textarea.focus()
    } else {
      event.preventDefault()
      sendMessage()
    }
  }
}


// 当前对话消息
const activeMessages = computed(() =>
  conversations.value[activeIndex.value]?.messages || []
)

// 当前助手头像
const currentBotAvatar = computed(() => '/avatars/ai-default.png')

// 方法
const selectConversation = (index: number) => {
  activeIndex.value = index
}

const newConversation = () => {
  const newConvo = {
    title: `dialogue ${conversations.value.length + 1}`,
    lastTime: new Date(),
    messages: [] // 明确初始化
  }
  
  conversations.value.push(newConvo)
  activeIndex.value = conversations.value.length - 1
  
  // 滚动到最新对话
  nextTick(() => {
    const container = document.querySelector('[data-radix-scroll-area-viewport]')
    container?.scrollTo(0, container.scrollHeight)
  })
}



import { apiMedicalRag, type Reference } from '@/api/medicalRag'
// 修改后的 sendMessage 方法
const sendMessage = async () => {
  if (isLoading.value) return; // Prevent multiple submissions
  isLoading.value = true;

  if (!selectedKbId.value) {
    alert('请先选择知识库')
    isLoading.value = false;
    return
  }


  // 获取知识库元数据
  const currentKb = knowledgeBases.value.find(kb => kb.id === selectedKbId.value)
  if (!currentKb || currentKb.processing_status !== 'completed') {
    alert('当前知识库不可用，请检查处理状态')
    isLoading.value = false;
    return
  }


  if (!inputMessage.value.trim()) {
    isLoading.value = false;
    return
  }

  try {
    // 确保当前对话存在
    let currentConvo = conversations.value[activeIndex.value]
    if (!currentConvo) {
      newConversation()
      currentConvo = conversations.value[activeIndex.value]
    }

    // 创建稳定的消息引用
    const userMessage = {
      role: 'user' as const,
      content: inputMessage.value,
      timestamp: new Date()
    }

    // 使用响应式对象（关键修改点）
    const assistantMessage = reactive({
      role: 'assistant' as const,
      content: '',
      timestamp: new Date(),
      metadata: {
        references: [] as Reference[]
      },
      _updateFlag: 0 // 用于强制更新的标记
    })

    // 原子化更新消息列表
    currentConvo.messages = [
      ...currentConvo.messages,
      userMessage,
      assistantMessage
    ]

    // const question = inputMessage.value
    inputMessage.value = ''

    // 创建更新机制（关键修改点）
    let buffer = ''
    let animationFrameId: number | null = null

    await apiMedicalRag.streamQuery(
      { 
        question: inputMessage.value,
        kb_id: selectedKbId.value 
      },
      {
        onData: (delta) => {
          buffer += delta
          
          // 使用 requestAnimationFrame 批量更新
          if (!animationFrameId) {
            animationFrameId = requestAnimationFrame(() => {
              // 更新内容并触发响应式更新
              assistantMessage.content = buffer
              assistantMessage._updateFlag++
              
              // 强制更新消息数组
              currentConvo.messages = [...currentConvo.messages]
              
              smartScroll()
              animationFrameId = null
            })
          }
        },
        onComplete: ({ references }) => {
          // 最终同步（关键修改点）
          cancelAnimationFrame(animationFrameId!)
          assistantMessage.content = buffer
          assistantMessage.metadata.references = references
          currentConvo.messages = [...currentConvo.messages]
          smartScroll(true)

          // assistantMessage.metadata = {
          //   references,
          //   // kb_id: currentKb.id,
          //   vector_path: currentKb.vector_storage_path
          // }
          isLoading.value = false;
        },
        onError: (error) => {
          cancelAnimationFrame(animationFrameId!)
          assistantMessage.content = `Request failed: ${error}`
          currentConvo.messages = [...currentConvo.messages]
          smartScroll()
          isLoading.value = false;
        }
      }
    )
  } catch (error) {
    console.error('Message sending failed:', error)
    handleSendError()
    isLoading.value = false;
  }
}

// 视图更新触发器
const triggerViewUpdate = (convo: Conversation) => {
  convo.messages = convo.messages.map(m => ({ ...m }))
}


const smartScroll = (force = false) => {
  nextTick(() => {
    const container = document.querySelector('[data-radix-scroll-area-viewport]') as HTMLElement
    if (container) {
      const threshold = 100 // 像素容差
      const isNearBottom = 
        container.scrollTop + container.clientHeight >= 
        container.scrollHeight - threshold
      
      if (force || isNearBottom) {
        container.scrollTo({
          top: container.scrollHeight,
          behavior: 'smooth'
        })
      }
    }
  })
}

const handleSendError = () => {
  const currentConvo = conversations.value[activeIndex.value]
  if (currentConvo?.messages?.length) {
    const lastMessage = currentConvo.messages[currentConvo.messages.length - 1]
    if (lastMessage.role === 'assistant') {
      lastMessage.content = 'The service is temporarily unavailable, please try again later.'
      triggerViewUpdate(currentConvo)
    }
  }
}

// 格式化工具
const formatDate = (date: Date) =>
  date.toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })

const formatTime = (date: Date) =>
  date.toLocaleTimeString('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: false
  })
</script>

<style>
.left_history_chat {
  height: calc(100vh - 85px);
}

[data-radix-scroll-area-viewport] {
  height: 100%;
  overflow-y: auto !important;
}

/* 优化滚动条外观 */
[data-radix-scroll-area-viewport]::-webkit-scrollbar {
  width: 6px;
}

[data-radix-scroll-area-viewport]::-webkit-scrollbar-thumb {
  background-color: hsl(var(--muted-foreground)/0.3);
  border-radius: 4px;
}

.markdown-body-1 {
  font-size: 0.8125rem;  /* 13px (原14px) */
  line-height: 1.6;      /* 增加行高补偿字号缩小 */

  /* 标题层级调整 */
  h1 {
    font-size: 1.4em;    /* 18.2px (原21px) */
    line-height: 1.3;
    margin-bottom: 2px;
  }
  
  h2 {
    font-size: 1.25em;   /* 16.25px (原19.25px) */
    line-height: 1.35;
    margin-bottom: 2px;
    margin-top: 2px;
  }

  h3 {
    font-size: 1.15em;   /* 14.95px (原17.5px) */
    line-height: 1.4;
    margin-bottom: 2px;
    margin-top: 2px;
  }

  h4 {
    font-size: 1.05em;   /* 14.95px (原17.5px) */
    line-height: 1.4;
    margin-bottom: 2px;
    margin-top: 2px;
  }

  /* 正文及列表 */
  p, li {
    font-size: 0.8125em; /* 10.56px (原12.25px) */
    line-height: 1.7;    /* 增加行高提升可读性 */
    margin-bottom: 4px;/* 增加段落间距 */
  }

  /* 代码块三级调整 */
  pre code {
    font-size: 0.75rem;  /* 12px (原13px) */
    line-height: 1.5;
    padding: 0.8em;      /* 增加内间距 */
  }

  /* 行内代码适配 */
  code:not(pre code) {
    font-size: 0.75rem;  /* 12px (原13px) */
    padding: 0.15em 0.3em;
    vertical-align: 0.05em; /* 对齐优化 */
  }

  /* 表格紧凑优化 */
  table {
    font-size: 0.75rem;  /* 12px (原13px) */
    th, td {
      padding: 0.4em 0.6em;
    }
    margin-bottom: 2px;
    margin-top: 2px;
  }

  /* 引用块调整 */
  blockquote {
    font-size: 0.75rem;  /* 12px (原14px) */
    padding: 0.5em 1em;
    border-left-width: 3px;
  }
}


/* 用户消息容器 */
.bg-primary.text-primary-foreground {
  font-size: 0.875rem;
  /* 同步基础字号 */
}
</style>