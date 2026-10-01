import { defineConfig } from 'vitest/config';
import path from 'node:path';

/**
 * 探针反转配置（CHAT-CONTEXT-BUDGET v1）。
 * 从仓库根运行：`npx vitest run --config docs/qa/CHAT-CONTEXT-BUDGET/probe-reversal/product-path-probe.config.ts`
 */
export default defineConfig({
  resolve: { alias: { '@': path.resolve('apps/web/src') } },
  test: {
    environment: 'jsdom',
    include: ['docs/qa/CHAT-CONTEXT-BUDGET/probe-reversal/product-path-probe.test.ts'],
  },
});
