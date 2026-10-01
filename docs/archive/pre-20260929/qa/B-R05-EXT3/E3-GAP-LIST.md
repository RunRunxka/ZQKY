# B-R05-EXT3-E3 逐页差距清单（v1）

- 核对时间：2026-09-19
- 参考仓库：`F:\DeepTutor`，`git rev-parse HEAD` = `42fab3cf429a1fbf36b257ab8d116a3814964202`（已核实，工作区干净）；中文文案对照 `web/locales/zh/app.json` 同提交。
- 当前仓库 HEAD：`1aad54beacf40ba2d36e82859e6296cb4aed7eff`（`docs: B-R05-EXT3 v2 收口`）。
- 审计范围声明：本清单只覆盖 /co-writer、/co-writer/[docId]、/reading、/reading/materials 四个库级页面的信息结构 / 交互状态 / 动画三类差距；`ReadingWorkspace.tsx` 与 `reading.css` 为禁区（仅附录 A 记录影响面）；DOCX 导入、真实解析/转录、真实 AI 通道、split-pane 分栏、同步滚动等登记为「有意保留差异（后续批）」。全程只读，未运行 build/dev/e2e/单测，未做 git 写操作。

证据约定：参考路径简写 `R:`（F:\DeepTutor\web\...），当前路径简写 `C:`（H:\备份xuexi\智启课源\...）。无双行号证据的条目不写。

---

## 摘要

### 四页各自最值得做的 3~5 条

**P-co-writer（/co-writer）**
1. 卡片网格化 + 内容预览：参考 1/2/3 列自适应网格（R:app/(workspace)/co-writer/page.tsx:246），卡片带 `line-clamp-4` 正文预览（R:page.tsx:312-314）；当前为垂直列表无预览（C:WritingLibrary.tsx:70-99）。
2. 相对时间显示：参考 `relativeTime`（1m/3h/2d…，R:page.tsx:17-31、277-280）；当前绝对时间 `toLocaleString`（C:WritingLibrary.tsx:95）。
3. 空态图标块 + 空态内联按钮组：参考 PenLine 30px 图标 + 双行文案 + 三按钮（R:page.tsx:117-168）；当前 `space-empty` 纯文字无图标无按钮（C:WritingLibrary.tsx:64-68）。
4. 卡片键盘可达 + hover 边框过渡：参考 `role="button" tabIndex={0}` Enter/Space（R:page.tsx:253-261）+ `transition-colors hover:border-[var(--ring)]`（R:page.tsx:262）；当前 Link 可聚焦但卡片无 hover 过渡（C:WritingLibrary.tsx:75；space.css:399-406 无 transition）。
5. 错误横幅带 rose 语义色（R:page.tsx:232-236）——当前 `space-banner error` 已有等价物（C:WritingLibrary.tsx:55-59），差距仅在视觉细节，可不动。

**P-co-writer-[docId]（/co-writer/[docId]）**
1. 顶栏信息架构：参考「返回 + 面包屑 + 可双击改名标题 + 字数/字符统计 + 保存状态 + 5 个工具按钮（清空/导出 MD/导出 Word/存笔记本/载入模板）+ Full Draft 主按钮」（R:CoWriterWorkspace.tsx:1673-1794）；当前标题在 h1、工具仅撤销/版本/AI 生成（C:WritingEditor.tsx:194-228）。
2. 保存状态语义：参考 `Saving…`/`Saved` 双态 + spinner（R:CoWriterWorkspace.tsx:1728-1737）——当前已有等价 chip「保存中…/已保存」（C:WritingEditor.tsx:222-224），**e2e 断言「已保存」exact，文案必须逐字保留**。
3. 字数统计：参考 CJK+拉丁分词计数（R:CoWriterWorkspace.tsx:532-544）；当前 `content.length` 字符数（C:WritingEditor.tsx:225）——口径不同非缺陷，可列为低优先。
4. 状态栏底条：参考 error/status 红绿底条（R:CoWriterWorkspace.tsx:2224-2234）；当前错误只在 AI 预览 Modal 内展示（C:WritingEditor.tsx:296-304），编辑器级错误（存储失败 saveState error）只有 chip。
5. 按钮动效：参考主按钮 `transition-[opacity,transform] duration-150 hover:opacity-90 active:scale-[0.97]`（R:CoWriterWorkspace.tsx:1788）；当前 `space-button` 无任何 transition（space.css:355-378）。

**P-reading（/reading）**
1. LibraryShell 双 tab 信息架构（Collections/Material library 带计数，R:LibraryShell.tsx:96-109、117-145）——当前两页互为孤岛、材料库页无返回集合页入口（C:ReadingLibrary.tsx:52-81；C:MaterialLibrary.tsx:66-94）。**改造有 e2e 冲突风险，见汇总 #5**。
2. 集合行结构：参考「图标块（材料 glyph/解析 spinner）+ serif 标题 + 材料名预览（前 2 个 + `+N more`）+ 相对日期 + hover 菜单删除」（R:ReadingLibrary.tsx:281-359）；当前 persona 卡片（描述 + 材料/会话/本地目录 3 chips + 进入/删除按钮，C:ReadingLibrary.tsx:103-145）。
3. 搜索 + 排序（Recent/Name）：R:ReadingLibrary.tsx:123-162；当前无（无对应 UI）。
4. 解析中/失败材料横幅（进度条 + 百分比 + 重试）：R:ReadingLibrary.tsx:86-95、361-426；当前材料状态只在材料库展示（C:MaterialLibrary.tsx:139-169），集合页无感知。
5. 空态双分支（搜索无结果 vs 真空态引导）：R:ReadingLibrary.tsx:428-462；当前单分支（C:ReadingLibrary.tsx:97-101）。

**P-reading-materials（/reading/materials）**
1. 筛选 chips：参考 4 个（All/Not in a collection/Preparing/Failed，R:MaterialLibrary.tsx:147-171）；当前 2 个 tab（全部/未分配，C:MaterialLibrary.tsx:96-108）——缺 Preparing/Failed 筛选。
2. 行内集合成员 chip（前 2 个集合名可点击 + `+N`，未分配显示虚线「Add to a collection」）：R:MaterialLibrary.tsx:423-455；当前只有「已入 N 个集合」计数 chip（C:MaterialLibrary.tsx:145）。
3. 列表网格化 + 响应式列（材料/Type/In collections/Added，R:MaterialLibrary.tsx:47-50、187-196）；当前单行 chips 堆叠，390px 溢出风险最大（见窄视口清单）。
4. 重试/失败徽标行内化：参考失败行内 Retry 链接 + Failed 徽标（R:MaterialLibrary.tsx:388-392、458-469）；当前已有等价按钮（C:MaterialLibrary.tsx:147-159）——差距仅在呈现位置。
5. 搜索框 + 材料计数：R:MaterialLibrary.tsx:120-145；当前无。

### 全局性发现

1. **写作模块无独立 CSS**：WritingLibrary/WritingEditor 全部复用 `space.css` 类 + 内联 style（C:WritingLibrary.tsx:15 导入 space.css；C:WritingEditor.tsx:235 `style={{ minHeight: 420, ... }}`、:218 内联 transform）。参考全用 Tailwind 原子类。**约束要求不建议改 space.css**，故动画/交互补齐的落地方式只能是：新增模块级 CSS（如 `features/writing/writing.css`，由本模块 import，不动共享层）或组件内 className 组合。此为有界实现卡要定的决策点。
2. **reading.css 是工作区共用禁区，但库级页面当前 import 了它却未使用其任何类**：C:ReadingLibrary.tsx:21、C:MaterialLibrary.tsx:22 均 `import '@/features/reading/reading.css'`，两文件内无 `reading-` 前缀类名（全文核对）；真正的消费方是禁区内的 ReadingWorkspace.tsx（详见附录 A）。**例外：WritingEditor.tsx:306 的 AI 预览借用了 `reading-msg assistant` 类**（C:WritingEditor.tsx:16-17 同时导入 AnswerMarkdown 与 reading.css）——写作页面跨模块依赖阅读工作区样式，若未来任何批次调整 reading.css，写作 AI 预览样式会被连带影响。本批禁改，仅登记。
3. 参考动画基础设施（dt-pop-in / dt-popup-up / fade-in 等关键帧，R:web/app/globals.css:646-811）在当前仓库**无对应物**（C:styles/globals.css 全文无 @keyframes，仅 space.css:274-290 space-pulse 与 :726-734 space-rotate）。若要补进出场动画需新增模块级 CSS，**不得改 globals.css/motion.css/space.css**。
4. 当前 `prefers-reduced-motion` 已全局处理（C:styles/globals.css:587-595 `animation: none !important`），与参考策略（R:globals.css:1094-1110，缩短而非全删）不同；当前更激进，但无害，不列为差距。
5. 参考库级阅读两页共用 `LibraryShell`（R:LibraryShell.tsx:19-115：标题/副标语/主操作按钮/双 tab/计数兜底拉取 40-67）；当前没有 shell 抽象，两页各自写 header——若后续实现 tab，需先决定 shell 归属（单一负责人）。

### 窄视口风险清单（390px）

| 页 | 元素/容器 | 证据 | 风险 | 参考对应处理 |
|---|---|---|---|---|
| /co-writer | `space-session-top`（图标+标题+2 chips+删除钮同行，**无 flex-wrap**） | C:WritingLibrary.tsx:72-93；space.css:408-412（`display:flex` 无 wrap） | 长标题 ellipsis 可缩（space.css:414-423），但「N 字」「N 个版本」chip 不缩，390px 挤压换行错乱 [推断，未运行验证] | 参考卡片纵向布局，标题 `truncate` + 容器 `min-w-0`（R:page.tsx:265-281），操作按钮右上角独立定位（R:page.tsx:283-310） |
| /co-writer | header 三按钮（参考）vs 当前单按钮 | C:WritingLibrary.tsx:41-48 | 当前仅 1 按钮，无风险；若补「模板/导入」按钮需 `flex-wrap`（space-card-actions 已有，space.css:645-650） | 参考按钮组 `shrink-0` + 标题区 `mb-7 flex items-end justify-between gap-4`（R:page.tsx:184-193），窄屏会溢出——参考自身也未处理 [推断] |
| /co-writer/[docId] | header 按钮组 `space-card-actions`（撤销/版本/AI 生成） | C:WritingEditor.tsx:200-213；space.css:645-650 有 wrap | 低风险 | 参考顶栏按钮多，靠 `hidden sm:inline` 隐藏字数/保存状态（R:CoWriterWorkspace.tsx:1725, 1729, 1734） |
| /co-writer/[docId] | 底部操作行 4 按钮（选区改写/润色/扩写/保存版本） | C:WritingEditor.tsx:238-257 | 有 flex-wrap，低风险 | 参考工具栏 `overflow-x-auto`（R:CoWriterWorkspace.tsx:1797） |
| /reading | persona 卡 3 chips + 2 按钮组 | C:ReadingLibrary.tsx:119-141；space.css:645-650 | chips 行（space-meta-row 有 wrap，space.css:310-317）+ 按钮行有 wrap，低风险 | 参考行式布局 `min-w-0 flex-1` + 双 truncate（R:ReadingLibrary.tsx:318-332） |
| /reading/materials | `space-session-top`：图标+标题+**5 个 chip**+最多 4 个操作按钮（重试/取消/分配/删除）同行 | C:MaterialLibrary.tsx:133-184；space.css:408-412 无 wrap | **最高风险**：解析失败+未分配的行同时出现重试/取消/分配/删除 4 按钮与 5 chip，390px 必然溢出 [推断，未运行验证] | 参考 GRID 三档列数（R:MaterialLibrary.tsx:47-50），窄屏隐藏 Type/In collections 列、次要信息收进第二行并 `truncate`（R:MaterialLibrary.tsx:394-414），操作收进 MoreHorizontal 菜单（R:MaterialLibrary.tsx:475-482） |
| 四页通用 | `space-page` padding 24px/20px | space.css:4-11 | 可接受 | 参考容器 `px-6 md:px-9`（R:LibraryShell.tsx:71） |

### e2e 冲突风险汇总

| # | 条目 | 触碰断言 | 倾向建议 |
|---|---|---|---|
| 1 | 列表页「新建文稿」弹窗（标题 label + 模板复选 + 创建按钮） | writing.spec.ts:16-20 | **建议保留现状**：参考是点击即建、无弹窗（R:page.tsx:62-79）；改掉会破坏 dialog/label/`创建` 三层断言。参考式直建可作为追加入口，不动现弹窗 |
| 2 | 列表/材料/集合删除用原生 `window.confirm` | writing.spec.ts:59-60；reading.spec.ts:164-168 | **建议保留现状**：参考为两击确认（R:page.tsx:41,283-310）/自定义 Dialog（R:ReadingLibrary.tsx:464-529）；换掉会破坏 `page.once('dialog')` 断言。两击确认可作为后续批另行评估（需同步改 spec，超出本批） |
| 3 | 「已保存」exact 文案 chip | writing.spec.ts:27, 49 | **建议保留现状**：参考 `Saved`（R:CoWriterWorkspace.tsx:1735），当前中文「已保存」（C:WritingEditor.tsx:223）。任何文案改动需同步 spec |
| 4 | 「撤销修改」「版本历史」「改写前自动快照」「恢复版本」aria-label/文案 | writing.spec.ts:41, 45-48 | **建议保留现状**：参考无版本历史系统（CoWriterWorkspace 全文无 versions 概念，仅 undo/redo 栈 R:258-261）；当前版本能力是超出参考的本地增强，不是差距，不能为对齐参考而删 |
| 5 | /reading 页 `.space-page` display:flex + `.space-persona-card` 计数 + 「打开阅读集合 X」link aria-label | reading.spec.ts:25-26, 30-33, 16, 35 | **可安全实现（有条件）**：LibraryShell tab 化若保留外层 `.space-page` 容器与卡片类名/aria-label 则不冲突；若替换为参考的行式列表（`<ul>` 行）会破坏 `.space-persona-card` 断言。倾向：tab/搜索可加，卡片结构本批保留 |
| 6 | 「沉浸阅读」「阅读材料库」heading（含 exact） | reading.spec.ts:23, 135, 259, 263, 277 | **建议保留现状**：参考标题是「Immersive Reading」+ 双 tab（R:LibraryShell.tsx:75-77）；tab 化后两 heading 必须原样存在 |
| 7 | 新建材料表单 label「标题」「正文」+「创建」exact + `?focus=mat-` URL | reading.spec.ts:142-147 | **建议保留现状**：参考入口是上传对话框（R:AddMaterialsDialog.tsx:42-49 ACCEPT 列表，无标题/正文表单）；向参考靠拢会整体破坏该用例。模拟类型选择 + 文本表单是当前显式模拟方案的载体 |
| 8 | 「分配材料 X」「分配「X」」「加入」「已把「X」加入」「已入 1 个集合」 | reading.spec.ts:151-161 | **可安全实现（有条件）**：参考 AssignDialog 结构不同（集合名+材料数+点击即加，R:MaterialLibrary.tsx:554-639）；若改对话框需保留上述五处文案与 aria-label。倾向：本批保留现结构，仅视觉靠拢 |
| 9 | 「还没有文稿」「还没有阅读集合」「还没有材料」空态文案 | writing.spec.ts:13, 61；reading.spec.ts:24, 136 | **可安全实现（有条件）**：参考空态可加图标/按钮（R:page.tsx:117-168），但 strong 文案「还没有文稿/材料/阅读集合」必须逐字保留 |
| 10 | 「载入演示数据」按钮 + 「已载入演示阅读数据」status | reading.spec.ts:14-15, 28-29, 138-139 | **建议保留现状**：参考无演示数据机制；这是当前显式模拟红线的一部分，任何 shell 改造不得移除该按钮 |

### 模拟标注保护清单（逐字保留，含当前行号）

1. 「AI 修改为显式模拟：流式预览 → 应用/放弃，应用前自动保存版本。」— C:WritingEditor.tsx:226
2. 「文稿、版本与草稿本地保存；AI 改写/润色/扩写为显式模拟（统一事件模型流式输出，可取消/重试）。DOCX 导入未接入，不伪装上传成功。」— C:WritingLibrary.tsx:51
3. 「（【模拟生成】本地模板转换，未接入模型…）」生成标注 — C:writing-ai.ts:38（e2e writing.spec.ts:36, 38 断言 `【模拟生成】`）
4. 「AI 改写预览」「AI 修改预览」标题/aria-label — C:WritingEditor.tsx:295, 306（e2e writing.spec.ts:35）
5. SIMULATED_KINDS：「PDF（模拟解析）/EPUB（模拟解析）/网页（模拟抓取）/视频（模拟转录）/音频（模拟转录）」— C:MaterialLibrary.tsx:24-30
6. 行内类型 chip「`${sourceKind.toUpperCase()} · 模拟解析`」— C:MaterialLibrary.tsx:138（e2e reading.spec.ts:377 断言「PDF · 模拟解析」）
7. 「材料解析（PDF/EPUB/DOCX/网页/音视频转录）依赖服务端，未接入；…」— C:MaterialLibrary.tsx:92；表单脚注「…非文本类型为显式模拟…全程标注。」— C:MaterialLibrary.tsx:301-303；「文件名（模拟导入，不读取真实文件）」— C:MaterialLibrary.tsx:327
8. 「已载入演示阅读数据（重复载入不产生重复条目）。材料解析与伴生回复为本地模拟。」— C:ReadingLibrary.tsx:63；「以集合组织阅读材料与伴生会话；材料解析…未接入，仅登记文本材料；…」— C:ReadingLibrary.tsx:79
9. **风险**：参考 MaterialRow/CollectionRow 均无「模拟」字样（R:MaterialLibrary.tsx:310-507、R:ReadingLibrary.tsx:281-359）。若按参考重构行结构，上述 6/8 两处行内标注必须随行迁移，不得因「参考无此元素」而删除。

---

## P-co-writer（/co-writer）

### 信息结构

| # | 差距 | 参考证据（文件:行） | 当前证据（文件:行） | 类型 |
|---|---|---|---|---|
| 1 | 参考为 1/2/3 列自适应卡片网格；当前为垂直 `space-session-list` 列表 | R:app/(workspace)/co-writer/page.tsx:246 `grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3` | C:features/writing/WritingLibrary.tsx:70 `<ul className="space-session-list">` | 结构不同 |
| 2 | 卡片含 4 行截断正文预览（空稿显示「空白草稿」）；当前无内容预览 | R:page.tsx:312-314 `line-clamp-4`；zh/app.json:1195「空白草稿」 | C:WritingLibrary.tsx:71-98（卡片只有标题+chips+时间） | 缺失 |
| 3 | 相对时间「最近更新 X 前」（1m/3h/2d/mo/y）；当前绝对时间 | R:page.tsx:17-31 `relativeTime`、:277-280；zh/app.json:1018「最近更新」 | C:WritingLibrary.tsx:95 `更新于 {new Date(...).toLocaleString('zh-CN')}` | 结构不同 |
| 4 | 头部三操作：导入 Word / 从模板开始 / 新建草稿；当前仅「新建文稿」 | R:page.tsx:193-229；zh/app.json:565「导入 Word」、:1202「从模板开始」 | C:WritingLibrary.tsx:43-48 单按钮 | 缺失（导入 DOCX = 有意保留差异（后续批）；「从模板」独立按钮可作为可选项） |
| 5 | 空态：PenLine 30px 图标 + 主文案 + 副文案 + 三按钮（新建/模板/导入）内联 | R:page.tsx:117-168（图标 :119-123，按钮组 :130-166） | C:WritingLibrary.tsx:64-68 `space-empty` 纯文字 | 缺失 |
| 6 | 卡片标题空时显示「未命名草稿」并带 title 提示 | R:page.tsx:271-275；zh/app.json:1192 | C:WritingLibrary.tsx:75-77 直接显示 doc.title（创建时已兜底「未命名文稿」，C:writing-store.ts:116） | 文案不同（「未命名文稿」被 e2e writing.spec.ts:58 依赖，保留） |
| 7 | 加载态：spinner + 「Loading drafts…」；当前为骨架块 | R:page.tsx:238-242 | C:WritingLibrary.tsx:60-63 `space-skeleton` | 结构不同（等价状态，呈现不同） |
| 8 | 错误横幅 rose 配色 | R:page.tsx:232-236 | C:WritingLibrary.tsx:55-59 `space-banner error`（红系，space.css:255-259） | 结构不同（可不动） |
| 9 | 当前有「N 字」「N 个版本」chips，参考卡片无此信息 | 无参考对应 | C:WritingLibrary.tsx:78-79 | 有意保留差异（本地版本能力的一部分，e2e 无断言但删除无收益） |
| 10 | 参考新建点击即建稿并跳转（无弹窗）；当前为 Modal 表单 | R:page.tsx:62-79 `handleCreate` 直接 `router.push` | C:WritingLibrary.tsx:101-109、115-157 `CreateDocForm` | 结构不同（**e2e 依赖弹窗**，见冲突汇总 #1） |

### 交互状态

| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| 1 | 两击删除：首击变红 + tooltip「再点一次确认」，二击执行；删除中 spinner 禁用 | R:page.tsx:41 `pendingDeleteId`、:283-310（`isPendingDelete ? bg-rose-500/15… : opacity-0 group-hover:opacity-100`）、:98-115 `deletingId` | C:WritingLibrary.tsx:81-91 原生 `window.confirm` | 结构不同（**e2e 冲突汇总 #2，建议保留 confirm**；两击确认登记后续批） |
| 2 | 卡片键盘可达：`role="button" tabIndex={0}` + Enter/Space 打开 | R:page.tsx:253-261 | C:WritingLibrary.tsx:75 `<Link>`（原生可聚焦回车触发，无 Space） | 结构不同（可达性等价偏弱） |
| 3 | 创建/导入进行中：按钮 disabled + Loader2 替换图标 | R:page.tsx:134-141、:220-228（`disabled={creating \|\| importing}`） | C:WritingLibrary.tsx:22 `creating` 仅控制弹窗开关，主按钮无 loading/disabled | 缺失 |
| 4 | 删除按钮 hover 显形：`opacity-0 group-hover:opacity-100` | R:page.tsx:302 | C:WritingLibrary.tsx:82 `icon-button` 常显（globals.css:237-251） | 缺失 |
| 5 | 删除失败回显 error 且保留列表；当前 confirm 后直接删（本地操作失败走 store 异常未捕获到 UI） | R:page.tsx:108-109 `setError` | C:WritingLibrary.tsx:84-88（`deleteDocument` 无 try/catch，store 抛 WritingStorageError 时未展示）[推断：store 抛错会冒泡为未处理异常，C:writing-store.ts:69] | 缺失 |
| 6 | 列表刷新订阅：当前有 `subscribeWriting` + storage 事件（参考为 API 拉取，无此机制） | 无参考对应 | C:WritingLibrary.tsx:33-36 | 有意保留差异（本地仓储架构，非差距） |

### 动画

| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| 1 | 主按钮 `transition-opacity hover:opacity-90 disabled:opacity-60` | R:page.tsx:135、:220 | C:WritingLibrary.tsx:44 `space-button primary`（space.css:355-378 无 transition/hover 透明度） | 缺失 |
| 2 | 次按钮 `transition-colors hover:bg-[var(--muted)]` | R:page.tsx:148、:198 | C:WritingLibrary.tsx:同上（仅 border-color hover，space.css:366-368 无过渡时长） | 缺失 |
| 3 | 卡片 `transition-colors hover:border-[var(--ring)]` | R:page.tsx:262 | space.css:399-406 `.space-session-card` 无 hover/transition | 缺失 |
| 4 | 页面级进出场：参考列表页无（`animate-pop-in` 未在该页使用） | R:page.tsx 全文无 animation 类 | C: 无 | 参考无明确动画来源，不新增（页面级） |

---

## P-co-writer-[docId]（/co-writer/[docId]）

逐状态分支：不存在 / 加载中 / 正常编辑 / AI 面板 / 预览弹窗 / 重命名 / 版本历史。

### 信息结构

| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| 1 | 顶栏：返回按钮带面包屑「Co-Writer / 标题」+ hover 背景 | R:CoWriterWorkspace.tsx:1673-1684（`:1678` `transition-colors hover:bg-[var(--muted)]`） | C:WritingEditor.tsx:196-199 `space-back`（space.css:30-45） | 结构不同（均有返回；参考为面包屑式） |
| 2 | 标题双击 inline 重命名（Enter 提交/Escape 取消/F2 触发，maxLength 120）；当前为按钮 + Modal 表单 | R:CoWriterWorkspace.tsx:1709-1724（`onDoubleClick`/`onKeyDown`）、:486-530 `commitTitle` | C:WritingEditor.tsx:217-219 重命名按钮 → :321-327 `RenameForm`（Modal） | 结构不同（inline 编辑为交互状态差距，见下表 #4） |
| 3 | 字数/字符统计 `N words · N chars`（CJK 分词口径）；窄屏隐藏 | R:CoWriterWorkspace.tsx:532-544、:1725-1727 | C:WritingEditor.tsx:225 `{content.length} 字` | 结构不同 |
| 4 | 5 个工具按钮：清空（danger tone）/导出 MD/导出 Word/存笔记本/载入示例模板（warning tone），各带自绘 tooltip | R:CoWriterWorkspace.tsx:1740-1775、:2426-2463 `ToolbarIconBtn` | C:WritingEditor.tsx:200-213 仅撤销/版本/AI 生成 | 缺失（导出/笔记本/清空登记为有意保留差异（后续批）；tone 着色与 tooltip 可作为视觉借鉴） |
| 5 | Markdown 格式工具栏 26 项（undo/redo/H1-H6/BI/删除线/行内码/引用/列表×3/hr/table/link/image/代码块/mermaid/math）+ 右侧 Sync Scroll 开关 + GFM/KaTeX/Mermaid 徽标 | R:CoWriterWorkspace.tsx:1167-1254 `TOOLBAR`、:1797-1862 | 无对应（C:WritingEditor.tsx:229-257 仅 textarea + 4 按钮） | 有意保留差异（高级编辑能力（后续批）；仅登记） |
| 6 | 底部状态条：error 红 / status 绿底条（清空成功、模板载入等 status 提示） | R:CoWriterWorkspace.tsx:2224-2234、:704-731（clearDocument/loadExampleTemplate 的 status） | C:WritingEditor.tsx:222-224 仅保存状态 chip；编辑器级错误无展示位 | 缺失 |
| 7 | 预览分栏：Editor/Preview 双面板 + 可拖拽 splitter + 折叠钮 + MarkdownRenderer 实时渲染 | R:CoWriterWorkspace.tsx:1864-1988、:1908-1932 splitter | C:WritingEditor.tsx:230-237 纯 textarea | 有意保留差异（split-pane 分栏（后续批）） |
| 8 | 版本历史：参考无此概念（仅 undo/redo 内存栈，上限 50）；当前有版本按钮 + 弹窗 + 恢复 | R:CoWriterWorkspace.tsx:258-261（undoStack/redoStack） | C:WritingEditor.tsx:205-208、:374-407 `VersionsForm`；C:writing-store.ts:160-194 | 有意保留差异（当前超出参考的本地能力，e2e writing.spec.ts:45-48 依赖，**不可删**） |
| 9 | 加载中分支：spinner + 「正在加载文档…」；当前为纯文字 banner | R:CoWriterWorkspace.tsx:1661-1668（`Loader2 animate-spin`） | C:WritingEditor.tsx:102-110「正在读取文稿…」无 spinner | 缺失（图标） |
| 10 | 不存在分支：居中大字「未找到文档」+ 说明 + 「返回 Co-Writer」主按钮 | R:CoWriterWorkspace.tsx:1640-1659；zh/app.json:1186 | C:WritingEditor.tsx:88-101 `space-empty` + `space-button` 返回链接 | 结构不同（等价，文案不同） |

### 交互状态

| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| 1 | 自动保存 1500ms 防抖 + 保存中/已保存双态 + 失败 setError；当前为即时同步写 localStorage（无防抖必要） | R:CoWriterWorkspace.tsx:98、:322-361（`AUTOSAVE_DEBOUNCE_MS`、`isSavingDoc`）、:1728-1737 | C:WritingEditor.tsx:68-79（同步 save）、:222-224 chip | 结构不同（本地存储下即时保存合理；**「已保存」exact 文案必须保留**） |
| 2 | undo/redo：栈 50、400ms 打字合并、Ctrl/Cmd+Z、Shift+Z/Ctrl+Y redo、工具栏按钮 | R:CoWriterWorkspace.tsx:396-484、:460-484 键盘 | C:WritingEditor.tsx:117-128（栈 9、无合并、无 redo、无键盘快捷键）；浏览器原生 undo 在 textarea 仍可用但与状态不同步 [推断] | 缺失（redo 与快捷键；栈深/合并可低优先） |
| 3 | 标题编辑：加载中禁入（`if (isLoadingDoc) return`）；当前 Modal 仅在 doc 存在时可开，等价 | R:CoWriterWorkspace.tsx:486-490 | C:WritingEditor.tsx:217（位于 `doc` 渲染分支内） | 无差距 |
| 4 | inline 重命名键盘链：Enter 提交/Escape 取消/blur 提交/自动 focus+select | R:CoWriterWorkspace.tsx:1690-1701、:524-530 | C:WritingEditor.tsx:335-372 Modal 表单（原生表单行为） | 结构不同（e2e 无重命名断言，可改，但两套交互并存无收益）[推断] |
| 5 | 清空/载入模板的确认 alertdialog（role + aria-labelledby + 撤销可恢复提示条） | R:CoWriterWorkspace.tsx:2348-2411（:2356-2359 aria，:2378-2382 amber 提示） | 无对应操作（无清空/模板按钮） | 有意保留差异（后续批若补工具按钮需连此确认） |
| 6 | AI 全文编辑弹窗：动作三选（Rewrite/Shorten/Expand）+ Source 三选（None/KB/Web）+ KB 选择器（禁用态 `disabled:opacity-40`）+ Auto Mark | R:CoWriterWorkspace.tsx:2237-2346（:2304-2305 disabled） | C:WritingEditor.tsx:260-292 单指令输入 + 开始生成 | 有意保留差异（真实 AI 通道（后续批））；「指令可选」语义当前已有（C:WritingEditor.tsx:272-281） |
| 7 | 选区浮动 popover（360px 可拖拽/可钉住/工具多选/模式菜单/KB 下拉/流式 trace 面板）；当前为 Modal + 全选语义 | R:CoWriterWorkspace.tsx:1990-2221 | C:WritingEditor.tsx:130-137（selectionRef 捕获）+ :260-292 | 有意保留差异（高级编辑能力（后续批）） |
| 8 | AI 应用前竞态防护：`markdownRef.current !== snapshot` 抛「草稿已变更」 | R:CoWriterWorkspace.tsx:1049-1055、:1107-1111 | C:WritingEditor.tsx:139-171 `runAi` 无飞行中变更检测（本地同步存储下风险低 [推断]） | 缺失（低优先，本地架构下可豁免） |
| 9 | AI 应用后恢复选区并刷新 popover（`setSelectionRange` + rAF focus） | R:CoWriterWorkspace.tsx:855-864 | C:WritingEditor.tsx:173-184 `applyPreview` 不恢复选区 | 缺失（依赖 popover，随 #7 后续批） |
| 10 | 导出文件名清洗（非法字符替换 + 80 字截断） | R:CoWriterWorkspace.tsx:782-786 | 无导出功能 | 有意保留差异（后续批补导出时一并实现） |
| 11 | 「保存失败，将重试」chip（saveState error）——当前已有，参考对应为错误状态条 | R:CoWriterWorkspace.tsx:2226-2232 | C:WritingEditor.tsx:223 | 无差距（呈现位置不同） |

### 动画

| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| 1 | 主按钮（Full Draft）`transition-[opacity,transform] duration-150 hover:opacity-90 active:scale-[0.97]` | R:CoWriterWorkspace.tsx:1788 | C:WritingEditor.tsx:209-212 `space-button primary`（space.css:355-378 无） | 缺失 |
| 2 | 工具栏图标按钮 `transition-colors hover:bg-[var(--muted)]/55 active:scale-[0.97]` | R:CoWriterWorkspace.tsx:1815 | C:WritingEditor.tsx:201-212 无 | 缺失 |
| 3 | 弹窗进场：`animate-in fade-in`（遮罩）+ `animate-in zoom-in-95`（卡片）——tailwindcss-animate 插件类 | R:CoWriterWorkspace.tsx:2239、:2244（AI Edit modal）、:2350、:2360（confirm dialog）；同类关键帧 R:globals.css:646-659 fade-in 0.35s ease-out translateY(8px)、:674-686 dt-pop-in 200ms cubic-bezier(0.22,1,0.36,1) | C:components/ui/modal.css 全文无 animation/transition（原生 `<dialog>` showModal，无进出场） | 缺失 |
| 4 | 自绘 tooltip：`opacity-0 → group-hover:opacity-100 delay-[120ms] duration-100` | R:CoWriterWorkspace.tsx:2455-2460 | C:WritingEditor.tsx:201-212 原生 title 属性（无动画） | 缺失 |
| 5 | 选区 popover / 下拉菜单 `dt-popup-up`：180ms cubic-bezier(0.16,1,0.3,1) translateY(6px) scale(0.96)，origin bottom-left | R:CoWriterWorkspace.tsx:1994、:2060、:2102；关键帧 R:globals.css:796-811 | 无对应 | 有意保留差异（随 popover 后续批） |
| 6 | 加载/保存 spinner `animate-spin` | R:CoWriterWorkspace.tsx:1664、:1730 | C:WritingEditor.tsx:102-110 无 spinner；当前有 `space-spin`（space.css:726-734）可用未用 | 缺失 |

---

## P-reading（/reading）

### 信息结构

| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| 1 | 双页共用 LibraryShell：serif 大标题（27/30px）+ 副标语 + 右上主操作按钮 | R:components/reading/library/LibraryShell.tsx:72-94（:75 字号、:86-93 按钮 `h-8 rounded-lg hover:opacity-90`） | C:features/reading/ReadingLibrary.tsx:54-81 `space-header`（h1 24px，space.css:48-54） | 结构不同 |
| 2 | Collections / Material library 双 tab 导航，带计数（`tabular-nums`），active 下边框主色 | R:LibraryShell.tsx:96-109、:117-145 `ViewTab` | C:ReadingLibrary.tsx 无 tab；材料库独立页无返回入口（C:MaterialLibrary.tsx:66-94 仅自身 header） | 缺失（**冲突汇总 #5/#6**） |
| 3 | tab 计数兜底：本视图缺另一视图计数时单拉一次接口，失败静默 | R:LibraryShell.tsx:40-67 | 无对应 | 缺失（随 #2） |
| 4 | 搜索框（`Search collections and materials`）+ 可清除按钮 + 「N collections」计数 + Recent/Name 排序分段钮 | R:ReadingLibrary.tsx:123-162（输入 :129-134、清除 :135-143、排序 :149-160） | 无对应 | 缺失 |
| 5 | 集合行：32px 图标块（首材料 glyph / 解析中 spinner / 空集合 ChevronRight）+ serif 标题 + 材料名预览（前 2 个 `·` 连接 + 「+N more」/「No material yet」）+ 相对日期 | R:ReadingLibrary.tsx:281-359（glyph :309-317、预览 :322-331、日期 :333-335；shared.tsx:107-121 `relativeDate`） | C:ReadingLibrary.tsx:103-145 persona 卡：BookOpen+标题+描述+3 chips（材料 X/会话 X/本地目录）+ 进入阅读/删除按钮 | 结构不同（**e2e 依赖 `.space-persona-card` 计数与「打开阅读集合 X」aria-label**，冲突汇总 #5） |
| 6 | 解析中/失败材料横幅（UnsettledRow）：进度条 `w-[160px]` + 百分比 + 失败原因 + 重试 | R:ReadingLibrary.tsx:86-95、:178-184、:361-426（进度条 :397-406） | 无对应（材料状态只在材料库，C:MaterialLibrary.tsx:139-169） | 缺失（真实解析未接入，登记为有意保留差异；结构可后续批借鉴） |
| 7 | 错误横幅带重试按钮（Retry 链接） | R:ReadingLibrary.tsx:164-176 | C:ReadingLibrary.tsx:88-92 `space-banner error` 无重试（本地存储一般不需重试 [推断]，可豁免） | 缺失（低优先） |
| 8 | 空态双分支：搜索无结果「Nothing matches that.」；真空态虚线框 + serif 标题 + 长说明 + New collection 主按钮 | R:ReadingLibrary.tsx:428-462（:436-441 搜索分支、:444-461 引导框） | C:ReadingLibrary.tsx:97-101 单一 `space-empty`「还没有阅读集合」+ 一句副文案 | 缺失（**「还没有阅读集合」逐字保留**，e2e reading.spec.ts:24） |
| 9 | 删除确认 Dialog：说明「集合与伴生会话将删除，N 份材料保留在库中」+ 危险主按钮 + working spinner | R:ReadingLibrary.tsx:464-529（文案 :483-491、按钮 :503-524） | C:ReadingLibrary.tsx:129-141 原生 confirm「删除阅读集合「X」？材料保留在库中，伴生会话将一并删除。」 | 结构不同（**e2e 原生 dialog 依赖，冲突汇总 #2，建议保留 confirm**） |
| 10 | 「载入演示数据」按钮 + 幂等提示 | 无参考对应 | C:ReadingLibrary.tsx:58-71 | 有意保留差异（当前显式模拟入口，e2e reading.spec.ts:14-15, 28-29 依赖，**不可删**） |
| 11 | 课程 scope chip（CourseScopeChip） | R:ReadingLibrary.tsx:53-54、:121 | 无对应（课程联动未接入） | 有意保留差异（后续批） |
| 12 | 主操作文案「新建阅读集合」vs 参考「New collection」打开统一 AddMaterialsDialog（create 模式：命名 + 拖放/链接/库内选择 + 重复检测） | R:ReadingLibrary.tsx:119、R:AddMaterialsDialog.tsx:59-96、:89-94 | C:ReadingLibrary.tsx:162-204 `CreateWorkspaceForm`（名称+简介表单） | 结构不同（真实上传/URL 导入 = 有意保留差异（后续批）；e2e 无集合新建断言拦截 [未验证：grep spec 未见「新建阅读集合」dialog 断言]） |

### 交互状态

| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| 1 | 搜索 140ms 防抖拉取 | R:ReadingLibrary.tsx:78-81 | 无搜索 | 缺失 |
| 2 | 行 hover 背景 `hover:bg-[var(--secondary)]` + 整行 Link | R:ReadingLibrary.tsx:305-308 | C:ReadingLibrary.tsx:108-124 卡片 Link（space-persona-card 无 hover，space.css:618-627） | 缺失 |
| 3 | 行菜单（MoreHorizontal）：`opacity-100 sm:opacity-0 sm:group-hover:opacity-100 sm:focus:opacity-100`（触屏常显、桌面 hover 显、focus 可达） | R:ReadingLibrary.tsx:337-344 | 删除按钮常显（C:ReadingLibrary.tsx:129-141） | 缺失（模式不同；当前按钮直达删除反而少一步，保留可行） |
| 4 | 错误时禁止空态文案（避免「请求失败」上叠「还没有集合」假象） | R:ReadingLibrary.tsx:191-200（注释明确此设计意图） | C:ReadingLibrary.tsx:88-101 error 与空态互斥渲染（:88 error 在前，:97 空态判断独立）——当前实现 error 时仍会同时显示空态 [核对：error 与空态非 else-if，error 时 `workspaces.length===0` 也会渲染空态] [推断：视觉叠加可能发生] | 结构不同（低风险，本地存储 error 罕见） |
| 5 | 排序切换 Recent（updated_at 降序）/ Name（localeCompare） | R:ReadingLibrary.tsx:101-112 | 当前 `readWorkspaces()` 顺序（C:services/reading-store.ts:337-339，未排序返回） | 缺失 |
| 6 | 删除失败在 Dialog 内回显 error | R:ReadingLibrary.tsx:492-494 | C:ReadingLibrary.tsx:132-137 confirm 后直接 `deleteWorkspace`（store 抛错未捕获到 UI [推断]） | 缺失 |

### 动画

| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| 1 | 行/按钮 transition：SortButton `transition`（R:ReadingLibrary.tsx:270-274）、主按钮 `transition hover:opacity-90`（R:LibraryShell.tsx:89）、tab `transition`（R:LibraryShell.tsx:131-135） | 同左 | C:ReadingLibrary.tsx:58-75 `space-button`（space.css:355-378 无 transition） | 缺失 |
| 2 | 行菜单 hover/focus opacity 过渡（`transition`，R:ReadingLibrary.tsx:341） | 同左 | C:ReadingLibrary.tsx:129-141 无 | 缺失 |
| 3 | 弹窗/菜单进出场：参考阅读库菜单**未用** `dt-popup-up`（R:ReadingLibrary.tsx:346 仅 `shadow-md`；R:MaterialLibrary.tsx:486 同）——参考此处无动画 | R:ReadingLibrary.tsx:345-356 | C: 无 | 参考无明确动画来源，不新增（菜单级） |

---

## P-reading-materials（/reading/materials）

### 信息结构

| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| 1 | LibraryShell 复用（同 /reading #1/#2）：标题「Immersive Reading」+ Material library tab active | R:MaterialLibrary.tsx:112-119、R:LibraryShell.tsx:96-109 | C:MaterialLibrary.tsx:66-94 独立 header「阅读材料库」 | 缺失（**e2e heading「阅读材料库」exact 必须保留**，冲突汇总 #6） |
| 2 | 筛选 chips 4 个：All / Not in a collection / Preparing / Failed，active 反色（foreground 底 background 字），带计数（>0 才显示） | R:MaterialLibrary.tsx:147-171、:281-308 `FilterChip` | C:MaterialLibrary.tsx:96-108 `space-tabs` 2 个（全部/未分配集合） | 缺失（Preparing/Failed 筛选；**e2e 无 tabs 断言拦截 [未验证]**，可安全增补） |
| 3 | 搜索框（按标题/文件名/链接）+ 清除 + 「N materials」计数 | R:MaterialLibrary.tsx:120-145 | 无对应 | 缺失 |
| 4 | 六列响应式网格 GRID（28/32px 图标 · 材料 · Type(≥lg) · In collections(≥sm) · Added · 菜单）+ 表头行 | R:MaterialLibrary.tsx:47-50 `GRID`、:187-196 表头 | C:MaterialLibrary.tsx:129-197 单列 `space-session-list` chips 堆叠 | 结构不同 |
| 5 | 行次行信息：身份（文件名/displayUrl）· 大小 · 页数/节数；类型尾（扩展名大写 tag · 时长）窄屏前置 | R:MaterialLibrary.tsx:344-354、:397-414；R:shared.tsx:57-105（formatTag/formatBytes/displayUrl/materialDetail） | C:MaterialLibrary.tsx:137-138 「N 字」chip + 类型 chip | 结构不同（当前无大小/页数/时长概念——本地文本材料无此元数据 [推断]） |
| 6 | 集合成员列：前 2 个集合名 chip（可点进集合，第一个 `flex-1`、第二个 `max-w-[96px]`）+ 「+N」；未分配显示虚线「Add to a collection」按钮 | R:MaterialLibrary.tsx:423-455（chip :428-443、虚线钮 :446-453） | C:MaterialLibrary.tsx:145 计数 chip「已入 N 个集合/未分配」（**e2e :161 断言「已入 1 个集合」**） | 结构不同（冲突汇总 #8：改造需保留该文案或同步 spec） |
| 7 | 状态徽标：解析中标题旁 `progress%`、失败标题旁红「Failed」 | R:MaterialLibrary.tsx:383-392 | C:MaterialLibrary.tsx:139-144 状态 chip（就绪/排队中/解析中/解析失败）+ :147-169 操作按钮 | 结构不同（等价，呈现不同；「解析失败」exact 被 e2e :373 依赖） |
| 8 | AssignDialog：标题 + 材料名 truncate；集合行（serif 名 + N materials + 加入中 spinner）；空态双文案（已在所有集合/还没有集合）；底部「New collection…」+ Cancel | R:MaterialLibrary.tsx:509-639（空态 :607-613、底栏 :620-635） | C:MaterialLibrary.tsx:214-265 `AssignButton` Modal：集合行 + 加入按钮 + 空态引导（:231-235）；加入后 status 横幅 | 结构不同（**e2e 五处文案依赖**，冲突汇总 #8；「New collection…」入口缺失） |
| 9 | DeleteMaterialDialog：按是否在集合区分两种文案（含所在集合列表）+ working spinner | R:MaterialLibrary.tsx:641-711（:661-673 双文案） | C:MaterialLibrary.tsx:173-183 原生 confirm | 结构不同（冲突汇总 #2，建议保留 confirm） |
| 10 | 新建/上传入口 AddMaterialsDialog（mode=upload）：拖放区（dragging 反色 `border-[var(--primary)] bg-[var(--muted)]`）+ 链接粘贴行 + 待传列表（重复检测 same_content/same_name + reuse/separate 决策 chip）+ 库内选择器（搜索 + loading + 空态）+ 提交态 | R:AddMaterialsDialog.tsx:59-96（mode）、:322-493（主体）、:374-428 拖放、:430-615 重复决策、:651-734 LibraryPicker | C:MaterialLibrary.tsx:267-358 `CreateMaterialForm`：文本粘贴表单 + 5 种模拟类型 + 模拟失败复选 + 「导入并开始模拟解析」 | 有意保留差异（真实上传/解析（后续批））；**模拟类型选择与失败演练复选是当前显式模拟方案载体（e2e R32 reading.spec.ts:364-370 依赖），不可删** |
| 11 | 「载入演示数据」按钮 | 无参考对应 | C:MaterialLibrary.tsx:71-84 | 有意保留差异（e2e reading.spec.ts:138 依赖，不可删） |
| 12 | 新建后 `?focus=mat-` 跳转 | 无参考对应（参考 onDone 后 refresh，R:MaterialLibrary.tsx:244-253） | C:MaterialLibrary.tsx:200-208 `router.push(\`/reading/materials?focus=${id}\`)`；**注意：当前组件未读取 focus 参数做任何高亮/滚动** [核对：全文无 `focus` 读取逻辑，仅 push URL] [推断：focus 参数目前只是 URL 痕迹] | 有意保留差异（e2e :147 断言 URL，**参数必须继续出现在 URL**；高亮行为可后续批补） |

### 交互状态

| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| 1 | 搜索 140ms 防抖 + 服务端过滤 | R:MaterialLibrary.tsx:91-94 | 无搜索 | 缺失 |
| 2 | Preparing/Failed 筛选 + 计数兜底 tally（服务端 counts 缺席时从行内推导） | R:MaterialLibrary.tsx:96-110、:147-171 | C:MaterialLibrary.tsx:60-63 仅前端 unassigned 过滤（计数实时算，:106） | 缺失（Preparing/Failed 分支） |
| 3 | 错误时禁止空态（同 /reading #4） | R:MaterialLibrary.tsx:203-214（注释同源） | C:MaterialLibrary.tsx:114-127 error 与空态可同时渲染 [推断：同 /reading 结构] | 结构不同 |
| 4 | 行菜单（MoreHorizontal）：hover 显形 + 菜单（加入集合/删除材料） | R:MaterialLibrary.tsx:475-504 | 操作按钮常显（C:MaterialLibrary.tsx:146-184） | 结构不同 |
| 5 | AssignDialog 每项 working 态（按 workspaceId 显示 spinner + disabled 其余项） | R:MaterialLibrary.tsx:522、:570-571、:602-604 | C:MaterialLibrary.tsx:242-255 加入无 loading 态（本地同步即时完成 [推断]，可豁免） | 缺失（低优先） |
| 6 | 未分配行内虚线「加入集合」直达按钮（免开菜单） | R:MaterialLibrary.tsx:446-453 | C:MaterialLibrary.tsx:170-172 `AssignButton` 常显按钮 | 无实质差距（等价入口） |
| 7 | 失败行内 Retry 链接（Added 列位置）+ 失败原因文案 | R:MaterialLibrary.tsx:458-469、:409-413 | C:MaterialLibrary.tsx:147-159 重试按钮 + :186-190 statusNote 行 | 无实质差距 |
| 8 | 材料点击行为：有集合→进第一个集合，无集合→开分配弹窗（`open()`） | R:MaterialLibrary.tsx:356-360 | C:MaterialLibrary.tsx:136 标题为纯 span 不可点（参考也仅图标/标题钮可点 :365-378） | 缺失（标题不可点；当前无「打开材料」语义——本地材料需先进集合 [推断]） |

### 动画

| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|---|---|---|---|
| 1 | FilterChip `transition`（active 反色切换） | R:MaterialLibrary.tsx:296-300 | C:MaterialLibrary.tsx:96-108 `space-tabs button`（space.css:701-716 无 transition） | 缺失 |
| 2 | 拖放区 dragging 反色 `transition`（border+bg 切换） | R:AddMaterialsDialog.tsx:381-385 | 有意保留差异（真实上传（后续批）） | 有意保留差异 |
| 3 | 行集合 chip `hover:border-[var(--primary)] hover:text-[var(--primary)]` | R:MaterialLibrary.tsx:432、:449 | 无对应 | 缺失 |
| 4 | 菜单/弹窗进出场：参考材料库菜单未用动画类（R:MaterialLibrary.tsx:486 仅 shadow-md）；Dialog 亦无 animate 类（R:MaterialLibrary.tsx:655-657） | 同左 | C:components/ui/modal.css 无动画 | 参考无明确动画来源，不新增（本页弹窗级） |

---

## 附录 A：样式文件归属与影响面

**writing：无模块 CSS 现状**
- C:features/writing/ 下无任何 .css 文件；WritingLibrary.tsx:15 与 WritingEditor.tsx:17 导入 `@/features/space/styles/space.css`；细粒度样式走内联（WritingEditor.tsx:218 `style={{ transform: 'rotate(90deg)' }}`、:235 `style={{ minHeight: 420, width: '100%', ... }}`、:306 复用 `reading-msg assistant`）。
- 结论：写作动画/交互补齐若需 CSS，应**新增** `features/writing/writing.css`（或等价模块文件）并在两个组件 import；**不建议改 space.css**（任务约束），space.css 现有类（space-button/space-session-card/space-chip 等）被 space/whisper/教案等多模块共用。

**reading.css 类清单与使用方**（C:features/reading/reading.css，160 行，工作区共用禁区）
| 类 | reading.css 行 | 实际使用方 |
|---|---|---|
| .reading-layout | :5-16 | ReadingWorkspace.tsx:337（**禁区，不可动**） |
| .reading-pane | :18-36 | ReadingWorkspace.tsx:508, 890, 944 |
| .reading-mark | :38-42 | ReadingWorkspace.tsx:747, 997 |
| .reading-companion / .reading-companion-body | :44-61 | ReadingWorkspace.tsx:1424, 1458 |
| .reading-msg / .user / .assistant | :63-79 | ReadingWorkspace.tsx:1474, 1480；**以及 WritingEditor.tsx:306（写作 AI 预览跨模块借用）** |
| .reading-composer | :81-92 | ReadingWorkspace.tsx:1516 |
| .reading-companion-drag | :95-107 | ReadingWorkspace.tsx:357（R31 键盘可达 e2e 依赖 reading.spec.ts:326-338） |
| .reading-drawer-backdrop / .reading-drawer | :110-130 | ReadingWorkspace.tsx:381, 383 |
| .reading-selection-bar | :140-152 | ReadingWorkspace.tsx:988 |
| .reading-quote-block | :154-160 | ReadingWorkspace.tsx:989, 1475 |
- 库级两页（C:ReadingLibrary.tsx:21、C:MaterialLibrary.tsx:22）import 了 reading.css 但**未使用其中任何类**（副作用导入；去掉属优化但会改变样式层叠输入，本批不动）。
- 结论：本批所有建议不得触碰 reading.css；WritingEditor 对 `reading-msg` 的借用单独登记（若后续批为写作预览建独立样式，可解除该跨模块耦合）。

**当前动画资产盘点**（可复用点）
- space.css:274-290 `space-skeleton`/`space-pulse`（1.4s ease-in-out，列表骨架在用）；:726-734 `space-spin`（0.9s 旋转，未在四页使用）；:96-105 `space-tile` hover 上浮（仅 space 页）；globals.css:587-595 reduced-motion 全局。
- 参考 keyframes 供后续批移植时的规格（只读参考，不拷贝文件）：fade-in（R:globals.css:646-659，0.35s ease-out，translateY(8px)）；dt-pop-in（:674-686，200ms cubic-bezier(0.22,1,0.36,1)，translateY(6px) scale(0.985)）；dt-popup-up（:796-811，180ms cubic-bezier(0.16,1,0.3,1)，scale(0.96)，origin bottom-left）；dt-breathing（:691-703）；dt-detail-in（:711-724）。任务卡提到的 `dt-pop-in` 在四个库级页面源码中**未被引用**（grep R: 侧页面文件无 `animate-pop-in`），实际被引用的是 tailwindcss-animate 插件类 `animate-in fade-in / zoom-in-95`（R:CoWriterWorkspace.tsx:2239, 2244, 2350, 2360）与 `dt-popup-up`（R:CoWriterWorkspace.tsx:1994, 2060, 2102）——登记以免实现卡误引。

## 附录 B：现有 e2e 断言的用户可见行为清单（库级相关，逐条 + 行号）

**tests/e2e/writing.spec.ts（95 行，3 test；whisper 1 例不在本批）**
| 行 | 断言/行为 | 当前实现位置 |
|---|---|---|
| :11-13 | /co-writer heading「协同写作」+「还没有文稿」 | WritingLibrary.tsx:42, 66 |
| :16 | 按钮「新建文稿」 | WritingLibrary.tsx:44 |
| :17-20 | dialog「新建文稿」+ getByLabel('标题') + label /教学设计示例模板/ check + 按钮「创建」 | WritingLibrary.tsx:120, 134, 139, 151 |
| :21 | URL /\/co-writer\/doc-/ | writing-store.ts:118 `uid('doc')` |
| :22 | heading「分数教学文稿」 | WritingEditor.tsx:215-220 h1 |
| :25-27 | getByLabel('文稿正文编辑区') fill → 「已保存」exact（10s） | WritingEditor.tsx:232, 223 |
| :30-31 | Ctrl+A → 按钮「选区改写」 | WritingEditor.tsx:239 |
| :32-34 | dialog「AI 改写」+ getByLabel(/指令/) + 按钮「开始生成」 | WritingEditor.tsx:261, 275, 287 |
| :35-36 | dialog「AI 改写预览」+ getByLabel('AI 修改预览') 含「【模拟生成】」 | WritingEditor.tsx:295, 306；writing-ai.ts:38 |
| :37-38 | 按钮「应用」→ textarea 值含「【模拟生成】」 | WritingEditor.tsx:314, 173-184 |
| :41-42 | 按钮「撤销修改」→ 值不再含标注 | WritingEditor.tsx:201, 121-128 |
| :45-48 | 按钮「版本历史」→ dialog 含 /改写前自动快照/ → /恢复版本/ first 点击 → 「已保存」 | WritingEditor.tsx:205, 377, 145（runAi 内快照 label）, 389 |
| :54-56 | 「新建文稿」→ dialog「创建」→ URL doc- | 同上 |
| :58 | `.space-session-card` 含「未命名文稿」 | WritingLibrary.tsx:72；writing-store.ts:116 |
| :59-60 | `page.once('dialog')` accept → getByLabel('删除文稿 未命名文稿') | WritingLibrary.tsx:83, 85 |
| :61 | 「还没有文稿」恢复 | WritingLibrary.tsx:66 |

**tests/e2e/reading.spec.ts（581 行，17 test；R-09 五例与工作区用例不在本批审计改面内，仅库级相关如下）**
| 行 | 断言/行为 | 当前实现位置 |
|---|---|---|
| :13-15 | /reading → 「载入演示数据」→ status 含「已载入演示阅读数据」 | ReadingLibrary.tsx:58-71, 63, 84 |
| :16, :35 | link「打开阅读集合 分数阅读（演示集合）」 | ReadingLibrary.tsx:112 |
| :23 | heading「沉浸阅读」 | ReadingLibrary.tsx:56 |
| :24 | 「还没有阅读集合」 | ReadingLibrary.tsx:99 |
| :25-26 | `.space-page` computed display === 'flex' | space.css:4-11（ReadingLibrary.tsx:53 容器类） |
| :30-33 | `.space-persona-card` 含「分数阅读（演示集合）」且 count 1、二次载入幂等 | ReadingLibrary.tsx:108；reading-store.ts:670+ loadDemoReading |
| :133-140 | /reading/materials heading「阅读材料库」+「还没有材料」→ 载入演示 → `.space-session-card` 含演示材料 | MaterialLibrary.tsx:69, 125, 71-84 |
| :142-147 | 「新建材料」dialog + getByLabel('标题')/('正文') + 「创建」exact → URL ?focus=mat- | MaterialLibrary.tsx:87, 275, 317, 322, 352, 205 |
| :151-161 | 「分配材料 X」→ dialog「分配「X」」→ 集合卡「加入」→ status「已把「X」加入」→「已入 1 个集合」 | MaterialLibrary.tsx:226, 230, 254, 247, 145 |
| :164-169 | 原生 confirm accept → getByLabel('删除材料 X') → 卡片 count 0 | MaterialLibrary.tsx:175, 177 |
| :254-277（R28） | 工作区「材料库…」按钮 → /reading/materials + heading「阅读材料库」exact → 前进后退一致；添加弹窗「打开材料库」 | MaterialLibrary.tsx:69（heading）；「材料库…」「打开材料库」在 ReadingWorkspace（禁区，勿动） |
| :361-386（R32 材料导入） | 「新建材料」→ 材料类型 select pdf → /文件名/ + checkbox → 「导入并开始模拟解析」→「解析失败」→「重试解析 X」→「就绪」→「PDF · 模拟解析」→ 分配 | MaterialLibrary.tsx:306-313, 328-339, 352, 143, 148-158, 138 |
| :388-405（R32 移动端） | 390px 下工作区抽屉（工作区范畴，本批不改；仅提示库级页面 390 无对应 e2e） | — |

## 范围矛盾与待队长决定事项汇总

1. **版本历史归属**：参考 CoWriterWorkspace 无版本系统；当前版本/快照/恢复是本地增强且 e2e writing.spec.ts:45-48 依赖。对齐参考 = 删功能 = 破坏 e2e。倾向：保留（登记为「当前超出参考的能力」，不计入差距）。
2. **新建文稿弹窗 vs 直建**：参考点击即建（R:page.tsx:62-79）；当前弹窗 + e2e writing.spec.ts:17-20 依赖。倾向：保留弹窗；若要参考式直建，作为第二入口追加。
3. **删除确认范式**：参考两击删除/自定义 Dialog；当前原生 confirm 被两个 spec 依赖（writing.spec.ts:59-60、reading.spec.ts:164-168）。倾向：本批保留 confirm；统一改两击/Dialog 需连 spec 一起改，属有界实现卡决策。
4. **LibraryShell tab 化与 .space-page**：参考信息架构是双 tab shell；当前独立页 + `.space-page`（e2e reading.spec.ts:25-26 断言 display:flex）。tab 可加，但外层容器类、两个 heading、「载入演示数据」按钮、`.space-persona-card` 计数断言必须保留，否则需改 spec（超出本批授权）。
5. **新建材料入口**：参考是真实上传对话框；当前是文本表单 + 模拟类型（e2e :142-147 与 R32 :364-370 双重依赖）。倾向：保留现表单，仅视觉层靠拢参考。
6. **`?focus=mat-` 语义**：URL 已被 e2e :147 断言，但当前组件无 focus 消费逻辑（C:MaterialLibrary.tsx 全文无读取）。是否补「新建后高亮/滚动定位」由实现卡决定；URL 参数本身不可移除。
7. **写作 CSS 落地方式**：动画补齐需要 CSS 载体，但 space.css 在禁改清单。需队长指定：新增 features/writing/writing.css（倾向）或复用 Tailwind（当前项目未在该模块使用 Tailwind [核对：WritingLibrary/WritingEditor 无 tailwind 类名]）。
8. **WritingEditor 借用 reading.css `reading-msg`**：跨模块耦合（C:WritingEditor.tsx:306）。本批不动；建议后续批给写作预览独立样式时解除。
9. **参考字数统计口径（words）与当前（字符数）**：非对错问题；改口径无 e2e 影响（[未验证]：spec 无字数断言），低优先。
10. **错误时空态叠加**：当前两库页 error 与空态非互斥渲染 [推断]；本地存储场景 error 罕见，是否按参考改为互斥由实现卡决定（低优先）。
