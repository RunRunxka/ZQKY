# B6 三路任务卡 v1

依赖已满足：ROOT G3-CLOSE-v1，2026-10-04 13:52:47+08:00；先形成 B6-REMAINDER-MATRIX-v1 后释放。最多 ROOT+3，候选产品继续STOP。可写范围均为本批新QA，权威文档/契约/迁移/锁/服务资源由ROOT独占。新产品缺陷先报告再登记，不边验边修。

| ID / owner | 起点与范围 | 独立验收条件与结果 |
| --- | --- | --- |
| B6-INTEGRATION-v1 / g3_impl | G3源941/build q84e/proxy8001；独占b6-integration。沿用T30/T60/T70/T80/T90、旧seed helper及生产流水线，不启动TCP服务。新fixture须先交ROOT装配 | 真实完整教学链、五整字段+teacher6、JSON/SQL/body/context/source/maps不可变、QB/KP/class变更与新失效provider0；实际命令PID/duration/isolatedroot/wire/SHA/首败/STOP |
| B6-QUALITY-v1 / g3_boundary_review | 独占b6-quality；生产只读，独立新TEMP TestClient无TCP；导入app.main前环境与credentials None。手写teacher规则oracle，不从生产聚合生成expected | ≥12匿名可复现case、expected、≥6维rubric、offline执行器和输入→候选→字段→结果SHA，逐例不足、feedback.csv/md、live待输入和teacher_pending明确；不自评生成质量pass；首败/工具验证/STOP |
| B6-EXPORTS-v1 / g3_v00 | 独占b6-exports；仅现有产品DOCX/冻结print输出；ROOT持有5174/后端，勿触用户WPS。应用documents/pdf技能，优先bundledNode/Python/Poppler；只用bundledLibreOffice若存在 | 四真实当前固定样本/模板和来源SHA、ZIP/XML全字段/字体/合并/长表格、打印冻结、可行真实PDF保存与全页render/view；DOCX实际渲染缺工具明确not_run。教师试用/页清单/反馈入口/首败/STOP |
| B6-CTRL-v1 / ROOT | 服务/QA协议装配、稳定候选冻结、剩余矩阵、独立交叉验收、权威文档 | 不重建已有能力、不扩展下一模块；技术/准备/模型/人审/WordWPSPDF/迁移压力分列；旧文档与v2任务保持；资源/保全/后验后STOP |

所有新Python执行新TEMP/env=test/PYTHONUTF8在main导入前，Settings.credentials_file=None。Node --no-experimental-webstorage。真实模型缺profile/model/数量/预算，不能读正式.env猜用；只Transport替身技术证明。保留所有TEMP与首败，不清未知数据或旧QA。不提交、推送、切分支、部署，不重试旧被拒HTTP身份复核。
