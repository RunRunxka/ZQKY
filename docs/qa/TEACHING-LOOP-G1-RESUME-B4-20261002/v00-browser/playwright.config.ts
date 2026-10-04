import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const batchRoot = path.dirname(fileURLToPath(import.meta.url));
const run = process.env.ZQKY_G1_BROWSER_RUN ?? 'collection';
if (!/^[a-z0-9][a-z0-9-]{0,39}$/.test(run)) throw new Error('Invalid isolated browser run identity');
export default defineConfig({
  testDir: '.', testMatch: 'real-browser.spec.ts', workers: 1, fullyParallel: false,
  timeout: 180_000, expect: { timeout: 15_000 },
  outputDir: path.join(batchRoot, `browser-artifacts-${run}`),
  reporter: [['list'], ['json', { outputFile: path.join(batchRoot, `browser-results-${run}.json`) }]],
  use: { baseURL: 'http://127.0.0.1:5174', viewport: { width: 1440, height: 900 },
    channel: process.env.PLAYWRIGHT_CHANNEL ?? 'msedge', trace: 'on', screenshot: 'only-on-failure' },
  // root/user own the already-built 5174 and real 8001. This config starts no servers.
});
