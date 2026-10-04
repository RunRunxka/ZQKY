# B6 匿名教学质量准备包

2026-10-04：15匿名病例已在一个新TEMP内完整运行真实API与候选应用；结构技术通过，**teacher_review_pending、live_run待输入、RAG-REL OPEN**。本包属于G3关闭后的B6-base-v1，后续SourcePanel产品修复及新构建须另作来源绑定，不把本包写成新构建重跑。

阅读顺序： [结果](RESULT-v1.md) → [手写规则](EXPECTED-RULES.md) → [8维量规](RUBRIC.md) → [15例目录](runs/offline-third/quality-cases/) → [可填CSV](feedback-offline-third.csv) / [可填MD](feedback-offline-third.md)。汇总和来源SHA见 [RESULT-v1.json](RESULT-v1.json)、[逐例结果](RESULTS-offline-third-v1.json)。每例的最终链记录为 `case-bound-v3.json`；较早部分 `case-bound-v2.json` 保留作为失败后验原件，不能拼成全15成功。

## 教师怎样评审

每例先读expected.json和student-state-table.json，再核input-frozen.json中的匿名modelPayload、wire.json与candidate.json；用selected-fields.json、original-lesson.json、applied-result.json比较选择及保持。case-bound-v3.json列全固定修订、SQL行、Blob及文件SHA，不需读取正式学生库。所有名单为隔离自写匿名数据，教材与题为自写fixture；未复制正式档案、原教材目录或真实草稿。

先在量规标记硬失败和原文位置，再填写8维0～3、修改建议及真人结论。当前CSV的15行评审人、日期、各分数与结论均留空，不将离线手写回复当真实AI质量。C03/C04/C15重叠计数不可相加；C07同学生只明确第二人次；零分母null；综合题错因待核实；历史班名缺失不补当前名。

C10正例、C11窄边界、C12范围外、C13缺请求证明依据分别评价。结构evidence存在不代表支持论断，更不证明真实检索拒答质量；RAG-REL保持OPEN。C09真实题库建议selected0和缺口，只是允许教师继续准备教案，不自动创建或发布正式题。15DOCX为现有模板和buildDocx产生的固定正文结构材料，文件SHA清单见 [DOCX-MANIFEST](exports/offline-third/DOCX-MANIFEST.json)；本路未渲染Word/WPS，也未保存PDF，实际四样本排版与PDF由导出lane另验。

## 复现工具

所有命令从仓库根执行，runner自动建立新的 `zqky-b5-b6-quality-*` OS TEMP，env=test/PYTHONUTF8在main导入前，Settings.credentials_file=None，数据保留。只用实际API的进程内TestClient，不启动TCP；只有上游HTTP transport替身，不替换生产聚合、source reader、model resolver或候选应用。

现有case-specs.json已在运行前冻结，不重新用实际结果生成expected。需要新的完整复现时使用**新的label**，输出不能覆盖：

```powershell
apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G3-B6-20261004/b6-quality/run_command.py --label offline-review-new -- apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G3-B6-20261004/b6-quality/offline_cases_v3.py
```

DOCX命令用workspace dependency loader返回的bundledNode24，先按documents技能登记本次操作（本批成功marker只执行一次，见docx-marker-first收据），复用原现有模板/exporter，不新增设计或改模板。实际本批输入label为offline-third：

```powershell
# $TaskNode 为 workspace dependency loader 返回的 Node 可执行路径
apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G3-B6-20261004/b6-quality/run_command.py --label docx-review-new -- $TaskNode docs/qa/TEACHING-LOOP-G3-B6-20261004/b6-quality/export_cases.mjs offline-review-new
```

只读SQL/Blob/ZIP审查使用finalize_review_v3.py，传同一新完整input label。新label会写自己的case绑定、反馈表和结果，不覆盖已交原件。所有阶段的首败、已关闭命令、PID、实际workload PID、时长、SHA和TEMP都保留；不能把失败版部分病例与下一版拼绿。产品后来改动时由CTRL核受影响源码同源性并重冻，不靠旧build猜新运行。

## Live 范围审查

真人真实模型调用没有获得profile/model/数量/预算输入。`live-scope.template.json`只放非敏感空模板，不能存key。以下命令已实际验证缺范围时按设计exit2拒绝，networkCalls0、mainImported=false、formalEnvRead=false：

```powershell
apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G3-B6-20261004/b6-quality/review_tool.py --scope docs/qa/TEACHING-LOOP-G3-B6-20261004/b6-quality/live-scope.template.json
```

填写明确modelProfileId、modelId、caseIds/sampleCount及正token或费用上限后，本工具只返回范围可供CTRL审查，不直接执行调用。CTRL应沿用现有runtime/Provider与匿名白名单，固定真实模型fingerprint、SYSTEM_PROMPT SHA版本、caseHash、时长、实际usage/失败及原输出；缺少usage要记不可得，不能推算成实际用量。不读正式.env猜模型，不切默认模型或下载模型，不另建prompt管道。新真实调用与教师人审各有单独结论，不因本包结构通过自动关闭质量验收。
