# TEACHING-LOOP B3 代码审查（2026-10-01）

**结论：定版清单自洽，但当前产品仍有 2 项 P1、8 项 P2。建议先修复本报告的问题，再进入 B4。** 两项 P1 分别阻断正常 AI 补题观察和合法缺考成绩确认，因此本次审查不能支持“无阻塞问题”的产品结论。原验收覆盖过的场景仍然有效；下面是其未覆盖输入和时序的新增实证。

审查对象为本地 `main@0f4b8cb190c2265d819b90e5d6df4e3954ad1906` 上的 B3 定版工作树。开工核对 `FROZEN-B3.json`：163/163 文件散列一致、0 漂移。本次没有修改产品代码、既有测试、B3 冻结件或权威进度文档，没有提交、推送、切分支或启动 B4。新增内容仅在本审查目录。测试全部使用临时数据根和受控模型，未操作正式浏览器会话。

| 编号 | 优先级 | 问题 | 主要定位 |
| --- | --- | --- | --- |
| B3-R01 | P1 | 初次补题的正常 claim 被当作接管，页面停止观察 | [jobs.ts](<H:/备份xuexi/智启课源/apps/web/src/features/question-bank/jobs.ts:220>) |
| B3-R02 | P1 | 文件缺考标记产生伪 missing，页面无法确认合法成绩 | [labels.ts](<H:/备份xuexi/智启课源/apps/web/src/features/assessments/labels.ts:328>) |
| B3-R03 | P2 | C/c 绕过重复列检查，正式成绩可写入错误分数 | [imports.py](<H:/备份xuexi/智启课源/apps/api/app/services/scores/imports.py:647>) |
| B3-R04 | P2 | 同一工作表修正表头行后，真实表头仍被当作学生行 | [service.py](<H:/备份xuexi/智启课源/apps/api/app/services/scores/service.py:763>) |
| B3-R05 | P2 | 有计分列但身份表头未识别，上传直接 500 | [imports.py](<H:/备份xuexi/智启课源/apps/api/app/services/scores/imports.py:488>) |
| B3-R06 | P2 | GB18030 CSV 被替换解码，姓名和状态原始证据乱码 | [tabular.py](<H:/备份xuexi/智启课源/apps/api/app/services/tabular.py:267>) |
| B3-R07 | P2 | recorded 修正携带空白/缺考/免考文本返回非契约 500 | [service.py](<H:/备份xuexi/智启课源/apps/api/app/services/scores/service.py:1646>) |
| B3-R08 | P2 | 创建施测的迟到响应绕过卸载守卫，覆盖新上下文选择 | [AssessmentsPanel.tsx](<H:/备份xuexi/智启课源/apps/web/src/features/assessments/AssessmentsPanel.tsx:172>) |
| B3-R09 | P2 | 失权整理执行轮仍能覆盖新执行轮 checkpoint | [service.py](<H:/备份xuexi/智启课源/apps/api/app/services/question_bank/service.py:1028>) |
| B3-R10 | P2 | 等待模型名额时已取消的任务，取得名额后仍调用模型 | [engine.py](<H:/备份xuexi/智启课源/apps/api/app/services/jobs/engine.py:175>) |

## B3-R01：首次补题观察窗口不符合真实任务协议

创建接口真实返回 `queued@attempt=0`，首次 claim 将 attempt 加到 1。`useQuestionJob.adopt` 使用精确窗口 `[0,0]`，正常执行即被判定为新尝试接管。探针用真实 HTTP 创建、真实 JobEngine 和受控 Provider 获得 `202 queued@0 → succeeded@1`（已落库 1 个候选），再将这两个真实响应交给实际 hook：一次 GET 后停止观察，页面仍为 queued@0、importId 为空、终态回调不执行。候选入口和失败结果均无法按正常创建链出现。

**修复验收：** 初次 queued 收据接受本轮首次 claim 的 `[N,N+1]`，已 running/terminal 收据按其实际状态处理，保留拒绝后续接管的守卫。测试必须使用真实创建收据的 attempt，覆盖首次成功、首次失败以及 N+2 接管，不能只用 queued(1)→terminal(1) 的替身。

证据：[真实后端响应](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B3-REVIEW-20261001/probes/ui_generation_fixture.json>)、[实际 hook 探针](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B3-REVIEW-20261001/probes/ui_generation_observation.test.tsx>)。

## B3-R02：文件标记覆盖整人次，前端却仍按原始空格计 missing

两名学生、三叶、施测出勤均 present。甲原表为 `(缺考,空白,空白)`，乙为 `(2,3,5)`。服务端按已确定的文件标记语义把甲整人次记 absent，预览 `missingCellCount=0`。前端只按施测出勤筛选 present、逐原始单元格计数，推导出甲的 2 个伪 missing。`ScoreImportReview.tsx:559` 强制勾选这项才能确认；实际组件发送该范围，真实 API 返回 422 `SCORE_ACKNOWLEDGEMENT_MISMATCH`。正确请求 `missing=null` 在同场景返回 200，但页面不勾选伪 missing 就禁用确认。

这不是已披露的“明细由前端推导”本身，而是推导与服务端相矛盾且没有可用的确认路径。接口 cells 只含映射分数列；本探针没有把学号/姓名列算成分数。免考覆盖整行也应纳入同一修复回归。

**修复验收：** 优先直接承认服务端权威预览范围；若暂时保持本地推导，必须应用与后端一致的文件缺考/免考整人次覆盖规则。真实 API + 实际组件分别覆盖缺考、免考、有效 0、真正 missing 的组合；不得为了通过而放宽后端承认闸门。

证据：[真实响应和两个确认结果](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B3-REVIEW-20261001/probes/ui_absence_fixture.json>)、[组件探针](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B3-REVIEW-20261001/probes/ui_acknowledgements.test.tsx>)。

## B3-R03：列身份在读取与校验时使用不同的归一化口径

列合法性和读格接受并大写归一 `c`，但重复/身份占用检查使用原字符串。原始小题分数为 `1/2/3`，将 Q1→C、Q2→c、Q3→E，PATCH 和确认均 200、无问题清单，正式矩阵被封存为 `100/100/300`，D 列的 2 分丢失。API 不能允许同一物理列以大小写区别对应两个叶子；同一缺口也影响身份列与计分列的占用比较。

**修复验收：** 在校验和持久化边界统一物理列身份，然后检查重复、占用和范围。C/c 重复及身份列大小写冲突均须 422、有列定位、零正式写入；合法小写列单独映射仍按明确契约正常处理。

## B3-R04：修改表头行没有重新提取数据行

两级表头 XLSX：第 1 行为“学号/姓名/小题得分”分组头，第 2 行才是“学号/姓名/Q1/Q2/Q3”，第 3、4 行是学生。教师在同工作表 PATCH `headerRow=2` 并完成 C/D/E 映射，返回 200，但 `rebuild` 只检查换工作表或原来没有映射，继续保留旧数据行 `[2,3,4]`。真实表头被当作待消歧学生，确认持续返回 422 `SCORE_ROW_UNRESOLVED`。前端有可编辑的“表头行（0=无表头）”，实际修改不能完成该校对动作。

**修复验收：** 影响数据行提取的映射变更从受管原件重建，按物理坐标保留仍适用的人工校正。上述文件修改后 rows 必须仅为 `[3,4]`；确认成功且两人的原分数不变。身份列变更也要核实提取行集合。

## B3-R05：自动识别不完整变成异常，阻断人工映射

UTF-8 CSV 表头为 `身份代号,学生称呼,Q1,Q2,Q3`。计分列能识别，身份列需要人工指定；当前条件只有“身份列均无且计分列也无”才返回 mapping=None。否则构造要求至少一个身份列的严格模型，抛未处理 ValidationError，上传返回纯文本 500，无法获得待映射批次和 PATCH 入口。

**修复验收：** 未识别身份列时仍创建可人工映射的批次，保留原始证据和候选提示。按真实 API 上传→指定 A/B 身份列→校对→确认走通；重复或歧义身份表头同样进入可恢复校对，不产生 500。

## B3-R06：成绩 CSV 解码损坏中文证据

成绩 CSV 使用 `utf-8-sig, errors='replace'`，与公共 CSV 读取及 API AGENTS 规定的 UTF-8/GB18030 支持不一致。同一个 GB18030 文件，公共读取正确显示“学号/姓名”，成绩读取成为 `ѧ��/����`；姓名、缺考和免考也无法可靠保留。实际上传返回 500，同时触发 R05；即使只修 R05，原始中文仍已在成绩预览中乱码。

**修复验收：** 复用公共严格解码策略，支持编码均失败时明确 422，禁止替换原字节后继续。UTF-8-BOM、GB18030 的中文身份/缺考/免考均要验证；受管原件与预览证据一致。

## B3-R07：recorded 分支只检查解析错误，没有检查解析状态

`parse_score_text` 将空白、缺考、免考解析成合法的非 recorded 状态，因此 `is_error=False`。修正服务随后以请求 `recorded` 和 `units=None` 插入，触发 DB CHECK。三种文本分别返回纯文本 500，违反错误信封和可定位校验契约。事务回滚有效，探针结束后仍只有原来的 1 个修订，没有部分成绩写入。

**修复验收：** recorded 分支须同时要求解析状态 recorded、units 非空；否则 422 + scoreText 定位。三种反例均零写入；数值 `0` 仍合法；不得靠放宽 DB CHECK 修复。

成绩 R03–R07 的完整请求、输出与定位见 [成绩审查证据](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B3-REVIEW-20261001/probes/scores_FINDINGS.md>) 和 [最终 JSONL](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B3-REVIEW-20261001/probes/scores_review_probe_output.jsonl>)。

## B3-R08：卸载检查发生在父级副作用之后

创建施测的 `run` 回调在返回 hook 之前执行 `setCreated/onSelectAssessment/onChanged`。创建在途时切班级或换原卷，面板随 key 重挂载；旧响应抵达时，hook 能拒绝过期结果，但父级选择已被旧回调更新。实际组件探针发起 POST 后卸载，延迟成功响应仍触发选择 old-assessment 和 onChanged 各 1 次，覆盖用户的新上下文。

**修复验收：** 请求回调仅返回结果，页面和父级副作用放在提交 hook 返回有效结果之后。卸载/换班/换卷后迟到成功和失败均不更新当前选择；正常创建仍只选择一次，不改变服务器幂等语义。

证据：[前端三项说明及命令](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B3-REVIEW-20261001/probes/ui_FINDINGS.md>)。

## B3-R09：任务失败 checkpoint 写入没有原租约 CAS

`_record_task_level_failure` 读 checkpoint 后无条件 `catalog.update_job`。隔离探针在读写间隙令租约过期、新 attempt=2 接管，再经真实 `record_organize_batch` 提交 1 个建议和 `nextBatchIndex=1`。旧 worker 随后写入旧 checkpoint，只留下 jobError：新 token/state 没被覆盖，但进度退为 0、suggestionIds 丢失，已提交建议仍在。后续恢复可能重复整理，不能仅凭任务终态的租约检查保护这些中间写入。

**修复验收：** 失败 checkpoint 的读改写也使用执行开始时的原 attempt/token、同一事务 CAS。旧持有者失权时零写入；新持有者的进度和建议 ID 保持一致。正常模型失败仍有可读错误。不得重新读取新 token 代替原租约。

## B3-R10：取消没有在取得模型名额后重新检查

共享引擎等待模型名额时已记录取消，Provider 尚未调用；释放名额后执行器仍发起模型请求，在返回后才检查取消（`generation.py:627/633`）。探针实测取消后的模型调用数为 1，最终 cancelled、发布批次数为 0。虽未写业务数据，却产生不必要的模型消耗，并继续占用唯一模型名额，延误其他任务。

**修复验收：** 取得名额后、启动执行器前核对本次租约与取消；实际调用模型前再次检查协作式取消。该场景必须 Provider 调用数 0、最终 cancelled、无发布；名额和心跳正常释放。检查共用引擎下知识点候选等同类执行器。

任务 R09–R10 的确定性交错、命令与结果见 [任务审查证据](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B3-REVIEW-20261001/probes/jobs_review_evidence.md>)。

## 验证与范围

- 迁移/任务既有窄测试：**56 passed、1 warning，exit 0**。
- 成绩既有窄测试：**33 passed、1 skipped、1 warning，exit 0**。跳过的是默认需 `ZQKY_RUN_SCALE_BASELINE=1` 的 200 人×100 叶基线；本次运行了默认 20 人×100 叶链，不把它冒称为重新验过 200 人基线。
- 独立成绩诊断 5 类（R07 含三种请求）、公共任务诊断 2 类均完成；真实 API 前端响应探针 2 条及实际组件/hooks 3 文件/4 例完成。**诊断测试断言当前缺陷存在；exit 0 不表示产品通过。**
- 未重跑全量 pytest、npm check、完整 E2E；未调用真实模型、Qdrant、Word/WPS，未做正式数据迁移。详细命令见 [EVIDENCE-COMMANDS.md](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-B3-REVIEW-20261001/EVIDENCE-COMMANDS.md>)。
- registry 导入和构造顺序、publish 原租约收敛、0007 重建/回滚/外键恢复在本次静态与窄验证范围内没有发现新 P1/P2。

## 不作为新增缺陷的观察与边界

1. 预览明细未进入服务端 DTO、无出勤校正端点、真实模型/Word/Qdrant 未执行等已披露边界，不重复计为 bug；R02 是已实现页面在合法输入上实际无法确认。
2. 封存闸门主要保护 draft→confirmed UPDATE，直接 SQL 插入 confirmed 空修订可绕过；当前服务没有这条写入路径，仅记录 DB 防御观察。模型指纹忽略端口/路径符合现有明确 baseHost 算法，不列新缺陷。
3. 原表含“总分=9”，三叶为 1/2/3 时上传和确认均成功且无警告，计算总分为 6。当前稳定契约只有计算总分，而任务卡存在“总分核对”表述；应统一是否还承诺核对教师原表总分。作为范围差异记录，没有算入上述 10 项缺陷。
4. 个别 absent 人次通过教师显式单格修正可成为 `(recorded,absent,absent)`，attendance 快照仍 absent。出勤与单格状态已被设计为分开存储，本审查不据此自动判错；后续学情模块必须使用冻结的单格四态作为分数证据，不能仅用 attendance 过滤掉 recorded 值。
5. 开工时 `apps/web/next-env.d.ts` 已有 `.next/dev/types → .next/types` 的构建生成差异，且不在 163 项定版清单内。本次原样保留，没有用恢复操作覆盖现场改动。

建议以这 10 项编号形成一轮 B3 修复候选，先通过独立反例复验，再按仓库要求运行受影响的回归检查；修复后另生成新冻结记录，保留原 B3 和本审查证据。
