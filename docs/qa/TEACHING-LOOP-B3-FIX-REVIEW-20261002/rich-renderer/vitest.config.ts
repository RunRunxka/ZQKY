import { defineConfig } from 'vitest/config';
import path from 'node:path';
export default defineConfig({
  esbuild: { jsx: 'automatic' },
  resolve: { alias: { '@': path.resolve('apps/web/src') } },
  test: {
    environment: 'jsdom',
    include: ['docs/qa/TEACHING-LOOP-B3-FIX-REVIEW-20261002/rich-renderer/*.test.tsx'],
    setupFiles: ['./tests/setup.ts'],
  },
});
