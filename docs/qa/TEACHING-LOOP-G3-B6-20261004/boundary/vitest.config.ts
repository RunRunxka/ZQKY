import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  resolve: { alias: { '@': path.resolve('apps/web/src') } },
  test: {
    environment: 'jsdom',
    include: ['docs/qa/TEACHING-LOOP-G3-B6-20261004/boundary/*.test.{ts,tsx}'],
    setupFiles: ['./tests/setup.ts'],
    testTimeout: 10000,
  },
});
