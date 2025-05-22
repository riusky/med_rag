<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle, CardFooter } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { toast } from 'vue-sonner'
import {
  Settings,
  Folder,
  Calendar,
  Plus,
  Trash2
} from 'lucide-vue-next'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  DialogDescription
} from '@/components/ui/dialog'
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from '@/components/ui/alert-dialog'
import { apiKnowledgeBase } from '@/api/knowledgeBase'
import { setBreadcrumbs } from '@/composables/breadcrumbs'


setBreadcrumbs([{ name: 'Document Manage', to: '/knowledge' }, { name: 'Knowledge Data Base' }])


interface KnowledgeBase {
  id: number  // 修改为number类型
  name: string
  description?: string
  document_count: number
  created_at: string
}

// const { toast } = useToast()
const router = useRouter()
const isDialogOpen = ref(false)
const confirmDeleteId = ref<number | null>(null)
const isLoading = ref(true)
const error = ref<Error | null>(null)

// 知识库数据
const knowledgeBases = ref<KnowledgeBase[]>([])

// 新建表单
const newKB = ref({
  name: '',
  description: ''
})

// 加载知识库列表
const loadKnowledgeBases = async () => {
  try {
    isLoading.value = true
    const { data } = await apiKnowledgeBase.getList({
      limit: 100
    })
    knowledgeBases.value = data
  } catch (err) {
    error.value = err as Error
    toast.error('Failed to load', {
      description: 'Failed to retrieve the knowledge base list. Please try again later.'
    })
  } finally {
    isLoading.value = false
  }
}

// 创建知识库
const createKnowledgeBase = async () => {
  try {
    if (!newKB.value.name.trim()) {
      toast.warning('Name cannot be empty', {
        description: 'Please enter a valid knowledge base name'
      })
      return
    }

    const { data } = await apiKnowledgeBase.create({
      name: newKB.value.name,
      description: newKB.value.description
    })

    knowledgeBases.value.unshift(data)
    newKB.value = { name: '', description: '' }
    isDialogOpen.value = false
    
    toast.success(`"${data.name}" created`, {
      description: 'Knowledge base creation time:' + new Date().toLocaleDateString(),
      action: {
        label: 'view',
        onClick: () => router.push(`/knowledge/${data.id}`)
      }
    })
  } catch (err) {
    toast.error('Creation failed', {
      description: err.message || 'Unknown error, please check your network connection'
    })
    throw err
  }
}

// 删除知识库
const deleteKnowledgeBase = async (id: number | null) => {
  if (!id) return

  const targetKB = knowledgeBases.value.find(kb => kb.id === id)
  let undoDeleted = false

  try {
    // 先移除本地数据
    knowledgeBases.value = knowledgeBases.value.filter(kb => kb.id !== id)
    
    await apiKnowledgeBase.delete(id)
    
    toast('Deleted successfully', {
      description: `Deleted knowledge base "${targetKB?.name}"`,
      action: {
        label: 'Cancel',
        onClick: () => {
          undoDeleted = true
          knowledgeBases.value.unshift(targetKB!)
        }
      }
    })
  } catch (err) {
    // 恢复本地数据
    if (!undoDeleted && targetKB) {
      knowledgeBases.value.unshift(targetKB)
    }
    
    toast.error('Deletion failed', {
      description: 'The deletion operation was not completed. Some documents in the knowledge base may not have been deleted. Please try again.'
    })
  } finally {
    confirmDeleteId.value = null
  }
}

// 初始化加载数据
onMounted(() => {
  loadKnowledgeBases()
})
</script>

<template>
  <div class="p-6">
    <!-- 加载状态 -->
    <div v-if="isLoading" class="text-center py-12">
      <div class="animate-spin inline-block w-8 h-8 border-2 border-current border-t-transparent rounded-full" />
      <p class="text-muted-foreground mt-4">Loading knowledge base...</p>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="error" class="text-center py-12 text-destructive">
      <Folder :size="48" class="mx-auto mb-4" />
      <p>Failed to load: {{ error.message }}</p>
      <Button class="mt-4" @click="loadKnowledgeBases">Retry</Button>
    </div>

    <!-- 正常内容 -->
    <template v-else>
      <!-- Header -->
      <div class="flex justify-between items-center mb-8">
        <div>
          <h1 class="text-2xl font-bold">Knowledge Base Management</h1>
          <p class="text-muted-foreground mt-1">
            Total {{ knowledgeBases.length }} knowledge bases
          </p>
        </div>

        <!-- 新建对话框 -->
        <Dialog v-model:open="isDialogOpen">
          <DialogTrigger as-child>
            <Button>
              <Plus :size="16" class="mr-2" />
              Create New
            </Button>
          </DialogTrigger>

          <DialogContent class="sm:max-w-[500px]">
            <DialogHeader>
              <DialogTitle>Create New Knowledge Base</DialogTitle>
              <DialogDescription>
                Add a new knowledge base to organize your documents
              </DialogDescription>
            </DialogHeader>

            <form @submit.prevent="createKnowledgeBase" class="space-y-4">
              <div class="space-y-2">
                <Label>Name</Label>
                <Input 
                  v-model="newKB.name" 
                  placeholder="Enter knowledge base name" 
                  required 
                  :disabled="isLoading"
                />
              </div>

              <div class="space-y-2">
                <Label>Description (optional)</Label>
                <Input 
                  v-model="newKB.description" 
                  placeholder="Enter brief description"
                  :disabled="isLoading"
                />
              </div>

              <div class="flex justify-end gap-2 pt-4">
                <Button 
                  variant="outline" 
                  type="button" 
                  @click="isDialogOpen = false"
                  :disabled="isLoading"
                >
                  Cancel
                </Button>
                <Button type="submit" :disabled="!newKB.name || isLoading">
                  Confirm
                </Button>
              </div>
            </form>
          </DialogContent>
        </Dialog>
      </div>

      <!-- 知识库卡片 -->
      <div v-if="knowledgeBases.length" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <Card 
          v-for="kb in knowledgeBases" 
          :key="kb.id" 
          class="hover:shadow-md transition-shadow relative group"
        >
          <!-- 操作按钮 -->
          <div class="absolute top-3 right-3 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
            <Button 
              variant="ghost" 
              size="sm" 
              class="text-primary/80 hover:text-primary"
              @click.stop="router.push(`/knowledge/${kb.id}`)"
            >
              <Settings :size="16" />
            </Button>

            <!-- 删除确认对话框 -->
            <AlertDialog>
              <AlertDialogTrigger as-child>
                <Button 
                  variant="ghost" 
                  size="sm" 
                  class="text-destructive/80 hover:text-destructive"
                  @click.stop="confirmDeleteId = kb.id"
                >
                  <Trash2 :size="16" />
                </Button>
              </AlertDialogTrigger>

              <AlertDialogContent>
                <AlertDialogHeader>
                  <AlertDialogTitle>Confirm Deletion</AlertDialogTitle>
                  <AlertDialogDescription>
                    Are you sure you want to delete
                    <span class="font-medium">"{{ knowledgeBases.find(k => k.id === confirmDeleteId)?.name }}"</span>?
                    This action cannot be undone.
                  </AlertDialogDescription>
                </AlertDialogHeader>
                <AlertDialogFooter>
                  <AlertDialogCancel @click="confirmDeleteId = null">Cancel</AlertDialogCancel>
                  <AlertDialogAction 
                    class="bg-destructive text-destructive-foreground hover:bg-destructive/90"
                    @click="deleteKnowledgeBase(confirmDeleteId)"
                  >
                    Confirm Delete
                  </AlertDialogAction>
                </AlertDialogFooter>
              </AlertDialogContent>
            </AlertDialog>
          </div>

          <!-- 卡片内容 -->
          <CardHeader class="pb-2">
            <CardTitle class="text-lg truncate">{{ kb.name }}</CardTitle>
          </CardHeader>

          <CardContent>
            <div class="space-y-4">
              <p class="text-sm text-muted-foreground line-clamp-2 h-[40px]">
                {{ kb.description || 'No description' }}
              </p>

              <div class="flex justify-between text-sm text-muted-foreground">
                <div class="flex items-center gap-1">
                  <Folder :size="16" class="stroke-[1.5]" />
                  <span>{{ kb.document_count }} documents</span>
                </div>
                <div class="flex items-center gap-1">
                  <Calendar :size="16" class="stroke-[1.5]" />
                  <span>{{ kb.created_at }}</span>
                </div>
              </div>
            </div>
          </CardContent>

          <!-- 管理按钮 -->
          <CardFooter class="border-t pt-4">
            <Button 
              variant="outline" 
              class="w-full" 
              @click="router.push(`/knowledge/${kb.id}`)"
            >
              <Settings :size="16" class="mr-2 stroke-[1.5]" />
              Manage
            </Button>
          </CardFooter>
        </Card>
      </div>

      <!-- 空状态 -->
      <div v-else class="text-center py-12 border-2 border-dashed rounded-lg">
        <div class="text-muted-foreground mb-4">
          <Folder :size="48" class="mx-auto opacity-50" />
          <p class="mt-2">No knowledge bases found</p>
        </div>
        <Button @click="isDialogOpen = true">
          <Plus :size="16" class="mr-2" />
          Create Now
        </Button>
      </div>
    </template>
  </div>
</template>

<style scoped>
.group:hover {
  transform: translateY(-2px);
  transition: transform 0.2s ease-in-out;
}
</style>