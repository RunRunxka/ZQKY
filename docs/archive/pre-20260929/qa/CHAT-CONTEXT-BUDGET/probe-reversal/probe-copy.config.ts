import { defineConfig } from 'vitest/config';
import path from 'node:path';

/**
 * 冻结探针**副本**的运行配置（CHAT-CONTEXT-BUDGET v1）。
 *
 * 为什么需要它：`probe.test.ts` 是逐字节复制的原探针（保留原样，md5 不变），其中的相对
 * 导入是按原位置 `_work/course-gate-20260922/` 写的；移到本目录后这些相对路径不再指向
 * 真实源码。此处只用 alias 把**同样的导入说明符**映射回真实文件，探针内容一个字未改。
 *
 * 运行（仓库根）：`npx vitest run --config docs/qa/CHAT-CONTEXT-BUDGET/probe-reversal/probe-copy.config.ts`
 */
export default defineConfig({
  resolve: {
    alias: [
      // 源码内部使用的 `@` 别名（与仓库根 vitest.config.ts 一致）
      { find: '@', replacement: path.resolve('apps/web/src') },
      {
        find: '../../apps/web/src/services/courses-store',
        replacement: path.resolve('apps/web/src/services/courses-store.ts'),
      },
      {
        find: '../../apps/web/src/services/course-session',
        replacement: path.resolve('apps/web/src/services/course-session.ts'),
      },
      {
        find: '../../apps/web/src/features/chat/model/store',
        replacement: path.resolve('apps/web/src/features/chat/model/store.ts'),
      },
      {
        find: '../../apps/web/src/services/chat-repository',
        replacement: path.resolve('apps/web/src/services/chat-repository.ts'),
      },
      {
        find: '../../apps/web/src/contracts/chat',
        replacement: path.resolve('apps/web/src/contracts/chat.ts'),
      },
    ],
  },
  test: {
    environment: 'jsdom',
    include: ['docs/qa/CHAT-CONTEXT-BUDGET/probe-reversal/probe.test.ts'],
  },
});
