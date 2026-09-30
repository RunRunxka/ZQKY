import { defineConfig } from 'vitest/config';
import path from 'node:path';

// V00 独立验收探针专用配置（不改动仓库 vitest.config.ts）。
// 根指向仓库根；只收集本证据目录里的探针用例；别名 @ 与正式配置一致。
const repoRoot = path.resolve(__dirname, '../../../..');

export default defineConfig({
  root: repoRoot,
  resolve: { alias: { '@': path.join(repoRoot, 'apps/web/src') } },
  test: {
    environment: 'jsdom',
    include: ['docs/qa/TEACHING-LOOP-B0/V00-probes/**/*.test.ts'],
    setupFiles: [path.join(repoRoot, 'tests/setup.ts')],
  },
});
