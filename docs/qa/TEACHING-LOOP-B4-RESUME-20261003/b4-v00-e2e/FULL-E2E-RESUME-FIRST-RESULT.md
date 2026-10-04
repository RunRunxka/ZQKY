原完整 24 个 spec／153 条用例单轮通过：153 pass，0 fail／retry／skip／flaky，CLI 与外层退出码均为 0，外层 371554.846ms。不是重复试跑；昨天两轮原首败及今日 R14 首败全部保留。

冻结候选 r21 SHA256：e558dfbf4af33790328c7c036edfee0aa38c1371da5cb65f6ac8c448ba7c4d39。前后独立审计 source879／QA53／contract5／build2007／历史3043／今日旧证据191 均零漂移；next-env、构建身份及现场 branch/HEAD 均匹配。与昨天两份原全量结果按文件、标题、suite 比较，153 条集合完全一致。

实际命令、环境、时间、PID、完整合并输出见 [command](../b4-root/full-e2e-resume-first-command.json) 和 [log](../b4-root/full-e2e-resume-first.log)。调用现有 Node24.19.0、原 Playwright CLI 与外部配置，workers1、无 webServer；未使用 filter、list、subset、retry、repeat 或放宽预算。显式 KEEP_TEST_DATA=1、UTF8、msedge。冻结配置实际控制变量是 ZQKY_B4_QA_RUN=resume-first，任务要求的 ZQKY_B4_E2E_RUN 同时设置相同值，未修改配置。

双标签原目标 case 实际 passed／20624ms：原顺序主体在两书 ready、跨标签原 noteA/noteB、两书 ID、两页无悬挂锁断言之后才完成。原附件实际 primaryFailure=null、closeFailure=null；两个 helper 均 ready，Continue 计数均 0，observer/timer/listener/resources 清理全真、cleanupErrors=[]。详见 [原附件逐字解码](FULL-E2E-RESUME-FIRST-TARGET-FACTS.json)。本轮该 case 走正常分支；一次真实故障 Continue 已由另一个 R14 固定后两 UI 单轮证明，不混入 153 条计数。原 JSON 无 steps，原 trace 策略 retain-on-failure 且全绿，因此实际 trace ZIP=0，运行时断言个数不可单独计量，不以静态 matcher 数替代。

两个原 API spec 的新 CREATED／RETAINED 根准确配对，自有 PID13884／13688 的 childClosed 与 logClosed 实际为 true；CLI4784、workers11524／7588 及两 API 已退出，8001／8002 空闲，用户前端 PID21816 的创建身份与 argv 保持。原 Windows 关闭方式是对自有 PID taskkill /T /F 后等待子进程与日志流关闭，不称为优雅退出。完整 CLI 与两 API 日志实际独占打开后关闭，记录 SHA，见 [生命周期](FULL-E2E-RESUME-FIRST-LIFECYCLE.json)。

两 API 根下共 8 个 .sqlite3、8 个受管 blob 保留；用标准库 mode=ro&immutable=1 逐库 quick_check 均为 ok、全部连接关闭、无 WAL、读前后字节 SHA 与全样本清单不变。表数分别为每根 knowledge10／question-bank14／teaching40／catalog16；完整逐表数量与所有文件路径、长度、SHA 见 [资源](FULL-E2E-RESUME-FIRST-RESOURCES.json)。离线整理首脚本误用 *.db 匹配，空集合断言失败；随后只纠正只读文件枚举为实际 .sqlite3。此整理错误如实保留于 SUMMARY，未写数据、未重跑业务。

另核三次早期 P 作者类型／lint 自检临时根仍存在、相应子进程已退出与 stdout/stderr 流已关闭，未改原收据；是静态自检资源，不增加本轮用例数。三根仅有 empty-textbooks，静态检查未导入 app.main／初始化 data。补充 3 根加 CTRL 已核 15 根，共今日 18 个不同顶层根，另 1 个嵌套 model 根，详见 [补充根](FULL-E2E-RESUME-FIRST-SUPPLEMENTAL-ROOTS.json)。初次整理误要求静态根有 data 子目录，断言失败；随后仅核实际存在的根，原收据、样本、源码均未改，未重跑检查。未触碰旧 83 根、旧拒删六根或正式数据／凭证；无删除。

本轮完整产物 58 文件：48PNG、4JSON、1DOCX、2PDF、2LOG、1XML；逐文件 SHA 见 [产物清单](FULL-E2E-RESUME-FIRST-ARTIFACTS.json)。不宣称本轮 48PNG 已全部人工看图。[逐用例](FULL-E2E-RESUME-FIRST-CASES.json)、[汇总](FULL-E2E-RESUME-FIRST-SUMMARY.json) 与 [机器结果](FULL-E2E-RESUME-FIRST-RESULT.json) 提供完整计数和证据。此前 R14 两 UI 的 6PNG、两 trace CRC/entry manifest 另册保留，已由 CTRL 实际查看。

P 已停止全部可执行源写入；本结果是当前固定候选的单轮原全集合门禁通过。最终独立来源、文档与 B4 关闭结论交由 CTRL，未将单轮全绿写成恒绿。
