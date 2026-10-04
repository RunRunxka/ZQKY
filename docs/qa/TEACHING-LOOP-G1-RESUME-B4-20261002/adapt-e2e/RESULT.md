# G1R-E2E-ADAPT v1 · ready / 停写

负责人 `/root/g1_resume_e2e`，2026-10-02。只修改 `tests/e2e/assessments.spec.ts`、`tests/e2e/question-bank-real.spec.ts` 及本目录。测试资源适配已自检；真实浏览器与完整 E2E 由 CTRL 执行，本任务没有运行或替代这些门禁。

## 实际改动

两份 spec 都增加明确 `ZQKY_KEEP_TEST_DATA=1` opt-in。创建本轮 `mkdtemp` 根时打印 `[ZQKY_TEST_DATA_CREATED]` JSON；正常收尾先停止自己的子进程，等待 spawn 时登记的 `close` Promise，再结束并等待日志流 `close`。两个输出 pipe 使用 `{end:false}`，避免 stdout 或 stderr 先结束时提前关闭共同日志。已经退出的子进程不再使用原 PID 调用 taskkill。

关闭完成后，沿用系统 temp 内路径及本 spec 前缀检查。opt-in 打印 `[ZQKY_TEST_DATA_RETAINED]` JSON，记录 spec、完整 tmpRoot/dataDir/apiLog、PID 与关闭状态，保留目录及 api.log；未设置标志时仍执行既有最多 6 次清理重试，只处理本轮自身新建根。关闭失败保留目录并明确告警，不在仍有句柄时尝试删除。没有增加 API 响应替身、改业务断言或改变默认测试集合。

开工原字节保存为 [assessments.before.ts](assessments.before.ts) 和 [question-bank-real.before.ts](question-bank-real.before.ts)。TypeScript AST 对比确认 4 个 assessments 与 2 个 question-bank-real 业务用例的名称和完整调用/回调逐字一致（仅统一比较 CRLF/LF）；除 startBackend/stopBackend 外，所有既有函数全文一致。新 SHA 收据见 [resource-receipts.json](resource-receipts.json)。

| 文件 | 开工 SHA256 | ready SHA256 |
| --- | --- | --- |
| assessments.spec.ts | `8abb8f4adcc3c9f9c28fa9ec0f09a88fdca906a73bd098d9c859a8260642affc` | `62a1c32ff1b1a869375cda0ae40c79ebebe8f026bc268b8defb520e037eee913` |
| question-bank-real.spec.ts | `34dedc6f6daf6eb944c69937707bbe30db89a51e76a946812a0bb0ba0e8f6137` | `6308d92fce1364a33cafb2ec6412c15026438da3d83275b469e039fd4934fa38` |

## 单次命令与结果

所有命令均从 `H:\备份xuexi\智启课源` 执行。日志与命令收据保留原轮次，不合并重复轮计数。

| 完整命令 | 单轮结果 | 原件 |
| --- | --- | --- |
| `node docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/adapt-e2e/resource-harness.mjs` 第一次 | exit 1；夹具前置等待尾部 EOF 超时，真实 afterAll 未开始，未执行资源用例或清理 | [日志](resource-first.log)、[命令](resource-first-command.json)、[首轮脚本](resource-first-source.mjs)、[首轮根](created-roots-first.json) |
| 同命令第二次 | **4 passed / 0 failed，exit 0，harness 2145ms** | [日志](resource-second.log)、[命令](resource-second-command.json)、[完整收据](resource-receipts.json) |
| `node node_modules/eslint/bin/eslint.js tests/e2e/assessments.spec.ts tests/e2e/question-bank-real.spec.ts --max-warnings=0` 首轮 | exit 0；未生成本地 stdout/stderr 日志，无耗时记录 | [原命令收据](lint-first-command.json) |
| `node node_modules/typescript/bin/tsc --noEmit --skipLibCheck --target es2022 --module nodenext --moduleResolution nodenext --types node tests/e2e/assessments.spec.ts tests/e2e/question-bank-real.spec.ts` 首轮 | exit 0；未生成本地 stdout/stderr 日志，无耗时记录 | [原命令收据](typecheck-first-command.json) |
| 相同完整 ESLint 命令，证据补录 r2 | exit 0，**1224ms**；stdout/stderr 均为实际捕获的空字符串 / 0 字节 | [完整收据](lint-receipt-r2.json)、[明确空输出日志](lint-receipt-r2.log)、[原始 stdout](lint-receipt-r2-stdout.log)、[原始 stderr](lint-receipt-r2-stderr.log) |
| 相同完整 tsc 命令，证据补录 r2 | exit 0，**611ms**；stdout/stderr 均为实际捕获的空字符串 / 0 字节 | [完整收据](typecheck-receipt-r2.json)、[明确空输出日志](typecheck-receipt-r2.log)、[原始 stdout](typecheck-receipt-r2-stdout.log)、[原始 stderr](typecheck-receipt-r2-stderr.log) |

[resource-harness.mjs](resource-harness.mjs) 编译当前完整 spec，仅替换 Playwright 的注册入口以捕获其真实 afterAll，并通过 QA 虚拟模块注入当前 run 自己创建的无端口 Node 子进程/日志/目录。业务回调不执行，startBackend 不调用。4 项为两个 spec 各一次 keep 与一次未设置标志的默认清理。记录真实 child close、日志 close 与 rm 的事件顺序，检查完整 stdout/stderr 尾部文本已落盘，校验被删路径只能是本 case 新建根，核保留 JSON 的所有字段与实际一致。不是实际 FastAPI/E2E 业务通过数。

首败归因：Node 在 Windows 上使用 stdout/stderr `.end()` 后，子进程仍存活时，父级并未收到期待的 stderr EOF。原等待同步点错误；只将 QA 夹具改为等待实际 `STDERR-TAIL` 字节，再调用真实 afterAll。没有修改业务代码、测试断言或资源实现来让首败消失。首败日志/源码/样本均保留。

独立 audit 发现首轮 `Tee-Object` 在无输出时未创建 `lint-first.log` / `typecheck-first.log`，此前本报告的两处日志链接不准确。本次保留原 command.json，删除无实物链接并明确首轮输出/耗时证据缺失；没有补造或回填首轮日志。CTRL 授权后重复相同两条窄检查，用重定向进程读回真实 stdout/stderr、耗时和 exit，保存为上述 r2 收据。两次检查各自计数，不并入资源验证 4 项、业务 E2E 或已有全量门禁。补录只写本报告及新 JSON/log，未写两份 spec 或任何冻结 .mjs/.ts 文件。

## 资源状态与未执行

本任务没有启动或停止用户的 5174，也没有启动 8001、导入 Python app.main、打开浏览器或读取正式 .env/库/凭证。4 项使用的自身 Node 子进程和日志句柄全部关闭；[最终自有进程核验](resources-final.json) 无匹配残留子进程。

保留本次新根：`C:\Users\96022\AppData\Local\Temp\zqky-f20i-FjNPWH`、`C:\Users\96022\AppData\Local\Temp\zqky-f10-real-lqFxVR`；首败新根 `C:\Users\96022\AppData\Local\Temp\zqky-f20i-Loktne` 保留。两次默认分支只删除各自本轮新根，精确路径、PID、关闭顺序见 [created-roots.json](created-roots.json) 与 resource-receipts。旧六拒删目录、所有未知目录与旧 QA 原件未触及。

未执行完整浏览器/E2E、check/API/build；本次仅测试生命周期适配，不冒称重复执行已有 G1 全量门禁。ready 后停止修改两份候选测试，由 CTRL 冻结及独立核验后执行全量。
