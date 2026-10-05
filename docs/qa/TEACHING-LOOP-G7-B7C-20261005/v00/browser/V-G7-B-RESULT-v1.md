# V-G7-B 独立验收结果 v1（同源双页真实浏览器链）

- ID/版本：V-G7-B/v1
- 验收者：V-G7-B（非作者；只读产品；只写 `docs/qa/TEACHING-LOOP-G7-B7C-20261005/v00/browser/`）
- 日期：2026-10-05（UTC 13:06–14:03；本地 +08:00）
- 候选：冻结构建 `apps/web/.next`（BUILD_ID `49nH0q5IXMfFQTcg4mpIR`，构建内代理目标 `http://127.0.0.1:8001`），源码指纹见 `edit/CANDIDATE-sources-prebuild-v1.json`
- 证据目录：`H:\备份xuexi\智启课源\docs\qa\TEACHING-LOOP-G7-B7C-20261005\v00\browser\`
- 结论一句话：**G7 写入闸门链 4/4 通过（r2b 单轮完整运行 4 passed / 0 failed / 0 retry / 0 skip）；r2 在任务卡原样 `trace:'on'` 配置下断言链全部完成，但受本机 Playwright runner 的 trace 收尾卡住影响被标为 timedOut（工具/环境缺陷，非产品缺陷）；r1 首败为本 spec 自身的同源语义断言错误，全部原始产物保留。**

## 0. 判据结果总表

| 用例（同一全新隔离 BrowserContext，两个 Page A/B） | r1 | r2（trace:'on'） | r2b（trace:'on' 配置 + CLI `--trace=off`） |
| --- | --- | --- | --- |
| create B-unknown-then-A-blocked 390 | fail（spec:383 断言错误） | timedOut（断言链全通过） | **pass** 12.40s |
| create B-unknown-then-A-blocked 1440 | fail（spec:383 断言错误） | timedOut（断言链全通过） | **pass** 12.97s |
| import B-unknown-then-A-blocked 390 | fail（spec:383 断言错误） | timedOut（断言链全通过） | **pass** 7.96s |
| import B-unknown-then-A-blocked 1440 | fail（spec:383 断言错误） | timedOut（断言链全通过） | **pass** 8.94s |

- 每例关键计数（r2/r2b 逐例一致）：**B 的 POST = 2**（第 1 次被扣押、`abort` 成未知；第 2 次为显式重放，两者逐字节相同）；**A 的 POST 在步骤 3.4 与 3.6 = 0**；A 在 3.7 显式重发 1 次（自己的 submissionId）；总 POST 序列恰为 `B, B, A`。
- r2b 单轮完整运行：`4 passed (43.4s)`，exit 0，workers 1、retries 0、0 skipped、0 flaky。

## 1. 候选与冻结构建核验

- `apps/web/.next/BUILD_ID` = `49nH0q5IXMfFQTcg4mpIR`（mtime 2026-10-05 20:48）✓
- 构建内 rewrites：`/api/v1/:path*` → `http://127.0.0.1:8001/api/v1/:path*`（`apps/web/.next/required-server-files.json` 的 `_originalRewrites`）✓ 与任务卡“proxy 8001”一致。
- `CANDIDATE-sources-prebuild-v1.json` SHA 复核（独立复算）：8 项中 7 项逐字节一致；`apps/web/next-env.d.ts` 与候选 JSON 的 “prebuild” 值不同，当前磁盘值 `0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc` 恰等于 `edit/BUILD-EVIDENCE-v1.json` 的 `nextEnvSHA`（构建后从 `opening-bytes` 恢复），属已登记的恢复动作、非未登记漂移。
- 前端启动（自起、隔离端口）：`ZQKY_API_ORIGIN=http://127.0.0.1:8001 node scripts/run-web.mjs start 5175`，PID 21868，birth 2026-10-05 21:05:27 (+08:00)，argv `"C:\Program Files\nodejs\node.exe" scripts/run-web.mjs start 5175`；未启动 API、未占用 5174/8001。

## 2. 运行清单

| run | 时间（UTC） | 命令 | 关键配置 | exit | 结果 |
| --- | --- | --- | --- | --- | --- |
| g7b-r1 | 13:06:02–13:14:24 | `G7B_RUN=g7b-r1 node node_modules/@playwright/test/cli.js test -c docs/qa/TEACHING-LOOP-G7-B7C-20261005/v00/browser/external.config.ts` | trace on / workers 1 / retries 0 | 1 | 0 passed / 4 failed / 0 retry / 0 skip（首败，见 §3） |
| g7b-r2 | 13:51:51–14:00:15 | 同上 `G7B_RUN=g7b-r2` | trace on | 1 | 4 timedOut：断言链全通过，唯一错误 `Test timeout of 120000ms exceeded`（见 §5） |
| g7b-r2b | 14:02:01–14:02:45 | 同上 `G7B_RUN=g7b-r2b` + `--trace=off`（CLI 覆盖；配置文件仍为 `trace:'on'`） | trace off（声明偏离，见 §5） | 0 | **4 passed**（12.40 / 12.97 / 7.96 / 8.94s） |
| g7b-r2probe（诊断） | 13:24:52–13:26:56 | 修正后单例 `import … 390` | trace on | 1 | 断言链全部完成（含 `v-g7b-case-evidence`），唯一错误为 runner 超时 |
| g7b-diag-probe*（诊断） | 13:28–13:48 | `diag-probe.config.ts` / `diag-probe2.config.ts` | 最小复现，见 §5 | — | 见 §5 |

运行均单轮完整、`retries 0`、`fullyParallel:false, workers:1`；失败/超时产物原样保留，未删改、未拼轮。

## 3. r1 首败定因（本 spec 的同源语义断言错误，非产品缺陷）

- 失败点：`g7b.spec.ts:383` `expect(await s.rawOperation(b, kind)).toBeNull()`，4 例同点（`g7b-r1.json` 的 `errorLocation.line=383`）。
- 定因：A、B 在**同一 BrowserContext、同源共享同一个 localStorage**；`rawOperation(a, kind)` 与 `rawOperation(b, kind)` 读的是**同一个键**。3.4/3.5 已通过——A 被阻断（A 的 POST 0、A 页键逐字节等于 B 原字节、可见“另一原操作/尚未发送HTTP”、开始按钮禁用、缓存重试可用）；B 显式重放第 2 个 POST 与原 POST 逐字段/逐字节相同、成功后 B 自己的包被清理（键空）。到 3.6，A 点“重试创建/导入操作恢复缓存”后把 A 自己的原包写回同一个键，因此从 B 页读同一键**必然**是 A 的包（r1 收到的正是 A 的包：`payload.source=manual`/`data.title=G7B独立create390A完整课题`、A 的 `loadGeneration`），与上一行 `rawA` 一致；期望 `null` 是错误期望。
- 处置（按 CTRL 指示，未改产品、未放宽产品判据）：修正为断言共享键此刻**逐字节等于 A 刚恢复的 `rawA`**，并要求**在 a、b 两页读到同一值、且非 null、且不等于 B 原字节**（更严格）。同时复核了全部 `rawOperation(a|b, kind)` 期望：3.1（加载时两页键空）、3.5（B 成功清理后两页读一致为空）、3.6（进入时键空）、3.7 与收尾（A 成功清理后两页读一致为空）在各时点均为真，且都改为 a、b 双页读证。
- r1 原始产物全部保留且未改动：`g7b-r1.log` / `g7b-r1.json` / `g7b-r1.xml`、`g7b-r1/<case>/`（trace.zip、test-failed-*.png、error-context.md、公开正文 JSON），SHA 见 §8。

## 4. 判据逐项（任务卡步骤 3.1–3.7；r2 与 r2b 每例证据一致）

| 步骤 | 判据 | 结果 | 关键证据 |
| --- | --- | --- | --- |
| 3.1 | 同一全新隔离 Context 内 A、B 两 Page；真实同源 localStorage 共享 | PASS | `a.context()===b.context()===context`；origin 均 `http://127.0.0.1:5175`；加载时两页操作键均空；A 写 legacy 键 B 读到、B 写 proof 键 A 读到（真实读写往返） |
| 3.2 | B 点击开始 → 恰 1 个 B 的 POST 被扣押；存储包与 POST 逐字段一致（完整恢复包） | PASS | `posts(B)=1` 且无 A；`submissionId=operationId=POST.submissionId`；`metadata.contextKey=lesson\|new\|<kind>`、`loadGeneration` 非空、`originalEditGeneration` 整数；`payloadKey` 等于独立复算的 `stablePayloadKey(payload)`；`payload === POST 去 submissionId`；create: `data====B正文`、`source=manual`；import: `draft===legacy 信封`；POST 键集恰为 `classId\|context\|data\|source\|subjectId\|submissionId`（create）/`classId\|context\|draft\|subjectId\|submissionId`（import） |
| 3.3 | B 的 POST 作为未知释放（abort）→ 可显式重放；B 原字节逐字节保持 | PASS | “重试原创建包/重试原导入包”出现且可用；`rawB1 === rawB0`（逐字节，两页读一致） |
| 3.4 | A 点击同一开始按钮 → 无第 2 个 POST；A 的操作键逐字节等于 B 原字节；可见阻断原因；A 禁用/重试缓存可用/不解锁/不导航/不创建 | PASS | A 的 POST 0（总 posts=1、无 A 的 held）；两页读到的操作键 `=== rawB0`；可见 alert 文本“发送前恢复缓存写入失败：当前恢复缓存已属于另一原操作，原字节保持。尚未发送HTTP。”（含“另一原操作”与“尚未发送HTTP”）；开始按钮禁用、`重试创建/导入操作恢复缓存` 可见可用、重放按钮为 0；URL 仍为 A 自己的文档、文档 GET 集合 `{idA,idB}`、A 页 localStorage 快照逐键不变；B 重放按钮保持可用 |
| 3.5 | B 点击重试原包 → 第 2 个 POST 与第 1 个逐字段/逐字节相同 → 成功 → B 自己的包被清理 | PASS | 两次 POST `raw` 逐字节相同（SHA256 相同）、`submissionId` 相同、完整 payload/metadata 相同；201 回执后操作键为空（a、b 两页读一致）；B 页面跳转到回执文档且标题匹配 |
| 3.6 | A 恢复缓存 → 成功恢复 A 自己的原包（payload 与 A 的输入一致、submissionId 为 A 的身份）；仍无 A 的 POST；界面提示“尚未发送HTTP，请显式重试原包” | PASS | 共享键逐字节 `=== rawA`（a、b 两页同值、非 null、`!== rawB0`）；create: `payload.data` 与 A 的初始正文及 A 页“备份草稿”导出的当前正文逐字段一致；import: `payload.draft` 与点击时磁盘 legacy 信封逐字段一致；`submissionId !== B 的`；A 的 POST 仍 0；toast“原操作包已恢复到缓存；尚未发送HTTP，请显式重试原包。”可见 |
| 3.7 | A 显式重试原包 → 第 3 个 POST 用 A 自己的 submissionId 与完整载荷；成功后 A 自己的包被清理 | PASS | 第 3 个 POST `submissionId === A 存储包 submissionId`（`!== B 的`），body 去 submissionId 后逐字段 `=== A 存储包 payload`；201 后键为空；序列恰为 `B, B, A` |
| 收尾 | 无未授权/跨站请求；legacy 原字节不变 | PASS | `unauthorized=[]`；非 GET 仅 3 个预期 POST；全部 `/api/v1` 请求 origin 仅 `http://127.0.0.1:5175`（无直连 8000/8001）；legacy 原字节在各检查点均不变 |

视觉核验（不只看 JSON，实际看页面）：A 被阻断 390/1440 整页图中三个开始按钮均禁用、蓝色“重试创建/导入操作恢复缓存”可用、红色阻断原因可见；A 恢复 1440 图中 toast 文案可见、`重试原导入包` 可用、开始按钮禁用；B 未知 390 图中 `重试原导入包` 可用。截图字节同时内嵌在 run JSON 与提取目录 `g7b-r2b-evidence/<case>/*.png`。

## 5. 基础设施发现：`trace:'on'` 下 runner 用例收尾卡住（需 CTRL 判处）

- 现象：`trace:'on'`（任务卡原样配置）时，即使**断言链全部完成**，Playwright runner 在用例结束后的 trace 收尾环节卡住，直到用例超时计时器（120s）触发，将用例标为 `timedOut`；trace.zip 仍会写出。r2 的 4 例、`g7b-r2probe` 均如此，唯一错误文本为 `Test timeout of 120000ms exceeded`，**无任何断言错误**；每例全部证据附件（含 `v-g7b-case-evidence`，`ok=true`）均生成。
- 同环境最小复现与排除（全部在 5175 冻结构建、同一机器）：
  - 极简用例 `diag-probe.spec.ts › diag single page load`（`goto /lesson-plans` + 断言标题）在 `trace:'on'` 下同样卡住；`--trace=off` 时该组 3 个用例 3.7s 内完成。
  - 非 msedge 特有（`channel: chrome` 同样卡）；换 G6 形态配置（import 根配置 + spread `use`，`diag-probe2.config.ts`）同样卡；`outputDir` 换到 `C:\...\Temp` 同样卡；关闭 snapshots/screenshots/sources 仍卡；页面静置 networkidle + 800ms 后仍卡。
  - 对照通过：纯静态 HTTP 页（本机 5176 静态 HTML）`trace:'on'` 1.6s 通过；`about:blank`/`setContent` 通过；在用例体内显式 `context.tracing.stop({path})` 返回 **17ms**（stop 本身不慢）。
  - `DEBUG=pw:api,pw:browser` 显示卡点在 `browserContext.close succeeded` 与 `browser.close started` 之间、时长≈剩余用例超时；期间 msedge CPU 空闲、trace 临时目录为空。
- 边界与处置：判定为**验收环境工具链问题**（Playwright 1.58.2 + 本机 + 本项目页面），与 G7 候选源码和断言语义无关，不以它判产品失败。r2 作为“工具卡住”记录原样保留；判据通过性以 **r2b**（同配置 `trace:'on'`、CLI `--trace=off` 的单轮完整运行，4/4 passed、0 retry）为准，并在此显式声明该 CLI 偏离仅用于规避 runner trace 收尾卡住；trace 证据由 r2 提供（4 个 `trace.zip`，SHA 见 §8）。建议 CTRL 决定是否在其它环境/Playwright 版本复跑“`trace:'on'` + 单轮全绿”，不建议为此改产品。

## 6. 服务与关闭收据

- 启动：`ZQKY_API_ORIGIN=http://127.0.0.1:8001 node scripts/run-web.mjs start 5175`；PID 21868；CreationDate `2026/10/5 21:05:27`；argv `"C:\Program Files\nodejs\node.exe" scripts/run-web.mjs start 5175`；日志 `g7b-web-5175.log`；端口监听 `127.0.0.1:5175`（PID 21868）。
- 关闭：按 **PID + 出生时间 + 命令行** 三项守卫核验一致（输出 `GUARD-OK`）后 `Stop-Process -Id 21868 -Force`；关闭后核验：该 PID 不存在、5175 不再 LISTENING、`run-web.mjs start 5175` 进程数 = 0。仅关本进程，未触碰 5174/8000/8001/其它进程。
- 诊断用静态页服务（仅用于 §5 对照，非产品/非前端服务）：`node C:/Users/96022/AppData/Local/Temp/g7b-static-5176.mjs`（127.0.0.1:5176），PID 23992、birth 2026/10/5 21:50:25；按 PID/出生/argv（`g7b-static-5176.mjs`）守卫核验后 `Stop-Process -Id 23992 -Force`，核验进程消失、5176 不再 LISTENING。关闭后全机 5174/5175/5176/8001 均无 LISTENING。
- 说明：`g7b-web-5175.log` 中 2 条 `Failed to proxy http://127.0.0.1:8001/api/v1/model-catalog ECONNREFUSED` 来自运行前 curl/裸浏览器冒烟时的 SSR 侧目录读取，恰证明 8001 无服务可达；判据运行中浏览器侧 `/api/v1` 全部被 `context.route` 接管（`apiRequestOrigins` 仅 5175），未触真实业务 API/数据库/凭据。

## 7. 未执行项与边界

- 未运行后端 pytest、前端单测、全量 e2e、RAG/学情复算等（不属本卡范围）；未做真实模型调用。
- 未使用真实模型/数据库/凭据；无网络出站（除本机 127.0.0.1:5175 与诊断用 5176 静态页）。
- §5 的工具链问题未继续根因到 Playwright 源码级（已给出最小复现、对照与排除项）。
- 未修改产品源码、权威文档、锁文件、Git 记录；未改动旧 QA（G6 spec/config 仅只读参考，未复用其“两页先后正常写入同键”前置）。
- 诊断用临时文件（`diag-probe*.ts`、`g7b-diag-*`、`g7b-outH/`）保留在本目录，作为 §5 的证据；均属本批自有 QA，不影响产品与旧 QA。

## 8. 证据清单与 SHA256（详见 `V-G7-B-artifacts-sha-v1.json`）

| 文件 | 说明 | SHA256（前 16） |
| --- | --- | --- |
| `external.config.ts` | 外部配置（`G7B_RUN`、`webServer: undefined`、trace:'on'、retries 0、reporters 到 `<run>.json/.xml`） | d7f8a8e8d3cb3715 |
| `g7b.spec.ts` | 最终 spec（含 3.6 修正） | 183d5b8cfd405905 |
| `g7b-r1.log` / `.json` / `.xml` | 首败成绩单（未改） | 2591193036956296 / 0224f6e7e8dcac7b / b89c6d3c11132db4 |
| `g7b-r2.log` / `.json` / `.xml` | trace:'on' 单轮（断言链全通过、runner 超时） | 73eefc3a81aafa4c / 2805470476f9b728 / ae40711981e68b16 |
| `g7b-r2b.log` / `.json` / `.xml` | 判据单轮 4/4 passed | 8288e53f85cd134d / 5891e779228bbc5c / ae4418b405854cfc |
| `g7b-r2/<case>/trace.zip`（4 个） | 各例 trace（trace:'on'） | 662afac2f84a389a / 1e42b39a9e486b67 / 081e137fb1e09fa3 / 857499cb5b199410 |
| `g7b-r2-evidence/`、`g7b-r2b-evidence/` | 从 run JSON 解出的每例截图/阻断文本/证据 JSON（各 4 例） | 见各目录内文件；`*.summary.json` 汇总 |
| `g7b-web-5175.log` | 自有前端服务日志 | d801f719e2371ba9 |
| `diag-probe.spec.ts` / `diag-probe.config.ts` / `diag-probe2.config.ts` + `g7b-diag-*.log` | §5 工具链卡住的最小复现与排除证据 | 52496d1dbe28f3a9 / 9a8841ae36a1d31f / dc7694aa188c1fe8 |
| `V-G7-B-artifacts-sha-v1.json` | 全量 SHA 清单 | — |
