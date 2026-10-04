# B4 前端代码复查与 B5 接入依据

日期：2026-10-03（北京时间）。只读复查生产源码；新增文件仅限本目录。未启动服务、浏览器、构建、B5；未访问正式环境、真实草稿或凭证。

结论：本范围发现 **2 项 P2**，共 **3 个独立正确行为断言失败**；既有相关 **4 文件 / 27 单测通过**。这不否认原 B4 的历史门禁结果，而是补充其未覆盖的编辑边界。

## FE01：原包重放重新捕获编辑代次，覆盖后续输入（P2）

练习保存：[PracticeEditor.tsx:69](../../../../apps/web/src/features/practices/PracticeEditor.tsx:69) 至 77 行。每次 `saveDraft()` 都把当前 `editGeneration` 当成此次提交的代次；未知重试时，`useFrozenSubmission` 实际发送的是第一次冻结的旧包，而外层 `generation` 已经变成后续编辑代次。两者相等后错误载入旧响应、清除 dirty，并重新放开审核。

独立组件探针：保存整题/叶满分 2；请求等待期间改成 3；首次返回 status 0；重试后确认两次 API 调用完全深等、仍发分值 2 原包；成功 ACK 后页面分值却回到 2。期望保留 3 的断言失败。探针采用受控成功 ACK，证明请求/组件边界；没有声称真实后端的每种未知结果都会返回 2xx。第一次未被服务端接受、第二次接受原包同样是合法触发条件。

教师备注同因：[LearningAnalysisWorkspace.tsx:213](../../../../apps/web/src/features/learning-analysis/LearningAnalysisWorkspace.tsx:213) 至 216 行。发送备注 A，等待期间继续写 B；未知后重试原 A 的成功收据；`sentGeneration` 在重试时等于当前 B 代次，导致 B 被清空。独立断言收到空字符串，而不是 B；两次请求载荷深等。

关闭标准：提交首次冻结时同时绑定原编辑代次，并跨未知重试保留；ACK 只确认原包，不把后续编辑标为已保存/已发送。后续分值、约束、选题、节点结构和备注均保持，未再次保存前禁止审核；补成功、明确失败、未知原包重放与切换/卸载矩阵。不能只比较重试按钮点击时的代次。

## FE02：切换练习或历史会无提示丢掉未保存草稿（P2）

[PracticeEditor.tsx:39](../../../../apps/web/src/features/practices/PracticeEditor.tsx:39) 向上仅报告 pending/unknown 锁，不包含 dirty 或未保存草稿状态；[PracticesWorkspace.tsx:49](../../../../apps/web/src/features/practices/PracticesWorkspace.tsx:49) 列表直接换 `setId`，62 行按该身份重新挂载；59 行历史切换也直接换 `fixedId`。编辑 state 未被保存、缓存或确认放弃。

独立工作区探针：原练习满分 1 改为 5（未点击保存）；点击第二练习，确认已显示第二练习；再返回原练习，分值变回 1，全程零 PATCH、无确认放弃交互。期望保留 5 的断言失败。此证据是工作区内列表切换的真实组件行为，不是假装浏览器路由导航已执行。

关闭标准：对列表切换、历史/当前工作区切换、跳转补题/来源报告及公共导航统一处理未保存状态，允许明确保存或明确放弃；保存失败/CAS 冲突/未知结果保留输入和当前身份。可以建立按练习/修订隔离的恢复缓存，但不得混用当前服务器视图或真实本地草稿。不能永久禁用切换却没有保存/取消出口。补真实浏览器用例。

## 运行证据与限制

Windows 根目录；每次测试均设置 `NODE_OPTIONS=--no-experimental-webstorage`。

```powershell
npm.cmd exec -- vitest run --config docs/qa/TEACHING-LOOP-B4-REVIEW-20261003/frontend/vitest.config.ts
npm.cmd exec -- vitest run --config docs/qa/TEACHING-LOOP-B4-REVIEW-20261003/frontend/vitest-regression.config.ts
```

- [probe 源码](practice-boundaries.test.tsx) 与 [最终日志](probes-final-v2.log)：3 failed，exit 1；失败均是用户输入保留断言，不是框架错误。
- [窄回归日志](regression.log)：4 文件 / 27 passed，exit 0；learning-analysis、practices、公共任务 hook 与任务 API。
- 首轮 [probes.log](probes.log) 保留：一条实际产品断言失败，另一条测试选择器没考虑无障碍名称空格；仅修正探针选择器后 [probes-final.log](probes-final.log) 两项产品断言失败。追加教师备注探针后的最终 3 项结果在 v2 日志，不覆盖首轮。
- [保全核对](AUDIT.json)：r21 前端 451 文件＋Python b4 契约 1 文件，**452/452 无漂移**；HEAD 仍 `main@6aeb57280f6a7e0d7391cad4d150745479ea58ec`；next-env 原 SHA `0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc`。
- 未执行：浏览器/E2E、三视口像素、全量 check/API、真实模型、Word/WPS、Qdrant、正式迁移；此次是只读针对性复查，未复用历史结果冒称本轮重跑。

固定成绩显式选择、人次选择、班名缺失说明、分页后端事实、读请求身份取消、练习审核与导出身份核对、未知转换原包、公共任务 attempt 窗口等代码和相关现有测试已读取。本范围未对这些点发现新的可复现缺陷，不能由窄回归推断全部场景无缺陷。

## B5 的已有能力与增量落点

以下为设计建议，不构成本轮启动 B5 授权。

1. **保留现有教案编辑器。** [types.ts](../../../../apps/web/src/features/lesson-plan/model/types.ts) 的 `LessonPlanData` 为原内容模型；`DraftEnvelope.schemaVersion=1` 和本地键 `zhiqikeyuan:lesson-plan:v1` 不改。已有单稿本地恢复、600ms 串行写入/失败保留、导航 flush、撤销重做、规则填充、JSON、模板 Word 和打印应全部保留。服务器文档身份/CAS/学科/班级/来源报告/固定练习链接属于外层元数据，不能塞进旧 v1 内容并宣称兼容。
2. **现有填充不是 AI 后端。** [EditorContext.tsx](../../../../apps/web/src/features/lesson-plan/model/EditorContext.tsx) 默认 `RuleBasedFillProvider`；`HttpFillProvider` 只是可选 host adapter，旧 `/lesson-plans/fill` 没有真实后端。新生成使用 FastAPI 教案任务＋候选差异＋字段应用，不把旧 parse/merge 当成持久化 AI 建议应用。
3. **服务器保存需要独立会话 ACK。** 既有 `DraftRepository.save` 返回 void、`createDraftWriter` 只处理本地 envelope 的串行保存，不包含服务器当前 CAS 或不可变修订 ID。可以复用 writer 纪律，但必须增加按 documentId 隔离的服务会话与恢复缓存、首次原包 submissionId、serverRevision/revisionId、sentEditRevision/acknowledgedEditRevision。只保存 ACK，不 hydrate 较旧回执；409 停自动写入并保输入。新服务器缓存不能写旧单稿键。导入旧稿是教师明确操作，校验 v1 并补上下文，成功后旧本地字节仍保留。
4. **来源使用 B4 固定事实。** 冻结 `analysisRunId`、该 run 的 `scoreRevisionId/paperRevisionId/ruleCode/inputHash`、明确班级/知识点范围和已审核 `practiceRevisionId`。B4 学情前端现已完成，F30 学情部分/F10 练习部分无需再次建模块。模型输入取后端固定事实聚合，而不是前端表格、active 成绩、当前名单、当前知识点名字或最新题修订。`FrozenParticipant.className` 是 null 且明确“该成绩未记录班名”，不能用当前班名伪造历史快照。
5. **过程结构不能破坏旧内容。** 原 `process` 仅 `{id,stage,design,secondary}`；AI 的环节分钟/目标/活动/检测/教材证据/练习关联放在候选外层结构化说明，经校验映射到原字段。`exercises` 是字符串，可有说明文字，正式练习身份与富内容留外层固定链接；不直接把 RichContentV2 或 DOCX blob 写成旧字符串或嵌入旧 schema。
6. **生成和应用分开。** flush 服务器保存后冻结 documentId、baseServerRevision、baseRevisionId、baseEditRevision、报告与模型快照，复用公共 teaching `lesson_generation` 六态/租约引擎。生成期间可编辑，但这会使建议过期；切文档、输入条件变化、模型变化与迟到回执需绑定原代次。仅允许 `coreCompetencies/keyPoints/teachingDesign/process/exercises`，教师显式选字段，标题/课时/课型/反思不被模型修改。apply 同库同事务校验固定 base、选字段白名单、过程时长/证据/练习归属、追加不可变修订和终结建议；部分应用后未选字段不自动继续应用，撤销是新编辑与新保存。客户端应用失败保留原稿。
7. **不把现有AI承诺扩大。** 新教案真实调用由配置的后端 Provider 完成；自动化可用受控 Provider，但必须单列真实教学质量 not_run。模型只拿必要的匿名班级聚合与固定知识点/教材/题目依据，不直接序列化含学生姓名、学号、人员 ID、整张成绩矩阵的 B4 report。报告原事实仍是确定性规则，不让 LLM 改写学情结论。
8. **原分期已过期。** v2 计划的 T90/F30 教案章节（937–1088 行）可作为增量依据；原 B5/B6 表仍把已完成学情/练习前端列为未来任务，新提示词应按当前 B4 状态重排，只新增 T90 与 F30 教案及必要 CTRL 集成。当前规格内未找到 T100 任务，不应当作已冻结任务 ID；如需新验收任务由总控明确编号/归属/标准。

B5 验收必须含：旧稿读取失败不覆盖、导入原稿不删除、快速导航/迟到回执/保存失败、相同 submissionId 原包重放、409/422 保输入、异步保存期间连续编辑、unknown 后保存重放后续编辑仍在、生成期间编辑与跨文档旧结果拒绝应用、只选字段改变、过程总时长、旧 Word/打印/JSON/规则与撤销重做、练习固定版本历史保留。浏览器测试在隔离上下文中执行；真实 Word/WPS 人工排版未执行时明确列出。
