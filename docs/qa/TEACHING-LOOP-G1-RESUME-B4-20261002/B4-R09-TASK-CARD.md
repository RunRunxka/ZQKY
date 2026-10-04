# B4-R09 v1 · 真实题库归属装配修复与独立复验

CTRL 负责产品修复，P 负责独立真实 HTTP 反例；A 只读审查，F 负责浏览器夹具适配与独立浏览器。授权止于 B4，Git、前端启动和正式数据边界沿用当前用户要求。

起点：main@6aeb57280f6a7e0d7391cad4d150745479ea58ec；修前冻结 b4-r7-r09-diagnostic，877 产品/38 可执行 QA/5 契约，SHA de3a345f48bc16e589ef1dc7b1af84a239aeba03ed0aa6879c3adfee9144d69d。P 四例单轮修前诊断先执行，完成并退出后才能改产品；所有首败原件保留。

CTRL 可写范围：apps/api/app/main.py、apps/api/app/services/practices/service.py、apps/api/tests/practices_support.py、apps/api/tests/test_practices_api.py，新增本批说明与权威状态。修复限显式区分教学 owner 与实际题库 owner，主装配从 QuestionBankService 注入，三个固定题读取点一致。既有 FixedQuestionReader 严格 owner 判定、题库默认 owner、历史记录和所有迁移保持原样。HTTP 夹具采用真实主装配 owner；独立负例仍明确拒绝其他归属题。

R09 修前实测：单轮4例1通过/3失败，exit1/4170ms，零setup error。真实local-user题未进入建议且保存404；另一失败为标准单题GET错误返回foreign题200，单列R10。新增R10可写范围：apps/api/app/services/question_bank/service.py的单题get/patch/delete归属闸门，以及新增apps/api/tests/test_question_owner_boundary.py回归。P先用真实foreign题补两项编辑/归档红测，旧四例不动；每项先保留修前行为再修复。题记录不改owner，正式修订不可变约束不放宽。

F 可写范围（收到后续明确放行才改）：本批 b4-v00-browser/seed.py 的正式题 fixture owner；保留修前字节及全部图片来源块、HTTP 资产验证和浏览器原断言。禁止调整 QuestionBankService 实际 owner 或绕过读取鉴权。

r9 实际自检4通过；独立R09四例4通过/4320ms、R10两例2通过/2989ms。全量API1698通过/1规模门控跳过，270.40s，外层exit0/272077.419ms，后验878/40/5零漂移。原P64的首例因probe_support.Scene.question硬写local停止，0通过/1失败/余63未执行；该Scene实际均为标准main。追加P唯一可写表达式改为self.app.state.question_bank_service.owner_id，保留原135测试断言/23定义与全部负例，并新QA清单冻结后原64全验。

第三轮浏览器实际完整1通过，Playwright child exit0/24628ms，后验878/40/5零漂移；外层run.py随后GBK回显Unicode字符失败，outer exit1，原始日志保留。追加F可写范围仅run.py的stdout/stderr显式UTF8编码两行，业务/CLI/收据/断言不变，保留原字节。新冻结后全新种子与第四轮完整browser验证真实outer exit0。CTRL自有第三轮8001/PID25260已优雅退出0；用户5174/PID24248保留。

验收：P 四例正确行为通过，原 P 64 例受影响独立复验；A 只读确认严格鉴权与 T70 聚合路径不受影响。稳定候选重新执行全量 API；前端源码和构建输入若逐 SHA 相同，绑定实际 r5 check/build，不冒称重跑。新种子、真实浏览器完成人工补题确认→选题→审核→双 DOCX/模板→新施测/T60/T70 回流，并实际观察导入 GET 成功；全部原 E2E、聊天集成与资源收口仍必需。

每次结果写单轮实际命令、exit、计数、用时、候选/QA SHA、owner 事实、错误信封、四库完整性及连接/进程/日志关闭。修复者自检、独立验收和最终门禁分别登记，不合并轮次，不将诊断失败视为已修复。
