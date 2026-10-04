import { defineConfig } from 'vitest/config';
import path from 'node:path';
export default defineConfig({
  esbuild: { jsx: 'automatic' },
  resolve: { alias: { '@': path.resolve('apps/web/src') } },
  cacheDir: path.resolve('docs/qa/TEACHING-LOOP-G1-REVIEW-20261002/frontend/cache'),
  test: {
    environment: 'jsdom', setupFiles: ['./tests/setup.ts'],
    include: ['docs/qa/TEACHING-LOOP-G1-REVIEW-20261002/frontend/*.test.tsx'],
    reporters: ['verbose', 'junit'],
    outputFile: { junit: 'docs/qa/TEACHING-LOOP-G1-REVIEW-20261002/frontend/probes.xml' },
  },
});
