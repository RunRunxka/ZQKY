# UX-PERF-CLOSEOUT v1 任务卡

批次 ID：**UX-PERF-CLOSEOUT v1**
版本：v1（2026-09-23 冻结）
负责人：本会话实施总控
角色：总控（共享契约、权威文档、构建目录、最终 Git）+ 限范围实现者（教案布局）+ 独立验收者（只读复验）

关联用户指令：2026-09-23 八节批次（P0 长推理流性能 / 学习问答模式菜单 / 学习记录与导航与图标 / 教案工作台布局 / 全站双语字体 / 文档整理 / 组织与交付门槛）。

## 起点

- 现场核对：`main@3dcace8`，工作区干净，`main` 相对 `origin/main` ahead 8（本机既有，未被本批改写）。
- 端口现场：5173（用户 dev）、8000（用户真实后端）已占用 → 本批一律不触碰，自动化使用 **5174 / 5199 / 8002**。
- 构建目录：`.next` 归总控（正式候选与 e2e）；`.next-test` 归总控（性能取证专用构建）。同一时段单一写入者。

## 非目标

- 不修改、冻结、复制、打包、启动、评测 `F:\ZQKY_RAG`；不把 RAG 说成已接入。
- 不推送、不部署、不并分支、不改全局 Git 身份、不使用 `git stash`、不批量暂存。
- 不处理 R-13 模型真实长答、不新建第二套业务后端、不改后端产品协议（除必要的行为无关修复）。
- 不做全站主题改版；不改已验收的业务布局与数据流。

## 子任务与文件归属

| 子任务 | 内容 | 可写文件 | 负责人 |
| --- | --- | --- | --- |
| T1 性能取证 | 受控上游 + 探针 + 基线/优化后数据 | `_work/perf-20260923/**` | 总控 |
| T2 流式优化 | 增量合并与 UI 提交节流、按需渲染、避免全量重渲染与同步布局读写 | `features/chat/model/store.ts`、`features/chat/ReasoningDisclosure.tsx`、`features/chat/Message.tsx`、`features/chat/ChatWorkspace.tsx`、`features/chat/styles/chat-home.css`、`.test.tsx` | 总控 |
| T3 模式菜单 | 修横向滚动；RAG 模式替代「更多能力」；清理专属死代码 | `features/chat/CapabilityMenu.tsx`、`features/chat/CapabilityConfigCard.tsx`、`services/capability-catalog.ts`、`features/chat/styles/chat.css`、`features/chat/model/capability-demo.ts`、相关测试 | 总控 |
| T4 学习记录入导航 | 删除独立 236px 中栏，并入全站导航；手机走导航抽屉；书籍并入教材资料库；favicon | `features/chat/ChatWorkspace.tsx`、`features/chat/SessionPanel.tsx`、`components/layout/WorkspaceShell.tsx`、`services/navigation.ts`、`components/layout/workspace-shell.css`、`features/chat/styles/chat-home.css`、`features/chat/styles/chat.css`、`app/icon.svg`、`app/layout.tsx` | 总控 |
| T5 教案布局 | 去面包屑、编辑区→教案配置→预览、单一折叠按钮 | `features/lesson-plan/**`、`tests/e2e/lesson-plan.spec.ts` | 限范围实现者 |
| T6 字体排版 | 字体 token、导航与聊天衬线、清理硬编码、fallback 验证 | `styles/globals.css`、`components/layout/workspace-shell.css`、`features/chat/styles/*.css`、各模块 CSS 字体行 | 总控 |
| T7 文档 | STATUS / PROJECT_GUIDE / 矩阵 / NEXT_SESSION_START / README | `docs/**`、`README.md` | 总控 |
| T8 验收与提交 | 全量测试、独立验收、小粒度提交 | 构建目录、Git | 总控 |

## 依赖

- T2/T3/T4 均修改 `ChatWorkspace.tsx` → **串行**：T2 → T3 → T4。
- T5 与 T2/T3/T4 无文件交集 → 可并行。
- T6 与 T2/T4 共用 `chat-home.css` / `chat.css` → 在 T4 之后串行。
- T8 依赖 T1–T7 的稳定候选。

## 行为闭环与验收条件

### T1（已完成部分：见 FROZEN/PERF 报告）
- 正常路径：受控上游按固定分块/间隔产生确定性推理文本；探针记录长任务、帧间隔、输入延迟、堆、首个可见增量、DOM 更新次数。
- 错误：上游断流、代理失败时探针必须失败可见，不得静默产出空数据。
- 数据兼容：探针使用隔离浏览器上下文与独立 IndexedDB，不读用户 5173 草稿。

### T2
- 正常路径：推理增量仍逐条进入 store，最终文本与上游逐字节一致（不丢 delta、不截断）；严格事件顺序保持。
- 空态/错误：停止、错误、断连、切会话、刷新前保存语义不变（含最终推理文本落库）。
- 取消/重试/恢复：停止后不再有 UI 更新；重试沿用原快照。
- 动画/减少动画：推理折叠行为、ThinkingOrb、减少动画压制不变。
- 性能：优化后相对基线在 20k/50k 场景有可侧量的改善（长任务总量、帧 p95、DOM 更新次数），且 **没有任何场景变差到超出噪声**。
- 未测硬件/真实供应商必须标 not_run。

### T3
- 模式菜单无横向滚动（`scrollWidth == clientWidth`，桌面/窄桌面/手机实测），无左右滑动，不裁切内容与焦点环。
- 「更多能力」入口、飞出层、专属状态/表单/样式/测试彻底移除；全局审计列可达性清单。
- 「RAG 模式」与「对话/追问澄清/智能出题/可视化」同级一行，同一菜单样式与选中语义；未接入状态清晰可见，不发送到普通聊天冒充 RAG。
- 历史会话旧能力值保持可读并明确降级展示。

### T4
- 学习记录并入左侧导航（可滚动区域），底部导航仍可见；无 236px 空列。
- 折叠/打开独立学习记录列的按钮与状态删除，仅保留全站导航折叠按钮。
- 手机学习记录在全站导航抽屉内，无第二套弹窗；焦点打开/关闭/ Escape / Tab 圈定正确。
- 新建、搜索、切换、重命名、删除、归档、深链、课程会话往返、本地保存行为不变。
- /books、/books/[...]、/courses 路由与数据不变，唯一正确高亮「教材资料库」。
- favicon：`/icon.svg` 返回 200 且为 SVG；标签页显示品牌图标；metadata 有 icons。

### T5
- 教案工作台无「备课空间 > 教案工作台」面包屑，改为同级直接标题（字体/字号/行高/对齐一致）。
- 顺序：编辑区 → 可折叠「教案配置」→ 教案预览；grid 与响应式与阅读顺序同步调整。
- 教案配置只有一个折叠按钮（EditorPanel 顶部），aria-label/aria-expanded 与状态一致；OutlinePanel 顶部按钮删除。
- 折叠/展开保留动画与内容状态（编辑位置、表单值、预览内容、撤销历史、焦点不丢）。
- 动画中连续点击、减少动画、手机布局、打印/导出回归。

### T6
- 有名称与用途的字体 token；标题 Chat Lora + 中文衬线 fallback；正文非衬线黑体 + 拉丁/中文/缺字 fallback。
- 左侧导航全部可见文字与控件衬线；聊天普通文字/消息/输入/模式菜单/学习记录/按钮/提示衬线；KaTeX/代码/图标局部例外。
- 其余页面正文统一黑体；同级标题/卡片/标签/按钮字号字重行高间距一致。
- 阻断自托管字体后 fallback 字形、换行、溢出、按钮可读性；1440/1920/390 三视口 + 长标题 + 学习记录 + 模式菜单 + 教案三栏实测截图。
- 不允许用 CSS 文本断言代替视觉证据。

## 必须运行

`npm run typecheck`、`npm run lint`（0 警告）、`npm run test:unit`、`npm run build`、后端相关 `npm run test:api`、定向 e2e、全量 e2e、性能套件前后各一轮、三视口视觉取证。

## 结果格式

按 `MULTI_AGENT_COLLABORATION_PROPOSAL.md` 的结果卡；本批汇总写入 `docs/qa/UX-PERF-CLOSEOUT-20260923/README.md`，逐项证据 JSON/截图同目录。

## 超出范围时

交回总控重新分配；不得自行扩大可写文件、不得代改共享契约、不得在验收期修复。
