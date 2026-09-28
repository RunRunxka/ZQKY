# courses 模块约定（课程）

先读根 `AGENTS.md`。入口 `/courses`（详情 `/courses/[courseId]`），为隐藏直达项（桌面侧栏高亮「教材资料库」）。
提供课程大纲、资源引用、颜色标记与**课程学习会话**（真实问答闭环）。

## 结构与职责

- `CoursesShelf.tsx`：课程书架（卡片、演示载入、归档区）。
- `CourseDetail.tsx`：详情（大纲勾选、资源附加/不可用态、学习会话区、归档只读）。
- `CourseSessions.tsx`：本课程会话列表与「新建学习会话」（保存成功后才跳转，同 tick 连点同步 ref 去重）。
- 仓储：`services/courses-store.ts`（大纲 covered 学员手判、资源引用、颜色）；
  会话归属：`services/course-session.ts`（`Conversation.courseId`，复用聊天 IndexedDB 库，不建第二套）。
- 样式：`courses.css`（规则以 `.courses-page`/`.courses-` 前缀收窄，不改写共享 `space-*` 类）。

## 关键不变量

- **资源三类**：`knowledge_base` / `notebook` / `book`。**笔记本已随学习空间移除**：不再作为候选来源；
  历史已附加的 `notebook` 资源保留并如实标注 `missing` 不可用，不回落、不猜目标。
- **资源三态（R-11）**：`available` / `missing` / `unknown`（目录读取失败时标 unknown，不把读失败当目标删除）；
  登记 ≠ 已解析 ≠ 已检索 ≠ 已随请求发送。
- **归属与删除**：`courseId` 缺失/空串 = 未归属，不按标题/最近访问/URL 猜测；课程删除/归档不级联删会话、
  不清空 `courseId`、不自动换绑；归档课程会话区只读。
- **课程上下文**：发送时把课程快照（名/约定≤1200 字符/大纲/资源登记清单）冻结为 `TurnCourseSnapshot`，
  经 `features/chat/model/request-budget.ts` 渲染为一条 system 消息；重试沿用原快照，课程修改只影响新轮。
  covered 为学员手判，不推断掌握度。

## 修改后必测

`typecheck`/`lint`/`test:unit`（courses-store 单测）；e2e 跑
`books-courses.spec.ts`、`course-sessions.spec.ts`、`course-resource-faults.spec.ts`。
