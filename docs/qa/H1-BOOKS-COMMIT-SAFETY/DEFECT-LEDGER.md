# H1-BOOKS-COMMIT-SAFETY v1 首败、修复与证据台账

起点候选：`fedfa09`（`main`）。缺陷来源：`_work/harden-gate-20260922/probe.test.ts`（复现已归档为 [probe-reversal/original-defect-probe.test.ts](probe-reversal/original-defect-probe.test.ts)）。

| ID | 缺陷（已复现） | 首败证据 | 修复 | 正式回归（断言正确行为） |
| --- | --- | --- | --- | --- |
| CS-01 | `writeListConverged` 三次冲突全部跳过写入后 `return last`：内存候选值被当成保存结果，`createBook` 返回幻影书籍、调用方进入成功流程 | 探针 1（`stampReads=6 / dataWrites=0`，`createBook` 仍返回带 id 的书籍，存储里没有它） | 事务化提交结果：`CommitResult`（`committed/conflict/missing/skipped/read-failed/write-failed`）；**任何非 committed 的 value 恒为 null**；冲突预算耗尽返回 `conflict`（调用方保留输入、可重试） | `books-store.harden.test.ts`「冲突预算耗尽 → conflict 且 value 为 null，存储未变、重试可成功」；`books-commit-safety.spec.ts`「另一标签页持有写锁：创建如实失败并保留输入，释放后重试成功」（真实浏览器 + 真实 Web Lock） |
| CS-02 | 写标记只能"写前检测"：另一写入者在"检测之后、写入之前"提交，会被旧整表覆盖（丢失更新） | 探针 2（注入时机在第二次读标记与写标记之间；对方写入并读回成功，随后其内容被覆盖为旧值） | **集合写锁**（`services/collection-lock.ts`）：生产路径用原生 Web Locks 互斥、jsdom 用 localStorage 取号+settle+读回校验；锁内完成"读快照→变更→写修订号→写数据→写后校验"，校验不过整事务在最新快照上重做 | `books-store.harden.test.ts`「快照读取后、写入前有非协议写入者改了别的书 → 事务重做，两边内容都在」「同一本书两次并发写被串行化，两次修改都保留」「不同书并发写各自落地」；`books-commit-safety.spec.ts`「双标签页并发写不同书」「生成与人工编辑并发」 |

## 探针在修复后的表现（如实记录）

见 [probe-reversal/probe-run-after-fix.txt](probe-reversal/probe-run-after-fix.txt)：两条探针**按预期失败**，失败原因即"缺陷假设不再成立"：

- 探针 1：首个失败在 `expect(stampReads).toBe(6)`（收到 0）——写标记协议已被事务取代，不再有 6 次标记读取；其后的"幻影书籍"断言未执行到（`createBook` 现在返回 `CommitResult`，形状上也不可能再返回幻影书籍）。
- 探针 2：首个失败在 `expect(injected).toBe(true)`（收到 false）——探针未 `await` 的 `createBook` 现在返回 Promise（`b.id` 为 undefined），事务判定 `missing`、从未写修订号，探针的注入点因此未命中；其后的 `peerReadBack` 断言未执行到。（先前文档写"失败于 `peerReadBack`"有误，此处按实测更正。）

**探针失败本身不作为修复证明**：正确行为由上面的正式回归与真实双标签页 e2e 断言。

## 写入口与调用方盘点（只读审计者产出，节选结论）

- 生产代码**没有绕过点**：全仓唯一 `writeStrictList(KEY, …)` 调用在 `books-store.ts` 的 `writeListConverged` 内（本批改为事务内）；`PageReader.tsx` 只有一处对 `zhiqikeyuan:books` 的**只读** `getItem`（书签真值兜底），不参与写入。
- 需迁移的调用方：`BooksRoute.tsx`（载入演示/删除/创建/确认提案/确认大纲/重建/暂停/恢复/重试 共 6 处写 + 3 处引擎入口）、`PageReader.tsx`（已读登记/书签/笔记/作答 4 处）、`book-generation.ts`（`applyStored` 落库闸门、`failTheRun`、`handleRunReadDenied`、`startRun` 场景持久化、`pause/resume/stop`、修复入口与复位回调）——全部已迁移为"等待事务结果"。
- 审计者点出的高危项与处置：
  1. `applyStored` 曾丢弃 `applyRunEvent` 的返回值 → 现在按 `applied/dropped/failed` 区分，失败走 storage 失败路径。
  2. `ensureBookRun(...) ?? book` 曾吞掉失败 → 现在 `writableRunId` 等待事务结果，未提交即 `skipped` 收尾（不再"按接近 runId 继续写"）。
  3. 修复复位的返回值曾丢失 → 现在检查 `committed`，未提交时不进入逐块写入。
  4. `recordQuizAttempt/markVisited/toggleBookmark` 曾无结果可判 → 现在返回带状态的提交结果，界面据此如实提示（作答未保存、阅读进度未保存）。
- 只读消费者未改语义：`readBooks/getBookPage(s)/readQuizAttempts/latestQuizAttempt/readingPercent/exportBookMarkdown/subscribeBooks`，以及课程 R-11 资源目录三态快照（`courses-store.ts` 只读 + 订阅）。

## 语义变化与既有边界（接手者必读）

1. **写 API 全部异步**：调用方必须 `await` 提交结果；界面只在 `committed` 后关表单/跳转/显示成功。
2. **幂等操作不写盘**：`markVisited`（状态已满足）、`loadDemoBooks`（演示书已齐）、`ensureBookRun`（已有检查点）返回 `skipped`/`committed` 但**不推进修订号**（测试断言修订号不变）。
3. **前置条件失败是提交层结果**：重名、状态机不允许、重复/迟到事件、非 `user_note` 块都不再"返回原值假装成功"，而是 `skipped`/`missing` + 原因文案。
4. **`storageFailureOnFinish` 注入保持不变**（最终完成写入失败 → `kind storage` 失败 + 「重试生成」不假完成）；本批把"最终完成写入失败"的判定从"抛错"扩展到"事务未提交"。
5. **可恢复性**：`conflict` 不改变任何数据；UI 保留输入并可重试；重试在同一表单/同一条目上完成。
6. **不宣称强原子性（Web Locks 之外的路径）**：jsdom 回退锁是"取号 + settle + 读回校验 + 写后校验"的启发式互斥，不是硬件级事务；生产浏览器走原生 Web Locks。真实"同一毫秒并发"由写后校验兜底（发现即 `conflict`，不静默丢失）。
7. **F4（A1 低危，登记口径）**：`transactBook` 类路径返回的 `value` 是内存对象，其 `updatedAt` 可能与落库对象不同（集合写入路径有数据级写后读回）；已核所有消费者只读 `status`/`id`/`run.runId`，无人读 `updatedAt`、无人回写，故为契约措辞精度问题，非数据缺陷。
8. **修约窗口内不改动**：`local-collection.ts`、集合键名与数据形态、R-11 三态、14 类 block、七态状态机、`paused` 不自动恢复、归档只读、旧数据（缺 status 按 ready 派生）全部保持。
