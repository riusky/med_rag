<template>
  <DropdownMenu>
    <DropdownMenuTrigger as-child>
      <Button variant="ghost" class="gap-1.5 px-3">
        <SunMoon class="h-4 w-4" />
        <span class="hidden sm:inline">Theme</span>
        <ChevronDown class="h-4 w-4 opacity-50" />
      </Button>
    </DropdownMenuTrigger>

    <DropdownMenuContent 
      class="w-[220px]" 
      align="end"
      :side-offset="8"
    >
      <DropdownMenuLabel class="px-4 py-2 text-xs font-medium text-muted-foreground">
        Theme Preferences
      </DropdownMenuLabel>
      <DropdownMenuSeparator />

      <ScrollArea class="h-[260px]">
        <DropdownMenuGroup>
          <DropdownMenuItem
            v-for="theme in effectiveThemes"
            :key="theme"
            class="cursor-pointer px-4 py-2.5 text-sm"
            :class="{ 'bg-accent/10': currentTheme === theme }"
            @click="setTheme(theme)"
          >
            <div :data-theme="theme" class="flex w-full items-center justify-between">
              <div class="flex items-center gap-3">
                <div class="flex h-5 w-5 items-center justify-center rounded-md border shadow-sm">
                  <div class="flex gap-[2px]">
                    <span class="h-3 w-2 rounded-sm bg-primary" />
                    <span class="h-3 w-2 rounded-sm bg-secondary" />
                    <span class="h-3 w-2 rounded-sm bg-accent" />
                  </div>
                </div>
                <span class="capitalize">
                  {{ themeDisplayNames[theme] || theme }}
                </span>
              </div>
              <Check
                v-if="currentTheme === theme"
                class="h-4 w-4 text-primary"
              />
            </div>
          </DropdownMenuItem>
        </DropdownMenuGroup>
      </ScrollArea>
      
      <DropdownMenuSeparator />
      <!-- <div class="p-2 pt-0">
        <Button
          variant="ghost"
          size="sm"
          class="w-full justify-start text-muted-foreground"
          @click="openThemeConfig"
        >
          <Settings class="mr-2 h-4 w-4" />
          Customize Colors
        </Button>
      </div> -->
    </DropdownMenuContent>
  </DropdownMenu>
</template>

<script setup lang="ts">
import { Check, ChevronDown, Settings, SunMoon } from 'lucide-vue-next'
import { ref, computed, onMounted } from 'vue'
import { themeChange } from 'theme-change'

// Components
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuGroup,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Button } from '@/components/ui/button'
import { ScrollArea } from '@/components/ui/scroll-area'

// 类型定义
type ThemeKey = keyof typeof themeDisplayNames

// 主题显示名称映射（使用常量断言）
const themeDisplayNames = {
  light: 'Light',
  dark: 'Dark',
  cupcake: 'Cupcake',
  bumblebee: 'Bumblebee',
  emerald: 'Emerald',
  corporate: 'Corporate',
  synthwave: 'Synthwave',
  retro: 'Retro',
  cyberpunk: 'Cyberpunk',
  valentine: 'Valentine',
  halloween: 'Halloween',
  garden: 'Garden',
  forest: 'Forest',
  aqua: 'Aqua',
  lofi: 'Lo-Fi',
  pastel: 'Pastel',
  fantasy: 'Fantasy',
  wireframe: 'Wireframe',
  black: 'Black',
  luxury: 'Luxury',
  dracula: 'Dracula',
  cmyk: 'CMYK',
  autumn: 'Autumn',
  business: 'Business',
  acid: 'Acid',
  lemonade: 'Lemonade',
  night: 'Night',
  coffee: 'Coffee',
  winter: 'Winter',
  dim: 'Dim',
  nord: 'Nord',
  sunset: 'Sunset',
  caramellatte: 'Caramellatte',
  abyss: 'Abyss',
  silk: 'Silk'
} as const

// 类型守卫函数
const isThemeKey = (key: string): key is ThemeKey => {
  return Object.keys(themeDisplayNames).includes(key)
}

const props = defineProps<{
  themes?: string[]
}>()

const currentTheme = ref<ThemeKey>('light')

// 初始化主题
onMounted(() => {
  const savedTheme = localStorage.getItem('theme')
  const systemTheme = window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
  
  if (savedTheme && isThemeKey(savedTheme)) {
    currentTheme.value = savedTheme
  } else {
    currentTheme.value = systemTheme as ThemeKey
  }
  
  themeChange(false)
  document.documentElement.setAttribute('data-theme', currentTheme.value)
})

// 有效主题列表
const effectiveThemes = computed<ThemeKey[]>(() => {
  const defaultThemes = Object.keys(themeDisplayNames) as ThemeKey[]
  
  return props.themes?.length 
    ? props.themes.filter(isThemeKey) as ThemeKey[] 
    : defaultThemes
})

// 主题切换方法
const setTheme = (theme: string) => {
  if (!isThemeKey(theme)) return
  
  currentTheme.value = theme
  localStorage.setItem('theme', theme)
  document.documentElement.setAttribute('data-theme', theme)
}

// 打开主题配置
const openThemeConfig = () => {
  // 这里可以添加打开主题配置面板的逻辑
  console.log('Open theme configuration')
}
</script>

<style scoped>
[data-theme] {
  transition: 
    background-color 0.3s cubic-bezier(0.4, 0, 0.2, 1),
    color 0.2s cubic-bezier(0.4, 0, 0.2, 1);
}

.scroll-area-viewport {
  padding-right: 4px;
}
</style>