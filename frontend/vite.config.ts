import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  build: { outDir: '../src/insar_pilot/web/static', emptyOutDir: true },
  server: { proxy: { '/api': { target: 'http://127.0.0.1:8765', ws: true } } },
})
