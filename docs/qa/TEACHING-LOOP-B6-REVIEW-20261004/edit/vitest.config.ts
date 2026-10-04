import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  esbuild: { jsx: 'automatic' },
  resolve: { alias: { '@': path.resolve('apps/web/src') } },
  test: {
    environment: 'jsdom',
    include: ['docs/qa/TEACHING-LOOP-B6-REVIEW-20261004/edit/*.test.{ts,tsx}'],
    setupFiles: ['./tests/setup.ts'],
    testTimeout: 10000,
  },
});
