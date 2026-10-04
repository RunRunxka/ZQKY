# G1R-AUDIT v1.5 · r5 独立审计通过 / G1 停写

负责人 `/root/g1_v00_fe`，2026-10-02。本结果只追加在 `audit/v13/**`；原 `audit/RESULT.md` 的 r1 结论、旧 G1 `v00-fe/**` 及历史首败原件未覆盖。本审计完成静态冻结、原文断言、资源与 ZIP 等效及已完成业务门禁的身份核对。CTRL 已据实际门禁关闭 G1；本 Agent 没有执行浏览器或全量 E2E，也不把审计计作业务执行。

## 稳定候选

当前 r5 manifest SHA256 为 `04fd4a41f1f883edc81917aba5ebd8dd9e00da7b0f73428a11b3c81f75e98a9f`。冻结脚本实际 exit0：826 项源码、24 项可执行 QA、815 项保护旧证据、1979 项既有构建文件均零漂移；`next-env.d.ts` 与原字节一致。现场 `main@6aeb57280f6a7e0d7391cad4d150745479ea58ec`；BUILD_ID `gIyYdxBPz-86QUIMw_JX2`；实际构建 `/api/v1/:path*` 继续代理 `http://127.0.0.1:8001/api/v1/:path*`。见 [冻结结果](freeze-frozen-r5.json)、[日志](freeze-frozen-r5.log)、[完整命令收据](freeze-command-frozen-r5.json)。

r5 对 r4 的 826 共同源码与 QA 集合均相同，只改变登记的 `audit/v13/verify_business.mjs` 计数归属。独立浏览器实际执行候选为 r2；r2 至 r5 的共同 826 项源码和共同 22 项可执行 QA 全部同 SHA，浏览器 spec/config、全量 E2E config、原代理、构建及测试 runtime 同身份。r3 相对 r2 新增两个当时未执行的审计源已明确登记；不能称 r2 的全部新 QA 已覆盖。完整逐项集合和证据 SHA 见 [已完成门禁与 r5 绑定](completed-gates-binding-r5.json)、[r2→r3 覆盖记录](r2-r3-coverage-audit.json)。

## 业务原文与真实门禁

冻结后的业务 oracle 实际 exit0，验证 browser 原源到现源只有授权的三个相邻初始操作重排：先选择免考、填写人次 3，再取消另一学生勾选。按这三步重建后整个文件逐字一致；两个测试名及 **87 个完整 expect 调用原文**全部相同。AST 归属为第一 callback 51、R08 callback 35、模块级 `screenshotLayout` helper 1，总 87；R08 关联断言 36 = callback 35 + helper 1。trace、timeout、use 与配置保持原样。见 [业务结果](business-frozen-r5.json)、[日志](business-frozen-r5.log)、[命令](business-command-frozen-r5.json)。

下列业务结果由 CTRL / 独立浏览器 Agent 真实执行，本 Agent 只核其完成收据、实际 JSON、文件 SHA 和共同候选身份；没有重跑、合并重试或以收集代替执行。

| 实际执行 | 实际候选 / 单轮结果 | 耗时 / 身份证据 |
| --- | --- | --- |
| 独立真实浏览器 second | r2；2 passed，0 skipped/failed/flaky，exit0 | JSON 7471.345ms；[命令](../../v00-browser/browser-second-command.json)、[结果](../../v00-browser/browser-results-second.json) |
| 完整原 E2E 集合 | r4；153 passed，0 skipped/failed/flaky，exit0 | 命令 366939ms，JSON 366186.744ms；[命令](../../root/full-e2e-first-command.json)、[结果](../../full-e2e-results.json) |

153 个实际 ID、file、line、title、project 与原始收集集合逐项相同；每项只有一个 passed 结果。两项独立业务为真实名单新增/导入/转班及勾选与人次保留、成绩映射/编辑保护到新确认矩阵，以及真实 DOCX OMML 全参数/分隔符校对确认、三视口/键盘/实际 reduced-motion。r5 的无关审计计数修正没有改变这些已执行业务，因此绑定其共同源身份，不声称这些业务重新在 r5 执行。

现有 Node24.19.0 仅用于 Playwright runner：`C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe`，实体 SHA `3602f2bb1a10f2cbab4c36886218a33c1ab3db87290e73b033c46c77147d0237`。`NODE_OPTIONS=--no-experimental-webstorage`；安装的 Playwright 1.58.2、安装包和 merge 函数未变。用户 5174 前端 PID6836 / Node26.2.0 保持原样。见 [runtime 收据](../../root/test-runtime.json) 和身份绑定结果；该原始 runtime 收据的 reason 在当时仍写验证 pending，最终独立全 entry 验证已完成，原收据未回写。

## ZIP 与资源

独立 Python stdlib oracle 未调用 Playwright/产品：相同 payload、两源 ZIP、安装 merge 函数下，Node24 的 merged ZIP **46 项、42 项按原规则跳过**，逆序 source 优先、trace 重命名、顺序、每项完整解压字节 SHA、CRC32、长度、central/EOCD 全部一致。Node26 同输入的 bounded probe exit2/20120ms，partial ZIP 无 central/EOCD；Node24 exit0/190ms 完整。结论限定于此安装库和输入的收尾链，不推广为所有 Node26 故障。独立 oracle prepared exit0/355ms、冻结 r3 单轮 exit0/372ms，源与输入至 r5 未变，未作无必要重跑。见 [46 项独立结果](zip-equivalence-frozen-r3.json)、[命令](zip-command-frozen-r3.json)、[日志](zip-frozen-r3.log)，原作者完整命令/输入收据保留于 [trace-diag](../../adapt-e2e/trace-diag/RESULT.md)。

second 的两份实际 trace 与 CTRL 完整 CRC/entry 收据的实体 SHA 和长度逐一一致：第一 trace 242 项、5418717 bytes、SHA `278370d089463df75bb3a9a622a26063d076ad4f21e1df455cbf43661e4227fd`；R08 trace 95 项、1564818 bytes、SHA `9667c38d5cdb8e6b0cc67b9fa6fe7021127beb850f510435d9a003ea415bd945`。嵌入测试源 SHA 均为当前 browser `5ebdc2d436f01ff5133f1e5f83bf2a7db75d7d2d4de27b2b27ecaf836e5c1a51`。本 Agent 对实际 second trace 核实体 SHA/bytes 与 CTRL 已解压全项收据，未另行解压重算；上述独立全内容 oracle 是受控 merged ZIP 的 46 项。CTRL 四 DB 收据完整性均 ok、外键问题 0、APIStopped=true；本 Agent 未新开 DB。见 [CTRL 原收据](../../root/second-database-trace-validation.json)、[本次绑定](completed-gates-binding-r5.json)。

r1 资源审计原件继续有效：两份完整 spec 的 6 业务 callback、19 非生命周期函数、58 顶层非生命周期语句原样；真实 afterAll harness 的 keep/default 四分支单轮 **4 passed / exit0 / 2145ms**，child-close → log-close → 自有根处理，完整 stdout/stderr 尾部落盘、默认只删除自身新根。该计数仅资源探针；本 Agent 静态核收据而未重跑 harness。四分支证据和 no-webServer 全量配置见 [原 r1 RESULT](../RESULT.md)、[配置资源审计](../config-resource-audit.json)。

## 适用性与单次审计命令

本轮无需额外 stream 集成：G1 13 项产品修改与保守聊天前端 87 文件 / API import 19 文件闭包无交集，实际 ChatService/SSE/Provider/共享 main.py 装配不变；完整 153 E2E 的现有聊天 UI 用例实际执行。额外 `test:chat` 未执行，原因是本轮无依赖影响；不把其写成通过。详见 [CHAT-APPLICABILITY.md](../CHAT-APPLICABILITY.md)。产品/build/check/API 身份不因无关 QA oracle 修正变化，没有重跑这些未受影响门禁。

以下均为本 Agent 已结束的只读静态进程，计数是审计范围，不合并为业务 passed 数。

| 完整命令 / 执行输入 | 单轮 exit / 耗时 | 范围与实物 |
| --- | --- | --- |
| `apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/audit/v13/verify_frozen.py frozen-r5 CANDIDATE-g1-resume-r5.json` | 0 / 743ms | 826 + 24 + 815 + 1979；[收据](freeze-command-frozen-r5.json) |
| `node docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/audit/v13/verify_business.mjs frozen-r5` | 0 / 299ms | 51 + 35 + 1 = 87 原断言；[收据](business-command-frozen-r5.json) |
| `node` stdin 只读元数据绑定（完整真实 inlineSource 已收据） | 0 / 232ms | r2/r4/r5 共同身份、实际 2/153 项、runtime/trace 实体；[收据](completed-gates-binding-command-r5.json)、[日志](completed-gates-binding-r5.log) |

## 首败保全

以下原件均保留，不覆盖、不伪补，不以最后通过掩盖前轮：

- r1 适配报告原先引用不存在的 first 日志，原 first 命令缺 elapsed/streams。发现后原作者只修报告并真实重跑相同 lint（exit0/1224ms）与 tsc（exit0/611ms），物理 stdout/stderr 均 0 bytes；首轮缺失仍明确。见 [独立补录审计](../receipt-supplement-audit.json)。资源 harness 首次 QA EOF 同步超时和 trace observer 首次 getter 错误也保留各自源/收据，不并入成功计数。
- 真实浏览器 first：exit1、2 timeout、0 pass，初始 disabled 操作顺序和收尾 partial trace 均保留。随后只授权三步操作次序调整、现有 runner 改为 Node24；没有关 trace、放宽 timeout、删原断言或换业务实现。
- r2 追加两份尚未执行的审计源遗漏冻结覆盖，立即报告后 r3 扩为 24 QA；共同 826+22 原样，原 r2 manifest 保留。
- 本 Agent r3 业务 oracle exit1/336ms：误将整个模块 87 与第一 callback 51 比较。原 [失败日志](business-frozen-r3.log)、[命令](business-command-frozen-r3.json)、[失败源](verify_business.first-source.txt) 保留。该轮失败之前的三步重建/expect 原文/名称已过，之后配置比较尚未执行，未假称通过。
- r4 oracle exit1/314ms：把 R08 关联 36 当 callback 计数，实际 callback 35 + module helper 1。只读 AST 定位记录于 [COUNT-SCOPE-READONLY-r4.md](COUNT-SCOPE-READONLY-r4.md)；原 [日志](business-frozen-r4.log)、[命令](business-command-frozen-r4.json)、[失败源](verify_business.r4-source.txt) 保留。full E2E 运行期间未改；正式结束后 CTRL 才授权计数归属修正，准备停写/重冻 r5 后用原 oracle 真正复跑成功。没有用未冻结 inline 替代门禁。

全部可执行源保持停写。本任务只新增 MD/JSON/log；未启动/停止任何 app、浏览器、服务、监听或后台进程，没有本 Agent 自建业务数据根，无 Git 写入，未读正式 .env/.local-data/凭证/用户草稿/旧六目录。旧 815 项、原 r1 结果及次序/计数/trace 首败证据保全；业务服务与临时根的最终释放由 CTRL/原执行者负责。本 Agent 至此停止 G1 写入，后续 B4 调查使用另行登记的 PREP 范围。
