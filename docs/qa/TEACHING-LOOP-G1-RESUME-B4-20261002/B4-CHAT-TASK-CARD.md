# B4-CHAT v1.1 · 原聊天集成完整回归

CTRL 独占8001/8002生命周期，仅在第六B4浏览器/手机视觉与完整原E2E全部结束、原自有教学后端与两个spec后端释放后执行。前端是用户手动启动的新构建，Agent不启动/结束它。B4 main装配及共享导航改变，原两spec共14场景为适用门禁；仍以实际JSON收集数为准，不套历史单轮结果。

启动前用新OS临时根设置DATA_DIR/test/UTF8/Qdrant16333/embedding9/空教材，再间接import main；Settings.from_env在test下credentials_file=None，显式断言。现行stream fixture没有外层数据隔离，所以只经本批stream_backend_keep.py执行，不直接调用默认test:chat（默认会重建.next-test并启动5174）。keep仅拦截原fixture自建zqky-chat-test-目录，使新模型样本嵌套新owned根并保留；三个synthetic协议/实际HTTP与SSE/原场景及断言不改。

CTRL内联启动程序完整argv/env保存到新receipt，先核8001/8002均空。为优雅退出，uvicorn.run仅在此次owned进程替换成同app/host/port/log配置的uvicorn.Server；监控新根stopfile将server.should_exit=true。原fixture finally的上游server.shutdown和temporary.cleanup仍真实执行，keep记录保留。启动/停止时间、实际PID/创建时间/监听/日志、nested模型根/全部自然退出与空监听分别核实；不能用Stop-Process、未知PID或编造closed标志补收口。

外部配置继承playwright.chat.config.ts的完整tests/integration集合、workers=1/fullyParallel=false/45000ms/expect10000/channel/retain-on-failure，只去webServer并改新输出。准确CLI为已有Node24运行项目Playwright `test --config docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-chat.external.config.ts`，不加spec/grep/shard/retries/timeout。外层ZQKY_B4_CHAT_RUN=first；run_check新label full-chat-first保存完整合并输出/argv/exit/elapsed/new outer根，引用最终r17-nav-final候选。

所有实现/QA停写。完整单轮与first failure、trace/截图/JSON全部保留；失败先如实归因和修复，新冻后仅适用复验，不试跑掩盖间歇。运行前后核878产品/45可执行QA/5契约、1150旧QA和next-env原字节；全部自有端口释放，用户5174保留。以下PREP为启动前历史记录；当前已因用户明确要求暂停，stream启动/优雅关闭实际状态见后文，原聊天回归未执行。外层准确新根 `zqky-b4-stream-first-osjh6eaz`、完整argv/env与stopfile适配保存root/stream-api-first.json；仅编译语法检查，main未导入、端口未启动。三个newline转义预备缺陷及首prepared字节保留，修后compile成功。用户新前端PID5172/新buildJi-Jz8X9yY2R_79JOPivD保持，原E2E正独占serial后端，不并行启动stream。

## 暂停状态（2026-10-03）

原完整E2E最新轮已结束152pass/1fail。root按既定隔离启动stream PID23268，sample outer osjh6eaz/nested zqky-chat-test-fhc80vjr，导入main前隔离断言已完成；Playwright原14场景尚未运行，用户随后明确要求先暂停。root只写经身份核实的自有stopfile，session30406自然exit0、originalFixtureFinallyReturned=true、上游finally执行、日志独占关闭、8001/8002释放，user5172保持。[实际资源](b4-root/PAUSE-RESOURCE-CLOSURE.json)。

本卡不授权暂停期间执行。用户恢复后需新stream顶层与nested根、新未使用label/receipt/log/stopfile；不要覆盖或重用本次已结束stream-api-first记录。先核当时8001/8002/用户5174与候选/build，再原完整两spec/14场景单轮；不启动或结束用户前端。当前未执行原因：用户要求暂停；无业务通过/失败计数。
