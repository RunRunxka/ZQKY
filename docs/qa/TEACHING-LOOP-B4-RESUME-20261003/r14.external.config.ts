import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from '@playwright/test';
import original from '../../../playwright.config';

const batch = path.dirname(fileURLToPath(import.meta.url));
const run = process.env.ZQKY_B4_R14_RUN ?? 'first';
if (!/^[a-z0-9-]+$/.test(run)) throw new Error('Invalid independent R14 evidence run');

export default defineConfig({
  ...original,
  testDir: path.join(batch, 'b4-v00-e2e'),
  testMatch: '**/r14-recovery.spec.ts',
  webServer: undefined,
  outputDir: path.join(batch, `r14-${run}`, 'artifacts'),
  reporter: [
    ['list'],
    ['json', { outputFile: path.join(batch, `r14-${run}`, 'results.json') }],
    ['junit', { outputFile: path.join(batch, `r14-${run}`, 'results.xml') }],
  ],
  use: { ...original.use, trace: 'on' },
});
