import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from '@playwright/test';
import original from '../../../playwright.config';

const batch = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(batch, '..', '..', '..');
const run = process.env.ZQKY_B4_QA_RUN ?? 'first';
if (!/^[a-z0-9-]+$/.test(run)) throw new Error('Invalid B4 evidence run');

// Full original suite, unchanged assertions/workers/timeouts. User owns 5174.
export default defineConfig({
  ...original,
  testDir: path.join(repo, 'tests', 'e2e'),
  webServer: undefined,
  outputDir: path.join(batch, `b4-e2e-${run}`, 'artifacts'),
  reporter: [
    ['list'],
    ['json', { outputFile: path.join(batch, `b4-e2e-${run}`, 'results.json') }],
    ['junit', { outputFile: path.join(batch, `b4-e2e-${run}`, 'results.xml') }],
  ],
});
