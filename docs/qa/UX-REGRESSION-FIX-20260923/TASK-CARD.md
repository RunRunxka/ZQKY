# UX-REGRESSION-FIX v1 任务卡

批次 ID：**UX-REGRESSION-FIX v1**
版本：v1（2026-09-23 冻结）
负责人：本会话实施总控（共享契约、权威文档、构建目录、最终 Git）
独立验收：只读复验者（A1）

## 起点

`main@3a2e4a8`，工作区干净；端口 5173/5174/8000/8002 均空闲（本批自建服务用 5199/5174/8000+8002 之外的隔离端口）。

## 授权范围（用户 2026-09-23 指令，只修三项回归）

1. **学习问答 LaTeX 公式**：流式过程中已闭合的公式必须立即渲染；未闭合尾段可暂以原文显示，补齐后转公式；保持上一批的长推理性能改善（不得对每个 delta 的完整增长文本重跑解析）；原始消息/复制/导出保留供应商原文；公式字体不得被正文衬线覆盖。
2. **教案工作台顶栏**：标题「教案工作台」进入现有 `app-header`，与「导出教案」同一行；移除教案专属的额外标题 DOM、网格行与失效 CSS；其他页面标题/面包屑不变；保留单一折叠按钮、过渡动画、草稿/撤销/预览/打印/导出。
3. **教材资料库返回路径**：`/books`、`/courses` 列表页各加固定指向 `/knowledge-bases` 的可访问返回链接；保留详情页既有「返回书籍列表」「返回课程列表」；两条完整往返路径可用；全程左侧导航「教材资料库」唯一当前项。

## 非目标

RAG、模型供应商、书籍生成、全站主题、其他页面视觉；不推送、不部署、不改 `F:\DeepTutor` 与 `F:\ZQKY_RAG`。

## 文件归属（互不重叠）

| 子任务 | 可写文件 | 负责人 |
| --- | --- | --- |
| 公式 | `features/chat/model/markdown-segments.ts`（新建）、`features/chat/StreamingMarkdown.tsx`（新建）、`features/chat/ReasoningDisclosure.tsx`、`features/chat/Message.tsx` 及其单测 | 总控 |
| 教案顶栏 | `features/lesson-plan/LessonPlanWorkspace.tsx`、`features/lesson-plan/styles/lesson-plan.css`、`styles/print.css` | 总控 |
| 返回路径 | `features/books/BooksRoute.tsx`、`features/courses/CoursesShelf.tsx` | 总控 |
| 测试资源 | `tests/integration/chat-reasoning.spec.ts`、`tests/fixtures/stream_backend.py`、`tests/e2e/lesson-plan.spec.ts`、`tests/e2e/books-courses.spec.ts` | 总控 |
| 文档 | `docs/STATUS.md`、三矩阵、`docs/qa/UX-REGRESSION-FIX-20260923/**` | 总控 |

运行资源：`.next`（e2e/构建指纹）、`.next-test`（受控上游 origin 8002 用于性能与复现；origin 8001 用于 `test:chat` 流式集成）、端口 5199/5174/8002/8001。

## 验收条件

- 公式：流式期间 `.katex` 可见且 `.katex-error` 为 0；未闭合尾段按原文显示、补齐后转公式；完成/停止/错误/展开折叠/刷新恢复均正确；落库原文逐字节不变；50k 长推理主线程与帧间隔不因本修复回到修复前水平。
- 教案：四视口（1920/1440/1024/390）标题与导出同一顶栏行、无重叠、无横向溢出、内容区紧接顶栏（无多出的一行）。
- 返回路径：两条完整路径真实点击可达；空列表/深链/手机视口均有返回入口；唯一当前项。
- 测试：typecheck、lint(0 警告)、unit、build、定向 e2e、`test:chat` 集成；如跑全量 e2e 记录真实通过/失败数并单独定性既有失败。

## 超出范围时

交回总控；不自行扩大文件或顺手重构。
