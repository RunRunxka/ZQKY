# H1-BOOKS-HARDEN v1 独立验收报告（A1，只读复验）

> 本文件由实施总控归档，正文为独立验收者（Independent-Acceptor）在候选 **r1** 上的只读复验报告原文；总控不修改其结论，仅在文末追加"总控处置"与 r2 复验记录。

## r1（首个冻结候选）复验 — 2026-09-22

### 0. 候选与指纹

| 项 | 实测 |
| --- | --- |
| HEAD | `40491be86f366cb13bd424d365506200ac5e8527`（分支 `main`，复验前后一致） |
| 候选形态 | 本批为工作树未提交改动；复验前后 `git status --porcelain --untracked-files=all` 完全一致（20 条），HEAD 未变 |
| 实现者停止写入 | 确认。全部产品文件 mtime ≤ `2026-09-22 13:33:50`（源码最晚 `13:24:17`），声明冻结时间 `13:50:00`；全程未观察到任何写入 |
| 12 文件 sha256 | **12/12 MATCH**（`sha256sum` 与 `node crypto` 两次独立核对，复验开始与结束各一次，结果相同） |
| BUILD_ID | 磁盘 `apps/web/.next/BUILD_ID` = `pqzZk9dNwqAvuoc0KGNIH`，与 FROZEN-CANDIDATE.json 一致，复验期间未被改写（mtime 仍 `13:25:55`） |
| 构建内含本批代码 | `grep -rl "已失去本书的生成所有权" apps/web/.next/` 命中 `.next/static/chunks/0i_es068amrvs.js` 等；`"最终完成状态写入失败"` 同样命中；两者在 `40491be` 的源码中计数为 0（确为本批新增），证明 e2e 跑的不是旧产物 |

改动范围（`git diff --name-only 40491be` + `git ls-files --others`，23 条路径逐条分类）：

- 允许域：4 个产品源码/测试、`docs/STATUS.md`、`docs/replica/{AI_INTERACTIONS,MOTION_MATRIX,PAGE_MATRIX}.md`、`docs/qa/H1-BOOKS-HARDEN/**`、`tests/e2e/books-harden.spec.ts`、2 个新单测。
- 禁止域：`apps/api`、`教案模板部分`、`assets/`、`.env*`、`.local-data`、任何 `*.css`/主题改动 —— **命中数 0**。
- **唯一超出清单的路径**：`apps/web/next-env.d.ts`（`M`，`next typegen`/`next build` 的生成式副产物，非产品改动），总控裁定不随本批提交（见挑刺 6）。

### 1. 逐项结论表

| 编号 | 复核内容 | 命令 / 证据 | 结果 |
| --- | --- | --- | --- |
| 1 | 指纹一致（12 文件） | `node -e`（crypto 比对 FROZEN-CANDIDATE.fileSha256）→ `ALL 12 HASHES STILL MATCH`（复验首尾各一次） | **pass** |
| 2 | 改动范围与禁止域 | `git diff --stat 40491be`（11 files, +1489/-250）+ 脚本化分类（23 条路径）→ 禁止域 0 命中 | **pass**（1 条生成文件备注） |
| 3 | 全量单测 | `NODE_OPTIONS=--no-experimental-webstorage npm run test:unit` → exit 0，`Test Files 48 passed (48)` / `Tests 379 passed (379)`，39.67s | **pass** |
| 4 | 单测 flaky 观察 | vitest 3.2.4 **无 `--repeat-each`**（`--help` 仅 `--retry`），改用 3 次顺序重跑 + 2 次 `--sequence.shuffle`（seed 101/202）→ 每次 `2 passed / 33 passed`、exit 0 | **pass**（未观察到 flaky） |
| 5 | 审查探针反转 | `NODE_OPTIONS=--no-experimental-webstorage npx vitest run --config docs/qa/main-review-20260922/book-probe.config.ts` → exit 1，`Tests 3 failed (3)`；失败原因逐条与文档一致：`Cannot read properties of null (reading 'heartbeatAt')`、`expected undefined to be 'running'`、`expected Promise{…} to be undefined` | **pass** |
| 6 | 探针未被削弱 | `git diff --stat 40491be -- docs/qa/main-review-20260922/` → 空；探针仍显式断言"缺陷存在" | **pass** |
| 7 | 新增 e2e | `npx playwright test tests/e2e/books-harden.spec.ts` → exit 0，`6 passed (47.8s)` | **pass** |
| 8 | 新增 e2e 稳定性 | 同文件 `--repeat-each=2` → exit 0，`12 passed (1.5m)` | **pass** |
| 9 | 全量 e2e（独立复现） | `npx playwright test` → **exit 0，`174 passed (5.4m)`，0 failed / 0 flaky** | **pass** |
| 10 | `_work` 归档未被覆盖 | mtime 仍为 `13:37:12` / `13:41:02`（早于其运行） | **pass** |
| 11 | 174 总数独立核对 | `npx playwright test --list` → `Total: 174 tests in 24 files`；`books-harden=6`、`books-pipeline=14` | **pass** |
| 12 | lint 0 警告 | `npm run lint` → exit 0，无任何 warning/error | **pass** |
| 13 | typecheck | 未运行（禁跑：`next typegen` 会重写生成文件） | **not_run** |
| 14 | build | 未运行（禁跑：构建目录总控单写）；旁证 BUILD_ID 与产物字符串 | **not_run** |
| 15 | 统一收尾唯一路径 | `registry.delete`/`stopTimers`/`clearOwnLease` 仅出现在 `teardownRun` 内（`:159-178`） | **pass** |
| 16 | `readBookForRun` 三态与分支 | `:193-203` 返回 `ok/missing/denied`；`freshBook :913-934` 分别收尾为 deleted / read-denied / stopped | **pass** |
| 17 | 修复入口 Promise + 冻结 runId | `RepairResult :1204-1218`；`startRepair :1335` 冻结；`runRepair :1465` 每步比对；无位置重取"当前 runId" | **pass** |
| 18 | 互斥 / 取代 / 取消 | `coversTargets :1245-1247` + `startRepair :1349-1356` + `cancelRepairs`，由 teardown/stopRun 调用 | **pass** |
| 19 | 租约写后读回 / 每步与心跳校验 / 只清自有 | `acquireLease :282-290`、`ownsLease` 每步与心跳、`clearOwnLease :304-315` 仅 owner+nonce+runId 匹配才清 | **pass** |
| 20 | books-store 写路径收敛 | `writeStrictList` 全仓仅 `books-store.ts:303`（在 `writeListConverged` 内）调用；全部写入路径经收敛路径 | **pass** |
| 21 | 键值形态未被改动 | `KEY`/`QUIZ_KEY`/`ReplicaBook` 未变；新增仅为 sidecar 键与 sessionStorage 身份键 + 可选 `storageFailureOnFinish` 与租约 `nonce` | **pass** |
| 22 | `shouldIgnorePageKey` | `PageReader.tsx:111-126` 覆盖 defaultPrevented/isComposing/修饰键/input/textarea/select/isContentEditable/closest('[contenteditable]') | **pass** |
| 23 | BooksRoute 渲染顺序 + 删除顺序 | 错误面板先于不存在先于加载态；`refresh` 成功清 error；删除先 `stopRun(id,'delete')` 再 `deleteBook(id)` | **pass** |
| 24 | M22-05 不假成功 | `run-finished` 事件不置 ready（只有 `finishBookRun :1107` 能置）；最终写失败 → `failTheRun(kind storage)`；一次性语义经单测断言 | **pass** |
| 25 | `getRunExit` 提示可达 | `BooksRoute.tsx:543-553` 对 read-denied/lease-lost 提示；e2e 真实浏览器断言可见 | **pass** |
| 26 | 诚实性对账（聚合数字） | 48/379 ✓、46 文件基数 ✓、353 基线 ✓（原审查独立测得 + 期间仅 docs 变更）、174/0 ✓、BUILD_ID ✓、探针 3/3 ✓；"不宣称强原子性"四处如实；"双标签页=接管失权而非同毫秒竞争"写明 | **pass** |
| 27 | 诚实性对账（分文件数字） | README:47「PageReader.test.tsx 两组共 **7** 条」、LEDGER:19「2 条 + **5** 条」与实际不符：实测 `-t "全局翻页键的输入排除"` → 2 passed、`-t "修复入口的真实异步结果"` → **6 passed**，应为 2+6 | **fail（仅文档计数）** |
| 28 | 诚实性对账（证据归属） | STATUS:68 把「`replacement-run` 下无块变 ready」归给"原探针断言反转"；探针 3 在 `:62` 即失败终止，从未执行到 `:69`；该结论实际由新单测 `book-generation.test.ts:634-663` 支撑 | **fail（仅归因）** |
| 29 | 假成功/未实现功能排查 | 逐 `catch`（16 处）与 `return null/false`（43 处）核对：无"读失败折叠成 null 后静默成功"残留；发现 2 处边缘假成功候选（见挑刺 1/2） | **pass（附挑刺）** |

**r1 批次结论：核心 6 项修复与全部聚合数字经独立复验成立；无阻断性失败。**

### 2. 独立挑刺（按严重度排序）

1. **`writeListConverged` 重放耗尽后仍返回"成功"（中）** — `books-store.ts:308 return last;`；`mutateBook :322`、`createBook :640-645`、`updateBook :779`、`deleteBook :748`、`setUserNote :420` 都不校验最终读回。
2. **`runRepair` 每步只校验 runId，不校验书籍可写性（中）** — `book-generation.ts:1465`；`applyStored` 无法感知 `applyRunEvent` 内部 `runWritable` 拒绝。最小复现：点「强制重新生成」→ 在 `blockDelay` 窗口内归档该书 → 页复位为 pending、其余写入被静默丢弃，但操作以 `completed` 结束并把块计入 `writtenBlockIds`。
3. **`readLease` 把读异常折叠成"失权"（低）** — `:258-260`，`ownsLease` 判假后向用户宣称"另一个标签页取得租约"，真实原因可能是存储读取瞬时被拒。
4. **`startRun` 可返回已同步失败的句柄，配出矛盾文案（低）** — `:858-860` 与 `BooksRoute.tsx:522-525`：可能出现绿色"已从断点继续"与红色"生成失败"并存。
5. **"溢出 0"与断言口径不符（低）** — README:55 / STATUS:138 写"溢出 0"，`tests/e2e/books-harden.spec.ts:101` 断言的是 `toBeLessThanOrEqual(1)`。
6. **`apps/web/next-env.d.ts` 属生成式改动，提交前需显式决策（低）**。
7. **README §5 称"新增界面只有两处"（低）** — 实际三处（含模拟设置复选项），复用既有形态，仅计数表述不精确。

### 3. not_run 清单与原因

| 项 | 原因 |
| --- | --- |
| `npm run typecheck` | 禁跑（`next typegen` 重写生成文件）；"typecheck 通过"未由其复现，沿用实施者记录 |
| `npm run build` | 禁跑（构建目录总控单写）；旁证 BUILD_ID 与 `.next` 产物含本批新增字符串 |
| `apps/api` 测试 | 零后端改动，批外；"基线 181"来自审查记录，未重跑 |
| 真实供应商 / 真实 LLM / 真实解析 | 本批全为本地模拟执行器与本地注入 |
| 单测基线 353 例的直接复跑 | 复跑需检出 `40491be`（会改动工作区）；改用三条独立旁证对账 |
| 真实浏览器 IME `isComposing` / 修饰键 | 无法稳定构造；批次已声明为组件层覆盖 |
| 运行中读取被拒 → `getRunExit('read-denied')` 的界面提示 | 有源码路径与单测断言，但 e2e 未构造该场景 |
| "同一毫秒并发写共享键" | `localStorage` 无 CAS，无法确定性构造 |

### 4. 剩余风险与边界

- 报告的 pass 只覆盖该冻结指纹（12 文件 sha256 + 磁盘 BUILD_ID）；复验结束时四项（哈希、BUILD_ID、`git status`、HEAD）均与开始一致。
- 不得由本报告推断 UI 视觉通过：本批未做视觉验收，PAGE_MATRIX 亦明确不升级视觉/动画标签。
- 测试绿 ≠ 真实供应商通过；M22-03 用"第二标签页接管"作确定性证据（非同时竞争），共享集合用"模型化并发注入"（非真实第二浏览器进程）。
- 挑刺 1/2 属"假成功"同族风险且无测试覆盖，建议队长决定补进后续批次或登记为已知边界。
- 文档对账 2 条 fail 不影响交付，修正成本极低。

---

## 总控处置（2026-09-22，不修改 A1 结论）

- **挑刺 2 已修（产品）**：`runRepair` 逐块写后读回校验；书籍在修复期间变为不可写时以 `failed` 结束、该块不计入 `writtenBlockIds`。新增回归 `book-generation.test.ts`「修复期间书籍变为不可写（归档）→ 不得报 completed」。
- **挑刺 1 部分已修（产品）**：`setUserNote` 改为写后读回校验后再返回 `true/false`（不再以回调副作用当已保存）；新增回归 `books-store.harden.test.ts`「笔记写入始终无法落地时返回 false」。`writeListConverged` 重放耗尽的返回值行为**未改**（避免在极端并发窗口抛未捕获异常），已登记为已知边界（台账 §"语义变化的已知边界"第 9 条）。
- **挑刺 3 已修（产品）**：失权提示改为「已失去或无法确认本书的生成所有权」（读取被拒与接管不再混淆）；e2e 断言同步更新。
- **挑刺 4 已修（产品）**：`BooksRoute` 自动续跑仅在句柄 `status !== 'failed'` 时提示"已从断点继续"，不再与失败横幅矛盾。
- **挑刺 5 / 7 已修（文档）**：窄视口改为"横向滚动差 ≤1px"；新增界面计为三处（含模拟设置复选项）。
- **挑刺 6 已裁定**：`apps/web/next-env.d.ts` 为构建生成文件，本批**不提交**（提交前已还原为仓库版本）。
- **A1 对账 27 / 28 已修（文档）**：PageReader 用例计数改为 2+6；STATUS 中「`replacement-run` 下无块变 ready」的归属改为**新增单测**（探针第三条在返回类型断言处即失败终止，不会执行到该断言）。
- 因上述产品文件改动，r1 冻结失效，重新冻结为 **r2**（见 [FROZEN-CANDIDATE.json](FROZEN-CANDIDATE.json)），并按批次规则在 r2 上重跑 typecheck/lint/unit/build/全量 e2e 与 A1 定向复验。

## r2（采纳 A1 挑刺后的修订候选）定向复验

## r2 复验记录（独立验收 A1，只读定向复验 — 2026-09-22）

### 候选与指纹

| 项 | 实测 |
| --- | --- |
| HEAD / 分支 | `40491be86f366cb13bd424d365506200ac5e8527` / `main`（复验首尾一致） |
| 候选形态 | 工作树未提交改动，20 条路径；复验期间路径集合未变 |
| 冻结指纹 | `FROZEN-CANDIDATE.json`（revision r2）12 文件 sha256 与磁盘 **12/12 MATCH**（复验开始与结束各校一次） |
| BUILD_ID | `.next/BUILD_ID` = `cTTq7b-No7rnD-HNmoyQc`，与冻结值一致，复验期间未被改写（mtime 仍 14:06:04） |
| 相对 r1 的差异面 | 与 r1 实测哈希比对：**改动 6 个 / 逐字节相同 6 个**，与任务描述完全吻合 |
| BUILD 是否含 r2 代码 | 生产 chunk 命中 r2 独有字符串 `已失去或无法确认`、`写入未生效`；依赖新文案的 e2e 断言通过 → 排除跑在旧产物上 |
| 写入静止性 | 6 个改动文件 mtime 停在 `14:01:16–14:05:37`，复验全程未变；HEAD、指纹、BUILD_ID、路径集合无漂移 |

改动（相对 r1）：`book-generation.ts`、`books-store.ts`、`BooksRoute.tsx`、`book-generation.test.ts`、`books-store.harden.test.ts`、`books-harden.spec.ts`。与 r1 逐字节相同：`PageReader.tsx`、`PageReader.test.tsx`、`BooksRoute.test.tsx`、`books-store.test.ts`、`BookGenerationStrip.test.tsx`、`books-pipeline.spec.ts`。

### 逐项结果表

| 编号 | 复核内容 | 命令 / 证据 | 结果 |
| --- | --- | --- | --- |
| 1 | r2 冻结指纹 12/12 | `node -e`（crypto 比对 FROZEN-CANDIDATE.fileSha256）→ 首尾两次 `12/12 MATCH` | **pass** |
| 2 | r1 未变文件确实未变 | 同脚本比对 r1 哈希 → `changed vs r1 (6)` / `identical to r1 (6)`，清单与任务描述逐项一致 | **pass** |
| 3 | 改动范围不含禁止域 | 20 条路径脚本化分类 → `forbidden hits: NONE`；`git diff --stat 40491be -- apps/api` 空、`-- '*.css'` 空 | **pass** |
| 4 | 全量单测 48 / 381 | `npm run test:unit`（带 `--no-experimental-webstorage`）→ exit 0，`48 passed (48)` / `381 passed (381)`（40.42s），无 `×` | **pass** |
| 5 | 新增 e2e 6 例 | `npx playwright test tests/e2e/books-harden.spec.ts` → exit 0，`6 passed (46.3s)` | **pass** |
| 6 | 全量 e2e 174 / 0（自跑） | `npx playwright test` → **exit 0，`174 passed (5.4m)`**，0 failed / 0 flaky；归档文件 mtime 未被覆盖，归档 stats（`expected=174, skipped=0, unexpected=0, flaky=0, duration=324963ms`）与其运行一致 | **pass** |
| 7 | 审查探针 3/3 按预期失败 | `npx vitest run --config docs/qa/main-review-20260922/book-probe.config.ts` → exit 1，`3 failed (3)`，失败原因与 r1 相同；探针目录 diff 为空；`probe-run-after-fix.txt` 为 r2 重跑结果且逐条一致 | **pass** |
| 8 | lint 0 警告 | `npm run lint` → exit 0，无 warning | **pass** |
| 9 | 采纳 ①：修复逐块写后读回 | `book-generation.ts:1489-1508`：写后 `readBookForRun` → 块为 `ready` 才 `writtenBlockIds.push`；否则 `droppedWrites += 1` 并 `finish(runChanged ? 'superseded' : 'failed', '写入未生效：书籍当前状态不接受生成…')` | **pass** |
| 10 | 采纳 ②：`setUserNote` 写后读回 | `books-store.ts:426-432 return readStoredNote(...) === text;` + `:434-443` 读取实现 | **pass** |
| 11 | 采纳 ③：失权文案 | `book-generation.ts:213-214`；e2e `books-harden.spec.ts:140` 断言同步更新 | **pass** |
| 12 | 采纳 ④：续跑提示不再矛盾 | `BooksRoute.tsx:522-525 if (handle.status !== 'failed')` | **pass** |
| 13 | 两条新回归存在且实质 | `book-generation.test.ts:796-815`（断言 `failed`/`writtenBlockIds` 空/`droppedWrites>0`/error 文案/`getRepair` 空/无块变 ready）；`books-store.harden.test.ts:131-160`（`saved === false`、数据未破坏、笔记仍为空） | **pass** |
| 14 | 复核点：整页重生成中"其他块 pending"是否误报 failed | 读回只检查**刚写入的那一个块**（`:1497-1498`），不看兄弟块；经验证据：两条整页用例与 e2e 连点用例均通过 | **pass（无误报）** |
| 15 | 复核点：`setUserNote` 正常路径仍为 true | 未改动的 `books-store.test.ts:238` 断言 `setUserNote(...) === true` 随 381 例通过；UI 取该布尔值如实提示 | **pass** |
| 16 | 文档口径复核 | README:44/46/47/50/54/55、LEDGER:19/20/21、STATUS:100/:143 与实测一致（`+28 = 13+8+5+2`） | **pass** |
| 17 | 处置记录与实际文件是否一致 | 我首轮记录称「STATUS 中 `replacement-run` 归属已改」——**当时 STATUS.md 未改**（仍为"原探针断言反转（返回 Promise、`replacement-run` 下无块变 ready）+ 单测 5 例"），记录与文件不一致 | **fail（仅文档，已回修）** |
| 18 | 同源：单测计数 | STATUS:68 的"单测 5 例"不准（M22-02 相关 7 例） | **fail（仅文档，已回修）** |
| 19 | 提交前还原 `next-env.d.ts` | 该文件现与 base 一致（diff 空），FROZEN 的 `notIncluded` 已写明 | **pass（r1 挑刺 6 已闭合）** |

### r1 挑刺处置核实

| r1 挑刺 | 独立核实 |
| --- | --- |
| 1（`writeListConverged` 耗尽返回最后值） | **成立（部分修 + 登记边界）**：`setUserNote`（`books-store.ts:426-432`）与修复路径（`book-generation.ts:1497-1508`）已改为写后读回；`books-store.ts:308` 仍返回 `last`，LEDGER 边界 #9 如实写明理由 |
| 2（修复逐块读回） | **成立**（结果表 9/13；无兄弟块误报，见 14） |
| 3（失权文案） | **成立**（11） |
| 4（续跑提示矛盾） | **成立**（12） |
| 5（"溢出 0" vs ≤1） | **成立**（README:55、STATUS:138 已改；本轮补：README:50、LEDGER:11、STATUS:70 已一并对齐为"≤1px"） |
| 6（`next-env.d.ts`） | **成立**（19） |
| 7（"新增界面只有两处"） | **成立**（README:54 三处） |
| 对账 27（PageReader 7→8） | **成立**（README:47、LEDGER:19 均为 2+6） |
| 对账 28（STATUS 探针归属） | 首轮**不成立**（17/18），已按本记录回修 |

### r2 新发现（低，均不构成假成功；已登记为已知边界）

1. **读回窗口内的终态归因不精确** — `book-generation.ts:1500-1508`：若在"写入 → 读回"极短窗口内发生删除或读取被拒，会被归为 `failed` + "不接受生成"，而非 `cancelled`/存储错误。三种终态都不报 `completed`。建议下一批把 `after.kind==='missing'` 归 `cancelled`、`denied` 用存储错误文案。
2. **`finishBookRun` 自身写入未做读回** — `book-generation.ts:976/992` 以内存返回值判定 `finished`/`interrupted`；若该次写入撞上边界 #9 的重放耗尽窗口，退出原因可能记 `finished` 而存储仍为 `compiling`（用户可见状态仍诚实显示"已中断 + 继续生成"）。建议对最终完成路径同样加一次读回。
3. **文档两处口径与一处归属** — 见 17/18 与挑刺 5，本轮已回修。

### not_run 与剩余风险

- **not_run**：`npm run typecheck`、`npm run build`（禁跑；旁证 BUILD_ID + 产物字符串 + e2e 新断言）。
- **not_run（沿用 r1）**：`apps/api` 测试（零改动）、真实供应商/真实 LLM（无调用入口）、真实浏览器 IME/修饰键（组件层覆盖）、运行中"读取被拒"的界面提示（源码 + 单测）、"同一毫秒并发写共享键"。
- **剩余风险**：边界 #9 为已登记的安全网缺口，其影响面被两处读回覆盖到用户可见声明；新发现 1/2 属亚毫秒竞态的归因精度；文档类未闭合项已在本轮回修。

### r2 结论（独立验收者原文）

> **r2 可交付。** 产品面：6 项修复 + 4 条采纳改动全部在源码中就位（附行号），两条新回归实质且通过；`48 文件 / 381 例`、`174 通过 / 0 失败 / 0 flaky`、探针 `3/3 按预期失败`、`lint 0 警告`、BUILD_ID 与 12 文件指纹均由其本机**独立复现**（未引用实施者归档）。唯一未闭合项是文档（STATUS:68 与 A1 报告相应陈述），不在产品指纹内，修正后**无需重新冻结产品候选**。边界重申：r2 通过仅代表本地模拟执行器与本地注入范围内的行为纠正，不代表真实供应商、真实 LLM/解析，也不代表 UI 视觉验收。

### 总控对 r2 新发现的处置

- 新发现 1/2 **本轮不改产品代码**：两者都不产生假成功（不报 `completed`、用户可见状态仍诚实），改动会使 r2 冻结失效并需要完整重跑 typecheck/lint/unit/build/全量 e2e 与又一轮独立复验；已连同建议的修法登记为已知边界（LEDGER §"语义变化的已知边界" #11/#12），列入后续批次的待办。
- 新发现 3（文档）**已回修**：STATUS:68 归属与计数改为"探针在返回类型断言处即失败终止 + 新增单测 7 例"；README:50 / LEDGER:11 / STATUS:70 的溢出表述统一为"横向滚动差 ≤1px"。
- 上述文档回修不触及任何产品文件，冻结指纹（12 文件 sha256 + BUILD_ID）保持不变。
