# B4-CHAT-20261003 v1.2 · 原14聊天单轮门禁

负责人 CTRL（服务/生命周期/运行/记录），独立执行结果核查 P，最终来源与文档核查 A。仅在 r20 冻结、source/QA停止写入、静态检查与身份复核通过后实际放行；本卡准备不是已执行结果。

使用原 `tests/integration/chat-live.spec.ts` 6例和 `chat-reasoning.spec.ts` 8例，以及原 `tests/fixtures/stream_backend.py`，不改场景、期望、45000ms全局、10000ms expect、workers=1、fullyParallel=false、channel=msedge、默认retry=0/repeat=1。新外部配置只关闭 webServer 并改今日输出；不得调用默认test:chat自起5174或build。当前用户持有5174 PID21816/r17构建保持，只读核服务就绪与代理8001。

CTRL用新 `b4-root/stream_service.py --label chat-first --candidate docs/qa/TEACHING-LOOP-B4-RESUME-20261003/CANDIDATE-r20.json` 启动自有原stream fixture，先确认8001/8002空闲、再在Settings/app导入前设置fresh OS根、ZQKY_ENV=test、UTF8、空教材、16333/embedding9、credentials=None。原fixture与keep wrapper签名绑定，新outer/nested样本保留、真实PID/argv/创建时间/端口/health/模型三协议就绪核验，front无生命周期操作。

唯一原14单轮命令经今日run_check.py保留merged UTF8日志/exit/PID/ms/candidateSHA/新OS根：

`C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe node_modules/@playwright/test/cli.js test --config docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-chat.external.config.ts`

配置默认resume-first，输出 `b4-chat-resume-first/results.json`。实际前后使用candidate audit分别登记，不以预期数量代替JSON实际attempt/pass/fail/skip/retry计数。首次失败即保留完整trace/日志/JSON，不重跑找绿；发现修复需求须声明窄范围、候选变更和原门禁再次完整单轮，旧失败不覆盖。独立检查原spec两份SHA/场景枚举、config有效timeout/workers/retry、结果计数与log实际退出。

完成后CTRL核自己的PID/创建时间/argv与stopFile绝对路径位于实际新outer根，以自有stopfile请求uvicorn优雅结束；原fixture finally `server.shutdown()` 和保留cleanup实际返回才写收据，等待进程自然退出/日志独占关闭/8001和8002释放。不能虚写server_close（原fixture没有该调用）；不能操作用户前端或未知PID，不删样本。新收据/报告/命令/资源/首败与CURRENT_STATUS立即同步。

范围止B4，不Git写/远端/部署/B5/T90。具体policy拒绝不重试或绕过。

执行必须经今日run_check.py：三external config真实run/绝对输出目录在Popen前核唯一；已有输出只拒绝，不删除、不换label覆盖。异常仅等待/必要结束该次自有Popen句柄并关闭stdout/log，后续CTRL另核spec自有descendants/API端口，未实核不能声称全部释放。
