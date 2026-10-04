# T90-AI v2 · B5R-R01 窄修结果

状态：**已修复、作者完整自检通过、已停写、待独立复验**。不代替独立 B5R-R01 关闭，也不宣称 B5 已关闭。

已先读独立 [STATIC-REVIEW-v1.md](../b5-review/STATIC-REVIEW-v1.md)。修前 11 源与 v1 清单零漂移，[BEFORE-v2.json](BEFORE-v2.json) SHA `23b61554106b8a57e85842d3d4cdccfb495892550789222c55cfd0048f00b148`。v1 RESULT、SOURCE-MANIFEST、全部日志/收据/XML/样本保持原字节。v2 写入仅原私有 preparation.py/privacy.py/service.py/validation.py（validator callsite 获 CTRL 明确窄修授权）及新增私有 test_lesson_generation_privacy_structure.py，没有改共享 DTO/DDL/端口或 BE 应用事务。

自由教学文本仍使用原已知身份阻断：短学号/人员 ID、姓名及明确身份标记保持有效，并补齐“学员ID/学籍号”明确标记。不是删除数字、全局替换个人号、跳过短数字检查或全局豁免别名。`check_text('new:N1',['1'])` 作为自由文本仍会阻断；只有结构化请求中精确服务生成的合法 alias 路径接受该匿名标识。

prepare 使用严格 modelPayload 结构检查：顶层、lesson/process、classSummary/KP/counts、requirements、evidence 全部精确键/类型白名单；P1..Pn、K1..Kn、E/Q/R 和 new:N1..N12 在生成的指定路径校验，统计只接受指定 count 键上的非负整数，总时长只接受 durationMinutes 的合法整数。任何 alias 放入正文/需求/知识点名称/教材题目练习标题及文字，都会重新按自由文本检查。伪 alias、增加个人字段、字符串或 bool 计数都拒绝。

最终 wire 检查会真正序列化再解析 provider body；三协议分别严格核消息数量、角色、块类型和键集合，固定 system 必须与原系统提示全文完全一致。user JSON 采用拒重复键的严格解析、与冻结 modelPayload 深等，再执行上述结构化路径检查。未知 tool/消息/字段、改 system、额外或改变的 user JSON 均不忽略。model ID、reasoning 等配置中的自由字符串继续核已知身份，输出预算检查保持。统计/固定 alias 的 JSON 语法不再被整体字符串扫描错当短学号。

candidate 仍先通过原完整字段/allowed stable IDs/四阶段/分钟/KP与依据别名严格 validator；之后仅在这些已验证路径接受稳定过程 ID、alias 和分钟值，全部建议正文、阶段标题/设计/二次备课、activity/check 继续阻断个人信息。已知短号为1时合法 `minutes=1` 可发布，候选正文 `学号:1` 或移入自由设计的 `P1` 仍拒绝。

最后新完整单轮 [ai-v2-r3-stable-command.json](ai-v2-r3-stable-command.json)：**144 passed = 原81 + 新63，0 failed/errors/skipped，exit0，62043.581ms，PID21516，12源前后 sourceDrift=[]**。新用例覆盖短学号1/2/12×三真实 provider.complete/最终 MockTransport 序列化成功、合法 alias/计数/minutes、自由文本的短号和 alias 正阻断、精确路径/类型/未知结构反例、三协议未知 tool/message/key/改变 system/user/重复 JSON key、候选自由文字及模型配置 ID 正阻断。这里是作者技术测试，不是真实供应商教学质量或独立 oracle。

短身份测试使用一致的公开固定 reader 投影设置 studentNo 和无数字的教学知识点名称，真实 teaching 数据库/ready 报告 lineage、RagV2 封存教材与 JobEngine 发布都保留；它是身份路径边界探针，**不冒称创建了包含这些新 studentNo 的真实报告 API 修订**。所用新无数字教材段落经实际 parser/Blob 封存和生产 selected-evidence 管线核验，没有手写可信证据或替换用户正文。独立验收可另外从新成绩/名单建立短号报告进行完整 oracle。

首败和复验原件均保留：

| label | 单轮结果 | exit / elapsedMs / PID | 归因 |
| --- | --- | --- | --- |
| ai-v2-r1-all | 93 pass / 48 fail / 0 error / 0 skip，141总例 | 1 / 54998.329 / 26700 | 原81全通过。短号1/2的新fixture仍选择旧sample_text中“第1/第2条”真实自由文字，按要求触发阻断，因而相关新测试未进入各自后续断言；完整log/XML/数据库/原文保留。只修新测试选取生产封存的无数字段落，没有放宽产品阻断 |
| ai-v2-r2-structure | 60 pass / 0 fail/error/skip | 0 / 27696.991 / 27104 | 新结构用例窄复验；随后仅补明确学员ID/学籍号标记与短person-ID路径反例 |
| ai-v2-r3-stable | 144 pass / 0 fail/error/skip | 0 / 62043.581 / 21516 | 当前完整新单轮，原81+新63，不拼接绿色结果 |

每轮完整命令/env/PID/source SHA/单轮 JUnit/耗时/日志 SHA/临时根/cleanup 保全在对应 command.json。最终样本根 `C:\Users\96022\AppData\Local\Temp\zqky-b5-ctrl-ai-v2-r3-stable-8xvqzd9u` 保留，runner PID21516已退出，日志、JobEngine、RAG及catalog连接已关闭；没有启停TCP/5174。仍为新OS TEMP先设置ZQKY_DATA_DIR/ZQKY_ENV=test/PYTHONUTF8/PYTHONIOENCODING、Settings.credentials_file=None、空隔离教材配置/Qdrant16333/embedding9，实际内存向量+HTTP MockTransport，不读正式.env/.local-data/凭证/草稿、不连6333或收费模型、不做Git写入。

当前 [MANIFEST-v2.json](MANIFEST-v2.json) 绑定12文件，SHA `1fbca5462ce684059bba6b67a0fbffc0062e28dc632347d5c364aff48acb527f`，记录停写时点、v1原件hash和修前/后变化。共享构造和BE调用端口保持；原 Scene helper 未改，仍供CTRL只读复用。未执行：独立复验、完整工程/浏览器/备份门禁、真实模型/Word/WPS/Qdrant/正式迁移；由CTRL对随后稳定候选另绑定，不以本轮作者测试关闭。
