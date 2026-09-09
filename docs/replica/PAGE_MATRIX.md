# DeepTutor v1.6.5 页面复刻矩阵（S1 框架完成 · 规格部分完成）

2026-09-09 更新：R26–R31 已修复并回归通过（见 review 修复记录），阅读 5 条保持实现待修复直至 R32 差距补齐；2026-09-08 独立审查将阅读 5 条标记实现待修复（R26–R32），书籍/课程详情因未补齐范围标记部分实现。R19–R25 已有后续修复记录，旧待修表述不再作为当前状态。最新依据见 [阅读审查](../reviews/READING_REVIEW_2026-09-08.md) 和 [当前进度](../STATUS.md)。

基线提交：42fab3cf429a1fbf36b257ab8d116a3814964202（固定版本源码核对）。状态词汇：`待实现` / `部分实现` / `实现待验收` / `已验收` / `实现待修复` / `真实服务未接入`。条目 id 稳定规则：`P-<路由段>`，动态段用 `[x]` 占位。

**S1 状态（R18 修正）**：矩阵框架完成；规格部分完成——各批实施前须先补该批条目的组件来源、弹窗/抽屉、状态机、出入路径、持久化与动画来源，再实现验收。分类：**参考产品页 50**、目标自有页 1（教案）、目标兼容别名 2（/mcp、/skills，目标侧仅重定向，不计页面完成量）；内部调试 1 不计分母。**非调试条目 53**：统计见下表末尾，由实际行生成；旧历史计数不作为当前完成度。

| id | 参考路由 | 目标路由 | 状态 | 范围摘要与证据 |
| --- | --- | --- | --- | --- |
| P-root | `/` | `/` | 已验收 | 默认跳转 /chat（用户指定）；e2e `lesson-plan.spec.ts` 首页断言 |
| P-chat | `/chat` | `/chat` | 部分实现 | 核心闭环（真实/模拟、停止/重试/隔离/刷新恢复、扩展、工具面板、追问）+S2 完整输入区（能力目录/配置门控/附件/引用/语音/650ms 过渡）已实现并有 e2e；S7 视觉逐项验收待做 |
| P-chat-[sessionId] | `/chat/[sessionId]` | `/chat/[sessionId]` | 实现待验收 | 深链定位+无效 id 提示+R17 不回跳+URL 同步（选择/新建/删除/模式切换写地址、popstate 重定位）；e2e `chat-deeplink.spec.ts` 7 项 |
| P-settings | `/settings` | `/settings` | 部分实现 | 分类导航/锚点/搜索、模型真实管理、扩展模拟管理已有；S6 完整整合（工作空间/网络/解析/记忆/任务模型/TTS/STT/图像等 sections）待实现 |
| P-lesson-plans | —（目标自有） | `/lesson-plans` | 已验收 | 目标项目既有教案工作台，保留独立地址与导航入口；首页现为 /chat；e2e `lesson-plan.spec.ts` 回归 |
| P-space | `/space` | `/space` | 实现待验收 | 学习空间仪表盘（S5-A）：3 组磁贴+实时计数（会话/题库/笔记/角色/CLI/技能/MCP）；whisper 磁贴按参考行为隐藏（树外插件能力本地不存在）；e2e `space-pages.spec.ts` |
| P-space-chat-history | `/space/chat-history` | `/space/chat-history` | 实现待验收 | 会话历史目录（S5-A）：双仓储（真实+模拟）搜索/模式/归档筛选、内联重命名、删除确认、归档恢复、重开（mock 会话深链带 `?mode=mock`）；e2e 同上 |
| P-space-questions | `/space/questions` | `/space/questions` | 实现待验收 | 题库（S5-A）：范围栏（全部/答错/未掌握/书签/未分类/分类）+计数、250ms 防抖搜索、排序、书签/已掌握/归类/删除、批量操作、分类管理、演示题目显式载入；数据与聊天"保存到题库"同仓储 |
| P-space-personas | `/space/personas` | `/space/personas` | 实现待验收 | 角色目录（S5-A）：卡片网格、查看/新建/编辑/删除（弹层+重名校验）、演示角色显式载入；与聊天输入区"人设"共用 persona-catalog |
| P-space-cli-apps | `/space/cli-apps` | `/space/cli-apps` | 实现待验收 | CLI 应用（S5-A）：已安装/目录双页签、本地登记安装（显式"模拟安装"标识）、启停/卸载、信任徽标；本地演示无执行能力 |
| P-space-mcp | `/space/mcp` | `/space/mcp`（跳设置#mcp） | 实现待验收 | 旧入口迁移跳转（S5-A）；参考为独立管理页，按既定决策重定向设置（有意差异）；e2e 断言锚点 |
| P-space-skills | `/space/skills` | `/space/skills`（跳设置#skills） | 实现待验收 | 同上（S5-A） |
| P-mcp | `/mcp` | `/mcp`（跳设置#mcp） | 已验收 | e2e `replica-settings.spec.ts` 覆盖重定向 |
| P-skills | `/skills` | `/skills`（跳设置#skills） | 已验收 | 同上 |
| P-knowledge-bases | `/knowledge-bases` | `/knowledge-bases` | 实现待验收 | 教材资料库列表（S5-B）：知识库/检索引擎双页签、演示载入幂等、新建重名拒绝、登记仅元信息（显式标注）；e2e `knowledge-notebooks.spec.ts` |
| P-knowledge-bases-[kbName] | `/knowledge-bases/[kbName]` | 同 | 实现待验收 | 库详情（S5-B）：文档/登记/来源/索引（显式空态）/设置分区；改名同步 URL、设默认库、删除确认；e2e 同上 |
| P-notebooks | `/notebooks` | `/notebooks` | 实现待验收 | 笔记本列表（S5-B）：默认笔记本虚拟项、记录展开/编辑/移动复制/导出/删除；e2e 同上 |
| P-notebooks-[notebookId] | `/notebooks/[notebookId]` | 同 | 实现待验收 | 笔记本详情（S5-B）：深链选中、无效 id 报错、搜索；S5-D 起"发到笔记本"写入此目录；e2e 同上 |
| P-books | `/books` | `/books` | 部分实现 | 书籍目录（S5-C）：统计条/演示载入（幂等）/新建（模拟提案）/状态徽标（草稿·大纲待确认·可阅读·归档）/阅读进度条/删除确认；生成流水线显式模拟标注；e2e `books-courses.spec.ts`  完整 block/阶段/作答保存/课程会话依对应页面补齐。 |
| P-books-[bookId] | `/books/[bookId]` | `/books/[bookId]` | 部分实现 | 书籍工作区（S5-C）：hub-and-spoke 单组件按状态机分流（draft=提案确认→spine_ready=大纲确认→ready=阅读器）；无效 id 报错；就绪书自动续读定位；重建（二次确认，清进度）；导出 Markdown（真实下载）；e2e 同上  完整 block/阶段/作答保存/课程会话依对应页面补齐。 |
| P-books-pages-[pageId] | `/books/[bookId]/pages/[pageId]` | 同 | 部分实现 | 页阅读器（S5-C）：Block 分发渲染（text/section/callout/quiz 子集，对照参考 14 种的尚未补齐，非批准缩减）、上一页/下一页+←/→ 键盘翻页、书签切换与侧栏标记、打开即登记已读（进度持久化）、无效页码显式报错；e2e 同上  完整 block/阶段/作答保存/课程会话依对应页面补齐。 |
| P-courses | `/courses` | `/courses` | 实现待验收 | 课程目录（S5-C）：进行中/已归档折叠区、演示载入（幂等）、新建（颜色标记）；主导航入口按参考隐藏（hidden ready，路由可达）；e2e 同上 |
| P-courses-[courseId] | `/courses/[courseId]` | `/courses/[courseId]` | 部分实现 | 已有大纲逐行编辑、覆盖标记、下一单元提示、资料附加/移除、失效资源提示、约定与归档恢复；课程学习会话及聊天 course_id 关联尚未实现，须补齐并验收。e2e `books-courses.spec.ts` 仅覆盖已有切片。 |
| P-reading | `/reading` | `/reading` | 实现待验收 | 沉浸阅读入口（S5-D）：集合卡片（材料/会话计数）、演示载入（R26 待修）、新建/删除确认；材料解析仅文本形态（显式标注）；e2e `reading.spec.ts`（含 R28–R31 正式回归）  R26–R31 已修复、R32 已补齐（2026-09-09）；实现待验收（媒体播放器原视图为显式模拟边界，S7 三视口/动画待验收）。 |
| P-reading-materials | `/reading/materials` | `/reading/materials` | 实现待验收 | 材料库（S5-D）：全部/未分配页签、新建文本材料（# 行按标题渲染）、分配到集合、删除级联清理；e2e 同上  R26–R31 已修复、R32 已补齐（2026-09-09）；实现待验收（媒体播放器原视图为显式模拟边界，S7 三视口/动画待验收）。 |
| P-reading-[workspaceId] | `/reading/[workspaceId]` | `/reading/[workspaceId]` | 实现待验收 | 三栏工作区（S5-D）：材料 Tab 条、大纲/书签/批注导航（locator=h-<行索引>）、文本阅读器（标题层级+quote 批注高亮+滚动进度保存/恢复+选区浮条 高亮五色/笔记/书签/问 AI）、伴生模拟 AI（显式【模拟回复】+replaceState 会话 URL）；e2e 同上  R26–R31 已修复、R32 已补齐（2026-09-09）；实现待验收（媒体播放器原视图为显式模拟边界，S7 三视口/动画待验收）。 |
| P-reading-sessions | `/reading/[workspaceId]/sessions` | `/reading/[workspaceId]/sessions` | 实现待验收 | 会话深链（S5-D）：与工作区同组件，无 sessionId 时取最近/首个会话；e2e 同上  R26–R31 已修复、R32 已补齐（2026-09-09）；实现待验收（媒体播放器原视图为显式模拟边界，S7 三视口/动画待验收）。 |
| P-reading-sessions-[sessionId] | `/reading/[workspaceId]/sessions/[sessionId]` | 同 | 实现待验收 | 会话恢复深链（S5-D）：routeSessionId 定位会话，无效提示并回退最近会话；e2e 同上  R26–R31 已修复、R32 已补齐（2026-09-09）；实现待验收（媒体播放器原视图为显式模拟边界，S7 三视口/动画待验收）。 |
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

必需完成分母：除 P-avatar-preview 外共 53 项（参考产品页 50 + 自有教案 1 + 额外兼容别名 2）。2026-09-09（R26–R32 后）实际行标签：**已验收 4 / 实现待验收 18 / 部分实现 6 / 待实现 25**；此前 2026-09-08 审查后为 已验收 4 / 实现待验收 13 / 部分实现 6 / 实现待修复 5 / 待实现 25。

标签不是完整产品验收百分比：路由 ready、自动用例通过、视觉/动画验收与真实后端验证分开记录。改变状态或条目时重算本段，禁止保留第二份旧统计。
