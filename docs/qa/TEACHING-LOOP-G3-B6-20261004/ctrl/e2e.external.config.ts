import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { existsSync } from 'node:fs';
import original from '../../../../playwright.config';

const label = process.env.G3_E2E_RUN;
if (!label || !/^[a-z0-9-]+$/.test(label)) throw new Error('A fresh G3_E2E_RUN label is required');
const output = path.resolve(`docs/qa/TEACHING-LOOP-G3-B6-20261004/e2e-${label}`);
if (process.env.TEST_WORKER_INDEX === undefined && existsSync(output)) throw new Error('Refusing to replace E2E evidence');
export default defineConfig({ ...original, testDir: path.resolve('tests/e2e'), webServer: undefined,
  workers: 1, retries: 0, fullyParallel: false, outputDir: path.join(output, 'artifacts'),
  reporter: [['list'], ['json', { outputFile: path.join(output, 'results.json') }], ['junit', { outputFile: path.join(output, 'results.xml') }]],
});
