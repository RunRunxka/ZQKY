# H1-BOOKS-COMMIT-SAFETY v1 批次证据（书籍保存一致性收口）

- 起点候选：`fedfa09`（分支 `main`，开工工作区干净；现场核对 HEAD/分支，未切分支、未合并、未推送、未部署）。
- 本批提交：见文末"提交与暂存范围"（本地小提交）。
- 冻结契约与范围：[TASK-CARD.md](TASK-CARD.md)。
- 首败、修复与写入口盘点：[DEFECT-LEDGER.md](DEFECT-LEDGER.md)。
- 原缺陷探针（脱敏）与修复后运行输出：[probe-reversal/](probe-reversal/README.md)。
- 冻结指纹与构建号：[FROZEN-CANDIDATE.json](FROZEN-CANDIDATE.json)。
- 独立验收：`A1-REPORT.md`（只读独立验收者产出，逐项 pass/fail/not_run；自检不计入）。

## 1. 本批做了什么（一句话）

把书籍本地仓储的写入从"写前检测 + 有界重放"改成**集合互斥锁内的事务读改写**，并引入显式的**提交结果契约**：创建/编辑/删除/笔记/作答/阅读进度/生成事件/页块修复/检查点/演示载入/场景设置全部走同一协议，非 `committed` 一律不返回候选值，调用方只在真正落库后才关表单、跳转或提示成功，冲突时保留用户输入并可重试。

**真实服务边界：全部仍为本地模拟执行器与本地存储，不接真实 LLM/解析；本批通过不代表真实供应商能力或全站完成。**

## 2. 验证结果（本批实跑）

| 维度 | 命令 | 结果 |
| --- | --- | --- |
| 类型 | `npm run typecheck` | 通过（`next typegen && tsc --noEmit`，无错误） |
| 静态检查 | `npm run lint`（`--max-warnings=0`） | 通过，0 警告 |
| 单元测试 | `NODE_OPTIONS=--no-experimental-webstorage npm run test:unit` | **48 文件 / 389 例通过**（上一批交付基线 48 / 381，本批净增 8 例、无新增文件） |
| 构建 | `npm run build`（总控自跑） | 通过，`BUILD_ID = AtxBYXEc_99FFQ8cGCtvu` |
| 浏览器回归（新增） | `npx playwright test tests/e2e/books-commit-safety.spec.ts` | **4 例通过**（真实双标签页 + 原生 Web Locks） |
| 浏览器回归（全量） | `npx playwright test` | **178 例通过 / 0 失败 / 0 flaky**（既有 174 + 新增 4；`stats.expected=178, unexpected=0`） |
| 原缺陷探针 | `npx vitest run --config docs/qa/H1-BOOKS-COMMIT-SAFETY/probe-reversal/probe.config.ts` | 2/2 **按预期失败**（缺陷假设不再成立），输出见 [probe-reversal](probe-reversal/probe-run-after-fix.txt) |
| 后端 | 未运行 | `apps/api` 零改动，API 测试未重跑（沿用本轮基线 181） |

## 3. 关键实现

1. **`services/collection-lock.ts`（新建）**：集合写锁。生产路径 = 原生 Web Locks（`navigator.locks`，exclusive，锁随上下文销毁释放，无悬挂锁；等待预算由 `AbortSignal` 控制）；**本批 jsdom 路径曾用 `localStorage` 回退锁（`{owner,nonce,ticket,acquiredAt}` + 取号 settle + 读回校验），该路径已在 BOOKS-CS-FOLLOWUP v1 整体删除**：无原生 Web Locks 即 `unavailable`（`unsupported`，不降级写），jsdom 单测改经 `__setCollectionLockProviderForTests` 注入 in-process 互斥；同标签页请求经模块级队列串行，临界区内嵌套请求入队延后（不重入、不死锁）。
2. **`services/books-store.ts`**：`CommitResult`/`CommitStatus` 契约与 `transactCollection` 事务核心——锁内读快照 → 应用变更 → 写修订号 → **校验修订号仍属本事务** → 写数据 → **写后读回校验**；校验不过则在最新快照上整事务重做（≤3 次，收敛），预算耗尽返回 `conflict`。全部写函数改为异步返回 `CommitResult`；幂等操作（已读状态已满足、演示书已齐、已有检查点）不写盘。
3. **`services/book-generation.ts`**：落库闸门 `applyStored` 返回 `applied/dropped/failed` 并等待事务；`flush` 串到 `state.flushChain` 保证顺序；`startRun`/`resumeRun`/`stopRun`/`handle.pause|stop` 改为等待"状态与事件真正落库"；修复入口同步返回 Promise（保持"同目标复用同一 Promise"），运行身份异步填充但**在任何块写入前完成**；复位写入校验 `committed` 后才进入逐块补生成。
4. **UI 迁移**：`BooksRoute`（载入演示/删除/创建/确认提案/确认大纲/重建/暂停/恢复/重试）与 `PageReader`（已读登记/书签/笔记/作答）全部按提交结果决定提示与跳转；失败保留输入/草稿并给出可重试入口；新增"阅读进度未保存""作答未保存"两条如实提示。

## 4. 测试与基线变化

单测：上一批（H1-BOOKS-HARDEN v1）交付基线 `48 文件 / 381 例` → 本批 **48 文件 / 389 例**（净增 8 例，无新增文件；全部来自 `books-store.harden.test.ts` 由 5 例扩为 13 例）。要点：

- `services/books-store.harden.test.ts` 重写为**提交一致性回归**（13 例）：冲突耗尽不假成功并可重试、锁被占时编辑/删除/笔记不写、`missing`/`skipped` 区分、读取被拒/写入失败不覆盖、`committed` 值来自写后读回、**可控交错下对方已保存内容不被旧快照覆盖**、同书/不同书并发写、幂等不写盘、锁卫生（无残留锁记录）、旧数据与损坏保护。
- `services/book-generation.test.ts`：迁移为异步并保留全部 30 例（含 HARDEN v1 的探针反转回归与新增"修复期间归档不报 completed"）。
- `features/books/PageReader.test.tsx`（25 例）、`BooksRoute.test.tsx`（2 例）、`services/courses-store.test.ts`（10 例）按异步提交语义迁移；组件测试新增"等待提交结果"的断言方式（不再假设同步落库）。

E2E：既有 174 例 + 新增 `tests/e2e/books-commit-safety.spec.ts` **4 例**（真实双标签页）：① 另一标签页持有写锁时创建如实失败并保留输入、释放后重试成功；② 双标签页并发写不同书两边内容都保留且**无悬挂锁**（`navigator.locks.query()` 无 held/pending、localStorage 无锁记录）；③ 生成与人工编辑并发（另一标签页写笔记，生成完成后笔记仍在且书籍达到可阅读）；④ 持锁时删除不假成功、释放后可删除。

**测试路径说明**：真实浏览器走原生 Web Locks（e2e 证据）；jsdom 单测走**测试注入的 in-process 互斥**（`__setCollectionLockProviderForTests(createInMemoryCollectionLockProvider())`，单测证据）。本批当时的“jsdom 回退锁 + 缩短 settle 窗口”路径已在 BOOKS-CS-FOLLOWUP v1 整体删除（无互斥即 `unsupported`），见该批 README §2.1 与本文 §5.2 处置记录。两条路径的证据分别记录，不互相冒充。

## 5. 设计选择与如实边界

- **为什么不是"再多重试/再加一次读回"**：原缺陷 2 的窗口在"检测之后、写入之前"，任何写前检测都挡不住；必须让写入本身进入互斥临界区。本批因此引入锁 + 事务，而不是加参数。
- **不宣称强原子性**：生产路径为原生 Web Locks；单测路径为测试注入的 in-process 互斥（本批当时的 `localStorage` 回退锁已在 BOOKS-CS-FOLLOWUP v1 删除）。写后读回校验能发现窗口内常见的并发改写并如实报 `conflict`（不静默丢失），但**不得声称“写后读回必然发现所有绕过协议的写入”**——绕过本协议、恰落在“校验之后、写入之前”的写入不在保证范围内。该口径按 BOOKS-CS-FOLLOWUP v1 任务卡 §6 就地订正，处置记录见 §5.2。
- **接口异步化**：全部写 API 改为 `Promise<CommitResult<…>>`，调用方逐个迁移；参数校验（空名/超长）仍以 `BookValidationError` 拒绝，前置条件（重名、状态机不允许、重复迟到事件）为 `skipped`。
- **不改动**：集合键名与数据形态、`local-collection.ts` 语义（其他模块存储不受影响）、R-11 三态、14 类 block、七态状态机、`paused` 不自动恢复、归档只读、旧数据（缺 status 按 ready 派生）、显式模拟标注。

## 5.1 独立验收 A1 处置（r1 条件通过）

A1 判 **可交付（条件通过）**：CS-01/CS-02 的修复在源码级、单测与真实双标签页浏览器三层独立成立；`48/389`、`178/0/0`、`BUILD_ID`、探针 `2/2 失败`、`lint 0 警告`、`tsc --noEmit` 均由其本机复现，12 指纹首/中/尾三次一致。全文见 [A1-REPORT.md](A1-REPORT.md)。

- **交付前已处置（不触及产品/测试文件，12 指纹不变）**：F1 更正单测基线为"上一批 48/381 → 本批 48/389（+8 例、无新文件）"；F2 提交前还原 `apps/web/next-env.d.ts`（构建生成文件）；F3 更正探针 2 的具名失败原因（首个失败在 `expect(injected).toBe(true)`，而非 `peerReadBack`）；F9 `frozenAt` 标注为名义冻结时刻。

- **登记为已知边界、留待下一批（改动会触及产品文件，需重新冻结与复验）**：
  1. **F5（低，无数据风险）**：`handle.pause()/resume()` 不检查 `pauseBookRun/resumeBookRun` 的提交结果（`book-generation.ts` 对应行）——持锁时点击暂停会出现"提示已暂停但存储仍为 compiling"，可恢复、无假成功；建议按提交结果分支并如实提示。
  2. **F6（低，死分支）**：`book-generation.ts` 中 `if (!applied) continue;` 恒不成立（`applyStored` 返回 `applied/dropped/failed` 非空字符串）；无行为后果，属误导性分支，建议删除。
  3. **F7（低，残留风险）**：`planPage`/`shouldInjectStorageFailure` 的裸读若在读被拒时抛出，可使修复 Promise 永不 settle（游离 IIFE 无 catch）；触发需"读被拒恰好落在两次读之间"，未观测到；建议收口为受控读。
  4. **F8（低，提示噪声）**：自动续跑在 500ms 轮询与 `startRun` 内 `setRunScenario` 提交叠加下存在罕见双入口；租约 nonce 会自愈，仅可能多一次"已失去或无法确认所有权"提示；建议给自动续跑加一次性闸。
- A1 另核对并**撤回**一条候选挑刺：W3C Web Locks 规范下"授予后 abort 被忽略"，因此等待预算不会在临界区中途放锁——该前提正是本批互斥正确性的关键。

### 5.2 BOOKS-CS-FOLLOWUP v1 之后的处置记录（r2，2026-09-22）

前置补丁 BOOKS-CS-FOLLOWUP v1 整体删除了本批的 `localStorage` 回退锁，并新增 `unsupported` 提交状态；据此，本文件原先描述回退锁的三处（§3 第 1 条、§3「测试路径说明」、§5「不宣称强原子性」）与 `DEFECT-LEDGER.md`「语义变化」第 6 条已**就地加注现状口径**（原始表述保留在 git 历史中可查：本批交付提交 `b8136dd`；处置不改写原始测试数字与结论）。同时按 FOLLOWUP v1 任务卡 §6 明确：**不得声称“写后读回必然发现所有绕过协议的写入”**——写后校验的保证范围只覆盖落在校验窗口内的并发改写，旁路写入不在保证内。本订正只涉及文档，不触及产品与测试文件，本批候选指纹与全部测试证据不变。

## 6. 边界与未执行项

- 未运行：`apps/api` 测试（零后端改动）、真实供应商/真实 LLM、移动端硬件触摸、逐帧动画曲线（属 H6）。
- 未接入：RAG（宿主接入准备核对清单见 `docs/PROJECT_GUIDE.md` §4.2；`F:\ZQKY_RAG` 保持只读，其 P8A 已修复但**仍无可恢复版本交付物**，人工质量 not_run）。
- 不包含：课程学习会话、BookChatPanel、主题重做、`feat/glass-theme` 合并、推送/部署。
- 视觉/动画：本批未改任何样式或动画（无视觉验收需求）；矩阵中不升级视觉/动画标签。

## 7. 提交与暂存范围（本地）

| 提交 | 内容 | 说明 |
| --- | --- | --- |
| 产品与测试提交 | `services/collection-lock.ts`（新建）、`books-store.ts`、`book-generation.ts`、`BooksRoute.tsx`、`PageReader.tsx`、4 个单测、`tests/e2e/books-commit-safety.spec.ts`（新建） | 提交前逐项检查暂存范围：无 `apps/api`、无 `教案模板部分`、无 `assets/`、无 `*.css`、无 `.env*`/`.local-data`、无构建产物与密钥；`next-env.d.ts` 已还原为仓库版本、不随批提交 |
| 文档提交 | `docs/STATUS.md`、`docs/PROJECT_GUIDE.md`、三矩阵、`docs/qa/H1-BOOKS-COMMIT-SAFETY/**` | 文档提交不触及产品文件，冻结指纹与 BUILD_ID 保持不变 |

未执行（用户未授权）：推送远程、部署、切换或合并 `feat/glass-theme`、改动全局 Git 身份。
