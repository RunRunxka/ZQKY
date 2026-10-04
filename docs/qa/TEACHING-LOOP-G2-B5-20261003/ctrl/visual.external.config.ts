import { defineConfig } from '@playwright/test';
import path from 'node:path';
import { existsSync } from 'node:fs';
import original from '../../../../playwright.config';
const label = process.env.G2_VISUAL_RUN;
if (!label || !/^[a-z0-9-]+$/.test(label)) throw new Error('A new visual label is required');
const output = path.resolve(`docs/qa/TEACHING-LOOP-G2-B5-20261003/visual-${label}`);
if (process.env.TEST_WORKER_INDEX === undefined && existsSync(output)) throw new Error('Refusing to replace a visual run');
export default defineConfig({ ...original, testDir: path.resolve('docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl'),
  testMatch: 'visual.spec.ts', webServer: undefined, outputDir: path.join(output, 'artifacts'),
  reporter: [['list'], ['json', { outputFile: path.join(output, 'results.json') }]], use: { ...original.use, trace: 'on' },
});
