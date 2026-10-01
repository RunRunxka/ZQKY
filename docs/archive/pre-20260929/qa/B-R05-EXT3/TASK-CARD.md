# B-R05-EXTEND v3 任务卡（队长定稿）

定稿时间：2026-09-18 ｜ 队长：外部 Agent（实施总控）｜ 起点 SHA：`1aad54b`（分支 `codex/replica-review-20260908`）
参考：`F:\DeepTutor` 固定 `42fab3cf429a1fbf36b257ab8d116a3814964202`（只读，不升级）

## 1. 批次范围（用户已锁定，不得扩大）

R-05 视觉规范推广第三批，**写作四页中的两页 + 阅读库级两页**：

| 页面条目 | 路由 | 组件 |
| --- | --- | --- |
| P-co-writer | `/co-writer` | `features/writing/WritingLibrary.tsx` |
| P-co-writer-[docId] | `/co-writer/[docId]` | `features/writing/WritingEditor.tsx` |
| P-reading | `/reading` | `features/reading/ReadingLibrary.tsx` |
| P-reading-materials | `/reading/materials` | `features/reading/MaterialLibrary.tsx` |

**明确不在本批**：
- `P-reading-[workspaceId]`、`P-reading-sessions`、`P-reading-sessions-[sessionId]`（`ReadingWorkspace.tsx`，1696 行）——它有 R-09 五例与 READ-RETRY/READ-END 已验收交互，视觉改动需单独任务卡。
- `P-whisper`、`P-books-pages-[pageId]`、设置/教案与其他模块。

**只做视觉与既有状态呈现推广，不补新业务。** DOCX 导入、真实材料解析、真实 AI 通道均不在本批。

## 2. 共享层定稿（队长自留，实现者只引用）

1. **`apps/web/src/styles/globals.css`、`motion.css`、`features/space/styles/space.css`：本批只读**（space.css 被 13 个模块 import）。
2. **`apps/web/src/features/reading/reading.css`：本批只读**——该文件被**不在本批**的 `ReadingWorkspace.tsx` 共用（`reading.css` 内 `.reading-layout/.reading-pane/.reading-companion/.reading-drawer*/.reading-selection-bar` 全是工作区样式）。改动它会波及 R-09 已验收的滚动/抽屉/拖拽行为。
3. 新增（本批创建，单一写入者见表）：
   - `apps/web/src/features/writing/styles/writing.css`（类前缀 `.writing-*`）
   - `apps/web/src/features/reading/styles/reading-library.css`（类前缀 `.reading-lib-*`）
   两文件顶部注明「消费 globals.css 单一变量层（R-05）」，**不重复定义色板/字体常量**，只引用既有变量。
4. 页面根节点加**修饰类**用于收窄覆盖：写作两页 `space-page writing-page`；阅读两页 `space-page reading-lib-page`。
   - **禁止**给 `ReadingWorkspace.tsx` 加任何类或改它的 import（它保持 `space-page` 不变，因此不会命中本批新样式）。
5. **硬性**：既有 `space-*` 类名零改名零删除；新增 CSS 零 `!important`；**注释内不得出现 `*/` 序列**（`--radius-*/` 会提前闭合注释导致 Turbopack 构建失败，前批已踩两次）。

## 3. 分卡与独占文件表

| 卡 | 负责人角色 | 独占可写文件 | 禁止修改 |
| --- | --- | --- | --- |
| B-R05-EXT3-E3 | Evidence-Collector（只读） | `docs/qa/B-R05-EXT3/E3-GAP-LIST.md` | 其余全部 |
| B-R05-EXT3-I1 | Limit-scope-implementer（写作） | `features/writing/WritingLibrary.tsx`、`features/writing/WritingEditor.tsx`、**新建** `features/writing/styles/writing.css` | `space.css`、`globals.css`、`motion.css`、`reading/**`、`services/**`、`tests/**`、矩阵/STATUS |
| B-R05-EXT3-I2 | Limit-scope-implementer（阅读库） | `features/reading/ReadingLibrary.tsx`、`features/reading/MaterialLibrary.tsx`、**新建** `features/reading/styles/reading-library.css` | `space.css`、`globals.css`、`motion.css`、**`reading/reading.css`**、**`reading/ReadingWorkspace.tsx`**、`writing/**`、`services/**`、`tests/**`、矩阵/STATUS |
| B-R05-EXT3-A1 | Independent-Acceptor（只读） | `docs/qa/B-R05-EXT3/A1-REPORT.md`、`docs/qa/B-R05-EXT3/A1-shots/` | 全部产品与测试文件 |
| 权威文档/矩阵/Git | 队长 | `docs/STATUS.md`、`docs/replica/*`、`docs/PROJECT_GUIDE.md`、Git | — |

I1 与 I2 文件集互不相交，可并行；两者都不启动服务器、不跑 build（构建与端口归队长）。

## 4. 资源分配

| 资源 | 归属 | 说明 |
| --- | --- | --- |
| 前端端口 5174 | 队长（实现者自测用 5175，A1 期间独占 5174） | 生产预览 `node scripts/run-web.mjs start 5174`；同一时刻只有一个进程 |
| 构建目录 `apps/web/.next` | 队长 | 实现者不得跑 `npm run build`；类型检查用 `npx tsc --noEmit -p apps/web` |
| e2e | 队长（A1 可复核） | 运行前必须先停队长的手动 5174 |
| 证据目录 | `docs/qa/B-R05-EXT3/` | `before/`、`after/`、`shoot.mjs`、`TASK-CARD.md`、`E3-GAP-LIST.md`、`A1-REPORT.md`、`README.md` |
| 用户端口 5173/8000、正式 `.env`/`.local-data`、真实草稿 | 禁碰 | 全程不读写 |

## 5. 行为闭环与验收条件

- **模拟标注必须完整保留**：写作「AI 修改为显式模拟：流式预览 → 应用/放弃，应用前自动保存版本」、材料「（模拟解析）/模拟抓取/模拟转录」「解析产物为本地结构化样例并全程标注」等文案**逐字保留**，不得美化、不得删减。
- **既有功能全部保留**：写作的自动保存/保存状态、撤销栈、版本快照与恢复、选区 AI 预览/应用/放弃/取消/失败重试、两击或 confirm 删除路径；阅读的集合卡片与材料/会话计数、材料筛选页签、模拟解析 queued/processing/ready/failed 四态与取消/重试、分配材料弹窗、批注/书签入口跳转。
- **交互状态**：加载/空/错误/筛选/hover/focus/禁用/长文案截断不得回退；键盘可达与焦点环保持。
- **窄视口（重点）**：390×844 历史高发区。常驻 flex 元素（字数/版本/状态 chip、操作按钮）必须可收缩或换行；实测 `getBoundingClientRect`，不能只看截图。
- **动画（R1）**：只实装参考有明确来源的参数（时长/缓动/触发），逐条记入 MOTION_MATRIX 新 `M-writing-*`/`M-reading-lib-*` 条目，状态最高「实现待验收」；无来源不添加。
- **减少动画**：复用 `motion.css` 全局机制，不新增旁路，不用 `!important` 绕过。
- **数据兼容**：`writing-store` / `reading-store` / `reading-ingest` 的读写语义与键名（`zhiqikeyuan:writing-*`、`zhiqikeyuan:reading-*`）零改动；不新增测试接口。

## 6. 必须运行的检查

- I 卡：`npx eslint <改动目录> --max-warnings=0`；`NODE_OPTIONS=--no-experimental-webstorage npx vitest run <相关测试>`；`npx tsc --noEmit -p apps/web`；窄视口 `getBoundingClientRect` 实测值。
- 队长：typecheck / lint / unit 全量 / build / e2e 全量（含 `reading.spec.ts` 17 例与 `writing.spec.ts` 3 例）+ 三视口前后截图。
- A1：独立浏览器三视口 + 焦点 + reduce + 正常/空/长标题/错误态（长文档名、版本历史展开、批注密集段的库级入口）+ 既有功能回归（阅读 R-09 行为不许回退）。

## 7. 队长裁定（E3 完成后回填，2026-09-19）

E3 交付 64 条差距（写作列表 20 / 编辑器 27 / 阅读库 21 / 材料库 24）、10 条 e2e 冲突风险、9 条模拟标注保护清单、7 条窄视口风险、10 条待决。**总原则：不改任何既有 e2e 断言**；触碰断言的结构改动一律保留现状。

### 7.1 必做（I 卡）

| # | 项 | 依据 |
| --- | --- | --- |
| 1 | **窄视口修复（最高优先）**：`/reading/materials` 的行头在解析失败+未分配态会同时出现 5 个 chip + 4 个操作按钮且 `space-session-top` 无 wrap（`space.css:408-412`），390px 必然溢出 | E3 窄视口清单首行（最高风险）；修法：本页作用域内允许 wrap，操作组可收缩/换行，实测 `getBoundingClientRect` |
| 2 | **写作模块新增 CSS 载体**（E3 待决 #7）：新建 `features/writing/styles/writing.css`，`.writing-*` 前缀 | space.css 禁改；写作模块当前零 CSS、全内联 |
| 3 | **阅读库级新增 CSS 载体**：新建 `features/reading/styles/reading-library.css`，`.reading-lib-*` 前缀 | `reading.css` 是工作区共用禁区（E3 附录 A 逐类列出消费方） |
| 4 | **卡片悬浮语言**：写作列表卡片、阅读集合卡片、材料行补 `transition` + hover 边框/底色 + `:focus-visible` 焦点环 | E3 四页「最值得做」均含此项；参考 `transition-colors hover:border-[var(--ring)]` |
| 5 | **空态增强（保留原文案）**：写作「还没有文稿」、阅读「还没有阅读集合」、材料「还没有材料」加图标块与主行动按钮；**strong 文案逐字保留** | E3 冲突 #9 判「可安全实现（有条件）」 |
| 6 | **按钮动效**：主按钮 `transition-opacity hover:opacity-90` + `active:scale-[0.97]`；沿用给 `.writing-page`/`.reading-lib-page` 作用域 | 参考 `CoWriterWorkspace.tsx:1788`；不改进 space.css |
| 7 | **材料库筛选 chips**（E3 P-reading-materials #1）：在现有 2 个 tab 基础上补「解析中/失败」筛选语义（可保留 tab 形态，只加筛选维度与计数） | 参考 4 chips；当前仅 2 |
| 8 | **模拟标注保留清单 9 条逐字核对**（E3 已给行号） | 红线项；实现后须自检文案未变 |
| 9 | **收藏集卡片相对时间 + 章节目录类交互过渡**：集合卡片与材料行的 hover/focus 过渡、时间显示可保持绝对时间但补 hover 过渡 | 低风险视觉项 |

### 7.2 不做（保留现状，记入矩阵/STATUS 边界）

| 项 | 裁定 | 理由 |
| --- | --- | --- |
| 新建文稿改「点击即建」（去掉弹窗） | **不做** | `writing.spec.ts:17-20` 依赖 dialog/label/`创建` 三层 |
| 删除改两击/自定义 Dialog（写作列表、材料库、阅读集合） | **不做** | 两 spec 依赖原生 `page.once('dialog')`；统一范式需连 spec 改，超出本批 |
| 版本历史/快照/恢复对齐参考（删除） | **不做** | 参考无此系统，当前是超出参考的本地增强，`writing.spec.ts:45-48` 依赖 |
| LibraryShell 双 tab 化（阅读两页合一壳、行式列表替换卡片） | **不做** | `reading.spec.ts:25-26` 断言 `.space-page` display:flex、`:30-33` 依赖 `.space-persona-card` 计数、`:16/:35` 依赖 aria-label；只保留两页各自 heading |
| 材料库改参考上传对话框 / 新建材料表单改上传 | **不做** | `reading.spec.ts:142-147` 与 R32 用例双重依赖现表单与「模拟解析」类型选择 |
| 列表网格化（写作卡片 1/2/3 列） | **不做** | 非阻塞视觉差异；换行与截断在窄视口更保守 |
| 搜索框（阅读集合/材料库） | **不做** | 属功能面新增；当前数据量小 |
| DOCX 导入、真实解析/转录、真实 AI 通道、split-pane、同步滚动、字数口径改为 words | **不做** | 后续批；字数口径无 e2e 影响但也无必要 |
| WritingEditor 解除对 `reading-msg` 的借用 | **不做**（仅登记） | 本批不动 reading.css；后续批可解耦 |
| `?focus=mat-` 消费逻辑（高亮/滚动定位） | **不做**（URL 保留） | 非视觉项；URL 参数本身不可移除 |

### 7.3 动画口径修正（依据 E3 附录 A）

E3 核出：四页源码**未引用** `dt-pop-in`；实际被引用的是 tailwindcss-animate 类（`animate-in fade-in / zoom-in-95`）与 `dt-popup-up`（仅编辑器内部若干处）。因此：
- 本批**不新增**进出场动画（无稳定来源），只做 hover/focus/active 过渡（参考有明确 `transition-* duration-150` 参数）。
- MOTION_MATRIX 新条目按实际实装的过渡填写，状态最高「实现待验收」。

### 7.4 共享样式边界（定稿）

- `space.css`、`globals.css`、`motion.css`、**`reading.css`**、`ReadingWorkspace.tsx` 本批**只读**。
- 新增 `features/writing/styles/writing.css`（`.writing-*`）与 `features/reading/styles/reading-library.css`（`.reading-lib-*`），只消费既有变量、零 `!important`、注释内不得出现 `*/` 序列。
- 页面根节点加修饰类：写作 `space-page writing-page`；阅读库 `space-page reading-lib-page`。**不给 ReadingWorkspace 加任何类**（它保持 `space-page`，不命中新样式）。
- 窄视口修复一律写在新 CSS 的页面前缀作用域内。
