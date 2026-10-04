import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const directory = path.dirname(fileURLToPath(import.meta.url));
const label = process.env.B6_INTEGRATION_RUN;
if (!label || !/^[a-z0-9-]+$/.test(label)) throw new Error('New isolated run label required');
export default defineConfig({ testDir: directory, testMatch: 'five-fields.spec.ts', testIgnore: ['**/qa-source/**', '**/source/**'], workers: 1,
  fullyParallel: false, retries: 0, timeout: 90000, expect: { timeout: 15000 },
  outputDir: path.join(directory, label, 'artifacts'),
  reporter: [['list'], ['json', { outputFile: path.join(directory, label, 'browser-results.json') }]],
  use: { baseURL: 'http://127.0.0.1:5174', viewport: { width: 1440, height: 900 },
    channel: 'msedge', trace: 'on', screenshot: 'only-on-failure' },
  webServer: undefined,
});
