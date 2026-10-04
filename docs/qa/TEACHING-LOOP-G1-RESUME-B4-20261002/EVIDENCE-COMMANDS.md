# 接续实际命令索引（单轮计数）

开工baseline仅只读盘点：main@6aeb572…，826源与原g1-r2逐字一致，815旧证据另保护，next-env原字节保存，BUILD_ID及1979构建文件登记。没有复跑或改写原check1088/API1599+1skip/规模专项；这些仍绑定原候选。

| 实际执行 | 结果 | 完整命令/日志/身份 |
| --- | --- | --- |
| 两spec afterAll实际资源harness | 单轮4pass/0fail、2145ms；仅资源生命周期，不计业务通过 | adapt-e2e/RESULT.md、resource-second.log/command.json/resource-receipts.json；首轮QA EOF故障保留 |
| 目标ESLint与tsc补录 | 分别exit0/1224ms、exit0/611ms | adapt-e2e/RESULT.md与receipt-r2；真实空stdout/stderr存档，原缺日志如实标记 |
| 独立audit v1.1 | 原业务回调/资源/配置/聊天影响核对通过 | audit/RESULT.md，完整单轮收据及命令；不计浏览器或全E2E |
| 独立浏览器first，Node26 | exit1，0pass/2timedOut，总544943.77ms | v00-browser/browser-first-command.json/browser-first.log/browser-results-first.json；首败、原脚本与两残缺trace保留 |
| 同安装原merge大型同输入诊断 | Node26 exit2/20120ms partial；既有Node24 exit0/190ms完整 | adapt-e2e/trace-diag/RESULT.md与各large-complete-command/receipt/log；纯诊断，不计业务 |
| 原作者标准库ZIP内容核 | exit0/19ms，46完整条目、42原规则重复跳过 | adapt-e2e/trace-diag/artifact-content-verification-first-command.json/log/json |
| 独立标准库ZIP oracle | 46名称/解压SHA/CRC/长度与来源一致；Node26残包被拒 | audit/v13 ZIP收据与实际命令/日志；不重跑诊断 |
| 独立浏览器second，既有Node24 | exit0，2passed/0failed/0skipped/0flaky，7471ms；两用例3345/2484ms | v00-browser/browser-second-command.json/log/results-second.json、SECOND-RESULT.md；实际执行r2，共同业务/config SHA绑定后续扩覆盖清单 |
| CTRL四新库/两实际trace只读核 | 第二次exit0/283ms，4库integrity ok/FK0；242/95条ZIP全CRC读取成功 | root/second-database-trace-command.json/validation.json；第一次glob误用.sqlite而非.sqlite3的QA失败命令原样存first-failure.json |
| r4独立freeze | exit0，826源/24QA/815旧证据/1979构建0漂移 | audit/v13冻结收据；r2漏覆盖两未执行audit源的原件与r3补覆盖保留 |
| 独立业务计数oracle | 两轮QA首败保留，未计通过 | audit/v13：模块87实际为第一callback51+R08 callback35+helper1；full E2E期间不改源，结束后按新冻结复验 |
| 原完整E2E --list | exit0，153用例/24文件，仅收集 | root/full-e2e-collection.log及collection JSON/XML；不是153pass |
| 原完整E2E first（实际完成） | exit0，153passed/0failed/0skipped/0flaky，reporter366186.744ms、命令墙钟366939ms | root/full-e2e-first.log/first-command.json、full-e2e-results.json/XML；r4，外部服务配置无webServer/fallback |

每轮结果分别计数，不合并重复轮次。额外stream聊天不适用，依据audit/CHAT-APPLICABILITY.md的87前端/19后端依赖闭包及13产品改动无交集；全量中原chat UI用例仍执行。没有代理启动Next、停止用户前端、下载/升级依赖或Git写入。
