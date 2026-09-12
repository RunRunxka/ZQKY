# 路由与状态

更新：2026-09-12 源码核对。此表仅说明运行时路由/导航，不是完整复刻验收结论；条目功能与视觉状态在 [页面矩阵](replica/PAGE_MATRIX.md)，当前代码审查与计划在 [STATUS](STATUS.md)。全站视觉以当前学习问答为准。

## 已建立路由

| 路径 | 页面 | 状态 |
| --- | --- | --- |
| `/` | 重定向到学习问答（2026-09-06 起为默认首页） | 可用 |
| `/lesson-plans` | 教案工作台 | 本地功能可用（`local`） |
| `/chat` | 学习问答（仅普通真实对话；未接入能力明确禁用） | 已实现（`ready`） |
| `/chat/[sessionId]` | 真实会话深链；旧 `?mode=mock` 不启用模拟或访问模拟库 | 已实现（`ready`） |
| `/papers` | 智能组卷 | 规划状态页 |
| `/knowledge-bases` | 教材资料库（登记/检索引擎/来源；显式模拟解析与索引已有，真实服务未接） | 已实现（`ready`） |
| `/knowledge-bases/[kbName]` | 资料库详情（文档/登记/来源/模拟索引版本/设置；真实解析与向量检索未接） | 已实现（`ready`） |
| `/notebooks` | 笔记本（默认库"学习笔记"；与聊天"保存到笔记"同仓储；侧栏隐藏入口） | 已实现（`ready`） |
| `/notebooks/[notebookId]` | 笔记本深链选中 | 已实现（`ready`） |
| `/books` | 书籍（生成流水线为本地显式模拟；进度/导出本地保存） | 已实现（`ready`） |
| `/books/[bookId]` | 书籍工作区（提案→大纲→编译状态机，hub-and-spoke） | 已实现（`ready`） |
| `/books/[bookId]/pages/[pageId]` | 页阅读器（Block 渲染/翻页/书签/进度） | 已实现（`ready`） |
| `/courses` | 课程（主导航入口按参考隐藏，路由可达） | 已实现（`ready`） |
| `/courses/[courseId]` | 课程详情（大纲/资料/约定；学习会话未接入） | 已实现（`ready`） |
| `/space` | 学习空间 | 已实现（`ready`） |
| `/space/chat-history` | 真实会话历史（旧模拟库不读写、不删除） | 已实现（`ready`） |
| `/space/questions` | 题库 | 已实现（`ready`） |
| `/space/personas` | 角色目录 | 已实现（`ready`） |
| `/space/cli-apps` | CLI 应用（本地模拟安装） | 已实现（`ready`） |
| `/space/mcp`、`/space/skills` | 旧入口迁移 | 重定向 `/settings#mcp`、`/settings#skills` |
| `/question-bank` | 题库 | 规划状态页 |
| `/templates` | 模板中心 | 规划状态页 |
| `/co-writer`、`/co-writer/[docId]` | 文档列表/编辑器；自动保存/版本恢复，AI 为显式模拟 | 入口 ready，完整交付待验收 |
| `/whisper` | 双席位房间与结束状态；回复为显式模拟 | 路由已建立，完整交付待验收 |
| `/reading` | 沉浸阅读集合列表 | 入口 ready，完整交付待验收 |
| `/reading/materials` | 阅读材料库；多格式模拟解析与新建/分配/删除 | 入口 ready，完整交付待验收 |
| `/reading/[workspaceId]` | 三栏工作区与事件驱动伴生模拟 AI | 入口 ready，完整交付待验收 |
| `/reading/[workspaceId]/sessions(/[sessionId])` | 阅读会话深链；会话切换仍有 replaceState，历史/滚动见 STATUS H-R1 | 入口 ready，完整交付待验收 |
| `/agents` | Agent 任务 | 规划状态页 |
| `/mcp` | MCP | 重定向 `/settings#mcp`；本地模拟管理 |
| `/skills` | Skills | 重定向 `/settings#skills`；本地模拟管理 |
| `/settings` | 设置（模型管理可用；S6 整合工作空间/解析/记忆等 sections） | 已实现（`ready`） |
| 其他未知路径 | 404 | 提供返回教案入口 |

导航清单的唯一运行时来源是 `apps/web/src/services/navigation.ts`，同时登记模块状态（`planned / local / ready`）、图标、分组、`hidden`（如 /notebooks、/courses：路由可达但不出现在侧栏）和各规划页的用途简介与能力清单。规划状态页由受控动态路由匹配清单中 `status=planned` 的项，没有清单项的路径不会渲染伪业务页面；规划页统一使用 `components/layout/PlannedModulePage.tsx`，不含示例数据和可提交的假操作。

桌面全站采用学习问答侧栏：220px 展开/56px 折叠，完整标签与规划徽标，分组标题在桌面隐藏；根级 Context 持有折叠偏好，跨页沿用。手机（≤767px）使用带遮罩、关闭按钮、当前菜单焦点、Tab 限制与焦点返回的模态抽屉。规划中模块的可访问名称统一为"模块名（规划中）"。学习问答的学习记录为导航与聊天之间独立一列。

## 后续规划但尚未建立

`/partners`、`/mastery`、`/memory`、账号页面和相应详情页仍待建立（STATUS H3–H5）。添加功能时登记具体页面、参数和验收，不提前堆积空模块；自有规划页 `/papers`、`/question-bank`、`/templates` 的后续关系见 STATUS T2。
