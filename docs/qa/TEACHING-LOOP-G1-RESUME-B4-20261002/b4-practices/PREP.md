# B4-T80-PREP v0 · 只读调查 ready / 待正式任务卡

负责人 `/root/g1_v00_fe`，2026-10-02。G1R-AUDIT v1.5 已完成并停止写入；CTRL 已关闭 G1。本次唯一新写入为本目录 `PREP.md` / `PREP.json`，未实现 T80、改共享契约/迁移/产品、运行测试/构建或启动服务。以下为交给 CTRL 的方案与实际接缝，**不是已冻结或已实现的 API**；最终字段、DDL 分期、共享端口以 CTRL 正式卡为准。

## 阅读依据与实际缺口

已读根/api/web AGENTS、CURRENT_STATUS/PROJECT_GUIDE、现行 API/ROUTES 对应段；用户第三附件 `a606c379-3ec5-417c-8692-29077474625f` 全文、`14d072ff-6825-4e33-bf45-ec448f6df6d3` 四至八；v2.0 T80、B3 实际补齐/B2 DDL、统一交互与验收；新 G1 REVIEW。旧教学设计 SQL 只核目标，不执行。调查现场仍 `main@6aeb57280f6a7e0d7391cad4d150745479ea58ec`；基线为已关闭 G1 r5，B4 正在准备，未声称当前共享源是新的稳定验收候选。

| 源码事实 | T80 需要的最小接线 |
| --- | --- |
| [题库 catalog](../../../../apps/api/app/repositories/question_bank/catalog.py) `list_questions:919` / `get_question:991` / `_question_record:2299` 读 current 修订；`question_knowledge_links:1090` 亦读 current，`question_knowledge_links_in:1099` 已可按固定修订读 links | CTRL 补固定历史 questionRevision reader，不能以 `get_question(questionId)` 替代固定选择。现有列表分页最大 200，没有题型/难度批量过滤端口，选题必须遍历完整符合范围的集合或新只读查询，不能只看首页后宣称无题 |
| [题面指纹](../../../../apps/api/app/services/question_bank/fingerprint.py:148) 为 `question-surface-v1`，明确排除答案/解析/随机 ID、保留材料/题干/选项/公式/图片结构 | 复用权威版本和真实图片 SHA；不同算法不可混比。原卷无 bank questionRevision 时从固定原题内容计算对照，不按题号或答案猜原题 |
| [question service](../../../../apps/api/app/services/question_bank/service.py:1837) 的 archive 直接 `catalog.archive_question`，当前未用 publication；confirm 已有先重放/锁外预检/锁内复核 | CTRL 将归档与练习新审核放在同一个 PublicationCoordinator；否则并发归档可以越过发布复核。历史 reviewed 导出读自身快照，后续归档不追改旧事实 |
| [paper migration](../../../../apps/api/app/core/migrations/teaching.py:191) `source_file_id NOT NULL`、practice 列 `CHECK IS NULL`，paper_confirm 无练习分支；确认/子表冻结已有 | 先实际建 practice 表，再受检重建 paper_revisions 来源二选一/真 FK/审核与同归属规则，保全所有文件卷闸门/原触发器、索引和子表 FK |
| [PaperRepository](../../../../apps/api/app/repositories/teaching/papers.py:575) `RevisionRecord.source_file_id:str`、读取强制文本、create_revision_in 强制文件且 practice=NULL；当前确认 reader 自开读连接 | CTRL 同步 Optional 来源记录/创建/复制/read DTO，并提供同 conn 固定卷读取；只改 DDL 会使练习卷被读成坏行，新事务内用旧 reader 也看不到未提交卷 |
| [PaperService 确认](../../../../apps/api/app/services/papers/service.py:827) 树/叶/总分/KP/未归属块/阻断问题及 [富题面引用校验](../../../../apps/api/app/services/papers/service.py:2063) 已有 | 文件卷保留原件/来源块规则；练习卷必须有 reviewed 源和题、叶、共同材料/资产完整映射。不能全部跳过来源检查或照搬文件必需列 |
| [T30 create](../../../../apps/api/app/services/assessments/service.py:427) 独立 execute_command；`_apply_create:452` / `_validate_participants:761` 已在传入 conn 内冻结服务端身份 | CTRL 公布不自开事务的转换端口，复用这些闸门/仓储；不能串调用公共 paper.confirm/create_assessment 获得同事务保证 |
| [T10 renderer](../../../../apps/api/app/services/rich_content/renderer_docx.py:367) 新建文档与 relationships、学生跳答案/解析；它接一个 RichContentV2+AssetStore | T80 只做正式快照的文档组合/材料去重，不复制 renderer。现有 QB 兼容 bare SHA / 独立 blobs，锁外验证后规范进入 managed AssetStore，保留原字节 SHA/出处 |
| [AssetStore](../../../../apps/api/app/services/assets/store.py:84) 内容寻址、原子存储、读取重算 SHA；[FileAssetsRepository.create_in](../../../../apps/api/app/repositories/assets/file_assets.py:106) 可同事务登记 | 下载权限不是 blob key 自带：新 artifact 路由核 owner、固定练习/施测归属和资产记录后再读受管字节 |
| teaching 已有 command_submissions/file_assets/workflow_jobs，未有 export_artifacts 或下载业务；main JobKind 已包含 teaching `analysis` / `export` | CTRL 新增最小 artifact 元数据/DTO/download 及执行器装配，复用原 kind，不另造任务表、资产引擎或假端点 |
| [JobStore.create_in](../../../../apps/api/app/repositories/jobs/repository.py:293) / [complete](../../../../apps/api/app/repositories/jobs/repository.py:522) 与 [JobOutcome.publish](../../../../apps/api/app/services/jobs/engine.py:65) 已支持同库事务 | 接受任务+submission 一次短事务；渲染/资产 IO 锁外；file_assets+artifact+job succeeded 用原 lease 同事务发布；取消/过期/旧 attempt 零业务写 |

## CTRL 应先冻结的形状

候选 API 沿用户四至八：practice-sets 创建/列表/工作区、固定 revisions、suggestions、draft PATCH、review、复制新草稿、revision exports、revision assessments，以及新 export-artifacts/{id}/download。请求/成功返回/409/422/404/501 示例、分页 `{items,total,offset,limit}` 与原 JobView 必需字段须 CTRL 定稿。`revision` 是 practice_sets 编辑 CAS，`practiceRevisionId` 是固定修订，互不代替。

草稿建议一题一个 selection，结构节点独立，避免一题多 KP 或多计分叶重复算题量：

```json
{
  "expectedRevision": 3,
  "items": [{
    "itemKey": "chosen-q1", "questionRevisionId": "fixed-qrev", "ordinal": 1,
    "itemStructure": {"nodes": [{
      "nodeKey": "q1-1", "parentNodeKey": null, "questionNo": "1", "ordinal": 1,
      "isScored": true, "maxScore": "2.00",
      "knowledgePointIds": ["kp-1"], "sourceBlockIds": ["stem-1"]
    }]}
  }],
  "constraints": {"questionCount": 1, "questionTypes": ["short_answer"], "difficulties": ["easy"], "allowUnspecifiedDifficulty": false, "excludeOriginal": true, "excludeDuplicates": true}
}
```

上述字段名仅提议。`itemKey/nodeKey` 为本修订映射键，不冒充题库 ID；各键唯一，父子限同 selection/revision、无环、题号/ordinal 唯一。计分容器拒绝，容器 maxScore=null；leaf maxScore 为 Decimal 文本 >0 转整数 ×100，正总分=所有计分叶之和。KP 须所选固定正式题 links 的子集、与报告学科相同；明确块归属并保留实质题面/共同材料，不能凭空拆出只有分值的空叶。没有评分点自动识别，叶结构由教师显式设计。

建议 fixed reader：`read_revision(question_revision_id, *, owner_id) -> FixedQuestionSnapshot`，包含 questionId/questionRevisionId/ownerId/current activity status/固定 content+metadata+answerState+confirmedAt/full contentHash/权威 surfaceFingerprint+algorithmVersion、固定正式 links（KP ID/revision/name/subject/role）、rich origin/source locators/资产声明。JOIN `question_revisions.question_id` 核归属，不跟 current 指针；当前仍 active 的题可以明确选择旧确认修订，更新题干不会偷偷换题。新审核在协调器内核 activity，历史导出只读 reviewed 快照。question_sources 目前按 questionId 追加，不是修订封存来源；优先保存固定 rich.origin 和该次核验来源，不能声称来源表本身全历史不可变。

## 必要 DDL 建议

由 CTRL 登记追加，不写回 0001–0007。以下为关系需求，不是执行 SQL：

- `practice_sets`：id/owner_id/analysis_run_id/subject_id/title/current_revision_id/revision/status/created_at。current 指针以 `(current_revision_id,id)` 对 practice_revisions 复合 FK 防跨练习；analysisRun 必须 ready 且同 owner/subject。
- `practice_revisions`：id/practice_set_id/version/state(draft|reviewed)/title_snapshot/input_hash/selection_snapshot_json/constraints_json/total_score_units/reviewed_at/created_at，`UNIQUE(id,practice_set_id)`；状态/日期对称 CHECK，禁止直接 INSERT reviewed。B5 lessonPlan/group 列省略（若 CTRL 保留，CHECK IS NULL）。
- `practice_selections`：每题一个 id/practice_revision_id/item_key/ordinal/question_id/question_revision_id/question_content_hash/content_snapshot_json/metadata_snapshot_json/rich_assets_json/source_snapshot_json/reason_json，selection/item_key/ordinal 唯一；跨库题 ID 是服务校验+快照，非 SQLite FK。
- `practice_items`：selection 的结构节点，id/practice_revision_id/selection_id/node_key/parent_item_id/question_no/ordinal/is_scored/max_score_units/content_json/source_locator_json；父子/selection 用复合 FK 保证同修订，只有正分叶计分；`practice_item_knowledge` 存固定 KP 身份/修订/名称/学科/role 与 item/revision 复合 FK。
- `practice_conversions`：id/owner_id/practice_revision_id/paper_revision_id/assessment_id/input_hash/participant_snapshot_json；`practice_paper_item_mappings`：conversion_id/practice_item_id/paper_item_id/paper_revision_id。同库所有归属均真 FK/复合 FK或不可绕过触发器；一 practice 可显式另建施测，不把不同转换请求错误合并；同 submission 原包返回同一转换。
- `export_artifacts`：id/owner_id/practice_set_id/practice_revision_id/variant/assessment_id nullable/file_asset_id/job_id/input_hash/frozen_input_json或冻结输入引用/created_at。FK 指 teaching 自己的实际表；`score_template` 必须 assessmentId，DOCX 必须 null，assessment 必须该 practiceRevision 的转换。绑定 `kind=export` 资产和成功 job；owner/版本归属 DB 或服务双核，拒跨 practice artifact。
- reviewed revision 与所有 selections/items/KP/material/snapshot 子表 INSERT/UPDATE/DELETE 全覆盖冻结触发器，UPDATE 检查 OLD/NEW parent，防搬行。封存闸门复核树、计分叶、总分、题面/KP/资产声明与目标覆盖；修改只能从 reviewed 复制新的 draft。

`Migration.__post_init__` 实际禁止 `rebuild` 与 `statements/adjust` 混用。最小分期为 **0008 先新增 B4 表 → 0009 RebuildPlan 重建 paper_revisions**；可由 CTRL 选择另一等价受检分期，不为一编号扩改迁移引擎。重建允许 source_file=null，CHECK 两来源恰一非空，真实 practice FK/同 owner 与审核源闸门，恢复全部 title_snapshot/confirmed 冻结/计分/源子表与索引触发器。FK 事务外 OFF、单事务拷贝/换表/恢复、全行 FK check/integrity/data reconciliation 后登记，finally ON。0007 active score 的同施测 FK 不重复重建。

## 服务流程与共享端口

建议构造参数：`PracticeService(teaching_catalog, *, analysis_reader, fixed_question_reader, knowledge_catalog, coordinator, assets, question_asset_reader, job_engine, job_registry, assessment_converter, owner_id="local")`。实际已实现的 AnalysisReader/DTO 由 CTRL/T70 交接，T80 不依赖其私有表猜 ready。

选题读取 ready 报告固定 KP 与原题证据；约束严格过滤题型和 `easy|medium|hard|unspecified`，未知难度由教师显式允许，否则排除。确定性按未覆盖目标数、约束匹配、questionId（必要时 fixed revisionId）排序；更新 uncovered 集合直到题量，真实记录 requested/selected/count/covered/missing、各排除理由、候选范围/算法版本。一次题选择覆盖多个 KP 仍只计 1 题；题量不足、某 KP 无题、原题/重复/归档/学科冲突不暗放宽。缺题只给人工已有补题入口：question-generation-jobs → needs_review → 人工保存 → reviewed → 正式 confirm 后重新 suggestions；不把 AI 草稿作为正式 reader，不发学生姓名/学号/人员 ID，不在 T80 偷调模型。

review 快路查成功 submission（同请求返回原结果，异请求 409）；锁外固定题/KP/结构/资产真实字节预检与 content hash；PublicationCoordinator 内再次查重放、复核题活动/KP身份/学科及同一预检身份/hash；短 teaching 事务内 CAS、写全部快照/子项、reviewed transition、submission 收据。预检读失败不为空题；编辑/题改版/归档交错须拒或按明确固定修订语义保留，不能换最新。锁内不解析/渲染/写资产。KP 更名/归档以后不改变既有 reviewed 名称/题面/下载；新引用另行按当前合法活动状态审核。

请求 `requestHash` 与任务 `inputHash` 区分：稳定显式请求决定同 `(owner,operation,submissionId)` 的重放；首次接受才把固定修订及冻结事实构成 inputHash。不要在每次重放先读取当前名单/名字再重算请求 hash。继续使用 canonical_hash，但集合先排序、结构按明确 ordinal、分数整数编码；成功重放必须优先于后来 CAS、归档或缺资产预检。未知响应仍冻结完整原请求，不换 submission。

转换端口建议：

```python
create_from_reviewed_practice_in(
    conn, *, reviewed_snapshot, title, held_on, class_ids, participants, owner_id
) -> {paperId, paperRevisionId, assessmentId, participants, mappings}
```

端口不自开事务、不自行提交、不另登记 submission；外层一次 execute_command/短 teaching 写事务负责纸卷草稿、固定来源/真实块材料与叶/KP复制、分支闸门确认、T30 服务端名单/日期/归属依据/人次/出勤快照、mapping、转换和收据。同 conn 读取刚确认卷，不走 reader 另连接；任何阶段故障全部零半卷/半施测。客户端不得指定替代 paperRevisionId、姓名/学号。转换新发布的 KP 活动核验在同 publication 协调顺序下，旧已成功转换重放不重核现在活动状态。

## 导出、模板及回流

DOCX 合成器只取 reviewed 快照；为所选题/节点命名空间化 block IDs，保留来源映射，按真实材料 identity+canonical内容去重（相同 id 内容冲突阻断，不能只按文本碰撞）。给每题、选项、叶题号和分值可读标签；教师答案/解析标签关联原题，缺答案明确“未提供”。RichContentV2 的 stem/shared materials 与 answer/explanation 投影分别组合，仍调用 T10 单一 renderer。旧纯 Markdown 正式题必须明确定义到段落/公式/图片的安全转换支持与限制，不能把未支持表格/公式静默降级成空文字成功。

学生投影无答案、解析、教师块；整个生成 ZIP 检查全部 XML/rels/header/footer/comments/customXML/嵌入对象，使用独立测试专属标记逐项扫，不只 document.paragraphs。源文件 attachments/rIds 不复制；图片真实 relationship+bytes SHA、合并表格、OMML 全参数/LaTeX 都验证。缺资产、错 hash、非法 owner、未知公式或转换失败阻断/明确问题，无成功 artifact。Word/WPS 中文长题干真实版式是单独环境验收，XML 通过不能冒称已看。

CTRL 已选 **score_template 必须 assessmentId 且属于本固定练习转换，DOCX 拒 assessmentId**。模板接受任务的同事务冻结实际当前 T30 participants（server 姓名、文本学号、attendance、attempt/class确认依据）和固定 paper/leaf 映射；job 执行/重试读取 frozen_input，不重新读最新名单。此时点不是 review 时，也不是下载时；此后改名/转班/补考/出勤变化不改旧模板。原包重放返同任务/固定产物；新 submission 可以产生新名单快照，UI明确时点。XLSX 学号单元文本、保留 `0012`，分数空且不补 0，不公式算原分；附 paper/practice/revision/leafID/full题号映射说明。模板快照不是未来 T60 成绩快照替代品，实际成绩仍按确认时自己的冻结上下文。

导出使用教学 kind `export`、模型名额 false；registry 由 CTRL 装配，公共 retry 仍 N/N+1、原 lease CAS，重启 running→interrupted 不自动执行。accept 在同事务存 JobStore.create_in 与 submission；渲染/ZIP验证/AssetStore.store_original 锁外。JobOutcome.publish(conn) 同事务登记 file_assets/immutable artifact/result 与 succeeded；取消/过期/旧 attempt 不能发布，失败可留下登记的孤立内容寻址 blob 但无可下载成功 artifact，不擅自清理未知文件。不要在已经持 teaching 写锁的 publish 中再获取 publication，反转 review 的 publication→SQL 顺序；导出只引用已封存同库快照，应无需新增跨库发布锁。

download 以 artifactId 核 owner、practiceRevision/assessment 所属、元数据和 file_asset 关系；受管 read 重算字节 SHA，校大小/media type、固定 Content-Disposition，不把请求文件名拼路径；损坏缺失明确错误，不返回空 200。旧导出迟到时前端按修订/variant/任务身份显示，不能替换当前版本条目。

回流保存 practice selection/node→paper item 映射，T60 的 scoreRevisionId/participant/item cell 已可精确定位，再通过 T70 evidence 的固定 paperItem/scoreRevision 回溯 conversion。实际路径必须完成转换施测→新成绩确认→新报告，核新报告 evidence 指回该 practice leaf；旧分析/练习/导出/成绩全未变，只有下载不算闭环。正式转换可多班/多 attempt，选择规则沿 T30，T70 每学生显式选一个人次，不自行取最好。

## 正式实现后的验收计划（本 PREP 全未执行）

| 场景 | 必须抓住的错误 / 证据 |
| --- | --- |
| 选题/缺口 | 多 KP 一题一位、已确认固定修订、原题与权威重复排除、难度 unspecified 策略、不只首页、稳定结果、缺口不暗放宽；AI 未确认不能入练习 |
| CAS/原包 | 两并发保存一赢家、409 currentRevision/422定位且前端输入保留；review/export/convert 响应丢失同完整原包重放、同键异包409、后来改名/归档/名单不阻已成功收据 |
| 审核封存 | 服务+直接 SQL 禁直接 reviewed、全部子表 INSERT/UPDATE/DELETE/搬行；旧 fixed question 更新/归档/KP改名后旧快照逐字不变；预检后编辑或归档交错拒绝且 IO不持锁 |
| 迁移 | 全新四库/有数据0007旧库、来源二选一/真FK/owner/未审核；拷贝/换表/触发器恢复/完整FK及integrity/登记各故障回滚可重跑，finally FK=ON；0001–0007散列全保留 |
| DOCX与资产 | 材料一次、长中文/表格合并/真实图片关系/OMML与LaTeX、教师缺答案；整个学生ZIP独立标记泄漏扫；缺图/hash/owner/公式失败无artifact；Word/WPS另列实际/not_run |
| job/产物 | queued六态、并发取消/retry/过期原lease/旧attempt/发布失败零metadata与终态分裂；完成job+artifact+file_asset一个tx；下载损坏/越权/跨练习不成功 |
| 模板 | assessment归属验证，接受时冻结参与者和叶，`0012`文本/空分数/固定映射；之后名单变化、job重试与旧下载不漂移；DOCX带assessmentId拒绝 |
| 转换与回流 | reviewed-only、一tx paper确认/T30参与者/mapping/submission；各阶段注入故障零半卷/施测；同包同ID/异包409；真实T60→新T70与practiceLeaf可追溯；旧件不改 |
| 独立/规模/集成 | 手写 Q1/Q2/Q3/A–D oracle+错误变体，200×100全矩阵与全部evidence/分页、纯分析3秒目标；真实四库FastAPI/三视口键盘reduced-motion/完整适用check/API/build/E2E，四库新表+资产离线备份恢复；Provider替身只技术链 |

T80 专属 API/service/repository/tests 待正式卡登记，SQL和共享 ports/DTO/Job/main/assets/renderer/migrations/root文件仍 CTRL 独占。未启动服务/浏览器/构建，没有候选产品修改、测试通过数、正式 .env/.local-data/凭证/用户草稿读取或 Git 写入；所有只读 shell 已结束，无本任务后台/监听/临时业务数据根。PREP ready 后停写，等待正式卡与契约/DDL/端口冻结，不自行实现。
