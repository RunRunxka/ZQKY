import { defineConfig } from '@playwright/test';
export default defineConfig({
  testDir: '.', testMatch: 'real-browser.spec.ts', workers: 1, fullyParallel: false,
  timeout: 180_000, expect: { timeout: 15_000 },
  outputDir: 'browser-artifacts',
  reporter: [['list'], ['json', { outputFile: 'docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-fe/browser-results.json' }]],
  use: { baseURL: 'http://127.0.0.1:5174', viewport: { width: 1440, height: 900 },
    channel: process.env.PLAYWRIGHT_CHANNEL ?? 'msedge', trace: 'retain-on-failure' },
  // root/user own the already-built 5174 and real 8001. This config starts no servers.
});
