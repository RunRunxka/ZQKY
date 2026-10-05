# B4-RSRC v1 · 新批资源收据审阅

本记录是 2026-10-02T13:02:27.025927+00:00 的只读收据快照，**不是 B4 全部门禁或最终资源关闭证明**。任务派发时全 API 和 check 正在运行；执行期间 CTRL 与原收据更新了实际终态。当前第二轮 check 仍由 CTRL 收口，不以 PID 当前是否存在证明原子进程退出。

只读本批七个 B4 QA 目录的命令、结果和资源 JSON，以及首败证据文件存在/字节数元数据；提取 86 个收据/结果、42 个新顶层样本根，完整路径、来源字段和 SHA 在 RESOURCE-AUDIT.json。未遍历这些样本根，未打开 DB/实际 data/正式 .env/.local-data；未查 PID/端口、启动测试/服务、操作候选/执行源/权威文档或删除文件。旧六根和未知 temp 未触碰。

## 当前门禁与资源事实

| 范围 | 原实际执行结果 | 进程、日志和资源证据 | 仍未完成 |
| --- | --- | --- | --- |
| A 独立分析 | first exit1 / 0完整场景 / 32 HTTP；second 和 fixed-first 各 exit0 / 8完整场景 / 165 HTTP | 三轮 receipt 的 held-process hasExited=true 与实际 exitCode；新根保留。仅进程内 TestClient，0监听；benchmark 是同步子进程返回，不用当前 PID 代替退出。未声称另做日志独占打开检查。 | B4 总体门禁归 CTRL。 |
| P 独立练习 | first 11pass/1fail/50未执行；diagnostic 51pass/11fail；commit-diagnostic 57pass/7fail；fixed-first 64pass/0fail | 四轮原 processExited=true、stdout/stderrStreamClosed=true；流关闭后日志独占读成功。fixed-first 55资源收据/四库220项完整性核验；backup/restore 在标准 app 退出与数据锁释放后执行。仅进程内 TestClient。所有旧轮/新根保留；不承诺既有 pytest policy 下每个早期 case 根永远存在。 | 不替代真浏览器、正式 Qdrant 或 Word/WPS。 |
| F 独立组件 | types first exit2；FE未执行；types second exit0；FE second exit1/0用例；third 与 fixed-first 各18pass | 各命令实际 exitCode 与 childExited；无 socket、业务 seed、真实 browser。5个新 runner 根保留，只有 empty-textbooks。 | seed/browser/ZIP像素/浏览器四库核验未执行。 |
| 根全 API r2 | exit0；CTRL报1695pass/1skip/279.14s；原命令 PID 13288，结束 2026-10-02T12:53:20.149961+00:00 | complete/exit/finishedAt/logSHA、samplePreserved=true；样本根 C:\Users\96022\AppData\Local\Temp\zqky-b4-full-api-v14-first-icivzla3。只登记原收据，未自行查 PID，也不据此补造逐子PID/日志独占关闭。 | 总控汇总余下门禁。 |
| 根 check first r2 | exit2；tsc 产品 R05：ReviewSession漏prop | 原日志与命令保留；CTRL报 next-env 已精确恢复。新样本根 C:\Users\96022\AppData\Local\Temp\zqky-b4-check-v14-first-rpd47gyq。 | 不标 check 通过。 |
| 根 check second r3 | 首读 running；生成快照时 complete / exit1，PID 11500；结束 2026-10-02T20:59:14.338888+08:00，wall96796.762ms | 新根 C:\Users\96022\AppData\Local\Temp\zqky-b4-check-v14-second-cb2ffw9g；r3 SHA b00532b1e54ef8bfec4b4f5de91729f198adf6e2cff44d1e52a14b5e1144d230；原日志 SHA202972b3c6b299c9fb887cdcf2947a24e4e47bbb998127e85f59d532400e060d。next-env typegen/精确恢复由 CTRL 独占，未执行全源审计。 | 不标 check 通过；失败原因、逐子PID/日志释放与 next-env 收口归 CTRL。 |

作者 T70 各轮 wrapper 根/退出及 T80 十轮自检根/childExited 也逐字段登记于 JSON；作者最终21pass、64pass与 FE14自检只是各自 self-check。T70 resources-final 的 r2 同时写 exitedAtReceipt=true 与 processPresentNow=true，当前 PID 快照不是原进程未退出的证据；P 同样有 CTRL 提醒的 PID 复用，均以原进程等待与收据判定。

用户前端 5174 的最新只读归属事实由 CTRL 提供：无监听，Agent 没有终止用户前端。本审阅不查询或操作它。新 B4 seed、真实浏览器、fullE2E、chat integration 尚未执行，不能登记为“全部释放完成”；也不能从本轮 0 browser contexts 推断后续浏览器门禁完成。

## 首败原件

A 首轮可选404 details被QA过严必填而失败；0/8完整场景，原脚本字节、完整stdout/stderr/JSON与后续第二轮分开。P 首轮真实完整题号反例、只读提取第一次列名错误、完整诊断与提交诊断都保留；产品修复后全64另用新根验证。F 首轮QA类型失败与二轮 No test files found 的0用例原件、两轮原执行源副本均保留，不写成产品通过。根全API首轮1694pass/1fail/1skip及后续9pass适配自检、check首轮exit2也保持独立原件。作者首轮日志仍在。元数据清单见 JSON；0 个本次列名文件未发现（若非零需按清单确认命名，不能冒称缺失内容）。

## 两个新空 temp 清理被拒记录

resources-second.json 记录精确动作 Remove-Item -LiteralPath $resolved -Recurse -Force，目标为 C:\Users\96022\AppData\Local\Temp\zqky-b4-v00-hfjs_jp7 与 C:\Users\96022\AppData\Local\Temp\zqky-b4-v00-650zrqob。自动审批在执行前拒绝整条命令，只返回 blocked by policy，没有给更具体理由；命令未执行、两根未删除，后来观察只含 empty-textbooks。CTRL 重申用户要求保留后未再尝试或换工具绕过。该历史事实原件不改，本审阅无任何清理动作。

动态最终资源、失败的 check 后续处理与 seed/browser/E2E/chat 收尾仍由 CTRL 登记。本任务只写两份资源审阅文件后停写。
