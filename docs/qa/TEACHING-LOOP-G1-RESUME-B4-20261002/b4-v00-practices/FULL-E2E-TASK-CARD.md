# B4-FULL-E2E v1.1 · 准备任务卡

负责人：`/root/g1_resume_e2e`。本卡仅准备 MD；**尚未执行完整原 tests/e2e，也未运行其 list/子集/窄测试或修改任何可执行源。** R11 原组件 QA 单轮修复复验已实际 2 pass；它不替代浏览器或全量 E2E。当前等待 r12 UI 修复产品的新 check/build、用户新前端 PID/BUILD 身份、第五轮完整独立 browser 118 与 mobile 验收、CTRL 自有 8001 释放证据，以及最终新候选与正式放行。

## 授权范围与执行前条件

- 只执行完整原 `tests/e2e` 集合一次；不 grep/shard/指定单 spec/subset、不改 retries/timeout/workers/断言/业务成功口径，不在失败后做 trial 重跑。
- 使用既有无 webServer 的 `b4-e2e.external.config.ts`，继承原 fullyParallel=false/workers=1/global timeout=45000/expect timeout=10000/use/baseURL=5174/channel/trace 与原用例内既定配置。仅本批输出 reporter/outputDir 与外部前端生命周期已由该配置登记。
- CTRL 先优雅关闭自己的 B4 独立 backend8001，并给实际子进程/日志关闭及空监听证据；放行后执行者再只读确认 8001 空。两个原 spec 的 8001 由各自既有 before/after 生命周期管理，workers=1，不与独立 browser/chat 后端并行。
- 等待 CTRL 的 r12 UI 新 check/build 成功及完整源/构建身份记录；由用户持有、启动新的 5174 前端，执行者不启动、停止、重启或替换前端。执行前只读核最新用户前端 PID、实际 BUILD_ID 与最终冻结产品一致。旧 PID 24248、旧 build `v3NL9Nd4Zve30UcCepg0R` 仅为历史事实，不能沿用于本轮或作为 r12 的执行前满足条件；旧 G1 的顶层 BUILD-IDENTITY 也不替代 B4 身份。
- 第五轮完整独立 browser 118 与 mobile 验收须在上述新前端/新构建完成，并由 CTRL 提供真实单轮结果、最新身份、关闭证据和验收记录；不以旧第四轮通过或本次 R11 组件 2 pass 代替。CTRL 释放本轮自有 8001 后才允许全量原 spec 自管后端；释放前、任一依赖未完成或尚无正式放行时均不执行。
- 所有冻结产品/测试/执行 QA/契约前后核 SHA；Node runtime 为既有 `C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe`（预期 Node24，正式执行时读实际版本留证），不切换用户前端 runtime、不升级依赖/锁。
- `ZQKY_B4_QA_RUN=real-first` 是本次唯一输出 run；`b4-e2e-real-first` 目录、预定 runner receipt/log 不得已存在，拒绝覆盖任一旧首败。外层 `ZQKY_KEEP_TEST_DATA=1` 明确 opt-in；仍保留旧保护目录与全部新样本。

## 预定完整命令

在仓库根目录，收到 CTRL 最终候选路径后填入该实际路径；候选 SHA 先独立校验，不猜测或沿用旧候选。使用已存在 `b4-root/run_check.py`：

```powershell
$env:ZQKY_B4_QA_RUN='real-first'
$env:ZQKY_KEEP_TEST_DATA='1'
& 'H:\备份xuexi\智启课源\apps\api\.venv\Scripts\python.exe' 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-root/run_check.py' --label full-e2e-real-first --candidate '<CTRL最终候选路径>' -- 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/@playwright/test/cli.js' test --config 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-e2e.external.config.ts'
```

命令没有 spec 参数或改变原测试配置的 CLI 开关。label 若 CTRL 指定另一全新值，先登记该具体值；不复用旧 label。

既有 wrapper 在间接 main 前建立新的 OS outer temp、空教材根，外层 test/UTF8/new DATA_DIR/QDRANT 16333/EMBEDDING 127.0.0.1:9/PYTHONPATH/KEEP=1；test Settings credentials_file=None。它生成完整 argv/cwd/隔离 env/新 temp/PID/exit/elapsed/candidate hash 收据，保留完整日志。wrapper 实际将 stderr 合入 stdout 的有序日志，本轮明确记录该合流事实，不能伪称单独 stderr 文件或 stderr=空。`ZQKY_B4_QA_RUN` 从外层继承，补充执行证据显式登记该值，不能只引用 wrapper 的 isolated env 子集。wrapper 原有只读 Git branch/HEAD 记录按 CTRL 授权使用，不新增 Git 操作。

执行日志与原始收据：`b4-root/full-e2e-real-first.log`、`full-e2e-real-first-command.json`。完整 reporter JSON/JUnit/artifacts：`b4-e2e-real-first/results.json`、`results.xml`、`artifacts/**`。执行者只在自己 `b4-v00-practices` 新 MD/JSON 汇总实际身份、单轮结果、生命周期和资源；不修改 runner/config/spec/executable QA。

## 两 spec 保留分支的实际验收

开工只读确认以下冻结源；此处是准备期 observed hash，正式执行须纳入 CTRL 最终候选重新核对：

| 文件 | 准备期 SHA256 |
| --- | --- |
| `b4-root/run_check.py` | `4f38874eaf4423b6ee7f05ef8488af53ff060ea87ac8e28bfbe08be03a9fb521` |
| `b4-e2e.external.config.ts` | `a944ea09f10064320b73fd53f5ccbd9c0abdb156077b8448ff3b06210154fc0c` |
| `playwright.config.ts` | `dd32a2826a686f95a13b8b4b12c756af3beca26c0bdfe8673cc740485cfa9df0` |
| `tests/e2e/assessments.spec.ts` | `62a1c32ff1b1a869375cda0ae40c79ebebe8f026bc268b8defb520e037eee913` |
| `tests/e2e/question-bank-real.spec.ts` | `6308d92fce1364a33cafb2ec6412c15026438da3d83275b469e039fd4934fa38` |

从本次实际日志逐条提取 `[ZQKY_TEST_DATA_CREATED]`、`[ZQKY_TEST_DATA_RETAINED]`。登记 spec、新 tmpRoot/dataDir/api.log、实际 child PID、childClosed/logClosed。按本次开始标记对应新自有根，不认旧目录或旧关闭收据。关闭标记必须在真实 child close 及日志 stream close 之后；KEEP=1 skip-rm 必须实际发生。

完成后只读核这两个新根存在、api.log 存在且可独占打开/完整读取，捕获实际长度/SHA 与独占读取结果；检查实际后台监听已清空，并以 PID + command/start time 辨认归属，避免将复用 PID 当原进程。若只有 created、未出现 retained 或 close=false，明确记录生命周期未完成，不补造关闭 flag，不清理未知进程/目录。runner 自有 Node 退出、outer temp 与日志写闭合也须留实际证据。

本轮只触发 opt-in 保留分支；默认 cleanup 分支此前真实验证仍保持原件，不在本次冒充重新执行。全量集合内的业务数据、独立 context、本地规则/受控 provider 与实际 API 边界按原测试保留，不以外部 formal 服务代替。

## 单轮结果格式与停止条件

完成一次完整进程后，原始 JSON/JUnit/trace/截图/日志全部保留。遍历 JSON 的 suites/specs/tests/results，列每个原 spec 的实际用例状态及失败 error/首败位置；给本次总数、expected/unexpected/flaky/skipped、实际 attempt/retry、elapsed 与进程 exit，并和 runner 日志的本次 collection 数量对应。原测试列表从最终冻结候选得到，不先套旧 G1 的 153 或把独立 B4 browser 场景并入总数。

完整成功需要实际单轮全集合正确结果、身份前后无漂移、两 spec 的新 retained/关闭/log 证据与空后端端口；若有失败/skip/中断/JSON不完整，准确区分 actual failed、被 serial skip 与未执行，不以静态配置或构建绿替代。不改产品/QA，不调整超时，不自动重跑；向 CTRL 报告原首败和完整实际结果，停写等新的修复或执行卡。

当前状态：**PREP READY，等待 r12 UI 新构建、用户新前端身份、第五轮 full browser 118 + mobile 验收、CTRL 自有 8001 释放、最终冻结与正式全量执行授权；所有全量 E2E 可执行源未改，完整原集合及其 list/子集均未执行。**
