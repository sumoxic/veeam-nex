import { fileURLToPath, URL } from 'node:url'

import vue from '@vitejs/plugin-vue'
import AutoImport from 'unplugin-auto-import/vite'
import Components from 'unplugin-vue-components/vite'
import { ElementPlusResolver } from 'unplugin-vue-components/resolvers'
import { defineConfig } from 'vite'

// 开发模式下前端 5174 直连后端 18000；生产由 Nginx 反代 /api
const API_TARGET = process.env.VITE_API_TARGET || 'http://127.0.0.1:18000'

// 按需加载的组件样式必须预声明，否则 Vite 首次发现新依赖会整页 reload，
// 刷新会丢掉内存中的登录态，表现为“点开新模块就被踢回登录页”。
const ELEMENT_COMPONENTS = [
  'alert', 'aside', 'button', 'container', 'date-picker', 'descriptions',
  'descriptions-item', 'dialog', 'drawer', 'dropdown', 'dropdown-item',
  'dropdown-menu', 'empty', 'form', 'form-item', 'header', 'icon', 'input',
  'input-number', 'loading', 'main', 'menu', 'menu-item', 'message',
  'message-box', 'notification', 'option', 'pagination', 'radio', 'radio-group',
  'result', 'select', 'switch', 'table', 'table-column', 'tab-pane', 'tabs',
  'tag', 'text', 'base',
]

export default defineConfig({
  plugins: [
    vue(),
    AutoImport({
      imports: ['vue', 'vue-router', 'pinia'],
      resolvers: [ElementPlusResolver()],
      dts: 'src/types/auto-imports.d.ts',
    }),
    Components({
      resolvers: [ElementPlusResolver()],
      dts: 'src/types/components.d.ts',
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  optimizeDeps: {
    include: [
      'element-plus/es',
      ...ELEMENT_COMPONENTS.map((name) => `element-plus/es/components/${name}/style/css`),
    ],
  },
  server: {
    host: '0.0.0.0',
    port: 5174,
    strictPort: true,
    proxy: {
      '/api': {
        target: API_TARGET,
        changeOrigin: true,
      },
    },
  },
  build: {
    outDir: 'dist',
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      output: {
        manualChunks: {
          vue: ['vue', 'vue-router', 'pinia'],
          element: ['element-plus'],
          charts: ['echarts'],
        },
      },
    },
  },
})
