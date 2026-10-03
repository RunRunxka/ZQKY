# 路由与模块状态

更新：2026-10-03，按 `apps/web/src/app` 和 `apps/web/src/services/navigation.ts` 核对。本表只说明现有路由、导航和服务边界；当前任务、审查缺陷与验收限制见 [CURRENT_STATUS](CURRENT_STATUS.md)。全站保留学习问答的视觉基准，建设核心以 2026-09-29 起的教学闭环为准。

`ready` 表示已有业务实现，不能据此认定所有场景已验收或运行依赖已就绪；`local` 表示本地功能；`planned` 只有用途说明页。B3 完整名单/原卷/施测/成绩和题库审核链的验收状态以 CURRENT_STATUS 为准。

## 已建立业务路由

| 路径 | 页面与能力 | 导航状态 / 服务边界 |
| --- | --- | --- |
| `/` | 重定向到学习问答 `/chat` | 唯一默认首页 |
| `/chat` | 学习问答：真实三协议 SSE、教材定位与追问、主动触发详解、本地会话 | `ready`；模型与 RAG 依赖分别检查，未接入能力明确禁用 |
| `/chat/[sessionId]` | 真实会话深链；旧 `?mode=mock` 不启用模拟或访问模拟库 | `ready` |
| `/lesson-plans` | 既有本地规则/编辑/旧稿/Word与打印；B5增量后台教案与固定学情建议 | 本地保留，后台源码集成与独立验收状态见CURRENT_STATUS；lessonPlanId/revisionId精确读文档历史，analysisRunId仅初始化来源 |
| `/knowledge-bases` | 教材资料库：基础库 / 我的教材 / 历史登记；真实上传、解析、入库、索引任务与任教范围 | `ready`；历史登记不参与真实检索 |
| `/knowledge-bases/libraries/[libraryId]` | 逻辑库详情：书册列表、更新、分类编辑、删除、来源预览 | `ready`；真实修订与乐观锁 |
| `/knowledge-bases/[kbName]` | 历史本地登记详情 | 只读保留；不参与真实检索 |
| `/knowledge-points` | 独立知识点库：学科、父树、建立/更新、别名、归档、教材依据、表格导入校对确认、AI 候选 | `ready`；独立于教材资料库 |
| `/question-bank` | 独立题库：导入批次、正式题目筛选分页、知识点关联、AI 补题候选 | `ready`；正式存储与教师确认链，富内容受管资产；具体验收见 CURRENT_STATUS |
| `/question-bank/imports/[importId]` | 试题校对台：原文与草稿对照、未归属原文、拆分合并、AI 建议、确认入库 | `ready`；AI 产物先审核，`200 + failures` 仍是整批未确认 |
| `/assessments` | 五步工作区：名单 → 原卷 → 施测 → 成绩 → 历史；成绩导入、映射、校对、承认、确认、修正与只读矩阵 | `ready`；固定成绩历史可进入学情分析；`assessmentId` + `step=score/history` 定位实际施测 |
| `/learning-analysis` | 固定已确认成绩、显式人次选择、班级/学生事实、全题证据与追加备注、建立针对练习 | `ready` 表示源码已有实现；B4 独立验收与门禁状态见 CURRENT_STATUS；`assessmentId/scoreRevisionId/runId` 保持固定身份 |
| `/practices` | 正式固定题建议与缺口、结构/满分/KP复核、草稿保存与审核、新修订、两版 DOCX、成绩模板、转换施测 | `ready` 表示源码已有实现；`practiceSetId/practiceRevisionId/analysisRunId` 定位固定上下文；回流复用 F20/T60 |
| `/books` | 书籍列表、生成与内容入口 | `ready`；生成流水线为本地显式模拟；侧栏隐藏，归属教材资料库 |
| `/books/[bookId]` | 书籍工作区：提案、大纲、编译状态机 | `ready`；本地保存 |
| `/books/[bookId]/pages/[pageId]` | 页阅读器：block、翻页、书签、进度 | `ready`；本地保存 |
| `/courses` | 课程入口 | `ready`；侧栏隐藏，归属教材资料库 |
| `/courses/[courseId]` | 大纲、资料、约定与课程学习会话；会话按稳定 courseId 归属 | `ready`；资源登记引用不等于已送入模型或 RAG |
| `/settings` | 外观、模型与连接、MCP、Skills 与扩展目录 | `ready`；模型管理是真实服务，扩展目录不代表已接入执行 |
| `/mcp` | 兼容入口 | 重定向 `/settings#mcp` |
| `/skills` | 兼容入口 | 重定向 `/settings#skills` |
| 其他未知路径 | 404 | 保留公共壳，提供返回学习问答入口 |

## 规划介绍页

题库支持受限查询 `tab=imports|library|generation`，`generation`打开已入库题目内的补题面板，不自动调用模型。显式查询优先于旧`#library/#generation`；重复或无效查询显示地址错误。确认入库返回`?tab=library`，题库及校对页用编码的`returnPracticeSetId`保留练习返回上下文。手动标签同步查询，已挂载页面也响应新意图。

以下根路径由 `[planned]/page.tsx` 从导航登记表匹配，只展示用途和能力规划，没有可提交的假业务操作。

| 路径 | 模块 | 当前边界 |
| --- | --- | --- |
| `/papers` | 智能组卷 | 本地组卷、选题、排版和导出尚未实现；原卷导入校对在 `/assessments` |
| `/co-writer` | 协同写作 | 只有规划根页；原列表、编辑器和房间实现已移除 |
| `/reading` | 沉浸阅读 | 只有规划根页；原材料库、工作区和会话实现已移除 |
| `/space` | 学习空间 | 只有规划根页；原仪表盘及子模块实现已移除 |
| `/templates` | 模板中心 | 任意 DOCX 模板上传、映射与版本管理尚未实现；既有教案模板导出继续可用 |

`/notebooks` 及其详情、`/whisper`、`/agents`、`/space/chat-history`、`/space/questions`、`/space/personas`、`/space/cli-apps`、`/space/mcp`、`/space/skills`，以及旧 `/co-writer/[docId]`、`/reading/materials`、`/reading/[workspaceId]` 和阅读会话深链，当前均无对应业务路由，按未知路径显示 404。旧文档对这些页面的“已实现”判断仅作历史追溯，不能用于当前导航或验收。

## 导航与公共壳

导航清单的唯一运行时来源是 `apps/web/src/services/navigation.ts`，统一维护状态、图标、分组、隐藏入口和规划页内容。`/books`、`/courses` 是隐藏直达业务页，桌面侧栏沿 `parentPath` 高亮教材资料库。规划页只匹配清单内 `planned` 根路径，未登记地址不生成伪业务页面。

教学工作台主导航加入学情分析与针对练习；教学资源为教材资料库与模板中心，设置在底部。导航具体顺序以源码为准，本表不维护第二份运行时清单。

桌面侧栏展开 220px、收起 56px，折叠偏好跨页保留；学习记录位于侧栏可滚动区域。手机使用带遮罩、显式关闭、焦点限制与焦点返回的模态抽屉。规划项的可访问名称为“模块名（规划中）”。新增或改动路由必须同步本表与导航登记，按当前任务验收，不从历史 H1–H6 页面清单推导新任务。
