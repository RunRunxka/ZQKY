import { defineConfig } from 'vitest/config';
import path from 'node:path';
export default defineConfig({
  resolve: { alias: { '@': path.resolve('apps/web/src') } },
  test: {
    environment: 'jsdom',
    include: ['apps/web/src/**/*.test.{ts,tsx}'],
    setupFiles: ['./tests/setup.ts'],
  },
});
