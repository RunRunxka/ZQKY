# H1-COURSE-SESSIONS v1 独立验收报告 r1（A1，只读复验）

> 归档说明（队长）：本文件由独立验收者 A1（`Independent-Acceptor`，只读、不修复）在候选 `8104654` 上产出，原样归档（§0–§7 为 A1 原文要点，长表格保留）；文末「总控处置（r1→r2）」为队长对 F1–F11 的逐条处置记录，不改写 A1 的原始结论与数字。A1 的证据日志在其本机 `%TEMP%\a1-h1cs\*.log` 与 `%TEMP%\a1-probe\`，不随仓库提交。

## 0. 任务版本、契约版本与“实现者已停止写入”

| 项 | 实测 |
| --- | --- |
| 任务版本 | `docs/qa/H1-COURSE-SESSIONS/TASK-CARD.md`（冻结契约：§1 数据/归属、§2 课程页、§3 聊天页、§5 验收条件 1–11） |
| 稳定决定版本 | `docs/PROJECT_GUIDE.md:157` §4.3（6 条） |
| 候选 | `8104654`，`main`，父 `a45b011`，tree `d55e1442fdb0cb04d3d3c2df1147b6c3ff41eb8f` |
| 停止写入 | 全程 `git status --porcelain` 为空（首/中/尾共 5 次），工作树 = HEAD；无实现者写入痕迹 |

## 1. 候选与指纹表

| 项 | 声称 | A1 实测 | 结论 |
| --- | --- | --- | --- |
| 候选提交 / 父 / tree | `8104654` / `a45b0116…` / `d55e1442…` | `git rev-parse 8104654^{tree}`、`8104654^` 与 FROZEN JSON 逐字相等 | pass |
| 差异规模 | 14 文件 +1333/−23 | `git show --stat 8104654` 一致 | pass |
| 逐文件 sha256(16) | FROZEN-CANDIDATE.json 14 条 | 14/14 匹配；另对 8 个文件比对工作树，8/8 一致 | pass |
| `68af6a0`/`9d966c3` 仅文档 | 不改产品代码 | `68af6a0` = 4 个 `docs/qa/**`；`9d966c3` = `docs/STATUS.md`、`PROJECT_GUIDE.md`、`docs/replica/**`、`docs/qa/H1-COURSE-SESSIONS/**`；零 `apps/**`、零 `tests/**` | pass |
| 范围排除 | 无 `.css`、无 `.env`、无构建产物、无 `apps/api` 产品代码 | `git show --stat 8104654 \| grep -E "apps/api/app\|\.env\|local-data\|\.next\|next-env\|\.css"` → 空；`apps/api` 只有 `tests/test_chat_stream_api.py` | pass |
| BUILD_ID | `2Rz23h6qbByqaJTSJY4x1` | 一致；mtime `19:02:02`（早于 A1 会话首个命令 19:26:11） | pass |
| 产物自证 | `所属课程：`/`返回课程`/`课程资源（仅登记引用` | 三串分别命中 3/6/6 个 `.next` server/static 文件 | pass |

## 2. 逐项结论表

### 2.1 用户 9 项产品要求

| # | 要求 | 关键证据 | 结论 |
| --- | --- | --- | --- |
| 1 | 课程详情展示本课程会话，新建/打开/恢复 + 加载/空态/读取失败/保存失败与重试 | `CourseSessions.tsx:23-28`、`:128-148`、`:117-126`、`:150-181`；e2e 第 1/2/3/9 例 | pass（读取失败分支当时**仅代码级**，见 F3） |
| 2 | 复用既有 `Conversation`/`chat-repository`/聊天 store；无第二套库、无模拟问答 | `CourseSessions.tsx:22` 用 `createIdbChatRepository('zhiqikeyuan-chat')`；全仓 `indexedDB.open` 仅 `chat-repository.ts:62`；e2e 捕获真实 `POST /api/v1/chat/stream` | pass |
| 3 | 归属按稳定 `courseId` 保存并贯通元数据；旧会话保持未归属；不猜归属 | 写入点穷举仅 3 处（`CourseSessions.tsx:63`、`store.ts:480`、`chat-repository.ts:40-43`）；`normalizeConversation` 只留非空字符串否则 `delete`；`toMeta:54` 条件透传；`course-session.ts:49` 仅相等过滤；e2e 第 2 例 | pass |
| 4 | 保存成功后才跳转；连点/重试/刷新/前进后退不产生重复会话 | `CourseSessions.tsx:66` `await save` 先于 `:67` `push`；e2e 第 3/4 例 | **fail（有界）—— F1** |
| 5 | 聊天页归属 + 返回课程；切换不残留 | `ChatWorkspace.tsx:191-198`、`:797-822`；`store.ts:385-399`；e2e 第 1/8 例；A1 探针 P3 补验两课程互切 | pass（警告字段残留见 F2） |
| 6 | 发送时冻结快照并**真正进入既有真实请求链路**；重试用原轮快照 | `store.ts:656-665`、`:680-682`、`:937-953`、`:978`、`:1049`；e2e 第 1/5/6 例（含整页 reload 后重试仍用旧快照）；`test_chat_stream_api.py` 9 passed；`test_providers.py` 18 passed | pass |
| 7 | 删除/归档/读取失败：保留历史、不级联、不换绑、不悄悄沿用其他课程 | `course-session.ts:29-40/54-58/110-132`；`store.ts:942-953`；e2e 第 6/7 例；A1 探针 P2 补验归档课程既有会话可打开、发送仍带本课程上下文 | pass |
| 8 | R-11 三态不回退；登记≠解析/检索/传给模型；RAG 未接入表述如实 | `course-session.ts:73-77/107-109/129`；单测含反向断言 `not.toMatch(/已检索到\|已解析教材\|RAG 已接入\|已向量检索/)`；`course-resource-faults.spec.ts` 回归 | pass |
| 9 | 保留手动大纲进度；不伪造掌握度/规划 | `course-session.ts:78-87`（covered 手判计数）；`CourseDetail.tsx:183-185`；`books-courses.spec.ts` 第 5 例 | pass |

### 2.2 独立复跑（A1 本机重现，不引用 README）

| 项 | A1 实测 | 结论 |
| --- | --- | --- |
| `npm run lint` | exit 0，无输出 | pass |
| 单元 `test:unit` | **51 passed / 415 passed（81.71s）** | pass |
| `test:api -- tests/test_chat_stream_api.py` | **9 passed, 1 warning（0.23s）** | pass |
| `test:api -- tests/test_providers.py`（A1 补跑） | **18 passed（0.04s）** | 补充证据 |
| 定向 e2e `course-sessions.spec.ts` | **9 passed（44.2s）**（耗时与环境有关，计数一致） | pass |
| 受影响 e2e `books-courses.spec.ts` | **6 passed（23.5s）** | pass |
| 全量 e2e `npx playwright test` | **189 passed / 0 failed（6.4m）**，无 flaky/retry | pass |
| `npx playwright test --list` | Total: **189 tests in 26 files** | pass |
| 构建 | 未重跑；BUILD_ID 一致；`.next` 在 A1 会话后新增文件数 0 | pass |

### 2.3 W1/W2 文档卡口复核 + 过期表述扫描

| 项 | 证据 | 结论 |
| --- | --- | --- |
| W1（CS 批次保证范围） | `68af6a0` 就地订正 `README.md:32/47/52` + `DEFECT-LEDGER.md:37` + 新增 `README.md:62` §5.2；原文可在 `git show b8136dd:…` 查到 | 已关闭 |
| W2（FOLLOWUP 候选/指纹/构建号） | `README.md:45-48` 已改为 tree/diff/14 文件 sha256；构建号 `YhmHpWDKx-EgSf1pGHkZh`；§4.1 关闭记录 | 已关闭 |
| 残留过期表述 | F5（`docs/ROUTES.md:22`）、F6（`PAGE_MATRIX.md:7` 自相矛盾）、F7（`STATUS.md:152`）、F8（`ReadingWorkspace.tsx:188/289`、`courses.css:60/106`） | 有残留（均低危） |

## 3. 挑刺（按严重度）

- **F1｜产品缺陷（中）｜新建学习会话在“保存并 push 之后、导航卸载之前”的窗口内再次点击会创建第二条会话 —— 直接违反要求 4。**
  最小复现（A1 自建探针，不进仓库）：`btn.click(); await new Promise(r=>setTimeout(r,10)); btn.click();` → **`gap=10ms → 新增 2`；`gap=25ms → 新增 2`**；`gap=0/50/80/150ms → 1`。机制：`CourseSessions.tsx` 的 `finally` 在 `router.push` 之后立即释放守卫，而 `/chat/<新uuid>` 的导航尚未卸载本页。影响：出现 2 条课程会话（其中一条为空），不丢数据、无假成功，可用 `/space/chat-history` 删除；窗口上界 = 导航延迟（慢设备更宽，键盘 Enter 连按亦可触发）。
- **F2｜产品缺陷（低）｜`courseContextWarning` 是 store 级字段，切到其他会话后残留**（A1 探针 `[P4] 切换后警告元素数=1`）；代码 `store.ts:942-953` 只写不清，`publish()`/`selectConversation` 都不清。请求内容不受影响（探针证明普通会话 `hasSystem=false`）。
- **F3｜测试有效性（中低）｜若干部位“声称覆盖 > 实际断言”**：① “连点不产生重复会话”仅同 tick（未覆盖 F1 窗口）；② 归档用例标题称“既有会话仍可打开且历史保留”但未打开任何会话（产品行为经 A1 探针 P2 证实成立）；③ `CourseSessions` 读取失败 + 重试**无任何测试引用**；④ `courseContextMessage` 的整体 2400 截断未测；⑤ “继续最近会话”无测试引用。**正面**：`books-courses.spec.ts:138` 的改动是**转换而非弱化**（1 条旧断言 → 2 条新断言，无删除），且同套件同时存在正向/负向 system 断言，故计数不是唯一证据。
- **F4｜文档不准（低）｜README §3 第 5 条与实现不符**：称“整体 ≤2400 字符，超出按条目截断并在文案里说明”，实现为整段字符级硬截断 + `…`（`course-session.ts:60-63/131`），没有“按条目”也没有说明句。
- **F5–F8｜文档/文案过期（低）｜** `docs/ROUTES.md:22`（课程详情“学习会话未接入”）；`PAGE_MATRIX.md:7` 同段自相矛盾；`STATUS.md:152`（§5.B 第 2 条仍以现在时写 localStorage 回退路径）；`ReadingWorkspace.tsx:188/289`（“会话课程标记未接入”）与 `courses.css:60/106` 注释。
- **F9｜边界/技术债（低）｜课程块不计入上下文预算**：`store.ts:663-665` 在 `contextBudgetChars` 裁剪**之后**追加 system（最多 +2400 字符），小窗口模型下可超预算（表现为上游报错，不是假成功）；批次文档未登记。
- **F10｜文档结构（nit）｜** `68af6a0` 把 `### 5.2` 插在 CS README §5.1 bullet 列表中间，导致“登记为已知边界（F5/F6）”两条读起来归属 §5.2。
- **F11｜测试写法（nit）｜** `course-sessions.spec.ts:326` 有一行无断言的遗留调用 `await page.getByRole('link', { name: '返回课程' }).count();`。
- **F12｜视觉（登记，不判 fail）｜** `.chat-banner.course`/`.chat-banner.warn` 无独立 CSS 规则，归属条与普通提示条视觉无区分；README §5.2 已如实声明且“不宣称视觉通过”——声明准确，不是夸大。

**A1 未发现问题的重点项（正面结论）**：无第二套会话库；无按标题/最近访问/URL 回填归属的路径；`save` 先于 `push`；删除/归档不改写会话字节；迟到写污染防线完整（turnId/sessionId/generation/terminal 四重守卫）；`retry` 走 `last.courseContext`（整页 reload 后仍成立 → 证明持久化）；无“无凭证却声称真实调用”。

## 4. not_run 清单与原因

| 项 | 原因 |
| --- | --- |
| 真实供应商问答 | A1 未发起真实调用；`apps/api/.env` 仅按“键名/非空行数”检查（未读值）：存在 1 条 `ZQKY_API_KEY_<id>`；`.local-data/` **不存在** → 本机没有可用的已保存连接/档案。故“无可用凭证”成立，但 A1 不背书该凭证有效性 |
| 逐状态视觉/动画人工评审 | 本批零 CSS 改动；只复跑 e2e 的溢出/焦点/reduce 断言，不代表视觉通过 |
| 移动端硬件触摸、真实两浏览器进程/两 profile 并发 | 本机未构造 |
| RAG 检索课程教材 | RAG 未接入，资源仅登记（R-11 三态） |
| `npm run build` / `typecheck` | 按只读约束不重跑；typecheck 证据仅来自 FROZEN JSON |
| 模型/供应商批次的清单项 | 归属模型批次；本候选 `apps/api` 产品代码与 `model-settings/**` 零改动 |

## 5. 剩余风险（A1 列，交付后仍存在）

1. F1 的双击窗口在慢导航/慢设备上变宽，属用户可见重复数据。
2. `CourseSessions` 读取失败分支与 2400 整体截断无自动化证据（当时）。
3. 课程块超预算（F9）在小窗口模型上可能触发上游报错。
4. `courseContextWarning` 跨会话残留会给出上下文错误的提示语。
5. 课程删除后发送走普通问答（与参考的差异已披露），用户自定义约定随之失效——已接受差异。
6. F5–F8 类过期文案会让后续接手者误判现状。

## 6. A1 结论

> **需修订（有界，1 处产品 + 1 处产品 + 文档清扫；其余全部通过）**：要求 1、2、3、5、6、7、8、9 独立复验通过；要求 **4 有界不通过（F1）**。结论只覆盖**本地模拟上游替身 + 冻结生产构建产物 + 真实 FastAPI/适配器替身测试链路**；不宣称真实供应商通过、不宣称 UI 视觉/动画通过、不宣称 typecheck/build（未重跑）。批准后“代码候选 + 数字证据”部分不需重做：14/14 指纹、189 例全量 e2e、9 例定向、415 单测、9+18 后端用例均已由 A1 本机重现。

## 7. A1 声明：未修改仓库任何文件

A1 跑过的命令类别：`git rev-parse/show/log/status`（只读）、`cat/sed/grep/find/stat/netstat`、`npm run lint`、`test:unit`、`test:api`、`npx playwright test --list` 与定向/受影响/全量 spec、以及基于**仓库外临时配置**的自建探针（P1–P4）。未执行任何 git 写操作、未 install、未 build、未碰 `.env`/`.local-data`/浏览器 profile；`.next` 在 A1 会话开始后新增文件数 = 0；端口 5174 每次跑完均释放；`git status --porcelain` 全程为空（e2e 只写 `.gitignore` 覆盖的 `test-results/`）。

## 8. 总控处置（r1 → r2，队长，2026-09-22）

| 卡口 | 处置 | 证据 |
| --- | --- | --- |
| **F1（必须修）** | **已修（产品）**：`CourseSessions.createSession` 改为“保存成功即**保持守卫到本页卸载**，只在失败分支释放 `creatingRef`/`creating`”，`router.push` 之后不再有可再次进入的窗口 | 源码 `CourseSessions.tsx`；新增 e2e「跨任务二次点击…」用 A1 同款探针（+20ms JS click）断言本课程会话**恰好 1 条** |
| **F2（同批修）** | **已修（产品）**：`create`/`selectConversation`/`deactivate`/`removeConversation` 四处清除 `courseContextWarning` | 源码 `store.ts`；课程删除 e2e 追加“切到普通新会话后警告消失”断言 |
| **F3（补证据）** | **已补**：新增 e2e「会话列表读取失败 → 错误 + 重试 → 恢复（不冒充空态）」；归档用例预置既有会话并**实际打开验证历史**；单测新增整体预算收缩用例；课程列表断言「继续最近会话」`href`；删除 F11 的无断言调用 | `tests/e2e/course-sessions.spec.ts`、`apps/web/src/services/course-session.test.ts` |
| **F4（文档 vs 实现）** | **改实现 + 改文档**：`courseContextMessage` 改为预算内收缩（压缩标签 → 减少条目并标注「…等共 N 项」→ 压缩约定），**免责句是固定前缀、不被砍尾**；README §3 第 5 条改写为真实行为 | `services/course-session.ts`、批次 README §3 |
| **F5–F8（清扫）** | **已清扫**：`ROUTES.md` 课程详情行、`PAGE_MATRIX` 矛盾句、`STATUS §5.B` 第 2 条回退路径加注、阅读页 chip/注释与 `courses.css` 注释 | 见对应文件 |
| **F9（登记）** | **已登记**：批次 README §10 第 7 条（课程块在预算裁剪后追加，最多 +2400 字符；超预算表现为上游报错而非假成功） | 批次 README |
| **F10（结构）** | **已修**：CS README 的 §5.2 移到 §5.1 bullet 列表之后 | `docs/qa/H1-BOOKS-COMMIT-SAFETY/README.md` |
| **F12（视觉）** | **不修，如实保留**：本批不宣称视觉通过；`.chat-banner.course` 仅作语义标注与测试锚点 | 批次 README §5.2 |

**处置后状态**：F1/F2 为产品代码改动 → **重新冻结候选并重跑**（新构建 + 定向/全量 e2e + 单测），随后交 A1 r2 复验（见 `A1-REPORT-02.md`）。r1 已验证通过的其余 8 项要求、14/14 指纹集合中未受影响的部分（13 个产品文件中的 11 个）与全部测试数字在 r2 中只做“未回退”核对。
