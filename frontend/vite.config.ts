import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import path from 'node:path'
import tailwindcss from '@tailwindcss/vite'
import Components from 'unplugin-vue-components/vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), tailwindcss(), Components({
    dirs: [path.resolve(__dirname, './src/components'), path.resolve(__dirname, './src/layouts')],
  })],
  server: {
    port: 9091, // 开发服务器端口
    watch: {
      usePolling: true  // 强制文件轮询
    },
    host: true  // 允许外部访问
  },
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
})
