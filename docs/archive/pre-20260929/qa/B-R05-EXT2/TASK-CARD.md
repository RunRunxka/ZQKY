# B-R05-EXTEND v2 任务卡（队长定稿）

定稿时间：2026-09-18 ｜ 队长：外部 Agent（实施总控）｜ 起点 SHA：`de3f8b7`（分支 `codex/replica-review-20260908`）
参考：`F:\DeepTutor` 固定 `42fab3cf429a1fbf36b257ab8d116a3814964202`（只读，不升级）

## 1. 批次范围（用户已锁定，不得扩大）

R-05 视觉规范推广第二批，**书籍 + 课程四个页面条目**：

| 页面条目 | 路由 | 组件 |
| --- | --- | --- |
| P-books | `/books` | `BooksRoute.tsx`（BookLibrary） |
| P-books-[bookId] | `/books/[bookId]` | `BooksRoute.tsx`（BookWorkspace / ProposalView 等） |
| P-courses | `/courses` | `CoursesShelf.tsx` |
| P-courses-[courseId] | `/courses/[courseId]` | `CourseDetail.tsx` |

**本批只做视觉与既有状态呈现推广，不补新业务。** H1 业务闭环（compiling/paused/error、流式生成、暂停恢复、书籍聊天、课程学习会话）**不在本批**，仍属后续独立批。`P-books-pages-[pageId]`（PageReader 阅读器）不在本批四个条目内；但其样式文件由 I1 独占，若为避免样式断裂必须触碰，须在实现卡中显式声明并单独说明。

## 2. 共享层定稿（队长自留，实现者只引用）

1. **`apps/web/src/styles/globals.css`：本批只读。** 变量层 `--font-*`/`--radius-*`/`--shadow-*`/`--space-*` 已建立，直接引用。
2. **`apps/web/src/features/space/styles/space.css`：本批只读。** 被 13 个模块 import，改动会外溢。
3. **`apps/web/src/features/books/books.css`：本批由 I1 独占（可写）**——该文件仅被 `BooksRoute.tsx` 与 `PageReader.tsx` import，是书籍模块私有样式，不外溢。实施要求：
   - 保持 `.books-*` 前缀；新增内容仍用 `.books-*` 或 `.books-page .space-*` 后代作用域；
   - 顶部注释说明「消费 globals.css 单一变量层（R-05）」；
   - **不得**重新定义色板/字体常量，只用既有变量；**不得**出现 `!important`。
4. **`apps/web/src/features/courses/` 无独立 CSS**：I2 新建 `apps/web/src/features/courses/courses.css`，前缀 `.courses-*`，同样只消费变量、无 `!important`，并在 `CoursesShelf.tsx` / `CourseDetail.tsx` 顶部 import。
5. 页面根节点加模块修饰类（`space-page books-page` / `space-page courses-page`）用于收窄覆盖；既有 `space-*` 类名零改名零删除。
6. **CSS 注释安全**：注释内不得出现 `*/` 序列（如 `--radius-*/` 会提前闭合注释导致 Turbopack 构建失败，上一批已发生一次）。用顿号、括号或改写表述。

## 3. 分卡与独占文件表

| 卡 | 负责人角色 | 独占可写文件 | 禁止修改 |
| --- | --- | --- | --- |
| B-R05-EXT2-E2 | Evidence-Collector（只读） | `docs/qa/B-R05-EXT2/E2-GAP-LIST.md` | 其余全部 |
| B-R05-EXT2-I1 | Limit-scope-implementer（书籍） | `features/books/BooksRoute.tsx`、`features/books/books.css`、（如需）`features/books/PageReader.tsx` | `space.css`、`globals.css`、`courses/*`、`services/*`、`tests/*`、矩阵/STATUS |
| B-R05-EXT2-I2 | Limit-scope-implementer（课程） | `features/courses/CoursesShelf.tsx`、`features/courses/CourseDetail.tsx`、**新建** `features/courses/courses.css` | `space.css`、`globals.css`、`books/*`、`services/*`、`tests/*`、矩阵/STATUS |
| B-R05-EXT2-A1 | Independent-Acceptor（只读） | `docs/qa/B-R05-EXT2/A1-REPORT.md`、`docs/qa/B-R05-EXT2/A1-shots/` | 全部产品与测试文件 |
| 权威文档/矩阵/Git | 队长 | `docs/STATUS.md`、`docs/replica/*`、`docs/PROJECT_GUIDE.md`、Git | — |

I1 与 I2 文件集互不相交，可并行；两者都不启动服务器、不跑 build（构建与端口归队长）。

## 4. 资源分配

| 资源 | 归属 | 说明 |
| --- | --- | --- |
| 前端端口 5174 | 队长（A1 期间借给验收者） | 生产预览 `node scripts/run-web.mjs start 5174`；同一时刻只有一个进程 |
| 构建目录 `apps/web/.next` | 队长 | 实现者不得跑 `npm run build`；如需类型检查用 `npx tsc --noEmit` |
| e2e | 队长（A1 可复核） | 运行前必须先停队长的手动 5174 |
| 证据目录 | `docs/qa/B-R05-EXT2/` | `before/`、`after/`、`shoot.mjs`、`E2-GAP-LIST.md`、`A1-REPORT.md`、`README.md` |
| 用户端口 5173/8000、正式 `.env`/`.local-data` | 禁碰 | 全程不读写 |

## 5. 行为闭环与验收条件

- **信息结构**：按 E2 清单补齐参考可见区块，保留全部既有数据、跳转、统计计数、进度、资源引用关系、模拟标注。
- **交互状态**：加载/空/错误/搜索/hover/focus/禁用/长文案截断不得回退；键盘可达与焦点环保持。
- **窄视口（重点）**：390×844 是历史高发缺陷区。常驻 flex 元素（徽标/时间戳/按钮）必须可收缩或换行；`sticky`/`nowrap` 容器要实测 `getBoundingClientRect` 确认不溢出视口。实现者自检必须给量测值，不能只看截图。
- **动画（R1）**：只实装参考有明确来源的参数（时长/缓动/触发），逐条记入 MOTION_MATRIX 新 `M-books-*`/`M-courses-*` 条目，状态最高「实现待验收」；无来源不添加。
- **减少动画**：系统与本地 reduced 均生效（复用 `motion.css` 全局机制，不新增旁路）。
- **数据兼容**：`books-store` / `courses-store`、R-11 目录故障三态、资源引用不可用提示的读写语义与提示文案不变。
- **role 冲突**：同一交互路径不得出现多个 `role="alert"`（上一批 e2e strict 定位冲突先例）。

## 6. 必须运行的检查

- I 卡：`npx eslint <改动目录> --max-warnings=0`；`NODE_OPTIONS=--no-experimental-webstorage npx vitest run <相关测试>`（books-store/courses-store）；`npx tsc --noEmit -p apps/web`；窄视口 `getBoundingClientRect` 实测值。
- 队长：typecheck / lint / unit 全量 / build / e2e 全量 + 三视口前后截图。
- A1：独立浏览器三视口 + 焦点 + reduce + 正常/空/长标题/错误态（含资源目录损坏态）+ 既有功能回归，逐项 pass/fail/not_run。

## 7. 队长裁定（E2 完成后回填，2026-09-18）

E2 交付 97 条差距（P-books 21 / P-books-[bookId] 30 / P-courses 15 / P-courses-[courseId] 31），标注 13 条 e2e 冲突风险与 8 条待决。**总原则：不改任何既有 e2e 断言**；会触碰断言的结构改动一律保留现状，只做不改变可寻址性/文案的视觉增强。

### 7.1 必做（I 卡，按 E2 倾向「可安全实现」且视觉收益高）

| # | 项 | 依据 |
| --- | --- | --- |
| 1 | **`.books-rail` ≤900px 解除 sticky**（本批第一优先） | E2 窄视口清单首行：单列后仍 `position:sticky; max-height:calc(100vh-120px)` 会挤压/遮挡正文；姊妹类 `.space-scope-rail` 在 `space.css:741-747` 已有 `position:static` 覆盖，books-rail 缺失。修复须保留 `aria-label="章节目录"`（`books-courses.spec.ts:81`） |
| 2 | **卡片悬浮语言**（books 卡、courses 卡）：`transform/border-color/box-shadow 150ms` + hover 抬升 + focus-visible 焦点环 + 尾部箭头位移 | E2 全局发现 2；参考 `BookLibrary.tsx:229`、`CoursesShelf.tsx:143` |
| 3 | **books 搜索常驻（≥640px 显示）+ 匹配计数行** | E2 冲突 #4 判「可安全实现」；保留 `aria-label="搜索书籍"` |
| 4 | **books 删除改卡片内两击确认**（替代 `window.confirm`） | E2 冲突 #3 判「可安全实现」（spec 无书籍删除断言） |
| 5 | **异步按钮 busy/disabled 态**（确认提案/确认大纲/保存大纲/创建/保存课程/归档） | E2 全局发现 3；参考 `disabled:opacity-50~60` + Loader2 旋转；沿用既有 `.space-spin` |
| 6 | **课程大纲区**：进度条（`progressbar` role + `aria-valuenow` + `transition-[width] duration-300`）、单元位置编号、covered `line-through`、下一单元底色高亮、topics 单行截断 | E2 P-courses-[courseId] #1；标题文本与 checkbox aria-label 必须保留（冲突 #9/#10） |
| 7 | **课程资料行**：kind 图标、label `truncate`、不可用后缀独立 `shrink-0`、移除钮 hover/focus-visible 显隐（`transition-opacity`） | E2 P-courses-[courseId] #2；文案不可改（冲突 #11） |
| 8 | **课程列表卡片页脚信息**（资料数带图标 + 「Nothing attached yet」空态语义；**会话数不得显示 0 冒充**） | E2 冲突 #8 判「可安全实现」，但会话体系未接入，须以未接入直述而非 0 |
| 9 | **加载骨架统一**：沿用既有 `.space-skeleton` 脉冲（不新增第二套） | E2 P-courses #5 |
| 10 | **统计 chips 保留结构、仅做视觉增强** | E2 冲突 #1 |

### 7.2 不做（保留现状，记入矩阵/STATUS 边界）

| 项 | 裁定 | 理由 |
| --- | --- | --- |
| books 统计 chips 改 StatCard 大数字卡 | **不做** | `books-courses.spec.ts:28-31` 依赖 `role=note` + `.space-chip` 结构 |
| courses 新建入口改网格末格卡 | **不做** | `books-courses.spec.ts:179-183` 依赖页头按钮 + dialog |
| courses 归档区改紧凑行 | **不做** | `books-courses.spec.ts:171-174` 依赖 `.space-persona-card` |
| 课程详情附加资料改内嵌面板 | **不做** | 冲突 #12 建议保守保留 Modal；两 spec 多处依赖 dialog 结构 |
| 大纲标题文本格式改动 | **不做** | 冲突 #9：正则依赖 `大纲（x/y 已完成…）` |
| BookCreator 知识源页签（KB/Notebooks/Questions/Chats） | **不做** | 属 H1 创建流程信息结构；Questions/Chats 目录在目标项目不存在，做半套会误导 |
| CourseNextStep / CourseProgress 聚合磁贴 | **不做**（页内 banner 已如实声明未接入） | 依赖 CourseState 聚合与会话体系（H1）；空态壳属新增业务面 |
| CourseDialog Mode/Persona 字段 | **不做** | 与会话体系强绑定（H1） |
| 「N wrong」证据徽标、会话计数、最近活跃时间 | **不做** | 聚合数据未接入，显示会失真 |
| 书籍阅读器侧栏折叠（232↔14px）、Rebuild 3.5s 两击、HealthBanner、Chat 面板、compiling/paused/error、流式生成 | **不做** | H1 业务闭环；E2 已登记为有意保留差异 |
| reduced-motion 机制对齐参考（参考保留关键过渡） | **不做** | 改 `globals.css` 全局层超出本批共享边界；仅登记差异 |

### 7.3 待决口径确认

- **「编译中」分支**：确认按 E2 处理——属 H1 状态机，本批不实现、不展示入口，只登记为有意保留差异。
- **[未验证] 项**（参考 404 UI、参考 Modal 进出场动画）：保持 not_run，不写入矩阵为已验。

### 7.4 共享样式边界（定稿）

- `books.css`（I1 独占）：保持 `.books-*` 前缀；新增用 `.books-page .space-*` 后代作用域。
- `courses.css`（I2 新建）：前后缀 `.courses-*`；节点加 `courses-page` 修饰类。
- **CSS 注释里不得出现 `*/` 序列**（上一批因 `--radius-*/` 导致 Turbopack 构建失败）。
- 既有类名（`.space-card-link` 被 courses 复用）不得删除或改名。
