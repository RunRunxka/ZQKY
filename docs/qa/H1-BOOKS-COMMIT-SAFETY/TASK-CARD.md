# H1-BOOKS-COMMIT-SAFETY v1 任务卡与冻结契约

- 起点候选：`fedfa09`（分支 `main`，开工工作区干净；现场核对 HEAD/分支，未切分支、未合并 `feat/glass-theme`、不推送、不部署）。
- 范围：**只收口书籍本地仓储的提交一致性**（共享集合读改写的互斥/事务与提交结果语义），并逐个迁移调用方。不重做已验收的界面、流水线与其他模块。
- 保留：旧数据兼容（缺 `status` 读取期派生）、损坏/读取被拒不覆盖、R-11 资源目录三态、H1-BOOKS-HARDEN v1 的 M22-01～06 修复、全部显式模拟标注。不清库、不自动删旧数据、不改通用存储设施（`local-collection.ts` 语义不变）影响其他模块。

## 0. 缺陷与复现（先复现再修）

原缺陷探针（已脱敏纳入 Git）：[probe-reversal/original-defect-probe.test.ts](probe-reversal/original-defect-probe.test.ts)。两条断言"缺陷存在"：

1. `writeListConverged` 三次冲突全部跳过写入，最后 `return last` → `createBook` 仍返回书籍对象，调用方进入创建成功流程（幻影保存）。
2. 第二次读标记之后、写标记之前插入另一写入者：对方成功写入并读回后，本次写入仍能用旧整表覆盖它（丢失更新）。

**不依赖"同一毫秒"**：缺陷 2 在可控交错（探针注入点）即可复现。

## 1. 提交结果契约（取代"返回候选值即成功"）

```ts
export type CommitStatus =
  | 'committed'    // 已写入并通过写后读回校验；value 为落库后的真实值
  | 'conflict'     // 未取得写权限/等待预算内未收敛；value 恒为 null，调用方可重试
  | 'missing'      // 目标记录不存在
  | 'skipped'      // 记录存在但本次变更不适用（状态机前置条件不满足 / 重复迟到事件 / 幂等已满足之外的无需改动）
  | 'read-failed'  // 读取被拒/数据损坏：不写入、不覆盖
  | 'write-failed';// 写入失败（配额/回滚）
export interface CommitResult<T = undefined> {
  status: CommitStatus;
  /** 仅 status==='committed' 时非 null，且来自**写后读回**，不是内存候选值 */
  value: T | null;
  /** 统一中文原因文案（UI 直接展示；成功为空串） */
  message: string;
}
```

- 全部写 API 为**异步**：`createBook / updateBook / deleteBook / setUserNote / recordQuizAttempt / markVisited / toggleBookmark / loadDemoBooks / applyRunEvent / ensureBookRun / pauseBookRun / resumeBookRun / failBookRun / finishBookRun / retryBlock / regeneratePage / setRunScenario`。
- **重试耗尽不得返回候选值**：任何非 `committed` 状态的 `value` 均为 `null`。
- 用户输入非法（书名为空/过长）仍以 `BookValidationError` 拒绝（参数校验，不是提交结果）；重名等**前置条件**由提交层返回 `skipped` + 原因。
- 幂等操作（`markVisited` 状态已满足、`loadDemoBooks` 演示书已齐、`ensureBookRun` 已有检查点）返回 `skipped`/`committed` 且**不写盘**（不推进修订号），语义在台账登记。

## 2. 互斥方案（选择理由与如实边界）

**核对现有设施**：`local-collection.ts` 只有"严格读 + 写前校验 + 失败回滚"，没有互斥/事务；`localStorage` 无 CAS；HARDEN v1 的写标记（`*-write`）只是**冲突检测**，检测发生在写入之前，挡不住"检测之后、写入之前"（缺陷 2）。

**选择**（`services/collection-lock.ts`）：

1. **主路径**：浏览器原生 Web Locks（`navigator.locks.request`，`mode:'exclusive'`，按集合键命名）——真正的跨标签页互斥，锁随持有上下文销毁自动释放（无悬挂锁）；等待预算用 `AbortSignal` 超时实现，超时即 `conflict`。
2. **回退路径**（jsdom / 无 Web Locks）：`localStorage` 锁记录 `{owner, nonce, ticket, acquiredAt}` + 取号后读回校验 + 固定 settle 窗口；未通过校验者视为未取得（后写者胜），带退避重试直到等待预算耗尽。
3. **同标签页**：模块级队列串行化所有请求；临界区内的嵌套请求入队延后（不重入、不死锁）。
4. **事务步骤（两路径共用）**：取锁 → 锁内读快照 → 应用变更 → 写修订号 → **校验修订号仍属本事务** → 写数据 → **写后读回校验** → 提交。校验不过则**在最新快照上整事务重做**（≤3 次，收敛），预算耗尽 → `conflict`。
5. **不变量（本批验收口径）**：一旦返回 `committed`，该内容不会被任何**遵守本协议**的写入者用旧快照覆盖。绕过锁的非协议写入者会被"取号后快照校验/写后读回校验"发现并如实报 `conflict`，不静默丢失。
6. **不改动**：集合键名、数据形态、`local-collection.ts` 语义（其他模块存储不受影响）。

## 3. 写入口与调用方（单一协议，无绕过）

- **书籍集合**（`zhiqikeyuan:books`）：创建、编辑、删除、笔记、作答、阅读进度（已读/书签）、生成事件（run-start/page/block/收尾/暂停/失败）、页/块修复、检查点补建、演示载入、执行器场景设置——全部经 `transactCollection`/`transactBookValue`。
- **作答集合**（`zhiqikeyuan:book-quiz-attempts`）：追加经同一事务入口。
- **执行器租约**（`zhiqikeyuan:book-lease:*`）：仍是"带 owner+nonce 归属校验的记录"（HARDEN v1 语义），与集合锁分工：租约保证**单书只有一个执行器**，集合锁保证**整表读改写互斥**；引擎每批事件在锁内重读最新记录，`runWritable` 判定基于锁内快照，旧执行器的迟到写入被 `runId` 校验拒绝。
- **调用方迁移**：落库成功后才关表单/跳转/显示成功；`conflict`/`write-failed`/`read-failed` 保留用户输入与草稿并给可重试入口；无未等待的 Promise（引擎 `flush`/`pause`/`stop`/收尾都等待事务链）。
- 盘点依据（只读审计者产出，含 `文件:行号`）：见 [DEFECT-LEDGER.md](DEFECT-LEDGER.md) §"写入口与调用方盘点"。

## 4. 验收条件

1. 原缺陷探针保留历史用途并归档到本目录；**新增正式回归断言正确行为**（冲突耗尽不假成功、创建输入保留、编辑/删除/笔记/最终完成以真实提交结果为准、可控交错下同书/不同书已保存内容不被旧快照覆盖）。
2. **真实隔离双标签页**浏览器验证：生成与人工编辑并发、持有写锁时的失败与释放后重试、无悬挂锁。
3. 旧数据可读、损坏与读取被拒时数据不被覆盖、R-11 三态与显式模拟标注不回退。
4. `typecheck`/`lint`/`unit`/`build`/相关 e2e；候选冻结后全量前端 e2e 并记录 BUILD_ID；后端零改动则注明 API 测试未重跑。
5. 稳定候选交独立验收者只读复验（不得只复述实现者报告）；模型化交错（单测）与真实浏览器证据分别记录。

## 5. 文件归属与资源

- 队长（唯一写入者）：`services/collection-lock.ts`（新建）、`services/books-store.ts`、`services/book-generation.ts`、`features/books/{BooksRoute,PageReader}.tsx`、相关单测与 `tests/e2e/`、文档与 Git。
- 只读审计者：写入口与调用方盘点（不改文件）。
- 独立验收者：稳定候选只读复验（不改文件）。
- 证据目录：`docs/qa/H1-BOOKS-COMMIT-SAFETY/`；e2e 独占端口 5174；构建目录总控单写；不操作用户浏览器数据与正式 `.env`/`.local-data`。
