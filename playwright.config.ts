import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: './tests/e2e',
  fullyParallel: false,
  workers: 1,
  timeout: 45000,
  expect: { timeout: 10000 },
  reporter: [['list'], ['json', { outputFile: 'test-results/results.json' }]],
  use: {
    baseURL: 'http://127.0.0.1:5174',
    viewport: { width: 1440, height: 900 },
    channel:
      process.env.PLAYWRIGHT_CHANNEL ?? (process.platform === 'win32' ? 'msedge' : undefined),
    trace: 'retain-on-failure',
  },
  webServer: {
    command: 'node scripts/run-web.mjs start 5174',
    url: 'http://127.0.0.1:5174/lesson-plans',
    reuseExistingServer: false,
    timeout: 60000,
  },
});
