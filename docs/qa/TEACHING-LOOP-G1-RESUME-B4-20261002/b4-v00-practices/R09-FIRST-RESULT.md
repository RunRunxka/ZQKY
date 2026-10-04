# B4-R09-DIAG v1 · r09-first 单轮红测

候选 `CANDIDATE-b4-r7-r09-diagnostic.json` SHA `de3a345f48bc16e589ef1dc7b1af84a239aeba03ed0aa6879c3adfee9144d69d`；QA manifest SHA `16ddaba03f799eda19943aa1e7e8d8ec8c7b40937e64f3a9bf9d1c5f633a96b4`。仅执行一次原四例 CollectAll，**1 pass / 3 fail / 0 setup error / 0 skip**，exit 1，4170 ms。完整命令 argv/cwd/env、时间、PID 和 stdout/stderr 均见 `r09-first-receipt.json`；首败 `r09-first-stdout.log` 保持原件，未重试或修改任何执行源/产品。

| 原场景 | 实际结果 | 归因 |
|---|---|---|
| 真实标准 HTTP 确认题及严格固定读取 | 标准 list 仅自己的题；local-user 固定 reader 可读，local reader 404；恢复标准服务后 foreign 单题 GET 实际 200 | 前面归属断言通过，最后 GET 边界失败，单列新增 R10；非 setup 错误 |
| 真实正式题建议进入 B4 | HTTP 200，但 items=[] / selectedCount=0 / 目标 coverage=0 | R09：Practice local 被用于读取 QBank local-user |
| 手动 fixed rid 保存及审核 | PATCH draft 404/QUESTION_NOT_FOUND | R09；后续 review 未执行，不能宣称审核通过或审核本身已复现 |
| foreign 题 B4 排除/拒绝 | 建议排除，手动保存404/统一信封，草稿修订/items 不变，固定 reader 跨 owner 404 | 通过；严格 owner 边界有效，不可用放宽所有 owner 修复正例 |

四例各自新 standard-main 四库：合计实际 90 HTTP 请求，8 道正式题均经真实 Markdown 上传、两次人工 patch（编辑与 reviewed）、confirm HTTP 创建；其中四道 local-user、四道 r09-other-owner。未直接 insert bank 题、未改任何 owner、foreign service 引用均 finally 复原。名单/T60 recorded 0/T70 ready 真链通过。

16 次四库 integrity=ok，全部 foreign_key_check 为零。题库 question_imports/questions 分别存在 local-user 和 r09-other-owner 真行；教学 analysis_runs/assessments/classes/students/papers/practice_sets/file_assets/workflow_jobs 实际 owner=local。knowledge/textbook 有关表不存在 owner 列时准确登记 absent/null。runtimeOwners 仅取 literal owner_id 属性，analysis/paper/scores/assessment 的 null 是属性名不同，不能解读为无归属：只读源可见 analysis.self.owner、其余 self._owner_id；实际教学库行是 local。完整逐表事实与请求响应见六份 `r09-first-evidence/*.json`。

UTC 2026-10-02 13:55:03.2557343～13:55:07.5625219，Python 子 PID22904 已退出，两输出流已关闭；stdout 5262 bytes / stderr 0 bytes（空文件确实存在），两日志关闭后独占读取通过。新 temp `C:\Users\96022\AppData\Local\Temp\zqky-b4-r09-r09-first-1ba835b02d0d47679592a2ce676f03ee` 保留；四 TestClient context 实际退出，0监听、正式凭证未读，候选与 QA 前后全部 SHA unchanged。

R09 应由 CTRL 分开注入教学 owner 与实际题库 owner，再让三个题库读取点使用后者，严格 FixedQuestionReader 和所有旧记录不改。新增 R10 GET 当前仅检查 record None 而未判 owner；PATCH/DELETE 静态同类疑点另准备窄诊断，未把静态发现计为已执行失败。这里是诊断报告，尚未修复验收；B4 不关闭。
