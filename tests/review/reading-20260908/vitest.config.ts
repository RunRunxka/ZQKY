import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  resolve: { alias: { '@': path.resolve('apps/web/src') } },
  test: {
    environment: 'jsdom',
    include: ['tests/review/reading-20260908/*.probe.ts'],
    setupFiles: ['./tests/setup.ts'],
  },
});
