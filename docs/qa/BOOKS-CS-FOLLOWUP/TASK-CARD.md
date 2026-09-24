# BOOKS-CS-FOLLOWUP v1 任务卡（有界前置补丁）

- 起点候选：`d2638f2`（分支 `main`，开工工作区干净）。
- 范围：只收口 H1-BOOKS-COMMIT-SAFETY v1 独立验收提出的已知问题（A1 报告的 F5–F8 + 两条测试口径）。**不扩大为引擎重构**，不改课程/聊天模块，不动 `local-collection.ts` 语义与既有集合键。
- 依据：[CS 批次 A1 报告](../H1-BOOKS-COMMIT-SAFETY/A1-REPORT.md)（挑刺 F5/F6/F7/F8）、[CS 台账](../H1-BOOKS-COMMIT-SAFETY/DEFECT-LEDGER.md)。
- 文件归属（本补丁单写者）：`services/collection-lock.ts`、`services/books-store.ts`、`services/book-generation.ts`、`features/books/BooksRoute.tsx`、对应单测与 `tests/e2e/books-commit-safety.spec.ts`。契约由队长冻结（本文件），实现者不越界改契约。

## 1. 缺 Web Locks 时不得静默降级（F3/最强项）

- **生产路径只认原生 Web Locks**：`navigator.locks` 不存在时不使用任何"无法保证互斥"的 localStorage 回退（当前回退锁是启发式：取号 + settle + 读回校验，存在双入场窗口）。
- 锁设施改为**可注入 provider**：
  ```ts
  export interface CollectionLockProvider {
    readonly kind: 'web-locks' | 'in-memory' | 'unavailable';
    acquire(lockName: string, waitMs: number): Promise<(() => void) | null>;
  }
  ```
  生产默认 provider = Web Locks；`available=false` 时 `withCollectionLock` 返回 `{ok:false, reason:'unavailable'}`。
- 仓储契约新增提交状态 **`'unsupported'`**：`message` 明确说明"当前浏览器不支持写入所需的互斥（Web Locks），本次修改未保存；界面内容保留，可在支持的浏览器重试"。**读取与草稿不受影响**（读取路径不取锁）。
- **测试替身经测试注入**：`__setCollectionLockProviderForTests(provider)`；jsdom 单测注入 in-process 互斥（同一 JS 环境内真实互斥），**不保留 localStorage 回退作为生产路径**。回退锁代码从生产路径移除（可整体删除）；相关 settle/wait 参数钩子一并清理。
- 回归：provider=unavailable → 写返回 `unsupported` 且存储未变、读取正常；provider=in-memory → 既有提交一致性回归全部成立；**注入失败必须不可静默忽略**（`__setCollectionLockProviderForTests` 返回是否生效，失效时测试应失败而不是放行）。

## 2. 控制操作按 CommitResult 分支（F5）

- `BookRunHandle.pause(): Promise<{ paused: boolean; message?: string }>`；`resume(): Promise<{ resumed: boolean; message?: string }>`。
- `pause()`：`await queueFlush` → `const result = await pauseBookRun(...)`；**只有 `committed` 才 `teardownRun('paused')` 并报成功**；否则执行器保持运行（不改成 paused 状态、不释放租约），返回 `{paused:false, message}`。
- `resume()`：沿用既有 `resumeBookRun` 结果校验，不重写恢复逻辑；未提交时返回 `{resumed:false, message}`。
- UI（`BooksRoute.handlePause/handleResume/handleRetryRun`）：按结果分支——失败时 `setNotice('暂停未保存：…')`（或对应文案），**不显示"已暂停"**，忙态照常退出，用户可重试；成功路径行为不变。
- 回归（单测 + e2e）：
  - 单测：占住锁 → `handle.pause()` → `{paused:false}`、`getRun` 仍在、存储状态仍 `compiling`；释放锁 → 再 pause → `{paused:true}`、状态 `paused`。
  - e2e：另一标签页持写锁 → 点「暂停生成」→ 出现失败提示且未显示"已暂停" → 释放锁 → 再点 → 暂停成功 → **刷新后仍为 paused**。

## 3. 修复任务全生命周期异常收尾（F7）

- `startRepair` 内部异步任务必须**整体 try/catch/finally**：任何抛出（含 `planPage`/复位后的计划读取被拒）都以 `finish('failed'|'cancelled', 原因)` 收尾。
- 不变量（每个返回的 Promise 都必须 settle）：`repairs` 注册项在 settle 时删除；同页后续请求不会复用永不 settle 的 Promise；`PageReader` 的忙态随 Promise settle 退出。
- 保持取消、取代、`runId` 隔离与迟到写入保护（既有语义与断言不得放宽）。
- 回归：**"复位成功后计划读取失败"**确定性用例——复位提交成功后让 `planPage` 的读取抛错（受控注入）→ 断言 Promise 在限定时间内 settle 为 `failed`、注册项已清、再次点击同页可发起新操作。

## 4. 测试口径订正与新增（F4 对应的测试面）

- 现有"双标签页并发写不同书"用例名与断言订正：它实际是**同一本书的两页**，改名为"同一本书不同页并发写"。
- 新增**真正不同 bookId、不同内容**的双标签页并发用例：一边写书 A 的笔记、另一边写书 B 的笔记（可借助生成中的书），断言**双方内容都存在于存储**、无覆盖、结束后无悬挂锁。

## 5. F6/F8 有界收口

- 删除 `queueFlush` 里恒不成立的 `if (!applied) continue;` 死分支（`applyStored` 返回 `'applied'|'dropped'|'failed'`），改为显式处理：`dropped` 计入丢弃（不写、不报失败），`failed` 抛出交由 `failTheRun`。
- F8 启动重入：核对 `startRun` 在 `await setRunScenario` 之后才 `registry.set` 造成的窗口；**用启动中占位去重**（在第一个 await 之前登记占位状态；第二次调用返回既有句柄或 null，不启动第二个执行器）。补一条确定性回归（并发两次 `startRun` → 只有一个执行器、只写一次租约）。
- 不做引擎重构；不加新注入场景（除本任务卡要求的测试注入）。

## 6. 文档订正

- 订正 CS 批次 README/台账中的保证范围：**不得声称"写后读回必然发现所有绕过协议的写入"**——写后校验能发现"在写入窗口内改表"的常见情形，但等价于同时写入的亚毫秒窗口无法证明被覆盖；口径改为"发现即如实报 conflict，不静默成功；不宣称强原子性"。
- 原始 A1 报告保持原样，处置记录由队长追加。

## 7. 验收条件

1. `npm run typecheck`、`npm run lint`（0 警告）、`npm run test:unit`（全绿，含新增回归）、`npm run build`。
2. `tests/e2e/books-commit-safety.spec.ts` 全绿（含新增/订正用例），并在集成后参与全量 e2e。
3. 单测若因移除回退锁而变更设置（settle 相关钩子），必须说明"settle 不再存在"的理由，而不是放宽断言。
4. 结果卡：起点/候选、改动文件与指纹、每条 A1 挑刺的处置、首败与修复证据、实际测试与 not_run、剩余边界。**本补丁单独提交、单独给独立验收结论。**
