# B-R05-EXTEND v4 任务卡（队长定稿）

定稿时间：2026-09-19 ｜ 队长：外部 Agent（实施总控）｜ 起点 SHA：`b0b24fa`（分支 `codex/replica-review-20260908`）
参考：`F:\DeepTutor` 固定 `42fab3cf429a1fbf36b257ab8d116a3814964202`（只读，不升级）

## 1. 批次范围（用户已锁定，不得扩大）

R-05 视觉规范推广第四批，**全站最后两个既有模块页**：

| 页面条目 | 路由 | 组件 |
| --- | --- | --- |
| P-settings | `/settings` | `features/settings/SettingsWorkspace.tsx` + `ExtensionManager.tsx`；模型区由 `features/model-settings/*` 提供 |
| P-lesson-plans | `/lesson-plans` | `features/lesson-plan/LessonPlanWorkspace.tsx` 及其 `components/*` |

**不在本批**：`P-reading-[workspaceId]` 及 sessions 子页（阅读工作区三栏）、`/space` 其余子页、`P-whisper`、`P-books-pages-[pageId]`、其他模块。做完本批后 R-05 仅剩「阅读工作区三栏 + `/space` 其余子页」（可规划 v5 收尾）。

**只做视觉与既有状态呈现推广，不补新业务。**

## 2. 两条硬边界（本批最高风险）

### 2.1 设置页模型区 = contract-v1 禁区

模型管理区（`features/model-settings/*`）承载 contract-v1 的 38 条注册、6 backend、专用适配、受管认证、发现来源、推理控制。本批：

- **不得改动**：任何模型契约与类型、连接/模型 ID 语义、`providerId`/`apiFormat` 分派、认证流程（OAuth/本机免 Key/受管键）、发现来源语义（upstream/catalog/manual）、推理三态与 effort 派生、v1→v2 迁移、后端调用路径、`services/model-settings-api.ts` 与 `apps/api` 的任何内容。
- **允许**：`features/model-settings/styles/model-settings.css` 与 `model-detail.css` 的**纯视觉增量**（颜色/间距/圆角/阴影/过渡/焦点环），以及组件内 className 的组合调整——**前提是不改变可访问名称、role、文案与交互顺序**。
- **模型区的 DOM 结构（卡片/详情/列表/表单层级）本批原则上不动**：`model-settings.spec.ts` 与 `model-settings-nesting.spec.ts` 用可访问名称定位，结构重排风险高。若 E4 发现某项「必须改结构才算完成视觉」，**列入保留现状交队长裁定**，不擅自实施。
- 凭证相关一律用测试替身或空值；**不写正式 `.env`**、不触碰 `.local-data`。

### 2.2 教案页 = 导出与草稿链路禁区

教案是目标自有页面、无 DeepTutor 参考对照（参考对象是 `/chat` 视觉基准 + 既有教案业务）。本批：

- **不得改动**：`services/pagination.ts`（分页预算）、`DraftRepository` 与 600ms 防抖/串行写入/flush 语义、`DraftEnvelope.schemaVersion=1` 与本地键 `zhiqikeyuan:lesson-plan:v1`、`FillProvider` 的规则填充与警告合并语义、Word 导出映射（`assets/templates/source/teacher-standard.docx` 派生模板）、PDF 打印页面命名 `lesson-plan` 与标准 A4、`print.css` 的分页规则。
- **允许**：`styles/lesson-plan.css` 的屏幕样式增量（不触碰 `@media print` 规则与 `print.css`）、组件 className 组合调整。
- **密集编辑区不强制 Lora**（PROJECT_GUIDE §2 明示）：`--serif` 回退链保持原样，不套 `--font-display`。
- 导出验证若需产物，写隔离目录并在报告中说明；**不修改原 Word 模板**。

## 3. 共享层定稿（队长自留，实现者只引用）

1. **`apps/web/src/styles/globals.css`、`motion.css`、`features/space/styles/space.css`：本批只读**。
2. **`features/settings/settings.css`（188 行，仅 `SettingsWorkspace.tsx` 引用）：本批由 I1 独占（可写）**——保持既有选择器语义，新增规则以 `.settings-*` 或 `.settings-workspace` 后代作用域；顶部注释「消费 globals.css 单一变量层（R-05）」。
3. **`features/model-settings/styles/model-settings.css`（475 行）与 `model-detail.css`（453 行）**：注意 `model-settings.css` **还被 `features/chat/ChatWorkspace.tsx` import**（聊天模型弹层共用）——本批 I1 **只允许追加** `.settings-workspace` 后代作用域的视觉增量，**不得修改既有选择器**（改既有规则会波及聊天页）。
4. **`features/lesson-plan/styles/lesson-plan.css`（1651 行）：本批由 I2 独占（可写）**——只增屏幕样式；**不得修改 `@media print` 块与 `print.css`**。
5. 新增（若 I 卡判断必要）：
   - `features/settings/styles/settings-extend.css`（`.settings-*` 前缀）
   - `features/lesson-plan/styles/lesson-visual.css`（`.lesson-*` 前缀）
   两文件顶部注明「消费 globals.css 单一变量层（R-05）」，只引用既有变量，**零 `!important`**。
6. 页面根节点加**修饰类**用于收窄覆盖：设置 `settings-workspace settings-page`；教案在 `WorkspaceShell` 的 `className` 追加 `lesson-page`（保留 `lesson-workspace` 及既有状态类）。
7. **CSS 注释内不得出现 `*/` 序列**（`--radius-*/` 会提前闭合注释导致 Turbopack 构建失败，前批已踩两次）。
8. **新增控件可访问名称不得与既有控件同名**（前批先例：空态按钮 vs 页头按钮触发 Playwright strict-mode 冲突；重复 `role="alert"` 同理）。

## 4. 分卡与独占文件表

| 卡 | 负责人角色 | 独占可写文件 | 禁止修改 |
| --- | --- | --- | --- |
| B-R05-EXT4-E4 | Evidence-Collector（只读） | `docs/qa/B-R05-EXT4/E4-GAP-LIST.md` | 其余全部 |
| B-R05-EXT4-I1 | Limit-scope-implementer（设置） | `features/settings/SettingsWorkspace.tsx`、`features/settings/ExtensionManager.tsx`、`features/settings/settings.css`、**新建**（如需）`features/settings/styles/settings-extend.css` | `model-settings/**` 逻辑与既有 CSS 选择器、`services/**`、`space.css`、`globals.css`、`motion.css`、`lesson-plan/**`、`tests/**`、矩阵/STATUS |
| B-R05-EXT4-I2 | Limit-scope-implementer（教案） | `features/lesson-plan/components/*.tsx`、`features/lesson-plan/styles/lesson-plan.css`、**新建**（如需）`features/lesson-plan/styles/lesson-visual.css` | `print.css`、`@media print` 块、`services/pagination.ts`、`model/*`、`services/**`、`space.css`、`globals.css`、`motion.css`、`settings/**`、`tests/**`、矩阵/STATUS、原 Word 模板 |
| B-R05-EXT4-A1 | Independent-Acceptor（只读） | `docs/qa/B-R05-EXT4/A1-REPORT.md`、`docs/qa/B-R05-EXT4/A1-shots/` | 全部产品与测试文件 |
| 权威文档/矩阵/Git | 队长 | `docs/STATUS.md`、`docs/replica/*`、`docs/PROJECT_GUIDE.md`、Git | — |

I1 与 I2 文件集互不相交，可并行；两者都不启动服务器、不跑 build（构建与端口归队长；自测用 5175）。

## 5. 资源分配

| 资源 | 归属 | 说明 |
| --- | --- | --- |
| 前端端口 5174 | 队长（A1 期间独占） | 生产预览 `node scripts/run-web.mjs start 5174`；同一时刻只有一个进程 |
| 构建目录 `apps/web/.next` | 队长 | 实现者不得跑 `npm run build`；类型检查用 `npx tsc --noEmit -p apps/web` |
| e2e | 队长（A1 可复核） | 运行前必须先停队长的手动 5174 |
| 证据目录 | `docs/qa/B-R05-EXT4/` | `before/`、`after/`、`shoot.mjs`、`TASK-CARD.md`、`E4-GAP-LIST.md`、`A1-REPORT.md`、`README.md` |
| 用户端口 5173/8000、正式 `.env`/`.local-data`、真实草稿 | 禁碰 | 全程不读写 |

## 6. 行为闭环与验收条件

- **设置页**：分类导航/锚点/搜索、五个分区（外观/模型与连接/MCP/Skills/关于）的视觉统一；`settings-index` 导航项 hover/current 态、搜索框 focus 态、分区标题层级、`settings-toggle` 开关视觉、`ExtensionManager` 卡片视觉；**模型区内层保持原样**（只允许外层容器视觉增量）。
- **教案页**：三栏工作台（大纲/编辑/预览）的视觉统一、表单分区与字段视觉、按钮与焦点态、移动端 tab；**导出与草稿链路零行为变化**。
- **交互状态**：加载/空/错误/hover/focus/禁用/长文案截断不得回退；键盘可达与焦点环保持。
- **窄视口（重点）**：390×844 历史高发区。设置页 `settings-workspace` 已有 `≤767px` 单列处理；教案页 `lesson-plan.spec.ts:168` 已断言三视口 `scrollWidth <= innerWidth`。实测 `getBoundingClientRect`，不能只看截图。
- **动画（R1）**：设置页已有 `M-settings-nav`（160ms 背景、滚动定位）与 `M-model-management`（150ms 卡片/箭头、`active:scale(.995)`、reduce 关闭）条目——本批实装须与其参数一致，不得改既有参数。新动画只做参考有明确来源者，记入 MOTION_MATRIX 新条目，状态最高「实现待验收」。
- **减少动画**：复用 `motion.css` 全局机制，不新增旁路，不用 `!important` 绕过。

## 7. 必须运行的检查

- I 卡：`npx eslint <改动目录> --max-warnings=0`；`NODE_OPTIONS=--no-experimental-webstorage npx vitest run <相关测试>`；`npx tsc --noEmit -p apps/web`；窄视口 `getBoundingClientRect` 实测值。
- 队长：typecheck / lint / unit 全量 / build / e2e 全量（含 `model-settings.spec.ts`、`model-settings-nesting.spec.ts`、`settings.spec.ts`、`lesson-plan.spec.ts` 7 例）+ 三视口前后截图。
- A1：独立浏览器三视口 + 焦点 + reduce + 正常/空/长标题/错误态；**设置页复核模型区全链路不回退**（供应商卡片→详情→发现→参数/推理表单→默认选择，参考 `model-settings.spec.ts` 断言）；**教案页复核导出与草稿**（Word/PDF 导出产物、草稿恢复、跨页返回）。

## 8. 队长裁定（E4 完成后回填，2026-09-19）

E4 交付 34 条差距（设置 21 / 教案 13，教案已声明无参考仓库对照）、**两份风险清单各 10 条**、7 项待决。**总原则：不改任何既有 e2e 断言；模型区与教案导出/草稿链路一律保守。**

### 8.1 必做（I 卡）

| # | 项 | 依据 |
| --- | --- | --- |
| 1 | **设置索引导航行视觉对齐参考 Row**（图标 + 标题 + 描述小字、hover/current 双态区分、focus 态），**保留 `aria-current="location"` 与 `设置分类` 导航名** | E4 S1/I3、`replica-settings.spec.ts:23-27` |
| 2 | **搜索框 focus 态 + 清除按钮**（清除钮用未占用的 aria-label，如「清除搜索」） | E4 I1/I2、S4 |
| 3 | **搜索无结果空态文案**（新增，不得与既有空态文案同名） | E4 S3 |
| 4 | **ExtensionManager 卡片/按钮视觉统一**（hover/disabled/focus、角色开关视觉）；保留既有 `settings-enter 160ms` 入场与 `role`/文案 | E4 摘要 #4、`settings.spec.ts:17-18` 依赖 |
| 5 | **外观分区与关于分区的视觉统一**（标题层级、段落排版、开关行样式），不改文案 | E4 S7 的可做部分 |
| 6 | **教案表单分区/字段/type-chip/模板缩略卡视觉统一**（不碰字段结构与 label） | E4 L3 |
| 7 | **教案预览工具栏图标按钮 hover/disabled 态统一**（`PreviewPane.tsx`） | E4 L4 |
| 8 | **教案 toast / storage-alert 视觉统一**（`EditorOverlays.tsx`；**不改 `role` 与文案**） | E4 L5、`lesson-plan.spec.ts:191` |
| 9 | **教案导航分段/章节项 hover-active 微调**（只增不改，保留既有类名） | E4 L1 |
| 10 | **导出菜单轻量进出场**（可选）：若做，参数必须对齐 /chat 基准 `chat-home-popup 180ms cubic-bezier(0.16,1,0.3,1)`（`chat-home.css:233`），记 MOTION_MATRIX 新条目 | E4 L2 |

### 8.2 不做（保留现状，记入矩阵/STATUS 边界）

| 项 | 裁定 | 理由 |
| --- | --- | --- |
| 参考式导航分组折叠（CategoryHeaderRow） | **不做** | E4 S1 已判有意保留差异；五分区平铺是当前信息架构 |
| 参考式页级工具栏（草稿三态 + Tour/Discard/Save draft/Apply） | **不做** | E4 待决 #2 / S5：contract-v1 直写服务端无草稿层，属架构级新增；且与 `settings.spec.ts:17-18` 错误态断言环境冲突 |
| 参考式页级加载/错误横幅 | **不做** | E4 S6：错误态收在模型区内层，`settings.spec.ts:12-15` 依赖内层文案；页级横幅会引入第二个「重试」 |
| Overview 状态条 / 服务就绪面板 / 语言开关 / Tour / 草稿时间戳 | **不做**（含静态占位） | E4 待决 #1：呈现它们需要后端状态数据，超出「只做视觉不补业务」边界；静态占位会展示不存在的状态（假信息） |
| 导航行失败红点徽标 | **不做** | E4 S2：需服务诊断数据 |
| 参考式窄视口分组下拉（替代横向滚动条带） | **不做** | E4 S9：条带已满足 390 断言，属结构变更 |
| 模型区任何结构与既有 CSS 选择器改动 | **不做** | 任务卡 2.1 + E4 风险 R1-R7/R9：五处可访问名称锚点 + 聊天页共用 `model-settings.css` |
| 共享 `Modal.tsx` / `modal.css` 弹层动效 | **不做** | E4 待决 #4：共享组件不在本批可写清单；记为遗留差距（后续批可单开小卡） |
| 教案硬编码色值替换为 globals 变量 | **不做** | E4 待决 #6：`lesson-plan.css` 既有大量硬编码色，「只增不改」下仅新增元素消费变量 |
| 教案预览缩放加过渡 | **不做** | E4 待决 #7：影响连续拖动体验且未实测帧率 |
| `M-settings-nav` 160ms → 150ms 参数对齐 | **不做** | E4 待决 #5：按「不得改既有参数」保持 160ms，差异仅记录 |

### 8.3 关键实施约束（E4 风险清单落地）

1. **`.settings-workspace` 后代作用域会穿透命中模型区内层同名类**（`.settings-form/.settings-hint/.settings-toolbar/.settings-feedback` 双定义，R8）→ I1 **不得**写 `.settings-workspace .settings-form` 这类会波及模型区的选择器；新增规则必须用**更窄的新类**（如 `.extension-manager` 后代、`.settings-index` 后代、新建 `.settings-*` 前缀类）。同名类一律不写新规则。
2. **不得改变 `SettingsWorkspace.tsx` 的 import 顺序**（`settings.css` 后加载会覆盖 `model-settings.css` 的同名类，翻转顺序会改变模型区表单布局——E4 全局发现）。
3. **模型区 5 处高危锚点**（卡片 aria-label `打开 {名} 的详情`、`用于问答`、checkbox `{id} 已添加`、`^Base URL` label、dialog aria-label）**一律不动**；R2 要求视觉增量不得把模型列表提升到卡片层。
4. **新控件不得与既有控件同名**（R9：设置页已有两处「添加连接」、两处「重试」）——新按钮用未占用名称。
5. **教案禁区 10 条（D1-D10）逐条遵守**：`print.css`、`@page lesson-plan`、Word 映射与模板校验、DraftRepository/schemaVersion/本地键、600ms 防抖与 flush、FillProvider、`services/pagination.ts`（整体禁改）、`--serif` 回退链（密集编辑区不强制 Lora）、布局断言锚点类名（`.subject-cell/.save-status/.storage-alert/.process-editor/.paper/.print-text/.secondary-cell/.approval-line/.paper-footer/.preview-pane/.chat-page/.chat-toolbar/.sidebar-brand`）。
6. **教案只增屏幕样式**：`lesson-plan.css` 内无 `@media print` 块（E4 已核实），但**不得新开 `@media print`**，也不得改 `@page`。
7. 动画只走 `motion.css` 全局 reduce 机制，零 `!important`；新动画不得引入新时长/缓动体系（沿用 150/160/180/200ms 既有档位）。
