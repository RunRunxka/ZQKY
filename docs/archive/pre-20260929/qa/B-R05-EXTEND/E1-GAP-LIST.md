# B-R05-EXTEND-E1 逐页差距清单（v1）

- 核对时间：2026-09-18
- 参考仓库：F:\DeepTutor，HEAD = 42fab3cf429a1fbf36b257ab8d116a3814964202（v1.6.5，与任务卡固定提交一致，已用 `git rev-parse` 核实）
- 当前仓库 HEAD：3f968b0e46646952c1cf7547fe156089ed7f85b6（工作区有 3 个未提交改动文件，未触碰）
- 审计范围声明：仅核对四个页面（/knowledge-bases、/knowledge-bases/[kbName]、/notebooks、/notebooks/[notebookId]）的信息结构、交互状态与动画三类差距；真实服务接入（RAG/解析/向量检索）不在本批范围，仅在标注「有意保留差异」处一句话提及。

---

## 摘要

### P-knowledge-bases（/knowledge-bases）最值得做
1. 页签改为参考式下划线指示器 + 图标 + 计数徽标（当前为分段按钮，无图标/无下划线/检索引擎页签无计数）。
2. 卡片补 StatusDot 状态圆点、右上角 ChevronRight 悬停显现、hover 描边与 focus-visible 环。
3. 空态改为图标 + 主行动按钮（「新建知识库」），当前空态无图标无按钮。
4. 卡片分组 meta 行加 provider 徽标（「本地目录」chip 可升级为参考的圆角描边小徽标样式）。
5. 新建按钮/主行动按钮补 hover:opacity-90 与 focus-visible ring。

### P-knowledge-bases-[kbName]（/knowledge-bases/[kbName]）最值得做
1. 详情头部改为参考式「图标 + 返回链接 + serif 标题 + 徽标组」结构，状态徽标带图标（Clock/AlertTriangle/CheckCircle2）。
2. 分区导航改为参考式底部 2px 下划线页签（当前为分段按钮盒），并补「设置」中的删除/默认操作归位与 retry 按钮的标题提示（title）。
3. 文档行补悬停显影的操作钮组（当前操作钮常驻）与行内确认删除（Check/X 二段式）。
4. 索引版本行补 Active/Stale/Building 图标章（星标/旋转/警告）与 dimension/签名/时间元数据行。
5. 「重试失败项」「全部解析并索引」补 disabled 态与 submitting 旋转图标。

### P-notebooks（/notebooks）最值得做
1. 左栏从 168px 提到参考的 250px，激活项加左侧 2.5px 指示条（h-62% 过渡动画）。
2. 顶栏加参考式「Notebooks serif 标题 + 计数徽标 + 右侧 Plus 图标按钮（aria-expanded）」，当前「新建笔记本」是 rail 内第一个列表项。
3. 行操作钮组改参考式「常驻触发钮 hover 显影 + MoreHorizontal 弹出菜单 + Move/Copy 子面板」，当前为三个常驻 icon-button。
4. 错误/空态改参考式 ConsoleNotice（图标块 + 标题 + 详情 + Retry 按钮），当前为 space-banner/space-empty 平铺。
5. 展开区补 animate-pop-in 进场动画与失败提示 role=alert 行内条。

### P-notebooks-[notebookId] 最值得做
（与 P-notebooks 同一组件，条目重合；仅列差异）
1. 深链不存在的笔记本时补参考式 ConsoleNotice 错误态（图标 + Retry），当前是顶部 banner 报错 + 「选择一个笔记本」空态并列。
2. URL 同步：当前仅 pushState 单向写 URL（NotebooksSection.tsx:129-131），无 popstate/back-forward 跟随，也无 router.replace 规范化；参考用 router.replace 双向跟随（NotebookConsole.tsx:89-92）。
3. 删除笔记本确认文案补 record_count 计数变体（「"x" 和它的 n 条记录将被删除」）。

### 全局性发现
1. 四页共用 `apps/web/src/features/space/styles/space.css`；该文件同时被 /space 子页、books、courses、reading、writing、whisper、chat（ArtifactPanel）使用（用 grep 核实文件清单见附录 A）。改共享类（space-button/space-chip/space-session-card/scope-rail/tabs）会波及这些页面；新增页面专属类（如 notebook 专用 rail 指示条）或局部 Tailwind 工具类是安全路径。
2. 参考四页的交互态几乎全部是 Tailwind 原子类（hover:/focus-visible:/active:/transition-*/animate-*），当前项目内这些能力在 space.css 只有零星覆盖（space-tile、space-back、space-button 有 hover；无 focus-visible 全局环、无 active:scale）。补交互态优先写在组件级类或 space.css 的新增块，不动 globals.css 变量层。
3. 参考的 `animate-pop-in`（globals.css:674-686：200ms cubic-bezier(0.22,1,0.36,1)，translateY(6px)+scale(0.985)→0）是四页共用进出场动画来源；当前 globals.css 只有 reduced-motion 全关块（globals.css:584-591）与 space.css 的 space-pulse/space-rotate，无等价 pop-in。复刻时需要新增一个 keyframes（建议放 space.css，避免动全局变量层）。
4. 参考详情页头部标题用 `font-serif`（KnowledgeBaseDetail.tsx:202），当前 space-header h1 已有 `--font-display`（space.css:48-54），方向一致，无需新变量。

---

## P-knowledge-bases（/knowledge-bases）

### 信息结构

| # | 差距 | 参考证据（文件:行） | 当前证据（文件:行） | 类型 |
|---|------|--------------------|--------------------|------|
| 1 | 页签结构：参考为「图标+标签+圆角计数徽标」的底部下划线页签，激活项文本变主色并在底部渲染 0.5px 高指示条 | KnowledgeHome.tsx:248-297（role=tablist 于 249-251；计数徽标 287-289；指示条 291-293） | KnowledgeBasesSection.tsx:137-154（space-tabs 分段盒按钮，文本内联「知识库 ({kbs.length})」，无图标无指示条） | 结构不同 |
| 2 | 「检索引擎」页签缺计数徽标：参考计入 providers.length + externalSources.length | KnowledgeHome.tsx:263（`count: providers.length + externalSources.length`） | KnowledgeBasesSection.tsx:146-153（按钮文本仅「检索引擎」，无计数） | 缺失 |
| 3 | 知识库卡片缺状态圆点 StatusDot：参考按 needsReindex/error/live/ready 显示 amber/red/sky(pulse)/emerald 圆点 | KnowledgeHome.tsx:78-92（StatusDot 定义），375（卡片内使用） | KnowledgeBasesSection.tsx:212-216（用 space-chip 文字徽标表达状态，无圆点） | 结构不同 |
| 4 | 卡片缺悬停显影的 ChevronRight：参考在 meta 行右侧 `opacity-0 transition-opacity group-hover:opacity-60` | KnowledgeHome.tsx:193（引擎卡片同款）、359-363（KB 卡片容器 group） | KnowledgeBasesSection.tsx:200-218（space-persona-card 无 ChevronRight） | 缺失 |
| 5 | KB 卡片缺 provider 小徽标样式：参考为圆角描边 chip（rounded-full border px-1.5 py-0.5）+「n docs」文本 | KnowledgeHome.tsx:386-395 | KnowledgeBasesSection.tsx:212-216（space-chip 三个：状态/文档数/本地目录；文档数是 chip 而参考是裸文本） | 结构不同 |
| 6 | 空态结构：参考为虚线框 + 图标（Database）+ 标题 + 说明 + 主行动按钮「New knowledge base」 | KnowledgeHome.tsx:330-349 | KnowledgeBasesSection.tsx:177-181（space-empty 仅有标题+说明，无图标无按钮） | 缺失 |
| 7 | 空态主行动按钮文案：参考复用「New knowledge base」；当前空态引导用户「载入演示知识库或新建」但无按钮 | KnowledgeHome.tsx:341-348 | KnowledgeBasesSection.tsx:179-180 | 文案不同 |
| 8 | 搜索无匹配空态：参考为细虚线框一行文本「No matches」（py-8）；当前用 space-empty 大空态（strong+span） | KnowledgeHome.tsx:350-353 | KnowledgeBasesSection.tsx:221-226 | 结构不同 |
| 9 | 搜索框仅 kbs.length > 6 时显示，且带左侧内嵌 Search 图标（pointer-events-none absolute） | KnowledgeHome.tsx:314-327 | KnowledgeBasesSection.tsx:184-195（同样 >6 才显示；但 space-search 无内嵌图标） | 部分缺失 |
| 10 | 头部：参考标题 19px semibold tracking-tight + 副标题 12.5px，主按钮为实心 primary 圆角 lg；当前标题 24px display 字体 + 描边按钮 + 额外「载入演示数据」按钮 | KnowledgeHome.tsx:229-246 | KnowledgeBasesSection.tsx:112-135 | 结构不同（标题字号/按钮形态）|
| 11 | 引擎卡片：参考带 KnowledgeEngineIcon（24px）+ 描述 line-clamp-2 + default_mode 圆角 mono 徽标 +「n KB」计数 | KnowledgeHome.tsx:162-197 | KnowledgeBasesSection.tsx:239-245（space-cli-card，通用 Globe/HardDrive/Server 图标，无 mode 徽标、无计数） | 结构不同 |
| 12 | 引擎分组标题：参考为「图标 + 13px 标题 + 11.5px 说明」左对齐组头 | KnowledgeHome.tsx:411-421、428-438、445-455、462-474 | KnowledgeBasesSection.tsx:232-233（space-group-label 单行标题，无图标无说明） | 结构不同 |
| 13 | 外部来源卡片：参考带「Connect vault / Connect library」行动文案与「n connected」计数 | KnowledgeHome.tsx:138-160、215-221 | KnowledgeBasesSection.tsx:73-76、254-262（desc 写「目标项目未接入」，无行动词无计数） | 有意保留差异（真实连接不接入，符合任务卡排除项；行动文案结构仍可借鉴） |
| 14 | 状态徽标 EngineStatusBadge：参考 Ready/Needs key/Needs setup/Not installed 四态圆角 chip（含 Check 图标） | KnowledgeHome.tsx:47-76 | KnowledgeBasesSection.tsx:54-71（引擎以「（演示）/（未接入）」后缀命名区分） | 有意保留差异（无真实引擎可探活） |
| 15 | 路由层级：参考 /knowledge-bases 与 [kbName] 共用同一个 KnowledgePage（同组件内 home/kb 视图切换，URL 由 router.replace 维护） | knowledge-bases/page.tsx:1-19；KnowledgePage.tsx:107-190 | 当前两路由各自渲染独立 Section 组件（app/knowledge-bases/page.tsx:5-7、[kbName]/page.tsx:5-7）；列表页 URL 无 ?section=engines 同步 | 结构不同（行为等价性：列表→详情导航为 Link 跳转，可用） |
| 16 | 全局错误条：参考顶部红色错误条带 Retry + Dismiss 双按钮 | KnowledgePage.tsx:301-321 | KnowledgeBasesSection.tsx:164-168（space-banner error 无按钮；数据读取失败无重试入口） | 缺失 |
| 17 | 加载态：参考为居中 Loader2 spinner（animate-spin） | KnowledgePage.tsx:323-326 | KnowledgeBasesSection.tsx:171-176（space-skeleton 两根骨架条） | 结构不同（两者皆可用；骨架非缺陷，登记为样式差异） |

### 交互状态

| # | 差距 | 参考证据（文件:行） | 当前证据（文件:行） | 类型 |
|---|------|--------------------|--------------------|------|
| 1 | 页签按钮缺 focus-visible ring：参考 `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-[var(--ring)]` | KnowledgeHome.tsx:278 | KnowledgeBasesSection.tsx:138-153（space-tabs 无 focus-visible 样式；space.css:701-716 亦无） | 缺失 |
| 2 | 页签 hover 变色：参考非激活项 `hover:text-[var(--foreground)]` + transition-colors | KnowledgeHome.tsx:278-282 | space.css:701-716（space-tabs button 无 hover 规则） | 缺失 |
| 3 | 卡片 hover 描边：参考 `hover:border-[var(--ring)]` + transition-colors（KB 卡与引擎卡同款） | KnowledgeHome.tsx:363、170 | space.css:618-627（space-persona-card/cli-card 无 hover 规则） | 缺失 |
| 4 | 卡片 focus-visible ring（卡片是 button，键盘可达） | KnowledgeHome.tsx:170（`focus-visible:ring-2 focus-visible:ring-[var(--ring)]`） | KnowledgeBasesSection.tsx:200-203（Link 无 focus-visible 类） | 缺失 |
| 5 | 主按钮 hover:opacity-90（新建/空态按钮） | KnowledgeHome.tsx:241、344 | KnowledgeBasesSection.tsx:126-129（space-button 仅 border-color hover，space.css:366-378） | 结构不同 |
| 6 | 搜索框 focus 样式：参考 `focus:border-[var(--foreground)]/25` + transition-colors | KnowledgeHome.tsx:324 | space.css:205-213（space-search 无 focus 规则） | 缺失 |
| 7 | 卡片长简介截断：参考引擎/来源卡描述 `line-clamp-2` | KnowledgeHome.tsx:181、212 | KnowledgeBasesSection.tsx:211、244（space-card-body 不截断，space.css:638-643） | 缺失 |
| 8 | 创建弹窗错误路径：当前有 KnowledgeValidationError 提示（对齐参考 dialog error 态） | CreateKbModal.tsx（重名校验在 modal 内，1566 行，未逐行核对）[未验证] | KnowledgeBasesSection.tsx:299-308、329-333（role=alert） | 已具备（无差距） |
| 9 | 键盘可达性：参考 tab 用 role=tab + aria-selected + aria-controls | KnowledgeHome.tsx:269-277、299-303 | KnowledgeBasesSection.tsx:138-141、146-149（有 role/aria-selected，无 aria-controls 与对应 id 的 tabpanel） | 部分缺失 |

### 动画

| # | 差距 | 参考证据（文件:行） | 当前证据（文件:行） | 类型 |
|---|------|--------------------|--------------------|------|
| 1 | live 状态 StatusDot `animate-pulse`（sky-500，进行中脉冲） | KnowledgeHome.tsx:87 | KnowledgeBasesSection.tsx:212-216（chip 无脉冲；模拟 processing 态为静态蓝 chip） | 缺失 |
| 2 | ChevronRight 悬停显影 `transition-opacity group-hover:opacity-60` | KnowledgeHome.tsx:193、220 | 无对应实现（当前卡片无该元素） | 缺失 |
| 3 | 主按钮 `transition-opacity hover:opacity-90` | KnowledgeHome.tsx:241、344 | space.css:366-368（space-button 仅 border-color 过渡隐式，无 opacity 过渡定义） | 缺失 |
| 4 | 页签/卡片 `transition-colors` | KnowledgeHome.tsx:170、278、363 | space.css 无 persona-card/cli-card/tabs 的 transition 定义 | 缺失 |
| 5 | 加载态 spinner `animate-spin` | KnowledgePage.tsx:325 | 当前用 space-skeleton（space.css:274-290 space-pulse 1.4s），无 spinner；space.css:726-734 有 space-rotate 可复用但未用于本页 | 结构不同 |

---

## P-knowledge-bases-[kbName]（/knowledge-bases/[kbName]）

### 信息结构

| # | 差距 | 参考证据（文件:行） | 当前证据（文件:行） | 类型 |
|---|------|--------------------|--------------------|------|
| 1 | 头部结构：参考为「36px 引擎图标 + 返回链接（箭头+「Knowledge bases」）+ serif 18px 标题 + Default/Assigned/StatusBadge 徽标组 + meta 行（provider · embedding · Updated 时间 · Last indexed 时间）」 | KnowledgeBaseDetail.tsx:179-229 | KnowledgeBaseDetailSection.tsx:158-187（space-back 描边按钮 + 24px 标题 + 默认库/状态 chip；无引擎图标、无 meta 行时间戳/provider 行内文） | 结构不同 |
| 2 | 状态徽标带图标与四态：参考 KbStatusBadge 有 Clock3(live)/CheckCircle2(ready)/AlertTriangle(error) 图标 + Needs reindex/Error/Processing live/Ready 文案 | KbStatusBadge.tsx:28-55 | KnowledgeBaseDetailSection.tsx:182-184（chip 纯文本「知识库状态：处理中」等） | 结构不同 |
| 3 | 分区导航形态：参考为 header 内底部页签（border-b-2 下划线，激活主色，非激活透明描边 hover 变色），带 13px 图标 | KnowledgeBaseDetail.tsx:253-274 | KnowledgeBaseDetailSection.tsx:204-215（space-segment 分段按钮盒） | 结构不同 |
| 4 | 分区集合差异：参考七分区 files/add/github/web/versions/devices/settings（github/web/devices 按 KB 类型出现） | KnowledgeBaseDetail.tsx:73-84（SECTION_CHROME）、170（kbDetailSections） | KnowledgeBaseDetailSection.tsx:42-50（files/add/sources/versions/settings 五分区，sources 合并 web+github，无 devices） | 结构不同（devices 为 MarginNote 专属，属有意保留差异；web/github 合并为「外部来源」是当前实现的有意简化，登记） |
| 5 | 错误态 retry 主按钮：参考在 header 右侧显示红色「Retry indexing」按钮（带 title 提示、disabled/submitting 旋转图标） | KnowledgeBaseDetail.tsx:231-250 | KnowledgeBaseDetailSection.tsx:267-277（「重试失败项」按钮在文档分区工具条内，仅 summary.error>0 时出现；header 无位） | 结构不同 |
| 6 | 文档列表形态：参考为左侧 220px 树形文件栏（文件夹树、图标、size+相对时间、折叠 44px 图标条）+ 右侧预览面板 | KbDocumentList.tsx:459-574（树渲染 268-457）；KbFilesTab.tsx:59-77（master-detail） | KnowledgeBaseDetailSection.tsx:280-369（space-session-list 卡片列表，无树/文件夹/预览/折叠） | 结构不同（文件内容预览依赖真实文件读取，主体属有意保留差异；但列表的树形分组/折叠/尺寸+时间元数据为纯前端结构，登记差距） |
| 7 | 文档行元数据：参考每行有 `formatBytes(size) · 相对时间`（just now/5m ago/2h ago…） | KbDocumentList.tsx:349-357、578-588 | KnowledgeBaseDetailSection.tsx:362-365（formatSize + `登记于 完整本地时间`） | 文案不同（相对时间 vs 绝对时间；功能等价） |
| 8 | 文档行内删除确认：参考为行内 Check/X 二段确认（「Delete?」文本 + 确认/取消小按钮） | KbDocumentList.tsx:359-383 | KnowledgeBaseDetailSection.tsx:321-330（直接删除，无确认） | 缺失 |
| 9 | 索引版本行结构：参考每行有状态图标章（Active=Star/Building=Loader2 spin/Stale=AlertTriangle/Legacy=Clock/普通=CheckCircle2）、Active/Stale/Legacy/Not published/Building 徽标、dimension/binding/时间/签名前 10 位 mono 元数据行 | KbIndexVersionsSection.tsx:503-593（行 504-534 图标；547-571 徽标；573-590 元数据） | KnowledgeBaseDetailSection.tsx:412-428（版本号 + 就绪/未就绪 + docCount/chunkCount chip；无图标章、无签名、无 dimension） | 结构不同 |
| 10 | 索引区头部：参考带 Layers 图标 + 版本计数徽标 + 说明文案 + 「Last indexed: 时间 · n indexed docs」信息条（Clock 图标） | KbIndexVersionsSection.tsx:216-236、297-318 | KnowledgeBaseDetailSection.tsx:384-403（仅 footnote + 重建索引按钮；无计数徽标、无 last-indexed 信息条） | 缺失 |
| 11 | 版本空态：参考为细虚线框单行「No index versions yet.」 | KbIndexVersionsSection.tsx:342-346 | KnowledgeBaseDetailSection.tsx:404-410（space-empty 带模拟说明长文案） | 有意保留差异（模拟标注必须保留，e2e 断言；结构可参考） |
| 12 | Re-index 提示条：参考 mismatch/needsReindex 时显示 amber 警示条 | KbIndexVersionsSection.tsx:289-295 | KnowledgeBaseDetailSection.tsx:386-388（常驻 footnote 模拟说明） | 有意保留差异（语义不同：当前是「模拟声明」常驻） |
| 13 | 失败横幅：参考 isError 时渲染 KbIndexFailureBanner | KbIndexVersionsSection.tsx:280 | KnowledgeBaseDetailSection.tsx:357-361（错误说明在单个文档卡内 statusNote，无 KB 级失败横幅） | 结构不同 |
| 14 | 未选中 KB 空态：参考为居中卡片（图标块 + 标题 + 说明 + 「Create your first knowledge base」按钮） | KnowledgeBaseDetail.tsx:108-133 | KnowledgeBaseDetailSection.tsx:122-135（space-empty + 返回列表按钮；文案针对「不存在」场景） | 结构不同（当前路由总有 kbName 参数，场景不完全对应） |
| 15 | 设置分区：参考 KbSettingsSection 承载 setDefault/delete（read_only 时禁用） | KnowledgeBaseDetail.tsx:326-336（引用） | KnowledgeBaseDetailSection.tsx:562-633（改名/删除在设置，设默认在 header；删除用 window.confirm） | 结构不同（位置不同，功能等价；参考 delete 是 ConfirmDialog） |

### 交互状态

| # | 差距 | 参考证据（文件:行） | 当前证据（文件:行） | 类型 |
|---|------|--------------------|--------------------|------|
| 1 | 分区页签 focus-visible / hover：参考 `hover:text-[var(--foreground)]` + transition-colors | KnowledgeBaseDetail.tsx:263-267 | space.css:229-244（space-segment 无 hover/focus-visible 规则） | 缺失 |
| 2 | Retry 按钮 disabled+submitting 态：参考 `disabled={retrySubmitting \|\| isReindexingLocally}` + Loader2 spin + 文案切换 Retrying… | KnowledgeBaseDetail.tsx:235-249 | KnowledgeBaseDetailSection.tsx:308-320（重试按钮无 disabled/无进行中态；重复点击可重入） | 缺失 |
| 3 | 文档行操作钮 hover 显影：参考 `opacity-0 transition-opacity group-hover/row:opacity-100` | KbDocumentList.tsx:385 | KnowledgeBaseDetailSection.tsx:321-330（操作钮常驻显示） | 缺失 |
| 4 | 文件列表 loading 骨架：参考 3 根 `animate-pulse` 骨架条 + 空态 + 错误 Retry 链接 | KbDocumentList.tsx:545-572 | KnowledgeBaseDetailSection.tsx:242-249（空态有；无加载骨架——本地读取瞬时，[推断]影响小） | 部分缺失 |
| 5 | 搜索框 focus 态（本页无搜索框，参考 Files 区亦无；跳过） | — | — | 不适用 |
| 6 | 删除 KB 确认：参考 ConfirmDialog 组件（含 busy 态）；当前 window.confirm 原生弹窗 | KnowledgePage.tsx:222-238（window.confirm，与当前同款）[注：参考此页也用 window.confirm] | KnowledgeBaseDetailSection.tsx:617-625 | 已具备（与参考同款原生 confirm，无差距；KbSettingsSection 内部实现未逐行核对 [未验证]） |
| 7 | 文档删除无确认（参考行内二段确认，见信息结构 #8） | KbDocumentList.tsx:359-383 | KnowledgeBaseDetailSection.tsx:321-330 | 缺失（与信息结构 #8 同源，按交互态重复登记一次） |
| 8 | 进度条无障碍：当前有 role=progressbar + aria-valuenow（参考无对应 aria） | KbIndexVersionsSection.tsx:367-374（仅视觉 div） | KnowledgeBaseDetailSection.tsx:337-354 | 已具备（当前反超参考，无差距） |
| 9 | 「全部解析并索引」无进行中禁用：参考 re-index 按钮 `disabled={submitting \|\| isReindexingHere}` | KbIndexVersionsSection.tsx:238-242 | KnowledgeBaseDetailSection.tsx:257-266（无 disabled） | 缺失 |

### 动画

| # | 差距 | 参考证据（文件:行） | 当前证据（文件:行） | 类型 |
|---|------|--------------------|--------------------|------|
| 1 | 进度条宽度过渡：参考 `transition-all duration-300` + `Math.max(percent,4)%` | KbIndexVersionsSection.tsx:368-373 | KnowledgeBaseDetailSection.tsx:346-353（已有 `transition-all duration-300` + 同款 max(percent,4)，对齐） | 已具备（无差距；当前 348-352 为 Tailwind 类 + 内联样式混用） |
| 2 | 状态徽标进行中无图标动画：参考 live 时 Clock3（静态）但 Building 版本行 Loader2 `animate-spin` | KbIndexVersionsSection.tsx:525-526、567-571 | KnowledgeBaseDetailSection.tsx:288-291（静态 chip） | 缺失 |
| 3 | Retry/Re-index 按钮 spinner：参考 Loader2 `animate-spin` | KnowledgeBaseDetail.tsx:241-245；KbIndexVersionsSection.tsx:262-266 | KnowledgeBaseDetailSection.tsx:264-265、317-318（RefreshCw 静态；space.css:726-728 有 .space-spin 未用） | 缺失 |
| 4 | 参考无页面级进出场动画（详情页无 animate-pop-in/fade-in 使用）[已核实 grep animate- 于 KnowledgeBaseDetail.tsx 仅 242 行 spinner] | KnowledgeBaseDetail.tsx:242 | 无需新增 | 参考无明确动画来源，不新增（除 #2/#3 spinner） |

---

## P-notebooks（/notebooks）

### 信息结构

| # | 差距 | 参考证据（文件:行） | 当前证据（文件:行） | 类型 |
|---|------|--------------------|--------------------|------|
| 1 | 左栏宽度：参考 250px 独立 aside（border-r，全高）；当前 168px sticky rail（space-bank-layout 内） | NotebookConsole.tsx:250（`w-[250px] shrink-0 flex-col border-r`） | NotebooksSection.tsx:190-233（space-scope-rail；space.css:456-463 `flex: 0 0 168px`） | 结构不同 |
| 2 | 左栏头部：参考「← Learning Space 返回链接 + NotebookPen serif 标题 + 计数徽标（tabular-nums）+ 右侧 Plus 图标钮（title + aria-expanded）」 | NotebookConsole.tsx:252-281 | NotebooksSection.tsx:183-187（页面 header h1「笔记本」+ 描述）、191-201（rail 内「新建笔记本」作为第一个列表项按钮） | 结构不同 |
| 3 | 新建表单形态：参考为 rail 内联展开卡（name+description 输入、Enter 创建 / Escape 取消、Create 主钮 + Cancel）；当前为居中 Modal 表单 | NotebookConsole.tsx:283-324 | NotebooksSection.tsx:354-399 | 结构不同 |
| 4 | 激活项左侧指示条：参考 2.5px 圆角竖条 `h-[62%]` 过渡（active 时显现） | NotebookConsole.tsx:381-386（`absolute left-0 top-1/2 w-[2.5px] -translate-y-1/2 rounded-r-full bg-[var(--primary)] transition-all duration-200`） | NotebooksSection.tsx:212-218（space-scope-item.current 仅为蓝底描边，space.css:482-487；无指示条） | 缺失 |
| 5 | rail 项描述行：参考激活项下有 description 单行截断（11px） | NotebookConsole.tsx:410-414 | NotebooksSection.tsx:212-232（仅名称+计数，无 description） | 缺失 |
| 6 | rail 项不可读徽标：参考 unreadable 时显示 AlertTriangle 替代计数 | NotebookConsole.tsx:399-408 | NotebooksSection.tsx:230（总是计数；本地数据无 unreadable 概念） | 有意保留差异（本地 store 无损坏态） |
| 7 | 记录行结构：参考行内「ChevronRight + 类型徽章（图标+色底，五种类型各有配色/图标）+ 标题 + 时间戳（常驻）+ HeaderAction 组」 | NotebookRecordRow.tsx:229-267（BADGES 定义 45-77）；NotebookConsole.tsx:561-578（HeaderAction：Edit/Export/Delete 带 Tooltip） | NotebooksSection.tsx:456-485（ChevronRight + 标题 + 类型 chip（蓝单色）+ 三个常驻 icon-button；无时间戳在行头，时间在 meta 行 486-488） | 结构不同 |
| 8 | 类型徽章配色：参考五类各有色（chat 天蓝/violet Partner/emerald Research/amber Co-Writer/red Video）+ 图标 | NotebookRecordRow.tsx:45-77 | NotebooksSection.tsx:46-51、473（TYPE_LABEL 四类文案 + 固定 space-chip blue 单色；research_report/chat/co_writer/video_learning） | 结构不同 |
| 9 | 记录行操作：参考为单个 MoreHorizontal 触发钮（hover 显影）弹 menu（Edit/Move to/Copy to/Delete + 子面板内嵌笔记本列表带色点与计数）；当前为三个常驻 icon-button + 独立 Modal（select + radio） | NotebookRecordActions.tsx:80-187（触发钮 83-98；menu 100-184）；NotebookConsole.tsx:561-578 | NotebooksSection.tsx:474-484（按钮组）、665-747（MoveRecordForm Modal） | 结构不同 |
| 10 | 展开区结构：参考「summary 段 + Query 行 + Open chat session 按钮 + 420px max-h 滚动 Markdown 渲染框（muted 底圆角边框）」 | NotebookRecordRow.tsx:296-325 | NotebooksSection.tsx:489-516（space-explanation 纯文本 pre-wrap；「打开原会话」Link 按钮样式；无 Markdown 渲染、无滚动容器） | 结构不同（Markdown 渲染属内容增强，登记为结构差距；真实渲染器接入超出纯前端范围可一句话说明） |
| 11 | 记录编辑器形态：参考为行内展开的连续文档式编辑器（无边框 input+textarea、Body 分段 tab Write/Preview、Unsaved changes 提示、dirty 才可保存） | NotebookRecordRow.tsx:369-498（tab 425-451；dirty 逻辑 136-139、474-478） | NotebooksSection.tsx:604-663（居中 Modal：标题/摘要/正文三字段表单） | 结构不同 |
| 12 | 取消编辑丢弃确认：参考 dirty 时 Cancel 触发 Discard ConfirmDialog | NotebookRecordRow.tsx:156-162、346-357 | NotebooksSection.tsx:652-659（直接关闭 Modal，无丢弃确认） | 缺失 |
| 13 | 删除笔记本确认文案：参考区分有记录（「"x" 和它的 n 条记录将被删除。此操作无法撤销。」）与无记录两态，用 ConfirmDialog | NotebookConsole.tsx:646-666 | NotebooksSection.tsx:151-164（window.confirm，文案承诺「记录回到默认笔记本不丢失」——当前语义是回退而非删除，是有意差异） | 文案不同（语义有意不同：当前产品删除=记录归档到默认本） |
| 14 | 顶部错误横幅：参考 banner 为 role=alert 红条 + X 关闭钮 | NotebookConsole.tsx:435-446 | NotebooksSection.tsx:244-248（space-banner error，无关闭钮） | 部分缺失 |
| 15 | 错误/空态面板：参考 ConsoleNotice（9x9 图标块 + 13.5px 标题 + 12.5px 详情 + 可选 Retry 按钮），错误有 role=alert | NotebookConsole.tsx:700-735（定义）、448-483（error/empty 两用） | NotebooksSection.tsx:254-258（space-empty）、79-80（setError 字符串） | 结构不同 |
| 16 | 笔记本删除后路由：参考 router.replace(notebookRoute(null)) + notify 成功提示 | NotebookConsole.tsx:197-211 | NotebooksSection.tsx:161-162（setSelectedId(null)，URL 不回退到 /notebooks） | 缺失（URL 不一致：删除后地址栏仍指向已删 id） |
| 17 | 成功通知形态：参考 notify() toast（Deleted/Notebook exported/Record saved 等）；当前为页面内 space-banner role=status 常驻条 | NotebookConsole.tsx:204、226；NotebookRecordRow.tsx:182、195、208-213 | NotebooksSection.tsx:148、162、167、340-342 等 | 结构不同（toast 系统不在本批范围，[推断]用现有 banner 语义等价） |
| 18 | 记录搜索阈值：参考 >8 条显示 + 搜索范围为 title/summary/output 三字段；当前 >8 条 + title/content 两字段 | NotebookConsole.tsx:582-595、131-140 | NotebooksSection.tsx:303-314、115-123 | 部分缺失（summary 未纳入搜索） |
| 19 | rail 笔记本筛选：参考 >6 本时显示 Filter notebooks 输入，匹配 name+description | NotebookConsole.tsx:345-358、108-116 | NotebooksSection.tsx:202-211（>6 显示，仅匹配 name） | 部分缺失（description 未纳入） |
| 20 | 保存到笔记本入口：参考 SaveToNotebookModal（跨页保存来源）；当前入口在聊天「保存到笔记」（banner 声明） | SaveToNotebookModal.tsx:148-220 | NotebooksSection.tsx:236-238（banner 说明不提供新建记录） | 有意保留差异（入口位置按当前产品规划在聊天侧） |

### 交互状态

| # | 差距 | 参考证据（文件:行） | 当前证据（文件:行） | 类型 |
|---|------|--------------------|--------------------|------|
| 1 | rail 项 focus-visible ring：参考 `focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--primary)]/40` | NotebookConsole.tsx:373 | space.css:465-487（space-scope-item 无 focus-visible） | 缺失 |
| 2 | rail 项过渡：参考 `transition-[background-color,color] duration-150`；hover 非激活项 `hover:bg-[var(--muted)]/50` | NotebookConsole.tsx:373-377 | space.css:478-480（hover background: var(--surface)，无 transition 定义） | 部分缺失（有 hover 无过渡时长） |
| 3 | 记录行 hover：参考 `hover:bg-[var(--muted)]/40` + transition-colors duration-150 | NotebookRecordRow.tsx:229 | NotebooksSection.tsx:456（space-session-card 无 hover 态，space.css:399-406） | 缺失 |
| 4 | busy 态：参考行执行中 `pointer-events-none opacity-50` | NotebookRecordRow.tsx:227 | NotebooksSection.tsx:无（本地同步操作，[推断]瞬时完成，影响低） | 部分缺失 |
| 5 | 操作钮 active 缩放：参考 `active:scale-[0.97]` + transition-[background-color,color,transform] duration-150 | NotebookConsole.tsx:688（HeaderAction）；NotebookRecordActions.tsx:90 | globals.css:237-249（icon-button 仅 hover 背景） | 缺失 |
| 6 | menu 键盘/焦点管理：参考 Escape 关闭 + pointerdown 外点关闭 + aria-haspopup/aria-expanded + focus-within 显影 | NotebookRecordActions.tsx:57-78、83-94 | NotebooksSection.tsx:475-483（常驻按钮无 menu） | 缺失 |
| 7 | 记录编辑 Enter/Escape 快捷键：参考编辑器与新建表单均绑 Enter 提交 / Escape 取消 | NotebookConsole.tsx:289-292、493-496、500-505 | NotebooksSection.tsx:371-396（表单仅 submit 按钮；Modal 无 Escape 绑定 [未验证 Modal 组件内部实现]） | 部分缺失 |
| 8 | 新建按钮 disabled 态：参考 `disabled={!newName.trim()}`（rail 表单与 meta 编辑同款） | NotebookConsole.tsx:310、526 | NotebooksSection.tsx:392-395（required 属性兜底，无 disabled 视觉） | 部分缺失 |
| 9 | 保存按钮 disabled：参考 `disabled={busy \|\| !dirty}` + disabled:opacity-40 | NotebookRecordRow.tsx:489-494 | NotebooksSection.tsx:655-659（无 dirty 检查，总是可提交） | 缺失 |
| 10 | 深链不存在笔记本：参考 ConsoleNotice error（「This notebook could not be opened」+ detail + Retry）；当前 banner 报错但主区仍显示「选择一个笔记本」空态 | NotebookConsole.tsx:463-483 | NotebooksSection.tsx:100-103、244-258 | 结构不同（信息重复呈现，见 P-notebooks-[notebookId] #1） |
| 11 | 记录时间戳常驻占位：参考注释明确「时间戳常驻避免 hover 交换时行高抖动」 | NotebookRecordRow.tsx:251-255 | NotebooksSection.tsx:486-488（时间在 meta 行非行头；无抖动问题） | 已具备（结构不同但无行为缺陷） |

### 动画

| # | 差距 | 参考证据（文件:行） | 当前证据（文件:行） | 类型 |
|---|------|--------------------|--------------------|------|
| 1 | 激活指示条 `transition-all duration-200`（h-0/opacity-0 → h-[62%]/opacity-100） | NotebookConsole.tsx:383-386 | 无（当前无指示条） | 缺失 |
| 2 | 展开区进出场 `animate-pop-in`（定义于参考 globals.css:674-686：`dt-pop-in 200ms cubic-bezier(0.22,1,0.36,1)`，from opacity 0 / translateY(6px) scale(0.985)） | NotebookRecordRow.tsx:270 | NotebooksSection.tsx:489-517（展开无动画） | 缺失 |
| 3 | 记录菜单 `animate-pop-in origin-top-right` | NotebookRecordActions.tsx:100-104 | NotebooksSection.tsx:423-433（Modal 替代；Modal 组件是否有动画 [未验证]） | 部分缺失 |
| 4 | ChevronRight 展开旋转 `transition-transform duration-200` | NotebookRecordRow.tsx:236-239 | NotebooksSection.tsx:464-470（内联 `transition: 'transform 0.15s'` + rotate 90deg） | 已具备（时长 150ms vs 200ms，微差，登记不改判） |
| 5 | HeaderAction hover/active 过渡 duration-150 + active:scale-[0.97] | NotebookConsole.tsx:688 | globals.css:237-249（icon-button 无 transition/active） | 缺失 |
| 6 | 色板 swatch hover `hover:scale-110` + 选中 ring（meta 编辑色板） | NotebookConsole.tsx:512-521 | NotebooksSection.tsx:566-584（outline 选中样式，无 scale 过渡） | 缺失 |
| 7 | 行内「Open chat session」按钮 `active:scale-[0.98]` + hover 边框/文字变主色 | NotebookRecordRow.tsx:308-317 | NotebooksSection.tsx:504-510（space-button 描边样式，无 active 缩放） | 缺失 |
| 8 | 加载 spinner `animate-spin`（列表加载与详情加载） | NotebookConsole.tsx:239-245、599-603 | NotebooksSection.tsx:250-253（space-skeleton 骨架） | 结构不同 |
| 9 | 返回链接箭头 hover 左移：参考 `group-hover:-translate-x-0.5` | NotebookConsole.tsx:252-262 | NotebooksSection.tsx:170-173（space-back 无箭头位移；space.css:42-45 仅变色） | 缺失 |

---

## P-notebooks-[notebookId]（/notebooks/[notebookId]）

与 P-notebooks 共用 NotebooksSection.tsx（当前 app/notebooks/[notebookId]/page.tsx:5-7 渲染同一组件）。信息结构/交互/动画条目与 P-notebooks 全部重合，不重复列出；以下仅列深链分支独有差异。

### 信息结构

| # | 差距 | 参考证据（文件:行） | 当前证据（文件:行） | 类型 |
|---|------|--------------------|--------------------|------|
| 1 | 深链规范化：参考 initialNotebookId 直通 useNotebookLibrary，选中变化后 router.replace 回写规范 URL；无效 id 由 detailError 走 ConsoleNotice | NotebookConsole.tsx:89-92；useNotebookLibrary.ts:102-117、143-153 | NotebooksSection.tsx:91-93（useEffect 直接 setSelectedId）、125-132（pushState 单向写） | 结构不同 |
| 2 | 课程作用域（?course=）：参考按 course 过滤 rail + course chip + X 退出 | NotebookConsole.tsx:326-343、98-129；NotebooksRoute.tsx:35-63 | 无（课程作用域属任务卡排除项「课程作用域」） | 有意保留差异 |

### 交互状态

| # | 差距 | 参考证据（文件:行） | 当前证据（文件:行） | 类型 |
|---|------|--------------------|--------------------|------|
| 1 | 无效深链反馈：参考 ConsoleNotice（图标+标题+详情）且不并列空态；当前 error banner + 「选择一个笔记本」空态同时出现 | NotebookConsole.tsx:463-483 | NotebooksSection.tsx:100-103、244-258 | 结构不同 |
| 2 | 浏览器后退/前进：参考把动态段当权威（initialId 变化重选中，useNotebookLibrary.ts:143-153）；当前无 popstate 监听，后退后 UI 选中不随 URL 变 | NotebookConsole.tsx:89-92；useNotebookLibrary.ts:140-153 | NotebooksSection.tsx:91-93（仅 routeNotebookId 变化时单向 setSelectedId；同组件内 pushState 的 URL 变化不触发 useParams 更新，[推断]后退时选中状态可能不跟随——未运行验证，标 [未验证]） | 缺失 |
| 3 | 删除选中笔记本后的 URL 修复：参考 replace 到 /notebooks；当前留在旧 URL | NotebookConsole.tsx:203 | NotebooksSection.tsx:161-162 | 缺失（与 P-notebooks #16 同源） |

### 动画

（无深链独有条目；参考深链分支与列表分支共用组件动画。参考无明确动画来源的新增项，不新增。）

---

## 附录 A：共用 space-* 类清单与使用范围

space.css 位置：`apps/web/src/features/space/styles/space.css`（748 行）。四页全部显式 `import '@/features/space/styles/space.css'`（KnowledgeBasesSection.tsx:5、KnowledgeBaseDetailSection.tsx:6、NotebooksSection.tsx:6）。

| 类名 | 本批四页中的使用 | 其他使用方（grep 全 features 核实） | 修改影响面 |
|---|---|---|---|
| .space-page / .space-header / .space-header-row / .space-content / .space-description / .space-back | 四页全部 | /space 全部子页、books、courses、reading、writing 等（所有引 space.css 的组件） | 大；改版式/标题字号会波及全 space 系页面 |
| .space-button / .space-button.primary / .space-button.danger | 四页全部 | 同上，全域按钮 | 大；补 hover:opacity/focus-visible 若写在此类上会全域生效（[推断]全域统一主按钮行为多数情况可接受，但需队长定稿） |
| .space-chip (+ blue/green/amber) | 四页全部（状态/类型/计数徽标） | books、courses、reading、space 子页、writing | 大；若为笔记本类型徽章做多色变体，建议新增类而非改 .space-chip |
| .space-banner (+ error/info) | 四页全部（模拟声明/notice/error） | space 子页、whisper、courses | 大；补关闭钮应加新修饰类 |
| .space-empty | 四页空态 | space 子页、reading、books | 大；补图标/按钮为结构变化，建议新增变体类 |
| .space-session-list / .space-session-card / .space-session-top / .space-session-title / .space-session-actions / .space-meta-row | KB 详情文档/来源/索引列表 + 笔记本记录行 | space 会话历史、courses、reading、writing | 大；e2e 断言直接依赖 .space-session-card 选择器（spec.ts:235、254-255、264、327、356 等），勿改名 |
| .space-scope-rail / .space-scope-item (+ .count) | 笔记本左栏 | space/QuestionBankSection.tsx:268-282（题库同款 rail） | 中；若把 rail 改 250px/加指示条会同时改题库。需为新样式引入新类（如 space-notebook-rail）或加修饰类 |
| .space-bank-layout / .space-bank-main | 笔记本双栏 | space/QuestionBankSection.tsx:268 | 中；同上 |
| .space-tabs | KB 列表页签 | space/CliAppsSection、chat/ArtifactPanel、reading/MaterialLibrary、ReadingWorkspace、whisper/WhisperRoom | 大；参考式下划线页签建议新类，勿直接改 .space-tabs |
| .space-segment | KB 详情分区导航 | space/ChatHistorySection | 中；同上建议新类 |
| .space-search / .space-toolbar / .space-select | 四页搜索/工具条/下拉 | space 子页、reading | 中；focus 态补在此类影响面可控但跨页 |
| .space-skeleton / @keyframes space-pulse | 列表/详情加载 | space 子页 | 小 |
| .space-persona-card / .space-cli-card / .space-card-grid / .space-card-title / .space-card-body / .space-card-actions | KB 列表卡片与引擎卡 | books、courses、reading、space/Personas、CliApps | 大；e2e 断言依赖 .space-persona-card（spec.ts:193-195、197、208），勿改名 |
| .space-form / .space-form-error / .space-form-footer / .space-toggle / .space-category-manager / .space-category-row / .space-group / .space-group-label / .space-footnote | 弹窗表单与分组 | space 子页、writing、courses | 中 |
| .icon-button（globals.css:237-249，非 space 系但四页在用） | KB 详情/笔记本记录操作钮 | 全站 | 大；补 transition/active:scale 建议评估全局影响 |

给队长的定稿建议（证据员仅陈述，不决定）：参考式新结构（下划线页签、250px rail、指示条、pop-in）一律以「新增类」落进 space.css 或组件局部样式，不改既有类语义；既有类只补无行为分歧的 focus-visible/disabled 态。

## 附录 B：现有 e2e 断言的用户可见行为清单

来源：`tests/e2e/knowledge-notebooks.spec.ts`（536 行，10 test）。实现者不得破坏以下断言文案与选择器。

P-knowledge-bases：
- L182 标题 heading「教材资料库」；L183 空态文案「还没有知识库」。
- L184-188 `.space-page` 计算样式 display:flex（space.css 直达路由加载回归）。
- L191-197 按钮「载入演示数据」+ role=status 文案前缀「已载入演示知识库」；卡片选择器 `.space-persona-card` 含「课程标准库」「教学设计案例库」，计数 2（幂等）。
- L200-208 按钮「新建知识库」→ dialog「新建知识库」→ label「名称」「简介」→ 按钮「创建」→ status「已创建知识库「测试资料库甲」」；卡片计数 3。
- L211-216 重名拒绝：alert 含「已存在同名知识库」；「取消」关闭。
- L219-225 检索引擎页签（role=tab name /检索引擎/）：可见文本「内置检索（未接入）」「LightRAG（演示）」「WeKnora（演示）」「IMA 云检索（演示）」「Obsidian」「MarginNote 4」。
- [与现有e2e冲突风险] 若把「检索引擎」页签加计数徽标（摘要建议 2），L219 的 name 正则 /检索引擎/ 仍匹配（getByRole name 为包含匹配，需确认 Playwright name 匹配规则：默认为可访问名称的子串匹配 [推断]），但若改动按钮文本结构（例如把计数移出 aria-name）需复核。

P-knowledge-bases-[kbName]：
- L177-178 分区导航限定 `nav[aria-label="知识库分区"]`，按钮 exact 文本：「索引」「登记文档」「文档」「外部来源」「设置」——分区导航结构改动必须保留该 nav aria-label 与按钮 exact 文案。
- L231-232 heading /课程标准库/；文本「默认库」（exact）。
- L235-236 `.space-session-card` 计数 2；`.space-chip` 含「未解析 · 未索引」。
- L239-243 「还没有索引版本」空态含「真实向量检索服务未接入」。
- L247-255 登记：label「选择要登记的文件」→ status「已登记 1 个文档」→ 文档卡含文件名，计数 3。
- L259-272 来源：文本「还没有登记来源。」；label「来源类型」「来源地址」；按钮「登记来源」；status「已登记来源」；alert「来源地址不能为空」；aria-label「移除来源 https://github.com/owner/repo」→ status「已移除来源登记」。
- L275-289 设置：label「知识库名称」；按钮「保存修改」；改名后 URL 同步；「知识库「课程标准库」不存在」计数 0；按钮「删除知识库」+ 原生 dialog accept → URL /knowledge-bases + 「还没有知识库」。
- L310 progressbar role 可见；L314 status/chip「已解析 · 已索引」；L320 卡片含 /版本 1/。
- L331-337 aria-label「取消解析 解析中文档.md」（exact）→ chip「处理失败」+ 文本 /已取消解析/；aria-label「重试解析 …」→「已解析 · 已索引」。
- L347 checkbox label「模拟一次解析失败（演示失败与重试路径）」；L358 卡片内文本 /解析失败/。
- L411-418 数据损坏：`.space-banner.error` 含「原数据已保留」；「正在读取知识库…」计数 0；localStorage 原值不覆盖。

P-notebooks / P-notebooks-[notebookId]：
- L426-427 heading「笔记本」（exact）；文本「选择一个笔记本」。
- L428-430 `.space-scope-rail` 内 `.space-scope-item` 含「学习笔记」「月度整理」且 contain「1」（计数渲染于 rail 项）——[与现有e2e冲突风险] 若把「新建笔记本」改为头部 Plus 图标钮（摘要建议 2），L494 仍用 rail 内 name「新建笔记本」定位 `.space-scope-item`，该断言会失败；实现此差距需同步调整 spec（由队长决定是否放开）。
- L433-437 点击后 URL /notebooks/notebook-main；记录卡含「演示研究报告」+ chip「研究报告」。
- L440-447 aria-label「展开记录 演示研究报告」→ 卡片 contain「# 报告正文」「演示摘要」；link「打开原会话」href /chat/seed-session-1。
- L450-458 aria-label「编辑记录 演示研究报告」→ dialog「编辑记录 · 演示研究报告」→ label「标题」→「保存」→ status「已保存记录「演示研究报告（改）」」。
- L461-491 aria-label「移动或复制记录 …」→ dialog「移动或复制 · …」→ label「目标笔记本」→ radio /复制/ →「执行」→ status「已把「…」复制到目标笔记本」；rail 计数变 2；移动对称断言。
- L494-502 rail item「新建笔记本」→ dialog「新建笔记本」→「创建」→ status「已创建笔记本「测试笔记本丙」」；`.space-session-title` 含新名；文本「这个笔记本还是空的」。
- L505-508 按钮「导出 Markdown」→ status「已导出「测试笔记本丙.md」」。
- L511-516 按钮「删除」（exact）→ status「已删除「测试笔记本丙」」→「选择一个笔记本」。
- L519-528 aria-label「删除记录 月度对话记录」→ status「已删除记录「月度对话记录」」→ 卡片计数 0。
- L531-535 深链 /notebooks/does-not-exist → role=alert 含「链接指向的笔记本不存在」。
- [与现有e2e冲突风险] 若把记录操作三按钮合并为 MoreHorizontal 菜单（摘要建议 3），L450/L462/L482/L523 的 aria-label「编辑记录 X」「移动或复制记录 X」「删除记录 X」直接定位按钮的断言会失败；需队长决定是否允许同步改 spec 或要求保留同义 aria-label 入口。
- [与现有e2e冲突风险] 若删除笔记本后 URL replace 到 /notebooks（P-notebooks #16），不影响现有断言（L512-516 未断言 URL）；已核对无冲突。

## 范围矛盾与待队长决定事项汇总
1. 三处 [与现有e2e冲突风险]（页签计数、新建入口改头部、记录操作合并菜单）——实现这些参考结构需同步修改 spec 断言，超出「不得建议改动既有断言」的边界，须队长裁定。
2. 参考的记录 Markdown 渲染（NotebookRecordRow.tsx:319-324）与「文件内容预览」（KbFilePreview）是否纳入本批纯前端范围：渲染器本身是前端，但内容来源依赖真实文件/记录产物，任务卡未明示；证据员未计入必做差距，仅登记结构差异。
3. space.css 共享类的修改边界（附录 A）需队长定稿：哪些类允许原位补态，哪些必须新增类。
