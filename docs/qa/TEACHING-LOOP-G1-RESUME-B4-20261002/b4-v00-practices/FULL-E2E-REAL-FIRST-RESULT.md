# B4 FULL E2E 原全集合单轮 — real-first

最终冻结候选 `CANDIDATE-b4-r13-ui-final.json`（SHA256 `68b9222de673e2abd6601c1001a6198b3e8e1d84276a1a1a483d2a1885f2327b`）单轮实际 **24 spec / 153 case：152 pass、1 fail、0 skip、0 flaky**，exit 1。153 个 actual attempts，所有 retry=0。完整原集合门禁未通过，B4 未关闭；没有试跑、重跑、改断言、产品修改或提前进入后续批次。

唯一首败为第 117 例 `question-bank-real.spec.ts` 的“真实 AI 补题 queued@0→attempt 1→人工校对确认→知识点检索”。失败前真实生成 queued/attempt/候选、人工编辑、再次校对、确认入库 200/无 failures/1 个正式 questionId 和“本次已入库 1 道题”断言均已执行通过。点击“查看已入库题目”后，`tests/e2e/question-bank-real.spec.ts:316:58` 断言 library tab 的 `aria-selected=true`，实际 10000 ms 内连续 13 次是 false。此处是实际返回界面选中状态错误，根因待后续冻结归因；首败之后的知识点筛选等断言未执行，不声称完整链已通过。第 118 例真实公共 retry 与其后剩余 35 例全部通过。

JSON 与 JUnit 独立解析计数一致：153 tests、1 failure、0 skipped，reportErrors=[]。Playwright JSON elapsed 378698.018 ms，wrapper 实际 elapsed 379467.171 ms（约 6.3 分钟）；collection 日志实际为 `Running 153 tests using 1 worker`。没有 grep、shard、单 spec/subset、重试或 timeout override；源内既定单例 timeout 保留。

| 原 spec | 实际 pass | fail |
| --- | ---: | ---: |
| assessments | 4 | 0 |
| books-commit-safety | 6 | 0 |
| books-courses | 7 | 0 |
| books-harden | 6 | 0 |
| books-pipeline | 14 | 0 |
| chat-composer-boundaries | 1 | 0 |
| chat-composer | 2 | 0 |
| chat-context-budget | 4 | 0 |
| chat-deeplink | 7 | 0 |
| chat-home | 4 | 0 |
| chat | 4 | 0 |
| course-resource-faults | 9 | 0 |
| course-sessions | 11 | 0 |
| knowledge-points | 9 | 0 |
| lesson-plan | 9 | 0 |
| model-settings-nesting | 4 | 0 |
| model-settings | 8 | 0 |
| navigation | 7 | 0 |
| question-bank-real | 1 | 1 |
| replica-settings | 1 | 0 |
| settings | 1 | 0 |
| shell-home-nav | 24 | 0 |
| sidebar-chat-fixes | 5 | 0 |
| sidebar-transition | 4 | 0 |

本轮只使用现有 Node24.19.0 运行 Playwright；用户前端 Node26/PID 3820、start `2026-10-02T22:56:41.760745+08:00` 保持，实际 build `ST2AWsfwxRYxFKZb_qsip`。`BUILD-IDENTITY-b4-r13.json` SHA `fb25165fa1c0d25dda45f519a8a5876094ad29815fb99bb745fd5a6fc2612d42` 的全部 2007 构建文件，以及 878 产品 / 43 可执行 QA / 5 契约文件，前后实际核对均 0 漂移；post 核对时间 `2026-10-02T15:15:23.048021+00:00`。运行前实际 8001/8002 空，用户 5174 身份匹配；未启动或停止用户前端。

准备期只读 HTML 核对曾误用不存在的 `/targeted-practice`，实际 404 的 PowerShell 非终止错误复用了上一条 response，故第一份该路径 HTML metadata 无效。原记录保留，`*-frontend-pre-r2.json` 明确纠正为正式 `/practices`；三正确路由 `/learning-analysis`、`/practices`、`/assessments` 已逐项真实 200。这不是业务反例或额外测试执行，不影响当时实际候选/构建 SHA 核验，也不计入 153 例。

外层 `ZQKY_KEEP_TEST_DATA=1`、唯一 `ZQKY_B4_QA_RUN=real-first` 实际启用；wrapper 创建新 outer temp `C:\Users\96022\AppData\Local\Temp\zqky-b4-full-e2e-real-first-liw8m0mh`，test/UTF8/新 DATA_DIR/空教材目录/Qdrant 16333/embedding 9/credentials None 隔离条件保持。wrapper child PID 25408 已实际退出，34965 字节完整 stdout+stderr 合并日志可独占读取，流已闭合；日志 SHA `68ecb584e256590de87d12ee36364e7d4c1886d4aebebe2191f951f757a20c91`。

两个 spec 的实际保留分支共产生 **3 个新根**：失败后 Playwright 按原配置换 worker 继续下一例，第二个题库根不是 retry。3 个 `[CREATED]` 与 3 个 `[RETAINED]` 精确逐根配对，全部 childClosed/logClosed=true；实际 PID 均不存在，每份 96 字节 API 日志独占读取成功，每根 4 个 SQLite 文件仍保留。

| spec / 新 tmpRoot | API PID | api.log SHA256 |
| --- | ---: | --- |
| assessments / `zqky-f20i-sPgYwW` | 25268 | `deec5548e41822bd7980c91a2b47b203625291be32967b3a58cc79acdd5d7b13` |
| question-bank-real 首败 / `zqky-f10-real-jIlDRs` | 25456 | `c1de2bbcd5bcf299e4523e1d93220226713f23fb76fbed25ba3cdc655d3aaf74` |
| question-bank-real 后续 / `zqky-f10-real-6BBw8R` | 26068 | `9b08e9965fd78d7beaa0fd6f0055ee2b92fa6e1934ed81239aa8cbb37e305ebc` |

所有新样本和完整 API 日志在系统 temp 下原样保留，旧六目录及未知数据未操作。运行后实际 8001/8002 无监听，唯一相关监听 5174/PID3820 仍在。此轮仅执行 KEEP=1 保留分支；默认 cleanup 分支的旧真实验证不冒充本轮重验。

首败 trace ZIP 2251497 字节、105 项：中央目录可读、EOCD offset=2251475、标准库逐项 CRC 全部通过，逐项名称/长度/CRC/SHA 已保存；ZIP SHA `ccedf777c065f40e7801d6d44513b55fb7c189ae5ca7e34f06cb6ac3fb0fbfa0`。4699 字节 error-context SHA `e103b50ebaa576968796eace31743d58af9d739ec8d44b02a8652c3ff2cae80f`，完整截图与 trace 未覆盖。

完整原始输出是 `b4-root/full-e2e-real-first-command.json` / `.log`，`b4-e2e-real-first/results.json` / `results.xml` / `artifacts/**`。本目录 `FULL-E2E-REAL-FIRST-CASE-INDEX.json` 保存全部 153 例原始 result/errors/attachments，`*-BY-SPEC.json`、`*-RESOURCES.json`、`*-ARTIFACT-VERIFY.json`、`*-SUMMARY.json` 与 pre/post 保存计数、资源、哈希和实际状态。

已执行准确命令（仓库根 cwd）：

```powershell
$env:ZQKY_B4_QA_RUN='real-first'
$env:ZQKY_KEEP_TEST_DATA='1'
& 'apps/api/.venv/Scripts/python.exe' 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-root/run_check.py' --label full-e2e-real-first --candidate 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/CANDIDATE-b4-r13-ui-final.json' -- 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/@playwright/test/cli.js' test --config 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-e2e.external.config.ts'
```

本次完整单轮结果与首败已闭合。本方停止所有文件写入和执行，等待 CTRL 后续冻结归因卡；不以既有 API/check/独立 B4 浏览器绿替代此次原全量失败。
