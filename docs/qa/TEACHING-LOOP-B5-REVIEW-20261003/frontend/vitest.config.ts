import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  resolve: { alias: { '@': path.resolve('apps/web/src') } },
  test: {
    environment: 'jsdom',
    include: ['docs/qa/TEACHING-LOOP-B5-REVIEW-20261003/frontend/*.test.{ts,tsx}'],
    setupFiles: ['./tests/setup.ts'],
    testTimeout: 10000,
  },
});
