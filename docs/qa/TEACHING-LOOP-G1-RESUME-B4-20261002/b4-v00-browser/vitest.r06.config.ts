import { defineConfig } from 'vitest/config';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const folder = path.dirname(fileURLToPath(import.meta.url));
const repository = path.resolve(folder, '../../../..');
export default defineConfig({
  resolve: { alias: { '@': path.join(repository, 'apps/web/src') } },
  test: {
    environment: 'jsdom',
    include: [path.join(folder, 'r06-readiness.test.tsx').replaceAll('\\', '/')],
    setupFiles: [path.join(repository, 'tests/setup.ts')],
    fileParallelism: false,
  },
});
