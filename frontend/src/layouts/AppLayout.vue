<script setup lang="ts">
import {
  Breadcrumb,
  BreadcrumbItem,
  BreadcrumbLink,
  BreadcrumbList,
  BreadcrumbPage,
  BreadcrumbSeparator,
} from '@/components/ui/breadcrumb'
import { Separator } from '@/components/ui/separator'
import { SidebarInset, SidebarProvider, SidebarTrigger } from '@/components/ui/sidebar'

import { breadcrumbs } from '@/composables/breadcrumbs'

import ThemeChange from "@/components/ThemeChange.vue";

</script>

<template>
  <SidebarProvider>
    <AppSidebar />
    <SidebarInset>
      <header
        class="bg-sidebar flex h-16 shrink-0 items-center gap-2 transition-[width,height] ease-linear group-has-[[data-collapsible=icon]]/sidebar-wrapper:h-12 justify-between"
      >
        <div class="flex items-center gap-2 px-4">
          <SidebarTrigger class="-ml-1" />
          <Separator orientation="vertical" class="mr-2 h-4" />
          <Breadcrumb>
            <BreadcrumbList>
              <template v-for="(item, index) in breadcrumbs" :key="index">
                <BreadcrumbItem class="hidden md:block">
                  <BreadcrumbLink
                    v-if="item.href && index !== breadcrumbs.length - 1"
                    :href="item.href"
                    >{{ item.name }}  SSS</BreadcrumbLink
                  >
                  <BreadcrumbPage v-else>{{ item.name }}</BreadcrumbPage>
                </BreadcrumbItem>
                <BreadcrumbSeparator
                  v-if="index < breadcrumbs.length - 1"
                  class="hidden md:block"
                />
              </template>
            </BreadcrumbList>
          </Breadcrumb>
        </div>
        <div class="flex items-center gap-2 mr-4">
          <Popover>
              <ThemeChange :all-colors="[]" />
          </Popover>
        </div>
      </header>
      <!-- <div class="main-content-container flex flex-1 flex-col gap-4 p-4 pt-0"> -->
      <div class="main-content-container  flex-col gap-4 p-4 pt-0">
      <!-- <div class="gap-4 p-4 pt-0 main-content-container"> -->
        <router-view v-slot="{ Component }">
          <Transition name="fade" mode="out-in">
            <div v-if="Component">
              <Component :is="Component" />
            </div>
          </Transition>
        </router-view>
      </div>
    </SidebarInset>
  </SidebarProvider>
</template>


<style scoped>
.main-content-container {
  box-sizing: border-box; /* 确保 padding 不影响整体尺寸 */
  display: flex;
  height: calc(100vh - 64px); /* 确保该区域撑满父容器 */
  overflow-y: auto; /* 允许纵向滚动 */
}
</style>