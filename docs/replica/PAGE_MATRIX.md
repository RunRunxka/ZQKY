# 页面复刻矩阵（功能与视觉分开验收）

更新：2026-09-12。全站视觉以当前学习问答为准；模块信息结构/功能/动画对照固定 DeepTutor。下表“状态”是**功能状态**；页面内容是否按学习问答完成视觉验收在文末单列，二者不得互相替代。根级 NavigationPreference 已统一侧栏几何和折叠状态，但不代表各页面内容视觉已统一。

历史主页/侧栏批次记录已合入 [交付历史](../archive/DELIVERY_HISTORY.md#snapshot-status-20260910)。主聊天运行时模拟服务和切换入口已删除，但主聊天会话契约、文案和样式仍有 mock 残留；旧模拟测试仅是历史证据。阅读、写作等模块已批准的显式模拟继续单独标注。当前代码审查问题见 [STATUS §3](../STATUS.md)。

基线提交：42fab3cf429a1fbf36b257ab8d116a3814964202（固定版本源码核对）。状态词汇：`待实现` / `部分实现` / `实现待验收` / `已验收` / `实现待修复` / `真实服务未接入`。条目 id 稳定规则：`P-<路由段>`，动态段用 `[x]` 占位。

**S1 状态（R18 修正）**：矩阵框架完成；规格部分完成——各批实施前须先补该批条目的组件来源、弹窗/抽屉、状态机、出入路径、持久化与动画来源，再实现验收。分类：**参考产品页 50**、目标自有页 1（教案）、目标兼容别名 2（/mcp、/skills，目标侧仅重定向，不计页面完成量）；内部调试 1 不计分母。**非调试条目 53**：统计见下表末尾，由实际行生成；旧历史计数不作为当前完成度。

| id | 参考路由 | 目标路由 | 状态 | 范围摘要与证据 |
| --- | --- | --- | --- | --- |
| P-root | `/` | `/` | 已验收 | 默认跳转 /chat；单一主页来源 HOME_PATH 派生，e2e `shell-home-nav.spec.ts` 断言标题与品牌入口 |
| P-chat | `/chat` | `/chat` | 部分实现 | 当前全站视觉基准：220/56px 导航、独立236px学习记录列、912px内容上限、输入区图标/字体/思考球与模型弹层。普通真实聊天及本地历史已有；运行时模拟服务与切换入口已删除，生产 mock 残留见 STATUS R-03，复杂能力真实通道未接。历史主页和 H0 侧栏回归不代表全产品或真实供应商通过。 |
| P-chat-[sessionId] | `/chat/[sessionId]` | `/chat/[sessionId]` | 实现待验收 | 与当前主页共用外观，真实会话深链/恢复/无效id处理已有；旧mode参数不恢复模拟。完整消息交互、历史数据与跨页来源待核验；侧栏父菜单高亮由 WorkspaceShell 统一。 |
| P-settings | `/settings` | `/settings` | 实现待验收 | 分类导航/锚点/搜索、模型真实管理、扩展模拟管理已有。2026-09-13 MODEL-EXEC v3 完成模型区域重做（供应商卡片→详情→模型列表，保留蓝色与真实目录，独立审查 MR-07/08/12/13/14/16 已修，e2e `model-settings.spec.ts` 8 项 + 真实联调 5 项）。B-H0R-SHELL 批已收口其公共壳与当前菜单（唯一主页/唯一当前项/统一 404 壳）。其他 S6 设置整合仍待实现 |
| P-lesson-plans | —（目标自有） | `/lesson-plans` | 已验收 | 目标项目既有教案工作台，保留独立地址与导航入口；首页现为 /chat；e2e `lesson-plan.spec.ts` 回归 |
| P-space | `/space` | `/space` | 实现待验收 | 学习空间仪表盘（S5-A）：3 组磁贴+实时计数（会话/题库/笔记/角色/CLI/技能/MCP）；whisper 磁贴按参考行为隐藏（树外插件能力本地不存在）；e2e `space-pages.spec.ts` |
| P-space-chat-history | `/space/chat-history` | `/space/chat-history` | 实现待验收 | 会话历史目录（S5-A）：真实仓储搜索/归档筛选、内联重命名、删除确认、归档恢复、重开；2026-09-09 移除模拟筛选与库读取，旧模拟数据留存不清理；e2e 同上 |
| P-space-questions | `/space/questions` | `/space/questions` | 实现待验收 | 题库（S5-A）：范围栏（全部/答错/未掌握/书签/未分类/分类）+计数、250ms 防抖搜索、排序、书签/已掌握/归类/删除、批量操作、分类管理、演示题目显式载入；数据与聊天"保存到题库"同仓储。**来源回链已修（R-10，2026-09-14）**：以真实 sessionId 定位会话，messageId 仅会话内定位；无身份不显示、会话删除提示不可用；**消息定位（2026-09-14）**：以 messageId 在会话内定位（messageId 仅会话内使用）；e2e `chat-message-locate.spec.ts` |
| P-space-personas | `/space/personas` | `/space/personas` | 实现待验收 | 角色目录（S5-A）：卡片网格、查看/新建/编辑/删除（弹层+重名校验）、演示角色显式载入；与聊天输入区"人设"共用 persona-catalog |
| P-space-cli-apps | `/space/cli-apps` | `/space/cli-apps` | 实现待验收 | CLI 应用（S5-A）：已安装/目录双页签、本地登记安装（显式"模拟安装"标识）、启停/卸载、信任徽标；本地演示无执行能力 |
| P-space-mcp | `/space/mcp` | `/space/mcp`（跳设置#mcp） | 实现待验收 | 旧入口迁移跳转（S5-A）；参考为独立管理页，按既定决策重定向设置（有意差异）；e2e 断言锚点 |
| P-space-skills | `/space/skills` | `/space/skills`（跳设置#skills） | 实现待验收 | 同上（S5-A） |
| P-mcp | `/mcp` | `/mcp`（跳设置#mcp） | 已验收 | e2e `replica-settings.spec.ts` 覆盖重定向 |
| P-skills | `/skills` | `/skills`（跳设置#skills） | 已验收 | 同上 |
| P-knowledge-bases | `/knowledge-bases` | `/knowledge-bases` | 实现待验收 | 教材资料库列表（S5-B/H1）：知识库/检索引擎双页签、演示载入幂等、新建重名拒绝、KB 级流水线状态徽标（空/待处理/处理中/已就绪/有失败，对照参考 KbStatusBadge）。2026-09-11 H1：登记/解析/索引为显式模拟，未接真实服务；e2e `knowledge-notebooks.spec.ts` |
| P-knowledge-bases-[kbName] | `/knowledge-bases/[kbName]` | 同 | 实现待验收 | 库详情（S5-B/H1）：文档/登记/来源/索引/设置分区；改名同步 URL、设默认库、删除确认；2026-09-11 补文档导入→解析→索引显式模拟：逐文档状态徽标（registered/parsing/indexing/ready/error）、进度条、取消/重试、全量解析、索引版本列表与重建（版本按 (docCount,chunkCount) 去重）、刷新恢复、旧数据兼容、损坏读取如实报错不覆盖。真实解析/向量检索未接；e2e 同上。出处 `_work/kb-h1/CONTRACT.md` |
| P-notebooks | `/notebooks` | `/notebooks` | 实现待验收 | 笔记本列表（S5-B）：默认笔记本虚拟项、记录展开/编辑/移动复制/导出/删除；**来源回链已修（R-10，2026-09-14）**：仅当记录带真实 sessionId 且会话存在时显示「打开原会话」，链接不带 `?mode=mock`；会话删除提示来源不可用；**消息定位（2026-09-14）**：链接带可选 messageId，会话内定位并提示「已定位到来源消息」，消息删除提示「原消息已不存在」；e2e `chat-source-links.spec.ts`、`chat-message-locate.spec.ts` |
| P-notebooks-[notebookId] | `/notebooks/[notebookId]` | 同 | 实现待验收 | 笔记本详情（S5-B）：深链选中、无效 id 报错、搜索；S5-D 起"发到笔记本"写入此目录；e2e 同上 |
| P-books | `/books` | `/books` | 部分实现 | 统计/目录/演示无损载入/新建模拟提案/状态徽标/进度/删除已有。生成目前为同步模拟；compiling/paused/error和流式生成、暂停恢复仍缺，见 STATUS H1。历史用例 books-courses.spec.ts 覆盖已有切片。 |
| P-books-[bookId] | `/books/[bookId]` | `/books/[bookId]` | 部分实现 | 提案确认→大纲确认→阅读器状态分流、无效id、续读定位、重建确认、Markdown导出已有。流水线状态和 BookChatPanel 待补；不再把14类分发与作答保存列作从零开发。 |
| P-books-pages-[pageId] | `/books/[bookId]/pages/[pageId]` | 同 | 部分实现 | BookBlockType/PageReader 已有14类分发、练习保存恢复、页内笔记、翻页/书签/已读进度。interactive/animation/concept_graph/figure等仅显式模拟形态，须逐类核参考交互；渲染类型数量不等于完整验收。 |
| P-courses | `/courses` | `/courses` | 实现待验收 | 课程目录（S5-C）：进行中/已归档折叠区、演示载入（幂等）、新建（颜色标记）；主导航入口按参考隐藏（hidden ready，路由可达）；**资源目录故障容错已修（R-11，2026-09-14）**：知识/笔记本/书籍目录读取失败时课程正文与大纲保留、显示错误与重试、不冒充空、不丢引用；e2e `course-resource-faults.spec.ts` |
| P-courses-[courseId] | `/courses/[courseId]` | `/courses/[courseId]` | 部分实现 | 已有大纲逐行编辑、覆盖标记、下一单元提示、资料附加/移除、失效资源提示、约定与归档恢复；课程学习会话及聊天 course_id 关联尚未实现，须补齐并验收。e2e `books-courses.spec.ts` 仅覆盖已有切片。 |
| P-reading | `/reading` | `/reading` | 实现待验收 | 集合卡片、新建/删除、按稳定id无损合并演示已有，R26–R31有历史修复和回归。完整阅读交付仍待验收；不再沿用R26未修结论。见 reading-store 与阅读 review。 |
| P-reading-materials | `/reading/materials` | `/reading/materials` | 实现待验收 | text/pdf/epub/webpage/video/audio类型、显式模拟解析的queued/processing/ready/failed与取消重试、分配/删除已有；真实解析和媒体原视图未完成。见 MaterialLibrary、companion-service 与阅读 review。 |
| P-reading-[workspaceId] | `/reading/[workspaceId]` | `/reading/[workspaceId]` | 实现待验收 | 三栏阅读、segments批注定位、选区工具、书签/进度、事件驱动伴生模拟（流式/取消/失败重试）、按会话保存草稿与手机面板已有。消息过程/来源完整性、增量强制回底、媒体原视图待核验；历史R32补齐仅覆盖当时切片。 |
| P-reading-sessions | `/reading/[workspaceId]/sessions` | `/reading/[workspaceId]/sessions` | 实现待验收 | 工作区会话入口及最近会话选择已有；会话切换仍有replaceState，须复核前进后退与异步归属。见 ReadingWorkspace 和 STATUS H-R1。 |
| P-reading-sessions-[sessionId] | `/reading/[workspaceId]/sessions/[sessionId]` | 同 | 实现待验收 | 按routeSessionId恢复、无效会话提示与草稿归属已有；不得用历史局部用例替代会话切换/浏览器历史/旧任务隔离完整验收。 |
| P-co-writer | `/co-writer` | `/co-writer` | 实现待验收 | 文档列表（S5-E）：新建空白/模板、删除确认、更新时间与字数；DOCX 导入未接入为显式说明；AI 修改为统一事件模型显式模拟；e2e `writing.spec.ts` |
| P-co-writer-[docId] | `/co-writer/[docId]` | `/co-writer/[docId]` | 实现待验收 | 编辑器（S5-E）：即时自动保存与保存状态、选区改写/润色/扩写与全文生成（流式预览/应用/放弃/取消/失败重试，应用前自动快照）、撤销栈、版本历史与恢复；e2e 同上 |
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

必需完成功能分母：除 P-avatar-preview 外共53项（参考产品页50 + 自有教案1 + 额外兼容别名2）。2026-09-12按实际行复核：**已验收4 / 实现待验收21 / 部分实现6 / 待实现22**。本次80项既有e2e通过，并补知识库1920/390状态样本；这些检查未覆盖所有条目完整规格，功能标签不因样本通过整体升级。功能与视觉状态分别记录。

标签不是完整产品验收百分比：路由 ready、自动用例通过、视觉/动画验收与真实后端验证分开记录。改变状态或条目时重算本段，禁止保留第二份旧统计。

## 学习问答视觉验收状态

视觉状态使用“基准页 / 部分验收 / 未通过 / 待验收 / 待实现 / 无独立页面”。2026-09-12补验候选99aea55：36页面、4抽屉、8知识状态样本，48张截图，独立验收者实际查看20张代表图；整体未通过。具体测量见 [视觉证据](../qa/acceptance-20260912/visual-measurements.json)，不计算全站视觉完成率。

| 状态 | 页面范围 | 当前证据与缺口 |
| --- | --- | --- |
| 基准页 | `P-chat` | 蓝色主题、Chat Geist/Lora、220/56px 导航、236px 学习记录中栏、912px 对话列、模型弹层和思考球是全站来源 |
| 部分验收 | `P-chat-[sessionId]` | 2026-09-12 Flash测试预算8192的真实长答：465汉字、27处公式，三视口无页面级溢出、推理折叠和刷新恢复通过；默认预算两模型和Pro8192长答失败。完整消息交互、历史数据和跨页来源仍待核验 |
| 部分验收 | `P-knowledge-bases-[kbName]` | 1920/390下就绪、失败、解析中显式模拟样本可读，系统减少动画下可到达就绪；完整内容风格、全部分区/弹窗与进度动画时序仍待验 |
| 未通过（收窄） | `P-settings`、`P-lesson-plans`、`P-space`、`P-knowledge-bases`、`P-notebooks`、`P-books`、`P-courses`、`P-reading`、`P-co-writer`、`P-whisper` | 三视口巡检确认内容字体/标题/卡片体系仍**未按 chat 统一**（R-05，视觉统一另批处理）。**R-04 的当前菜单问题已由 B-H0R-SHELL v1 修复并关闭**：courses/notebooks/whisper 现标记可见父菜单、抽屉焦点落在当前项；因此不再以“缺当前菜单”作为这些页面的未通过理由。 |
| 待验收 | `P-space-chat-history`、`P-space-questions`、`P-space-personas`、`P-space-cli-apps`、`P-notebooks-[notebookId]`、`P-books-[bookId]`、`P-books-pages-[pageId]`、`P-courses-[courseId]`、`P-reading-materials`、`P-reading-[workspaceId]`、`P-reading-sessions`、`P-reading-sessions-[sessionId]`、`P-co-writer-[docId]` | 既有e2e覆盖部分功能；本次未逐页完成全部状态的视觉对照，保留待验收 |
| 待实现 | `P-papers`、`P-question-bank`、`P-templates`、`P-partners*`、`P-agents`、`P-mastery*`、`P-memory*`、`P-login`、`P-register`、`P-profile`、`P-admin-users` | 规划状态页不是最终业务视觉验收；正式页面实现时直接按学习问答基准建设 |
| 无独立页面 | `P-root`、`P-space-mcp`、`P-space-skills`、`P-mcp`、`P-skills` | 仅重定向；验收目标是去向、历史、焦点和最终页面当前菜单 |

每个页面升级视觉状态时必须提供 1440×900、1920×1080、390×844、键盘/焦点、长文/空态/错误和减少动画证据；业务功能状态保持独立。

H0 公共壳是横向证据：现有页面已共用 220/56px 侧栏、折叠偏好和选定响应式行为，但这不为任何页面内容区授予“部分验收”。隐藏直达页的当前菜单/抽屉焦点和部分错误场景的统一壳仍待修复。

额外错误场景 `/acceptance-404`：三视口均无公共壳，恢复入口仍回教案，判定未通过（R-02/R-06）；这是错误态证据，不增加53项分母。本次未做固定DeepTutor像素差分或全部主题/详情/弹窗覆盖。
