import { defineConfig } from 'vitest/config';
import path from 'node:path';
export default defineConfig({
  resolve: { alias: { '@': path.resolve('apps/web/src') } },
  esbuild: { jsx: 'automatic' },
  test: { environment: 'jsdom', include: ['docs/qa/TEACHING-LOOP-B4-REVIEW-20261003/frontend/*.test.tsx'], setupFiles: ['./tests/setup.ts'] },
});
