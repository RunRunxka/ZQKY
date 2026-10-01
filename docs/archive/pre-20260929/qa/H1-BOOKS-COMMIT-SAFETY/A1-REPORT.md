# H1-BOOKS-COMMIT-SAFETY v1 独立验收报告（A1，只读复验）

> 本文件由实施总控归档，正文为独立验收者（Independent-Acceptor）在候选 **r1** 上的只读复验报告；总控不修改其结论，仅追加"总控处置"。

## 0. 候选、冻结指纹与"实现者已停止写入"

| 项 | 实测 |
| --- | --- |
| 任务版本 | `H1-BOOKS-COMMIT-SAFETY v1`（`TASK-CARD.md` + `FROZEN-CANDIDATE.json` revision **r1**，无 r2、无冻结后产品改动记录） |
| HEAD / 分支 | `fedfa09`（`fedfa09ab9e1f618127f12b48f066b89c7e47181`）/ `main`；本批尚无任何提交，候选 = 工作树改动 |
| 差异散列 | `FROZEN-CANDIDATE.json.fileSha256` **12/12 全部与磁盘一致**；开工、中段（17:09）、收尾三次独立复算，三次均 `ok=12 bad=0` |
| 差异范围 | `git diff --name-status fedfa09` = 15 个 `M`（4 产品源码 + 6 单测 + `next-env.d.ts` + 4 文档）+ 3 个未跟踪项（`collection-lock.ts`、`docs/qa/H1-BOOKS-COMMIT-SAFETY/`、`tests/e2e/books-commit-safety.spec.ts`）；**无 `apps/api`、`教案模板部分`、`assets/`、`*.css`、`.env*`、`.local-data`、构建产物** |
| 停止写入证据 | 产品源码最后 mtime 16:36:42、测试 16:42、文档 17:04；全程 26 分钟只读复验中 12 指纹与 `git status`（18 条）零变化；无遗留 5173/5174 监听进程 |
| 构建号 | `apps/web/.next/BUILD_ID` = **`AtxBYXEc_99FFQ8cGCtvu`**（mtime 16:45:30），**晚于**全部产品源文件 mtime（最晚 16:36:42）→ e2e 跑的确是被冻结源码的产物 |
| 只读性 | 未改任何源码/文档/冻结文件，未提交、未切分支、未 stash、未跑 `npm run build` / `npm run typecheck` |

## 1. 逐项结论表

| # | 复核内容 | 命令 / 证据 | 结论 |
| --- | --- | --- | --- |
| 1a | 12 个 sha256 与磁盘一致（首/中/尾三次） | `node -e` + `crypto` 逐文件比对；`ok=12 bad=0` ×3 | **pass** |
| 1b | diff 范围只含清单文件 + 文档 | `git diff --name-status fedfa09` | **pass** |
| 1c | 无 `apps/api`/`教案模板部分`/`assets`/`*.css`/`.env*`/`.local-data`/构建产物 | 同上 + `git status --porcelain -uall` | **pass** |
| 1d | `apps/web/next-env.d.ts` 已还原（diff 空） | `git diff -- apps/web/next-env.d.ts` → 1 hunk / 2 行（生成式切换，mtime 16:44:19） | **fail**（F2） |
| 1e | `local-collection.ts` 无改动 | `git diff --stat fedfa09 -- …/local-collection.ts` 空 | **pass** |
| 2a | 全量单测 | `NODE_OPTIONS=--no-experimental-webstorage` + `vitest run` → `48 passed (48)` / `389 passed (389)`，EXIT=0，90.6s | **pass** |
| 2b | 重点文件 flaky 复跑 | harden + engine 两文件顺序重跑 3 次 + `--sequence.shuffle` 1 次 → 每次 `43 passed (43)`，退出码 0 | **pass** |
| 2c | "基线 46/353"对照 | 见 F1（实测 `fedfa09` = 48 文件 / 381 例） | **fail**（F1，文档对账） |
| 3a | 原缺陷探针 2/2 失败 | 探针命令 → `2 failed (2)`，逐条原因与归档一致 | **pass** |
| 3b | 探针原件与 `_work/harden-gate-20260922/probe.test.ts` 仅差导入路径 | `diff -u` → 唯一差异为 import 相对路径与一行注释 | **pass** |
| 3c | 探针失败"原因"的记述准确性 | 见 F3（探针 2 首个失败在 `expect(injected).toBe(true)`） | **fail**（文档精度） |
| 4a | 新增 e2e 4 例 | `npx playwright test tests/e2e/books-commit-safety.spec.ts` → `4 passed (26.2s)` | **pass** |
| 4b | 全量前端 e2e（自跑） | `npx playwright test` → `178 passed (6.0m)`、EXIT=0、无 flaky；归档 stats `expected=178, unexpected=0, flaky=0`（未覆盖归档文件） | **pass** |
| 4c | "无悬挂锁"是真断言 | spec 内 `navigator.locks.query()` held/pending=0 + `zhiqikeyuan:books-lock` 为 null | **pass** |
| 5a | 主路径是真 Web Locks（exclusive）、预算由 AbortSignal、超时→conflict | `collection-lock.ts`；并核 W3C `web-locks` §3.2.1「授予后 abort 被忽略」→ 超时不会在临界区中途放锁 | **pass** |
| 5b | 回退路径取号/读回校验/退避/预算耗尽 | `collection-lock.ts`（ticket+settle+三字段读回校验、6→80ms 退避、`>= deadline → conflict`） | **pass** |
| 5c | 同标签页队列、临界区内嵌套请求延后、不重入不死锁 | `collection-lock.ts`；`books-store.ts` 全文件仅 1 处 `await`（取锁本身），mutate 回调全同步 | **pass** |
| 5d | 释放只清自己的锁记录 | `removeLockRecord` owner+nonce 双校验 | **pass** |
| 5e | `transactCollection` 步骤顺序 | 锁内读快照 → mutate → 写修订号 → 快照未变校验 → 写数据 → 修订号仍属本事务 → 数据写后读回 → committed | **pass** |
| 5f | retry 在最新快照上重做 | 校验不过返回 `retry`，外层 ≤3 次重新取锁+重读，耗尽 conflict | **pass** |
| 5g | 是否仍有返回候选值的路径 | 非 committed 全部 `value:null`；`transactBook` 路径 value 的 `updatedAt` 为内存值（F4） | **pass（附 F4）** |
| 5h | 非 committed 的 value 恒为 null | `books-store.ts`；单测逐条断言 | **pass** |
| 5i | 幂等分支不写盘 | `noop` 不写修订号/数据；单测断言 `${KEY}-write` 字节不变 | **pass** |
| 5j | `applyStored` 区分 applied/dropped/failed，失败走 storage 路径 | `book-generation.ts`（committed/skipped→applied、missing→dropped、其余 throw）；`queueFlush` catch → `failTheRun(kind:'storage')` | **pass**（附 F6） |
| 5k | `flushChain` 保证事件顺序 | `state.flushChain.then(run, run)` + `.catch` 兜底，逐条 await | **pass** |
| 5l | `startRun/resumeRun/stopRun/handle.pause\|stop` 等待落库 | 均先 `queueFlush` 再收尾/返回；`pause/resume` 未按提交结果分支（F5） | **pass（附 F5）** |
| 5m | 修复入口：任何块写入前定 runId、复位未提交即失败、写后读回 | `writableRunId` → 复位校验 `committed` → 逐块写后读回（归档/暂停不报 completed） | **pass** |
| 5n | UI 写调用 await + committed 后才提示/跳转/关表单 + 失败保留输入 | `BooksRoute.tsx` / `PageReader.tsx` 各调用点均按 `status` 分支 | **pass** |
| 5o | 无未等待 Promise / 悬空任务 | 引擎为有意的后台任务（`void drive`、`void queueFlush`）；`startRepair` IIFE 残留见 F7/F8 | **pass（附 F7/F8）** |
| 5p | 迁移完整性：无同步调用、无绕过事务直写 | 全仓 grep（含 `tests/`、`scripts/`）；`zhiqikeyuan:books*` 直写点仅修订号/租约/锁记录 | **pass** |
| 5q | useEffect 写是否重复提交 | `markVisited` 幂等 noop；自动续跑仅 `compiling` 且 `getRun`/`autoRunRef` 双闸（罕见双入口见 F8） | **pass（附 F8）** |
| 6a | 48/389、178/0/0、BUILD_ID、探针 2/2、两条路径分别记录 | 全部实测复现 | **pass** |
| 6b | 基线对照数字 | 见 F1 | **fail** |
| 6c | "next-env.d.ts 已还原" | 见 F2 | **fail** |
| 6d | not_run 清单如实 | README §6 列全 | **pass** |
| 7a | `local-collection` 未改、损坏/读取被拒行为仍在 | diff 空 + 其单测 4 例 + harden"损坏数据写入被拒且原字节保留" | **pass** |
| 7b | R-11 三态与显式模拟标注未被波及 | `courses-store.ts` 不在 diff 内；其测试仅 `loadDemoBooks()`→`await` | **pass** |
| 7c | 七态状态机 / 14 类 block / 归档只读 / `paused` 不自动恢复 | `BookStatus`/`BookBlockType` 与 `fedfa09` 字节一致；模拟标注计数只增不减 | **pass** |

## 2. 挑刺（按严重度）

- **F1（中｜文档对账）** 基线单测数字沿用了上一批的"修复前"列（写 `46/353`），而上一批**交付结果**是 `48/381`；实测 `fedfa09` 与本批文件清单逐文件相同 → 正确口径是 `48/381 → 48/389（+8 例、无新文件）`。
- **F2（中｜范围/卫生）** `next-env.d.ts` 未还原（构建/typegen 生成式改写，2 行），文档却称"已还原"；提交前必须 `git checkout --`。
- **F3（低｜文档精度）** 探针 2 的首个失败在 `expect(injected).toBe(true)`（未 `await` 的 `createBook` 返回 Promise → `b.id` undefined → 事务 `missing` → 从未写修订号 → 注入点未命中），不是文档所称的 `peerReadBack`；探针 1 同样在 `stampReads` 断言即失败，未执行到"幻影书籍"断言。
- **F4（低｜契约文本）** `TASK-CARD §1` 称 committed 的 value「来自写后读回」：集合写入路径确实做了数据级写后读回，但 `transactBook` 类路径返回的 value 是内存对象（`updatedAt` 与落库对象不同）；已核消费者无人读 `updatedAt`、无人回写 → 文档精度问题。
- **F5（低｜引擎/UI）** `handle.pause()/resume()` 不检查 `pauseBookRun/resumeBookRun` 的提交结果：持锁时点击暂停会出现"提示已暂停但存储仍 compiling"，可恢复、无假成功、无测试覆盖。
- **F6（低｜死分支）** `if (!applied) continue;` 恒不成立（`applyStored` 返回值非空字符串）；无行为后果。
- **F7（低｜残留风险）** `planPage`/`shouldInjectStorageFailure` 的裸读若在读被拒时抛出，可使修复 Promise 永不 settle（游离 IIFE 无 catch）；触发需极端时序，未观测到。
- **F8（低｜提示噪声）** 自动续跑在 500ms 轮询与 `startRun` 内 `setScenario` 提交叠加下存在罕见双入口；租约自愈，仅可能多一次失权提示。
- **F9（低｜记账）** `frozenAt` 晚于其文件 mtime，属名义时间，建议标注。
- **撤回项**：A1 一度怀疑"等待预算超时会在临界区中途放锁"，核实 W3C 规范后撤回（授予后 abort 被忽略）——该前提正是本批互斥正确性的关键。

## 3. not_run 清单

| 项 | 原因 |
| --- | --- |
| `npm run build` 重跑 | 只读约束禁止（构建目录总控单写）；以 BUILD_ID mtime 晚于全部产品源文件佐证 |
| `npm run typecheck` | 只读约束禁止（`next typegen` 重写生成文件）；以 `npx tsc --noEmit -p apps/web/tsconfig.json` 等效核对：退出码 0 |
| 在 `fedfa09` 上重跑单测以直接测出 381/48 | 需回退工作树（禁止）；改用 `git show fedfa09:<file>` 静态计数 + 归档记录交叉取证 |
| `apps/api` 测试 | 零后端改动，批外 |
| 真实供应商/LLM/解析 | 本批全为本地模拟与本地存储；不适用 |
| 空档期长临界区（>1.5s）的 Web Locks 实测 | 需长事务夹具；改以规范条款论证 |
| 回退锁"两个协议写入者同时入场"的调度停顿构造 | 需 >`settleMs` 停顿注入；生产浏览器走 Web Locks |
| UI 视觉/动画、移动端触摸、跨浏览器进程并发 | 本批无 CSS/动画改动；不宣称任何视觉通过 |

## 4. 剩余风险与边界

1. 回退锁是启发式（无 CAS）：仅在"预检与写入之间出现 >24ms 调度停顿"时才可能双入场；此时数据写后读回会把丢失更新判为 `conflict`（不静默成功）。该路径只在 jsdom/无 Web Locks 环境生效。
2. e2e 的并发是同 context 双标签页（真实 Web Locks + 同一 localStorage 分区），不等价于两个浏览器进程/两个 profile。
3. 锁被占场景由页面持有同名 Web Lock 构造（真实原生锁），而非两个真实事务同时对同一本书读改写；同书/不同书真实并发写由单测（同标签页队列）与 e2e 第 2/3 例共同覆盖。
4. F5–F8 均无测试覆盖且都不产生静默数据丢失，登记为已知边界留待下一批。
5. 真实供应商、移动端、动画精度不在本批证据范围；本批通过不等于书籍模块或全站完成。

## 5. 结论（独立验收者原文）

> **可交付（条件通过）**：CS-01 与 CS-02 的修复在源码级、单测与真实双标签页浏览器三层独立成立；`48/389`、`178/0/0`、`BUILD_ID`、探针 `2/2 失败`、`lint 0 警告`、`tsc --noEmit` 全部实测复现，12 指纹首中尾三次一致。交付前必须处置 F1/F2/F3（+F9 记账）——均不涉及产品/测试文件、12 指纹不变、无需重新冻结；F5–F8 建议登记并留待下一批（改动需重新冻结与复验）。未发现任何"非 committed 却返回候选值"的路径、任何绕过事务直写生产代码、任何 `useEffect` 重复落盘或锁重入死锁；`local-collection`、R-11 三态、七态状态机、14 类 block、`paused` 不自动恢复、归档只读均未回退。

## 总控处置（不修改 A1 结论）

- **F1/F2/F3/F9 已处置**（文档与提交卫生；不改产品/测试文件，指纹不变）：基线与净增数字按实测更正；提交前还原 `next-env.d.ts`；探针失败原因按实测更正（并注明"未执行到"的后继断言）；`frozenAt` 标注为名义冻结时刻。
- **F4**：在台账"语义变化与既有边界"中登记契约措辞口径（value 的 `updatedAt` 可能与落库对象不同；无消费者依赖）。
- **F5–F8 登记为已知边界**（见批次 README §5.1 与台账），理由：修复会触及产品文件，需重新冻结 + 独立复验；四者均不产生静默数据丢失或假成功。
