# 前端复刻实施交接

## 当前入口：S5-D 已完成（2026-09-08），按用户指令暂停，等待指示后进入 S5-E→I →S6→S7→S8

S5 批次 D「沉浸阅读」完成。全量回归：正式单测 **206/206**（197 基线 + reading-store 9 项）、全量 e2e **92/92**（87 基线 + S5-D 新增 5 项 `tests/e2e/reading.spec.ts`，产物默认 `test-results/`）、typecheck/lint 0 警告、build 通过（30 个路由含 /_not-found 与 /[planned]，其中 5 个为 S5-D 新增）。**用户指令：S5-D 完成后暂停，不自动进入 S5-E。**

S5-D 实施要点（后续批次不得回退）：
- **服务层**：新建 `services/reading-store.ts`（localStorage `zhiqikeyuan:reading-materials/workspaces/annotations/bookmarks/sessions` 五库 + `zqky:reading` 事件订阅）。材料仅文本形态（`sourceKind:'text'`，参考的 PDF/EPUB/网页/媒体解析走服务端——不接入，新建表单与页面描述均显式标注）；批注按 quote 锚定（对照参考 TextQuoteSelector 思路，无几何 rect，原文变更时导航点击提示"无法定位"）；伴生回复 `simulateCompanionReply` 为本地确定性模板并显式【模拟回复】；`organizeNotes` 为本地模板聚合；`sendToNotebook` **真实写入 notebook-store**（跨页联动）。`notebook-store.ts` 新增 `createNotebookRecord` 写入端（校验目标笔记本存在）。
- **/reading 集合列表**：卡片（材料/会话计数）、演示载入幂等（1 工作区+2 材料+批注/书签/会话各 1，`loadDemoReading`）、新建/删除确认；链接 `打开阅读集合 <title>`。
- **/reading/materials**：全部/未分配双页签、新建文本材料（标题+正文，`# ` 行按标题渲染）、分配到集合（无候选显式空态）、删除确认（级联清批注/书签/工作区引用）。
- **/reading/[workspaceId] 三栏工作区**：材料 Tab 条（切换/移除 X/添加 Modal/材料库跳转）+ `reading-layout` grid。左栏 `SourceNavigator` 大纲/书签/批注三页签（大纲解析 `#{1,4}` 行 locator=`h-<行索引>`，与演示书签 `h-4` 一致；点击 scrollIntoView；批注/书签可删除）。中栏 `ReaderPane`：标题层级渲染（#/##/###→h1/h2/h3）、段落 `data-loc`、批注 quote 在段落内渲染为 `<mark data-annotation-id>`（五色 MARK_COLORS）、滚动 300ms 节流保存 positionPct + 进入恢复上次位置、选区浮条（高亮五色/笔记 textarea/书签/问 AI，`onMouseDown preventDefault` 防浮条点击丢失选区）。右栏 `CompanionPane`：会话 select 切换 + 新会话、发送→appendMessage+simulateCompanionReply（Enter 发送带 isComposing 守卫）、首条消息后会话标题取前 24 字、**会话创建/切换用 `history.replaceState` 改写 `/sessions/<id>`（Next 不感知，组件 state 驱动，无闪烁）**、深链 routeSessionId 首次同步（无效提示并回退最近会话）、`zqky:reading-ask` 事件把选中文本预填输入框并携带为消息 quote。
- **路由**：5 个 page.tsx re-export（`/reading`、`/reading/materials`、`/reading/[workspaceId]`、`/reading/[workspaceId]/sessions`、`/reading/[workspaceId]/sessions/[sessionId]`）；`navigation.ts` reading 升 ready（教学工作台组，BookOpen）。
- **有意差异/边界（均显式标注）**：材料解析/转录不实现（仅文本）；伴生 AI 为模拟（无真实模型/检索）；整理笔记为本地模板聚合（页面标注"未接入模型整理"）；课程作用域仅 `?course=` 展示（会话课程标记未接入）；参考的 ReadingContext 跨 URL 保活因本实现 store 驱动状态而天然满足，省略。

S5-D e2e 排障记录：
- navigation.spec 两处随实现状态适配：`plannedRoutes` 移除 `/reading`、导航名清单加入"沉浸阅读"。中途一次 Edit 工具报成功但 plannedRoutes 修改未落盘，导致复跑仍失败——**用 grep 复核文件内容后才算改完，不以工具成功回执为准**。
- 伴生会话消息断言不能用 getByText（select option 的会话标题与消息文本同串，strict mode 冲突），改 `.reading-msg` filter 定位；书签条目按钮与删除按钮 aria-label 同含 quote，用 `.first()`。
- 弹窗「关闭」按钮与 Modal 头部「关闭对话框」图标按钮同字，需 `exact: true`。

下一条动作：**已按用户指令暂停**。恢复后：S5-E 写作/whisper → F 伙伴/智能体 → G 精通之路 → H 记忆 → I 账户 → S6 设置整合 → S7 视觉动画三视口 → S8 最终验收交付 FINAL_ACCEPTANCE.md；每批参考源码研究先行，不等待批次间授权（除非用户另行指示）。

## 历史：S5-C 已完成（2026-09-08），正在连续执行 S5-D→I →S6→S7→S8

S5 批次 C「书籍与课程」完成。全量回归：正式单测 **197/197**（188 基线 + books-store 5 项 + courses-store 4 项）、全量 e2e **87/87**（81 基线 + S5-C 新增 6 项 `tests/e2e/books-courses.spec.ts`，产物 `tests/.e2e-output-20260908-s5c/`）、typecheck/lint 0 警告、build 通过（20 路由含 5 个新路由）。

S5-C 实施要点（后续批次不得回退）：
- **服务层**：新建 `services/books-store.ts`（localStorage `zhiqikeyuan:books`：Book/Chapter/Page/Block/阅读进度内联一档；演示书编译产物确定性构建，页 id=`<bookId>-p<n>`）与 `services/courses-store.ts`（localStorage `zhiqikeyuan:courses`：大纲/资源/颜色/归档；资源候选实时聚合本地知识库+笔记本+书籍目录——真实跨页联动）。
- **书籍状态机（显式模拟）**：draft（创建即生成模拟提案）→确认提案→spine_ready（章节登记）→确认大纲并编译（同步模拟，每章 2 页，含 section/text/callout/quiz 四类 block，内容显式"模拟生成"）→ready；重建=重新模拟编译并清进度。pause/resume/health 属长流水线特性，不适用（无 WS 流水线），如实记录。
- **/books**：统计条（共/进行中/可阅读/章节）、演示载入幂等、新建 Modal（重名拒绝 `BookValidationError`）、状态徽标+阅读进度条+状态化 CTA（继续创建/确认大纲/继续阅读）、删除确认；就绪书卡片链接 `打开书籍 <title>`。
- **/books/[bookId]**（hub-and-spoke 单组件 `BooksRoute.tsx`，对照参考三路由 re-export 模式）：按状态分流视图；无效 id 显式报错；就绪书无页码时自动续读（当前页→首页 `router.replace`）。
- **阅读器**：Block 分发渲染（14 种中的 4 种子集，有意缩减见矩阵备注）；上一页/下一页+←/→ 键盘翻页；书签切换（侧栏"签"标记）；打开即 `markVisited` 登记已读；章节 rail 显示 visited/bookmark；练习块本地判定（正确/错误+解析），**不持久化作答**（参考为服务端 attempt，已显式标注）；`PageReader key={pageId}` 重置页内状态；无效页码"章节页不存在或已被重建"；导出 Markdown 真实下载。
- **/courses**：进行中卡片+已归档 `<details>` 折叠；新建（名称/简介/颜色）。**主导航入口按参考隐藏**（`hidden: true` ready 项，路由可达；参考 nav-entries.ts L75-77 注释同款决定）。
- **/courses/[courseId]**：大纲（textarea"标题 | 主题1, 主题2"逐行编辑、保存重建并重置 covered、covered 学员手判勾选、下一单元高亮）；资料（附加/移除，候选=本地目录实时枚举，目标消失显"不可用：目标已删除或未载入"，可跳转 /knowledge-bases/<name>、/notebooks/<id>、/books/<id>）；约定 instructions；编辑/归档/恢复/删除确认。**课程学习会话未接入**：参考按 session.preferences.course_id 过滤，聊天侧未携带课程标记——页内横幅如实标注（延后批次决策，未伪装）。
- **导航**：`books` 升 ready 进侧栏（教学资源组，图标 BookMarked）；`courses` ready+hidden；navigation.test 就绪清单与隐藏断言已适配。

S5-C e2e 排障记录（重要，避免重蹈）：
- **悬挂下载对象压垮 headless Edge**：`waitForEvent('download')` 拿到 Download 后若不 saveAs/cancel，下一个用例 `browser.newContext` 报 "Target page, context or browser has been closed"（稳定复现、与用例顺序无关的触发点在下载步骤）。处置：`await download.saveAs(...)` 落盘后再断言内容（顺带强化验证）。此前误判为顺序依赖的二分结论作废。
- 演示数据 id 前缀重复（`demo-${base.id}` 当 base.id 已含 demo 前缀）导致种子进度引用错页——演示数据 id 必须与页 id 公式一致。
- 详情类页面经 `router.replace`/状态切换重挂载后 notice 不保留：编译/重建后的断言以 URL 与页面内容为准，不依赖 status 横幅。

下一条动作：S5-D（阅读 /reading*）→ E 写作/whisper → F 伙伴/智能体 → G 精通之路 → H 记忆 → I 账户 → S6 设置整合 → S7 视觉动画三视口 → S8 最终验收交付 FINAL_ACCEPTANCE.md，不等待每批授权。

## 历史：S5-B 已完成（2026-09-08）

S5 批次 B「教材资料库与笔记本」完成。全量回归：正式单测 **188/188**（178 基线 + notebook-store 5 项 + knowledge-catalog 5 项新增）、全量 e2e **81/81**（77 基线 + S5-B 新增 4 项 `tests/e2e/knowledge-notebooks.spec.ts`；全量跑中 navigation.spec 1 项因导航名称适配失败，修正断言后复跑 5/5，产物 `tests/.e2e-output-20260908-s5b/`），typecheck/lint 0 警告，build 通过（build_exit=0，17 路由含 4 个新路由）。

S5-B 实施要点（后续批次不得回退）：
- **/knowledge-bases 列表**：知识库/检索引擎双页签；引擎三组静态展示且显式标注（本地=内置未接入、服务端=LightRAG/WeKnora 演示、云端=IMA 演示）+外部来源（Obsidian/MarginNote 未接入）；横幅显式"解析与索引服务未接入：文档登记仅保存名称与大小"；演示知识库显式载入（幂等，`loadDemoKnowledge`）；新建 Modal（`KnowledgeValidationError` 重名拒绝）。
- **/knowledge-bases/[kbName] 详情**：分区导航 文档/登记文档/外部来源/索引/设置；文档卡带"未解析 · 未索引"标记、大小与登记时间；登记文档仅存文件名+大小（file input 元信息，不读内容）；外部来源 github/web 登记不同步抓取，空地址报错；索引分区显式空态（依赖解析/向量检索服务，未接入）；设置分区改名/简介/删除确认、设为默认库（幂等唯一，默认库星标）。**改名成功后 `router.replace` 同步新 URL**（修复重命名后按旧名查找落"不存在"页的边界 bug）。
- **/notebooks[/[notebookId]]**：双栏 rail+记录区；默认笔记本"学习笔记"为虚拟项（`DEFAULT_NOTEBOOK_ID='notebook-main'`，无存储自动带出、不可删除）；无 notebookId 的记录（含聊天"保存到笔记"旧数据，normalize 补齐）归默认库；URL 深链选中（pushState），指向不存在笔记本明确报错；记录展开（摘要/提问/正文/打开原会话 `/chat/[id]?mode=mock` 深链）、编辑、删除确认、移动/复制（副本标题加"（副本）"、保留来源 metadata）、笔记本内搜索（>8 条出现）；笔记本新建/编辑（名称/简介/颜色）/删除（记录回默认库）、导出 Markdown（下载 `笔记本名.md`，空库仅标题）。页面显式不提供"新建记录"（记录由聊天/研究产生）。
- **服务层**：新建 `services/notebook-store.ts`（localStorage `zhiqikeyuan:notebooks` + `zhiqikeyuan:notebook-entries`，后者与聊天"保存到笔记"共用同一仓储与身份）；`knowledge-catalog.ts` 扩展 docs/sources/isDefault/createdAt + CRUD（`zqky.replica.knowledge.v1`，与聊天知识来源同目录）；两 store 均事件订阅（`zqky:notebooks`/`zqky:knowledge`）+ storage 跨页同步。
- **导航**：`knowledge`（教材资料库）升 ready 进侧栏（原 planned）；`notebooks` 升 ready 保持 hidden（参考亦不在侧栏显示）。
- **有意差异（按参考边界）**：KB 详情无"引用到聊天"动作（RAG 查询在聊天 composer，知识来源为范围声明不执行检索）；聊天侧已有入口不复制第二套管理。

S5-B e2e 排障记录：改名 `router.replace` 后详情页组件重挂载回默认"文档"分区（断言需重新进入"设置"分区再删除，与真实用户路径一致）；navigation.spec "教材资料库（规划中）"断言适配为"教材资料库"（随实现状态更新，同 S5-A /space→/notebooks 的处理）。

**S5-B 收尾补修（直达路由 CSS 断链）**：space.css 仅由 SpaceMain.tsx 引入，/notebooks、/knowledge-bases 的路由模块图不含它——预渲染 HTML 的 CSS chunk 无 `.space-page` 规则，直达访问整页无样式（S5-A 子页因与 SpaceMain 共享 webpack chunk 侥幸带上了样式）。修复：KnowledgeBasesSection/KnowledgeBaseDetailSection/NotebooksSection 显式 `import '@/features/space/styles/space.css'`（bundler 幂等去重）；重建后 /notebooks 预渲染 HTML 已加载含 space 规则的 chunk；knowledge-notebooks.spec 增加样式回归断言（`.space-page` 计算样式为 flex）。**教训：跨模块复用样式时每个使用组件都要显式引入；预渲染 HTML 的 CSS chunk 内容可用于实证检查**。

下一条动作：S5-C（书籍 /books、/books/[bookId]、/books/[bookId]/pages/[pageId] + 课程 /courses、/courses/[courseId]；参考研究报告已备：书籍=hub-and-spoke 单组件+Block 分发阅读器+状态机 draft→spine_ready→compiled，后端生成流水线需显式模拟；课程=聚合状态+大纲/资源/会话，/courses 参考中隐藏主导航）→ D 阅读 → E 写作 → F 伙伴/智能体 → G 精通 → H 记忆 → I 账户 → S6 → S7 → S8，最终交付 FINAL_ACCEPTANCE.md，不等待每批授权。

## 历史：S5-A 已完成（2026-09-08）

S5 批次 A「学习空间」完成。全量回归：正式单测 **178/178**（164 基线 + 14 新增）、全量 e2e **77/77**（69 基线 + S5-A 新增 8 项 `tests/e2e/space-pages.spec.ts`，产物 `test-results/e2e-full-s5a2/`），typecheck/lint 0 警告，build 通过。

S5-A 实施要点（后续批次不得回退）：
- **/space 仪表盘**（hub-and-spoke，对照参考 SpaceDashboard）：3 组磁贴（会话与资料/个性化）+实时计数（双仓储会话数、题库/笔记/角色/CLI/扩展计数）；whisper 磁贴按参考行为隐藏（树外插件能力本地不存在）。
- **/space/chat-history**：双仓储（真实+模拟）全量列表，搜索/模式/归档三重筛选、内联重命名（Enter/blur 提交）、删除确认、归档/恢复；重开按模式带 `?mode=mock` 深链。
- **/space/questions**：范围栏（全部/答错/未掌握/书签/未分类/各分类）+计数；250ms 防抖搜索、排序；卡片含选项对错标色、解析折叠、书签/已掌握/归类/删除、出处会话链接（演示题不显示）；批量（全选/已掌握/归类/移出/删除）；分类管理（增改删，删除分类题目回未分类）；演示题目显式载入（幂等）。数据与聊天"保存到题库"同 `space-store` 仓储。
- **/space/personas**：卡片网格+Modal 查看/新建/编辑/删除（重名校验 `PersonaValidationError`）；与聊天输入区人设共用 persona-catalog（新增 content/source/createdAt 字段，旧数据兼容）。
- **/space/cli-apps**：已安装/目录双页签；本地登记安装（横幅与提示均显式"模拟安装，不下载或执行任何程序"）、启停/卸载、内置/第三方徽标。新服务 `services/cli-apps-store.ts`（localStorage `zhiqikeyuan:cli-apps`）。
- **/space/mcp、/space/skills**：重定向 `/settings#mcp` / `/settings#skills`（参考为独立管理页；按既定决策"管理只在设置"重定向，记为有意差异）。
- **会话归档位**：`Conversation.archived?: boolean`（契约扩展，存储往返已测）；store `publish()`/`latestConversation()` 过滤已归档会话（侧栏不显示，深链仍可打开）。
- **跨模式深链**：`/chat/[id]?mode=mock` —深链定位前先切模式（一次性守卫不被误标记）；`syncSessionUrl` 在模拟模式写 `?mode=mock`，刷新后保持模式与定位。
- **导航**：space 登记为 ready；新增隐藏 planned `/notebooks`（`NavigationItem.hidden` 不进侧栏但保留 [planned] 解析）。
- space-store 扩展：书签/已掌握/分类/来源字段 + 分类 CRUD + `loadDemoQuizEntries` 显式演示载入；`updateQuizEntry`/`removeQuizEntries`。

S5-A e2e 排障记录：`规划中`文本断言会撞侧栏隐藏 small 标记（改用规划页正文）；演示题目与种子题目文本要错开避免 strict mode 冲突；navigation.spec 的 plannedRoutes 移除 /space 加入 /notebooks（随实现状态更新）。

下一条动作：S5-B（知识库 /knowledge-bases* + 笔记本 /notebooks*，参考源码研究进行中）→ C 书籍/课程 → D 阅读 → E 写作 → F 伙伴/智能体 → G 精通 → H 记忆 → I 账户 → S6 → S7 → S8，最终交付 FINAL_ACCEPTANCE.md，不等待每批授权。

## 历史：S4 已完成（2026-09-08）

S4 逐能力模拟闭环全部完成。全量回归：正式单测 **164/164**、全量 e2e **69/69**（65 基线 + S4 新增 4 项 `tests/e2e/chat-capabilities.spec.ts`，产物 `test-results/e2e-full-s4c/`），typecheck/lint 0 警告，build 通过（build_exit=0）。

S4 实施要点（后续批次不得回退）：
- **能力阶段序列**（对照参考 v1.6.5 manifest）：deep_solve=planning→reasoning→writing；deep_question=exploring→planning→quizzing（每题 `quiz_question_emitted` 增量）；deep_research=rephrasing→decomposing→researching→reporting（两段式：大纲确认卡→检索报告）；visualize=analyzing→generating→reviewing（manim 路由 concept_analysis→concept_design→code_generation→code_retry→summary→render_output）；ask_questions 能力复用纯追问双卡流程。
- **轮内阶段 `TraceStageRecord`**（contracts/chat.ts）：按 stageId 原地更新（start 置 running、end 置 done），end/error/stop 经 `closeRunningStages` 收口为 done/cancelled；`TraceStages.tsx` 时间线（running 旋转/done 对勾/cancelled·error 叉，终态不渲染）。
- **结构化产物**：`ChatArtifact.kind` 扩展 quiz/report/chart/mermaid + `data` 字段。QuizArtifactView（选择题点选判定、填空/概念本地比对、简答不判分、保存到题库）、ReportArtifactView（markdown+子问题+引用 CIT-x-x 定位、保存到笔记）、ChartPreview（Chart.js，失败回退配置原文）、MermaidPreview（mermaid@11 动态导入，失败回退源码）。ArtifactPanel 分发与扩展名已接。
- **空间仓储 `services/space-store.ts`**：localStorage `zhiqikeyuan:quiz-bank` / `zhiqikeyuan:notebook-entries`，幂等保存 + 作答记录；S5 业务页（题库/笔记）共用同一仓储与身份，不另造静态副本。
- **能力轮部分失败重试**：每个能力首阶段后 `failCapabilityTurn()`（`MOCK_CAPABILITY_ERROR`，retryable，可按原快照重试）。
- **分流修正**：纯追问条件加 `!hasExtensions && !capabilityDrivesArtifact` 守卫（否则带能力/扩展的工具卡被追问流程截断）；组合流条件相应收紧。
- **新依赖**：chart.js@4.5.1、react-chartjs-2@5.3.1、mermaid@11.14.0（锁文件已更新）。
- e2e 排障沿用 S3 记录：轮次结束信号=停止按钮消失；次要能力"更多能力"用 hover 不用 click。

下一条动作：S5 批次 A（/space 学习空间：chat-history/questions/personas/cli-apps + mcp/skills 迁移）→ B 知识/笔记 → C 书籍/课程 → D 阅读 → E 写作 → F 伙伴/智能体 → G 精通之路 → H 记忆 → I 账户，每批独立浏览器验收后继续；随后 S6→S7→S8，最终交付 FINAL_ACCEPTANCE.md，不等待每批授权。

## 历史：S3 已完成（2026-09-08）

S3 消息与结果工作区全部完成。正式 e2e **65/65 通过**（61 基线 + S3 新增 4 项 `tests/e2e/chat-workspace.spec.ts`，产物 `test-results/e2e-full-s3/`），正式单测 **157/157**，typecheck/lint 0 警告，build 通过。出口要求"工具→追问→同轮续写→产物→下载→刷新恢复"组合回归通过（chat-workspace.spec.ts:45）。

S3 实施要点（后续批次不得回退）：
- **WorkspacePanel（ArtifactPanel.tsx 重写）**：标签页形态——活动主页常驻第一（不可关闭），产物标签可关闭；关闭=移除标签（ChatWorkspace `closedTabs` 集合，产物本体保留，点产物 chip 恢复标签）并回退相邻标签/主页；会话/模式切换重置标签与关闭态。
- **宽度拖动**：左缘把手 pointer+rAF 合帧写 `--viewer-width`，400–960px 钳制（软上限 `innerWidth*0.7`），持久化键 `zhiqikeyuan:viewer-width`；<768px 隐藏把手（手机整幅抽屉）；220ms `chat-workspace-in` 展开动画；ESC 关闭。
- **活动主页**：InfoPanel + CapabilityConfigCard（R22 配置请求激活主页并定位配置卡）。
- **消息操作**：用户消息复制/复用（`.chat-msg-actions`）；assistant 来源与上下文块 `.chat-sources`（persona/knowledge/historyRefs/attachments/mcps/skills 条目，如实"未真实检索/未读取"说明）。
- **mock 组合流**（chat-service.ts）：纯追问（无能力且无扩展）走原双卡流程；带能力/扩展的追问走 S3 组合流——MCP 工具卡→单张追问卡（ask-combo-*）→同轮续写→能力产物（出题 markdown/可视化 SVG/研究报告）。**注意：must 保持该分流条件，否则工具卡被追问流程截断**。
- **R19 可用性收口**：capBlocked 时发送按钮保持可点击（标签"先确认能力配置"），点击走 submit 的 capBlocked 分支打开配置卡；修复了"无输入时按钮禁用导致必须先输入文字才能确认配置"的死锁。
- **R25 迁入**：`apps/web/src/features/chat/message-duration.test.tsx`（4 项）。

S3 排障记录（避免重蹈）：
- e2e 断言"轮次结束"不能用空输入下的发送按钮 enabled 态（发送后输入清空，按钮本来就该禁用）；用"停止按钮消失"作信号。
- SVG 产物走 data-URL `<img>` 安全渲染，其中文字不是 DOM 文本；断言用 `img[alt]` 可见性而非 toContainText。
- `getPropertyValue('--viewer-width')` 返回 "700px"，用 parseFloat 提取。
- 后台 shell 里 `next build` 偶发失败（环境文件锁竞争），前台重跑即过；e2e 必须确认 build_exit=0 后再跑，否则测的是旧产物。

下一条动作：S4 逐能力模拟闭环（deep_solve/deep_question/deep_research/visualize/数学动画/mastery_path，对照参考源码提取阶段与结果样式；结构化题目/报告渲染；保存到业务页同一仓储）→ S5 A–I → S6 → S7 → S8，最终交付 FINAL_ACCEPTANCE.md，不等待每批授权。

## 历史：R19–R25 已修复并迁移正式回归（2026-09-08）

R19–R25 全部修复，独立复现探针（单元 2、浏览器 7）全部通过后迁入正式回归；正式 e2e **61/61 通过**（54 原有 + 7 迁入边界场景，`test-results/e2e-migrated-run1/`），上轮报告的 chat-motion context teardown 超时本轮未复现（判定为环境相关偶发，S8 全量复验时如实记录）。正式单测 **157/157**（153 + R25 耗时终态 4 项，含复核要求的恢复路径独立回归）。typecheck/lint 0 警告/build 通过。

修复要点（后续批次不得回退）：
- **R20 提交契约**：store.send 接受空文字但必须携带附件/引用快照（用户消息以 `[附件] …`/`[引用会话] …` 明确标识）；新增 onAccepted 同步回调，一次性选择只在轮次被接纳时清理；真实模式附件/仅引用发送显式阻断并保留输入（不静默转纯文字）。
- **R19 配置确认**：门控改为 `needsConfig && (!confirmed || errors)`，任意字段变更撤销确认（桌面+手机共用 handleCapFormChange）。
- **R21 会话归属**：人设/知识/会话引用/附件按「模式+会话 id」归属（ChatWorkspace pendingRef），新会话明确空默认，切回恢复；欢迎页暂存随首个会话迁移。
- **R22 面板选择**：右面板显式单选 panelView（info/config/artifact），配置请求激活配置视图并定位聚焦，不再被产物视图遮挡；手机抽屉同语义。
- **R23 文件并发**：串行接纳队列 + 读取占位（reading）预留配额；完成核对批次身份（发送/移除/卸载后不插回）；失败释放占位并提示；粘贴/拖入统一走队列且拒绝原因显式。
- **R24 产物身份**：结果工作区以复合 key（消息 id:产物 id）打开/tab/复制/下载，不同轮同 id 各自正确；旧历史兼容。
- **R25 耗时**：Message 标题区为唯一耗时渲染点（正文出现后不消失）；patchError 补 finishedAt；normalizeLoaded 以会话 updatedAt 冻结恢复/旧历史耗时（多次载入稳定）。

迁移的正式回归：`apps/web/src/features/chat/message-duration.test.tsx`（4 项）、`tests/e2e/chat-composer-boundaries.spec.ts`（7 项，验收语义未削弱，原始探针证据保留在 `_work/review-s2-s3-20260908/fix-run1/`）。

下一条动作：S3 剩余（引用/来源定位、消息菜单、多标签工作区、宽度拖动、跟随滚动收口）→ S4 能力闭环 → S5 A–I → S6 → S7 → S8，最终交付 FINAL_ACCEPTANCE.md，不等待每批授权。

历史摘要：53 非调试条目中 46 待实现的口径仍以三矩阵为准；真实供应商/MCP/Skills/解析/STT 未验证。上一轮（2026-09-08 复核）记录见下节。

## 历史：2026-09-08 独立复核（R19–R25 复现，未修）

当前完整前端未交付；S2 已实现但需修复，S3 部分实现，S1 规格仍需随批补齐。最新依据为 [REVIEW_S2_S3_2026-09-08.md](REVIEW_S2_S3_2026-09-08.md)，全部后续执行指令已统一在 [NEXT_SESSION_START.md](NEXT_SESSION_START.md)。上一轮终态 2/2、URL 刷新 1/1 探针通过；正式 typecheck/lint/build、153 单测通过；本次正式 e2e **53 通过、1 个录像 context teardown 超时**。新探针 **7 浏览器+2 单元场景失败**，对应 R19–R25，尚未修改产品代码修复。

下一条动作：运行 `_work/review-s2-s3-20260908` 两份探针配置，先修提交清理/真实附件提示和配置门控，再处理会话归属、面板选择、附件并发、产物身份、耗时。修复后迁移回归，立即继续 S3 引用/消息/多标签/可调宽度 → S4 能力闭环 → S5 全业务页 → S6 设置 → S7 全站视觉动画 → S8 最终验收，不等待每批授权。详细命令和完成条件见当前入口。

实际矩阵：53 非调试条目，4 已验收、1 实现待验收、2 部分实现、46 待实现；不能用历史44或旧测试数。真实供应商/MCP/Skills/解析/STT未验证，test:api本轮未执行。证据在 `_work/review-s2-s3-20260908/`；本轮仅审查/探针/文档，无产品修复、无提交。下方均为历史实施记录，旧“下一动作”不再作为当前任务。

## 历史：2026-09-07 收尾批 + S2 输入区 + S3 基础实施记录

交付复核（[REVIEW_DELIVERY_2026-09-07.md](REVIEW_DELIVERY_2026-09-07.md)）所列收尾问题已修复并迁移正式回归；S2 输入区和 S3 基础已实施。以下保留当时报告，当前缺陷与验收状态以 2026-09-08 独立复核为准。

### 收尾批完成内容与证据（2026-09-07 晚）

- **终态顺序两处 P2**（store.ts）：
  - `submitReplyAnswers` 归属校验区分业务终态与 Promise 生命周期——`turnAlive` 要求 `endReason === null`；error/stop/disconnect 已到达（即使 run Promise 未返回）时迟到 accepted ACK 一律拒绝。提交异常路径同样只在未终态时改写卡片。
  - `patchStoppedIfStreaming` / `patchError` 幂等进入：已有明确终态（end/error/stop）时通用断流兜底不再覆盖 `endReason`，合法同步续答的迟到确认可保留答案（卡 answered）。
  - 探针迁移正式回归 2 项（`ask-user.test.ts`，现 23 项）：error 先到 run 挂起时迟到 ACK 拒绝；正常 end 后 run 返回时合法 ACK 接受。
- **深链 URL 同步**（ChatWorkspace.tsx）：用户主动选择/新建/删除/切换模式经 `history.pushState/replaceState` 同步地址（选择=push，新建/删除/模式切换=replace；pushState 不触发 Next 软导航，与 R17 一次性深链定位不冲突、无双向循环）；`popstate`（前进/后退）按 URL 在当前模式 store 重新定位，指向已删除/其他模式会话时显示明确提示。探针迁移正式 e2e 3 项（`chat-deeplink.spec.ts`，现 7 项）：选择后 URL 同步且刷新恢复、后退/前进重定位、新建后地址指向新会话且刷新无“不存在”提示。
- **Lint**：删除 `ask-user.test.ts` 未使用的 `emitWaiting` 声明；0 警告。
- **文档**：根 TASKS/HANDOFF 当前摘要已与本节对齐；FINAL 首批执行表标注为历史快照（S1=部分完成、53 条目口径）。

### 收尾批验证（实际执行）

typecheck 通过；lint 0 警告；`test:unit` **119/119**（基线 117 + 终态顺序 2）；`npm run build` 通过；`test:e2e` **45/45**（基线 42 + 深链 3，产物目录 `tests/.e2e-output-20260907-deliveryfix/`）；复核探针 **terminal-order 2/2、route-refresh 1/1**（`_work/review-delivery-20260907/fixcheck-02/`）；上轮探针复跑 **ask-user 单元 7/7、浏览器 1/1**（`_work/review-ask-user-20260907/fixcheck-03/`）。本轮录像 teardown 超时未复现（历史 2 次，逐次记录，根因未定位）。真实供应商/真实 MCP、Skills 未验证；`test:api` 未复跑（后端零改动）。

### S2 完整输入区批次完成与证据（2026-09-07 深夜）

新组件：`CapabilityMenu.tsx`（能力 chip+主列表+更多能力飞出层）、`CapabilityConfigCard.tsx`（出题/可视化/研究三表单+确认门控）、`ComposerSpaceMenu.tsx`（“添加内容”菜单+引用树）。新服务：`capability-catalog.ts`（对照 v1.6.5 目录与配置类型/默认值/校验）、`persona-catalog.ts`、`knowledge-catalog.ts`（演示目录：显式“载入演示数据”，不自动写入）、`doc-attachments.ts`（对照参考 classifyFile/selectAttachmentFiles，20MB/25MB 上限）。契约：`TurnExtensionSnapshot` 增加可选 capability/persona/knowledge/historyRefs/attachments（旧快照兼容）。

- **能力门控**：needsConfig（出题/可视化/研究）未确认时发送按钮为 blocked 态，点击打开右面板配置卡而非静默失败；切换能力使确认失效；任何字段编辑重置确认。
- **真实/模拟分离**：真实模式仅对话能力可选，非对话能力禁用并标注“真实服务未接入”，不静默转模拟；切回真实模式时明确提示并重置为对话；真实模式不支持仅附件/引用发送并有明确提示。
- **快照冻结**：发送冻结 capability+config+persona+knowledge+historyRefs+attachments（深拷贝），重试沿用；一次性引用与附件发送后清空（同参考），人设/知识为会话级。
- **模拟复述**：mock 服务按快照复述能力配置摘要、人设、知识来源（“仅声明检索范围，未执行真实检索”）、引用会话、附件（“未读取文件内容——当前无解析服务，不伪装上传成功”）；阶段行显示“按「X」能力准备”。
- **附件**：选取/拖入（虚线覆盖层）/粘贴/类型与配额校验（错误 4s 自动清除）/图片 SVG 缩略图与文档卡/预览弹层（无解析服务如实说明）/移除。
- **语音**：明确“未接入”说明+带标识演示转写插入，不采集音频。
- **发送按钮**：改为参考的单按钮整轮语义（idle/blocked/ready/streaming，箭头↔方块 200ms 同格交叉淡变）——修复 650ms 宽度过渡期间两按钮互换导致的点击竞态（连续发送回归曾复现误发第二轮，trace 定位后按参考设计消除）。
- **650ms 过渡**：max-width 768→960、cubic-bezier(0.16,1,0.3,1)（对照参考）；textarea minHeight 64→28、0.15s 高度过渡；窄屏恢复 100%。
- **窄屏**：工具行 flex-wrap，390px 发送按钮换行不溢出（R6 断言通过）。

测试：新增 `capability-catalog.test.ts`（6）、`doc-attachments.test.ts`（6）、`composer-snapshot.test.ts`（3：冻结深拷贝/模拟复述/重试沿用）、`CapabilityMenu.test.tsx`（5）；e2e 新增 `chat-composer.spec.ts` 8 项（能力门控闭环/附件/语音/真实模式禁用/650ms 中间帧采样/三视口截图+溢出断言）；`chat-mock.spec.ts` 停止点击改 force（650ms 过渡期间按钮移动，actionability 重试会落到流结束之后——验收语义不变，已在测试注释说明）。单元 **142/142**、e2e **53/53**（chat-mock+chat-composer 27/27 先行验证，全量后 53/53），typecheck/lint 0 警告/build 通过。三视口截图与宽度采样见 `tests/.e2e-output-20260907-s2f/chat-composer-*`（1440/1920/390 已人工查看：欢迎区布局、工具行换行、无横向溢出）。

边界：真实供应商未验证；真实文件解析/STT/persona/知识库服务未接入（均为明确模拟或不可用状态）；能力模拟的完整阶段流程在 S4；三矩阵已同步（A-capability/A-attachments/A-voice/A-persona、M-composer-width/M-first-send、P-chat/P-chat-[sessionId]）。

### S3 切片 1：结果工作区基础（2026-09-07 深夜，已完成）

- **契约**：`ChatArtifact { id, kind: 'markdown'|'svg'|'html'|'text', title, content, createdAt }`（contracts/chat.ts）；artifact 事件负载 `ChatArtifactPayload = Omit<ChatArtifact,'createdAt'>`（store 落盘时补 createdAt）；消息新增 `artifacts?`（旧历史兼容）。
- **store**：artifact 事件按 id 幂等更新（同 id 覆盖=增量/完成、createdAt 保留；新 id 追加）；终态/取消守卫拒绝迟到事件（复用现有 emit 守卫）；随会话持久化、恢复不重放。
- **mock**：出题→markdown 出题结果、可视化→SVG 图表、研究→markdown 报告（内容含配置摘要与“模拟/未访问”标识）；对话/求解等无产物；失败轮不产产物。
- **UI**：`ArtifactPanel.tsx` 右侧结果工作区（与 InfoPanel 共用右栏位；手机走 Modal）：产物列表 tab、markdown（AnswerMarkdown 安全渲染）/svg（data-URL img，img 上下文不执行脚本）/html（空 sandbox iframe 禁脚本）/text 渲染；复制（clipboard，2s 已复制态）与下载（Blob+download 属性，真实内容+安全文件名）。消息内产物入口 chip（图标+标题+kind）定位打开。
- **关键修复——flush 串行队列（数据丢失级）**：旧实现“保存中直接返回在途 Promise”会取消挂起的防抖 timer，保存期间到达的变更（如点击面板/下载触发的 blur→flush、流式增量）无人重排，刷新后数据丢失。改为链式排队：后到 flush 在前一保存完成后处理剩余脏数据；单测回归覆盖（保存中到达的变更必须由后续 flush 落盘）。
- **轮级耗时（切片 2 已完成部分）**：消息新增 startedAt/finishedAt（占位创建/五收尾点记录，持久化）；trace-timing.ts（对照参考 formatTurnDuration：Xs/Xm Ys/Xh Ym，先取整）；流式状态行逐秒滴答、完成后标签行冻结显示（单一状态行设计，不在每个过程卡重复显示——参考明确 per-trace 时长嘈杂）；trace-timing.test.ts 4 项。
- **测试**：`artifact.test.ts` 6 项（幂等 upsert/终态拒绝/持久化恢复/三类能力产物）；store.test.ts 新增保存队列回归 1 项；e2e 1 项（出题轮 chip→预览→下载真实内容→关闭→等轮次完成后刷新→恢复不重放；测试在轮次完成后再 reload——流式中途 reload 的 fire-and-forget 保存不可靠，取消语义由其他用例覆盖）。
- **验证**：单测 **153/153**、e2e **54/54**（`tests/.e2e-output-20260907-s3full/`、`-s3t2/`）、typecheck/lint 0 警告/build 通过。
- **S3 剩余（切片 2 续）**：引用/来源定位、消息菜单（消息级操作）、问题编辑复用细化、跟随底部/回底提示核对、artifact 渲染器扩展（quiz/报告结构化等随 S4）、标签页多开与宽度可调（对照 SessionViewerPanel：220ms 展开、400–960px 持久化宽度，localStorage `dt:viewer-width`）、移动端抽屉细节。耗时显示已完成（轮级单点，对照参考）。

### 下一动作：S3 切片 2（引用定位/消息菜单/过程面板补全），随后 S4–S8

按 FINAL S3：引用/来源定位、消息菜单、跟随底部与回底、过程面板补全（阶段/耗时/状态顺序）、artifact 消费方与右侧结果工作区（按 artifactId/sessionId/turnId 幂等更新、渲染器按能力分批、复制下载用真实内容、历史恢复不重放、HTML/SVG 等安全渲染、桌面分栏/窄屏抽屉）。先读参考 SessionViewerPanel/SessionActivityPanel 及消息列表相关源码，补规格后实现。下面是前次实施记录，不能代替本次独立检查结果。

## 最新交接：续审 R17/R11补充/R13补充/R12补充/R18 修复完成（2026-09-07 夜）——因上下文硬限制暂停，整体未完成

正在执行 FINAL 总任务（S0–S8）。本会话累计完成：S0（R11–R16）、S1 框架（三矩阵 id 化）、S2 深链切片，以及本轮**续审 6 项修复**（R17、R11 补充、R13 补充、R12 补充、R18）。**因会话上下文达到硬限制暂停**；S2 完整输入区与 S3–S8 未开始实施。逐条证据见 [REVIEW_S0_S2_2026-09-07.md](REVIEW_S0_S2_2026-09-07.md) "修复记录（2026-09-07 晚，继续批）"。

### 本轮（续审修复批）完成与证据

- **R17 深链锁死**已修复：`ChatWorkspace.tsx` 深链改一次性定位（`deepLinkHandled` 守卫），新建/切换/删除后不再被 URL 回跳；刷新/前后导航重新挂载按 URL 重定位；lint 依赖以 disable+理由处理。浏览器探针 A/B 通过；迁移 e2e 2 项（`chat-deeplink.spec.ts` 现 4 项全过）。
- **R11 补充**已修复：token 增加 `endReason`（stop/end/error/disconnect 五收尾点记录）；提交归属=未中止 ∧ 未被顶替 ∧（轮次活跃 ∨ endReason='end' 正常完成）∧ 提交身份 ∧ 同会话——error/断流后迟到 accepted ACK 拒绝、中断卡不被改写；正常两卡同步续答保留。迁移回归 2 项（error/disconnect）。
- **R13 补充**已修复：waiting/failed 后的过期 preview 不覆盖完整题目/选项/引言（仅 preview→preview 允许补全）；草稿保留。迁移回归 1 项（状态/题目/选项/引言/草稿五维断言）。
- **R12 补充**已修复：`Message.tsx` 复制按钮可用性改用 `conversationProjection`——纯追问续答可复制，空白占位不显示。
- **R18 文档修正**：PAGE_MATRIX 统计 **53 非调试条目（参考产品页 50 + 目标自有 1 + 兼容别名 2）：已验收 4 / 实现待验收 1 / 部分实现 2 / 待实现 46**；S1="框架完成、规格部分完成"；深链条目降为"实现待验收"；DECISIONS 默认入口行标记历史并统一 `/`→`/chat`。
- 迁移回归：单元 3 项入 `ask-user.test.ts`（现 21 项）、e2e 2 项入 `chat-deeplink.spec.ts`。

### 本轮验证（实际执行）

typecheck 通过；lint 0 警告；独立探针 3/3 单元 + 3/3 浏览器（fixcheck-01）通过；原探针（ask-user 7、extensions 2、复制 1）与 chat 正式测试 72 项通过；build 通过；深链 e2e 4/4。**全量 e2e 修复后未重跑**（恢复后先全量，预期 40/40；chat-motion teardown 若再现按既往记录处理）。

### 恢复点：下一条可执行动作

1. 全量回归：`npm run test:e2e -- --output=<新目录>`（预期 40/40）。
2. **S2 完整输入区**（先读 `F:\DeepTutor\web/components/chat/home/ChatComposer.tsx`、`ComposerInput.tsx`、`CapabilityConfigCard.tsx`）：
   a. 业务能力选择（chat/deep_solve/deep_question/deep_research/visualize）与 real/mock 服务模式分离；能力目录建议新文件 `services/capability-catalog.ts`（订阅机制参照 extension-catalog）；发送时冻结 capability 进快照（复用扩展快照冻结模式）。
   b. persona/附件（选取/拖入/粘贴/校验/预览/移除）/引用/语音入口（权限与无服务状态准确，不后台采集）。
   c. 欢迎区→首次发送 650ms 过渡（逐属性核对）；真实模式选非 chat 能力发起前明确"暂无真实服务"。
3. 之后按 FINAL 提示词 S3→S8 循环（每批：实现→单测→build→e2e 新目录→更新 HANDOFF+三矩阵）。
4. 最终交付 `docs/replica/FINAL_ACCEPTANCE.md`（页面/交互/动画/模拟验证/真实服务验证五列）。

### 已知风险与边界

- chat-motion 录像 teardown 超时：复核轮与本轮复核各 1 次，本会话 3 连跑未复现——根因未知，独立文件隔离，逐次记录。
- 真实供应商未验证（无凭证）；真实 MCP/Skills 未接入；`test:api` 未复跑（后端零改动）。
- Git 零提交、大量文件未跟踪，不能以 diff 证明历史改动边界。

## 前置批：R10 修复＋追问卡片与同轮续答（2026-09-07 傍晚，用户指定）

按 docs/replica/NEXT_PHASE_ASK_USER.md 执行：先修 R10，再实现模拟追问。逐条证据见 REVIEW_EXTENSIONS_2026-09-07.md 的"R10 修复记录"；本节记录追问阶段。

### R10（前置，已完成）

`ExtensionPicker.tsx` 外部点击监听条件写反（`!mounted || open`）导致打开时永不注册——修正为打开时注册、关闭/卸载移除；外部点击 `closePanel(false)` 不抢焦点。探针先复现后通过；正式回归落在 `ExtensionPicker.test.tsx` 与 `chat-mock.spec.ts`（R10 用例）。原 R5–R9 探针 2/2+4/4 复跑通过。

### 追问卡片与同轮续答（模拟，已完成）

- **契约**：wait-user 事件结构化（interactionId/intro/questions/status；preview 只读、waiting 开放，同 id 就地更新不覆盖草稿）；`ChatService.submitReply`（可选能力，ChatServiceReplyRequest 含 sessionId/turnId/interactionId/submissionId/answers/signal）；真实服务显式 REPLY_NOT_SUPPORTED。契约新增 `AskUserQuestion/AskUserOption/AskUserAnswer/AskUserInteraction/AskUserDraft`（contracts/chat.ts），消息新增 `asks?: AskUserInteraction[]`（含逐卡 `followUp` 续写正文），正文→提问→回答记录→续写按序渲染。
- **语义（对照原版源码逐条核对）**：单选选中跳下一未答题、多选不前进、自由文本单选互斥、未答提交为跳过、提交中锁定；卡片级失败保留草稿与选项可重试（MOCK_REPLY_ERROR）；已答只读摘要。主输入框等待时路由到同一提交接口（第一道未答题计入自由文本，其余按草稿/跳过）；等待+空输入显示停止（取消等待），有输入显示提交回答。
- **等待上下文**：模拟 run 经挂起点保持活动（不提前返回、可取消）；submissionId+submittingReply 幂等；取消/断流/切会话/卸载/终态后卡标记 interrupted 并拒绝提交；等待/提交状态只在运行期存在，不持久化运行对象。
- **持久化与恢复**：问题、草稿、确认答案、状态、续写随会话保存；`normalizeLoaded` 将未完成等待标记中断（init 与再选共用）；不重放、可显式重试原问题开新尝试；旧历史兼容。
- **模拟场景（确定性，模拟横幅"模拟追问/模拟提交失败"布防，无隐藏关键词）**：同轮两卡、单选+多选/自由文本、续写反映实际选择、全部跳过、一次提交失败可重试、等待中取消、提交时取消。
- **修改/新增文件**：`contracts/chat.ts`、`features/chat/model/chat-service.ts`、`model/store.ts`、`features/chat/AskUserCard.tsx`（新）、`features/chat/Message.tsx`、`features/chat/ChatWorkspace.tsx`、`styles/chat.css`、`ExtensionPicker.tsx`（R10）、`model/ask-user.test.ts`（新 11 项）、`ExtensionPicker.test.tsx`（+R10）、`tests/e2e/chat-mock.spec.ts`（+6：R10 与追问五场景）。

### 验证（全部实际执行）

- typecheck、lint（0 警告）、`test:unit` **107** 项（基线 95）、build：通过。
- `test:e2e`：**38/38** 通过（基线 32；+6）。产物目录 `tests/.e2e-output-20260907-askuser2/`（首轮 askuser 目录中"减少动画+手机布局"用例失败 1 次，未复现——同用例复跑 2 次及全量复跑均通过，按偶发 flake 如实记录，未改断言）。
- 探针：R10 探针修复前失败/修复后通过；R5–R9 原探针 2/2+4/4 复跑通过。
- **chat-motion 录像 teardown 超时诊断**：复核轮报告的 `Tearing down "context" exceeded the test timeout` 在本轮连续 3 次独立复跑（4.4–4.8s/次，产物 teardown-teardown-1/2/3）均未复现；录像用例独立成文件，业务断言不受其影响。未复现原因无法进一步定位（疑似录像文件收尾与环境负载相关），如实记录。
- 未验证项：真实供应商、真实 MCP/Skills（模拟边界）；`test:api` 未复跑（后端零改动）；WebM 未逐帧播放（此前定格帧已人工查看）；390/1920 追问专项截图未单独补（布局组件复用已验证的响应式规则，追问长文本 390px 人工复核待做）。

### 下一阶段

产物工作区或其他能力待用户指定；旧提示词中"提交后以新轮次继续"已作废（以本节与 NEXT_PHASE_ASK_USER.md 的同轮续答语义为准）。

## 扩展审查 R5–R9 修复（2026-09-07 下午，用户指定）

仅修复 docs/replica/REVIEW_EXTENSIONS_2026-09-07.md 的 R5–R9，未进入追问/产物新功能。逐条代码依据、探针复现与修复后证据见该报告“修复记录”一节。要点：

- **R5**：`store.ts` 新增 `normalizeLoaded()`，初始化与 `selectConversation()` 共用恢复语义——再次选择历史不再复活 streaming/running；保留 revision、消息、快照与工具历史，恢复不重放。
- **R6**：输入区重排（`ChatWorkspace.tsx` + `chat.css`）——已选扩展独立 `.chat-ext-row` 可换行、长名称省略+title、移除按钮可见、说明横排、发送按钮常驻；390×844/1920×1080 断言+截图通过，无裁切隐藏。
- **R7**：`ToolProcessPanel.tsx` 详情 `inert={!open}`——收起即移出焦点顺序与可访问树，收起时焦点自动回头部；动画与快速开关保留。
- **R8**：扩展菜单补退场动画（对照原版 AnimatePresence 160ms cubic-bezier(.16,1,.3,1)，退场 y4/scale.97）；新增 `--ease-standard`（Tailwind ease-out cubic-bezier(0,0,0.2,1)）用于过程展开，与弹出层缓动区分；快速开关/中断/减少动画验证；WebM 录像 + 定格帧截图均已人工查看。
- **R9**：发送开始自动关闭已打开菜单并禁用全部选项，程序化关闭不抢焦点；键盘路径（Shift+Tab×2 回输入框 Enter）正式回归覆盖。

验证：typecheck、lint（0 警告）、`test:unit` 95（基线 93）、build、`test:e2e` 32（基线 26）全部通过；独立探针修复后单元 2/2、浏览器 4/4 通过。真实供应商与真实 MCP/Skills 未验证（模拟边界）；`test:api` 未复跑（后端零改动）。e2e 产物 `tests/.e2e-output-20260907-r5/`、录像 `…-r12/`（每轮新独立目录）。

期间修正的回归：扩展行初版位于工具行之后，破坏 Shift+Tab 两步回输入框路径——已移至输入框与工具行之间。工具链：`npx playwright install ffmpeg` 安装了 Playwright 自带辅助二进制（用户缓存，不动项目依赖与锁文件）。

下一阶段仍为“追问交互”，提示词见本文件“扩展目录联动＋工具过程面板”一节（适用前提 R1–R9 均已修复）。

## 聊天扩展目录联动＋工具过程面板（2026-09-07，用户指定）

### 实际完成内容

- **事件契约**：`ChatServiceEvent` 改为以 `type` 为判别字段的联合类型（`chat-service.ts`）——text/reasoning 必带 `delta`，tool 必带 `call`（callId/kind/name/status，状态 running/done/error/cancelled），end 必带 finishReason，error 必带 error；sessionId/turnId 与终态守卫保留。`ChatServiceRequest` 增加 `extensions?: TurnExtensionSnapshot`；真实服务不读取、不向真实后端发送该字段（真实 SSE 协议未变）。
- **快照冻结与重试**：发送时由当前选择构建快照（`ChatWorkspace.buildSnapshot`，纯数据拷贝），store 再次深拷贝随消息持久化；重试沿用原消息快照（`retry` 读取 `last.extensions`），不读取最新目录；目录变化只影响后续发送。
- **扩展选择器**（`ExtensionPicker.tsx`，仅模拟模式）：复用 `services/extension-catalog.ts` 单一来源与变更订阅；MCP 与 Skills 分区展示、搜索、选中态（aria-pressed）、移除；“管理 MCP / 管理 Skills”链接定位 `/settings#mcp`、`/settings#skills`；Escape 关闭并恢复触发按钮焦点；空态指引。选中项在输入区以 chips 展示可移除。目录变化后失效的待发送选择明确提示（`已移除失效的扩展选择：…`）并移除，不静默替换。真实模式输入区显示“扩展 · 真实模式尚未接入”，不执行真实扩展、不因真实服务错误切模拟。
- **模拟执行**（`createMockChatService`）：确定性脚本——技能逐个“技能上下文已加载（模拟）”（加载记录，不伪装远程调用）；MCP 逐个 running→done（卡片带“模拟工具调用 · 未连接真实服务”标识）；`armFailure()` 布防后首个 MCP 以 MOCK_TOOL_ERROR 明确收尾（保留过程，可按原快照重试），未选 MCP 时保持原 MOCK_ERROR 行为；无扩展时与原流程一致；取消由信号中止触发，运行中卡片由 store 收尾。
- **工具过程面板**（`ToolProcessPanel.tsx`，对照 DeepTutor `TracePresentation.tsx` 行内活动行）：按 callId 去重原地更新（重复更新不新增卡片）；卡片终态（done/error/cancelled）后不接受重开或改写；手动展开/收起固定（卡片组件态 keyed by callId，正文增量不重置）；详情用 AnswerMarkdown 安全渲染（skipHtml），不执行扩展返回内容；展示工具名、状态、模拟标识与可展开摘要；技能加载记录与 MCP 工具记录以 kind 区分（MCP/Skill 徽标）。
- **收尾与持久化**：end/error/取消/断流时所有运行中卡片收尾为“已取消”（store `closeRunningTools`）；过程随会话写入 IndexedDB；刷新只恢复记录不重放（init 不触发服务），历史中仍为 running 的卡片恢复时收尾为 cancelled；旧历史无 toolCalls/extensions 字段按空集合处理，不清空不重置。重试保留带过程记录的失败尝试（`superseded` 标注），即使该轮无正文。
- **动画与可访问性**：卡片展开用已登记 `--motion-trace` 300ms ease-out grid+opacity（对照原版），选择器弹出层用 `--motion-pop` 160ms；状态切换只改类名，不在正文增量时重播；减少动画由 motion.css 全局（prefers-reduced-motion + zqky.motion）接管；选择器键盘可达（Escape、焦点恢复、清晰可访问名称）；上滚阅读不强制滚底行为未变；未引入新动画库。

### 修改与新增文件

- 契约：`contracts/chat.ts`（TurnExtensionSnapshot、ToolCallRecord、ChatMessage.extensions/toolCalls）
- 服务与状态：`features/chat/model/chat-service.ts`（判别式联合、请求快照、模拟脚本）、`features/chat/model/store.ts`（send/retry 快照、tool 路由、closeRunningTools、init 归一化）、`model/ChatContext.tsx`（未改，沿用 R1–R3 机制）
- 界面：`features/chat/ExtensionPicker.tsx`（新）、`features/chat/ToolProcessPanel.tsx`（新）、`features/chat/Message.tsx`（接入面板）、`features/chat/ChatWorkspace.tsx`（目录订阅、选择状态、失效提示、chips、真实模式提示）、`features/chat/styles/chat.css`（面板与选择器样式）
- 测试：`model/extensions-snapshot.test.ts`（新 9 项）、`features/chat/ExtensionPicker.test.tsx`（新 4 项）、`tests/e2e/chat-mock.spec.ts`（新 4 项浏览器用例）

### 实际命令与结果（2026-09-07 全部实际执行）

- `npm run typecheck` 通过；`npm run lint` 通过（0 警告）。
- `npm run test:unit`：93 项通过（上一基线 77；新增快照冻结/重试快照/callId 去重/终态收尾/取消与断流收尾/工具失败重试/历史恢复与兼容/真实路径不带快照/选择器交互等 16 项）。
- `npm run build` 通过。
- `npm run test:e2e`：26 项通过（上一基线 22；新增：扩展选择→发送→卡片→展开稳定→刷新恢复不重放；工具失败→错误收尾→按原快照重试；执行中取消→运行中卡片全部收尾→刷新仍收尾；减少动画+390px 手机布局完整闭环+截图）。e2e 产物目录 `tests/.e2e-output-20260907-r4/`（沙箱批量删除守卫会拦截旧产物目录清理，每轮使用新目录，既有证据未删除；手机截图 `chat-extensions-390.png`）。
- 中途修复：e2e 发现重试会丢弃“零正文的失败占位”，而工具失败轮的过程记录因此丢失——已改为保留带过程记录的失败尝试并有单测覆盖。

### 已知限制与边界

- 真实供应商未验证（本轮未调用真实模型；扩展能力整体为本地模拟，无真实安装、授权、联网检测或远程执行）。
- 录屏未完成（沿用此前限制，未重试 REPLICA_VIDEO）；动画符合性以参数与截图为证，人工视觉审阅待做。
- 发送中扩展选择入口禁用（`disabled={store.sending}`）；在途轮次不可增减扩展（快照冻结语义）。
- 卡片详情为本地脚本生成的演示内容；扩展“内容”字段仅作为技能上下文摘要展示，不做检索或执行。
- 等待用户（wait-user）、产物（artifact）事件仍为预留类型；追问、产物工作区、MCP/Skills 商店与真实检测留待后续阶段。

### 下一阶段执行提示词（追问交互，可直接复制）

> 项目 H:\备份xuexi\智启课源。先读根与 apps/web 的 AGENTS.md、docs/replica/REVIEW_2026-09-07.md、docs/replica/HANDOFF.md 最新一节（扩展目录联动与工具过程面板已完成）；聊天动手前先读 apps/web/src/features/chat/ 全部源码，以当前源码为准；参考仓库 F:\DeepTutor 只读（提交 42fab3cf…）。本次只实施“追问交互”：在统一事件服务的 wait-user 事件上实现消息内追问卡（提问列表、作答输入、提交后以新轮次继续，不伪造远程工具调用），对照原版追问组件的行为与动画（复用已登记 160ms/300ms token 与减少动画机制）；追问沿用本轮扩展快照与统一事件路由，遵守既有终态守卫（迟到事件不重开卡片、不修改已完成过程）、卸载清理幂等（含 StrictMode）与单一仓储机制，不得回退。模拟脚本覆盖“无追问/单问题/多问题/作答后继续/追问中取消”，过程与作答随会话持久化，刷新恢复记录不重新执行；真实模式明确显示未接入。运行 typecheck、lint、test:unit、build、test:e2e（浏览器用隔离上下文与固定测试数据，使用新的独立产物目录），更新 docs/replica 三个矩阵、HANDOFF 与 docs/TASKS。不实现产物工作区与其他页面，不接真实 MCP/Skills，不动教案模块，不升级依赖，不自动提交 Git。

## 审查 R1–R4 修复（2026-09-07，用户指定“下一轮 A”）

本次只修复 docs/replica/REVIEW_2026-09-07.md 中的 R1–R4，未进入新功能开发。修复内容、行为变化、验证命令与结果、未完成项（含“事件类型判别式联合”留待下一轮）详见 [REVIEW_2026-09-07.md](REVIEW_2026-09-07.md) 的“修复记录”一节。要点：

- **R1 卸载清理**：ChatProvider effect cleanup 对两个 store 幂等 `dispose()`（取消生成+冲正保存），客户端路由卸载/浏览器返回不再依赖 pagehide；兼容 React StrictMode。ChatWorkspace 内重复 effect 已移除，beforeNavigate 保留。
- **R2 单一仓储**：固定模式 store 只注入/加载/读写自己的仓储（`ChatDeps.repository` 取代 `repository`+`mockRepository` 双注入；mock 默认库仍为 `zhiqikeyuan-chat-mock`，数据兼容）。真实库挂起不阻塞模拟 store；跨模式同 ID 不串扰。
- **R3 终态守卫**：generation token 增加 `terminal`；end/error/取消/断流收尾后拒绝 stage/process/usage 等一切后续事件。
- **R4 测试修正**：隔离测试注入被测 spy 仓储/服务再断言；复现探针迁移为正式回归并新增卸载取消（含 StrictMode）、卸载保存、dispose 幂等、初始化互不阻塞、跨模式同 ID、三类迟到事件、不自动回退模拟用例。

验证：typecheck、lint（0 警告）、`test:unit` 77 项、`test:api` 84 项、build、`test:e2e` 22 项（新增浏览器“返回离开页面→生成已取消且内容冻结”回归）、`_work/review-chat` 独立探针 4 项，全部通过。真实供应商仍未验证。e2e 本次以 `--output=tests/.e2e-output-20260907` 运行（沙箱批量删除守卫拦截旧 `test-results/` 清理，未删除既有产物；该目录已进 .gitignore）。

### 下一阶段执行提示词（下一轮 B，已于本日下一阶段实施，留档）

> 项目 H:\备份xuexi\智启课源。先读根与 apps/web 的 AGENTS.md、docs/replica/REVIEW_2026-09-07.md（R1–R4 已修复，读“修复记录”）、docs/replica/HANDOFF.md 最新一节；聊天动手前先读 apps/web/src/features/chat/ 全部源码，以当前源码为准。本次只实施“聊天扩展目录联动＋工具过程面板”：把 services/extension-catalog.ts 的变更订阅接入模拟聊天服务，展示已启用的 MCP/Skills；在统一事件服务的 tool/process 事件上实现消息内工具过程展示（按 callId 更新，覆盖 running/done/error/cancelled，重复更新不产生重复卡片，取消/终态不留“运行中”）；发送时冻结本轮配置快照，重试沿用原快照，设置变更只影响下一轮；真实模式继续明确“未接入外部工具”，零外部调用。严格遵守 R1–R3 修复语义：卸载/取消清理幂等（含 StrictMode）、固定模式 store 单一仓储、终态后拒绝阶段/过程事件，不得回退；事件类型可在本轮改为 type 判别式联合（审查“下一轮 A”遗留项），并保证 text.delta、tool.call 必要字段不可缺失。模拟脚本覆盖无扩展、单扩展、多扩展、一次失败、取消；过程持久化，刷新显示历史而不重新执行。对照原版 trace 展开动画，使用已登记的 300ms 参数及减少动画机制，不在每次正文增量重播卡片动画。运行 typecheck、lint、test:unit、build、test:e2e，更新 docs/replica 三个矩阵、HANDOFF 与审查报告状态。不接真实 MCP/Skills 服务，不动教案模块，不升级依赖，不自动提交 Git。

## 统一聊天事件服务＋最小模拟对话闭环（2026-09-06，用户指定阶段）

### 实际完成内容

- 统一聊天事件服务（`features/chat/model/chat-service.ts`）：定义 `ChatService` 接口与 `ChatServiceEvent` 联合类型，事件覆盖开始、正文增量、推理增量、过程增量、阶段、工具、等待用户、产物、用量、完成、错误；全部事件携带 `sessionId + turnId`。分类对齐参考仓库 v1.6.5 `web/contracts/generated/turn-protocol.ts` 的 `StreamEventType`（thinking→reasoning、content→text、done→end 等），工具/等待用户/产物为预留类型（类型已定义、消费方待后续阶段接入）。
- 真实实现 `createRealChatService`：包装现有 `streamChat` SSE 客户端，真实路径行为不变；旧测试的 `stream` 依赖继续兼容。
- 模拟实现 `createMockChatService`：纯本地脚本流式输出，回复带【模拟回复】标识；支持 `armFailure()` 布防一次失败（先输出部分文本再返回可重试 `MOCK_ERROR`）；不访问真实模型、MCP 或外部工具。
- store 双模式改造（构造时固定 `mode`，模式切换由上层在两个 store 实例间选择）：会话仓储按模式分离——真实走原 IndexedDB 库，模拟走独立库 `zhiqikeyuan-chat-mock`；会话列表按模式过滤；`send/retry` 在模拟模式接受无模型档案；事件消费带 turnId/sessionId 守卫，取消后、切换会话后的迟到事件一律丢弃。
- 界面闭环：工具栏新增“真实 / 模拟”分段切换；模拟模式下显示蓝色横幅（含“模拟一次失败”布防按钮）、模型选择器替换为“模拟模式 · 不访问真实模型”标识；输入→发送→流式→完成全流程可用，停止/重试/切会话/刷新恢复均验证。
- 过程增量（process）与阶段（stage）事件已消费：模拟回复前显示“正在组织回答”阶段与过程说明行；工具过程完整工作区待后续阶段。

### 修改文件与新增接口

- 新增：`features/chat/model/chat-service.ts`、`features/chat/model/chat-service.test.ts`、`features/chat/model/mock-mode.test.ts`、`tests/e2e/chat-mock.spec.ts`。
- 修改：`features/chat/model/store.ts`（双模式双仓储双服务、事件路由守卫）、`features/chat/model/ChatContext.tsx`（双 store 会话上下文、模式切换）、`features/chat/ChatWorkspace.tsx`（模式切换、横幅、发送分支）、`features/chat/Message.tsx`（stage/process 展示）、`features/chat/InfoPanel.tsx`（模拟说明）、`features/chat/styles/chat.css`、`contracts/chat.ts`（`ChatServiceKind`、会话 `mode`、消息 `stageLabel/processNote`）、`services/chat-stream.ts`（`reasoning.delta` 事件，本阶段早前完成）。
- 新增公共接口：`ChatService`/`ChatServiceEvent`/`createRealChatService`/`createMockChatService`（chat-service.ts）；store 构造项 `mode`/`mockRepository`/`services`。

### 实际运行命令和结果

- `npm run typecheck`、`npm run lint`（0 警告）、`npm run test:unit`（68 项通过，含新增 chat-service 4 项与 mock-mode 5 项）、`npm run test:api`（84 项通过）、`npm run build` 通过。
- `npm run test:e2e`：21 项通过，含新增 `chat-mock.spec.ts` 3 项（发送→流式→完成→隔离→刷新恢复；连续发送不重复+停止后不再追加；模拟失败→明确错误→重试成功）。
- 截图证据：`test-results/chat-mock-模拟模式发送…/chat-mock-1440.png`（模拟模式完整界面）；每次 e2e 运行自动重新生成。

### 已知问题和未完成项

- 真实供应商未验证：本轮未调用真实模型供应商，真实 SSE 行为由既有单测与浏览器回归覆盖。
- 工具事件、等待用户、产物工作区仅有类型与扩展位置；聊天中与模拟扩展目录（`services/extension-catalog.ts`）的联动未接入。
- 追问交互、过程完整工作区、聊天与面板的完整动画（MOTION_MATRIX 其余条目）待后续阶段。
- 模式切换在生成进行中被禁用（需先停止）；未做生成中后台切换。
- e2e 中中文输入法真实组合输入无法模拟，Enter/Shift+Enter 与 `isComposing` 守卫以代码审查+单测覆盖。

### 下一阶段执行提示词（可直接复制）

> 项目 H:\备份xuexi\智启课源。先读根与修改目录 AGENTS.md、docs/replica 四份文档与 docs/replica/HANDOFF.md 最新一节。本次只实施“聊天扩展目录联动＋工具过程面板”：把 services/extension-catalog.ts 的变更订阅接入模拟聊天服务，在统一事件服务的 tool/process 事件上实现消息内工具过程展示（运行/完成/失败状态），保持真实问答路径不变、模拟标识清晰；覆盖启用/禁用扩展后的行为差异、事件迟到与取消的回归；运行 typecheck、lint、test:unit、build、test:e2e 并更新 docs/replica 三个矩阵与 HANDOFF。不接真实 MCP/Skills 服务，不动教案模块，不自动提交 Git。

## 上一阶段：设置分类、MCP/Skills 本地模拟与减少动画（2026-09-06）

完成参考基线、路由扫描矩阵、AI 交互和动画待办登记；落地设置分类、搜索、锚点定位、MCP/Skills 旧入口重定向及本地模拟管理。
已实现模拟扩展添加、编辑、搜索、启用、删除确认和检测说明；同一目录提供变更订阅，尚未接入聊天选择器。
减少动画偏好支持系统设置、用户覆盖、刷新及跨标签页同步；列表进入动画已实现。

验证：

- TypeScript、Lint、生产构建通过。
- 单元测试 59 项通过，包含原有聊天、教案、模型管理测试及新增模拟目录测试。
- 原导航与设置浏览器测试 6 项通过，含教案编辑后导航往返不丢草稿。
- 新增设置流程浏览器测试通过，覆盖重定向、启用保存、刷新、分类定位和手机无页面横向溢出。
- 查看了桌面和手机截图。录屏尝试在浏览器上下文关闭时超时，未完成动态录像验收；`REPLICA_VIDEO=1` 可单独重试。
- 未调用真实供应商或真实 MCP 服务，未运行本轮 Word/PDF 完整导出验收。

未完成（不可标为完整复刻）：

全量页面和原版视觉、全部设置分类、MCP 商店、Skills 标签与商店、统一 ChatService、聊天能力选择联动、复杂事件模拟、追问与产物工作区、聊天及面板完整动画、全部响应式主题与综合验收均待后续实施。
当前属于阶段 01/02 的部分落地，不代表用户要求的八阶段已全部完成。

工程状态：

目标仓库原有文件多数未被 Git 跟踪，保持现状，未自动提交。参考仓库未改动。
目标模型服务未启动时仍显示准确错误，不以模拟模型代替。
