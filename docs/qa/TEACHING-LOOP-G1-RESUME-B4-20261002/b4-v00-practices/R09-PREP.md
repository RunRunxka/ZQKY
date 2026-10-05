# B4-R09-DIAG v1 · 独立窄诊断准备

负责人 P；当前仅准备，未执行 pytest、业务种子、浏览器或监听。CTRL 冻结新 QA 源及完整候选并明确放行后才能运行。FULL-E2E 预备暂缓。产品、既有测试与原 P 四份执行 QA 不改。

只读发现：标准 `main._build_question_bank_runtime` 未覆盖题库 service 默认 `local-user`；`_build_b4_runtime` 的 PracticeService 默认 `local`。PracticeService 的 suggestions、_prepared（保存及审核准备）、_active_refs（审核发布复核）均用 `self.owner_id` 读取题库；FixedQuestionReader 的精确 `q.owner_id=?` 没有降级或宽松匹配。因此这是跨域装配的有界疑点，尚未用运行结果确认缺陷。

作者 `tests.practices_support.seed_api_loop`、独立 P 的 `Scene.question` 与作者 `PracticesScene.question` 均直接 seed `owner_id='local'` 题。原 P 64 项通过是真实结果，但这些题库夹具不覆盖 standard-main 真实上传/人工确认题的 `local-user` 所有权；本轮补充该路径，保留原证据。

新增执行 QA 仅 `test_r09_owner_diag.py`、`run-r09.ps1`。运行器沿用原 P 的完整候选/QA 清单前后逐 SHA 核查、创建并保留新系统 temp、外层 test/UTF8/None 凭证/空教材源/16333/embedding9 隔离、真实子进程退出与两输出流关闭、stdout/stderr 全量及独占读取记录；仅切换新四例、R09 标签和有界 180 秒。可使用 `-CollectAll` 收齐四例，诊断结果不冒充修复验收。固定新 label，拒绝覆盖任何旧收据。

四例每例各自创建全新标准 main 四库与 TestClient（不监听），只复用作者的 `open_api_scene` context，**不调用**会低层插 local bank 题的 `seed_api_loop`。初测原卷是唯一直接业务夹具：实际 T10 渲染 DOCX、受管 AssetStore/FileAssets 登记、PaperRepository 写入固定原卷/正式 KP 并经真实确认闸门。名单、施测、零分 XLSX 导入确认、T70 ready 与 T80 全走真实 HTTP。

R09 正式题完全由真实 `question-imports` Markdown 上传 → 人工明确编辑 type/difficulty/正式 KP（显式 richContent=null）→ 原内容第二次人工 reviewed → confirm HTTP → GET 题目建立。固定 revision id 只读取得，禁止直接插题或改 owner；标准题必须仍是 `local-user`，练习/分析仍是 `local`。

负例使用相同新库、独立 `QuestionBankService(owner_id='r09-other-owner', ...)`，临时替换该 TestClient request 的 service 对象，通过同一 HTTP 上传/编辑/review/confirm 产生确实存在的 foreign 正式题，finally 恢复原标准对象并关闭临时 service。不修改标准对象、题记录或 FixedQuestionReader；标准 GET 与固定 reader 必须严格拒绝该题。此对象注入仅构造负例，不参与正例 suggestions/save/review。

四项原断言：

1. 标准 HTTP 确认题可见、正式 KP/内容准确，严格固定 reader 对 `local-user` 可读，对 `local` 404；foreign 题标准 GET 404。
2. 实际 B4 目标/题型/难度约束内建议选中唯一标准题，selectedCount=1、gaps=[]、固定 rid 一致。
3. 教师手动指定该固定 rid 与完整计分结构，保存 200，再真实审核 reviewed，题面与固定 rid 准确。
4. foreign 题不进入建议，手动保存 404/QUESTION_NOT_FOUND/完整错误信封，草稿修订和 items 不变，固定 reader 严格跨 owner 拒绝。

每例完整 HTTP 请求/响应、两真实确认题、初测事实、运行时 service owner、四库所有表是否存在 owner 列及实际分组行数、integrity/FK 检查、TestClient 实际退出后资源事实均写新 JSON。缺 owner 列记录 null，禁止臆造跨库 owner；记录新临时根并保留。

仅完成静态 Python AST 和 PowerShell AST 解析，未导入 app、未执行四例。静态断言已对照冻结 DTO：AnalysisRunView.reportReady、PracticeRevisionView.items/draftItems，不使用不存在的 state/selections 字段。待 CTRL 新候选 SHA 与执行放行。

若行为反例成立，建议由 CTRL 最小分离 PracticeService 的 teaching owner 与 question owner，main 显式注入实际 QuestionBankService.owner_id，并让三个题库读取点使用该 question owner。严格 reader 与旧所有权记录保持事实。此处是待执行验证的建议，本 Agent 不改产品。
