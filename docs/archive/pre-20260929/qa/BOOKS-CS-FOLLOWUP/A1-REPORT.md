# BOOKS-CS-FOLLOWUP v1 独立验收报告（A1，只读复验）

> 归档说明（队长）：本文件由独立验收者 A1（`Independent-Acceptor`，只读、不修复）在候选 `a45b011` 上产出，原样归档；文末「总控处置」为队长对其中 W1/W2 的关闭记录，不改写 A1 的原始结论与数字。证据日志（A1 本机 `/tmp/a1-books-cs-followup/`）不随仓库提交。

> 本报告由独立验收者（A1）在候选 `a45b011` 上只读复验；证据日志保存在 `C:\Users\96022\AppData\Local\Temp\a1-books-cs-followup\`（Git Bash：`/tmp/a1-books-cs-followup/`）。未修改任何仓库文件、未提交/切分支/stash、未跑 `npm run build` 与 `npm run typecheck`。**本报告不宣称 UI 视觉/动画通过**（e2e 是真实浏览器功能证据，不是视觉验收），也不宣称任何真实供应商通过（本批全部为本地模拟执行器与本地存储）。

## 0. 候选、指纹与“实现者已停止写入”

| 项 | 实测 |
| --- | --- |
| 任务版本 | BOOKS-CS-FOLLOWUP v1（契约 `docs/qa/BOOKS-CS-FOLLOWUP/TASK-CARD.md`，本批为提交型候选，无 FROZEN 记录） |
| HEAD / 分支 | `a45b0116be1a143bfc9c7efb9d3b836fa5f7e575` / `main`；父提交 `d2638f27e2970dc60218ec9e9aed8f517bf6e437` |
| 差异范围 | `git show --stat a45b011` → 14 文件，+1204/−330；**无** `apps/api`、`features/courses/**`、`features/chat/**`、`services/chat-*.ts`、`contracts/**`、`*.css`、`.env*`、`.local-data`、构建产物；`local-collection.ts` 不在清单；`apps/next-env.d.ts` 不在提交 |
| 差异散列 | tree `d1db11b3ed364707714ee4613e21a380e55028c3`；`d2638f2..a45b011` diff 散列 `d84fb7af29c73b8f489fbff8a37ed226db5dc820` |
| 逐文件 sha256（前 16 位，取自 `git show a45b011:<file>`，全部与工作树一致） | BooksRoute.test.tsx `6be4b885b7f04260`、BooksRoute.tsx `bd575c4d40f41e09`、PageReader.test.tsx `d530a67f28b66fbf`、book-generation.test.ts `b5222a76addca568`、book-generation.ts `d669b7a74817940c`、books-store.harden.test.ts `424e852f4b144f67`、books-store.test.ts `829c10c96c243a71`、books-store.ts `9c773d76b701c7a1`、collection-lock.test.ts `58f634961a6c0483`、collection-lock.ts `f3e8740974ffa843`、courses-store.test.ts `5ee52d8bbc005918`、README.md `7d8ec94a19b9ffa6`、TASK-CARD.md `57f5b3352a173773`、books-commit-safety.spec.ts `5bc106ed248c8d11` |
| 构建 | `BUILD_ID = YhmHpWDKx-EgSf1pGHkZh`（mtime `2026-09-22 18:27:35.998`），**晚于候选全部产品源文件**（最晚 `book-generation.ts` 18:24:34）；构建产物内含候选专属字符串（`当前浏览器不支持写入所需的互斥` 命中 `books-store` SSR chunk 与静态 chunk；`长时间被其他标签页占用` 命中 `BooksRoute`/引擎 chunk）→ e2e 跑的是本候选的产物；我的全部测试运行期间 BUILD_ID 与 `.next` 文件 mtime（最晚 18:27:36.92）零变化 |
| 停止写入 | **候选 14 文件在全程只读复验中未被任何写入者触碰**（首/中/尾三次 `git diff HEAD -- <14 文件>` 均为空、逐文件哈希一致）。**但工作区已不静止**：复验期间另一批次（H1-COURSE-SESSIONS）开始写入 `contracts/chat.ts`、`features/chat/**`、`features/courses/**`、`services/course-session*.ts`、`apps/api/tests/test_chat_stream_api.py`、`docs/PROJECT_GUIDE.md`、`docs/replica/*`、`tests/e2e/course-sessions.spec.ts`（18:35–18:45）。这些文件与候选范围零交集，故本报告结论对候选仍成立；受影响的只有“repo 级 lint”一项（见 7a） |

## 1. 逐项结论表

| # | 复核内容 | 命令 / 关键证据 | 结论 |
| --- | --- | --- | --- |
| 1a | diff 只含 books 源码/测试 + `docs/qa/BOOKS-CS-FOLLOWUP/**` | `git show --stat a45b011`（14 文件清单见上） | **pass** |
| 1b | 无 `apps/api`/`features/courses/**`/`features/chat/**`/`services/chat-*.ts`/`contracts/**`/`*.css`/`.env*`/`.local-data`/构建产物 | 同上；`git status --porcelain -- <14 文件>` 为空 | **pass** |
| 1c | `local-collection.ts` 无改动；`next-env.d.ts` 不在提交 | diff 清单 + `git diff --stat HEAD -- apps/web/next-env.d.ts` 空 | **pass** |
| 2a | 生产 provider 只认 `navigator.locks`；无它即 `unavailable` | `collection-lock.ts:54-106`（`webLocksProvider.kind` getter；`acquireWebLock` 无 locks 即 `Promise.resolve(null)`） | **pass** |
| 2b | `withCollectionLock` 在 `unavailable` 时**不进临界区** | `collection-lock.ts:210-214` 直接返回 `{ok:false,reason:'unavailable'}`（`enqueue` 未调用）；单测断言 `ran===false` 且 `localStorage.length===0` | **pass** |
| 2c | `books-store` 新增 `unsupported` 且所有写经事务入口 | `books-store.ts:301-348`（状态+文案）、`386-466`（唯一事务入口）；`locked.reason==='unavailable' → failed('unsupported')` | **pass** |
| 2d | 读取/草稿路径不取锁 | `readBooks/getBookPage(s)/readQuizAttempts/latestQuizAttempt/readingPercent/exportBookMarkdown` 只用 `readStrictList`，全文件 `withCollectionLock` 仅 1 处（事务内） | **pass** |
| 2e | localStorage 回退锁**删干净** | `grep -n 'localstorage\|sessionstorage\|settle\|stale\|ticket' collection-lock.ts` → 仅注释里“已整体删除”；旧版 `peekCollectionLock`/`__setCollectionLockOptionsForTests`/`CollectionLockOptions` 全仓零引用 | **pass** |
| 2f | 注入钩子“未生效可见” | `collection-lock.ts:159-175`（返回 boolean + `__getCollectionLockProviderKindForTests`）；各 `beforeEach` 以 `expect(...).toBe(true)` + kind 断言守卫 | **pass** |
| 2g | **无 Web Locks 时是否仍有写盘路径** | 集合写全部经 `transactCollection`（grep 全仓 `writeStrictList` 调用点仅 books/courses/notebook/space-store，books 键唯一写在事务内）。**唯一可达的非集合写**：`book-generation.ts:292-301` 租约键 `zhiqikeyuan:book-lease:<bookId>`（写后读回、`teardownRun` 清理）与会话级 owner/tab 标识；**不存在写书籍数据的路径** | **pass**（附 W3） |
| 3a | `pause()` 返回结果对象；只有 `committed` 才 `teardownRun('paused')` | `book-generation.ts:1277-1303`；未提交分支提前 return，不 teardown | **pass** |
| 3b | 未提交时执行器/租约/状态保持 | 单测 F5 用例：`getRun≠null`、`handle.status==='running'`、存储仍 `compiling`、`pauseKind` 未写、`getLease≠null` | **pass** |
| 3c | UI 失败文案且不显示“已暂停” | `BooksRoute.tsx:679-690`（`暂停未保存：…`）；e2e 用例 4：`getByText(/暂停未保存：/)` 可见、`getByText('生成已暂停')` count=0、释放后再点 → `.book-pipeline-paused` 可见、刷新后仍 paused | **pass** |
| 3d | `resumeRun` 既有校验未被无谓重写 | `git show d2638f2:…/book-generation.ts` 的 `resumeRun` 与候选逐字节相同（本批只改了 `stopRun` 的 `flushBestEffort` 一行） | **pass** |
| 4a | `queueFlush` 四类结果分派，死分支已删 | `book-generation.ts:479-503`（applied/dropped/conflict/failed 显式处理）；父提交的 `if (!applied) continue;` 消失 | **pass** |
| 4b | `startRepair` 全生命周期收尾 | `1621-1656` 整体 try/catch/finally + `finish` 幂等（`settled` 门闩、注册项在 settle 时删除）+ `earlyRepair`（计划读取失败→`failed`，`1662-1681`） | **pass** |
| 4c | 取消/取代/runId 冻结/迟到写入未放宽 | `runRepair` 与父提交 **逐字节 IDENTICAL**（diff 仅移动调用位置）；3 条 M22-02 用例（复用/取代/late-write）全绿 | **pass** |
| 4d | `startRun` 启动中占位（第一个 await 之前登记） | `900-917`：`startingRuns.set` 在 `await pending` 之前同步执行；F8 单测：`h2===h1`、`leaseWrites===1`、单执行器 | **pass** |
| 5a | 冲突 → 事件回队首 + 300ms + 整体重试；预算 20s | `461-529`（`state.pending = [...batch.slice(index), ...state.pending]`；`FLUSH_CONFLICT_RETRY_DELAY_MS=300`、`FLUSH_CONFLICT_BUDGET_MS=20000`） | **pass** |
| 5b | 预算耗尽按 storage 如实终止、不假报完成 | 单测“持锁耗尽预算”（36.4s）：`startRun→null`、`getRunExit().reason==='failed'`、message 匹配 `/写入冲突\|另一个标签页写入/`、`getRun/getLease` 为 null、存储仍 `compiling`、释放后恢复跑完 | **pass** |
| 5c | 控制/停止有界最尽力（1s） | `flushBestEffort`（1266-1268）用于 `pause`(1282)、`stop`(1329)、`stopRun`(1370) | **pass** |
| 5d | 集成决策是否真解决“锁被占期间跑到收尾然后终止” | 见 §2 独立判断：机制成立（单测 1“1.2s 短暂持锁整轮照常完成” + e2e 用例 4） | **pass** |
| 6a | 全量单测 | `NODE_OPTIONS=--no-experimental-webstorage npm run test:unit` → **49 files / 403 tests passed**，EXIT=0，82.10s；逐文件计数之和=403 且收集到的 49 个测试文件与候选树一一对应（无并行批次文件混入） | **pass** |
| 6b | 重点 3 文件顺序重跑 ×3 | 每次 `3 passed (3)` / `57 passed (57)`，EXIT=0 → 无 flaky | **pass** |
| 6c | e2e（两文件） | `npx playwright test tests/e2e/books-commit-safety.spec.ts tests/e2e/books-pipeline.spec.ts` → **20 passed (3.1m)**，EXIT=0（6 + 14，逐条 ok） | **pass** |
| 6d | e2e（第三文件，核对 26 例） | `npx playwright test tests/e2e/books-courses.spec.ts` → **6 passed (23.6s)**，EXIT=0；三文件合计 **26**，与 README 分项数字一致 | **pass** |
| 6e | 端口/进程/构建卫生 | e2e 后 `netstat` 5174 无 LISTENING；BUILD_ID 未变；`.next` 无测试期间新文件 | **pass** |
| 7a | README“lint 0 警告” | `npm run lint` → **EXIT=1**，唯一问题：`apps/web/src/services/course-session.test.ts:12:27 'readCourses' is defined but never used`（**另一批次 18:39 新建、不在 a45b011**）。同一次输出对候选 14 文件 0 问题 → 候选范围无错误/警告；repo 级声明因并行写入**无法复现** | **pass（候选范围）／not_run（repo 级）** |
| 7b | README 单测 49/403 | 实测一致 | **pass** |
| 7c | README 构建号/记录 | 表格写 `kuKTXV4Pi5WG0pN37WJCr`，实际 `YhmHpWDKx-EgSf1pGHkZh`；§4 指向的“FROZEN 记录”不存在；§7.4 要求的“候选/指纹”未落盘 | **fail（W2）** |
| 7d | “写后校验不宣称必然发现所有绕过协议的写入” | 本批 README §5 已写明（不得声称必然发现） | **pass** |
| 7e | 任务卡 §6“订正 CS 批次 README/台账保证范围” | a45b011 不含任何 CS 文档改动；CS 文档在 HEAD 仍以现在时描述已删除的回退锁 | **fail（W1）** |
| 7f | 未执行项如实标注 | README §3/§5 列全（全量 e2e、真实进程并发、视觉/动画） | **pass** |
| 8a | 抽查 UI/引擎无“未提交却成功/跳转/收尾为已暂停” | `createBook`(429)/`confirmProposal`(852)/`confirmSpine`(1061)/`rebuildBook`(1192)/`deleteBook`(363)/`loadDemoBooks`(203)/`toggleBookmark`/`setUserNote`/作答 全部 `status==='committed'` 分支后才提示/跳转/关表单；引擎 `finishBookRun` 非 committed → `failTheRun`；`pause` 已按提交分支 | **pass** |
| 8b | `unsupported` 不被折叠成成功或自动重试 | grep：`unsupported` 仅出现在 books-store 定义/映射与测试；`applyStored` 对 `unsupported` **抛错**走 storage 失败（不是静默跳过）；UI 透出仓储 `message`（含 Web Locks 字样） | **pass**（附 W3/W4） |

## 2. 集成决策复核（独立判断，对应 §1.5）

**结论：该改动确实解决了“锁被占期间执行器跑到收尾然后终止”，且未引入活锁/堆积/阻塞/错序。** 理由：

1. `await queueFlush` 现在语义上等于“等到真正落库或 20s 预算耗尽”。驱动循环在 `stepOnce` 的每个页/块里程碑都 `await queueFlush`，因此另一个标签页持锁时驱动**不会**继续推进页/块、更不会跑到收尾；父实现是“首个冲突即抛错 → `failTheRun(storage)`”，必然出现“跑一段后以存储失败终止”。单测 1（真实 in-process 互斥持有 1.2s）整轮照常跑完、退出原因 `finished`；e2e 用例 4 证明“持锁→暂停失败→释放→暂停成功→刷新仍 paused”在真实 Web Locks 下成立。
2. **无活锁**：重试有 300ms 间隔、每次冲突判定预算、预算耗尽抛错；`guard>200` 安全阀在预算之前不可达。
3. **无 pending 堆积**：驱动被 flush 阻塞，`emit` 不再增加队列；`flushChain` 保证同一执行器事件串行、顺序不变量成立（冲突时把剩余事件放回**队首**，等待期间新事件排在其后）。
4. **停止流程不被阻塞**：`pause/stop/stopRun` 的写盘等待上界 1s（其后各自按提交结果分支/保留断点）；控制写入本身受仓储 3 次取锁尝试约束，最坏仍是有限时间。
5. **失败不假成功**：预算耗尽按 `kind storage` 收尾并点名“写入冲突/另一个标签页”；若失败原因也写不进存储，书籍停在 `compiling`（界面“已中断 + 继续生成”），单测逐条断言。
6. 我另行枚举的新问题检查（详见 W5/W7）：无阻断性新问题；发现一个“暂停成功后仍可能有批内迟到事件落库”的外观窗口（非丢数据、非假成功，见 W7）与一个既有裸读微窗口（见 W5）。

## 3. 挑刺（按严重度；均不影响产品数据正确性）

- **W1（中｜交付物未完成＋文档对账）** 任务卡 §6 要求“订正 CS 批次 README/台账中的保证范围”，但 `a45b011` **不含任何 `docs/qa/H1-BOOKS-COMMIT-SAFETY/**` 改动**，而本批 README 第 52 行却称“口径已在文档中订正”。同时 CS 文档在 HEAD 上仍以现在时描述已删除的回退锁，与本批 README §2.1“回退锁整体删除”直接矛盾：`docs/qa/H1-BOOKS-COMMIT-SAFETY/README.md:47`（“jsdom 单测走 localStorage 回退锁（单测证据）”）、`:52`（“不宣称强原子性：回退锁是启发式的”）、`:32`（§3.1 回退路径）、`DEFECT-LEDGER.md:37`（§语义变化 6 同）。
  - 最小复现：`git show --stat a45b011 | grep -c 'H1-BOOKS-COMMIT-SAFETY'` → 0；`grep -n '回退锁' docs/qa/H1-BOOKS-COMMIT-SAFETY/README.md` → 32/47/52 行仍在；`grep -rn 'localStorage' apps/web/src/services/collection-lock.ts` → 仅注释。
  - 影响：交接/复验者会误以为单测跑的是已删除的回退锁；“不宣称强原子性”边界文本挂在不存在的组件上。**产品代码零影响。**
  - 建议（队长安排，纯文档、不触产品/测试文件、无需重新冻结或重跑）：CS README §3.1/§4/§5、DEFECT-LEDGER §6 改为“生产只认原生 Web Locks，jsdom 经 `__setCollectionLockProviderForTests` 注入 in-process 互斥；无互斥即 `unsupported`（不降级写）”，并加一行指向本批处置。
- **W2（低｜记账/结果卡）** README `:34` 记 `BUILD_ID = kuKTXV4Pi5WG0pN37WJCr`，实际候选构建为 **`YhmHpWDKx-EgSf1pGHkZh`**（`:46` 自己把后者列为“有界最尽力写盘后”的最新迭代）；`:46` 指向的“最终候选见 FROZEN 记录”在 `docs/qa/BOOKS-CS-FOLLOWUP/` 下**不存在**（只有 README/TASK-CARD）；任务卡 §7.4 要求的“候选/指纹”未落盘（无 `a45b011` 提交号、无任何文件哈希）。
  - 最小复现：`cat apps/web/.next/BUILD_ID`；`ls docs/qa/BOOKS-CS-FOLLOWUP/`。
  - 影响：复验者必须自建指纹；“e2e 跑的就是本候选产物”无法自证。建议归档本报告时一并写入候选/ tree/ diff 散列与上表哈希。
- **W3（低｜边界文档精度）** README §5 称“无原生 Web Locks 的浏览器上书籍**写**功能不可用（读取/草稿/导出不受影响）”——集合数据确实一个字都写不进（已核）。但补充实测细节：无互斥时仍会写**非集合**键——`runStart→acquireLease` 的租约记录（写入后读回、收尾清理）与会话级 owner/tab 标识；并且当打开一本 `compiling` 书时，自动续跑 effect（500ms tick，`BooksRoute.tsx:535-554`）在 `startRun` 返回 null 后**不会**写入 `autoRunRef`，于是每 500ms 重试一次（每次写+删一次租约、起停一次心跳），界面无假成功提示。建议在边界里补一句。
- **W4（低｜文案精度）** 永久性不可用场景的提示被泛化：`BooksRoute.tsx:707/725`（恢复/重试）在 `resumeRun` 返回 null 时统一说“…或本地存储暂不可写（**可稍后重试**）”，而仓储的精确原因（`unsupported` 含“当前浏览器不支持…Web Locks”）在该路径被丢弃；`PageReader.tsx:719` 笔记失败也是固定文案（同文件的 `toggleBookmark` 路径则透出了 `result.message`）。不构成假成功，但会引导用户在无 Web Locks 浏览器上反复重试。
- **W5（低｜既有裸读微窗口，非本批引入）** `book-generation.ts:475` 的 `shouldInjectStorageFailure(state)` 在 try 之外裸读（`596-606` 调 `readBooks()`）；若恰在此处读被拒/数据损坏，`queueFlush` 返回的 Promise 会 reject，而 `emit(immediate=true)` 的 `void queueFlush`、`pagehideHandler`、`void drive(state)` 都不收尾执行器（未处理拒绝 + 状态残留）。触发需“`scenario.storageFailureAt` 生效 + 存储读恰在 `freshBook` 与 guard 之间被拒”，且位置与父提交一致（非本批回归）。建议下一批把该 guard 读收口为受控读。
- **W6（信息｜既有重复声明）** `books-store.ts:365` 与 `:469` 重复声明内容完全相同的 `BookMutateOutcome`（父提交已存在，declaration merging 无行为影响），建议顺手清理。
- **W7（低｜外观一致性窗口）** `queueFlush` 的批内 `for` 循环只看 `while(!state.cancelled …)`、批内不再检查 `cancelled`，且 `runWritable` 允许 `paused`（`books-store.ts:1035-1043`，与父提交逐字节相同）。因此 `pause()` 成功（`flushBestEffort` 1s 上限）时，若该 flush 正在写一个已取出的 batch，**批内剩余事件仍可能在暂停提交之后落库**，使“书已 paused、某页却被迟到 `block-ready/block-start` 改回 generating/planning”。不丢内容（恢复时该页重新 plan，`user_note` 内容由仓储保留），书状态字段不被事件改写（e2e“刷新后仍 paused”成立），但“已暂停”的页面快照可能短暂显示某页生成中。与父实现相比该窗口更宽（父 `pause` 会等完整 `queueFlush`），但父实现同样存在“驱动在 flush 与 pauseBookRun 之间 emit”的窗口，属既有语义而非新缺陷。建议下一批在批内循环加 `if (state.cancelled) return;`。

## 4. not_run 清单

| 项 | 原因 |
| --- | --- |
| `npm run typecheck` | 只读约束禁止（`next typegen` 会改写生成文件）；以 `npx tsc --noEmit -p apps/web/tsconfig.json` **EXIT=0** 等效核对 |
| `npm run build` 重跑 | 只读约束禁止（构建目录总控单写）；以 BUILD_ID/mtime/构建产物字符串指纹佐证 |
| repo 级 `npm run lint` 0 警告 | 并行批次新文件污染（见 7a）；候选范围 0 问题已见到输出 |
| 全量前端 e2e（178 例） | 只跑 books 三个文件（26 例）；全量与课程批集成后由队长跑 |
| `apps/api` 测试 | 候选零后端改动（本批未触碰 `apps/api`） |
| 真实供应商/LLM/解析 | 本批全为本地模拟执行器与本地存储；无凭证，不适用 |
| 真实两浏览器进程/两 profile 并发 | e2e 为同 context 双标签页；“锁被占”由页面持真实原生 Web Lock 构造 |
| 无 Web Locks 的真实浏览器手测 | 以单测 `provider='unavailable'` 注入代替；未在真实旧浏览器跑 |
| 无 Web Locks 下自动续跑周期重试的浏览器实测（W3） | 仅源码走查 + 时序推演 |
| UI 视觉/动画/移动端硬件触摸 | 本批无样式改动；本报告不宣称视觉通过 |

## 5. 剩余风险（交付后仍存在）

1. 暂停/停止后仍可能有批内迟到事件落库（W7）：只影响页面状态外观，不丢内容、不假成功；刷新/恢复自洽。
2. 锁被长时间占用（>20s 连续冲突）时整轮按 storage 失败终止；失败原因可能也写不进存储 → 书停在 `compiling`（界面“已中断 + 继续生成”，可恢复），需用户理解“生成中断”而非“完成”。
3. 无 Web Locks 环境下写功能不可用，且打开生成中的书会产生 500ms 周期的静默重试（W3）。
4. `queueFlush` guard 裸读微窗口（W5）与 `BookMutateOutcome` 重复声明（W6）为既有技术债。
5. 交接文档仍需订正（W1/W2），否则后续读者对“单测跑的是哪条锁路径”和“哪个构建号对应本候选”会得出错误结论。

## 6. 结论

> **代码与测试层面：可交付（独立复验通过）。** F3（缺 Web Locks 不降级：生产只认原生锁、无它即 `unsupported`、回退锁删净、无集合写盘路径、注入生效可见）、F5（控制操作按提交结果分支，未提交不收尾/不释放租约，UI 不显示假暂停）、F6（四类结果分派、死分支已删）、F7（修复任务全生命周期收尾、任何抛出都 settle、注册项清理、既有取消/取代/runId 冻结语义逐字节未放宽）、F8（启动中占位去重、租约只写一次）五项均在源码、单测（49 文件/403 例，重点文件 3×57 无 flaky）、真实浏览器 e2e（26 例：6+14+6）三层独立成立；集成决策（冲突预算重试+背压、控制操作 1s 有界最尽力）经独立判断确为有效修复，未引入活锁/堆积/停止阻塞/顺序错乱；抽查未发现任何“未提交却提示成功/跳转/收尾为已暂停”的路径，`unsupported` 未被折叠成成功或静默重试。
>
> **交付卡口（需队长安排，仅文档，不触及产品/测试文件，不需重新冻结或重跑测试）：** W1 补做任务卡 §6 的 CS 批次文档订正（并消除与本批事实矛盾的回退锁描述）；W2 订正本批 README 的构建号为 `YhmHpWDKx-EgSf1pGHkZh`、删掉不存在的“FROZEN 记录”引用、补候选提交号与指纹。若把任务卡 §6/§7.4 视为硬验收项，则本批当前状态为**需修订（仅文档）**；代码指纹与全部测试证据无需重来。
>
> **范围声明：** 本报告不宣称 UI 视觉/动画通过、不宣称真实供应商通过、不宣称后端通过；`apps/api` 与真实服务均 not_run。

## 7. 总控处置（队长，2026-09-22）

| 卡口 | 处置 | 证据 |
| --- | --- | --- |
| W1 CS 批次文档保证范围订正 | **已关闭（仅文档）**：`docs/qa/H1-BOOKS-COMMIT-SAFETY/README.md` §3 第 1 条、「测试路径说明」、§5 共 3 处就地加注现状口径，并新增 §5.2 处置记录；`docs/qa/H1-BOOKS-COMMIT-SAFETY/DEFECT-LEDGER.md`「语义变化」第 6 条同步订正。原始表述保留在 git 历史（本批交付提交 `b8136dd`）中，原始测试数字与结论未改写；同时明确「写后读回不必然发现所有绕过协议的写入」 | 上述两文件；`git log --oneline -1 b8136dd` |
| W2 候选/指纹与构建号 | **已关闭（仅文档）**：`docs/qa/BOOKS-CS-FOLLOWUP/README.md` 构建号更正为 `YhmHpWDKx-EgSf1pGHkZh`，删去不存在的「FROZEN 记录」引用，新增 §3.1 候选与指纹（提交 `a45b011`、tree `d1db11b3…`、diff `d84fb7af…`、14 文件 sha256）与 §4.1 卡口关闭记录 | `docs/qa/BOOKS-CS-FOLLOWUP/README.md` §3.1/§4.1 |
| W3/W4/W5/W6/W7（挑刺，非交付卡口） | **登记，不在本批修**：均为既有语义或非阻断性技术债（W3 边界文档精度、W4 文案泛化、W5 既有裸读微窗口、W6 重复类型声明、W7 暂停后批内迟到事件的外观窗口）。已在 §5 剩余风险与本批 README §5 保留，留给后续批次（H1-BOOKS-* 下一批）按优先级处理，**不扩大本批范围** | 本文件 §3/§5 |

**处置后结论：BOOKS-CS-FOLLOWUP v1 的代码与测试证据不变（候选 `a45b011`，49 文件/403 例单测 + 26 例书籍 e2e），两项文档卡口已在同批交付内关闭；该补丁独立验收通过（限定范围：本地模拟执行器与本地存储；真实供应商/后端/视觉 not_run）。**
