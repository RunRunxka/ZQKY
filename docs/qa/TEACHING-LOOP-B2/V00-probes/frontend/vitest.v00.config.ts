/**
 * V00-B2 独立验收（V8）自建 vitest 配置：只收集本探针目录下的用例，
 * 复用仓库既有 jsdom 环境 / `@` 别名 / jest-dom setup；不改动产品配置。
 *
 * 运行（仓库根）：NODE_OPTIONS=--no-experimental-webstorage npx vitest run \
 *   --config docs/qa/TEACHING-LOOP-B2/V00-probes/frontend/vitest.v00.config.ts
 */
import { defineConfig } from 'vitest/config';
import path from 'node:path';

export default defineConfig({
  resolve: { alias: { '@': path.resolve('apps/web/src') } },
  // 本探针目录在 apps/web 之外：显式用自动 JSX 运行时，避免 classic 运行时要求 React 在作用域
  esbuild: { jsx: 'automatic', jsxImportSource: 'react' },
  test: {
    root: process.cwd(),
    environment: 'jsdom',
    include: ['docs/qa/TEACHING-LOOP-B2/V00-probes/frontend/**/*.test.{ts,tsx}'],
    setupFiles: ['./tests/setup.ts'],
  },
});
