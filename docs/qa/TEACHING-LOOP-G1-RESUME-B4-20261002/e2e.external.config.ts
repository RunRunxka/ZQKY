import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { defineConfig } from '@playwright/test';
import original from '../../../playwright.config';

const batch = path.dirname(fileURLToPath(import.meta.url));
const repo = path.resolve(batch, '..', '..', '..');

// Use the exact existing suite and behavior against the user-owned 5174.
// A missing external service is a missing prerequisite; this config has no fallback.
export default defineConfig({
  ...original,
  testDir: path.join(repo, 'tests', 'e2e'),
  webServer: undefined,
  outputDir: path.join(batch, 'e2e-artifacts'),
  reporter: [
    ['list'],
    ['json', { outputFile: path.join(batch, 'full-e2e-results.json') }],
    ['junit', { outputFile: path.join(batch, 'full-e2e-results.xml') }],
  ],
});
