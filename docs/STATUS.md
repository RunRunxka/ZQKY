# 当前进度、完整计划与项目交接

更新：2026-09-11。本文是唯一进度、后续计划和交接入口；目标与取舍见 [PROJECT_GUIDE](PROJECT_GUIDE.md)，操作规则见根 [AGENTS](../AGENTS.md)。历史日志不再与当前状态混排。

## 1. 当前结论

**整体前端复刻尚未完成，不能称为全部功能或真实服务已交付。** 当前学习问答是全站视觉基准；本次（2026-09-11）完成 H1 的知识库「文档导入→解析→索引」显式模拟闭环并通过独立验收，不顺带开发下表未来能力。

本次起点：分支 `codex/replica-review-20260908`，HEAD `93a2a06`；主聊天最近实现提交 `848b8b3`，主页外观提交 `723e20f`。起始未提交内容 `AGENTS.md`（多智能体协作段）、`.zcode/` 属于用户，本批保留并排除提交。实际最新提交用 `git log -5 --oneline` 查看。

| 模块 / 旧阶段 | 当前代码具备什么 | 尚未达到的交付边界 |
| --- | --- | --- |
| 公共壳 / S1 | 所有已有模块接入同一导航；本批根级保存折叠偏好、统一菜单尺寸与动画 | 全站页面内容还未完成视觉统一；侧栏通过不替代各模块验收 |
| 教案 | 本地规则填充、编辑、草稿恢复、Word/PDF 导出 | 非 AI 教案生成；新改动继续保留保存/打印/导出回归 |
| 学习问答、模型 / S2 | FastAPI 三协议 SSE、真实模型目录、连接/默认模型、服务端 .env 凭证；推理折叠与 LaTeX；会话本地保存 | 真实供应商未验收；主聊天仅普通真实对话，不恢复模拟模块 |
| 结果与复杂能力 / S3–S4 | 配置、过程、追问、产物渲染、消息操作等组件和历史数据展示仍在 | 旧模拟执行已移到测试；深度解题/出题/研究/可视化/Manim 等不能从当前主聊天发起，真实执行通道待接入 |
| 学习空间 / S5-A | 仪表盘、真实会话历史、题库、角色目录、CLI 模拟登记 | 来源定位、跨页联动、视觉/动画需完整核验；CLI 未执行真实程序 |
| 资料库/笔记 / S5-B | 文件/来源元信息登记、目录、笔记编辑保存与阅读写入；**2026-09-11 新增文档导入→解析→索引显式模拟闭环（registered/parsing/indexing/ready/error + 进度/取消/重试/刷新恢复/索引版本）并独立验收** | 知识导入→解析→索引**真实**服务未接；RAG 无真实服务；引擎/来源同步仍为登记或演示 |
| 书籍/课程 / S5-C | 14 类 block 分发、练习保存恢复、页内笔记、大纲/资源/进度/导出 | 部分 block 仅模拟形态；同步编译缺流式/暂停/恢复/失败；书籍聊天、课程学习会话未接通 |
| 阅读 / S5-D | R26–R31 有修复和回归记录；R32 已有事件驱动伴生模拟、材料模拟解析、草稿归属、手机面板 | 仍有会话 replaceState、增量强制回底待复核；媒体原视图、完整过程与引用、视觉/动画未全验收 |
| 写作/Whisper / S5-E | 文档自动保存、AI 预览/应用/取消/重试、撤销、版本恢复；Whisper 双席位 | AI 均为显式模拟，DOCX 导入/完整参考差距、视觉与动画待验收 |
| 伙伴/智能体 / S5-F | `/agents` 为规划状态页 | 伙伴列表/创建/详情/群组和任务执行页面待实现 |
| 精通 / S5-G | 尚无完整业务路由 | 路径/节点/会话/作答反馈/阶段交接/恢复待实现 |
| 记忆 / S5-H | 尚无完整业务路由 | 总览/冲突/图谱/L1/L2/L3 内容操作待实现 |
| 账户 / S5-I | 尚无完整业务路由 | 登录/注册/资料/用户管理与权限状态待实现 |
| 设置 / S6 | 外观、模型、MCP、Skills、关于五类已有 | 工作空间、解析、网络、记忆、智能体及模型用途等配置未完整整合；扩展管理仍为本地模拟 |
| 视觉/动画/总验收 / S7–S8 | 学习问答有局部历史证据，本批补侧栏切换验证 | 全站三视口、完整动画、数据兼容、最终报告尚未完成 |

逐页状态只维护在 [页面矩阵](replica/PAGE_MATRIX.md)；AI 能力、动画分别看 [AI 矩阵](replica/AI_INTERACTIONS.md)、[动画矩阵](replica/MOTION_MATRIX.md)。路由可达、类型存在、组件保留都不能直接计作完整能力；不给缺少统一验收分母的“整体完成百分比”。

## 2. 需要优先复核的现有问题

以下是本次静态源码核查发现，尚未运行对应业务复现；不自动推翻或放大历史修复结论。

| ID | 位置与事实 | 后续验收要求 |
| --- | --- | --- |
| H-R1 | `ReadingWorkspace.tsx` 切会话/首次发送仍写 replaceState；流式增量直接设置 scrollTop | 核对浏览器前进后退与会话身份；手动上滚不强制回底，切会话/卸载停止旧任务 |
| H-R2 | `NotebooksSection.tsx` 来源链接仍带 `?mode=mock`；`QuestionBankSection.tsx` 用 messageId 拼会话地址 | 以真实 sessionId/messageId 关联和旧数据兼容验收；不恢复模拟运行、不清旧数据 |
| H-R3 | 14 类 BookBlock 已有类型与呈现，但 interactive/animation 等为模拟形态 | 对照参考逐类补配置、交互、失败与保存；不能仅靠类型数量验收 |
| H-R4 | `apps/api/app/api/v1/capabilities.py` 描述仍称凭证仅进程内 | 后续 API 小批校正状态文案并跑后端回归；当前真实持久化契约以 API.md 为准 |
| H-R5 | `ChatWorkspace.tsx` 附件拒绝提示仍提及切换模拟模式 | 后续聊天说明小批删除无效指引，保留附件/草稿；不得因此恢复模拟执行 |
| H-R6 | `courses-store.ts` 两处 `readKnowledge()`（`listResourceCandidates`/`resourceHref`）无 try/catch，经 `CourseDetail` 的 `useMemo` 渲染 | 知识库目录损坏时课程详情可能渲染中断（改动前即如此，非本批新增）；后续课程小批加错误兜底并回归，不标已修 |

历史审查与修复链见 [阅读 review](reviews/READING_REVIEW_2026-09-08.md)、[有界差距审计归档](archive/REVIEW_HISTORY.md#snapshot-gap-audit-20260909)。不要再从旧“R26–R32 全未修”开始重复开发。

## 3. 完整实施计划 v1

总体目标是全部必需产品前端、AI 交互和参考动画完成。全站外观以当前学习问答为准，各业务信息结构与功能对照固定 DeepTutor；主聊天真实执行与新模块显式模拟的边界不混用。以下为未来计划；**H0（2026-09-10）与 H1 的知识库部分（B-H1-KB，2026-09-11）已完成**，H1 其余项仍未开始。

每批先在三矩阵补该范围的参考组件、入口/详情/弹窗、状态、数据与动画来源，再改代码。每批采用“实现者自检 → 稳定候选独立验收 → 总控更新证据与本地提交”；共享文件、构建目录、端口和报告由总控分配单一负责人。

| 顺序 / ID | 范围与依赖 | 具体交付及验收门槛 |
| --- | --- | --- |
| H0 已完成 | 当前视觉基准、导航、文档 | 修跨壳折叠重置与旧 CSS 覆盖；桌面双向切换逐帧/当前菜单，手机焦点/遮罩/关闭，保留独立学习记录；交接入口统一 |
| H1 既有模块收口（知识库部分已完成） | H0；对应 S5-B/C | **知识导入→解析→索引（B-H1-KB，显式模拟闭环）已完成并独立验收**；仍待做：书籍 compiling/paused/error 与流式生成，书籍聊天和课程学习会话；失败/取消/重试/保存/刷新恢复齐全。复用已有14类分发与练习保存 |
| H2 数据与交互复核 | H0；可按文件边界与 H1 并行 | 闭环 H-R1–H-R6；补阅读媒体原视图与来源/伴生过程；审写作预览应用、版本恢复、Whisper 状态；复核学习空间/笔记/题库联动和 S3 产物来源。损坏读取、配额、多键失败、过期任务不丢数据 |
| H3 伙伴与智能体 | 共享任务/事件/配置契约稳定；S5-F | 列表/新建/详情/群组/渠道/会话；智能体任务过程、工具、产物、取消/失败重试与历史恢复；配置统一进入设置 |
| H4 精通与记忆 | H3 事件及跨页引用契约；S5-G/H | 路径/节点/学习会话/答案反馈/阶段交接/进度；精通新轮规则区别普通 ask_user。记忆总览/冲突/图谱/L1/L2/L3 列表详情、编辑与引用；配置进设置 |
| H5 账户与完整设置 | 配置/权限契约先定；S5-I/S6 | 登录/注册/资料/管理的校验、加载、失败、权限视图；本地身份明确模拟。设置分类连续内容、搜索/锚点/高亮/历史同步、保存撤销校验、全量配置与业务真实联动。MCP/Skills 只在设置管理 |
| H6 全站视觉与动画 | 各模块实施时同步做，H1–H5 后集中补缺；S7 | 所有首页、列表、详情、弹窗沿用当前学习问答的蓝色、字体层级、间距、控件和导航；业务工作区保留必要结构。1440×900、1920×1080、390×844、主题、减少动画、键盘/焦点、长文本/空态/错误无溢出；录制并查看开始/过渡/结束、快速中断与退出 |
| H7 最终交付 | 必需前端条目和阻断缺陷闭环；S8 | 工程全量检查、相关 API/HTTP 链路与浏览器回归；三矩阵逐条证据、旧数据兼容、模拟/真实边界；满足门槛后才创建 FINAL_ACCEPTANCE.md，不预写“完成” |

**真实服务轨道 T1（与上述计划协同，单独验收）：** 现有三协议用实际供应商验证末包前首段可见、reasoning、停止、错误/重试、模型选择与历史恢复；凭证只由服务端读取，报告不含密钥。为主聊天复杂能力补真实执行事件与后端接口，真实服务缺失时明确不可用，禁止恢复聊天模拟。新模块解析、MCP/Skills、STT、账户等服务可分批接入，已允许的显式模拟前端闭环与真实后端接通分别记录。外部服务不可用时可继续其余前端，不把 T1 标为通过。

**自有规划轨道 T2：** `/papers`、`/question-bank`、`/templates` 是目标项目现有规划入口，未纳入53项参考清单。先核对它们与学习空间题库、书籍练习、现有教案模板的关系，再单独确定任务与验收范围；保留入口，不擅自移除，也不混入本次实现。

**停止/通过规则：** 新的数据丢失与错误归属问题先修再扩展；界面占位、同步假成功、只有截图文件、只通过 build 均不能作为完整验收。阶段通过后继续已授权范围；新会话按实际用户指令选任务，不将本计划自动当成全项目执行授权。

## 4. 本批改动与验证（2026-09-11，B-H1-KB）

任务 `B-H1-KB`：复刻参考 DeepTutor 的知识库「文档导入→解析→索引」前端闭环。参考只读 `F:\DeepTutor` v1.6.5 / 42fab3cf429a1fbf36b257ab8d116a3814964202；取证、契约、任务卡见 `_work/kb-h1/`（reference-notes.md、CONTRACT.md）。真实 PDF 解析与向量检索服务未接入，本批为**显式模拟**并与真实服务验收分开记录，不恢复主聊天模拟。

- `services/knowledge-catalog.ts`：新增 `KbDocStatus`（registered/parsing/indexing/ready/error）、`KbDocProgress`、`KbIndexVersion` 与 `KnowledgeEntry.indexVersions?`；`readKnowledge()` 对旧数据内存归一化（`status ?? 'registered'`、`indexVersions ?? []`）**不写回**，非法/损坏 JSON 抛友好错误且不覆盖原数据；新增 `updateKbDocument`、`addKbIndexVersion`、纯函数 `kbPipelineSummary`。
- `services/knowledge-ingest.ts`（新）：显式模拟流水线 `simulateKbDocIngest / simulateKbIngestAll / cancelKbDocIngest / cancelKbIngestAll / resumeKbIngests`，阶段 registered→parsing→indexing→ready、确定性 `parsedChars/chunks`、全部就绪按 `(docCount,chunkCount)` 去重追加索引版本；与 `features/reading/reading-ingest.ts` 同构，持久化仍走单一 knowledge 目录。
- `features/knowledge/KnowledgeBaseDetailSection.tsx`、`KnowledgeBasesSection.tsx`：KB 级与逐文档状态徽标、进度条（`transition-all duration-300`，参考有）、取消/重试/「全部解析并索引」/「重建索引」、索引版本列表；登记后自动模拟；顶部与列表 banner 如实标注「显式模拟/真实服务未接入」，保留「未解析 · 未索引」「还没有索引版本」等既有文案。详情页挂载 `resumeKbIngests` 做刷新恢复；读取失败如实显示错误（含 `!kb` 早返回分支，修 F1）。
- 测试：`knowledge-catalog.test.ts`、`knowledge-ingest.test.ts`（新）覆盖归一化不写库、状态机、去重、取消/失败/重试/resume；`tests/e2e/knowledge-notebooks.spec.ts` 保留既有断言并新增自动解析、取消、失败重试、刷新恢复、旧数据兼容、目录损坏报错。
- 顺带修复过期断言：`tests/e2e/books-courses.spec.ts` 的 `/papers` 导航用例原假定项目导航默认收起，与 H0 引入的默认展开（`NavigationPreference`）冲突；改为兼容两种状态。该失败由本批全量 e2e 暴露，非本批代码引入。

| 本次检查 | 当前结果与证据 |
| --- | --- |
| typecheck | 通过（exit 0），`_work/kb-h1/typecheck-r3.log` |
| lint | 通过，0 警告（exit 0），`_work/kb-h1/lint-r3.log` |
| 正式单测 | 260/260、41 文件通过（含新增知识库 18 项）；`NODE_OPTIONS=--no-experimental-webstorage npm run test:unit`，`_work/kb-h1/unit.log` |
| build | 通过（exit 0），`_work/kb-h1/build-r3.log` |
| 浏览器 e2e | 80/80 通过（隔离端口 5174，`_work/kb-h1/e2e-full-r2.log`）；knowledge 单 spec 10/10（`e2e-knowledge-r3.log`）；books-courses 6/6（`e2e-books-r1.log`） |
| 独立验收 | `pass`：全范围（B-H1-KB-V1）+ 修复增量（B-H1-KB-V2），证据 `_work/kb-h1/verify/`（含损坏数据探针、去重证伪、截图） |
| 后端/真实供应商 | 未改 `apps/api`，未运行 test:api / test:chat，未调用实际供应商；解析/索引为显式模拟，真实服务未验证 |
| 未执行 | 1920×1080 / 390×844 知识库视觉、减少动画专项、真实解析/向量检索；均保持未验证 |

修 F1 说明：损坏目录原本在详情页会停在「正在读取知识库…」，`readKnowledge` 现对非法 JSON 抛统一友好错误，详情页 `!kb` 分支在有 `error` 时渲染错误 banner，原数据不被覆盖；由独立验收 V2 复核通过（探针 + e2e）。

### 历史批次（2026-09-10，H0）

任务 H0，协调员独占公共壳、权威文档、Git 和运行资源；独立审计者只读审查源码/文档及导航候选，没有改文件或启动服务。

- `NavigationPreference` 在根布局持有折叠状态，页面壳首帧直接沿用；保留 localStorage 偏好、存储失败仍可操作与实例隔离。
- 公共侧栏样式由根布局一次载入；菜单宽度/间距优先级覆盖教案遗留规则；桌面与手机导航字体一致。220/56px 与 200ms 折叠规则收归公共壳，聊天删除重复声明。
- 保存前导航守卫、手机 dialog、学习记录独立列、各业务内容与后端实现保留原有功能。本批验证软导航过程与刷新后恢复，不声称刷新水合前首帧完全无变化。
- README、PROJECT_GUIDE、STATUS、NEXT_SESSION_START 明确各自职责；旧 STATUS、旧续做提示、GAP_AUDIT 原文合并入现有历史文件并记录哈希。同步路由/API/目录规范、三矩阵和多智能体提案里的过时说明，不再新增交接计划副本。
- 修正“阅读未开始”“书籍仅4类”“写作/Whisper仍规划”“主聊天双模式”等冲突；未复测的历史成绩标明日期和范围。

| 本次检查 | 当前结果与证据 |
| --- | --- |
| typecheck | 通过，`_work/handoff-20260910/verify-typecheck.log` |
| lint | 通过，0 警告，`_work/handoff-20260910/verify-lint.log` |
| 正式单测 | 247/247、40 文件通过；含壳重挂载与存储失败/实例隔离。Node 26 需 `NODE_OPTIONS=--no-experimental-webstorage`，未设时 78 项因 `window.localStorage` 未定义报错，与本批代码无关 |
| build | 通过，`_work/handoff-20260910/verify-build.log` |
| 浏览器 | 25/25 通过（`verify-e2e.log`）：软导航 1440/1920 逐帧不跳变、跨板块几何一致、手机抽屉焦点/遮罩/关闭、各业务壳 200ms 与减少动画、回归 chat-home/lesson-plan/navigation/sidebar-chat-fixes。隔离端口 5174，产物 `_work/handoff-20260910/browser*` 与 `docs/qa/handoff-20260910/` |
| 文档校验 | 通过，13 文件 93 链接 3 快照 0 错误，`verify-docs-check.log` |
| 后端/真实供应商 | 本批未改后端执行代码，未运行 test:api / test:chat，未调用实际供应商；历史结果不能替代本次验收 |

历史证据分开保留：2026-09-09 存储加固候选单测241、e2e102；主页复刻候选相关e2e65；侧栏/真实聊天修复候选单测245、API88、相关浏览器43项最终逐例通过、隔离HTTP链路9项。它们属于不同候选，部分模拟用例后来已删除；详见 [旧进度快照](archive/DELIVERY_HISTORY.md#snapshot-status-20260910)。

## 5. 接手操作与下一动作

1. 从根 [README](../README.md) 按顺序读规则、目标、本文和三矩阵；核对当前 HEAD/status，保留用户未提交内容。实际源码优先于历史“已完成”。
2. 运行入口：前端 `npm.cmd run dev` → `127.0.0.1:5173/chat`；真实 API 首次 `npm.cmd run setup:api`，然后 `npm.cmd run dev:api` → `127.0.0.1:8000`。设置保存连接/模型，Key 在忽略的 `apps/api/.env`；手动改文件后重启 API。详见 [API](API.md)。
3. H1 知识库「导入→解析→索引」已完成并独立验收（B-H1-KB，2026-09-11），下一步建议做 **H1 剩余**：书籍 compiling/paused/error 与流式生成、书籍聊天、课程学习会话；先读 `books`/`courses` feature、`books-store`/`courses-store` 与固定参考，列完整状态及失败回滚用例。或按 H2 闭环 H-R1–H-R6。若复现数据丢失或错误归属，则先修对应阻断问题。不要重做阅读演示合并、书籍14类分发或写作已有功能，也不重做已完成的知识库流水线。
4. 每个任务登记 ID/版本/负责人/可写文件/依赖/验收/产物路径；默认总控独占共享契约和文档。可用 [协作提案](MULTI_AGENT_COLLABORATION_PROPOSAL.md) 的任务卡，不照抄其历史断点。
5. 检查 `npm.cmd run typecheck`、`lint`、`test:unit`、`build`；typecheck/build 顺序执行，浏览器使用隔离数据/5174，相关 API 再跑 `test:api`/`test:chat`。Node 26 单测按需先设 `$env:NODE_OPTIONS='--no-experimental-webstorage'`。不要改用户真实浏览器草稿或依靠旧构建验收。
6. 写清实际命令、结果、首败/重跑、未执行原因及下一动作；显式暂存本批文件并检查敏感数据后本地小提交，不推送/部署。检查 next-env.d.ts 是否仅被类型生成改写，不夹带无关文件。

[新会话启动文本](replica/NEXT_SESSION_START.md) 只说明如何接手，不复制阶段计划。未达到 H7 前不生成最终完成报告。
