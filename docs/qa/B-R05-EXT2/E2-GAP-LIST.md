# B-R05-EXT2-E2 逐页差距清单（v1）

- 核对时间：2026-09-18
- 参考仓库：`F:\DeepTutor`，固定提交 `42fab3cf429a1fbf36b257ab8d116a3814964202`（已用 `git rev-parse` 核实，tag v1.6.5）
- 当前仓库：`H:\备份xuexi\智启课源`，HEAD `de3f8b7ef9cdba1ffbc5f0282a038fc86ab97971`（工作区另有 `apps/web/next-env.d.ts` 一处既有改动与本任务无关）
- 审计范围声明：仅对 P-books、P-books-[bookId]、P-courses、P-courses-[courseId] 四个页面做信息结构/交互状态/动画三类只读比对；未运行任何 build/dev/测试，未修改任何源码。
- 路径缩写：`参` = `F:/DeepTutor/web`，`现` = `H:/备份xuexi/智启课源/apps/web/src`。所有行号均来自实际读取的文件内容。
- 标记约定：[推断]=由代码结构推断、未在浏览器验证；[未验证]=无法从静态读取确认；[与现有e2e冲突风险]=实现会触碰两个既有 spec 的断言。

---

## 摘要

### P-books（/books）最值得做的 3~5 条
1. 卡片悬浮反馈缺失（hover 抬升/描边/阴影，参考 BookLibrary.tsx:229）——books/courses 卡片共用 `space-persona-card` 无任何 hover 规则。
2. 统计区形态：参考是 4 张 StatCard（图标+大数字），当前是 4 枚 chip（现 BooksRoute.tsx:107-112）——改形态会碰 e2e，见冲突汇总。
3. 顶栏搜索常驻（参考 BookLibrary.tsx:132-143 `hidden sm:flex` ≥640px 显示）+ 匹配计数行「x/y · matching query」（参考 185-198）；当前仅 >6 本才显示搜索（现 BooksRoute.tsx:137-148）且只按书名过滤（现 71-75）。
4. 卡片信息行：状态 pill 仅非 ready 显示、章/页带图标、% read 带 tooltip、相对时间带 Clock 图标（参考 303-359）；当前是绝对时间 `toLocaleString`（现 181）与固定状态 chip（现 172）。
5. 删除改为卡片内两击确认（参考 258-286，触屏常驻 hover 显隐）；当前 `window.confirm`（现 190-199）——无 e2e 断言删除，可安全实现。

### P-books-[bookId] 最值得做的 3~5 条
1. 提案分支：参考提案卡是可编辑表单（Title/Description/Scope/Target level/Estimated chapters + KB chips，BookCreator.tsx:824-857、1150-1249）+ 确认按钮 busy 态（842-855）；当前只读展示（现 BooksRoute.tsx:414-433）且确认按钮无 busy/disabled（现 434-444）。
2. 大纲分支：确认大纲按钮无 busy/disabled（参考经 SpineEditor loading=confirmingSpine，参 BooksRoute.tsx:1023-1040；现 498-508），也无「Loading spine…」加载态（参 1150-1154）。
3. 阅读分支侧栏：参考侧栏可折叠（232px↔14px，BookSidebar.tsx:88-131）、含书名/状态/章数头、Export 链接、Rebuild 两击确认 3.5s 自动解除（180-219）、页行 ActivityMark 状态点+已读变暗+书签圆点（255-284）；当前侧栏无折叠、无头部、导出/重建在页头用 window.confirm（现 546-581）、书签用「签」chip（现 642-646）。
4. 窄视口：`.books-rail` 在 ≤900px 单列后仍保持 `position: sticky; top:16px; max-height:calc(100vh-120px)`（现 books.css:15-20），姊妹类 `.space-scope-rail` 在 ≤760px 有 `position: static` 覆盖（现 space.css:741-747）而 books-rail 没有——本批最高优先疑似缺陷，见窄视口清单。
5. 状态机类差异（compiling/paused/error、流式、Chat、HealthBanner）全部登记为有意保留差异（后续批 H1），本批不展开。

### P-courses（/courses）最值得做的 3~5 条
1. 「新建课程」入口：参考是网格末格虚线卡（空库时图标 BookOpen + 文案「Create your first course」，CoursesShelf.tsx:195-219）；当前是页头按钮 + Modal（现 CoursesShelf.tsx:73-76）——改文案/入口位置会碰 e2e。
2. 卡片页脚信息：参考是资料数(Layers)+会话数(MessagesSquare)+最近活跃相对时间，空资源时显示「Nothing attached yet」（参考 162-191）；当前是「大纲 x/y + 资料 n + 本地目录」chips（现 163-169）。
3. 卡片 hover 抬升 + shadow + focus-visible ring + ArrowRight 位移（参考 143、154-157）；当前无。
4. 归档折叠区：参考为紧凑行列表（色点+名+归档时间，232-255）；当前复用完整卡片（现 114-125）——改结构会碰 e2e。
5. 加载骨架 3 张 h-32 `animate-pulse`（参考 128-136）；当前 `.space-skeleton` 已有同型 pulse 动画（现 space.css:274-290），形态差异小。

### P-courses-[courseId] 最值得做的 3~5 条
1. 大纲：参考有 progressbar role + aria-valuenow + `transition-[width] duration-300` 填充条（CourseSyllabus.tsx:142-155）、单元带位置编号、covered 用 line-through、下一单元用底色高亮、topics 单行 truncate（186-245）；当前全部以标题文本+chip 表达（现 CourseDetail.tsx:185-268），无进度条、无编号、无 line-through、无高亮。
2. 资料行：参考 kind 用图标、label truncate、「Unavailable」带 title 提示、kind 名靠右、移除钮 opacity-0 hover/focus-visible 显隐 + `transition-opacity`（CourseResources.tsx:190-235）；当前 kind 用 chip、移除钮常驻（现 300-335）。
3. 学习约定：参考内联 textarea + dirty 追踪 + blur 保存 + Saved 指示（CourseConventions.tsx:55-108）；当前只读段落 + 编辑弹窗（现 344-353、421-427）。
4. 保存类按钮普遍缺 busy/disabled（参考 Syllabus Saving 169-177、Conventions 73-82、Dialog Saving... 209-219；当前保存大纲 219-233、编辑弹窗 458-465 均无）。
5. CourseNextStep / CourseProgress / 会话区 / 顶栏菜单里的「Start course study」依赖 CourseState 聚合与会话体系——登记为有意保留差异（待队长裁定是否做「空态壳」）。

### 全局性发现（跨页面共性）
1. **books.css 已存在、courses 无独立 CSS**：books 模块有 91 行专属样式（现 `features/books/books.css`），courses 只 import space.css（现 CoursesShelf.tsx:19、CourseDetail.tsx:33）。若新增 courses.css，只影响 CoursesShelf.tsx 与 CourseDetail.tsx 两个使用方（详见附录 A）。
2. **卡片悬浮语言整体缺失**：参考在 books 卡（BookLibrary.tsx:229）、courses 卡（CoursesShelf.tsx:143）、进度磁贴（CourseProgress.tsx:153）三处用同一套 `transition-all duration-150 hover:-translate-y-0.5 hover:shadow… focus-visible:ring-2`；当前 `space-persona-card`/`space-tile` 均无（现 space.css:618-627；`.space-tile` 有 hover 抬升 96-106 但未被本四页使用）。补法是给 space.css 增补或新建模块类，不动 globals.css。
3. **busy/disabled 状态面整体偏弱**：参考的异步按钮统一 `disabled:opacity-50~60` + Loader2 `animate-spin`（BookCreator.tsx:810-816、CourseSyllabus.tsx:173 等）；当前四页所有异步按钮（确认提案/确认大纲/保存大纲/创建/保存课程）均无 busy 态。
4. **键盘焦点**：当前 globals.css 有统一 `:focus-visible` outline（现 globals.css:88-95），参考用 `focus-visible:ring-2 ring-[var(--ring)]`（CoursesShelf.tsx:143 等）——效果等价级别，差距主要为卡片容器（当前卡片是 `<a>` 包裹，键盘可达，无需改结构）。
5. **reduced-motion**：参考 globals.css 1094-1110 保留关键交互过渡；当前为全量 `animation/transition: none !important`（现 globals.css:588-594）。按约束不建议改全局层，仅登记差异。

### 窄视口风险清单（390×844，本批最重要）
| 页面 | 元素/容器 | 证据 | 风险 |
|---|---|---|---|
| P-books-[bookId] | `.books-rail`（章节侧栏） | 现 books.css:9-20（≤900px 折为单列后仍 `position:sticky; top:16px; max-height:calc(100vh - 120px); overflow-y:auto`）；对照现 space.css:741-747（`.space-scope-rail` ≤760px 有 `position:static` 覆盖，books-rail 没有） | [推断] 单列布局下侧栏吸顶 `top:16px` 且占满一行，长阅读时持续悬浮在视口顶部、占据约 `calc(100vh-120px)` 高度，阅读正文被挤压/遮挡；`space.css:461-463` 的 `flex:0 0 168px` 被 books.css:3 `grid-template-columns:240px` 覆盖为 grid 轨道，≤900px 后变整行。**疑似本批最应修复项** |
| P-books-[bookId] | 侧栏页链接文字 | 现 BooksRoute.tsx:639-641（`chapter.title（1/2）` 所在 span 无 ellipsis/nowrap，容器 space-scope-item 现空间样式 space.css:465-476 无 min-width） | [推断] 长章节名会换行（不溢出页面），但在吸顶侧栏内加剧高度问题 |
| P-books-[bookId] | ReaderLayout 页头操作区 | 现 BooksRoute.tsx:546-581（back 链接 + 导出/重建两按钮，`.space-header-row` flex-wrap 现 space.css:22-28） | 按钮可换行，不溢出；安全 |
| P-books | 卡片操作行（CTA+删除） | 现 BooksRoute.tsx:183-200（`.space-card-actions` flex-wrap 现 space.css:645-650） | 安全 |
| P-books | 统计 chips 行 | 现 BooksRoute.tsx:107-112（`.space-meta-row` flex-wrap 现 space.css:310-317） | 安全 |
| P-courses | 课程卡片 chips 行 | 现 CoursesShelf.tsx:163-169（同上 flex-wrap） | 安全 |
| P-courses-[courseId] | 单元主题 chips | 现 CourseDetail.tsx:258-266（`.space-meta-row` flex-wrap） | 安全 |
| P-courses-[courseId] | 资料行标题 | 现 CourseDetail.tsx:311-317（不可用后缀并入 `.space-session-title`，nowrap+ellipsis 现 space.css:414-423） | 长文案被截断（省略号），不溢出；参考将 Unavailable 作为独立 shrink-0 span（参 CourseResources.tsx:203-220），截断行为不同，登记为结构不同 #10 |
| P-courses-[courseId] | 头部按钮行（编辑/归档/删除） | 现 CourseDetail.tsx:119-145（flex-wrap） | 安全 |
| P-courses（参考对照） | 参考搜索框 | 参 BookLibrary.tsx:132（`hidden sm:flex`：<640px 隐藏） | 参考在 390px 不显示搜索；当前若改为常驻搜索需同样处理窄视口（当前 >6 本才显示，天然规避） |
| 四页通用 | `.space-page` | 现 space.css:4-11（padding 24/20，max-width 960 居中） | e2e 已验证 390px 无横向溢出（tests/e2e/course-resource-faults.spec.ts:215 scrollWidth 断言），books 两页无同等断言 [未验证] |

### e2e 冲突风险汇总（裁定归队长）
| # | 条目 | 触碰断言 | 倾向建议 |
|---|---|---|---|
| 1 | P-books 统计 chips 改 StatCard | books-courses.spec.ts:28-31（`role=note` 含「共 2 本」、`.space-chip` 含「可阅读」） | 建议保留 chips 结构，仅做视觉增强；或由队长批准同步改 spec |
| 2 | P-books CTA 文案对齐参考三分支 | books-courses.spec.ts:33（继续阅读）、53（继续创建） | 现有文案语义已与参考一致，建议保留现状 |
| 3 | P-books 卡片删除改两击确认 | spec 无书籍删除断言（books-courses.spec.ts 全文无「删除」按钮用例） | 可安全实现 |
| 4 | P-books 搜索常驻/匹配描述 | spec 未断言搜索框 | 可安全实现（保留 aria-label「搜索书籍」现 BooksRoute.tsx:143） |
| 5 | P-books 页面外壳 `.space-page` | books-courses.spec.ts:16-17（`.space-page` display:flex） | 任何外壳重构必须保留 `.space-page` 类名与 flex 布局 |
| 6 | P-courses 新建入口改网格末格卡 | books-courses.spec.ts:179-183（页头按钮「新建课程」+ dialog「新建课程」+「创建」按钮） | 若改入口需保留可寻址按钮名或同步改 spec；建议先做视觉、后动结构 |
| 7 | P-courses 归档区改紧凑行 | books-courses.spec.ts:171-174（`已归档课程（2）` + 展开后 `.space-persona-card` 可见） | 建议保留现状或同步改 spec |
| 8 | P-courses 卡片页脚改资料/会话/时间 | books-courses.spec.ts:127 仅断言卡片存在，未断言 chips 内容 | 可安全实现（会话数恒 0/隐藏需如实标注未接入） |
| 9 | P-courses-[courseId] 大纲标题结构 | books-courses.spec.ts:134,140,159（正则 `大纲（x/y 已完成…）`）；course-resource-faults.spec.ts:56（`/^大纲（/`） | 进度条/单元行可改；标题文本建议保留现格式或同步改 spec |
| 10 | 大纲 checkbox aria-label | books-courses.spec.ts:139；course-resource-faults.spec.ts:55（`标记「X」为已完成`） | 自绘勾选框时必须保留同名 aria-label |
| 11 | 资料行文案 | books-courses.spec.ts:136,149,163-165；course-resource-faults.spec.ts:75-76,108,132 | 「（不可用：目标已删除或未载入）」「（目录读取失败，暂无法确认）」「移除资料 X」「已附加资料」「已移除资料」为固定断言，图标化/重排可做，文案不可改 |
| 12 | 附加资料对话框结构 | books-courses.spec.ts:143-148；course-resource-faults.spec.ts:145-148,157,196-200（`li.space-session-card`、`section.space-group`、按钮「附加资料」「附加」「重试」） | 改为内嵌展开面板需保留这些 role/类名/文案或同步改 spec；建议保守保留 Modal |
| 13 | 返回链接 | course-resource-faults.spec.ts:214（`返回课程列表`） | 保留文案 |

---

## P-books（/books）

参考主体：`参/app/(workspace)/books/components/BookLibrary.tsx`（445 行）；当前主体：`现/features/books/BooksRoute.tsx:46-226`（BookLibrary）+ `228-285`（CreateBookForm）。

### 信息结构
| # | 差距 | 参考证据（文件:行） | 当前证据（文件:行） | 类型 |
|---|---|---|---|---|
| 1 | 顶栏搜索框常驻（≥640px），placeholder「Search books」，带放大镜图标 | 参/app/(workspace)/books/components/BookLibrary.tsx:132-143 | 现/features/books/BooksRoute.tsx:137-148（仅 books.length>6 渲染） | 结构不同 |
| 2 | 统计区为 4 张 StatCard（Total books/Ready/In progress/Chapters，图标+大数字+accent 色） | 参 BookLibrary.tsx:158-182、389-415 | 现 BooksRoute.tsx:107-112（4 枚 space-chip 文本计数） | 结构不同 [与现有e2e冲突风险→摘要#1] |
| 3 | 分组标题「My library」+「x/y books」过滤计数 + 搜索命中提示「matching "query"」 | 参 BookLibrary.tsx:185-198 | 现 无对应区块（现 BooksRoute.tsx:136-211） | 缺失 |
| 4 | 卡片网格 1列/sm:2列/xl:3列 | 参 BookLibrary.tsx:212 | 现 space.css:612-616（auto-fill minmax(250px,1fr)，390px 单列，桌面列数不同） | 结构不同 |
| 5 | 卡顶 3px 进度 hairline：percent>0 即显示（不限 ready） | 参 BookLibrary.tsx:240-256 | 现 BooksRoute.tsx:176-180（仅 ready 显示 reading-bar） | 结构不同 |
| 6 | 卡片删除：两击确认（title「Click again to confirm」）+ 悬停显隐/触屏常驻 | 参 BookLibrary.tsx:258-286 | 现 BooksRoute.tsx:190-199（常驻「删除」按钮 + window.confirm） | 结构不同 [可安全实现] |
| 7 | 徽标组：状态 pill 仅 status≠ready 显示（draft/spine_ready/compiling/paused/error/archived 七态配色 BookLibrary.tsx:23-68）、Shared·edit/read 徽标、章数(Layers)/页数(FileText)图标、% read(BookOpen,带 tooltip)、相对时间(Clock3, formatRelativeTime) | 参 BookLibrary.tsx:303-359 | 现 BooksRoute.tsx:171-181（状态 chip 恒显、章/页 chip 无图标、绝对时间 toLocaleString、无 Shared 徽标——本地无共享概念） | 结构不同 / 文案不同 |
| 8 | CTA 文案三分支：Continue setup（draft/spine_ready）/ Continue reading（visited>0）/ Start reading | 参 BookLibrary.tsx:361-377 | 现 BooksRoute.tsx:153-162（继续创建/确认大纲/继续阅读/开始阅读/查看） | 文案不同 [与现有e2e冲突风险→摘要#2] |
| 9 | 空态结构：28px 图标 + 主句「No books yet」+ 副句 + New book 按钮 | 参 BookLibrary.tsx:417-444 | 现 BooksRoute.tsx:130-134（纯文字 space-empty，按钮在页头） | 结构不同 |
| 10 | 搜索无命中独立空态「No books match "query"」（有书即显示，不限数量） | 参 BookLibrary.tsx:207-210 | 现 BooksRoute.tsx:205-210（仅 >6 本时显示「没有匹配的书籍」） | 结构不同 |
| 11 | 搜索匹配 title+description | 参 BookLibrary.tsx:92-100 | 现 BooksRoute.tsx:71-75（仅 title） | 结构不同 |
| 12 | 页头副标题「Generate, browse and study your AI-authored books.」 | 参 BookLibrary.tsx:123-129 | 现 BooksRoute.tsx:102-104（说明文案为「生成流水线未接入…」——有意如实标注） | 文案不同 |
| 13 | 新建流程为意图驱动（intent + 知识源），书名由提案生成 | 参 BookCreator.tsx:98-117、515-538 | 现 BooksRoute.tsx:228-285（直接输入书名/简介） | 有意保留差异（知识源接入属后续批，见 P-books-[bookId] #4） |

### 交互状态
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| 1 | 卡片 role=button + tabIndex=0 + Enter/Space 键盘激活 | 参 BookLibrary.tsx:218-228 | 现 BooksRoute.tsx:165-199（整卡为 Link 键盘可达；卡内另有 CTA/删除按钮，焦点路径更多但无整卡键盘语义） | 结构不同 |
| 2 | 删除按钮 pendingDelete 视觉态（rose 底色）+ hover 显隐 + 触屏常驻 | 参 BookLibrary.tsx:278-282 | 现 BooksRoute.tsx:190-199（无两击态） | 缺失 |
| 3 | 加载态为 Loader2 spin + 文案 | 参 BookLibrary.tsx:200-204 | 现 BooksRoute.tsx:124-129（骨架块，aria-hidden） | 结构不同 |
| 4 | 搜索框 focus 描边 `focus:border-[var(--primary)]/40` | 参 BookLibrary.tsx:141 | 现 space.css:205-213（.space-search 无 focus 规则，仅全局 outline 现 globals.css:88-95） | 缺失 |
| 5 | 演示数据载入按钮与 notice | 参 无对应（参考无本地演示数据机制） | 现 BooksRoute.tsx:86-95、113-117（本项目特性，显式标注模拟） | 有意保留差异（本项目本地模拟声明） |

### 动画
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| 1 | 卡片 `transition-all hover:-translate-y-0.5 hover:border-[var(--primary)]/40 hover:shadow-md` | 参 BookLibrary.tsx:229 | 现 space.css:618-627（.space-persona-card 无 hover/transition 规则） | 缺失 |
| 2 | 按钮 `transition-opacity hover:opacity-90`（新建/CTA/空态按钮三处） | 参 BookLibrary.tsx:148、367、436 | 现 globals.css:96-101（button 仅 background/color/box-shadow 0.15s；space.css:355-386 hover 仅 border/背景色） | 缺失 |
| 3 | compiling 状态点 `animate-pulse`（STATUS_STYLES.dot） | 参 BookLibrary.tsx:42 | 现 books-store.ts:6-8（无 compiling 态，见 H1 登记） | 有意保留差异（后续批） |

---

## P-books-[bookId]（/books/[bookId]）

参考主体：`参/app/(workspace)/books/BooksRoute.tsx`（1182 行，单路由内 list/creator/spine/reader 四视图，38 行）；当前主体：`现/features/books/BooksRoute.tsx:287-654`（BookWorkspace + ProposalView + SpineView + ReaderLayout + BookSidebar）。分支映射：提案确认=ProposalView；大纲确认=SpineView；就绪/归档阅读=ReaderLayout（+`/pages/[pageId]` 由 PageReader 渲染，非独立审计条目）；无效 id=现 316-329；读取失败=error banner；「编译中」分支当前不存在（本地状态机无该态，现 books-store.ts:6-8）→ 有意保留差异（后续批 H1）。

### 信息结构（逐分支）
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| 1 | 侧栏（BookSidebar）在 list 以外所有视图常驻（creator/spine/reader 均渲染） | 参 BooksRoute.tsx:956-970 | 现 BooksRoute.tsx:341-381（ProposalView/SpineView 无侧栏，仅 ReaderLayout:600-604 有） | 结构不同 |
| 2 | 视图顶部固定高度活动条 BookGenerationActivity（46px，单行） | 参 BooksRoute.tsx:980-997；参 BookGenerationActivity.tsx:32-56、164-224 | 现 无对应（编译/流式属 H1） | 有意保留差异（后续批） |
| 3 | Suspense 加载边界 + 「Loading…」spin | 参 BooksRoute.tsx:74-84 | 现 BooksRoute.tsx:331-339（「正在读取书籍…」banner） | 结构不同 |
| 4 | 创建表单（creator）：intent textarea(5行,示例占位) + 知识源四标签页 KB/Notebooks/Questions/Chats（带计数徽标、树形/扁平选择、懒加载子项）+ 语言 12 项下拉 + Depth 三段选择（aria-pressed+title 提示）+ 摘要 chips + 可折叠表头（折叠后显 intent 摘要与来源 chips） | 参 BookCreator.tsx:460-520（折叠头）、524-537（intent）、539-591（tabs）、593-763（列表）、766-806（语言/深度）、186-201（提案到达自动收起） | 现 BooksRoute.tsx:228-285（仅书名+简介两输入框的 Modal） | 缺失（知识源选择依赖目录数据，本地仅知识库/笔记本可模拟；题库/会话目录不存在）→ 待队长裁定实现深度 |
| 5 | 提案确认分支：提案卡可编辑（Title/Description/Scope/Target level/Estimated chapters 数字输入 min2 max12）+「Knowledge bases used」chip 组 + 保存前 KB 回显（savedKbs） | 参 BookCreator.tsx:824-857（确认卡）、1150-1249（ProposalForm）、1159-1164（savedKbs 回显） | 现 BooksRoute.tsx:414-433（只读：angle/audience/章节列表+「模拟提案」chip） | 缺失（可先做只读结构对齐：字段分组/标题/说明行） |
| 6 | 提案确认按钮「Confirm proposal & build spine」+ confirmLoading spinner + disabled | 参 BookCreator.tsx:842-855；参 BooksRoute.tsx:540-556（confirmingProposal 状态） | 现 BooksRoute.tsx:434-444（无 busy/disabled；confirmProposal 为同步模拟 现 services/books-store.ts） | 缺失 |
| 7 | 大纲确认分支：SpineEditor 独立编辑器（key=book_id:version 重挂载、loading=confirmingSpine、depth/initialBlockTypes 传入） | 参 BooksRoute.tsx:1023-1040、558-588 | 现 BooksRoute.tsx:450-512（SpineView 只读章节列表 +「每章 2 页（模拟）」chip + 确认按钮） | 结构不同（编辑器完整对齐依赖 H1 能力，登记） |
| 8 | spine 数据未就绪态「Loading spine…」+ spin | 参 BooksRoute.tsx:1150-1154 | 现 无（spine_ready 即有章节列表，本地同步数据无加载窗口）[推断] | 缺失 |
| 9 | 阅读分支侧栏头部：书名 line-clamp-2 + 状态·章数小字 | 参 BookSidebar.tsx:151-164 | 现 BooksRoute.tsx:609-654（侧栏直接列章节，无头部） | 缺失 |
| 10 | 侧栏折叠态（14px 图标列，页码按钮，active 高亮）与展开/收起按钮 | 参 BookSidebar.tsx:88-131、142-148 | 现 无折叠能力 | 缺失 |
| 11 | 侧栏内 Export Markdown 链接（download 属性直链） | 参 BookSidebar.tsx:166-175 | 现 BooksRoute.tsx:552-569（页头按钮 + Blob 下载） | 结构不同（功能等价，位置/实现不同） |
| 12 | 侧栏 Rebuild 两击确认 + 3.5s 自动解除 + rebuilding 禁用 + 后果说明文案 | 参 BookSidebar.tsx:176-219 | 现 BooksRoute.tsx:570-579（页头按钮 + window.confirm「重建书籍…清空阅读进度」） | 结构不同（文案语义已对齐：均声明清空进度） |
| 13 | 侧栏页行：书签=1.5px 圆点（title Bookmarked）、状态=ActivityMark 12px 活动（generating 时动画）、已读 ready 页点变暗 opacity-45、tooltip 状态词 | 参 BookSidebar.tsx:255-284 | 现 BooksRoute.tsx:617-647（书签=「签」amber chip、已读=实心圆点/未读空心+整行 opacity 0.75、无状态标——本地无 generating） | 结构不同 |
| 14 | 侧栏空态「Pages will appear here once the spine is confirmed.」 | 参 BookSidebar.tsx:222-225 | 现 无（ready 书必有页）[推断] | 缺失 |
| 15 | Health/漂移横幅（BookHealthBanner：源未覆盖/生成失败原因/kb 漂移/日志问题/Mark as seen 两段确认）与共享书说明横幅 | 参 BooksRoute.tsx:1051-1076；参 BookHealthBanner.tsx:184-366 | 现 无（生成健康体系属 H1；共享书概念本地不存在） | 有意保留差异（后续批） |
| 16 | Chat 浮动按钮 + BookChatPanel | 参 BooksRoute.tsx:1158-1177 | 现 无 | 有意保留差异（后续批，任务卡明确排除） |
| 17 | 阅读进度呈现：参考经 book.progress（visited/bookmarked 集合驱动侧栏）；页头无进度文本 | 参 BooksRoute.tsx:966-968 | 现 BooksRoute.tsx:583-591（页头「阅读进度 x% · 已读 n/m 页」+ 归档 chip） | 结构不同（当前为本地仓储形态，信息等价） |
| 18 | 无效页码分支（PageReader 前）：当前独立处理 | 参 BooksRoute.tsx:419-424（requested→resumed→firstReady 兜底选页，无独立 404 视图） | 现 BooksRoute.tsx:529-542（「章节页不存在或已被重建」空态 + 返回首页） | 结构不同（当前显式 404，参考静默兜底；e2e 依赖现行为 books-courses.spec.ts:86-89，保留现状） |
| 19 | 无效书籍 id 分支：参考对不存在书仅 guard toast（未见 404 视图） | 参 BooksRoute.tsx:148-173、384-428 [未验证——未逐行追 detail 拉取失败后的 UI] | 现 BooksRoute.tsx:316-329（「书籍不存在」空态 + 返回） | 结构不同（当前超出参考，属本地仓储特性） |
| 20 | Block 层 hover 工具条（上移/下移/换类型/编辑/重新生成/删除两击，opacity-0→group-hover）与 bridge_text 段 | 参 blocks/BlockRenderer.tsx:263-366 | 现 PageReader.tsx:107-321（无编辑工具条；交互/动画/图形块为显式模拟占位 现 273-281） | 有意保留差异（块编辑/再生成依赖生成管线，属 H1；PageReader 本身非本批四条目） |

### 交互状态
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| 1 | 创建/确认提案/确认大纲按钮 busy+disabled（含 409 冲突自动恢复 revision 后重试） | 参 BooksRoute.tsx:540-556、558-588、143-173 | 现 BooksRoute.tsx:434-444、498-508（同步模拟无异步窗口；失败经 notice 文案提示） | 缺失 |
| 2 | 侧栏折叠/展开按钮 title + hover | 参 BookSidebar.tsx:91-104、136-148 | 现 无 | 缺失 |
| 3 | Rebuild 失焦自动解除武装（onBlur） | 参 BookSidebar.tsx:192 | 现 无（window.confirm 阻塞式） | 缺失 |
| 4 | 409/操作失败 toast（notify tone error 8s） | 参 BooksRoute.tsx:148-173、463-498 | 现 BooksRoute.tsx:344-350 等（页面内 error banner） | 结构不同（本地模拟无网络错误面） |
| 5 | 键盘翻页 ←/→ 与深链续读 | 参 BooksRoute.tsx:344-353、417-424 | 现 PageReader.tsx:34-44、现 BooksRoute.tsx:309-314（已实现） | 无差距（登记为已有实现） |
| 6 | 列表页删除书后的选中态清理与路由 replace | 参 BooksRoute.tsx:450-461 | 现 独立实现（deleteBook 同步 现 services/books-store.ts） | 无差距级别 [推断] |

### 动画
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| 1 | 活动层入场 `dt-detail-in`（180ms cubic-bezier(0.16,1,0.3,1)，含与 -translate-x 居中冲突的处理注释） | 参 BookGenerationActivity.tsx:226-241；参 app/globals.css:711-724 | 现 无（活动条属 H1；当前无任何入场动画类） | 有意保留差异（后续批） |
| 2 | 侧栏/按钮 `transition-colors hover:bg-[var(--muted)]/40` 系 | 参 BookSidebar.tsx:94、101、138、145、170、197 | 现 `.space-back` hover 仅变色无过渡（现 space.css:30-45）；button 全局 0.15s 过渡（现 globals.css:96-101） | 缺失（低强度） |
| 3 | Loader2 `animate-spin`（生成/确认中） | 参 BooksRoute.tsx:78、1152；参 BookCreator.tsx:813 | 现 `.space-spin`（space.css:726-734）已定义但本四页未使用 | 缺失 |
| 4 | 参考无明确针对本页其它进出场动画来源（dt-pop-in 等用于 chat/modal 层） | 参 app/globals.css:674-686 | — | 参考无明确动画来源，不新增 |

---

## P-courses（/courses）

参考主体：`参/components/courses/CoursesShelf.tsx`（267 行）+ `参/app/(utility)/courses/page.tsx`（15 行，页 = 组件本身，无第二标题）+ `参/app/(utility)/courses/layout.tsx`（19 行，max-w-5xl 容器）。当前主体：`现/features/courses/CoursesShelf.tsx`（255 行）+ `现/app/courses/page.tsx`。

### 信息结构
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| 1 | 页头为 serif 22px h1「My courses」+ 副句，section aria-labelledby；页面无第二标题 | 参 CoursesShelf.tsx:113-126；参 app/(utility)/courses/page.tsx:12-14 | 现 CoursesShelf.tsx:58-82（space-header h1「课程」+ 工具按钮 + 说明行——说明为如实标注「大纲进度由学员手动勾选」） | 文案不同 / 结构不同 |
| 2 | 新建入口=网格末格虚线按钮卡（min-h-32 与卡片同高；空库时图标 BookOpen+「Create your first course」+ 引导句，否则 Plus+「New course」+ 副句） | 参 CoursesShelf.tsx:195-219、30-33（设计注释） | 现 CoursesShelf.tsx:73-76（页头「新建课程」按钮）+ 127-135（Modal 表单） | 结构不同 [与现有e2e冲突风险→摘要#6] |
| 3 | 卡片=整卡 Link（href 直达），色点+serif 名(truncate)+ArrowRight；描述 line-clamp-2；页脚：空资源「Nothing attached yet」/资料数(Layers)+会话数(MessagesSquare)+最近活跃相对时间(ml-auto) | 参 CoursesShelf.tsx:140-192、19-33（计数来源注释） | 现 CoursesShelf.tsx:141-173（chips：大纲 x/y、资料 n、「本地目录」；无会话数/时间——会话未接入） | 结构不同 / 文案不同 [会话数/时间为有意保留差异] |
| 4 | 加载骨架=3 张 h-32 animate-pulse 卡片 | 参 CoursesShelf.tsx:128-136 | 现 CoursesShelf.tsx:95-99（2 张 76px .space-skeleton） | 结构不同（动画等价） |
| 5 | 空库无独立空态块（末格「Create your first course」即空态） | 参 CoursesShelf.tsx:201-218 | 现 CoursesShelf.tsx:101-105（「还没有进行中的课程」空态块） | 结构不同 |
| 6 | 归档折叠区=details/summary「Archived courses」+计数，内为紧凑行列表（色点 opacity-60 + 名 truncate + archived_at 相对时间） | 参 CoursesShelf.tsx:223-257 | 现 CoursesShelf.tsx:114-125（完整卡片网格复用 + 卡片 opacity 0.7 现 144） | 结构不同 [与现有e2e冲突风险→摘要#7] |
| 7 | 新建对话框字段：name(60)/description(300)/颜色 8 色板/默认 Mode 下拉(Chat/Course Study/Guided Solving/Quiz)/Persona(80)/错误 role=alert/按钮 busy「Saving...」 | 参 CourseDialog.tsx:29-34、97-221；参 lib/courses-api.ts:121+ DEFAULT_COURSE_COLORS（8 个 hex） | 现 CoursesShelf.tsx:175-254（name/description/颜色 5 色 CourseColor 现 services/courses-store.ts:14,50）；无 Mode/Persona（会话体系未接入）；有 error alert 现 238-242 | 部分缺失；Mode/Persona=有意保留差异（后续批）；色板数量 5 vs 8=结构不同 |
| 8 | 课程数据双请求（courses+sessions）聚合会话计数与最近活跃 | 参 CoursesShelf.tsx:41-96 | 现 本地订阅 readCourses/subscribeCourses 现 CoursesShelf.tsx:29-43 | 有意保留差异（会话未接入） |

### 交互状态
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| 1 | 卡片 hover 抬升+描边+阴影+focus-visible ring（整卡 Link） | 参 CoursesShelf.tsx:143 | 现 CoursesShelf.tsx:145-153（Link 无样式）；space.css:618-627 无 hover | 缺失 |
| 2 | 新建卡 hover：border/bg 变化（dashed→实色底） | 参 CoursesShelf.tsx:198 | 现 无（页头按钮 hover 仅边框 现 space.css:366-368） | 缺失 |
| 3 | 归档 summary hover 变色 transition-colors | 参 CoursesShelf.tsx:225 | 现 CoursesShelf.tsx:116（cursor:pointer inline，无 hover 色） | 缺失 |
| 4 | 加载/失败态 | 参 CoursesShelf.tsx:128-136（loading；失败随 Promise.all 静默为空 [未验证——参考无显式错误 UI]） | 现 CoursesShelf.tsx:84-93（notice + error banner，本地容错更完整） | 结构不同（当前超出参考） |

### 动画
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| 1 | 卡片 `transition-all duration-150 hover:-translate-y-0.5 hover:border-[var(--foreground)]/20 hover:shadow-[0_6px_20px_-12px_rgba(0,0,0,0.25)]` | 参 CoursesShelf.tsx:143 | 现 无对应（shadow 值与现 globals.css:45 --shadow-card 相同，可复用变量） | 缺失 |
| 2 | ArrowRight `transition-transform group-hover:translate-x-0.5` | 参 CoursesShelf.tsx:154-157 | 现 无 ArrowRight | 缺失 |
| 3 | 骨架 `animate-pulse` | 参 CoursesShelf.tsx:133 | 现 space.css:282-290（space-pulse 1.4s 等价实现） | 无差距 |

---

## P-courses-[courseId]（/courses/[courseId]）

参考主体：`参/app/(utility)/courses/[courseId]/page.tsx`（424 行）+ `参/components/courses/`{CourseNextStep 187、CourseProgress 167、CourseSyllabus 248、CourseResources 314、CourseConventions 110、CourseDialog 224、CourseScope 142、OrganizedSessionList 694}。当前主体：`现/features/courses/CourseDetail.tsx`（574 行）。

### 信息结构
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| 1 | 页头=rounded-2xl 卡（color 点+serif 28px 名+Archived pill+描述+活跃会话计数）+ 右侧动作区 | 参 [courseId]/page.tsx:223-245 | 现 CourseDetail.tsx:113-167（开放式 space-header，无卡片容器、无会话计数） | 结构不同（会话计数=有意保留差异） |
| 2 | 「Start course study」主按钮（bg foreground）+ MoreHorizontal 菜单（aria-label「Course actions」/aria-haspopup/aria-expanded；内含 New course chat/Edit/Archive-Restore/Delete） | 参 [courseId]/page.tsx:246-314 | 现 CourseDetail.tsx:119-145（平铺 编辑/归档/删除 三按钮；Start course study 无——会话未接入，页内 banner 现 169-172 声明） | 结构不同；Start course study/新会话项=有意保留差异（后续批）[与现有e2e冲突风险→按钮名「归档」exact 断言 books-courses.spec.ts:168] |
| 3 | CourseNextStep 面板（Signpost 图标+headline/detail+行动按钮，决策链：无资源→最弱类→停滞路径→未读完阅读→材料就绪） | 参 CourseNextStep.tsx:136-187、37-134 | 现 无对应区块 | 有意保留差异（聚合数据未接入）；「空态壳可先渲染」待队长裁定 |
| 4 | CourseProgress 四磁贴（Mastery Path/Question Bank/Immersive Reading/Notebooks：值+detail+空态文案） | 参 CourseProgress.tsx:61-134 | 现 无对应区块（页内 banner 现 169-172 声明聚合进度未接入） | 有意保留差异（待裁定是否做空态壳） |
| 5 | 大纲区：h2「Syllabus」+「x/y units covered」副句+Edit/Add 按钮+progressbar(role=progressbar, aria-valuenow/min/max)填充条 | 参 CourseSyllabus.tsx:113-155 | 现 CourseDetail.tsx:185-206（汇总并入 h2 文本「大纲（x/y 已完成，下一单元…）」，无进度条/无 aria） | 结构不同 [与现有e2e冲突风险→摘要#9] |
| 6 | 大纲编辑器：mono 字体 textarea 8 行 resize-y + 格式示例 placeholder + Save/Saving + 保存重建大纲保留已存在单元 id（covered 继承） | 参 CourseSyllabus.tsx:27-64、157-178 | 现 CourseDetail.tsx:207-235（footnote 格式说明 + .space-search 复用为 textarea + 保存大纲/取消；无 Saving；保存重置 covered 现语义一致 现 services/courses-store.ts:198-210） | 结构不同 / 文案不同 |
| 7 | 单元行：位置编号(position+1.)、sr-only checkbox+自绘 16px 勾选框（covered 实心+Check 图标）、covered line-through、topics 单行「 · 」join truncate、「N wrong」证据徽标(title 提示)、下一单元行 bg 高亮 | 参 CourseSyllabus.tsx:186-245 | 现 CourseDetail.tsx:242-268（原生可见 checkbox、无编号、covered opacity 0.7、topics 为独立 chips 换行、无 wrong 徽标[题库未接入]、下一单元=「下一单元」chip） | 结构不同 [与现有e2e冲突风险→摘要#10] |
| 8 | 大纲空态：「Paste the course outline…」dashed 提示 | 参 CourseSyllabus.tsx:179-184 | 现 CourseDetail.tsx:236-241（「还没有大纲」space-empty） | 文案不同 |
| 9 | 资料区：h2「Materials」+副句+Add 切换按钮；行=kind 图标+label truncate+「· Unavailable」(title 提示)+右侧 kind 名+移除钮(hover/focus 显隐)；空态 dashed 文案 | 参 CourseResources.tsx:160-235 | 现 CourseDetail.tsx:274-335（kind=chip、不可用/未知并入标题 span、移除钮常驻 icon-button、空态 space-empty） | 结构不同 [与现有e2e冲突风险→摘要#11] |
| 10 | 附加面板=页内展开区（Add 再点收起）：候选按 kind 分组、已附加「✓ label」disabled、候选钮 max-w-[220px] truncate、底部「Start something new」创建链接组（带 ?course=） | 参 CourseResources.tsx:238-311、69-94 | 现 CourseDetail.tsx:477-573（Modal「附加课程资料」+分组列表+「附加/已附加」按钮）+ 现 336-340（页脚「新建关联设施」静态链接） | 结构不同（?course= 带参=有意保留差异）；[与现有e2e冲突风险→摘要#12] |
| 11 | 附加面板空态与目录失败态分离（面板内 Loading/空/错误三态，目录失败不阻断已附加列表） | 参 CourseResources.tsx:118-133、240-252 | 现 CourseDetail.tsx:491-519（同型三态，R-11 已实现且断言固定） | 无差距（登记已有实现） |
| 12 | 学习约定：内联 textarea（rows3,maxLength4000,blur 保存）+ dirty 才显 Save + Saved 2s 指示 + agentNotes 折叠区「What DeepTutor has noticed」 | 参 CourseConventions.tsx:55-108 | 现 CourseDetail.tsx:344-353（只读段落）+ 421-427（编辑弹窗内 textarea，无 dirty/Saved） | 结构不同；agentNotes=有意保留差异（course_edit 写入链路属会话体系） |
| 13 | 删除确认=ConfirmDialog（标题/确认钮 tone danger/正文「Conversations will not be deleted…」） | 参 [courseId]/page.tsx:407-420 | 现 CourseDetail.tsx:133-141（window.confirm「仅移除本地目录登记」） | 结构不同（文案语义已本地化如实声明） |
| 14 | 加载态=aria-label「Loading course」+两块 animate-pulse 骨架 | 参 [courseId]/page.tsx:178-185 | 现 CourseDetail.tsx:93-101（「正在读取课程…」banner） | 结构不同 |
| 15 | 未找到态=BookOpen 图标+h1「Course not found」+返回链接 | 参 [courseId]/page.tsx:187-202 | 现 CourseDetail.tsx:78-91（space-empty「课程不存在或已被删除」+返回） | 结构不同（信息等价） |
| 16 | Conversations 区+归档会话折叠区+OrganizedSessionList | 参 [courseId]/page.tsx:349-393 | 现 无（页内 banner 现 169-172 声明） | 有意保留差异（任务卡明确排除） |
| 17 | 编辑对话框含 Mode/Persona 字段与 busy「Saving...」 | 参 CourseDialog.tsx:149-221 | 现 CourseDetail.tsx:383-468（name/description/instructions/color；无 busy） | 部分缺失；Mode/Persona=有意保留差异 |
| 18 | 目录快照容错（R-11：快照集中读取+失败重试+unknown 三态） | 参 无对应（参考走后端 API） | 现 CourseDetail.tsx:46-71、104-109、284-293（本项目特性，e2e 已固化） | 有意保留差异（本地容错超出参考，保留） |

### 交互状态
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| 1 | 菜单按钮 aria-haspopup/aria-expanded 状态 | 参 [courseId]/page.tsx:256-263 | 现 CourseDetail.tsx:119-145（平铺按钮，无菜单） | 缺失（随结构 #2 决定） |
| 2 | 移除资料钮 focus-visible 显隐（键盘可达）+ aria-label「Remove from course」 | 参 CourseResources.tsx:224-231 | 现 CourseDetail.tsx:319-330（常驻按钮，aria-label「移除资料 X」——e2e 依赖现文案） | 缺失（hover 显隐可加，aria-label 文案保留） |
| 3 | 大纲/约定/编辑保存按钮 Saving busy + disabled | 参 CourseSyllabus.tsx:169-177；参 CourseConventions.tsx:73-82；参 CourseDialog.tsx:209-219 | 现 CourseDetail.tsx:219-233、458-465（无 busy；本地同步保存无异步窗口 [推断]） | 缺失 |
| 4 | 下一单元行底色高亮（非 chip） | 参 CourseSyllabus.tsx:188-194 | 现 CourseDetail.tsx:255（chip 标注） | 结构不同 |
| 5 | 候选钮 already disabled + ✓ 前缀 | 参 CourseResources.tsx:262-277 | 现 CourseDetail.tsx:534-559（「已附加」文案 disabled） | 文案不同（语义等价） |
| 6 | CourseNextStep going 状态（「Opening」disabled 防死点击） | 参 CourseNextStep.tsx:146-155、173-183 | 现 无 | 有意保留差异 |

### 动画
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| 1 | 返回链接箭头 `transition-transform group-hover:-translate-x-0.5` | 参 [courseId]/page.tsx:211-221 | 现 CourseDetail.tsx:115-118（.space-back 无 transform 过渡 现 space.css:30-45） | 缺失 |
| 2 | 大纲进度条填充 `transition-[width] duration-300` | 参 CourseSyllabus.tsx:150-153 | 现 无进度条；现 books.css:36-41 有同类 `.space-reading-bar-fill transition width 0.2s`（books 专用，courses 不可直接用） | 缺失 |
| 3 | 磁贴/卡片 `transition-all duration-150 hover:-translate-y-0.5 … focus-visible:ring-2` | 参 CourseProgress.tsx:153 | 现 无磁贴（随 #4 裁定） | 有意保留差异 |
| 4 | 颜色钮 `transition-transform hover:scale-105 focus-visible:ring-2 ring-offset-2` | 参 CourseDialog.tsx:130-145 | 现 CourseDetail.tsx:433-451（22px 圆 + inline outline，无 hover 缩放） | 缺失 |
| 5 | 资料行 `hover:bg-[var(--muted)]/40` + 移除钮 `transition-opacity opacity-0 group-hover:opacity-100` | 参 CourseResources.tsx:196、228 | 现 space-session-card 无 hover（现 space.css:399-406）；移除钮常驻 | 缺失 |
| 6 | 会话行 chevron `transition-transform rotate-90` 等列表动画 | 参 OrganizedSessionList.tsx:281-305、573-583 | 现 无（会话区=有意保留差异） | 有意保留差异（后续批） |
| 7 | Modal 进出场（参考 Modal 组件内部实现） | 参 CourseDialog.tsx:88-96（Modal 用法）[未验证——未读参 Modal 源码，无法确认动画类] | 现 components/ui/Modal（现 项目内组件）[未验证] | [未验证] 双方 Modal 动画均未核对，登记待查 |

---

## 附录 A：样式文件归属与影响面

### books.css 现有类清单与使用方（现 features/books/books.css，91 行）
| 类名 | 行号 | 使用方 |
|---|---|---|
| `.books-layout`（grid 240px+1fr；≤900px 单列） | 2-13 | 现 BooksRoute.tsx:600 |
| `.books-rail`（sticky top16 + max-height + overflow-y） | 15-20 | 现 BooksRoute.tsx:611（叠加在 .space-scope-rail 上） |
| `.space-card-link`（block 化链接；注意 space-* 前缀却定义在 books.css） | 22-26 | 现 BooksRoute.tsx:165、现 CoursesShelf.tsx:145（跨模块共用） |
| `.space-reading-bar` / `.space-reading-bar-fill`（width .2s 过渡） | 28-41 | 现 BooksRoute.tsx:177-179 |
| `.books-reader` | 43-48 | 现 PageReader.tsx:50 |
| `.books-block` | 50-52 | 现 PageReader.tsx:122、129、136、145、173、192、218、233、251、259、273、315 |
| `.books-block-callout` | 54-59 | 现 PageReader.tsx:138 |
| `.books-quiz-option`(+.correct/.wrong) | 61-81 | 现 PageReader.tsx:294 |
| `.books-reader-footer` | 83-91 | 现 PageReader.tsx:78 |
| `.books-code`（**在 TSX 引用但 CSS 未定义**，样式全靠 inline） | — | 现 PageReader.tsx:167 `className="books-code"` |

- 导入点：现 BooksRoute.tsx:21-22（space.css + books.css）、现 PageReader.tsx:15（books.css）。参考侧 books 无独立 css（全部 Tailwind 原子类）。
- 影响面结论：扩 books.css 只影响 BooksRoute/PageReader 两文件；`.space-card-link` 被 courses 复用，改动它会影响 CoursesShelf。

### courses 无独立 CSS 的现状
- 现 CoursesShelf.tsx:19、现 CourseDetail.tsx:33 均 `import '@/features/space/styles/space.css'`；无 courses.css。
- 若新增 `features/courses/courses.css`：使用方仅 CoursesShelf.tsx 与 CourseDetail.tsx 两文件（已核对全仓库引用 `features/courses` 的组件只有这两个 + 两个 page.tsx 路由文件）。新文件应只含新类名，**不得搬移/重定义 space.css 既有 space-* 类**（space.css 被 /space 系列页面共用，改公共类会波及教案外其它页面——e2e books-courses.spec.ts:16-17 也直接依赖 .space-page）。
- 若选择扩 books.css 放共享卡片样式：会把 courses 的依赖引进 books 模块文件，属反向耦合，不建议；共享卡片 hover 更适合落在 space.css 新增类或各模块自己的 css。

### 现有可复用点
- 现 globals.css 变量层：--font-display/--blue/--blue-soft/--green/--danger/--radius-*/--shadow-card（45 行，值与参考 hover shadow 完全一致）/--space-*。
- 现 space.css 已有等价物：hover 抬升范式（.space-tile 96-106，未接线到卡片）、pulse 动画（282-290）、spin（726-734）、banner/chip 三色调（331-347）、focus-visible 全局 outline（现 globals.css:88-95）。
- 现 books.css `.space-reading-bar-fill` 的 width 过渡可直接作为 courses 大纲进度条的样式蓝本（复制到 courses 侧或抽公共类，不改 books 现有断言语义）。

## 附录 B：现有 e2e 断言的用户可见行为清单（必须保持）

### tests/e2e/books-courses.spec.ts（196 行，6 test）
| 行 | 断言的用户可见行为 |
|---|---|
| 13 | /books 有 heading「书籍」 |
| 14 | 空库文本「还没有书籍」 |
| 16-17 | `.space-page` 存在且 display:flex |
| 19-20 | 按钮「载入演示数据」→ role=status 含「已载入演示书籍」 |
| 21-25 | `.space-persona-card` 含「分数入门（演示书籍）」「修辞手法小册（演示草稿）」，共 2 张且重复载入仍 2 |
| 28 | role=note 含「共 2 本」 |
| 29-31 | 卡内 `.space-chip` 含「可阅读」 |
| 32-34 | 卡内按钮「继续阅读」 |
| 37-45 | 按钮「新建书籍」→ dialog「新建书籍」→ label「书名」「简介」→ 按钮「创建（生成模拟提案）」→ URL /books/bk- → heading 书名 → 「提案（模拟）」→ 「模拟提案：本地模板生成」 |
| 51-56 | 卡内按钮「继续创建」→ URL demo-book-draft → 「提案（模拟）」 |
| 58-61 | 按钮「确认提案（进入大纲）」→ status「已确认提案」→ 「章节大纲（4 章）」→ 「1. 比喻是什么」 |
| 63-67 | 按钮「确认大纲并编译（模拟）」→ URL /pages/ → 「第 1/8 页」→ role=note 含「本地模拟编译产物」 |
| 74-76 | link「打开书籍 分数入门（演示书籍）」→ URL …p0 → 「已读 1/4 页」 |
| 79-83 | 按钮「添加书签」→「移除书签」；侧栏（aria-label 章节目录）内「签」×2；ArrowRight → p1 |
| 86-89 | 无效页码 → 「章节页不存在或已被重建」→ link「返回书籍首页」 |
| 92-97 | 「重建书籍」+原生 dialog accept → 「章节页不存在或已被重建」→ 「已读 1/4 页」 |
| 100-107 | 「导出 Markdown」→ 下载文件名「分数入门（演示书籍）.md」→ 内容含 `# 分数入门（演示书籍）` → status「已导出「…」」 |
| 113-119 | 练习块：按钮「A. 理解本页概念并能举例」→ status「回答正确。」；「B. 背诵全文」→「回答错误，正确答案 A。」 |
| 124-128 | /courses heading「课程」；「载入演示数据」→ status「已载入演示课程」；卡「七年级数学（演示课程）」；「已归档课程（1）」 |
| 130-136 | link「打开课程 七年级数学（演示课程）」→ URL demo-course-math → role=note 含「课程学习会话未接入」→ 「大纲（1/2 已完成，下一单元：一元一次方程）」→ 「课程标准库（不可用：目标已删除或未载入）」 |
| 139-140 | checkbox「标记「一元一次方程」为已完成」→ 「大纲（2/2 已完成，全部完成）」 |
| 143-152 | 「附加资料」→ dialog「附加课程资料」→ heading「笔记本」→ 卡「学习笔记」内按钮「附加」→ status「已附加资料「学习笔记」」→ link 学习笔记 href=/notebooks/notebook-main |
| 155-159 | 「编辑大纲」→ label「大纲文本」fill → 「保存大纲」→ status「已保存大纲」→ 「大纲（0/1 已完成，下一单元：新单元甲）」 |
| 162-165 | 按钮「移除资料 学习笔记」→ status「已移除资料「学习笔记」」→ link 消失；不可用态仍在 |
| 168-174 | 按钮「归档」exact → status「已归档课程」→ link「返回课程列表」→ 「已归档课程（2）」可点击展开 → 卡可见 |
| 179-186 | 「新建课程」→ dialog「新建课程」→ label「名称」「简介」→ 按钮「创建」→ URL /courses/cs- → heading → 「还没有大纲」 |
| 190-195 | /papers 壳内按钮「书籍」×1、「课程」×0（导航显隐） |

### tests/e2e/course-resource-faults.spec.ts（217 行，R-11）
| 行 | 断言的用户可见行为 |
|---|---|
| 52-56 | heading「容错课程」、文本「学习约定文本」、checkbox「标记「单元一」为已完成」、heading `/^大纲（/` |
| 72-73 | 「资源目录读取失败」文本 + 按钮「重试」 |
| 75-76 | 「课程标准库（目录读取失败，暂无法确认）」出现；「目标已删除」×0 |
| 80-81 | 课程 localStorage 逐字节不变 |
| 99-101 | 存储被拒场景同样显示错误且不覆盖 |
| 108-109 | 空目录 → 「课程标准库（不可用：目标已删除或未载入）」；错误文本 ×0 |
| 115-131 | 重试仍失败→错误仍在；修复数据→重试→ link「课程标准库」出现 |
| 145-148 | dialog「附加课程资料」内「资源目录读取失败」+「重试」 |
| 157-159 | `li.space-session-card` 内按钮「附加」→「已附加资料」 |
| 161-169 | 知识库详情链接 href 可见/消失 |
| 196-200 | 故障目录不冒充空：`section.space-group` 含「知识库」×0，书籍候选「容错书籍」仍可见 |
| 203-215 | 390×844：正文完整、错误+重试可见、.app-shell、「打开功能导航」、「返回课程列表」、`scrollWidth <= innerWidth` |

---

## 范围矛盾与待队长决定事项汇总
1. **「编译中」分支**：任务卡在 P-books-[bookId] 审计分支中列出「编译中」，但严禁纳入清单排除 compiling/paused/error 状态机——本清单按后者处理（登记为有意保留差异，见该页 #2/#15），请队长确认口径。
2. **BookCreator 知识源标签页（KB/Notebooks/Questions/Chats）**：属提案创建的信息结构（未列入排除清单），但 Questions/Chats 目录在目标项目不存在；本地可模拟 KB/Notebooks 两页签。做完整四页签、两页签、还是整体留待 H1——待裁定（本清单标记为待裁定，不给验收结论）。
3. **CourseNextStep / CourseProgress「空态壳」**：两者依赖 CourseState 聚合（掌握/题库/阅读），当前页内 banner 已如实声明未接入；是否先渲染带空态文案的磁贴/面板（参考 CourseProgress.tsx:88、104、119、130 的空态文案本身就是“怎么补内容”的指引）——待裁定。
4. **CourseDialog Mode/Persona 字段**：属于“对话以何种模式开始”，与会话体系强相关（H1）；但作为表单字段可先行落库。待裁定。
5. **单元「N wrong」证据徽标 / 会话计数 / 最近活跃时间**：同属聚合数据，本批只登记不实现。
6. **e2e 改动权**：摘要表 13 条冲突中 #1/#2/#6/#7/#9/#12 涉及「改实现 vs 同步改 spec」的取舍，裁定归队长；其余标注「可安全实现」的条目不动任何既有断言。
7. **[未验证] 项清单**：参考侧对不存在书籍 id 的 404 UI（P-books-[bookId] #19）；参考 Modal 组件的进出场动画（P-courses-[courseId] 动画 #7）；当前 e2e 在 HEAD 的通过状态（本任务只读、未运行测试）。
8. **窄视口最优先疑似缺陷**：`.books-rail` ≤900px 单列下 sticky 未解除（现 books.css:15-20 vs 现 space.css:741-747 的姊妹类处理）——建议列为有界实现卡的第一项，修复时注意 books-courses.spec.ts:81 依赖 aria-label「章节目录」。
