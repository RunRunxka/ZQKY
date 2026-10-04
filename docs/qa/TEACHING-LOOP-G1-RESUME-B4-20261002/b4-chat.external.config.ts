import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from '@playwright/test';
import original from '../../../playwright.chat.config';

const batch = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(batch, '..', '..', '..');
const run = process.env.ZQKY_B4_CHAT_RUN ?? 'first';
if (!/^[a-z0-9-]+$/.test(run)) throw new Error('Invalid B4 chat evidence run');

export default defineConfig({
  ...original,
  testDir: path.join(repo, 'tests', 'integration'),
  webServer: undefined,
  outputDir: path.join(batch, `b4-chat-${run}`, 'artifacts'),
  reporter: [
    ['list'],
    ['json', { outputFile: path.join(batch, `b4-chat-${run}`, 'results.json') }],
  ],
});
