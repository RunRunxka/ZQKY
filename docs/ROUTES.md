# 路由与状态

更新：2026-09-08（S5-C 书籍/课程落地；同步 S5-A/S5-B 实现状态）。

## 已建立路由

| 路径 | 页面 | 状态 |
| --- | --- | --- |
| `/` | 重定向到学习问答（2026-09-06 起为默认首页） | 可用 |
| `/lesson-plans` | 教案工作台 | 本地功能可用（`local`） |
| `/chat` | 学习问答（真实/模拟双模式；RAG/附件等能力见聊天页内标注） | 已实现（`ready`） |
| `/chat/[sessionId]` | 会话深链（支持 `?mode=mock` 跨模式定位与 URL 同步） | 已实现（`ready`） |
| `/papers` | 智能组卷 | 规划状态页 |
| `/knowledge-bases` | 教材资料库（登记/检索引擎/来源；解析与索引未接入） | 已实现（`ready`） |
| `/knowledge-bases/[kbName]` | 资料库详情（文档/登记/来源/索引/设置） | 已实现（`ready`） |
| `/notebooks` | 笔记本（默认库"学习笔记"；与聊天"保存到笔记"同仓储；侧栏隐藏入口） | 已实现（`ready`） |
| `/notebooks/[notebookId]` | 笔记本深链选中 | 已实现（`ready`） |
| `/books` | 书籍（生成流水线为本地显式模拟；进度/导出本地保存） | 已实现（`ready`） |
| `/books/[bookId]` | 书籍工作区（提案→大纲→编译状态机，hub-and-spoke） | 已实现（`ready`） |
| `/books/[bookId]/pages/[pageId]` | 页阅读器（Block 渲染/翻页/书签/进度） | 已实现（`ready`） |
| `/courses` | 课程（主导航入口按参考隐藏，路由可达） | 已实现（`ready`） |
| `/courses/[courseId]` | 课程详情（大纲/资料/约定；学习会话未接入） | 已实现（`ready`） |
| `/space` | 学习空间 | 已实现（`ready`） |
| `/space/chat-history` | 会话历史（双仓储） | 已实现（`ready`） |
| `/space/questions` | 题库 | 已实现（`ready`） |
| `/space/personas` | 角色目录 | 已实现（`ready`） |
| `/space/cli-apps` | CLI 应用（本地模拟安装） | 已实现（`ready`） |
| `/space/mcp`、`/space/skills` | 旧入口迁移 | 重定向 `/settings#mcp`、`/settings#skills` |
| `/question-bank` | 题库 | 规划状态页 |
| `/templates` | 模板中心 | 规划状态页 |
| `/co-writer` | 协同写作 | 规划状态页 |
| `/reading` | 沉浸阅读（集合列表；材料解析仅文本形态，显式标注） | 已实现（`ready`） |
| `/reading/materials` | 阅读材料库（新建/分配/删除） | 已实现（`ready`） |
| `/reading/[workspaceId]` | 三栏工作区（导航/阅读器/伴生模拟 AI） | 已实现（`ready`） |
| `/reading/[workspaceId]/sessions(/[sessionId])` | 阅读会话深链（会话切换用 replaceState 写 URL） | 已实现（`ready`） |
| `/agents` | Agent 任务 | 规划状态页 |
| `/mcp` | MCP | 重定向 `/settings#mcp`；本地模拟管理 |
| `/skills` | Skills | 重定向 `/settings#skills`；本地模拟管理 |
| `/settings` | 设置（模型管理可用；S6 整合工作空间/解析/记忆等 sections） | 已实现（`ready`） |
| 其他未知路径 | 404 | 提供返回教案入口 |

导航清单的唯一运行时来源是 `apps/web/src/services/navigation.ts`，同时登记模块状态（`planned / local / ready`）、图标、分组、`hidden`（如 /notebooks、/courses：路由可达但不出现在侧栏）和各规划页的用途简介与能力清单。规划状态页由受控动态路由匹配清单中 `status=planned` 的项，没有清单项的路径不会渲染伪业务页面；规划页统一使用 `components/layout/PlannedModulePage.tsx`，不含示例数据和可提交的假操作。

桌面与平板使用左侧图标导航（可展开显示分组标题与文字徽标，条目过多时内部滚动）；手机（≤767px）通过页头菜单按钮打开功能导航抽屉，入口、分组与规划标记与桌面一致。规划中模块的可访问名称统一为"模块名（规划中）"，展开、收起与手机导航一致。

## 后续规划但尚未建立

原项目规划中的 `/partners`、`/mastery`、`/memory`、`/whisper`、账号页面和其余详情页仍在后续任务范围（S5-E→I）。添加真实功能时再建立具体页面、参数和验收，不提前堆积空模块。
