# 路由与模块状态

更新：2026-10-20（全局移除归档功能；知识点整树删除、题库彻底删除后核对）。按 `apps/web/src/app` 与 `apps/web/src/services/navigation.ts` 核对。

| 路径 | 页面与能力 | 状态 |
| --- | --- | --- |
| `/` | 重定向到 `/chat` | 唯一默认首页 |
| `/chat` | 学习问答：会话管理、流式消息、附件上传、上下文容量环、思考强度（受支持档位）、Agent 中断确认卡、产物面板 | `ready` |
| `/lesson-plans` | 教案工作台：三栏（模块/排版 · 编辑 · 第 3 页起 A4 预览）、流式生成、导出 docx（自动补封面目录）；**本地教案**（本机后端保存，列表可新建/打开/**彻底删除**，无归档入口；新建需选教案归属：学科 + 班级） | `ready` |
| `/textbooks`、`/textbooks/libraries/[libraryId]` | 教材资料库：**新建逻辑库**（基础库/我的教材）/ **索引与嵌入**（建档案 + 起始索引代 + 受控重建）/ 导入（第 4 步加入逻辑库）/ 清洗 / 入库任务 / 库与书册详情 | `ready` |
| `/knowledge-points` | 知识点：搜索 + 可展开树 + 详情编辑（含学习目标）、AI 候选/教材提取/导入审阅；**删除整棵子树**（有引用时逐节点列出计数），**无归档入口**（2026-10-20 裁定） | `ready` |
| `/question-bank`、`/question-bank/imports/[importId]` | 题库：筛选（知识点/难度/搜索）+ 分类树 + 列表分页；批量导入（含课后习题提取）与校对；**删除=物理删除**（有练习/教案引用时 409 列出计数），无归档语义 | `ready` |
| `/practices` | 练习：学情/描述出题 → 微调 → 确认门槛 → 学生卷/教师卷导出预览 | `ready` |
| `/learning-analysis` | 学情分析：筛选、**「新建施测」**（已确认原卷 + 班级 → 施测）/ **「生成学情报告」**（已确认成绩修订 → 报告）（两入口 2026-10-13 补齐）、小题分导入、五图、AI 评价、报告导出；**「删除该施测」**（R10-BE 级联成绩链，二次确认 + 回执列级联计数） | `ready` |
| `/assessments`（重定向到 roster）、`/assessments/roster` | 班级管理：班级/学生名单（xlsx 导入、性别、分页）；删除学生双模式（无成绩=彻底删除 / 有成绩=移除并保留历史），班级人数即时下降；**无归档入口**（2026-10-13 裁定） | `ready` |
| `/assessments/papers` | 试卷管理：导入（DOCX/PDF 文本层）→ 拆题校对 → AI 知识点分类占比环图；删除即删除（无归档入口） | `ready` |
| `/settings` | 设置：外观 / 模型与连接 / 关于 | `ready` |
| 其他未知路径 | 404 | 保留公共壳，提供返回对话入口 |

**已删除**（历史实现见 git tag `archive-full-v1-20261011`）：`/knowledge-bases*`、`/books*`、
`/courses*`、`/mcp`、`/skills`、规划页捕获路由。

**壳与导航约定**：导航清单唯一来源 = `apps/web/src/services/navigation.ts`；业务根在
`components/layout/ModuleWorkspaceShell.tsx` 的 `independentRoots` 登记后由壳统一提供侧栏与
滚动容器（页面裸渲染、不自包 WorkspaceShell）。桌面侧栏展开 220px、收起 56px；手机为模态抽屉。
新增路由必须同步本表、导航登记与 `independentRoots`。
