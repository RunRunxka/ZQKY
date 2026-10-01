import { defineConfig } from 'vitest/config';
import path from 'node:path';

/**
 * V00-G0 前端探针专用 vitest 配置（只读候选：不改根 `vitest.config.ts`）。
 *
 * 动因：仓库根配置的 `test.include` 是 `apps/web/src/**\/*.test.{ts,tsx}`，只读边界
 * 不允许在 `apps/**` 下新建探针文件；本配置把 include 指向
 * `docs/qa/TEACHING-LOOP-B3/V00-probes/**\/*.test.{ts,tsx}`，alias 与 setupFiles
 * 与根配置保持一致。
 */
export default defineConfig({
  resolve: { alias: { '@': path.resolve('apps/web/src') } },
  test: {
    environment: 'jsdom',
    include: ['docs/qa/TEACHING-LOOP-B3/V00-probes/**/*.test.{ts,tsx}'],
    setupFiles: ['./tests/setup.ts'],
  },
});
