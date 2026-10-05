# R13 后续适用门禁准备（仅只读）

本卡只读核查并记录依赖；没有执行新的门禁、list、子集、业务探针或服务，没有写任何产品/测试/配置/可执行 QA。原 `real-first` 24 spec / 153 case 单轮 152 pass / 1 fail 的全部输出、首败、资源及报告保持原件。

首败后的筛选上下文不能省略：原 `question-bank-real.spec.ts:316` 必须先验证“已入库题目”被选中。接着明确选择 `#qb-filter-subject=math`，再选择 `initialStats.pointId`；`QuestionLibrary` 在学科变化时清空 draft knowledgePointId，因此不得颠倒这两步或沿用上一学科的选择。页面表单“查询”才将 draftFilters 应用为查询，并重置 offset=0；`queryOf` 和 API 客户端同时保留 subjectId 与正式 knowledgePointId。

原后续正确断言仍是匹配该知识点查询 response，`total=1`、questionId 精确等于本次 confirmedQuestionIds[0]、唯一可见题卡为人工编辑后的题干、GET detail 的人工题干和正式知识点一致、最终 providerCalls=1 / frozen profile 一致。上述首败后的断言在原红轮未执行，下一轮不能把知识点清空、放宽结果数量、改成只看入库成功消息或删掉筛选链来替代。

最初只读到的 **r13 首败时源**：`ReviewWorkspace` 返回 URI 为 `/question-bank[?returnPracticeSetId=编码值]#library`；`QuestionBankWorkspace` 的 hash 处理只在 mount effect 执行。这是首败时实现边界的静态观察，没有新增运行证实机制。随后 CTRL 在 F red POST 闭合后完成 r16 修复，本卡 JSON 的后一次 SHA 捕获已如实显示 3 个所读产品文件相对 r13 改变，属于声明修复，并非原单轮 post 漂移。

收到 r16 通知后再只读核：返回动作改用显式 `tab=library` 查询且保留编码后的练习返回参数；薄路由校验 requestedTab，workspace 初始化及后续 effect 响应 requestedTab，无查询时兼容 legacy hashchange；QuestionLibrary 同步变化的 generation 意图，筛选逻辑仍为先数学再正式知识点、显式查询。此处不声称新运行通过；作者 74 pass 和 F 修后 1 pass / 1 QA 环境错误为 CTRL 提供的他方结果。当前等待仅 dialog polyfill 适配后的 r17 新冻结、check/build、用户新前端及正式门禁放行，不能用原 r13 身份启动下一轮。

完整聊天回归来自 `tests/integration/chat-live.spec.ts`（三协议 + 停止 + 长回答 + 模型配置，共静态 6 场景）及 `chat-reasoning.spec.ts`（三协议推理 + 正文公式 + 继续推理 + 20000/50000 字符两性能场景 + 推理滚动，共静态 8 场景）。共 14 是现有源码循环展开预期，未来仍必须用实际 reporter collection/result 核实，不援引旧批次 14 pass。

`b4-chat.external.config.ts` 继承原完整 integration 集合和 workers=1 / fullyParallel=false / 45000ms / expect10000ms / 5174 / channel / retain-on-failure，只去掉 webServer 并指定本批输出。不使用 `scripts/test-chat.mjs`：它会重新构建 `.next-test`，原配置还会启动 5174，与用户持有的新前端生命周期冲突。两个 performance 场景源内原有 timeout 也保持，不加 CLI 放宽或子集。

stream 准备要求：CTRL 单独拥有 8001/8002；在任何 `app.main` 间接导入前设置全新 OS temp 的 data 根、test、UTF8、空教材、Qdrant16333、embedding9，并实际断言 Settings.from_env 的 credentials_file=None。原 fixture 使用注入的 model repository、新临时模型配置及无 env_path 的内存 `SecretStore()`，只放 synthetic key，不读正式凭证。新 `stream_backend_keep.py` 仅拦截原 fixture 精确 `TemporaryDirectory(prefix='zqky-chat-test-')`，将其嵌套在新 owned outer 根并登记保留；三个协议/HTTP/SSE实现不变。

该 keep wrapper **本身没有 stopfile 监控**。CTRL 任务卡已明确外层内联程序将此次 uvicorn.run 适配为相同 app/host/port/log_level 的 uvicorn.Server，并监控本轮独有 stopfile 置 should_exit。启动前保存精确 argv/env/新根/创建时间/PID；退出须让原 fixture finally 中 server.shutdown 与 temporary.cleanup 实际执行、nested 模型样本保留，再确认自然 child exit、日志/管道闭合和两个端口实际空。若启动或 finally 未完成，按实际失败报告，不能补造关闭标志，也不杀未知进程。

顺序等待：R13 red POST → CTRL 最小修复和自检 → 新稳定候选及 check/build → 用户新前端 PID/BUILD 身份 → 适用的独立 FE/browser/mobile 复验 → 新未用 label 原全 153 单轮 → 其自有后端完全释放 → 单独放行原全 14 聊天。未来不能沿用 PID3820 或 build `ST2AWsfwxRYxFKZb_qsip` 作为修复候选身份。`real-first` 首败/样本/输出永不覆盖；新 E2E run/label 由 CTRL 派发。

准确聊天 CLI 模板仍为完整无 spec 参数：

```powershell
$env:ZQKY_B4_CHAT_RUN='first'
$env:ZQKY_KEEP_TEST_DATA='1'
& 'apps/api/.venv/Scripts/python.exe' 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-root/run_check.py' --label full-chat-first --candidate '<CTRL 最新修复候选实际路径>' -- 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/@playwright/test/cli.js' test --config 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-chat.external.config.ts'
```

模板不构成放行。当前 `b4-chat-first` 和 `full-chat-first-command.json` 未存在，后续执行前再核不可覆盖；所有源码/QA/构建身份用最终新 freeze，不能套旧 878/43/5 数字冒充最新证据。资源、完整 reporter JSON/trace/首败和隔离 stdout/stderr 必须按单轮实际留证，受控流式通过不能宣称真实供应商教学质量。

当前 PREP READY，报告已完成并停写；未启动 stream、未执行任何后续检查，等待 CTRL 正式任务卡。
