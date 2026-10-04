import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  cacheDir: path.resolve(__dirname, '.vite-regression-cache'),
  resolve: { alias: { '@': path.resolve('apps/web/src') } },
  esbuild: { jsx: 'automatic' },
  test: {
    environment: 'jsdom',
    include: [
      'apps/web/src/services/use-workflow-job.test.tsx',
      'apps/web/src/components/ui/RichContentRenderer.test.tsx',
      'apps/web/src/features/assessments/AssessmentsPanel.test.tsx',
      'apps/web/src/features/assessments/PaperImportReview.test.tsx',
      'apps/web/src/features/assessments/ParticipantAddPanel.test.tsx',
      'apps/web/src/features/assessments/ParticipantAttendanceEditor.test.tsx',
      'apps/web/src/features/assessments/RosterImportPanel.test.tsx',
      'apps/web/src/features/assessments/ScoreImportReview.test.tsx',
      'apps/web/src/features/assessments/ScorePanel.test.tsx',
      'apps/web/src/features/question-bank/jobs.test.tsx',
      'apps/web/src/features/question-bank/GenerationPanel.test.tsx',
      'apps/web/src/features/question-bank/ReviewWorkspace.test.tsx',
      'apps/web/src/features/question-bank/DraftEditor.guard.test.tsx',
      'apps/web/src/features/question-bank/QuestionDetailLinks.test.tsx',
      'apps/web/src/features/question-bank/QuestionPreview.rich.test.tsx',
    ],
    setupFiles: [path.resolve('tests/setup.ts')],
    testTimeout: 12000,
    maxWorkers: 1,
  },
});
