# B4-FE-PREP v0 — 学情分析与针对练习页面准备

状态：ready_for_contract；仅设计准备，未实现、未执行产品门禁。负责人：`/root/g1_resume_browser`。日期：2026-10-02。

本卡唯一写入为本目录 `PREP.md` / `PREP.json`。产品、公共契约、客户端、导航、薄路由、样式、旧 G1 证据均只读；未构建、未启动或停止服务、未操作用户 5174 和正式草稿。现场分支 `main`，HEAD `6aeb57280f6a7e0d7391cad4d150745479ea58ec`。以 CTRL 已关闭 G1 的通知和 CURRENT_STATUS 顶部为当前状态，历史 G1 结论不追改。

## 1. 依据与范围

已读根及 `apps/web/AGENTS.md`、CURRENT_STATUS、PROJECT_GUIDE、用户第三附件、14d…附件“四至八”、v2.0 T70/T80/F30/F10、P5/P7，以及 `C:/Users/96022/.codex/skills/frontend-design/SKILL.md`。已读安装中的 Next 16 本地 layouts/pages、server/client components、linking/navigation 和 server/client boundary 文档；不按旧版同步 searchParams 编写薄路由。

用户最终要求优先于旧分批：B4 包括 T70、T80、F30 学情页和 F10 练习页；B5/T90、AI 教案调整不在范围。v2.0 原文没有独立 F40 任务，不能编造该 ID 的旧规格。本准备用 B4-F 表示两个新前端模块。

预期模块为 `features/learning-analysis/**` 与 `features/practices/**`，路由建议 `/learning-analysis`、`/practices`，实际路径、共享入口与 DTO 等 CTRL 冻结。客户端只调用 FastAPI，不在 Next Route Handler 建业务后端。前端展示后端事实，不计算掌握度、观察状态、班级计数、分母或知识点分数。

## 2. 已核现有复用点与缺口

| 现有文件 | 实际可复用能力 / 本批需要的最小衔接 |
| --- | --- |
| `features/assessments/HistoryPanel.tsx` | 已有明确 `selectedRevisionId`、confirmed 修订、固定只读矩阵和 participantSnapshot；目前无分析 Link。CTRL 在所选 confirmed 修订旁补入口，href 固定 assessmentId + scoreRevisionId；不将旧历史点击改为 active。 |
| `app/assessments/page.tsx`、`features/assessments/AssessmentsWorkspace.tsx` | 当前页面无 searchParams/initial props，工作区默认从名单开始；回流需要 CTRL 最小加入已返回 assessmentId 与 step=score/history 的可序列化定位。保留原五步和 F20 业务。 |
| `services/assessments-api.ts` | 已有 listAssessments/listScoreRevisions/getScoreRevision/getPaperRevisionContent/getScoreMatrix；getPaperAsset 是 BlobDownload 收据，富内容 loader 必须取 `.blob`，不能把收据当 Blob。创建施测接口复用现有 T30 参数，但练习转换只调用 T80 专用接口。 |
| `contracts/scores.ts` | ScoreParticipantSnapshot 只有 participantId/studentId/studentNo/name/classId/attemptNo/attendance，没有 className。分析冻结源只能来自该 revision 自己的快照；当前名单不用于补历史班名。 |
| `contracts/assessments.ts` | AssessmentParticipantInput = studentId/classId/attendance?/attemptNo?/classConfirmed?/classConfirmationNote?。转换姓名学号由服务端冻结，不能客户端提供；heldOn 归属不覆盖时需要教师明确确认和依据。 |
| `components/ui/RichContentRenderer.tsx` | 已有 RichContentRenderer（共同材料+题干）、RichBlocks（选项/答案/解析）、ContentMarkdown；assetScope + AbortSignal 管理受管图片。没有必要再做富内容渲染器。 |
| `features/question-bank/QuestionPreview.tsx` | 会展示答案，不能直接当学生版预览。新教师审阅可以用公共 renderer/blocks；解析块存在时不应依赖旧 explanationMarkdown 非空才显示。 |
| `services/use-workflow-job.ts` | 使用现有 `useObservedJob('teaching')` 的 adopt/reset/retry/cancel、六态、attempt 与 N/N+1 观察窗口；不新造任务 hook。终态回调再读取固定报告/产物权威详情。 |
| `features/assessments/hooks.ts` | 已有 useAsyncResource 的 loading/ready/failed、lastData、epoch、abort、StrictMode alive 恢复；已有 useFrozenSubmission 冻结 submissionId/payload，status=0 进入 unknown。是否直接跨模块复用或 CTRL 提升为公共文件需冻结；不再复制第二个实现。 |
| `features/question-bank/QuestionLibrary.tsx`、`GenerationPanel.tsx`、`ReviewWorkspace.tsx` | 现有正式题与 AI 补题→needs_review→人工保存→校对→确认链可复用；当前 GenerationPanel 没有目标 KP/返回练习 initial props，QuestionBankWorkspace 只认 #library。CTRL 需登记最小返回上下文或授权复用现有面板的明确入口。 |
| `services/navigation.ts`、`components/layout/ModuleWorkspaceShell.tsx` | 尚无两新路由登记。ModuleWorkspaceShell independentRoots 只含资料库/KP/书籍/课程/题库。CTRL 应为新页面登记 ready 导航并加入公共壳，确保只一层壳、手机抽屉焦点圈定/返回。 |
| `components/layout/space.css`、`styles/globals.css` / `motion.css` | 沿用共享 space 控件，业务布局覆写限定 `.learning-analysis-page` / `.practices-page`；不改共享层。字体和颜色只用已有 token；现有 reduce 规则可验证真实动画/transition 行为。 |

## 3. 页面设计

教师主要任务是核对一次固定成绩的依据，再把需巩固知识点变成可审核、可施测的练习。首屏突出固定来源与下一操作，详情展开完整题目材料。标志性元素是简洁的“固定来源链”一行：成绩版本 → 学情报告 → 练习审核版本 → 新施测；每一项链接到实际固定对象，未产生对象不显示成功。

颜色使用既有 token：`--blue #2563eb` 主操作、`--blue-soft #eff5ff` 所选来源、`--bg #fff` 纸面、`--surface #f7f7f7` 分组、`--ink #0d0d0d` 正文、`--line #e5e5e5` 分隔。错误沿用 `--danger`。标题 `--font-display`，界面/表格 `--font-ui`，编号/固定 ID `--font-mono`，文档纸面 `--font-document`。不添加字体名、渐变或大号“掌握率”统计。

桌面学情页：主内容最多约 1240px，1920 屏居中；1440 屏优先给事实和证据宽度。200×100 矩阵不全放首屏，以服务端分页人次/知识点事实和按需证据替代全量 DOM。

```text
公共侧栏 | 学情分析                              [历史报告]
         | 固定来源：施测 → 成绩 vN → 原卷 vN     [查看历史成绩]
         | 成绩/人次选择 · 出勤/补考说明 · 明确规则 [创建本次报告]
         | 任务状态 / 重试 / 取消 / 错误 / 结果准备
         | [班级依据] [学生依据] [全部题证据] [教师备注]
         | 班级/KP筛选 · 分页 · 需巩固/满分/信息不全/无依据
         | 事实表（分母、分子及后端比例） | 选中项完整题证据
         | 目标 KP checklist + 冻结名称             [创建针对练习]
```

桌面练习页：左边为固定版本/草稿工作区切换；主体按“选题与结构 → 保存 → 独立审核 → 固定导出/转换”排列，主按钮只对应当前阶段。完整共同材料与父子题在选题审阅区；计分叶采用可访问的表格编辑，换序用上移/下移按钮而非只靠拖拽。

```text
公共侧栏 | 针对练习           固定来源链           [练习列表]
         | 来源报告/KP · 草稿 revision 或审核 vN · 未保存提示
         | 题量/题型/难度/unknown策略/原题排除/查重  [获取正式题建议]
         | 覆盖与真实缺口 · 正式题固定修订候选       [采用所选候选]
         | 题树与计分叶编辑 | 完整材料/选项/教师答案解析审阅
         | [保存草稿]  [独立审核] / [从此审核版建立新草稿]
         | 固定版本导出任务：学生DOCX / 教师DOCX / 成绩XLSX
         | 转换施测：题名/日期/班级/显式人次/归属确认 [转换并录入成绩]
```

390×844：顶部来源链换行，详情在正文中顺序展开；表单单列，操作区换行，不固定遮挡底部输入。事实宽表只在有标题/说明的内部滚动容器横向滚动，页面根不得横溢。页签可横向内部滚动但 Tab 焦点可见；目标选择、证据展开和换序都有文本按钮。手机抽屉直接复用公共壳焦点管理。

## 4. 完整真实操作与 UI 状态

| 操作 | 权威前置条件、pending/失败/成功表现 |
| --- | --- |
| 固定成绩来源 | 从历史入口携带两个固定 ID，GET revision 核 confirmed/assessmentId/paperRevisionId；错误或不匹配明确显示，不回退 active。独立页面可显式选施测和历史 revision；读取失败不能“无成绩”。 |
| 选择人次 | 用固定 participantSnapshot；默认不悄悄全选。同 studentId 多次互斥，明确 attemptNo/attendance，至少一人次；数据来源过期/读取失败禁止创建。 |
| 创建分析 | POST 固定 scoreRevisionId/selectedParticipantIds/any_loss_v1；按钮防重复。202 表示接受，用实际 job 六态。unknown 锁住原操作，显示“结果尚未明确，重试原提交”；不生成新 submissionId。 |
| 查看报告 | reportReady 和成功 job 收据匹配后 GET classes/students/evidence。REPORT_NOT_READY 展示仍未准备；ready 后列表失败保留上次数据并标“读取失败，显示上次结果”，不呈空成功。 |
| 班级/学生事实 | 展示 needs_consolidation/full_credit/incomplete/no_evidence 与独立 informationIncomplete；不把重叠计数相加当总数。className=null 显示“该成绩未记录班名（班级ID…）”，currentClassName 若有另标实时。 |
| 比例/四态 | consolidationRatio 仅展示后端 numerator/denominator/value；分母0显示“暂无有效依据”。recorded(0) 保留有效0分，missing/absent/exempt各自标识。措辞“本次需巩固 / 暂无有效依据 / 信息不全”。 |
| 展开题证据 | 不限失分：recorded满分、0分、missing、absent、exempt都可展开。固定KP修订/名称、题路径/计分叶/分数/材料/源坐标/资产原样；多KP显示“综合题失分关联，具体错因待教师确认”。 |
| 追加备注 | 文本与选定 participant/KP 来自本 run；提交中不清输入。422位置和409详情原样，失败保编辑；成功仅清除发送时那一代文本，后续输入保留。备注追加，不修改报告事实。 |
| 从报告建练习 | 仅 ready run，目标 KP 显式选择且核属于该run。冻结来源/目标/约束/title；成功用返回 practiceSetId/revision 进入真实工作区，失败保选项。 |
| 正式题建议 | expectedRevision + 明确 constraints；不隐式改草稿。候选具有固定 questionRevisionId、完整富内容与已确认KP；展示后端覆盖/理由/gaps。教师显式采用；缺题不自动放宽，不自动调用模型。 |
| 补题与返回 | 用户主动进入现有 AI 补题/校对链，界面明确候选不能进练习。返回练习后重新获取正式题建议/显式加入；不从生成 job 的候选直接填 draft。返回上下文只携带固定练习ID/来源KP等必要ID，不含学生资料。 |
| 草稿结构/保存 | 显式增删、顺序、题号/父子/仅叶计分/maxScore十进制文本/正式KP子集；expectedRevision CAS。保存中可以继续编辑，但 review 禁止；返回只应用发送版本的权威revision，不覆盖更晚约束/结构/输入。 |
| 独立审核 | 仅权威已保存 draft 且无dirty/no pending/unknown；明确按钮，不能“保存并审核”暗合并。资产/题/KP/结构失败显示定位并保draft；成功转固定 reviewed revision。 |
| 历史与新草稿 | reviewed只读；编辑需调用 revisions 明确从哪个sourceRevision复制。旧版本详情、下载、转换来源始终固定；新草稿不会改变旧导出条目。 |
| 导出与下载 | 仅 fixed reviewed revision；三种variant分别显示接受/排队/执行/成功/失败/取消/中断。202不显示下载。终态成功读取并核artifact owner/revision/variant/attempt，再提供真实Blob下载；下载错误保产物收据，不保存空文件。 |
| 转换施测 | 仅 reviewed source，明确 title/heldOn/classIds/非空participants。姓名/学号不给客户端写；attendance/attempt/历史班级显式确认沿用T30。失败保表单，unknown原包重试。成功仅使用返回paper/assessment/practiceRevision IDs，进入原F20成绩。 |
| 新成绩回流 | 转换→现有T60上传/映射/保存/承认/确认→新scoreRevision→新T70run；来源链接保留practiceItem→paperItem→scoreCell→analysisEvidence，旧报告只读。无新成绩/报告时不标闭环完成。 |

## 5. 必须由 CTRL 冻结的 DTO / API / 入口

以下是实现所需字段清单，不宣称现行端点已存在。外部 camelCase，revision 编辑 CAS 与 revisionId 固定身份分开。所有列表 `{items,total,offset,limit}`，错误 `{code,message,requestId,retryable,details}`，409保留currentRevision，422包含可定位issues。

1. **分析创建与来源**：POST `/assessments/{assessmentId}/analysis-runs` 请求 `submissionId,scoreRevisionId,selectedParticipantIds,ruleCode`；202至少 `runId,inputHash,scoreRevisionId,paperRevisionId,job` 和明确replayed语义。GET run必需 `runId,assessmentId,scoreRevisionId,paperId,paperRevisionId,ruleCode,ruleVersion,inputHash,selectionSnapshot,participantSnapshot,job,reportReady,createdAt`；各快照名称/学号/班ID/attempt/attendance可直接显示，className明确nullable。
2. **可发现固定旧报告**：root决定是否提供 GET `/analysis-runs`（assessmentId/scoreRevisionId + 分页）或在现有成绩历史列表提供固定报告链接；仅 runId GET 且无任何历史索引会使刷新后的旧报告不可找。选择后不能转active。
3. **报告列表**：classes/students过滤 `classId/participantId/knowledgePointId` 分页；班级KP事实必需 `classId,className,knowledgePointId,knowledgeRevisionId,knowledgeNameSnapshot,selectedStudentCount,validStudentCount,needsConsolidationCount,informationIncompleteCount,noEvidenceCount,fullCreditCount,consolidationRatio:{numerator,denominator,value:null|decimal}`。学生KP必需 participant固定身份、KP冻结身份、`observation,informationIncomplete` 以及各四态数量/证据定位（名称及计数的精确字段由root冻结）。前端不自行汇总。
4. **全部证据**：必须有固定 evidenceId/runId/scoreRevisionId/paperRevisionId/participantId/itemId/itemPath/maxScoreUnits/scoreUnits/status/KP关联修订和名称、真实 RichContentV2、完整共同材料/sourceLocator/assets；若按父题重复材料，明确完整引用关系和去重只用于展示。practiceItemId/sourcePracticeRevisionId 等回流映射可nullable，后端给出归属，不靠路径字符串猜。
5. **备注**：POST/GET notes 的 noteId/runId/participantId?/knowledgePointId?/note/createdAt/replayed（若适用）和分页；participant/KP缺省值null/省略规范明确，备注不替换事实。
6. **练习 create/current/history**：practiceSetId/analysisRunId/title/subjectId/targetKnowledgePoints冻结ID+修订+名称/currentDraftRevision编辑数字/固定reviewedRevisions列表。fixed revision有 practiceRevisionId/version/state/sourceRevisionId/constraints/items/coverage/gaps/selectionRationale/createdAt/reviewedAt；current draft有权威revision、issues及完整结构，不用GET currentQuestion替代固定快照。
7. **约束与候选**：constraints精确 `count,questionTypes,difficulty,unknownDifficultyPolicy,excludeOriginal,excludeDuplicates` 或root同语义冻结命名；候选需 `questionId,questionRevisionId,subjectId,type,difficulty,richContent,formalKnowledgeLinks,parent/leafStructure,selectionReason,coverage`，gaps给目标KP/所需与可供数量/原因码；稳定次序/采用候选是否带默认分叶/满分由后端明确。
8. **draft itemStructure**：固定questionRevisionId/ordinal/questionNo/local practiceItemId或draft引用ID/parentItemId/isScored/maxScore十进制文本/selectedKnowledgePointIds。若复用 PaperItemInput，冻结父子引用、叶与KP的准确字段，禁止前后端各造树形结构。所有rich/assets只读来源由后端返回；教师不能客户端改正式题快照。
9. **审核/新草稿收据**：review request `submissionId,expectedRevision` → practiceSetId/practiceRevisionId/固定详情/replayed；revisions request `submissionId,sourceRevisionId` → 新draft/编辑revision/replayed。未知收据可以原包重放，已成功重放先于当前CAS。
10. **导出基础**：root新增最小 export_artifacts + file_asset下载端口，确认确有实现。exports接受 `submissionId,variant`，返回 `job,practiceSetId,practiceRevisionId,variant,inputHash`；job.kind/domain/成功result `{artifactId,practiceRevisionId,variant,...}` 精确冻结；artifact收据 `artifactId,ownerType,ownerId,practiceRevisionId,variant,fileAssetId,sha256,mediaType,fileName,createdAt` 以及真实download route。history可查原artifact；下载用apiRequestBlob、Content-Disposition，不自行编成功。
11. **成绩模板名单时点**：必须明确 score_template是转换后指定assessmentId的固定participantSnapshot、或导出请求另冻结显式participants。模板含固定paper/叶映射/文本学号/姓名/出勤、分数留空不补0；若模板必须已有转换，UI先转换再启用模板，不能假造尚不存在paper/名单。请root在冻结卡明确请求字段与返回 rosterSnapshot/frozenAt/assessmentId/paperRevisionId。
12. **转换收据**：请求 `submissionId,title,heldOn,classIds,participants:AssessmentParticipantInput[]`，无客户端paperID。返回 `paperId,paperRevisionId,assessmentId,practiceRevisionId,replayed`；practice→paper完整题/叶映射和来源可在fixed details或dedicated read给UI，不靠题号相等推断。
13. **assets/services**：两个特性服务通过显式Services props/Context注入，默认实现为root登记的新API客户端；root定只读asset路径的revision/owner绑定。公共paper asset复用时loader取BlobDownload.blob；practice使用固定revision资产端口，不用当前question图片端口读取旧快照。
14. **导航和薄路由**：root登记两新ready页面、公壳roots和ROUTES；Next16 server page `await searchParams` 后传serializable initial IDs。建议 query：analysis `assessmentId,scoreRevisionId,runId`；practices `practiceSetId,practiceRevisionId,analysisRunId,knowledgePointId[]`（root选实际命名）；assessment回流 `assessmentId,step=score`。参数重复/冲突/不属于固定对象显示错误，不启动默认新任务。Link构造encodeURIComponent/URLSearchParams，只允许本地登记路径返回。
15. **既有通用提交hook归属**：root冻结复用 `features/assessments/hooks.ts` useFrozenSubmission 还是提升公共路径；新页面不复制任务/确认hook。需要保证 keyed对象切换不遗失unknown原包，允许查看其他对象时保留原操作收据且不把旧结果写到新工作区。

## 6. 晚响应、编辑与未知原包守卫

读取identity包含页面对象、fixedrevision/runId、筛选、页码；每次切换递增generation并AbortController.abort。应用结果前核alive + generation + object ID，失败不置空成功；旧数据仅在同一个identity读取失败时显示stale标签，不能把上一对象的lastData显示成新对象。

每次写请求冻结 operationKey（owner/operation/submissionId）、payload克隆、expectedRevision、发送editGeneration。保存返回只更新对应服务端revision；当前编辑代次未变才使用权威内容并清dirty，代次已变保更晚文本/结构/约束及dirty，并明确仍需再次保存。重读同对象不能悄悄覆盖dirty草稿，409提供“保留输入并读取新版本”后由教师决定重放修改。

unknown保存完整原包，控制原操作涉及的来源、约束、结构、审核/转换按钮，重试只复用原submissionId与payload；不能用当前表单或新revision改写。切换对象不能release后丢包；原操作收据独立保留，迟到成功只归原owner。known 422/409写失败保编辑，明确结果后才允许新操作。

任务直接用公共useObservedJob，不绕过attempt边界。分析终态回调核run/job固定身份，再GET run确认reportReady；导出按 `(practiceSetId,practiceRevisionId,variant,jobId,attempt)` 绑定，切修订reset观察并保持历史收据分组，旧结果只入对应历史组，不替换当前下载按钮。Blob下载/图片URL在owner切换或卸载取消/撤销；StrictMode setup必须恢复alive，cleanup取消旧观察，不在render或模块顶层读浏览器状态。

## 7. 未来行为测试与独立验收计划

此处全部为 not_run：当前仅准备、共享契约尚未冻结，不能把计划当pass。正式实现后仅写对应新模块行为测试，最终独立验收由CTRL另派。

| 测试层 | 有意义的覆盖 |
| --- | --- |
| Vitest 学情 | fixed历史入口不换active；来源不匹配报错；显式人次/同学生互斥；后端事实直接显示（例如后端已给比例2/3及各重叠计数，不在UI求和）；className:null明确缺失；全四态/0分/满分/多KP提示；failed list不是empty；备注失败保输入/成功保更晚编辑；延迟旧run/过滤响应不盖当前；202/failed/cancelled/interrupted/unknown原包。 |
| Vitest 练习 | 建练习来源ready及目标KP；constraints原样、建议不隐式改draft、缺口不自动放宽；fixed正式题结构与rich；保存期间更晚编辑保留/409/422定位；dirty禁止review、保存不等审核；旧审核版只读/新draft另身份；旧导出迟到不替换新revision；成功job但缺artifact身份不下载；unknown转换锁定原包/同包重放；使用返回assessmentID定位原F20。 |
| 单元替身边界 | Services注入或现行API模块spy只用于单元行为；业务算法由T70独立字面oracle验，不在前端复制数学验证。renderer已有公共单测不再镜像，增加实际特性传递fullblocks/assetScope相关用例。 |
| 实际FastAPI浏览器 | 固定历史成绩→选人次→真实分析job/全部事实证据→备注→目标KP练习→约束/正式题缺口→必要现有候选审核链→保存/独立审核→两版DOCX和模板真实下载→转换丢响应同包重放→原F20新成绩确认→新报告映射；旧对象读回不变。只可route.fetch延迟/丢失真实结果，不制造业务成功响应。 |
| 三视口像素 | 1440×900/1920×1080/390×844学情及练习稳定ready截图+重点材料/公式/表格/图片局部图；根document/body宽度无横溢，宽表容器可滚，长ID/题目/错误信息换行不遮主操作。人工复核真实画面，不以截图文件存在计pass。 |
| 键盘/动画 | 实际Tab/Shift+Tab/Enter/Space遍历选择、页签、展开、换序、审核、下载、手机抽屉；验证可见outline和关闭后返回。正常/OSreduce/现有reduce设置分别读取计算后的transition/animation，比较实际hover/job指示动画与getAnimations活动/几何变化，不能只测matchMedia=true；遵从现有全局规则。 |
| 性能/分页 | 200学生×100叶完整数据后端核全证据；浏览器分别记录首次事实页、下一页、证据打开真实耗时及返回total/offset/limit，不能减少输入/截断证据达目标。前端只分页渲染；cold/warm与计算硬件由独立后端记录，3秒目标不冒称恒达。 |
| 导出与门禁 | 稳定候选后check/test:api/build→E2E；实际DOCX打开/重解析材料/图片/公式/表格及学生版无答案解析/缺图失败。XLSX文本学号和空白分数、固定paper/叶/名单核对。shared renderer、模板验证、chat、备份/迁移影响由CTRL判适用，未执行逐项明示原因。 |

全链独立浏览器须新隔离上下文和本批脱敏样本，root核监听归属/构建身份且冻结后才执行；沿用用户前端的手动启动边界，不重试或绕过被拒启动。首败保完整stdout、exit、JSON、trace、截图和候选SHA，判产品/夹具后由root登记重冻再复跑。

## 8. 就绪与停写

准备已完成；实现前依赖 CTRL 冻结全部返回 DTO/constraints/itemStructure/job.kind+result/asset与artifact下载/模板名单时点/路由定位/题库返回上下文/通用提交hook归属。后续正式卡须列新模块可写范围，以及任何既有入口文件的唯一写入者。

本卡没有产品实现、构建或业务验收结果。交接后停止写入，等待共享契约冻结和 B4-F 正式任务卡。
