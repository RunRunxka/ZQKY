# B-R05-EXT5-E5 逐页差距清单（v1）

- 核对时间：2026-09-19
- 参考仓库：`F:\DeepTutor` 固定提交 `42fab3cf429a1fbf36b257ab8d116a3814964202`（已 `git rev-parse` 核实一致；只读，未写入未升级）
- 当前仓库 HEAD：`7b2ba5e9ac71f86085e24b6934ff3f7f5e097baf`（工作区仅 `apps/web/next-env.d.ts` 已有改动与 `docs/qa/B-R05-EXT5/` 未跟踪目录，均与本审计无关）
- 审计范围声明：本报告只覆盖任务卡 B-R05-EXT5-E5 v1 分配的两组页面——组 A 阅读工作区（`/reading/[workspaceId]` 含 sessions 子路由）与组 B `/space` 四个子页（chat-history / questions / personas / cli-apps）。不涉及 P-whisper、P-co-writer、P-books-pages、阅读媒体原视图（PDF/EPUB/音视频播放器）、真实解析、真实模型通道、`/space/mcp` 与 `/space/skills` 重定向页。全程只读：未运行 build/dev/e2e/单测，未做 git 写操作，除本文件外未写任何文件。
- 证据标注约定：`[推断]` = 由代码结构推断、未逐行验证执行路径；`[未验证]` = 未取得直接证据；`[与现有e2e冲突风险]` = 改动会触碰 `tests/e2e/reading.spec.ts`（17 例）、`tests/e2e/space-pages.spec.ts`（8 例）或 R-10 相关 spec 的断言。

## 摘要

### 组 A（阅读工作区）最值得做的 3~5 条
1. **伴生栏头部信息结构**：参考有会话重命名/删除浮动菜单、保存笔记本/下载 Markdown/跳转问题溢出菜单（参考 `web/components/reading/workspace/ReadingCompanion.tsx:303-494`、`dialogs.tsx:107-175`）；当前仅原生 select + 新会话按钮（`apps/web/src/features/reading/ReadingWorkspace.tsx:1430-1450`）。
2. **错误横幅不可关闭**：参考 ReaderPane 错误条带 X 关闭（`ReaderPane.tsx:849-866`）；当前 sessionError / turn error 无 dismiss（当前 `ReadingWorkspace.tsx:1452-1456, 1488-1497`）。
3. **按钮反馈过渡**：参考大量 `transition-[background-color,color,transform] duration-150 active:scale-90`（`ReadingCompanion.tsx:331,351,370,383`）；当前按钮无 active 缩放反馈（来源明确，可补）。
4. **tab 条长标题截断缺失**（窄视口风险）：参考 tab 标题 `max-w-[168px] truncate`（参考 `ReadingWorkspace.tsx:395-397`）；当前无截断（当前 `ReadingWorkspace.tsx:309-327`）。
5. **tab busy 指示**：参考材料解析中 tab 有 `Loader2 animate-spin`（参考 `ReadingWorkspace.tsx:390-394`）；当前 tab 无 busy 状态（正文有，tab 没有）。

### 组 B（/space 子页）最值得做的 3~5 条
1. **CLI 目录缺搜索/详情/分页**：参考目录页有搜索（250ms 防抖）、分类 chips、Load more 分页、EntryDetail 详情页含安装日志（参考 `web/components/cli-apps/CliAppsSection.tsx:250-348, 442-535, 588-778`）；当前为静态卡片网格（当前 `apps/web/src/features/space/CliAppsSection.tsx:163-205`）。
2. **角色卡查看交互形态**：参考卡片整体可点（role=button + 键盘）+ hover 显操作钮 + read_only 保护（参考 `web/components/space/PersonasSection.tsx:296-310, 356-375`）；当前常驻三按钮、demo 角色也可删改（当前 `PersonasSection.tsx:116-149`）。
3. **题库错误态无重试入口**：参考错误面板带 Retry 按钮（参考 `question-bank/QuestionBankSection.tsx:164-182`）；当前仅横幅（当前 `QuestionBankSection.tsx:262-266`）。
4. **会话历史头部缺计数与刷新按钮**：参考有 `N conversations` chip + Refresh（loading spinner+disabled）（参考 `ChatHistorySection.tsx:209-228`）；当前无（当前 `ChatHistorySection.tsx` 无对应物）。
5. **题库列表 refreshing 变暗**：参考 `transition-opacity + opacity-60`（参考 `question-bank/QuestionBankSection.tsx:223-227`）；当前仅单卡 busy opacity（`space.css:510-512`）。

### 全局性发现
1. **参考阅读工作区没有引用 `dt-pop-in`/`animate-pop-in` 等进出场关键帧**。`grep` 核实：参考 `web/components/reading/**` 与 `web/components/space/**` 中这些关键帧类仅 `AnnotationLayer.tsx:95` 的 `dt-reader-flash`（globals.css:936-957）与 `MyAgentsSection.tsx:516`（agents 区，非本批页面）命中。阅读与 space 子页的参考动画全部是 **transition/feedback 类**（hover/active/opacity/spin），无进出场来源。与 MOTION_MATRIX「v3 起参考源码未引用的进出场动画不补」口径一致。
2. **参考阅读伴生栏是主聊天的完整复用**（`ChatMessageList`、`StandaloneComposer`、`useChatAutoScroll`、`SessionViewerPanel`，见参考 `ReadingCompanion.tsx:40-67`），当前是独立本地模拟实现。按参考逐组件复刻等价于接入真实聊天服务，超出本批边界 → 差距仅登记信息结构/状态形态层，深层行为差异标注「有意保留差异」。
3. **当前会话 URL 历史（push/popstate）超出参考**：参考仅首绑定时 `replaceState`（`useReadingWorkspace.ts:447-461`），无 popstate 监听；当前 `syncSessionUrl` push/replace + popstate（当前 `ReadingWorkspace.tsx:1228-1277`）为目标自有增强，且被 R-09 e2e 锁定（spec:462-492）。
4. **当前滚动跟随阈值 90px 双向生效 vs 参考 80px 且流式中只 arm 不 release**（参考 `ReadingCompanion.tsx:502-524` 长注释、`useChatAutoScroll.ts:30-37`；当前 `ReadingWorkspace.tsx:1460-1465`）。语义不同且 R-09 e2e 已按当前行为断言 → 待队长裁定保留或对齐。
5. **reading.css 被 3 个文件显式导入**（`ReadingWorkspace.tsx:57`、`MaterialLibrary.tsx:22`、`ReadingLibrary.tsx:21`），但 `.reading-*` 类被未导入该 css 的 `WhisperRoom.tsx`、`WritingEditor.tsx` 依赖（Next 全局 CSS 生效），存在隐式耦合（见清单 2）。
6. 当前 `reading.css`（160 行）内 **没有任何 keyframes/animation/prefers-reduced-motion 规则**；动画兜底由 `apps/web/src/styles/globals.css:587-593` 与 `motion.css` 全局 reduce 覆盖（R-09 移动端 reduce 用例 spec:549 依赖该全局层，勿在模块 css 内另写 reduce 覆盖它）。

### 窄视口风险清单
| # | 页面 | 风险元素 | 证据 | 说明 |
|---|------|----------|------|------|
| N1 | 阅读工作区 | 材料 tab 条无截断 | 当前 `ReadingWorkspace.tsx:309-327`（无 max-width/truncate）；参考 `ReadingWorkspace.tsx:395-397` 有 `max-w-[168px] truncate` | 长材料标题横向撑爆，390px 移动端尤甚 |
| N2 | 阅读工作区 | 伴生 640px 上限时正文仅剩 ~345px | 当前 `ReadingWorkspace.tsx:106,158,339-346`（300–640 范围）；1280px 分界减 nav 230 + drag 5 | 可用但拥挤；参考以 `minmax(360px,1fr)` 保正文（参考 `ReadingWorkspace.tsx:341`）|
| N3 | 会话历史 | `.space-session-top` 不换行 | `space.css:408-411`（无 flex-wrap）+ `.space-session-actions` `:442-445` | chip「真实/已归档」+4 个图标钮在 390px 挤压标题（标题自身 ellipsis `:414-421` 可兜底）[推断] |
| N4 | 题库 | 760–1280px 区间无断点 | `space.css` 仅 `:736 @media (max-width:760px)`；`.space-scope-rail` 固定 `:456-462 flex:0 0 168px` | 760–900px 时正文列约 550px，选项网格 `minmax(220px,1fr)`（`:528`）退化为 2 列，可接受 [推断]；<760 已折行处理 |
| N5 | 题库 | 批量选择条 sticky wrap | 当前 `QuestionBankSection.tsx:493-551` + `space.css:571-584`（有 flex-wrap） | 已 wrap，风险低 |
| N6 | CLI/角色 | `.space-card-grid` minmax(250px,1fr) | `space.css:612-616` | 390px 单列 ok [推断] |
| N7 | 阅读 | 移动抽屉宽度 | 当前 `reading.css:119-126` `min(420px,92vw)` | 390px 视口 92vw≈359px，伴生 select+按钮头部（当前 `ReadingWorkspace.tsx:1430-1450`）可能换行 [推断]；R32/R-09 移动端用例（spec:388-404, 547-581）当前通过基线，勿随意改抽屉内布局 |
| N8 | 会话历史/题库 | 搜索框 min-width | `space.css:205-212` `.space-search flex:1 1 220px; min-width:180px` | 390px 单行可容纳 [推断] |

### e2e 冲突风险汇总（本报告内逐条标注的汇总）
| 位置 | 触碰点 | spec 行号 |
|------|--------|-----------|
| 阅读顶栏/tab 形态改参考式 | heading「分数阅读（演示集合）」、按钮「收起导航/展开导航」「材料库…」、aria「添加材料」「移除材料 X」 | reading.spec.ts:18, 176, 183, 186, 216-219, 257-263 |
| 阅读选区浮条改参考底部条 | `role=menu`「选区操作」及内部按钮 | reading.spec.ts:71-97 |
| 伴生滚动跟随语义对齐参考 | R-09 五例（425/462/494/521/547）断言 90px/回到最新/历史 | reading.spec.ts:425-581 |
| 阅读布局类名/role | `.reading-layout > .reading-pane:not(aside)`、`role=separator`「调整伴生栏宽度」、localStorage 键 | reading.spec.ts:252, 326, 333-338 |
| 会话历史筛选/重命名控件形态 | searchbox「搜索会话历史」、textbox「会话名称」、按钮「归档/恢复/删除 会话 X」 | space-pages.spec.ts:165-191 |
| 题库 notice/分类控件 | status「已载入 5 道演示题目」+「关闭提示」、textbox「新分类名称」、combobox「移动到分类」 | space-pages.spec.ts:220-246 |
| 题库来源链接结构 | link「查看出处会话」、文案「来源会话已不存在」 | chat-source-links.spec.ts:92-118, 143-149 |
| 角色卡改 hover 显隐 | 按钮「编辑/删除/查看」需可见可点 | space-pages.spec.ts:272-284 |
| CLI 开关改 role=switch | 按钮「已启用/已停用」 | space-pages.spec.ts:305-312 |

### 与既有 MOTION_MATRIX 条目关系
- `M-reading-layout`（`docs/replica/MOTION_MATRIX.md:27`，部分实现）：本审计补充该条目下可对齐的具体来源——按钮 `active:scale-90`+150ms 过渡（`ReadingCompanion.tsx:331,351,370,383`）、tab busy spin（参考 `ReadingWorkspace.tsx:391`）、`dt-reader-flash` 跳转脉冲（globals.css:941-950）。仍未做阅读专属动画验收，与本条目「不能将原视图缺项视为允许缩减」一致。
- `M-reading-lib`（MOTION_MATRIX.md:39）已覆盖阅读库/材料库过渡，本批不重复登记。
- space 子页当前动画仅 `space-pulse`（space.css:274,282）、`space-rotate`（space.css:727,730）本地形态；参考子页无进出场来源 → 不新增，与 v3 口径一致。

---

## 清单 1：阅读工作区交互保护区（必交）

> 以下位置**语义不可改变**。行号以当前 `apps/web/src/features/reading/ReadingWorkspace.tsx`（1696 行版）为准，另注 e2e/单测锚点。

| # | 机制名 | 文件:行号 | 当前实现要点 | 若改动会破坏 |
|---|--------|-----------|--------------|--------------|
| 1 | R-09 follow-bottom 状态机（effect） | `ReadingWorkspace.tsx:1207-1212` | 仅 `followBottom` 为真时把 `bodyRef.scrollTop=scrollHeight`；依赖 `[followBottom, activeId, messageCount, turn?.text, turn?.process.length]` | reading.spec.ts:425-460（R-09 滚动跟随，上滚不被拉回） |
| 2 | R-09 onScroll 阈值 `< 90` | `ReadingWorkspace.tsx:1460-1465` | `scrollHeight - scrollTop - clientHeight < 90` 决定跟随开关；实时双向 | reading.spec.ts:441-443（>90 判定）、456-458（回到最新后 <2）；阈值改 80 等数值会使 poll 边界 flaky |
| 3 | R-09 回到最新按钮 | `ReadingWorkspace.tsx:1501-1515` | 仅 `!followBottom` 渲染；点击仅滚 `.reading-companion-body`，不碰正文/整页 | reading.spec.ts:447-459（reader.scrollY 不变断言）、569-570 |
| 4 | R-09 切会话恢复跟随 | `ReadingWorkspace.tsx:1201-1205` | `[activeId]` effect 无条件 `setFollowBottom(true)` | 会话切换后不跟随 → spec:474-491 草稿/URL 断言链路的隐含前提 |
| 5 | R-09 会话 URL push/replace | `ReadingWorkspace.tsx:1228-1243`（`syncSessionUrl`）+ `1279-1284`（focusSession push）、`1388-1407`（send 内 1396 push） | 地址一致不写（1236）；主动切换/新建 push | reading.spec.ts:117, 125, 472-491（前进后退历史条数语义） |
| 6 | R-09 popstate 监听 | `ReadingWorkspace.tsx:1246-1277` | 正则解析 `/reading/<ws>[/sessions[/<id>]]`；先 `flushDraft()` 再 `setActiveId`；不存在会话报错回退 | reading.spec.ts:483-491（goBack/goForward 恢复会话+草稿）、573-580（移动端历史） |
| 7 | turnId/sessionId 事件守卫 | `ReadingWorkspace.tsx:1335-1337`（switch 内首行）、`1338-1343`（update 闭包再校验）、`1057-1095`（`turns[sessionId]` 归属，`1195` 只渲染当前会话轮次） | 所有事件（含 end/error）必须 `event.turnId===turnId && event.sessionId===sessionId` | reading.spec.ts:494-519（迟到 end 只落旧会话）、521-545（取消后迟到收尾不污染新会话）；单测 `ReadingWorkspaceCompanion.test.tsx:143-211` |
| 8 | READ-END 幂等 | `ReadingWorkspace.tsx:1096-1097`（`finalizedTurnsRef`）、`1291-1310`（finalizeTurn：幂等、只删自己控制器、内容落所属会话、只清本会话本轮块） | 同一 turnId 只收尾一次；`current[sessionId]?.turnId !== turnId` 不动新轮 | 单测 test.tsx:144-211（重复 end/取消后 end/新轮后旧 end 三例）；spec:510-513 |
| 9 | READ-RETRY 放行边界 | `ReadingWorkspace.tsx:1413-1421` | `turn && !errored` 时拒绝（流式防重入）；错误态放行并以 `lastSendRef` 同文本开新轮 | 单测 test.tsx:116-141；spec 无直接用例但 R32 流式落盘（341-359）依赖 lastSend 不被提前清除（1309） |
| 10 | abort 归属 `abortsRef` | `ReadingWorkspace.tsx:1094, 1314-1317`（新轮 abort 旧轮仅限同会话）、`1409-1411`（cancelTurn 只 abort activeId）、`1214-1221`（卸载全部 abort）+ `1367-1371`（AbortError → finalizeTurn(cancelled) 保留已生成并标注「（已取消）」） | 跨会话互不夺取消能力 | spec:521-545（取消保留内容）、494-519（切会话旧轮继续完成）；test.tsx:182-211 |
| 11 | 草稿归属 `draftOwnerRef` | `ReadingWorkspace.tsx:1098-1103, 1160-1177`（effect 同步 owner + 400ms 防抖落盘 + 卸载兜底）、`1223-1226`（flushDraft）、`1144-1158`（按会话加载草稿） | 切会话/卸载按归属会话保存，不串写 | spec:341-358（R32 草稿归属）、462-491（popstate 草稿同步） |
| 12 | 阅读位置节流与生命周期 | `ReadingWorkspace.tsx:843-856`（handleScroll 300ms 防抖，pending 记录材料 id）、`797-823`（材料切换：rAF 恢复、清理定时器、旧材料 pending 落盘、选区失效） | pct 按旧材料捕获、只落盘不读新视图 | reading.spec.ts:300-312（R30 零位置回顶/旧位置恢复）、280-298（R29 依赖 selections 与 blocks 定位不受滚动影响） |
| 13 | 批注定位解析 | `ReadingWorkspace.tsx:625-721`（segments 区间 + quote 回退 + ambiguous/missing 显式提示）、`724-758`（renderMarked 先到先得） | 重复段落只标一处；旧格式歧义不猜位置 | spec:280-298（R29）、42（演示批注 mark 恢复） |
| 14 | 拖拽轨 pointer + 键盘 | `ReadingWorkspace.tsx:148-184`（pointer capture、300–640 夹紧、Arrow ±16/Shift ±32、立即持久化）、`355-368`（`role="separator"` `aria-orientation="vertical"` `aria-label="调整伴生栏宽度"` tabIndex=0） | 键盘可达为目标自有增强（参考仅 pointer，`ReadingWorkspace.tsx` 参考:656-666） | spec:314-339（R31 拖 40px→420、ArrowLeft→436）；aria-label/role 是定位锚点不可改 |
| 15 | 桌面/移动分界 | `ReadingWorkspace.tsx:133-137`（matchMedia 1280px）、`239-255`（按钮组切换）、`336-377`（桌面才渲染 nav/轨/伴生）、`380-400`（移动抽屉） | 1280px 断言与参考一致（参考:178） | spec:314（1440 桌面）、388-404（390 移动抽屉）；抽屉 `role=dialog` + aria-label「阅读导航/伴生助手（模拟）」是锚点 |
| 16 | 「问 AI」事件总线 | `ReadingWorkspace.tsx:1179-1190`（监听 `zqky:reading-ask` 预填草稿）、`353`（ReaderPane 派发） | 引用随会话归属保存 | spec:94-97（问 AI 预填） |
| 17 | 材料切换/激活 | `ReadingWorkspace.tsx:226-228`（activateMaterial）、`799-823`（位置恢复链） | tab `role=tab aria-selected`（308-334） | spec:183-187（tab 切换+aria-selected）、300-312（R30） |
| 18 | 解析失败重试放行 | `ReadingWorkspace.tsx:916-921`（retryIngest：queued + simulateMaterialIngest）、`967-971`（仅 failed 渲染重试钮） | 显式模拟链路 queued→processing→ready | spec:361-386（R32 材料导入失败/重试） |
| 19 | 有意渲染为「模拟」的声明 | `ReadingWorkspace.tsx:1424`（aria-label 含「（模拟）」）、`1467-1470`（空态说明）、`1428`（chip「模拟回复」） | 文案与可访问名被多处 spec 用作锚点 | spec:39, 102, 118, 393, 402 等 |

**className / aria 锚点分级（当前 `ReadingWorkspace.tsx` + `reading.css`）**

- **e2e 依赖，不可动**：`.reading-companion-body`（`1458`；spec:411 `companionBody`）、`.reading-layout`（`337`；spec:252 `reviewReader` 选择器的一部分）、`.reading-msg`（`1474,1480`；spec:103,497）、`.reading-companion-drag` 的 `role=separator`+`aria-label=调整伴生栏宽度`（`355-368`；spec:326）、`data-testid=companion-turn`（`1480`；spec:500,505,512,528）、`aside aria-label=伴生助手（模拟）`（`1424`；spec:39,102 等）、`aria-label=阅读导航`（`508`；spec:38）、`role=menu aria-label=选区操作`（`988`；spec:71）、`aria-label=高亮（yellow）` 等（`996`；spec:73,290）、`aria-label=批注笔记内容`（`1039`；spec:81）、`aria-label=向伴生助手提问/发送提问/停止生成/重试伴生回复/新建阅读会话/阅读会话选择/回到最新`（`1432,1446,1519,1530,1535,1492,1513`；spec:97,110-116,124,345-357,453,530,569）、`mark[data-annotation-id]`（`746`；spec:42）、`[data-loc]`（`978-982`；spec:57,282）、`.reading-drawer`/`.reading-drawer-backdrop` + `role=dialog`（`381-387`；spec:393,402）、`localStorage 键 zhiqikeyuan:reader:companionWidth`（`127,142`；spec:333,338）。
- **纯视觉可动（无 e2e 依赖）**：`.reading-pane` 内边距/圆角/边框（reading.css:18-36）、`.reading-mark` 圆角 padding（38-42）、`.reading-quote-block` 配色（154-160）、`.reading-companion`/`.reading-composer` 的边框配色（44-52, 81-92；但注意清单 2 的共用方）、header/composer 的内联样式（`1425-1451, 1516-1540`）。
- **结构敏感（改前须改 spec）**：`.reading-layout` 列模板（reading.css:5-16 + 内联 `336-347`）、导航三 tab 结构（`509-519`，spec:47-50 用 tab 名「书签（1）/批注（1）」计数格式）、空态文案（`1467-1470`，spec:118,507）。

---

## 清单 2：reading.css 多方共用影响面（必交）

> 行号：`apps/web/src/features/reading/reading.css`（160 行）。使用方经全仓 grep 核实（`apps/web/src` 内 `.tsx/.ts/.css`）。

| 类名 | reading.css 行号 | 使用方（文件:行号） | 若修改会波及 | 倾向 |
|------|------------------|----------------------|--------------|------|
| `.reading-layout` | 5-16（含 `@media max-width:1279px` 12-16） | 仅 `features/reading/ReadingWorkspace.tsx:337` | 阅读工作区三栏全部；spec:252 选择器依赖该类名 | **不可改类名**；列模板改动需同步 spec R31；移动单列规则被 spec:388-405 移动抽屉场景隐式依赖 |
| `.reading-pane` | 18-24 | `ReadingWorkspace.tsx:508`（SourceNavigator aside）、`944`（ReaderPane）；`reading.css:128-130` 抽屉内覆写 | 阅读正文+导航+抽屉三处外观；spec:252 用 `> .reading-pane:not(aside)` 区分 | 视觉可改；**不可给 `.reading-pane` 加影响布局流的全局规则**（导航与正文共用） |
| `.reading-pane h1/h2/h3/h4/p` | 26-36 | 仅 ReaderPane 渲染块（`ReadingWorkspace.tsx:978-982`） | 正文排版 | 可安全改（仅阅读正文）；行高/边距影响 R29 截图基线 [推断] |
| `.reading-mark` | 38-42 | `ReadingWorkspace.tsx:747`（正文高亮 mark）、`997`（选区色板按钮同类名） | 高亮外观 + 选区色板外观（两类元素共用一类名） | 改圆角/padding 安全；**改 cursor/display 会同时影响色板按钮**，须后代作用域收窄 |
| `.reading-companion` | 44-52 | `ReadingWorkspace.tsx:1424`（CompanionPane）、**`features/whisper/WhisperRoom.tsx:159`**；`reading.css:134-138` 抽屉覆写 | 阅读伴生 + 密室聊天两侧 | **必须用后代作用域收窄**（如 `.reading-workspace .reading-companion`）或双侧回归；`max-height:640` 是阅读侧滚动前提（spec:433 可滚动内容断言） |
| `.reading-companion-body` | 54-61 | `ReadingWorkspace.tsx:1458`、**`WhisperRoom.tsx:165`** | 同上；且 e2e spec:411 直接以该类名驱动滚动断言 | 同上收窄；**flex/overflow/gap 语义不可改**（R-09 滚动行为依赖） |
| `.reading-msg` | 63-79 | `ReadingWorkspace.tsx:1474,1480`、**`WhisperRoom.tsx:175,182`**、**`features/writing/WritingEditor.tsx:314`**（`max-width:100%` 内联覆写） | 阅读伴生 + 密室 + 写作 AI 预览三处 | 同上收窄；配色/圆角可改但三页同时变 |
| `.reading-composer` | 81-92 | `ReadingWorkspace.tsx:1516`、**`WhisperRoom.tsx:189`** | 阅读与密室输入区 | 同上收窄；textarea `min-height/resize`（88-92）语义两侧一致，改动需双侧确认 |
| `.reading-companion-drag` | 95-107 | 仅 `ReadingWorkspace.tsx:357` | 仅阅读桌面三栏 | hover/focus-visible 背景（103-107）可安全改；`touch-action:none`（100）是拖拽正确性前提不可删 |
| `.reading-drawer-backdrop` | 110-117 | 仅 `ReadingWorkspace.tsx:381` | 仅移动抽屉 | 视觉可改；`z-index:60` 与 Modal 层级关系改动前须核对 [推断] |
| `.reading-drawer` | 119-126 | 仅 `ReadingWorkspace.tsx:383` | 仅移动抽屉；spec:393-404 锚点为 role=dialog 不依赖样式 | 可安全改（宽度/阴影） |
| `.reading-drawer .reading-pane` / `.reading-drawer .reading-companion` | 128-138 | 仅抽屉内 | 抽屉内滚动行为（R-09 移动端 spec:547-581 依赖伴生在抽屉内可滚） | **滚动语义（max-height:none; height:100%）不可改** |
| `.reading-selection-bar` | 140-152 | 仅 `ReadingWorkspace.tsx:988` | 仅选区浮条 | 视觉可改；`position:absolute; z-index:30` 与定位计算（`881-883` left 夹紧）联动，改 max-width 需同步 `882` 的 `containerRect.width - 290` |
| `.reading-quote-block` | 154-160 | `ReadingWorkspace.tsx:989`（选区浮条内）、`1475`（伴生消息引用） | 两处引用块外观 | 可安全改配色；两类场景共用，改字号/边距双处生效 |

补充事实：
- 显式 `import '@/features/reading/reading.css'` 仅 3 处：`ReadingWorkspace.tsx:57`、`MaterialLibrary.tsx:22`、`ReadingLibrary.tsx:21`。`WhisperRoom.tsx`/`WritingEditor.tsx` **不导入** reading.css，依赖 Next 全局 CSS 打包后类可用 [推断：Next App Router 全局样式机制]；若未来 reading.css 改为 CSS Modules 或按需加载，密室/写作将裸奔 → 登记为架构风险。
- reading.css 当前无 `@keyframes`、无 `animation`、无 `prefers-reduced-motion`（全 160 行核实）；reduce 兜底在 `apps/web/src/styles/globals.css:587-593` 与 `styles/motion.css`，勿在模块内重复实现。
- 本批不改 `space.css`（748 行）；上表中 space.css 行号仅作影响面引用。

---

## P-reading-[workspaceId]（/reading/[workspaceId]）

参考对照物：`web/components/reading/workspace/ReadingWorkspace.tsx`（827 行）、`ReadingCompanion.tsx`（630）、`ReadingComposer.tsx`（141）、`dialogs.tsx`（530）、`WorkspaceChrome.tsx`（196）、`SourceNavigator.tsx`（467）、`useReadingWorkspace.ts`、`web/components/reading/ReaderPane.tsx`（1019）、`AnnotationLayer.tsx`、`AnnotationList.tsx`、`AnnotationPopover.tsx`、`TextUnitView.tsx`、`ReadingExtensionBar.tsx`。

### 信息结构
| # | 差距 | 参考证据（文件:行） | 当前证据（文件:行） | 类型 |
|---|------|---------------------|---------------------|------|
| A1 | 顶栏为紧凑工具条（返回/集合名即重命名钮/材料 tab 带图标与 busy/溢出菜单/导航折叠/伴生开关），当前为 space 大标题式头部 | 参考 workspace/ReadingWorkspace.tsx:347-512 | 当前 ReadingWorkspace.tsx:232-334 | A；[与现有e2e冲突风险] spec:18,176,183,186,216-219,257-263 |
| A2 | 伴生头部缺会话重命名/删除、下载 Markdown、跳转问题、活动面板入口 | 参考 ReadingCompanion.tsx:364-470；dialogs.tsx:107-175 | 当前 ReadingWorkspace.tsx:1430-1450 | A |
| A3 | 导航缺字幕（transcript）节与字幕搜索、文献 refs 节（文本侧能力） | 参考 workspace/ReadingWorkspace.tsx:537-578；SourceNavigator.tsx（467 行全文件） | 当前 ReadingWorkspace.tsx:461-603 仅大纲/书签/批注 | A（媒体播放器/真实解析部分→有意保留差异） |
| A4 | ReaderPane 缺阅读器工具栏：位置 n/total、当前页书签 toggle、auto-jump 开关、导出、批注面板开关、阅读历史后退/前进/历史 | 参考 ReaderPane.tsx:706-810（工具栏 726-808） | 当前 ReadingWorkspace.tsx:949-958 仅标题+chip 行 | A；auto-jump/导出依赖真实通道→有意保留差异（后续批）；阅读历史为纯前端可补 |
| A5 | 选区操作形态：参考为底部居中条（仅 Ask AI/清除）+ ReaderPane 内 selection 工具；当前为跟随选区的浮条（高亮色板/笔记/问AI/书签） | 参考 workspace/ReadingWorkspace.tsx:624-653 | 当前 ReadingWorkspace.tsx:987-1050 | A；[与现有e2e冲突风险] spec:71-97 依赖 role=menu 浮条 |
| A6 | 伴生空态缺建议问题（openers） | 参考 ReadingCompanion.tsx:257-272, 556-560；WorkspaceChrome.tsx CompanionWelcome | 当前 ReadingWorkspace.tsx:1467-1470 说明文字 | A/B（openers 来源为后端接口→可显式模拟） |
| A7 | 材料库弹窗形态：参考 AddMaterialsDialog（24KB，上传/URL/库多入口）；当前简化 AddMaterialForm | 参考 workspace/ReadingWorkspace.tsx:766-776；library/AddMaterialsDialog.tsx | 当前 ReadingWorkspace.tsx:1595 起 | A；上传/URL 属真实解析边界→有意保留差异 |

### 交互状态
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|------|----------|----------|------|
| B1 | 错误/通知横幅不可手动关闭 | 参考 ReaderPane.tsx:849-866（X dismiss） | 当前 ReadingWorkspace.tsx:292-305, 1452-1456, 1488-1497 | B |
| B2 | tab 上无解析 busy spinner | 参考 workspace/ReadingWorkspace.tsx:390-394 | 当前 ReadingWorkspace.tsx:309-327 | B |
| B3 | workspace 加载态：参考 spinner 页 vs 当前横幅 | 参考 workspace/ReadingWorkspace.tsx:292-299 | 当前 ReadingWorkspace.tsx:211-219 | B（等价，低优先） |
| B4 | 滚动跟随语义：参考流式中距离只 arm 不 release（80px），当前 90px 双向 | 参考 ReadingCompanion.tsx:502-524；hooks/useChatAutoScroll.ts:30-37 | 当前 ReadingWorkspace.tsx:1460-1465, 1207-1212 | B；[与现有e2e冲突风险] spec:425-460 按当前语义断言；待队长裁定 |
| B5 | 伴生流式过程/阶段/取消/重试状态齐备（对齐） | 参考 ReadingComposer.tsx:119-140（cancelStreamingTurn） | 当前 ReadingWorkspace.tsx:1479-1497, 1529-1533, 1413-1421 | 已覆盖（登记一致性，非差距） |
| B6 | composer Enter/Shift+Enter/ composing 守卫（对齐） | 参考 StandaloneComposer（经 ReadingComposer.tsx:119 复用）[未验证内部] | 当前 ReadingWorkspace.tsx:1517-1527 | 已覆盖 |
| B7 | 发送按钮禁用态（对齐） | 参考 ReadingComposer 内部（isStreaming 分支） | 当前 ReadingWorkspace.tsx:1535 `disabled={!draft.trim()}` | 已覆盖 |
| B8 | 长标题截断缺失（tab 条） | 参考 workspace/ReadingWorkspace.tsx:395-397 | 当前 ReadingWorkspace.tsx:309-327 | B + 窄视口 N1 |
| B9 | 会话切换/删除确认：参考删除会话有确认弹窗（WorkspaceConfirmDialog） | 参考 dialogs.tsx（WorkspaceConfirmDialog）+ workspace/ReadingWorkspace.tsx:723-736 | 当前无伴生会话删除功能 | A/B（与 A2 同源） |

### 动画
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|------|----------|----------|------|
| C1 | 按钮 active 反馈：`transition-[background-color,color,transform] duration-150 active:scale-90/95` | 参考 ReadingCompanion.tsx:331,351,370,383；dialogs.tsx:76；WorkspaceChrome.tsx:41 | 当前 space-button 无 active 缩放（space.css:355-386 仅 hover） | C；来源明确，可补 150ms+scale(.9) |
| C2 | tab busy `animate-spin`（Loader2） | 参考 workspace/ReadingWorkspace.tsx:391 | 当前 tab 无（space.css:730 `space-rotate 0.9s` 为本地等价关键帧可复用） | C；随 B2 一起补 |
| C3 | 跳转定位脉冲 `dt-reader-flash`（1.5s ease-out，pulses 后驻留淡色，reduce 关闭） | 参考 globals.css:936-957；AnnotationLayer.tsx:95 | 当前 jumpTo 仅 `scrollIntoView smooth`（当前 ReadingWorkspace.tsx:503-505, 576），无视觉驻留 | C；服务 reader_goto 引用→媒体/模型部分「有意保留差异（后续批）」；导航点击 flash 可模拟补齐 |
| C4 | 页面进出场动画 | **参考无明确动画来源，不新增**（参考 reading/** 无 dt-pop-in/animate-pop-in 命中，grep 核实） | 当前无 | C；声明不新增 |
| C5 | 弹窗进出场 | 参考 dialogs.tsx 无 animate-* 类（grep 核实，仅按钮 transition） | 当前 Modal 无进出场 | C；不新增 |

---

## P-reading-sessions-[sessionId]（含 sessions 子页）

参考对照物：`web/app/(workspace)/reading/[workspaceId]/sessions/page.tsx` 与 `sessions/[sessionId]/page.tsx` 均渲染同一 `ReadingWorkspacePage`（两文件 1-4 行核实）。

### 信息结构
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|------|----------|----------|------|
| A1 | 会话深链路由形态对齐（渲染同一组件） | 参考 sessions/[sessionId]/page.tsx:1-4 | 当前 `ReadingWorkspace.tsx:82-88`（useParams sessionId） | 已对齐 |
| A2 | 深链会话不存在 → 提示并回退最近会话 | 目标自有，无参考对照（参考经服务端校验 [未验证]） | 当前 ReadingWorkspace.tsx:1134-1137, 1258-1262 | A；保留（有提示语义） |

### 交互状态
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|------|----------|----------|------|
| B1 | URL 会话历史：参考仅首绑定 `replaceState`（无 push/popstate） | 参考 useReadingWorkspace.ts:447-461 | 当前 ReadingWorkspace.tsx:1228-1277（push/replace + popstate + flushDraft） | B；**目标自有增强**，被 spec:462-492, 547-581 锁定，**不可按参考降级** |
| B2 | popstate 离开阅读板块/其他空间的不处理分支 | 参考（路由卸载，无对应逻辑） | 当前 ReadingWorkspace.tsx:1249-1250 | 目标自有，无参考对照 |

### 动画
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|------|----------|----------|------|
| C1 | 无 | **参考无明确动画来源，不新增**（sessions 子页与工作区同组件） | 当前无 | C |

---

## P-space-chat-history（/space/chat-history）

参考对照物：`web/components/space/ChatHistorySection.tsx`（307 行）、`ArchivedConversations.tsx`、`SpaceSectionHeader.tsx`、`OrganizedSessionList`（courses/，未逐行 [未验证]）。

### 信息结构
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|------|----------|----------|------|
| A1 | 头部缺「N conversations」计数 chip 与 Refresh 按钮（loading 时 spinner+disabled） | 参考 ChatHistorySection.tsx:209-228 | 当前 ChatHistorySection.tsx 无（SpaceMain actions 未用） | A |
| A2 | 卡片整体点击进入会话（按 sessionRoute 重开到原表面） | 参考 ChatHistorySection.tsx:127-134 | 当前仅「重新打开」链接（当前 298-301） | A |
| A3 | 归档视图独立分桶组件（restore 行内 restoring 状态） | 参考 ChatHistorySection.tsx:156-181, 285-291；ArchivedConversations.tsx | 当前归档条目 chip 标注混排（当前 253, 265-273） | A |
| A4 | 会话类型筛选（主对话/导师线程） | 参考 ChatHistorySection.tsx:245-258 | 当前无（仅 real 会话 → 有意保留差异） | A（有意保留差异） |
| A5 | 课程筛选隐藏位（courseFilter 常量 all） | 参考 ChatHistorySection.tsx:68, 242-244 | 当前无 | A（有意保留差异，目标无课程贯通） |

### 交互状态
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|------|----------|----------|------|
| B1 | 恢复动作无行内 loading（参考 restoringId） | 参考 ChatHistorySection.tsx:168-182 | 当前 ChatHistorySection.tsx:265-273 仅全局 busy 禁用 | B |
| B2 | 加载骨架（对齐：参考 4×h-8 pulse，当前 4×space-skeleton 64px） | 参考 ChatHistorySection.tsx:276-284 | 当前 ChatHistorySection.tsx:212-217 | 已覆盖 |
| B3 | 错误横幅 | 参考（API 层无页面级横幅 [推断]） | 当前 ChatHistorySection.tsx:206-210 | 目标自有 |
| B4 | 搜索/筛选双空态 | 参考（无专门空态 [推断]） | 当前 ChatHistorySection.tsx:218-230 | 目标自有（超出参考） |
| B5 | 重命名内联 Enter/Escape/blur 提交 | 参考 OrganizedSessionList [未验证] | 当前 ChatHistorySection.tsx:236-248 | 已覆盖；[与现有e2e冲突风险] spec:171-176 |
| B6 | 删除 confirm | 参考 ChatHistorySection.tsx:144-154 | 当前 handleDelete（调用 window.confirm [推断]，spec:189-191 通过） | 已覆盖 |

### 动画
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|------|----------|----------|------|
| C1 | Refresh 按钮 loading spinner | 参考 ChatHistorySection.tsx:221-226（`Loader2 animate-spin`） | 当前无刷新按钮（补按钮时随带，可复用 `space-rotate` space.css:730） | C；来源明确 |
| C2 | 进出场动画 | **参考无明确动画来源，不新增**（grep animate- 无命中） | 当前无 | C |

---

## P-space-questions（/space/questions）

参考对照物：`web/components/space/question-bank/`（QuestionBankSection.tsx 260+、QuestionCard.tsx、BankScopeRail.tsx、BankToolbar.tsx、BankSelectionBar.tsx、CategoryManager.tsx、CategoryMenu.tsx、useQuestionBank.ts）。

### 信息结构
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|------|----------|----------|------|
| A1 | 审查过滤器（reviewFilters，已掌握/未掌握维度） | 参考 BankToolbar props（question-bank/QuestionBankSection.tsx:131-142） | 当前 QuestionBankSection.tsx:342-364 无该筛选（scope 栏有「未掌握」部分覆盖） | A |
| A2 | 范围栏形态：参考横向滚动 `overflow-x-auto`，当前纵向 sticky rail | 参考 BankScopeRail.tsx:74 | 当前 QuestionBankSection.tsx:268-289 + space.css:456-462, 736-747 | A；[与现有e2e冲突风险] spec:207-217 以文本定位 scope item，形态可改文本不可改 |
| A3 | 课程作用域 chip（?course=） | 参考 question-bank/QuestionBankSection.tsx:61-89, 108-126 | 当前无 | A（有意保留差异，课程贯通未接入） |
| A4 | 题卡来源链接：参考直接渲染 `/chat/<session_id>` + 书籍定位链接；当前带存在性校验的 SourceSessionLink | 参考 QuestionCard.tsx:378-392 | 当前 QuestionBankSection.tsx:61-79, 475 | A；[与现有e2e冲突风险] chat-source-links.spec.ts:92-118,143-149 依赖当前校验语义，**不可按参考放宽** |
| A5 | 超量截断提示（Showing X of Y）与分页上限 | 参考 question-bank/QuestionBankSection.tsx:255-260 | 当前 QuestionBankSection.tsx:487-489 footnote（全量渲染 [推断]） | A（数据量小，低优先） |
| A6 | 空态分支：参考 4 种（搜索无结果/已归类完/课程无题/全空） | 参考 question-bank/QuestionBankSection.tsx:183-220 | 当前 QuestionBankSection.tsx:372-385 两种 | A |

### 交互状态
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|------|----------|----------|------|
| B1 | 读取失败无重试按钮（参考 Retry） | 参考 question-bank/QuestionBankSection.tsx:164-182 | 当前 QuestionBankSection.tsx:262-266 | B |
| B2 | 列表 refreshing 整体变暗 opacity-60 | 参考 question-bank/QuestionBankSection.tsx:223-227 | 当前仅单卡 `.busy`（space.css:510-512） | B |
| B3 | 加载态：参考 spinner vs 当前骨架 | 参考 question-bank/QuestionBankSection.tsx:160-163 | 当前 QuestionBankSection.tsx:366-371 | 已覆盖（形态差异） |
| B4 | 批量选择/归类/移出/删除（对齐 BankSelectionBar） | 参考 question-bank/QuestionBankSection.tsx:92, 235-251 | 当前 QuestionBankSection.tsx:493-551 | 已覆盖 |
| B5 | 分类管理行内重命名 onBlur + 删除 confirm | 参考 CategoryManager.tsx [未验证] | 当前 QuestionBankSection.tsx:292-340 | 已覆盖；[与现有e2e冲突风险] spec:232-238 |
| B6 | 演示载入幂等 notice + 关闭钮 | 参考（demo 入口在 useQuestionBank [未验证]） | 当前 QuestionBankSection.tsx:166-174, 252-261 | 已覆盖；[与现有e2e冲突风险] spec:220-224 |
| B7 | 250ms 搜索防抖（对齐） | 参考 CliAppsSection 同款模式；题库防抖在 useQuestionBank [未验证] | 当前 QuestionBankSection.tsx:98-102（注释声明对照参考） | 已覆盖 |

### 动画
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|------|----------|----------|------|
| C1 | 列表 refreshing `transition-opacity` + `opacity-60` | 参考 question-bank/QuestionBankSection.tsx:224-226 | 当前无 | C；来源明确（Tailwind transition-opacity 默认 150ms [推断 duration]） |
| C2 | 进出场动画 | **参考无明确动画来源，不新增**（question-bank/ 无 animate- 命中） | 当前无 | C |

---

## P-space-personas（/space/personas）

参考对照物：`web/components/space/PersonasSection.tsx`（276 行参考版为 429 行完整版；本审计以参考仓库实际文件为准）。

### 信息结构
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|------|----------|----------|------|
| A1 | 卡片可点查看（role=button + tabIndex + Enter/Space） | 参考 PersonasSection.tsx:296-310 | 当前 PersonasSection.tsx:116-149 常驻按钮（有「查看」按钮承担） | A；[与现有e2e冲突风险] spec:255-284 依赖「新建角色/编辑/删除/查看」按钮名 |
| A2 | read_only（admin 预设）保护：仅可查看，编辑/删除隐藏 | 参考 PersonasSection.tsx:298-300, 356-360, 399-402 | 当前 demo 角色与自建同样可编辑删除（当前 133-146） | A（语义差距；本地目录无 admin 概念 → 待队长定是否以 source 区分保护） |
| A3 | 悬停显隐操作钮（group-hover/focus-within opacity） | 参考 PersonasSection.tsx:361-366 | 当前常驻 | A；[与现有e2e冲突风险] spec:272-284 直接点击编辑/删除 |
| A4 | 正文 markdown 渲染（PersonaMarkdown 动态加载 + frontmatter 剥离） | 参考 PersonasSection.tsx:50-59, 420 起 viewer | 当前 PersonasSection.tsx:162-165 `white-space:pre-wrap` 纯文本 | A |
| A5 | 名称 slug 校验（小写字母/数字/连字符） | 参考 PersonasSection.tsx:178-186 | 当前 PersonaValidationError（仅重名/空名 [推断]；spec:263-269 验证重名拒绝） | A；[与现有e2e冲突风险] 改校验规则需保持重名拒绝文案「已存在同名角色」 |
| A6 | 头部计数 chip + 主操作钮（SpaceSectionHeader meta/action） | 参考 PersonasSection.tsx:242-262 | 当前 SpaceMain actions（当前 63-77）+ footnote 计数（当前 153） | 已覆盖（形态差异） |

### 交互状态
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|------|----------|----------|------|
| B1 | 删除行内 busy（deleting===name spinner） | 参考 PersonasSection.tsx:368-375 | 当前 PersonasSection.tsx:140-146 无 | B |
| B2 | 保存进行中态（saving spinner + 防重复提交） | 参考 PersonasSection.tsx:187, 259（saving 字段）[推断 UI 呈现] | 当前 PersonaForm 225-274 无 saving | B |
| B3 | 编辑加载详情 loading | 参考 PersonasSection.tsx:103-135（openEdit 拉详情） | 当前本地同步读（当前 205-207） | 目标自有（本地数据即所得） |
| B4 | 加载骨架（对齐） | 参考 PersonasSection.tsx:270-273（spinner） | 当前 PersonasSection.tsx:90-95（骨架） | 已覆盖 |
| B5 | 空态引导（图标+文案+双按钮） | 参考 PersonasSection.tsx:274-294 | 当前 PersonasSection.tsx:96-113 | 已覆盖 |

### 动画
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|------|----------|----------|------|
| C1 | 卡片 hover 阴影/边框过渡（`transition-all hover:border hover:shadow-md focus-visible:ring-2`） | 参考 PersonasSection.tsx:302-306 | 当前 space-persona-card 无 hover 态（space.css:618-628） | C；来源明确 |
| C2 | 操作钮 hover 显隐 `transition-opacity` | 参考 PersonasSection.tsx:361-366 | 当前常驻 | C；随 A3 决策联动，勿单独实施 |
| C3 | 进出场动画 | **参考无明确动画来源，不新增** | 当前无 | C |

---

## P-space-cli-apps（/space/cli-apps）

参考对照物：`web/components/cli-apps/CliAppsSection.tsx`（1024 行；页面 `web/app/(utility)/space/cli-apps/page.tsx` 渲染它）。

### 信息结构
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|------|----------|----------|------|
| A1 | 目录搜索（250ms 防抖）+ 分类 FilterChip + 「Include unavailable」开关 | 参考 CliAppsSection.tsx:330-348, 452-488, 957-994 | 当前 CliAppsSection.tsx:163-205 静态网格 | A |
| A2 | 目录分页（Load more + 游标 + shown/total） | 参考 CliAppsSection.tsx:386-412, 512-530 | 当前无 | A |
| A3 | 条目详情页（EntryDetail：Requirements/Notes/Installs/Tool name/信任徽章/安装日志 details） | 参考 CliAppsSection.tsx:422-440, 588-778 | 当前目录卡内直接列 requires/installNotes（当前 189-192） | A |
| A4 | 已装列表形态：参考行式列表 + Toggle `role=switch aria-checked`；当前卡片 + aria-pressed 按钮 | 参考 CliAppsSection.tsx:212-304, 815-845 | 当前 CliAppsSection.tsx:115-161, 142-158 | A；[与现有e2e冲突风险] spec:305-312 依赖按钮名「已启用/已停用」 |
| A5 | tab 形态：参考下划线 TabButton + 计数徽章；当前 space-tabs | 参考 CliAppsSection.tsx:101-115, 920-955 | 当前 CliAppsSection.tsx:71-88 | A；spec:297,305 依赖 role=tab 名称，形态可改名称不可改 |
| A6 | 权限/信任呈现：参考 admin 安装 + granted/未授权提示 + TrustChip（Pinned/第三方/未钉版本） | 参考 CliAppsSection.tsx:44-50, 233-239, 254-261, 798-813 | 当前 CliAppsSection.tsx:120-130（内置/第三方 chip）+ 209-211 footnote 声明演示形态 | A；无真实服务 → 有意保留差异（本地登记） |
| A7 | 头部计数「N available to you」 | 参考 CliAppsSection.tsx:94-98 | 当前无（tab 计数有） | A |

### 交互状态
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|------|----------|----------|------|
| B1 | per-app busy 禁用（busy===id） | 参考 CliAppsSection.tsx:158-174, 266-298 | 当前 CliAppsSection.tsx:143-157 无 busy | B；[与现有e2e冲突风险] 若加禁用需保证 spec:299-312 流程不 Timing out |
| B2 | 安装 loading（installing spinner + 耗时说明） | 参考 CliAppsSection.tsx:602-621, 741-763 | 当前同步本地登记（当前 44-52），即时完成 | 有意保留差异（无真实安装） |
| B3 | 错误/通知横幅（对齐 Banner tone） | 参考 CliAppsSection.tsx:117-119, 866-885 | 当前 CliAppsSection.tsx:90-102 | 已覆盖 |
| B4 | 空态（icon+标题+正文+跳目录按钮） | 参考 CliAppsSection.tsx:177-197, 895-918 | 当前 CliAppsSection.tsx:105-113 | 已覆盖 |
| B5 | 加载 spinner | 参考 CliAppsSection.tsx:887-893 | 当前同步读取无 loading [推断 listCliApps 同步] | 目标自有 |
| B6 | 卸载 confirm | 参考 CliAppsSection.tsx:277-298 | 当前 CliAppsSection.tsx:54-62 | 已覆盖 |

### 动画
| # | 差距 | 参考证据 | 当前证据 | 类型 |
|---|------|----------|----------|------|
| C1 | Toggle 颜色/位移 transition（transition-colors/transform） | 参考 CliAppsSection.tsx:826-843 | 当前按钮形态无对应 | C；仅当采纳 role=switch 形态时适用（与 A4 联动） |
| C2 | 骨架/加载动画 | 参考 Loader2 animate-spin（887-893） | 当前无 loading 态 | C（随 B5 决策） |
| C3 | 进出场动画 | **参考无明确动画来源，不新增** | 当前无 | C |

---

## 附录 A：样式文件归属与影响面

| 样式文件 | 导入方 | 本批页面使用 | 共用方 | 结论 |
|----------|--------|--------------|--------|------|
| `apps/web/src/features/reading/reading.css`（160 行） | `ReadingWorkspace.tsx:57`、`MaterialLibrary.tsx:22`、`ReadingLibrary.tsx:21` | 阅读工作区全部 `.reading-*` 类 | `WhisperRoom.tsx:159,165,175,182,189`、`WritingEditor.tsx:314`（隐式依赖，未导入） | 共用 4 类（companion/body/msg/composer）必须后代作用域收窄或双侧回归；详见清单 2 |
| `apps/web/src/features/space/styles/space.css`（748 行，本批只读） | 13 个文件（BooksRoute/Courses*/Knowledge*/Notebooks/Reading 三页/SpaceMain/WhisperRoom/Writing 两页等，grep 核实） | 四个 space 子页 + 阅读工作区大量复用（space-button/banner/tabs/session-card/chip 等） | 全站公共 | **本批不改**；阅读侧类名复用清单见清单 2 备注 |
| `apps/web/src/features/reading/styles/reading-library.css` | ReadingLibrary/MaterialLibrary（`ReadingLibrary.tsx:22` 等） | 阅读库页（非本批审计对象） | 无 | 不涉及 |
| `apps/web/src/styles/globals.css`、`styles/motion.css` | 全局 | reduce 兜底（globals.css:587-593；motion.css:10-31） | 全站 | **禁止修改**（任务约束）；模块动画依赖其 reduce 兜底，勿在模块内重复 |

## 附录 B：/space 子页 e2e 断言锚点清单（逐条 + 行号）

来源：`tests/e2e/space-pages.spec.ts`（320 行，8 例）与 R-10 `tests/e2e/chat-source-links.spec.ts`（210 行）。`chat-message-locate.spec.ts`（381 行）属聊天页定位，本批未逐行核对 [未验证]。

**仪表盘（spec:130-155）**
- spec:134 heading「学习空间」；spec:136-139 `.space-tile` 含文本「会话历史/题库/笔记本/角色目录」并 containText 计数
- spec:141-142 `.space-tile` 技能/MCP `href=/settings#skills|#mcp`
- spec:144-146 题库 tile 点击 → `/space/questions` + heading「题库」
- spec:151-153 笔记本 tile → `/notebooks` + heading「笔记本」exact

**会话历史（spec:157-200）**
- spec:162 `.space-session-card` count 2（timeout 15000）
- spec:165-168 `role=searchbox name=搜索会话历史` 过滤 → `.space-session-title` 文本
- spec:171-176 `button 重命名会话 会话甲` → `textbox 会话名称` Enter → `.space-session-title` 更新
- spec:179-186 `归档会话 X` → count 1；`/^已归档/` → 可见；`恢复会话 X`；`/^进行中/` → count 2
- spec:189-191 `删除会话 会话乙` + dialog accept → count 1
- spec:194-200 mock 库不展示：`.space-session-card 旧模拟记录` count 0；`role=group 按模式筛选` count 0；indexedDB `zhiqikeyuan-chat-mock` 仍存在

**题库（spec:202-247）**
- spec:207-209 `.space-scope-item` 全部/答错/书签 containText 计数
- spec:211-216 答错视图 `.space-question-card` count、`.space-question-text`、`.space-option.user-wrong/.correct` 文本
- spec:220-224 `button 载入演示题目` → `role=status` 含「已载入 5 道演示题目」→ `status 内 button 关闭提示` → 再次载入 → 「演示题目已全部在库中」
- spec:227-229 `.space-question-card 小草钻出泥土` 内 `button 收藏` → 书签 scope containText 2
- spec:232-238 `button 管理分类` → `textbox 新分类名称` + `button 添加 exact` → `.space-scope-item 月度复习` 可见 → `combobox 移动到分类` selectOption → `.space-chip.green 月度复习` → `.space-scope-item 未分类` containText 6
- spec:241-246 `.space-question-card 1/4 + 2/4` 内 `button 删除` + dialog accept → `.space-question-card` count 6

**角色目录（spec:249-290）**
- spec:252 `.space-persona-card` count 3
- spec:255-261 `button 新建角色` → dialog「新建角色」`textbox 名称/简介` → `button 保存` → 卡片可见 count 4
- spec:263-269 重名 → `dialog2.getByRole('alert')` 含「已存在同名角色」→ 取消
- spec:272-277 卡内 `button 编辑` → dialog「编辑角色 · 测试角色甲」→ 简介更新 → 卡片文本更新
- spec:280-285 `button 删除` + dialog accept → count 3
- spec:288-289 `button 载入演示角色` → 幂等 count 3

**CLI 应用（spec:292-313）**
- spec:294 文本「还没有安装任何 CLI 应用」
- spec:297-302 `role=tab 应用目录` → `.space-cli-card 口算题生成器` 内 `button 安装（本地登记）` → `role=status` 含「模拟安装」→ `button 已安装` disabled
- spec:305-312 `role=tab 已安装` → 卡内 `button 已启用` → `button 已停用` 可见 → `button 卸载` + dialog accept → 空态回归

**R-10 来源回链（chat-source-links.spec.ts）**
- :92-101 `/space/questions` 内 `link 查看出处会话` href 指向会话深链
- :103-109 旧数据无 sessionId → link count 0 且无「来源会话已不存在」
- :112-118 会话已删除 → 文本「来源会话已不存在」可见、link count 0
- :143-149 link href 断言（两例）
- :159, 167-168 相关文案复验 [未验证细节，未逐行读该段]

**改锚点红线**：上表任何 name/role/testid/class 文案变更都属破坏性，必须同批改 spec 并说明；本报告所有 `[与现有e2e冲突风险]` 条目均已对应到上述行号。

## 范围矛盾与待队长决定事项汇总

1. **参考伴生栏 = 主聊天复用**（`ReadingCompanion.tsx:1-21` 文件头声明 + imports）：逐组件复刻需接入真实聊天服务/统一 ChatService，与任务卡「阅读工作区不引入新业务能力（真实模型通道）」矛盾。倾向：保留当前本地模拟实现，仅补信息结构形态（A2/A6）与状态层差距（B1/B2/B8）。
2. **滚动跟随语义**：参考「流式中距离只 arm 不 release（80px）」vs 当前「90px 双向」（清单 1 #2、组 A B4）。当前语义已被 R-09 spec:425-460 锁定；对齐参考必须同时改 spec。倾向：保留当前（已验收基线），登记为有意差异。
3. **会话 URL 历史**：参考无 push/popstate（仅 replaceState），当前实现超出参考并被 spec:462-492 锁定。倾向：保留当前（目标自有增强），不按参考降级。
4. **角色卡交互形态**：参考 hover 显隐操作钮 + 卡片可点 vs 当前常驻按钮。e2e spec:272-284 依赖常驻按钮可点。倾向：保留常驻按钮（可达性更直白），hover 显隐若采纳需同批改 spec。
5. **CLI 目录搜索/详情/分页**：参考有明确对应物但依赖远程 catalog API；本地可显式模拟（CLI_CATALOG 静态目录已存在，当前 `cli-apps-store.ts` [未逐行]）。属于「复刻前端信息结构」与「新业务能力」边界地带，待队长裁定是否纳入后续批。
6. **persona read_only 保护**：参考有 admin 预设只读语义；当前本地目录所有角色可改删。若采纳需定义本地等价规则（如 demo 角色可删但「演示」chip 保留），待队长定。
7. **参考 `dt-reader-flash` 跳转脉冲**：来源明确（globals.css:941-950）但服务的 reader_goto 引用链路属真实模型通道；导航点击 flash 可纯前端模拟。倾向：作为 `M-reading-layout` 的可选子项单独排批。
8. **`space.css` 断点单一（760px）**：760-1280px 区间题库 rail 挤压为可接受但非最优 [推断]；改断点属全局影响，超出本批权限，仅登记。
