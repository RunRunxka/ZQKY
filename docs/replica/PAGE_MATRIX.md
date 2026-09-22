# 页面复刻矩阵（功能与视觉分开验收）

更新：2026-09-20（整理摘要与统计，不升级条目验收状态）。全站视觉以当前学习问答为准；模块信息结构/功能/动画对照固定 DeepTutor。下表“状态”是**功能状态**；页面内容是否按学习问答完成视觉验收在文末单列，二者不得互相替代。根级 NavigationPreference 的公共壳证据不代替各页面内容证据。

历史主页/侧栏批次记录已合入 [交付历史](../archive/DELIVERY_HISTORY.md#snapshot-status-20260910)。主聊天运行时模拟服务、切换入口及不可达文案/样式已由R-03清理；旧兼容类型和模拟测试仅是历史/测试用途，旧模拟库不读写。阅读、写作等模块已批准的显式模拟继续单独标注。当前代码审查问题见 [STATUS §3](../STATUS.md)。

2026-09-22 main 审查：`P-books-[bookId]` / `P-books-pages-[pageId]` 保持部分实现，新增读取失败加载不退出、修复任务归属与忙态、方向键干扰编辑等未修复项；参见 [M22-01～06](../qa/main-review-20260922/README.md)。历史视觉部分验收保留，本轮未重新进行浏览器/视觉验收。

基线提交：42fab3cf429a1fbf36b257ab8d116a3814964202（固定版本源码核对）。状态词汇：`待实现` / `部分实现` / `实现待验收` / `已验收` / `实现待修复` / `真实服务未接入`。条目 id 稳定规则：`P-<路由段>`，动态段用 `[x]` 占位。

**S1 状态（R18 修正）**：矩阵框架完成；规格部分完成——各批实施前须先补该批条目的组件来源、弹窗/抽屉、状态机、出入路径、持久化与动画来源，再实现验收。分类：**参考产品页 50**、目标自有页 1（教案）、目标兼容别名 2（/mcp、/skills，目标侧仅重定向，不计页面完成量）；内部调试 1 不计分母。**非调试条目 53**：统计见下表末尾，由实际行生成；旧历史计数不作为当前完成度。

| id | 参考路由 | 目标路由 | 状态 | 范围摘要与证据 |
| --- | --- | --- | --- | --- |
| P-root | `/` | `/` | 已验收 | 默认跳转 /chat；单一主页来源 HOME_PATH 派生，e2e `shell-home-nav.spec.ts` 断言标题与品牌入口 |
| P-chat | `/chat` | `/chat` | 部分实现 | 当前全站视觉基准：220/56px 导航、独立236px学习记录列、912px内容上限、输入区图标/字体/思考球与模型弹层。普通真实聊天及本地历史已有；运行时模拟服务与切换入口已删除，R-03生产mock残留已清理，复杂能力真实通道未接。历史主页和 H0 侧栏回归不代表全产品或真实供应商通过。 |
| P-chat-[sessionId] | `/chat/[sessionId]` | `/chat/[sessionId]` | 实现待验收 | 与当前主页共用外观，真实会话深链/恢复/无效id处理已有；旧mode参数不恢复模拟。完整消息交互、历史数据与跨页来源待核验；侧栏父菜单高亮由 WorkspaceShell 统一。 |
| P-settings | `/settings` | `/settings` | 实现待验收 | 分类导航/锚点/搜索、模型真实管理、扩展模拟管理已有。2026-09-13 MODEL-EXEC v3 完成模型区域重做（供应商卡片→详情→模型列表，保留蓝色与真实目录，独立审查 MR-07/08/12/13/14/16 已修且后续独立复验；9965592补嵌套/草稿/焦点，设置全页与全部动画仍未整体通过）。B-H0R-SHELL 批已收口其公共壳与当前菜单（唯一主页/唯一当前项/统一 404 壳）。其他 S6 设置整合仍待实现。**B-R05-EXTEND v4（2026-09-19）视觉推广**：索引导航图标+双态+焦点环（保留 `aria-current="location"` 与 160ms）、搜索框 focus+清除按钮+无结果空态、ExtensionManager 卡片/开关视觉、外观与关于分区排版；**模型区 contract-v1 零改动**（`model-settings/**` 与 `chat/**` diff 全空）；390 页面级溢出归零。A1 pass 33/0/4（含模型区 mock 成功态全链路）见 [报告](../qa/B-R05-EXT4/A1-REPORT.md) |
| P-lesson-plans | —（目标自有） | `/lesson-plans` | 已验收 | 目标项目既有教案工作台，保留独立地址与导航入口；首页现为 /chat；e2e `lesson-plan.spec.ts` 回归。**B-R05-EXTEND v4（2026-09-19）视觉推广**：表单分区/type-chip/模板卡视觉、预览工具栏 hover/disabled、toast 与 storage-alert 视觉（文案与 role 未动）、导航分段微调、导出菜单进场 180ms（对齐 /chat 基准）。**导出与草稿链路零改动**（`print.css`、`@page lesson-plan`、Word 映射、防抖/flush、`pagination.ts`、`--serif` 回退链）；A1 复核 `verifyDocx` 全项通过、损坏草稿不覆盖 |
| P-space | `/space` | `/space` | 部分验收 | 学习空间仪表盘（S5-A）：3 组磁贴+实时计数（会话/题库/笔记/角色/CLI/技能/MCP）；whisper 磁贴按参考行为隐藏（树外插件能力本地不存在）；e2e `space-pages.spec.ts`。**B-R05-SPACE-VISUAL v1（2026-09-18）视觉迁移**：Lora 标题、图标块+计数+单位+ArrowUpRight 磁贴、脉冲骨架；三视口前后截图见 [qa README](../qa/space-r05-20260918/README.md)；功能全状态仍待验收 |
| P-space-chat-history | `/space/chat-history` | `/space/chat-history` | 实现待验收 | 会话历史目录（S5-A）：真实仓储搜索/归档筛选、内联重命名、删除确认、归档恢复、重开；2026-09-09 移除模拟筛选与库读取，旧模拟数据留存不清理；e2e 同上。**B-R05-EXTEND v5（2026-09-19）视觉推广**：计数 chip（`N 个会话`）+ 刷新 spinner 态、卡片/列表 hover 与焦点环、行头窄视口 wrap；`space.css` 只读、增量进新建 `space-sections.css` |
| P-space-questions | `/space/questions` | `/space/questions` | 实现待验收 | 题库（S5-A）：范围栏（全部/答错/未掌握/书签/未分类/分类）+计数、250ms 防抖搜索、排序、书签/已掌握/归类/删除、批量操作、分类管理、演示题目显式载入；数据与聊天"保存到题库"同仓储。**来源回链已修（R-10，2026-09-14）**：以真实 sessionId 定位会话，messageId 仅会话内定位；无身份不显示、会话删除提示不可用；**消息定位（2026-09-14）**：以 messageId 在会话内定位（messageId 仅会话内使用）；e2e `chat-message-locate.spec.ts`。**B-R05-EXTEND v5（2026-09-19）**：计数 chip + 刷新 spinner、refreshing 变暗（对照参考 `transition-opacity + opacity-60`）、选项/卡片视觉统一；范围栏与筛选语义未动 |
| P-space-personas | `/space/personas` | `/space/personas` | 实现待验收 | 角色目录（S5-A）：卡片网格、查看/新建/编辑/删除（弹层+重名校验）、演示角色显式载入；与聊天输入区"人设"共用 persona-catalog。**B-R05-EXTEND v5（2026-09-19）**：卡片 hover/焦点环视觉；**按裁定保留常驻三按钮**（hover 显隐会降低可达性且 e2e 依赖可点） |
| P-space-cli-apps | `/space/cli-apps` | `/space/cli-apps` | 实现待验收 | CLI 应用（S5-A）：已安装/目录双页签、本地登记安装（显式"模拟安装"标识）、启停/卸载、信任徽标；本地演示无执行能力。**B-R05-EXTEND v5（2026-09-19）**：卡片视觉统一 + 启停状态徽标色；**目录搜索/详情/分页按裁定不做**（依赖远程 catalog API，属新业务能力）；「模拟安装」等标注逐字保留 |
| P-space-mcp | `/space/mcp` | `/space/mcp`（跳设置#mcp） | 实现待验收 | 旧入口迁移跳转（S5-A）；参考为独立管理页，按既定决策重定向设置（有意差异）；e2e 断言锚点 |
| P-space-skills | `/space/skills` | `/space/skills`（跳设置#skills） | 实现待验收 | 同上（S5-A） |
| P-mcp | `/mcp` | `/mcp`（跳设置#mcp） | 已验收 | e2e `replica-settings.spec.ts` 覆盖重定向 |
| P-skills | `/skills` | `/skills`（跳设置#skills） | 已验收 | 同上 |
| P-knowledge-bases | `/knowledge-bases` | `/knowledge-bases` | 实现待验收 | 教材资料库列表（S5-B/H1）：知识库/检索引擎双页签、演示载入幂等、新建重名拒绝、KB 级流水线状态徽标（空/待处理/处理中/已就绪/有失败，对照参考 KbStatusBadge）。2026-09-11 H1：登记/解析/索引为显式模拟，未接真实服务；e2e `knowledge-notebooks.spec.ts`。**B-R05-EXTEND v1（2026-09-18）视觉推广**：下划线指示器页签（图标+计数徽标+aria-controls/tabpanel）、卡片状态圆点（处理中脉冲）与悬停 ChevronRight、hover 描边与焦点环、描述 line-clamp-2、空态图标块+主行动、搜索框内嵌图标、引擎分组图标+说明、错误条重试/关闭；三视口前后截图见 [批次证据](../qa/B-R05-EXTEND/README.md) |
| P-knowledge-bases-[kbName] | `/knowledge-bases/[kbName]` | 同 | 实现待验收 | 库详情（S5-B/H1）：文档/登记/来源/索引/设置分区；改名同步 URL、设默认库、删除确认；2026-09-11 补文档导入→解析→索引显式模拟：逐文档状态徽标（registered/parsing/indexing/ready/error）、进度条、取消/重试、全量解析、索引版本列表与重建（版本按 (docCount,chunkCount) 去重）、刷新恢复、旧数据兼容、损坏读取如实报错不覆盖。真实解析/向量检索未接；e2e 同上。出处 `_work/kb-h1/CONTRACT.md`。**B-R05-EXTEND v1（2026-09-18）视觉推广**：头部图标块+带图标状态徽标（Clock/Check/AlertTriangle）、分区导航改下划线页签（五个 exact 文本与 `nav[aria-label="知识库分区"]` 未变）、文档行操作悬停显隐+行内二段移除确认、批量操作进行中禁用防重入、索引区头部与版本行状态图标章 |
| P-notebooks | `/notebooks` | `/notebooks` | 实现待验收 | 笔记本列表（S5-B）：默认笔记本虚拟项、记录展开/编辑/移动复制/导出/删除；**来源回链已修（R-10，2026-09-14）**：仅当记录带真实 sessionId 且会话存在时显示「打开原会话」，链接不带 `?mode=mock`；会话删除提示来源不可用；**消息定位（2026-09-14）**：链接带可选 messageId，会话内定位并提示「已定位到来源消息」，消息删除提示「原消息已不存在」；e2e `chat-source-links.spec.ts`、`chat-message-locate.spec.ts`。**B-R05-EXTEND v1（2026-09-18）视觉推广**：左栏 168→250px（仅本页）、激活项 2.5px 指示条（200ms）、描述行、四类多色类型徽章（保留 `space-chip`）、时间戳常驻行头、行 hover、操作钮 150ms 过渡与 active 缩放、展开区 pop-in、ConsoleNotice 空/错态、删除后 URL 规范化、popstate 同步选中；A1 复验 pass 14/14，见 [批次证据](../qa/B-R05-EXTEND/A1-REPORT.md) |
| P-notebooks-[notebookId] | `/notebooks/[notebookId]` | 同 | 实现待验收 | 笔记本详情（S5-B）：深链选中、无效 id 报错、搜索；S5-D 起"发到笔记本"写入此目录；e2e 同上。**B-R05-EXTEND v1（2026-09-18）**：深链无效时错误独占呈现（不再与空态并列）、`popstate` 前进后退同步选中、删除后 URL 规范化；390 窄视口行头换行 + 时间戳第二行（A1 F2 修复） |
| P-books | `/books` | `/books` | 部分实现 | 统计/目录/演示无损载入/新建模拟提案/状态徽标/进度/删除已有。**H1-BOOKS-PIPELINE v2（2026-09-20）**：生成不再是"确认即同步 ready"——卡片对生成中/已暂停/生成失败/可阅读四态可见（生成中带脉冲圆点 + `n/m 章` 进度）；历史用例 books-courses.spec.ts 覆盖列表切片。**B-R05-EXTEND v2（2026-09-18）视觉推广**：卡片悬浮语言（150ms 抬升/阴影/箭头位移）、搜索 ≥640px 常驻 + 匹配计数行、删除改两击确认、章/页/时间图标化、异步按钮 busy；统计 chips 结构按队长裁定保留 |
| P-books-[bookId] | `/books/[bookId]` | `/books/[bookId]` | 部分实现 | 提案确认→大纲确认→阅读器状态分流、无效id、续读定位、重建确认、Markdown导出已有。**H1-BOOKS-PIPELINE v2（2026-09-20）**：确认大纲后进入异步流水线（活动条 46px + 阶段文案/章数/计时 + 展开详情；暂停横幅；paused 不自动续跑；已中断给「继续生成」；整轮失败给原因与「重试生成」；归档书生成入口禁用）；BookChatPanel 待补；不再把14类分发与作答保存列作从零开发。**B-R05-EXTEND v2（2026-09-18）**：确认提案/确认大纲 busy 态、模拟编译加载提示、侧栏长章节名截断、书签图标化、已读/未读视觉区分；窄视口 `≤900px` 解除侧栏吸顶（B-R05-EXT2-A1 实测 pass）；侧栏折叠/HealthBanner/Chat 按裁定属 H1 |
| P-books-pages-[pageId] | `/books/[bookId]/pages/[pageId]` | 同 | 部分实现 | BookBlockType/PageReader 已有14类分发、练习保存恢复、页内笔记、翻页/书签/已读进度。interactive/animation/concept_graph/figure等仅显式模拟形态，须逐类核参考交互；渲染类型数量不等于完整验收。**H1-BOOKS-PIPELINE v2（2026-09-20）**：页/块六态（排队·规划·编译中·就绪·部分失败·失败）+ 生成中/排队占位分两态 + 块失败卡与单块重试 + 页失败面板与整页重生成（保留笔记与块身份）+ 未生成页打开不登记已读 + 作答版本关系（`contentVersion` 由执行器按内容写入）；三视口/焦点/reduce/中断/快速开关实测见 [批次证据](../qa/H1-BOOKS-PIPELINE/README.md)。**B-R05-EXTEND v2 视觉推广未含此页**（样式文件共享 `books.css`，当时未触碰 PageReader） |
| P-courses | `/courses` | `/courses` | 实现待验收 | 课程目录（S5-C）：进行中/已归档折叠区、演示载入（幂等）、新建（颜色标记）；主导航入口按参考隐藏（hidden ready，路由可达）；**资源目录故障容错已修（R-11，2026-09-14）**：知识/笔记本/书籍目录读取失败时课程正文与大纲保留、显示错误与重试、不冒充空、不丢引用；e2e `course-resource-faults.spec.ts`。**B-R05-EXTEND v2（2026-09-18）视觉推广**：卡片悬浮语言、页脚资料数图标化 + 空资料直述（不显示未接入的会话数）、归档折叠头视觉过渡、创建按钮 busy；入口与归档结构按队长裁定保留 |
| P-courses-[courseId] | `/courses/[courseId]` | `/courses/[courseId]` | 部分实现 | 已有大纲逐行编辑、覆盖标记、下一单元提示、资料附加/移除、失效资源提示、约定与归档恢复；课程学习会话及聊天 course_id 关联尚未实现，须补齐并验收。e2e `books-courses.spec.ts` 仅覆盖已有切片。**B-R05-EXTEND v2（2026-09-18）**：大纲进度条（progressbar + 300ms 宽度过渡）、单元编号/covered 删除线/下一单元高亮/topics 截断；资料行 kind 图标 + 不可用后缀独立 shrink-0 + 移除钮 hover/focus 显隐；保存与归档 busy；R-11 三态经 A1 独立回归（含重试链路与损坏数据逐字节未变）。聚合磁贴/Mode-Persona 字段按裁定属 H1 |
| P-reading | `/reading` | `/reading` | 实现待验收 | 集合卡片、新建/删除、按稳定id无损合并演示已有，R26–R31有历史修复和回归。完整阅读交付仍待验收；不再沿用R26未修结论。见 reading-store 与阅读 review。**B-R05-EXTEND v3（2026-09-19）视觉推广**：集合卡片 hover 抬升与焦点环、计数 chip 图标化、空态图标+主行动；A1 独立验收 pass 0 fail 见 [报告](../qa/B-R05-EXT3/A1-REPORT.md) |
| P-reading-materials | `/reading/materials` | `/reading/materials` | 实现待验收 | text/pdf/epub/webpage/video/audio类型、显式模拟解析的queued/processing/ready/failed与取消重试、分配/删除已有；真实解析和媒体原视图未完成。见 MaterialLibrary、companion-service 与阅读 review。**B-R05-EXTEND v3（2026-09-19）**：筛选 2→4 tab（补解析中/失败，真实计数）、状态色点、行头窄视口 wrap 修复（390 超界 0）、空态增强；模拟标注逐字保留；A1 pass 0 fail |
| P-reading-[workspaceId] | `/reading/[workspaceId]` | `/reading/[workspaceId]` | 实现待验收 | 三栏阅读、segments批注定位、选区工具、书签/进度、事件驱动伴生模拟、按会话保存草稿与手机面板已有。**R-09 已修（2026-09-15）**：滚动跟随由用户控制、已测轮次按会话归属；错误态重试与重复/迟到end已于2026-09-18受控补测修复（STATUS READ-RETRY/READ-END），见 [STATUS阅读批索引](../STATUS.md#4-已完成批次与证据索引)。消息过程/来源完整性、媒体原视图待核验。**B-R05-EXTEND v5（2026-09-19）视觉推广 + R-09 增强修复**：按钮反馈过渡、材料 tab 截断（窄视口 N1）与解析中旋转指示、错误横幅可关闭、头部形态 chip 化；**同批受控诊断并修复 R-09 滚动跟随真实缺陷**（流式拉底 scroll 重置 followBottom，见 [STATUS §3](../STATUS.md)）；视觉分工保护原交互，R-09 产品修复另列，整批并非交互零改动。A1 独立验收 R-09 五例 5/5 + 压测 10/10 pass 0 fail |
| P-reading-sessions | `/reading/[workspaceId]/sessions` | `/reading/[workspaceId]/sessions` | 实现待验收 | 工作区会话入口及最近会话选择已有；**R-09 已修**：切会话改 `pushState`、`popstate` 按 URL 同步空间/会话/草稿，后退到无会话地址回落默认会话。见 ReadingWorkspace 与 [STATUS阅读批索引](../STATUS.md#4-已完成批次与证据索引)。**B-R05-EXTEND v5（2026-09-19）**：URL/历史语义未动（超出参考的目标自有增强，按裁定保留） |
| P-reading-sessions-[sessionId] | `/reading/[workspaceId]/sessions/[sessionId]` | 同 | 实现待验收 | 按routeSessionId恢复、无效会话提示与草稿归属已有；**R-09 已修**：前进/后退同步会话与草稿，已测跨会话事件归属受 `sessionId+turnId` 约束；重复/失效终态持久化另见STATUS的READ-END补测。正式回归见 `tests/e2e/reading.spec.ts` R-09 五例。**B-R05-EXTEND v5（2026-09-19）**：草稿归属与迟到事件守卫未动；A1 复核通过 |
| P-co-writer | `/co-writer` | `/co-writer` | 实现待验收 | 文档列表（S5-E）：新建空白/模板、删除确认、更新时间与字数；DOCX 导入未接入为显式说明；AI 修改为统一事件模型显式模拟；e2e `writing.spec.ts`。**B-R05-EXTEND v3（2026-09-19）视觉推广**：卡片 hover 过渡与焦点环、空态图标+主行动（按钮与页头区分命名，修复 strict 冲突）、按钮 opacity/scale 动效；模拟标注逐字保留 |
| P-co-writer-[docId] | `/co-writer/[docId]` | `/co-writer/[docId]` | 实现待验收 | 编辑器（S5-E）：即时自动保存与保存状态、选区改写/润色/扩写与全文生成（流式预览/应用/放弃/取消/失败重试，应用前自动快照）、撤销栈、版本历史与恢复；e2e 同上。**B-R05-EXTEND v3（2026-09-19）**：正文区样式迁出内联（focus 环）、保存三态 chip 色彩化、标题行/版本行整理；AI 预览与版本能力（超出参考的本地增强）按裁定保留；A1 pass 0 fail |
| P-whisper | `/whisper` | `/whisper` | 实现待验收 | Whisper 密室（S5-E，用途以固定源码为准）：双席位（访客/学员）分席会话、房间创建/结束态、危机表述系统引导卡（援助热线）；回复为显式模拟流式；能力未接入保留可演示前端路径；e2e 同上 |
| P-partners | `/partners` | `/partners` | 待实现 | 伙伴列表（S5-F） |
| P-partners-new | `/partners/new` | `/partners/new` | 待实现 | 创建/配置（S5-F） |
| P-partners-[partnerId] | `/partners/[partnerId]` | `/partners/[partnerId]` | 待实现 | 会话/详情（S5-F） |
| P-partners-groups-new | `/partners/groups/new` | `/partners/groups/new` | 待实现 | 群组创建（S5-F） |
| P-partners-groups-[groupId] | `/partners/groups/[groupId]` | `/partners/groups/[groupId]` | 待实现 | 群组会话（S5-F） |
| P-agents | `/agents` | `/agents` | 待实现 | 智能体任务/会话/过程/产物（S5-F）；运行配置在设置 |
| P-mastery | `/mastery` | `/mastery` | 待实现 | 精通之路路径（S5-G） |
| P-mastery-[pathId] | `/mastery/[pathId]` | `/mastery/[pathId]` | 待实现 | 主题/知识节点（S5-G） |
| P-mastery-sessions | `/mastery/[pathId]/sessions` | `/mastery/[pathId]/sessions` | 待实现 | 学习会话列表（S5-G） |
| P-mastery-sessions-[sessionId] | `/mastery/[pathId]/sessions/[sessionId]` | `/mastery/[pathId]/sessions/[sessionId]` | 待实现 | 作答/反馈/进度（S5-G） |
| P-memory | `/memory` | `/memory` | 待实现 | 分层记忆总览（S5-H） |
| P-memory-resolve | `/memory/resolve` | `/memory/resolve` | 待实现 | 冲突处理（S5-H） |
| P-memory-graph | `/memory/graph` | `/memory/graph` | 待实现 | 记忆图谱（S5-H） |
| P-memory-l1 | `/memory/l1` | `/memory/l1` | 待实现 | L1 内容（S5-H） |
| P-memory-l2 | `/memory/l2` | `/memory/l2` | 待实现 | L2 列表（S5-H） |
| P-memory-l2-[surface] | `/memory/l2/[surface]` | `/memory/l2/[surface]` | 待实现 | L2 详情（S5-H） |
| P-memory-l3 | `/memory/l3` | `/memory/l3` | 待实现 | L3 列表（S5-H） |
| P-memory-l3-[slot] | `/memory/l3/[slot]` | `/memory/l3/[slot]` | 待实现 | L3 详情（S5-H） |
| P-login | `/login` | `/login` | 待实现 | 本地演示身份（S5-I），不伪装真实鉴权 |
| P-register | `/register` | `/register` | 待实现 | 本地演示注册（S5-I） |
| P-profile | `/profile` | `/profile` | 待实现 | 个人信息（S5-I） |
| P-admin-users | `/admin/users` | `/admin/users` | 待实现 | 管理视图（S5-I），按原版权限表达 |
| P-avatar-preview | `/avatar-preview` | — | 内部调试 | 只登记；不纳入必需完成项，不暴露主导航 |

必需完成功能分母：除 P-avatar-preview 外共53项（参考产品页50 + 自有教案1 + 额外兼容别名2）。2026-09-20按现有行标签重算：**已验收4 / 实现待验收21 / 部分实现5 / 部分验收1 / 待实现22**；仅订正统计，未改任何行的功能状态。`P-space` 在既有批次被标为“部分验收”，仍保留全状态功能未验边界，不能与“已验收”合并。2026-09-12的80项e2e及知识库状态样本是历史证据，后续批次见STATUS；功能与视觉状态分别记录。

标签不是完整产品验收百分比：路由 ready、自动用例通过、视觉/动画验收与真实后端验证分开记录。改变状态或条目时重算本段，禁止保留第二份旧统计。

## 学习问答视觉验收状态

视觉状态使用“基准页 / 部分验收 / 未通过 / 待验收 / 待实现 / 无独立页面”。2026-09-12补验候选99aea55：36页面、4抽屉、8知识状态样本，48张截图，独立验收者实际查看20张代表图；整体未通过。具体测量见 [视觉证据](../qa/acceptance-20260912/visual-measurements.json)，不计算全站视觉完成率。

| 状态 | 页面范围 | 当前证据与缺口 |
| --- | --- | --- |
| 基准页 | `P-chat` | 蓝色主题、Chat Geist/Lora、220/56px 导航、236px 学习记录中栏、912px 对话列、模型弹层和思考球是全站来源 |
| 部分验收 | `P-chat-[sessionId]` | 2026-09-12 Flash测试预算8192的真实长答：465汉字、27处公式，三视口无页面级溢出、推理折叠和刷新恢复通过；默认预算两模型和Pro8192长答失败。后续R-10会话回链/消息定位已有独立功能证据；全消息视觉和真实交互仍待完整验收 |
| 部分验收 | `P-knowledge-bases-[kbName]` | 1920/390下就绪、失败、解析中显式模拟样本可读，系统减少动画下可到达就绪；完整内容风格、全部分区/弹窗与进度动画时序仍待验。**B-R05-EXTEND v1（2026-09-18）增补**：下划线页签、图标块头部、行悬停操作、二段确认与进行中禁用经 A1 独立验收 pass（三视口/焦点/reduce/溢出实测）；A1 明细见 [报告](../qa/B-R05-EXTEND/A1-REPORT.md) |
| 部分验收 | `P-knowledge-bases` | **B-R05-EXTEND v1（2026-09-18）**：下划线指示器页签+计数徽标、卡片状态圆点+悬停 ChevronRight、空态图标+主行动、搜索内嵌图标、引擎分组；三视口前后截图与 A1 独立验收见 [批次证据](../qa/B-R05-EXTEND/README.md)。全部分区/弹窗逐状态验收仍待后续批 |
| 部分验收 | `P-notebooks`、`P-notebooks-[notebookId]` | **B-R05-EXTEND v1（2026-09-18）**：左栏 250px+指示条、描述行、多色类型徽章、时间戳行头、pop-in、ConsoleNotice、深链/URL 语义；A1 首轮 needs_revision（390 窄视口两处缺陷）→ 修复候选复验 **pass 14/14**。记录编辑器形态、Markdown 渲染与 toast 系统按队长裁定未纳入，仍待后续批 |
| 部分验收 | `P-books`、`P-books-[bookId]` | **B-R05-EXTEND v2（2026-09-18）**：卡片悬浮语言/搜索常驻与匹配计数/两击删除/busy 态、详情确认 busy 与模拟编译加载提示、窄视口侧栏解除吸顶（390 实测随文档流、1440 恢复 sticky）。A1 独立验收 **pass 0 fail**（三视口 12 组合 0 溢出、长文案截断、reduce 压制）见 [报告](../qa/B-R05-EXT2/A1-REPORT.md)。**H1-BOOKS-PIPELINE v2（2026-09-20）**：生成流水线状态（活动条/展开详情/暂停横幅/继续生成/重试生成/归档只读）经三视口 + 焦点 + reduce 实测与独立验收 A1 **pass 32/0/0** 见 [A1 报告](../qa/H1-BOOKS-PIPELINE/A1-REPORT.md)。BookChatPanel、侧栏折叠、真实 LLM/解析仍属后续批 |
| 部分验收 | `P-courses`、`P-courses-[courseId]` | **B-R05-EXTEND v2（2026-09-18）**：卡片悬浮语言/页脚资料数/归档折叠头、大纲进度条与单元视觉、资料行显隐与不可用后缀、保存与归档 busy；R-11 三态与重试链路经 A1 独立回归（损坏数据逐字节未变）。A1 **pass 0 fail** 见 [报告](../qa/B-R05-EXT2/A1-REPORT.md)。课程学习会话、聚合磁贴、Mode/Persona 按裁定属 H1 |
| 部分验收 | `P-co-writer`、`P-co-writer-[docId]` | **B-R05-EXTEND v3（2026-09-19）**：列表卡片 hover/焦点环与空态图标+主行动、编辑器正文区样式与保存三态 chip、按钮动效。A1 独立验收 **pass 0 fail（31 项）** 见 [报告](../qa/B-R05-EXT3/A1-REPORT.md)。DOCX 导入、字数口径、分栏/同步滚动、参考式直建与两击删除按裁定属后续批 |
| 部分验收 | `P-reading`、`P-reading-materials` | **B-R05-EXTEND v3（2026-09-19）**：集合卡片 hover/焦点环与计数图标、材料库筛选 4 tab（真实计数）+ 状态色点 + 行头窄视口 wrap 修复（390 超界 0）+ 空态增强。A1 **pass 0 fail**（含 R-09 工作区不回退实测、模拟标注 9 条逐字命中）见 [报告](../qa/B-R05-EXT3/A1-REPORT.md)。LibraryShell 双 tab 化、网格化、搜索框、真实解析按裁定属后续批；`P-reading-[workspaceId]` 三栏工作区**不在本批** |
| 部分验收 | `P-settings` | **B-R05-EXTEND v4（2026-09-19）**：索引导航图标+双态+焦点环、搜索 focus/清除按钮/无结果空态、ExtensionManager 卡片与开关视觉、外观/关于分区排版。A1 独立验收 **pass（33/0/4）**，含模型区 mock 成功态全链路与 390 溢出归零，见 [报告](../qa/B-R05-EXT4/A1-REPORT.md)。模型区 contract-v1 结构与其动画按裁定保留现状；Overview 状态条/就绪面板/页级草稿工具栏/共享 Modal 动效属后续批 |
| 部分验收 | `P-lesson-plans` | **B-R05-EXTEND v4（2026-09-19）**：表单分区/type-chip/模板卡、预览工具栏 hover/disabled、toast/storage-alert 视觉、导出菜单进场 180ms。A1 **pass**（`verifyDocx` 导出全项、损坏草稿不覆盖、草稿恢复、跨页返回）；导出与草稿链路零改动见 [报告](../qa/B-R05-EXT4/A1-REPORT.md)。教案密集编辑区不强制 Lora（`--serif` 回退链保留）；硬编码色未替换、预览缩放过渡未加（按裁定保留） |
| 部分验收 | `P-reading-[workspaceId]`、`P-reading-sessions`、`P-reading-sessions-[sessionId]` | **B-R05-EXTEND v5（2026-09-19）**：三栏工作区视觉统一（按钮过渡/tab 截断与 busy 指示/错误横幅可关闭/头部 chip 化）；**同批受控诊断并修复 R-09 滚动跟随真实缺陷**（follow-bottom 竞争）。视觉分工保护原交互；该产品修复另列，不称整批零语义改动。A1 独立验收 **pass 0 fail**：R-09 五例 5/5、压测 `--repeat-each=10` 10/10、55 项浏览器实测，见 [报告](../qa/B-R05-EXT5/A1-REPORT.md)。媒体原视图与完整过程/来源仍待后续批 |
| 部分验收 | `P-space-chat-history`、`P-space-questions`、`P-space-personas`、`P-space-cli-apps` | **B-R05-EXTEND v5（2026-09-19）**：四页卡片/列表/工具条视觉统一、计数 chip + 刷新 spinner、题库 refreshing 变暗、CLI 状态徽标、行头窄视口 wrap。真实计数/筛选/搜索/批量/演示载入/来源回链（R-10）保留；`space.css` 只读。A1 pass（`space-pages` 8/8、`chat-source-links` 21/21、`chat-message-locate` 12/12）见 [报告](../qa/B-R05-EXT5/A1-REPORT.md)。CLI 搜索/详情/分页与角色卡 hover 显隐按裁定不做 |
| 部分验收 | `P-space` | **B-R05-SPACE-VISUAL v1（2026-09-18）**：标题/分组标签迁 Chat Lora（--font-display）、磁贴对照参考 DashboardCard 迁移（40px 图标块+大数字计数+单位+ArrowUpRight+脉冲骨架+hover 上浮阴影）、仪表盘不显示自指返回链接；真实计数/全部跳转/演示标识保留。三视口前后截图+焦点+reduce 动画证据 [docs/qa/space-r05-20260918](../qa/space-r05-20260918/README.md)；unit297/e2e154 通过。功能级完整验收（弹窗/错误/长文案逐状态）仍待后续批 |
| 部分验收 | `P-books-pages-[pageId]` | **H1-BOOKS-PIPELINE v2（2026-09-20）**（本批升级：三视口截图 + 量化动画数据 + 独立验收）：页/块六态与四类失败呈现、块占位两态、重试与整页重生成、归档只读；1440×900/1920×1080/390×844 溢出 0、焦点环 2px、reduce 压制（浮层/呼吸 `1e-05s`）、快速开关净关闭、展开中暂停不卡死。证据 [visual/evidence.json](../qa/H1-BOOKS-PIPELINE/visual/evidence.json) + [A1 报告](../qa/H1-BOOKS-PIPELINE/A1-REPORT.md)（pass 32/0/0）。逐帧曲线、硬件触摸、14 类 block 逐类交互对照仍属 H6/后续批 |
| 待验收 | （当前无条目） | `P-books-pages-[pageId]` 已由 H1-BOOKS-PIPELINE v2（2026-09-20）按三视口 + 焦点 + reduce + 量化动画证据升级为部分验收（见上表）；其余历史条目已由 B-R05-EXTEND v1~v5 移入部分验收（知识库/笔记本/书籍/课程/写作/阅读库/设置/教案/阅读工作区/space 子页） |
| 待实现 | `P-papers`、`P-question-bank`、`P-templates`、`P-partners*`、`P-agents`、`P-mastery*`、`P-memory*`、`P-login`、`P-register`、`P-profile`、`P-admin-users` | 规划状态页不是最终业务视觉验收；正式页面实现时直接按学习问答基准建设 |
| 无独立页面 | `P-root`、`P-space-mcp`、`P-space-skills`、`P-mcp`、`P-skills` | 仅重定向；验收目标是去向、历史、焦点和最终页面当前菜单 |

每个页面升级视觉状态时必须提供 1440×900、1920×1080、390×844、键盘/焦点、长文/空态/错误和减少动画证据；业务功能状态保持独立。

H0 公共壳是横向证据：现有页面已共用 220/56px 侧栏、折叠偏好和选定响应式行为，但这不为任何页面内容区授予“部分验收”。隐藏直达页当前菜单/抽屉焦点和404壳已由e7fb2a4修复；错误页reset运行时仍未验。各模块后续视觉证据与缺口按上表分别保留。

历史额外错误场景 `/acceptance-404` 在2026-09-12无壳且返回教案，首败保留；R-02/R-06已于e7fb2a4修复并有404浏览器复验，不继续列作当前缺陷。错误态不增加53项分母；全主题/详情/弹窗及错误reset运行时仍未全部覆盖。

R-05 在登记的既有页面推广范围内已收口（沿用2026-09-19记录），依据与边界见 [STATUS 当前批次](../STATUS.md#current-task)。这不升级上表“部分验收/待验收”标签；`P-books-pages-[pageId]` 的标签另行由 H1-BOOKS-PIPELINE v2（2026-09-20）按其自身的三视口 + 焦点 + reduce + 量化动画与独立验收证据单独升级为部分验收（与 R-05 收口无关）。`待实现` 模块按 `/chat` 基准建设，动画精度随 H6 总验收补齐；新任务以用户指令与STATUS为准，不重复执行已交付批次。
