import { defineConfig } from '@playwright/test';
import base from '../../../playwright.config';

export default defineConfig({
  ...base,
  testDir: '.',
  testMatch: '*.probe.spec.ts',
  expect: { timeout: 2500 },
  reporter: 'line',
  webServer: { ...base.webServer, cwd: process.cwd() },
});
