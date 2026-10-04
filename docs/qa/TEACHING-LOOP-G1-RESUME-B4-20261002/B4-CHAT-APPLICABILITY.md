# B4 聊天回归适用范围

B4修改标准main四库运行时、执行器注册及共享导航；虽未修改聊天SSE/供应商解析代码，本批仍安排既有完整chat-live/chat-reasoning集成。未执行时不能引用旧G1的不适用判断或旧批14通过。

仅新配置继承原Playwright聊天配置与原两spec全部测试/断言/超时，移除webServer，输出新目录；前端仍由用户手动启动，生产构建代理须核实8001。Playwright仅使用已登记Node24，不下载、不改依赖。

本批独占8001与8002，须在教学独立浏览器和全量E2E自有8001均退出后串行执行。根wrapper在任何app.main导入前要求外层全新系统temp的ZQKY_DATA_DIR、env=test、UTF8、16333、embedding9、空教材；执行现有stream_backend.py全部原协议/上游实现，唯一临时目录适配是将其自有模型配置样本保留在本轮根内并登记，不删样本。Settings.credentials_file=None由test配置闸门保证。它不启动前端，不连接未知端口，不替代教学backend。

须记录精确命令/PID/创建时间/数据根/完整stdout与stderr/日志关闭/端口归属与退出。所有未执行或失败如实独立登记，不能把替身流式质量当真实供应商教学质量。
