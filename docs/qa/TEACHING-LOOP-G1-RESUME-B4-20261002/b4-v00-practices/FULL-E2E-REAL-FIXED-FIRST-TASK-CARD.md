# B4 FULL E2E 修复候选原全集合 — real-fixed-first（仅准备）

当前只准备新任务卡/准确命令，未运行测试、list、子集或服务，未改任何可执行源。原 `real-first` 的 24 spec / 153 case、152 pass / 1 fail、完整首败和所有样本永久保留；本卡不是执行放行。

CTRL 已报告 r17 check/build 实际 exit0 / 104383.649 ms、unit1110、type/lint0、next-env 原字节恢复。拟执行身份只绑定 `CANDIDATE-b4-r17-nav-final.json`，SHA256 `7ee8b05c5bdacd17c3410c08f6a31b026fbcf26a895f227c9e2cb877d8b792b1`（878 产品 / 45 可执行 QA / 5 契约），`BUILD-IDENTITY-b4-r17.json` SHA `29252444df2d9fb4160c3f26b9d28baaf3b93271014a49f696883feb51ae8b93` / BUILD_ID `Ji-Jz8X9yY2R_79JOPivD` / 2007 构建文件。这里只读核了两份 identity JSON 的 SHA，没有提前执行门禁或冒充完整运行前 audit。

必须等待用户手动启动的新 5174 前端，由 CTRL 给实际新 PID/创建时间/命令/BUILD 与真实 8001 代理身份；旧 PID3820/旧 build 不作为本轮条件。Agent 不启动、停止、重启或替换用户前端。第六轮新种子 B4 完整独立浏览器完成、CTRL 所有 owned8001/8002 后端实际关闭、日志/子进程退出且端口空，再由 CTRL 明确放行本轮。不能与第六轮或聊天 stream 生命周期交叉运行。

放行后先真实核当前候选全部 878/45/5、2007 构建文件、next-env、用户前端和 8001/8002 空状态，完整保存 pre；若有身份或端口问题停止，不试跑。完成后同样核 post，报告实际时序和所有差异，不把后续声明修复误写为原运行漂移。

唯一新 output run 为 `ZQKY_B4_QA_RUN=real-fixed-first`，wrapper label 为 `full-e2e-real-fixed-first`。本次准备只读检查 `b4-e2e-real-fixed-first` 及新 wrapper log/receipt 均不存在，正式执行前再核拒绝覆盖。

准确完整原 24 spec 单轮命令（仓库根 cwd）：

```powershell
$env:ZQKY_B4_QA_RUN='real-fixed-first'
$env:ZQKY_KEEP_TEST_DATA='1'
& 'apps/api/.venv/Scripts/python.exe' 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-root/run_check.py' --label full-e2e-real-fixed-first --candidate 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/CANDIDATE-b4-r17-nav-final.json' -- 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/@playwright/test/cli.js' test --config 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-e2e.external.config.ts'
```

使用现有 Node24.19.0 只运行 Playwright，不换用户前端 runtime、不升级依赖。外部配置仍继承原完整 tests/e2e、workers1 / fullyParallel=false / 45000ms / expect10000ms / use / channel / trace，仅已有无 webServer 和本批 reporter/outputDir 适配。没有 spec 参数、grep、shard、retries、timeout override 或改断言；153 为原当前集合预期，仍从本轮实际 collection + JSON/JUnit 核计数，不套历史 pass 数。

wrapper 在间接 main 前建立新 OS outer root、test/UTF8/new DATA_DIR/空教材/Qdrant16333/embedding9/credentials None，实际 KEEP1 和唯一 QA_RUN 另行登记。现有 wrapper 只读 branch/HEAD metadata 沿用 CTRL 授权，不新增 Git 操作。其 stdout/stderr 是完整合流日志，记录实际 argv/cwd/env/PID/start/exit/elapsed，不能伪称独立 stderr=空。

旧首败例全部原断言保留：人工确认后返回 library 必须 selected=true；选择 math 后再选本次正式 pointId，原精确查询 total/questionId/题卡/题干/detail知识点/provider/profile 断言必须实际执行通过。不是只跑该失败例，也不以 query URI 单测或第六 B4 浏览器绿替代原全量门禁。

两个原 spec 自管8001生命周期，workers1串行；只触发资源 KEEP1 保留分支。提取本轮全部 `[CREATED]` / `[RETAINED]`，逐个新根配对、核 childClosed/logClosed、实际 PID/创建身份、日志独占读取、SQLite/样本仍在。根数按实际记录：不套旧红轮的3根，也不假定失败 worker 重建只能产生2根；不得清理未知/旧保护目录或追加手动停服务。默认 cleanup 的旧真实验证保持原件，本轮不冒充重验。

完整结果输出在 `b4-e2e-real-fixed-first/results.json` / `results.xml` / `artifacts/**`，原日志与收据在 `b4-root/full-e2e-real-fixed-first.log` / `*-command.json`。本方只在 own P 目录新 MD/JSON 汇总真实全部 case/spec/attempt/retry/failure、完整 trace/CRC/EOCD、资源关闭及前后身份。原单轮进程按原配置完成；若有首败，完整留证并停止后续，不能改源/trial重跑。门禁只有实际完整通过才可由 CTRL 关闭，原152/1首败不改写。

当前 PREP READY / 所有文件停写，等待用户新前端、第六浏览器结束、CTRL 真实 release 与明确执行授权。
