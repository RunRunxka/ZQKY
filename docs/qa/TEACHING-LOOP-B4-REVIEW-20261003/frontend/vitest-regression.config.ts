import { defineConfig } from 'vitest/config';
import path from 'node:path';
export default defineConfig({
  resolve: { alias: { '@': path.resolve('apps/web/src') } },
  esbuild: { jsx: 'automatic' },
  test: { environment: 'jsdom', include: ['apps/web/src/features/learning-analysis/LearningAnalysisWorkspace.test.tsx', 'apps/web/src/features/practices/PracticesWorkspace.test.tsx', 'apps/web/src/services/use-workflow-job.test.tsx', 'apps/web/src/services/workflow-jobs-api.test.ts'], setupFiles: ['./tests/setup.ts'] },
});
