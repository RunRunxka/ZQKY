import { defineConfig } from 'vitest/config';
import path from 'node:path';
export default defineConfig({
  esbuild: { jsx: 'automatic' },
  resolve: { alias: [
    { find: '@/features/lesson-plan/components/SourcePanel', replacement: path.resolve('docs/qa/TEACHING-LOOP-B6-REVIEW-20261004/sources/baseline-SourcePanel.tsx') },
    { find: '@', replacement: path.resolve('apps/web/src') },
  ] },
  test: { environment: 'jsdom', include: ['docs/qa/TEACHING-LOOP-B6-REVIEW-20261004/sources/source-intent.test.tsx'], setupFiles: ['./tests/setup.ts'], retry: 0 },
});
