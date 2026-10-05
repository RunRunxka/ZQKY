# B7-B 新结果与人工返回完整性检查 v1

`trial_result_check.py` 只读接入 X 所属 [trial-result v1](../../docs/qa/TEACHING-LOOP-G6-B7B-20261005/executor/SCHEMA-v1.md)。不修改旧 aggregate/prepare/preflight/common，不重建原 15/273 包或四历史导出。所有输出使用不存在的新目录。

```powershell
apps/api/.venv/Scripts/python.exe -B scripts/teaching-quality/trial_result_check.py --kind technical --manifest <新label/trial-result.json> --manifest-sha <SHA> --case-specs <原case-specs.json或canonical一致副本> --case-specs-sha <SHA> --output-dir <不存在的新label>
```

`--kind teacher` 或 `--kind native` 另需 `--return-file <新返回JSON> --return-sha <SHA>`。三种入口都先核实际 manifest、完整源码最小闭包、SHA-bound ledger/scope快照、scope canonical重算、原15手写事实、案例/attempt/job/raw/wire/usage/candidate关联。ledger只是本label只读审计快照，不改变执行器固定control-state归属。JobView只核实际公开jobId/attempt，不虚构视图不存在的inputHash/modelSnapshot。

ledger的累计attempts从完整tickets顺序独立重算；当前reviewLabel的send总数、每票状态/发送次数和结算usage均交叉核对。X v1没有注册可验证live模型计费证明，因此本检查器也明确拒绝live结果 provenance，不会把fixture改label后认作真实调用。未来live支持需先升级执行器的证明/来源契约和本检查入口，再独立验收；本脚本不签预算或真人授权。

case.status需与实际job.state一致，manifest.stopReason需与ledger快照一致。失败结果不能借用applied/DOCX。若上游raw因隐私安全被执行器禁止落盘，只接受failed/unknown且已STOP的hash-only关联，明确标suppressed_hash_only，不宣称核过原文或候选。

production结构复用实际 normalize_model_output/validate_for_apply、modelPayload/最终wire隐私规则与生产SYSTEM_PROMPT。阶段分钟合法变化可通过，不比较旧fixture的stageMinutes或字面答案。选中但停止的案例明确unrun，未选集合单列。应用存在时核六教师字段和未选AI字段全等、所选完整字段来自候选；QA选择标qa。缺应用或新DOCX为not_run，不冒称教师接受或已导出。新DOCX仅核hash、固定应用证据和ZIP包完整性，不给排版通过结论。

教师返回为严格JSON：schemaVersion=1、reviewLabel/evidenceKind/caseId/caseSpecSHA、outputSHA/candidateSHA/docxSHA、reviewerKind=human、reviewer、reviewedAt（带时区ISO）、verdict（usable/needs_revision/unusable）。dimensions恰含facts/material/coverage/activity/time/control/accuracy/feedback，每项score为整数0..3并有location/reason；hardFailures为明确列表（每项location/reason，空列表表示未观察到）；supported和unsupported各有location/reason，suggestion非空。返回需原文位置、支持/不支持理由、修改建议与结论俱全，硬失败不能被平均分抵消。完整性通过原样保留humanVerdict，createsTeacherApproval=false，不由脚本生成评分或默认教学PASS。

原生返回具有同一身份字段，另需application=Word/WPS、applicationVersion、totalPages正整数、pages严格覆盖1..totalPages。每页pageNumber/totalPages、实际图片evidence引用（file/sha256）、reason、verdict，以及checks恰含secondary/chineseSymbols/mergedCells/crossPage/clipping；每项observation为ok/issue/not_applicable且location/reason非空。逐页记录仍是人类提交证据的完整性核查；脚本不证明谁实际打开了Word/WPS。历史PDF或其页数不能作为原生记录；没有原生返回native_pending。

CLI在生产模块导入前创建并保留新TEMP，设置ZQKY_DATA_DIR/ZQKY_ENV=test/PYTHONUTF8=1。允许只读生产模块导入（包初始化含preparation/service），逐项记录productionModulesImported；app.main禁止导入。网络、正式.env、数据库打开均被audit guard禁止且记录实际尝试数，不把允许的生产导入计成app0。credentialsFile=null；不访问正式库/6333/真实模型。本批没有明确live范围，真实模型未执行。教师/native顶层始终pending；完整返回只在detail记录完整性与原人工verdict，最终认可须独立确认。RAG-REL保持OPEN，结构/教学/原生/检索相关性分别验收。

专属selfcheck `tests/test_trial_result_v1.py` 使用手写可变分钟、独立fixed事实、身份/shape/保持/人工返回反证，每个子CLI留实际argv/PID/起止/elapsed/exit/源QA散列/四guard；合成DOCX和1像素页图仅检接口，不构成教师/native材料。作者停止写入后交ROOT独立V00，不自签技术关闭。
