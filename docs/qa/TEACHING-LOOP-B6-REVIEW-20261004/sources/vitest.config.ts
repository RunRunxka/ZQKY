import { defineConfig } from 'vitest/config';
import path from 'node:path';
export default defineConfig({
  resolve: { alias: { '@': path.resolve('apps/web/src') } },
  test: {
    environment: 'jsdom',
    include: ['docs/qa/TEACHING-LOOP-B6-REVIEW-20261004/sources/source-intent.test.tsx', 'apps/web/src/features/lesson-plan/b6-source-loading.test.tsx'],
    setupFiles: ['./tests/setup.ts'],
    retry: 0,
  },
});
