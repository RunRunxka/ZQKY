# 审查探针在修复后的运行结果（断言反转证据）

- 探针原文：[main 审查证据](../main-review-20260922/README.md)、`docs/qa/main-review-20260922/book-probe.test.ts`（**未修改**，保留原样）。
- 探针断言的**是缺陷存在**（书已删除仍 `running`、读取失败仍持租约、修复返回 `undefined` 且借用新 runId 写入），因此修复后它们**必须失败**。本目录保存修复后的实跑输出：
  - `probe-run-after-fix.txt`：`npx vitest run --config docs/qa/main-review-20260922/book-probe.config.ts`（`NODE_OPTIONS=--no-experimental-webstorage`）。

## 三条探针的失败原因 = 缺陷已不复现

| 探针 | 修复后实际输出 | 说明 |
| --- | --- | --- |
| `deleting a running book leaves a registered runner and renewing lease` | `TypeError: Cannot read properties of null (reading 'heartbeatAt')`（`getLease(book.id)!` 为 `null`） | 删除后**租约已释放**（不再有可续租的租约记录），探针取心跳的语句直接取空 |
| `transient storage read denial ends the loop but retains running state` | `expected undefined to be 'running'` | 读取被拒后**执行器已收尾**（`getRun` 返回 `null`），不再留下"仍在运行"的幽灵任务 |
| `repair returns void and an old task writes under a replacement run ID` | `expected Promise{…} to be undefined` | 修复入口**返回 Promise**（真实异步结果），不再是 fire-and-forget 的 `undefined` |

反转过后的正确行为断言在正式回归里：

- `apps/web/src/services/book-generation.test.ts` → `H1-BOOKS-HARDEN v1 缺陷回归（原探针断言反转）`（含删除收尾、读失败收尾并可恢复、冻结 runId 拒绝迟到写入）；
- `apps/web/src/features/books/BooksRoute.test.tsx`（首次读取失败可见 + 重试）；
- `apps/web/src/features/books/PageReader.test.tsx`（修复结果的 failed/skipped 如实显示、忙态互斥、翻页键排除）。

**边界**：探针输出为 jsdom 隔离运行（临时存储、假时钟/真实定时器按各用例），不是真实浏览器或真实服务验收；修复后的正式回归覆盖真实浏览器场景见 `tests/e2e/books-harden.spec.ts`。
