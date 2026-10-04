import { defineConfig } from 'vitest/config';
import path from 'node:path';

const repository = path.resolve('.');
export default defineConfig({
  cacheDir: path.resolve(__dirname, '.vite-cache'),
  resolve: { alias: { '@': path.join(repository, 'apps/web/src') } },
  esbuild: { jsx: 'automatic' },
  test: {
    environment: 'jsdom',
    include: ['docs/qa/TEACHING-LOOP-B3-FIX-20261002/V00-FRONTEND-probes/*.test.tsx'],
    setupFiles: [path.join(repository, 'tests/setup.ts')],
    testTimeout: 12000,
    maxWorkers: 1,
  },
});
