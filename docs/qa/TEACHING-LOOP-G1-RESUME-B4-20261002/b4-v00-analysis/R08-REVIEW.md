# B4-R08-STATIC v1 · 独立静态补审

**R08导航静态PASS；全r6 QA身份不成立**。唯一新增spec第168行精确导航await，原业务断言未删除或放宽；晚GET500独立证据仍在，不能用等待适配消账。单独question_owner_id若仅改变题库读取身份、保留教学owner及同一固定输入，不进入T70已验算计算路径。这不是新owner装配或浏览器已通过。

快照 2026-10-02T14:02:13.228423+00:00。r6清单SHA fd24f5d7e7cf6088459f1a3143a38bd947bc8e93d58e63f348212b463ed6ec9e；spec before cb425d1ca424f4e59a10f9362eaa590b8d64172a7f52cf574a434fb2ff461dae、after 66e1c563fa46c83102a84d6761c362bb0a901bcf68e73d0fc91c292f8d436156。该生成快照877产品/5契约相对r6零变化；QA36有spec与seed两项，seed已变f84e424d40dcbc6ed4d03f08116374175072d3b84278fe2a14d6ec713d654ada，所以不能宣称其它35QA全0改。CTRL随后授权新owner-fixed候选中的seed一表达式补审，另卡核查；本R08仅导航断言通过，新元数据报告不属于可执行源。

移除单一新增行后，与real-browser.spec.r6-before.txt全文及LF完全一致。只用TypeScript parse，不导入/执行spec，诊断0。原115个direct expect matcher全部保留，新116；另两个expect.poll（实际图片complete/naturalWidth、模型calls=1）未变，宽口径117→118。新wait限定固定localhost5174、/question-bank/imports/非空ID、本次created.practiceSetId与末尾锚定；后续原page.url().match/not.toBeNull、人工校对/确认、固定oracle/PII/原包/模板/timeout全部保留。没有sleep或扩大timeout，作者原字面URL检查只读，未执行新的URL/业务用例。

原browser-real-second-late-GET500.json SHA ff1d396be0b6ffe3a401a440adf7febf443d4e9ee78581b2c81ecd51278e5c1f：旧trace GET http://127.0.0.1:5174/api/v1/question-imports/29696d7d83354ce4b04ad4de3d2b3d02 于2026-10-02T13:34:04.126Z返回500，21字节Internal Server Error。RESULT-browser-real-second.md:7明确这是null首败之后、context关闭之前的独立HTTP失败，不先定为teardown。结果、命令、stdout/stderr、late JSON原件SHA/大小登记于本JSON，未覆盖。导航wait只能修异步URL读取，不能证明该500消失。

当前QuestionBankService默认owner=local-user（service.py:147），PracticeService教学owner=local（:28/40）。拟议窄修是单独注入实际question_bank_service.owner_id，仅供FixedQuestionReader的三处调用（practice service.py:157/202/262）；未指定question_owner_id时沿教学owner兼容既有直接fixture。FixedQuestionReader仍WHERE q.owner_id=?，不能绕过归属用裸ID读。教学owner继续用于command/repo/analysis.read_ready_report/转换/export/资产身份。

T70在main.py:321–322独立装配；snapshot.py:20–32读归属正确的施测及显式固定score/paper，:58–66从教学映射/转换取lineage并保留教学owner；aggregate.py:7只算冻结participants/items/cells整数矩阵，没有question_owner_id或题库reader。对相同固定输入与上述窄范围，已验数学/主体证据路径无直接变化。未来练习选题集合可改变，旧A通过不能自动证明新owner路径；未重跑scale或A/P。

实际夹具影响：r6原seed.py:125初始读时插题owner_id=local，main改读local-user后，初始题会从suggestions/固定revision读取消失。新授权seed应改用实际question_bank_service.owner_id，仅对齐来源身份，保留T30/T60/全部oracle及旧失败。生成期间seed另发生owner表达式变化，来源SHA已分开记录；新owner-fixed卡将另审，本R08不将其混入导航PASS。本审阅不改seed。CTRL报告的R10标准foreign GET200与fixed reader404及后续GET/PATCH/DELETE guards属于独立产品修复，不被R08导航wait覆盖或证明。

只写本MD/JSON后停写。未执行任何新测试、seed/browser/Appmain/服务/HTTP/scale、端口/进程查询或temp/用户data操作。完成两次TypeScript纯解析；报告序列化首命令SyntaxError在任何导入/写入前退出，原工具错误保留，修正后生成报告，不归业务失败。
