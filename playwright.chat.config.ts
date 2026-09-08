import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/integration',
  workers: 1,
  fullyParallel: false,
  timeout: 45000,
  expect: { timeout: 10000 },
  outputDir: 'test-results/chat-integration',
  reporter: [['list'], ['json', { outputFile: 'test-results/chat-integration.json' }]],
  use: {
    baseURL: 'http://127.0.0.1:5174',
    channel:
      process.env.PLAYWRIGHT_CHANNEL ?? (process.platform === 'win32' ? 'msedge' : undefined),
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: 'uv run --project apps/api python tests/fixtures/stream_backend.py',
      url: 'http://127.0.0.1:8001/api/v1/health',
      reuseExistingServer: false,
      timeout: 30000,
    },
    {
      command: 'node scripts/run-web.mjs start 5174',
      env: { ZQKY_TEST_BUILD: '1', ZQKY_API_ORIGIN: 'http://127.0.0.1:8001' },
      url: 'http://127.0.0.1:5174/chat',
      reuseExistingServer: false,
      timeout: 60000,
    },
  ],
});
