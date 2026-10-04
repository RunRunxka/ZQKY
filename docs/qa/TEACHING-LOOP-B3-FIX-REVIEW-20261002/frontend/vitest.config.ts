import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  cacheDir: path.resolve(__dirname, '.vite-cache'),
  resolve: { alias: { '@': path.resolve('apps/web/src') } },
  esbuild: { jsx: 'automatic' },
  test: {
    environment: 'jsdom',
    include: ['docs/qa/TEACHING-LOOP-B3-FIX-REVIEW-20261002/frontend/*.test.tsx'],
    setupFiles: [path.resolve('tests/setup.ts')],
    testTimeout: 12000,
    maxWorkers: 1,
  },
});
