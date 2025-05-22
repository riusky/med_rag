<script setup lang="ts">
import { ref, computed, h, onMounted, onUnmounted, watch } from 'vue'
import dayjs from 'dayjs'
import {
  Download,
  Trash2,
  ArrowUpDown,
  ChevronDown,
  FileUp,
  Settings,
  BookOpenCheck,
  Loader2,
  Play,
} from 'lucide-vue-next'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Switch } from '@/components/ui/switch'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
  DropdownMenuCheckboxItem,
} from '@/components/ui/dropdown-menu'
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table'
import { Tooltip, TooltipContent, TooltipTrigger } from '@/components/ui/tooltip'
import {
  useVueTable,
  getCoreRowModel,
  getPaginationRowModel,
  getSortedRowModel,
  getFilteredRowModel,
  FlexRender,
  type SortingState,
  type ColumnFiltersState,
  type VisibilityState,
} from '@tanstack/vue-table'
import { valueUpdater } from '@/components/ui/table/utils'
import { cn } from '@/lib/utils'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { apiKnowledgeBase } from '@/api/knowledgeBase'
import { useRoute, useRouter } from 'vue-router'
import { apiDocument } from '@/api/document'
import { toast } from 'vue-sonner'
import { setBreadcrumbs } from '@/composables/breadcrumbs'

setBreadcrumbs([{ name: 'Document Manage', to: '/knowledge' }, { name: 'Document' }])
const handleFileChange = (event: Event) => {
  const input = event.target as HTMLInputElement
  if (input.files?.[0]) {
    uploadFile.value = input.files[0]
  } else {
    uploadFile.value = null
  }
}

const handleFileUpload = async () => {

  if (!uploadFile.value || !selectedKnowledgeBaseId.value) {
    toast.error('Upload failed', {
      description: 'Please select a knowledge base and upload files first.'
    })
    return
  }

  const toastId = toast.loading('File uploading...', {
    description: 'Please do not close the page'
  })

  try {
    const formData = new FormData()
    formData.append('kb_id', selectedKnowledgeBaseId.value.toString())
    formData.append('file_name', uploadFile.value.name)
    formData.append('file', uploadFile.value)
    formData.append('chunk_method', chunkSettings.value.method)
    formData.append('chunk_params', JSON.stringify({
      chunk_size: chunkSettings.value.chunkSize,
      overlap: chunkSettings.value.overlap
    }))

    const { data } = await apiDocument.create(formData)
    toast.success('Upload successful', {
      description: `${data.file_name} Uploaded successfully`,
      id: toastId
    })

    loadDocuments()
    isUploadDialogOpen.value = false
  } catch (error: any) {
    const errorMsg = error.response?.data?.detail || error.message
    toast.error('Upload failed', {
      description: errorMsg,
      id: toastId
    })

  } finally {
    uploadFile.value = null
  }
}

const isLoadingDocuments = ref(false)



// 修改文档列表加载错误处理
const loadDocuments = async () => {
  if (!selectedKnowledgeBaseId.value) return

  try {
    isLoadingDocuments.value = true
    const { data } = await apiDocument.getByKb(Number(selectedKnowledgeBaseId.value))

    documents.value = data.map(formatDocument) // 应用格式转换

    table.setOptions(prev => ({
      ...prev,
      data: documents.value
    }))

    const kb_data  = await apiKnowledgeBase.getDetail(selectedKnowledgeBaseId.value)
    console.log(selectedKnowledgeBaseId.value)
    if (kb_data.data.processing_status) {
          if (kb_data.data.processing_status == 'processing') {
            isParsing.value = true
          } else {
            isParsing.value = false
          }
    }
  } catch (error: any) {
    toast.error('Document failed to load', {
      description: error.response?.data?.detail || error.message
    })
  } finally {
    isLoadingDocuments.value = false
  }
}

const props = defineProps({
  param: {
    type: [Number], // 参数类型
    default: null // 未传时的默认值
  }
})

console.log('Prop param:', props.param)

interface KnowledgeBase {
  id: number
  name: string
  description?: string
  document_count: number
  created_at: string
}

// 知识库相关状态
const knowledgeBases = ref<KnowledgeBase[]>([])
const selectedKnowledgeBaseId = ref<null | Number>(null)
const isLoading = ref(false)
const error = ref(null)

// 加载知识库数据
const loadKnowledgeBases = async () => {
  try {
    isLoading.value = true
    error.value = null
    const { data } = await apiKnowledgeBase.getList({ limit: 100 })
    knowledgeBases.value = data

    // 初始化选中状态
    // initSelectedKnowledgeBase()
    if (props.param) {
      const kbId = Number(props.param)
      const exists = knowledgeBases.value.some(kb => kb.id === kbId)
      selectedKnowledgeBaseId.value = exists ? kbId : null
      // 得到状态
      if (exists) {
        const { data } = await apiKnowledgeBase.getDetail(kbId)
        if (data.processing_status) {
          if (data.processing_status == 'processing') {
            isParsing.value = true
          } else {
            isParsing.value = false
          }
        }
      }
    }

    if (selectedKnowledgeBaseId.value) {
      loadDocuments()
    }
  } catch (err) {
    console.error('Knowledge base failed to load:', err)
  } finally {
    isLoading.value = false
  }
}

// 组件挂载时加载数据
onMounted(() => {
  loadKnowledgeBases()
})

// 初始化选中状态
const initSelectedKnowledgeBase = () => {
  if (props.param) {
    const kbId = Number(props.param)
    const exists = knowledgeBases.value.some(kb => kb.id === kbId)
    selectedKnowledgeBaseId.value = exists ? kbId : null
    // 得到状态
    // if (exists) {
    //   await apiKnowledgeBase.getDetail(kbId)
    // }
  }
}

// 路由实例
const route = useRoute()
const router = useRouter()

// 处理知识库变更
const handleKnowledgeBaseChange = (kbId) => {
  selectedKnowledgeBaseId.value = kbId
  loadDocuments()
}

// 知识库文档接口
interface KnowledgeDocument {
  id: number // 改为number类型
  kb_id: number // 新增字段
  file_name: string
  file_path: string
  chunk_method: string
  chunk_params: { // 字段名和结构变更
    chunk_size: number
    overlap: number
  }
  upload_time: string // 原始字段
  parsing_status: 'pending' | 'processing' | 'completed' | 'failed' // 状态枚举变更
  is_active: boolean
}

const formatDocument = (doc: KnowledgeDocument) => ({
  ...doc,
  // 字段重命名和格式转换
  uploadedAt: dayjs(doc.upload_time).format('YYYY-MM-DD HH:mm'), // 格式化时间
  chunkMethod: doc.chunk_method.replace(/^\w/, c => c.toUpperCase()), // 首字母大写
  parsingStatus: {
    pending: 'pending',
    processing: 'processing',
    completed: 'success',
    failed: 'error'
  }[doc.parsing_status],
  chunkParams: {
    chunkSize: doc.chunk_params.chunk_size,
    overlap: doc.chunk_params.overlap
  }
})

const documents = ref<ReturnType<typeof formatDocument>[]>([])

// 状态过滤选项
const statusOptions = [
  { value: 'all', label: 'All Status' },
  { value: 'pending', label: 'Pending' },
  { value: 'processing', label: 'Processing' },
  { value: 'success', label: 'Success' },
  { value: 'error', label: 'Error' },
]

// 切片方法选项
const chunkMethodOptions = [
  {
    value: 'fixed',
    label: 'Fixed Size',
    description: 'Fixed-size chunking, suitable for structured documents'
  },
  {
    value: 'smart',
    label: 'Smart Segmentation',
    description: 'Intelligent semantic chunking, suitable for natural language content'
  },
  {
    value: 'markdown',
    label: 'Markdown Structure',
    description: 'Split into blocks according to Markdown heading structure'
  },
]

// 表格列定义
const columns = [
  {
    accessorKey: 'file_name',
    header: 'Document Name',
    cell: ({ row }) => h('div', { class: 'font-medium' }, row.original.file_name)
  },
  {
    accessorKey: 'chunk_method',
    header: 'Chunk Method',
    cell: ({ row }) => h('div', chunkMethodOptions.find(m => m.value === row.original.chunk_method)?.label)
  },
  {
    accessorKey: 'chunk_params.chunk_size',
    header: 'Chunk Size',
    cell: ({ row }) => h('div', `${row.original.chunk_params.chunk_size} chars`)
  },
  {
    accessorKey: 'chunk_params.overlap',
    header: 'Overlap',
    cell: ({ row }) => h('div', `${row.original.chunk_params.overlap} chars`)
  },
  {
    accessorKey: 'upload_time',
    header: 'Upload Time',
    cell: ({ row }) => dayjs(row.original.upload_time).format('YYYY-MM-DD HH:mm')
  }
  ,
  {
    accessorKey: 'enabled',
    header: 'Status',
    cell: ({ row }) => h(Switch, {
      checked: row.getValue('enabled'),
      onUpdate: (checked) => row.original.enabled = checked
    }, () => null) // 添加空函数插槽
  },
  {
    accessorKey: 'parsingStatus',
    header: 'Parsing Status',
    cell: ({ row }) => {
      const status = row.getValue('parsingStatus')
      const variantMap = {
        pending: 'secondary',
        processing: 'default',
        success: 'success',
        error: 'destructive'
      }
      return h(Badge, {
        variant: variantMap[status]
      }, () => status) // 添加函数包裹
    }
  },
  {
    id: 'actions',
    header: 'Actions',
    cell: ({ row }) => {
      const document = row.original

      // 创建工具提示的通用函数
      const createTooltipButton = (trigger: any, content: string) => {
        return h(
          Tooltip,
          {},
          {
            default: () => [
              h(TooltipTrigger, { asChild: true }, () => trigger),
              h(TooltipContent, {}, () => content) // 统一使用函数返回内容
            ]
          }
        )
      }

      return h('div', { class: 'flex gap-2' }, [
        // 解析按钮
        // createTooltipButton(
        //   h(
        //     Button,
        //     {
        //       variant: 'ghost',
        //       size: 'sm',
        //       onClick: () => handleParse(document.id),
        //       disabled: document.parsingStatus === 'processing'
        //     },
        //     () => h(Play, { class: 'h-4 w-4' })
        //   ),
        //   document.parsingStatus === 'processing' ? 'Parsing...' : 'Start parsing'
        // ),

        // 分块设置按钮
        createTooltipButton(
          h(
            Button,
            {
              variant: 'ghost',
              size: 'sm',
              onClick: () => showChunkSettings(document)
            },
            () => h(Settings, { class: 'h-4 w-4' })
          ),
          `Chunk settings (current: ${document.chunkParams?.chunkSize || 1024} chars)`
        ),

        // 下载按钮
        createTooltipButton(
          h(
            Button,
            {
              variant: 'ghost',
              size: 'sm',
              onClick: () => handleDownload(document.id),
              disabled: !document.filePath
            },
            () => h(Download, { class: 'h-4 w-4' })
          ),
          document.filePath ? 'Download original' : 'File unavailable'
        ),

        // 删除按钮
        createTooltipButton(
          h(
            Button,
            {
              variant: 'ghost',
              size: 'sm',
              onClick: () => showDeleteConfirm(row.original)
            },
            () => h(Trash2, { class: 'h-4 w-4 text-destructive' })
          ),
          `Confirm delete: ${document.name}`
        )
      ])
    }
  }
]


// 删除相关状态
const isDeleteConfirmOpen = ref(false)
const currentDeleteDocument = ref<KnowledgeDocument | null>(null)

// 显示删除确认对话框
const showDeleteConfirm = (doc: KnowledgeDocument) => {
  currentDeleteDocument.value = doc
  isDeleteConfirmOpen.value = true
}

// 执行删除操作
const confirmDelete = async () => {
  if (!currentDeleteDocument.value) return

  const docId = currentDeleteDocument.value.id
  const docName = currentDeleteDocument.value.file_name

  toast.promise(
    apiDocument.delete(docId),
    {
      loading: `Deleting ${docName}...`,
      success: () => {
        loadDocuments()
        return `${docName} Deleted successfully`
      },
      error: (error: any) => {
        const errorMsg = error.response?.data?.detail || error.message
        return `Deletion failed: ${errorMsg}`
      }
    }
  )

  isDeleteConfirmOpen.value = false
}

// 文件上传相关状态
const isUploadDialogOpen = ref(false)
const uploadFile = ref<File | null>(null)
const chunkSettings = ref({
  method: 'fixed',
  chunkSize: 1024,
  overlap: 128,
  separator: '\\n\\n'
})

// 分块设置对话框
const isChunkSettingsOpen = ref(false)
const currentDocument = ref<KnowledgeDocument | null>(null)

// 显示分块设置对话框
const showChunkSettings = (doc: KnowledgeDocument) => {
  currentDocument.value = {
    ...doc,
    // 初始化 chunkParams 如果不存在
    chunkParams: doc.chunkParams || {
      chunkSize: 1024,
      overlap: 128,
      separator: '\n\n'
    }
  }
  isChunkSettingsOpen.value = true
}

// 处理文档解析
const handleParse = async (id: string) => {
  const doc = documents.value.find(d => d.id === id)
  if (doc) {
    doc.parsingStatus = 'processing'
    // 实际应调用API
    setTimeout(() => {
      doc.parsingStatus = 'success'
      doc.chunks = Math.floor(Math.random() * 100) + 1
    }, 2000)
  }
}



// 其他交互逻辑（删除、下载等）与示例类似，此处省略...

// TanStack Table配置（与示例类似）
const sorting = ref<SortingState>([])
const columnFilters = ref<ColumnFiltersState>([])
const columnVisibility = ref<VisibilityState>({})
const rowSelection = ref({})

const table = useVueTable({
  data: documents.value,
  columns,
  getCoreRowModel: getCoreRowModel(),
  getPaginationRowModel: getPaginationRowModel(),
  getSortedRowModel: getSortedRowModel(),
  getFilteredRowModel: getFilteredRowModel(),
  state: {
    get columnVisibility() { return columnVisibility.value },
    get rowSelection() { return rowSelection.value },
    get sorting() { return sorting.value },
    get columnFilters() { return columnFilters.value }
  },
  onStateChange: (state) => {
    // 保持状态同步
    sorting.value = state.sorting
    columnFilters.value = state.columnFilters
    columnVisibility.value = state.columnVisibility
    rowSelection.value = state.rowSelection
  }
})

const handleUploadButtonClick = () => {
  if (!selectedKnowledgeBaseId.value) {
    toast.warning('Please select a knowledge base first', {
      description: 'You need to select a knowledge base first before uploading documents.'
    })
    return
  }
  isUploadDialogOpen.value = true
}



const saveChunkSettings = async () => {
  try {
    if (!currentDocument.value) {
      toast.error('No document selected')
      return
    }

    // 参数验证
    if (chunkSettings.value.chunkSize < 100 || chunkSettings.value.chunkSize > 5000) {
      toast.error('Chunk size must be between 100-5000 characters')
      return
    }

    if (chunkSettings.value.overlap < 0 || chunkSettings.value.overlap > chunkSettings.value.chunkSize) {
      toast.error(`Overlap must be between 0-${chunkSettings.value.chunkSize}`)
      return
    }

    const toastId = toast.loading('Saving settings...')

    // 构建符合接口的参数
    const queryParams = new URLSearchParams({
      chunk_method: chunkSettings.value.method
    })

    const payload = {
      chunk_size: chunkSettings.value.chunkSize,
      overlap: chunkSettings.value.overlap
    }

    // 调用更新接口
    await apiDocument.update(
      currentDocument.value.id,
      queryParams,
      payload
    )

    // 更新本地数据
    const index = documents.value.findIndex(d => d.id === currentDocument.value?.id)
    if (index > -1) {
      documents.value[index] = {
        ...documents.value[index],
        chunk_method: chunkSettings.value.method,
        chunk_params: {
          ...documents.value[index].chunk_params,
          ...payload
        }
      }
    }

    toast.success('Settings saved', { id: toastId })
    isChunkSettingsOpen.value = false
  } catch (error: any) {
    const errorMsg = error.response?.data?.detail || error.message
    toast.error('Save failed', {
      description: errorMsg || 'Please check your network connection'
    })
  }
}


import { FileSearchIcon, Loader2Icon } from 'lucide-vue-next'

// 状态管理
const isParsing = ref(false)

// 轮询相关状态
const pollingInterval = ref<NodeJS.Timeout | null>(null)
const isProcessing = ref(false)
// 观察选中的知识库ID变化
watch(selectedKnowledgeBaseId, (newId, oldId) => {
  if (newId !== oldId) {
    // ID变化时停止之前的轮询
    stopPolling()
    // 启动新轮询
    if (newId) startPolling(newId)
  }
})

// 组件卸载时清理
onUnmounted(() => {
  stopPolling()
})

// 启动轮询
const startPolling = (kbId: number) => {
  // 立即获取一次状态
  checkProcessingStatus(kbId)
  
  // 设置定时轮询
  pollingInterval.value = setInterval(async () => {
    await checkProcessingStatus(kbId)
  }, 5000) // 每5秒轮询一次
}

// 停止轮询
const stopPolling = () => {
  if (pollingInterval.value) {
    clearInterval(pollingInterval.value)
    pollingInterval.value = null
  }
  isProcessing.value = false
}

// 检查处理状态
const checkProcessingStatus = async (kbId: number) => {
  try {
    const { data } = await apiKnowledgeBase.getDetail(kbId)
    
    // 更新知识库列表中的状态
    const kbIndex = knowledgeBases.value.findIndex(kb => kb.id === kbId)
    if (kbIndex > -1) {
      knowledgeBases.value[kbIndex].processing_status = data.processing_status
    }

    // 根据状态控制轮询
    if (['completed', 'failed'].includes(data.processing_status)) {
      stopPolling()
    } else {
      isProcessing.value = true
    }

    // 如果是当前选中的知识库，更新解析按钮状态
    if (selectedKnowledgeBaseId.value === kbId) {
      isParsing.value = data.processing_status === 'processing'
    }
  } catch (error) {
    console.error('状态检查失败:', error)
    stopPolling()
  }
}


const handleParseDocuments = async () => {
  try {
    if (!selectedKnowledgeBaseId.value) return
    
    isParsing.value = true
    const { data } = await apiKnowledgeBase.processDocuments(selectedKnowledgeBaseId.value)
    
    // 启动轮询
    startPolling(selectedKnowledgeBaseId.value)
    
    toast.info('Processing started', {
      description: `Monitor URL: ${data.monitor_url}`,
      action: {
        label: 'Open',
        onClick: () => window.open(data.monitor_url, '_blank')
      }
    })
    
  } catch (error: any) {
    isParsing.value = false
    const errorMsg = error.response?.data?.detail || error.message
    toast.error('Failed to start processing', {
      description: errorMsg
    })
  }
}


const getStatusBadge = (status?: string) => {
  switch (status) {
    case 'processing': return 'default'
    case 'completed': return 'success'
    case 'failed': return 'destructive'
    default: return 'secondary'
  }
}

const formatStatus = (status?: string) => {
  switch (status) {
    case 'processing': return 'Processing'
    case 'completed': return 'Completed'
    case 'failed': return 'Failed'
    default: return 'Pending'
  }
}
</script>

<template>
  <div class="p-4">
    <div class="flex justify-between items-center mb-6">
      <h1 class="text-2xl font-bold">Knowledge Data Base</h1>
      <div class="flex gap-2">
        <Button @click="handleUploadButtonClick" :disabled="!selectedKnowledgeBaseId">
          <FileUp class="mr-2 h-4 w-4" />
          Upload Document
        </Button>
      </div>
    </div>

    <!-- 过滤和搜索区域 -->
    <div class="flex gap-4 mb-6">
      <Select v-model="selectedKnowledgeBaseId" @update:model-value="handleKnowledgeBaseChange" :disabled="isLoading">
        <SelectTrigger class="w-[200px]">
          <SelectValue>
            <span v-if="!selectedKnowledgeBaseId">Select Knowledge Base</span>
          </SelectValue>
        </SelectTrigger>
        <SelectContent>
          <template v-if="isLoading">
            <SelectItem disabled value="loading">
              Loading...
            </SelectItem>
          </template>
          <template v-else-if="knowledgeBases.length">
            <SelectItem v-for="kb in knowledgeBases" :key="kb.id" :value="kb.id">
              {{ kb.name }}
            </SelectItem>
          </template>
          <template v-else>
            <SelectItem disabled value="no-data">
              {{ error ? error.message : 'No knowledge base available' }}
            </SelectItem>
          </template>
        </SelectContent>
      </Select>

      <Input placeholder="Search documents..." class="max-w-sm"
        :model-value="table.getColumn('file_name')?.getFilterValue()"
        @update:model-value="table.getColumn('file_name')?.setFilterValue" />

      <Select :model-value="table.getColumn('parsingStatus')?.getFilterValue() || 'all'" @update:model-value="value => {
        table.getColumn('parsingStatus')?.setFilterValue(value === 'all' ? undefined : value)
      }">
        <SelectTrigger class="w-[180px]">
          <SelectValue placeholder="Filter by status" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem v-for="status in statusOptions" :value="status.value">
            {{ status.label }}
          </SelectItem>
        </SelectContent>
      </Select>
      <Button 
        variant="secondary" 
        size="sm" 
        class="h-9 gap-1"
        @click="handleParseDocuments"
        :disabled="!selectedKnowledgeBaseId || isParsing"
      >
        <FileSearchIcon v-if="!isParsing" class="h-4 w-4" />
        <Loader2Icon v-else class="h-4 w-4 animate-spin" />
        {{ isProcessing ? 'Processing...' : 'Parse Documents' }}
      </Button>

      <!-- 状态指示器 -->
      <div v-if="selectedKnowledgeBaseId" class="flex items-center gap-2 text-sm text-muted-foreground">
        <span>Knowledge Base Status:</span>
        <Badge :variant="getStatusBadge(knowledgeBases.find(kb => kb.id === selectedKnowledgeBaseId)?.processing_status)">
          {{ formatStatus(knowledgeBases.find(kb => kb.id === selectedKnowledgeBaseId)?.processing_status) }}
        </Badge>
      </div>
    </div>

    <!-- 数据表格 -->
    <Table>
      <TableHeader>
        <TableRow v-for="headerGroup in table.getHeaderGroups()" :key="headerGroup.id">
          <TableHead v-for="header in headerGroup.headers" :key="header.id">
            <FlexRender v-if="!header.isPlaceholder" :render="header.column.columnDef.header"
              :props="header.getContext()" />
          </TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow v-if="isLoadingDocuments">
          <TableCell :colspan="columns.length" class="h-24 text-center">
            <div class="flex items-center justify-center gap-2">
              <Loader2 class="h-4 w-4 animate-spin" />
              Loading document...
            </div>
          </TableCell>
        </TableRow>
        <TableRow v-else-if="documents.length === 0">
          <TableCell :colspan="columns.length" class="h-24 text-center">
            No documents in the current knowledge base.
          </TableCell>
        </TableRow>
        <TableRow v-for="row in table.getRowModel().rows" :key="row.id" :data-state="row.getIsSelected() && 'selected'">
          <TableCell v-for="cell in row.getVisibleCells()" :key="cell.id">
            <FlexRender :render="cell.column.columnDef.cell" :props="cell.getContext()" />
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>

    <!-- 分页控制（参考示例） -->

    <!-- 上传文档对话框 -->
    <Dialog v-model:open="isUploadDialogOpen">
      <DialogContent class="sm:max-w-2xl">
        <DialogHeader>
          <DialogTitle>Upload Document</DialogTitle>
          <DialogDescription>
            Supported formats: PDF, Markdown, TXT (Max 200MB)
          </DialogDescription>
        </DialogHeader>

        <div class="grid gap-4 py-4">
          <div class="grid grid-cols-2 gap-4">
            <div class="space-y-2">
              <Input type="file" @change="handleFileChange" />
              <div class="text-sm text-muted-foreground">
                Recommended: Documents under 2000 pages with clear structure
              </div>
            </div>
            <!-- 修改分块参数输入布局 -->
            <div class="space-y-4">

              <div class="grid grid-cols-[auto_1fr] items-center gap-4">
                <span class="text-sm text-muted-foreground">Chunk Method:</span>
                <Select v-model="chunkSettings.method">
                  <SelectTrigger class="w-full">
                    <SelectValue placeholder="Select chunk method" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem v-for="method in chunkMethodOptions" :key="method.value" :value="method.value">
                      {{ method.label }}
                    </SelectItem>
                  </SelectContent>
                </Select>
              </div>



              <div class="grid grid-cols-[auto_1fr] items-center gap-4">
                <span class="text-sm text-muted-foreground">Chunk size:</span>
                <div class="flex items-center gap-2">
                  <Input v-model.number="chunkSettings.chunkSize" type="number" min="100" max="5000" />
                  <span class="text-sm">characters</span>
                </div>
              </div>

              <div class="grid grid-cols-[auto_1fr] items-center gap-4">
                <span class="text-sm text-muted-foreground">Overlap:</span>
                <div class="flex items-center gap-2">
                  <Input v-model.number="chunkSettings.overlap" type="number" :min="0" :max="chunkSettings.chunkSize" />
                  <span class="text-sm">characters</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button @click="handleFileUpload">Start Upload</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>

    <!-- 分块设置对话框 -->
    <Dialog v-model:open="isChunkSettingsOpen">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Chunk Parameters</DialogTitle>
        </DialogHeader>

        <div class="space-y-6">
          <!-- 方法选择 -->
          <div class="grid grid-cols-[120px_1fr] items-center gap-4">
            <span class="text-sm font-medium text-muted-foreground">Chunk Method</span>
            <Select v-model="chunkSettings.method">
              <SelectTrigger class="w-full">
                <!-- 自定义选中显示 -->
                <SelectValue>
                  <span class="truncate">
                    {{chunkMethodOptions.find(m => m.value === chunkSettings.method)?.label || 'Select method'}}
                  </span>
                </SelectValue>
              </SelectTrigger>

              <SelectContent class="min-w-[300px]">
                <SelectItem v-for="method in chunkMethodOptions" :key="method.value" :value="method.value">
                  <!-- 保持下拉项的完整信息 -->
                  <div class="flex flex-col">
                    <span class="font-medium truncate">{{ method.label }}</span>
                    <span class="text-xs text-muted-foreground truncate">{{ method.description }}</span>
                  </div>
                </SelectItem>
              </SelectContent>
            </Select>
          </div>

          <!-- 分块参数 -->
          <div class="space-y-4">
            <!-- 分块大小 -->
            <div class="grid grid-cols-[120px_1fr] items-center gap-4">
              <div class="space-y-1">
                <span class="text-sm font-medium text-muted-foreground">Chunk Size</span>
                <p class="text-xs text-muted-foreground">100-5000 characters</p>
              </div>
              <div class="flex items-center gap-2">
                <Input v-model.number="chunkSettings.chunkSize" type="number" class="w-32" min="100" max="5000" />
                <span class="text-sm text-muted-foreground">characters</span>
              </div>
            </div>

            <!-- 重叠字符 -->
            <div class="grid grid-cols-[120px_1fr] items-center gap-4">
              <div class="space-y-1">
                <span class="text-sm font-medium text-muted-foreground">Overlap</span>
                <p class="text-xs text-muted-foreground">0-{{ chunkSettings.chunkSize }} characters</p>
              </div>
              <div class="flex items-center gap-2">
                <Input v-model.number="chunkSettings.overlap" type="number" class="w-32" :min="0"
                  :max="chunkSettings.chunkSize" />
                <span class="text-sm text-muted-foreground">characters</span>
              </div>
            </div>
          </div>
        </div>

        <DialogFooter>
          <Button @click="saveChunkSettings">Save Settings</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>



    <!-- 添加确认对话框 -->
    <Dialog v-model:open="isDeleteConfirmOpen">
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Confirm deletion?</DialogTitle>
        </DialogHeader>
        <DialogDescription>
          Confirm deletion {{ currentDeleteDocument?.file_name }} ？
        </DialogDescription>
        <DialogFooter>
          <Button @click="isDeleteConfirmOpen = false">Cancel</Button>
          <Button variant="destructive" @click="confirmDelete">Confirm Deletion</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  </div>
</template>
