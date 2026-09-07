import { defineConfig } from '@playwright/test'

const external = process.env.PILOT_E2E_BASE_URL
export default defineConfig({
  testDir: './e2e',
  timeout: 30000,
  workers: 1,
  use: { baseURL: external || 'http://127.0.0.1:8767', viewport: { width: 1366, height: 768 }, trace: 'retain-on-failure' },
  projects: process.platform === 'win32'
    ? [{ name: 'windows-edge', use: { browserName: 'chromium', channel: 'msedge' } }]
    : [{ name: 'firefox', use: { browserName: 'firefox' } }, { name: 'chromium', use: { browserName: 'chromium' } }],
  webServer: external ? undefined : {
    command: `${process.env.PILOT_E2E_PYTHON || 'python'} ../tests/web_browser_server.py`,
    env: { PYTHONPATH: '../src' },
    url: 'http://127.0.0.1:8767/',
    reuseExistingServer: false,
  },
})
