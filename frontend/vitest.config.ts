import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

export default defineConfig({
  plugins: [vue()],
  resolve: { alias: [{ find: /^quasar$/, replacement: 'quasar/dist/quasar.client.js' }] },
  test: { maxWorkers: 2, include: ['src/**/*.test.ts'] },
})
