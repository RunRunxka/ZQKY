import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  esbuild: { jsx: 'automatic' },
  resolve: { alias: { '@': path.resolve('apps/web/src') } },
  test: {
    environment: 'jsdom',
    include: ['docs/qa/TEACHING-LOOP-B3-REVIEW-20261001/probes/ui_*.test.{ts,tsx}'],
    setupFiles: ['./tests/setup.ts'],
  },
});
