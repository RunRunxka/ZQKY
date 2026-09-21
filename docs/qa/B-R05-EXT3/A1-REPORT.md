# B-R05-EXT3-A1 独立验收报告（v1）

- 候选：`fc005d0` ｜ 起点：`1aad54b` ｜ 验收时间：2026-09-19 14:03–14:35
- 验收者：Independent-Acceptor（只读）｜ 资源：5174（验收期间独占，验收结束已停止并释放）
- 运行方式：候选 `.next` 构建产物 + `node scripts/run-web.mjs start 5174`（就绪检查 `/lesson-plans` → 200）；浏览器为 Playwright(1.58.2)+msedge headless 直驱，**非** 实现者截图复用；全部量测为页面内实测（`getBoundingClientRect`/`getComputedStyle`/`document.documentElement.scrollWidth`）
- 结论：**pass**（0 fail；2 项低风险备注，不阻塞）

## 逐项结果

| # | 验收项 | 结果 | 命令/操作 | 证据 |
| --- | --- | --- | --- | --- |
| 0.1 | 候选与资源归属 | pass | `git log --oneline -5`→HEAD=`fc005d0`（分支 `codex/replica-review-20260908`）；`git status --short` 干净；5174 启动前无监听 | 命令输出（本报告记录） |
| 0.2 | 实现者已停止写入 | pass | 验收期间工作树仅新增 `docs/qa/B-R05-EXT3/A1-shots/`（本验收产物）；产品文件零改动 | `git status --short` 终态 |
| 1.1 | 静态核查：tests/ 零改动 | pass | `git diff 1aad54b..fc005d0 --name-only -- tests/` → 0 个文件 | 命令输出 |
| 1.2 | 静态核查：禁区五文件零改动 | pass | `git diff 1aad54b..fc005d0 --name-only` 对 `reading.css`/`ReadingWorkspace.tsx`/`space.css`/`globals.css`/`motion.css` 均无输出 | 命令输出 |
| 1.3 | 静态核查：本批产品改动仅 6 文件 | pass | `git diff 1aad54b..fc005d0 --stat -- apps/web/src/`：MaterialLibrary.tsx(+99)/ReadingLibrary.tsx(+29)/reading-library.css(+243 新建)/WritingEditor.tsx(+34)/WritingLibrary.tsx(+14)/writing.css(+230 新建) | 命令输出 |
| 1.4 | writing.css 前缀与 ！important | pass | 解析全部顶层选择器：32 条首 token 均以 `.writing-` 起头（0 例外）；`grep -c important` → 0 | 命令输出 |
| 1.5 | reading-library.css 前缀与 ！important | pass | 108 条选择器首 token 均以 `.reading-lib-` 起头（0 例外）；`!important` → 0 | 命令输出 |
| 1.6 | §7.2「不做」项确认未做 | pass | 源码核查：新建仍走 Modal 弹窗（WritingLibrary.tsx:130、ReadingLibrary.tsx:188、MaterialLibrary.tsx:350）；删除仍原生 `window.confirm`（WritingLibrary.tsx:95、ReadingLibrary.tsx:154、MaterialLibrary.tsx:251）；阅读集合仍是卡片网格（`.space-card-grid`+`.space-persona-card`，ReadingLibrary.tsx:118-123）；四页均无搜索框；写作编辑器仍借用 `reading-msg`（WritingEditor.tsx:314，§7.2 仅登记）；`?focus=` 参数保留原样（MaterialLibrary.tsx:279） | 源码行号 |
| 1.7 | 页面根修饰类 | pass | 写作两页 `space-page writing-page`（WritingEditor 三处分支均带）；阅读两页 `space-page reading-lib-page`；ReadingWorkspace.tsx 保持 `space-page` 未加类 | 源码行号 |
| 2.1 | 三视口×四页：无横向溢出 | pass | 12 组合（4 页×1440/1920/390）实测：`scrollWidth` 均等于视口宽、`horizOverflow=false`、`right>innerWidth` 元素数均 0 | a1-phase1-viewport.json、A1-*-1440x900/1920x1080/390x844.png（12 张） |
| 2.2 | 三视口视觉与 after/ 一致、层级可读 | pass | 逐张打开人工比对 after/ 同机位截图：布局结构、chip 排布、按钮组一致；实测截图见 A1-shots | A1-cowriter-list-1440x900.png 等 12 张 |
| 3.1 | 窄视口：materials「解析失败+未分配」390 深度实测 | pass | 真实构造：新建 PDF 材料+勾「模拟一次解析失败」→ 失败态行（5 chip+重试+删除钮）；390 实测 `scrollWidth=390`、超界 0、页面内全部按钮 `right` 最大 369≤390 | a1-phase2c-reading.json（F-materials-390-failrow）、A1-materials-390-failrow.png |
| 3.2 | 窄视口：co-writer 长标题（51 字）390 | pass | 列表卡：`textOverflow=ellipsis`、`whiteSpace=nowrap`、`scrollWidth>clientWidth`（省略生效）、right=227.1；编辑器：`.writing-title-text` overflow-x hidden+ellipsis、clientW=315/scrollW=1189（真实截断）、right=335；正文区 right=370；全部按钮 right 最大 370；页面超界 0 | a1-phase3-focus-reduce.json（I-*）、A1-editor-390-longtitle.png、A1-list-390-longtitle.png |
| 3.3 | 窄视口：/reading 卡片 390 | pass | 390 实测 scrollWidth=390、超界 0（进入/退出演示数据两态均测）；进入/删除按钮完整可见 | a1-phase1-viewport.json（viewport-reading-list-390x844）、A1-reading-list-390x844.png |
| 4.1 | 键盘焦点：写作列表 | pass | 连续 Tab：功能导航→返回学习问答→新建文稿→打开文稿链接→删除文稿…每个焦点 `outline: solid 2px rgb(37,99,235)` 可见 | a1-phase3-focus-reduce.json（I-keyboard-focus-list） |
| 4.2 | 键盘焦点：编辑器顶栏/文本区/底部按钮 | pass | Tab 序：返回协同写作→撤销修改→版本历史→AI 生成全文→重命名文稿→文稿正文编辑区→选区改写/润色/扩写→保存版本，9 站点全部 ring=true；文本区 focus 后 `borderColor=rgb(37,99,235)`+3px 蓝晕（writing.css focus 环实测生效） | a1-phase3-focus-reduce.json（J-keyboard-focus-editor、J-textarea-focus） |
| 4.3 | 断言前提（写作） | pass | 编辑器页实测 count=1：`已保存`(exact)/`撤销修改`/`版本历史`/`AI 生成全文`/`文稿正文编辑区`/`AI 修改为显式模拟：流式预览 → 应用/放弃，应用前自动保存版本。`；AI 流程 `AI 改写预览` dialog+`AI 修改预览` aria-label、预览含`【模拟生成】`；版本历史含`改写前自动快照`+`恢复版本`钮 | a1-phase2b-writing.json（B-editor-asserts/B-ai-preview/B-versions） |
| 4.4 | 断言前提（阅读） | pass | `沉浸阅读` heading=1；`.space-page` display=flex（列表页实测）；`.space-persona-card` 计数正常；材料行 `PDF · 模拟解析`、`重试解析 X`/`取消解析 X`/`分配材料 X`/`删除材料 X` aria-label 全部命中；`分配「X」` dialog、`加入` 钮、`已把「X」加入` status、`已入 1 个集合` chip 全部实测出现 | a1-phase2c-reading.json（D0/E4/E5/G3/G4） |
| 4.5 | **重名按钮复查（上一轮失败点）** | pass | 三个空态独立 context 实测：`{name:'新建文稿'}`（含非 exact）→1（空态可见文案为「新建第一篇文稿」，无 aria-label 重名）；`{name:'新建阅读集合'}` 非 exact/exact 均→1（空态钮带 aria-label=「新建第一篇阅读集合」，可访问名已区分）；`{name:'新建材料'}` 非 exact/exact 均→1（空态 aria-label=「新建第一份材料」）。材料页空态主行动与写作空态主行动点击均可打开对应弹窗 | a1-phase2b-writing.json（X-reading-empty-state）、验收过程记录（A-duplicate-button-empty-states：writing 1/1、reading 1/1、materials 1/1） |
| 5.1 | 减少动画（写作） | pass | `reducedMotion:'reduce'` context 实测计算样式：卡片 `transitionDuration=1e-05s`、`animationDuration=1e-05s`、主按钮 `transitionDuration=1e-05s`；hover 后 transform 仍为 none（本页 hover 只变色不加位移，全局压制生效） | a1-phase3-focus-reduce.json（J-reduce-motion-computed）、A1-reduce-motion-list.png |
| 5.2 | 减少动画（阅读） | pass | reduce 下集合卡/材料行 `transitionDuration=1e-05s`；无 reduce 对照组同元素 `0.15s` 且 hover 位移实测生效——说明压制来自全局机制而非样式缺失。备注见「备注 1」 | a1-phase3r-reduce-reading.json、A1-reduce-motion-reading.png |
| 6.1 | 写作列表交互 | pass | 页头「新建文稿」→dialog（标题+模板复选+创建）→跳转 `/co-writer/doc-*`；列表卡 1 张；原生 confirm 接受后删除→卡片 0+空态「还没有文稿」出现；空态「新建第一篇文稿」→dialog 打开 | a1-phase2b-writing.json（B-created/C-list-cards/C-delete-card）、A1-cowriter-empty-after-delete.png |
| 6.2 | 写作编辑器交互 | pass | fill 正文→「已保存」(exact) 回归；Ctrl+A→「选区改写」→dialog→「开始生成」→预览流式含`【模拟生成】`→「应用」→正文含标注→「撤销修改」→恢复原文；「版本历史」→`改写前自动快照`→「恢复版本」→「已保存」；「重命名文稿」→新标题 heading 出现 | a1-phase2b-writing.json（B-autosave~B-rename）、A1-editor-ai-preview.png、A1-editor-versions.png、A1-editor-after-apply.png |
| 6.3 | 阅读集合交互 | pass | 「新建阅读集合」→dialog→创建→跳转；卡片 hover 实测 transform none→translateY(-2px)+border/阴影变化（150ms 过渡存在）；confirm 删除→卡片 0；空态「新建第一篇阅读集合」→dialog | a1-phase2c-reading.json（D1~D4）、A1-reading-card-hover.png |
| 6.4 | 材料库筛选四 tab | pass | tabs=4：「全部（n）/未分配集合（n）/解析中（n）/解析失败（n）」；真实计数核验：解析失败 tab 在失败行存在时=1、解析中=0、未分配=2，与行实际状态一致，无编造 | a1-phase2c-reading.json（E1/F-tab-filter） |
| 6.5 | 材料库：文本/模拟解析/失败/重试/取消 | pass | 文本材料创建→行出现；PDF 表单含「文件名（模拟导入，不读取真实文件）」+「模拟一次解析失败」复选；导入后失败态：`解析失败` chip+`PDF · 模拟解析` chip+statusNote「【模拟】解析失败：解析器不可用（演示失败路径，可重试）。」+「重试解析」钮；重试→queued/processing（「取消解析」出现）→点取消→回到失败态；再重试（默认不勾失败）→「就绪」chip | a1-phase2c-reading.json（E2~E5/G-retry-cancel/G2）、A1-materials-failed-row-1440.png、A1-materials-pdf-ready.png |
| 6.6 | 材料库：分配弹窗+删除 | pass | 「分配材料 X」→`分配「X」` dialog（无集合时显示空态「还没有阅读集合」+「先到「沉浸阅读」新建集合。」）；载入演示集合后「加入」→status「已把「X」加入…」+行 chip「已入 1 个集合」；confirm 删除→行消失 | a1-phase2c-reading.json（G3/G4/H）、A1-materials-assigned.png |
| 6.7 | 模拟标注保护清单 9 条 | pass | 候选源码逐字 grep 全部命中（含行内 chip `PDF · 模拟解析` 实测、SIMULATED_KINDS 五项 option 文本实测 allTextContents、编辑器说明/列表描述/表单脚注/演示提示均为逐字） | a1-phase2c-reading.json（E2 simKinds、E5 note）、§6.4/6.5 实测值 |
| 7.1 | R-09 三栏结构 | pass | `/reading/demo-reading-ws`：`伴生助手（模拟）` complementary=1；`.reading-layout` display=grid；演示批注 mark=1 可见 | a1-phase4-r09.json（K1）、A1-r09-workspace-1440.png |
| 7.2 | R-09 滚动跟随 | pass | 流式中 `.reading-companion-body` 上滚后 scrollTop=0 保持（scrollable=254，1.5s 后仍 0，未被拉回）；「回到最新」点击后 bottomGap=0，且 `window.scrollY` 与 `.reading-pane` top 前后不变（只作用于伴生容器） | a1-phase4-r09.json（K2/K3）、A1-r09-scroll-up.png |
| 7.3 | R-09 抽屉（<1280px） | pass | 1100px：「打开导航面板」→`阅读导航` dialog 打开→背板点击关闭；「打开伴生助手面板」→`伴生助手（模拟）` dialog 打开→背板关闭（dialogAfter=0） | a1-phase4-r09.json（K4/K4b）、A1-r09-drawer-1100.png |
| 7.4 | R-09 工作区 390 | pass | 工作区页 390 实测 scrollWidth=390、超界 0（本批未触碰该页，纯回归确认） | a1-phase4-r09.json（K5）、A1-r09-workspace-390.png |

## 失败项最小复现

无 fail 项。

## 备注（低风险，不阻塞，供队长知悉）

1. **reduce 下 hover 位移终态仍达成**：`reducedMotion:'reduce'` 时阅读集合卡/材料行 hover 后 transform 仍瞬时变为 `translateY(-2px)`（transitionDuration 已被全局机制压至 1e-05s，即位移瞬间完成、无动画过程）。这与 EXT2 已验收批次（books.css/courses.css 同样存在 `translateY(-2px)` hover 且未加 reduce 旁路）口径一致，机制上符合任务卡「复用 motion.css 全局机制」（压制的是动画过程，不是终态）。如后续要求 reduce 下完全去除位移，需队长另立裁定（涉及 books/courses/reading-lib 三处统一），不属于本批回退。
2. **Phase1 种子文稿标题为「未命名文稿」**：首轮种子脚本 fill 选择器与本页 input 不匹配（验收脚本自身问题，非产品问题；phase2b 起改用 `getByLabel('标题')` 正常填入）。不影响任何验收判定——后续全部交互均在正确种子数据上完成。

## 未执行项与原因

- e2e spec 未运行（任务卡明确 A1 不运行也不改 spec）；`npm run typecheck/lint/test:unit/build` 未重复执行（任务卡声明 `.next` 已是候选构建产物，A1 只读核验运行时表现；静态范围核查见 §1.1–1.3）。
- after/ 截图像素级 diff 未做：以本机实际打开页面实测+与 after/ 人工目测一致为准（不同构建时间戳下像素 diff 意义有限，沿用 EXT2 A1 口径）。
- 编辑器「AI 生成全文」路径与「保存版本」手动快照按钮：本批与既有 writing.spec.ts 已覆盖且非本批改动焦点，实测走通「选区改写」主链路（生成共用同一 preview 弹窗机制），未单独重复全量 AI 三模式（改写/润色/扩写共用同一服务与弹窗，本批仅按钮样式变化）。
- 本任务为纯前端本地模拟视觉验收：无真实供应商调用、无凭证路径，相关后端验收项不适用（不计入 not_run）；所有「AI/解析」均为页面内显式模拟，其通过不代表真实供应商通过（本批无真实通道接入）。

## 与实现者结论的差异

- 无实质差异。实现者宣称的窄视口修复（材料行 wrap）、重名按钮修复（三处空态 aria/文案区分）、禁区零改动均独立复核成立。
- 补充实现者未明述的一点：reduce 下 hover 位移终态仍达成（见备注 1），实现者提交说明称「复用 motion.css 全局机制」，该描述准确但队长应知悉「压制过程、保留终态」的语义。

## 证据清单

- 目录：`docs/qa/B-R05-EXT3/A1-shots/`（30 png + 6 json）
- 三视口 12 张：`A1-cowriter-list/editor/reading-list/reading-materials-{1440x900,1920x1080,390x844}.png`
- 窄视口深度：`A1-materials-390-failrow.png`、`A1-editor-390-longtitle.png`、`A1-list-390-longtitle.png`
- 交互过程：`A1-editor-ai-preview.png`、`A1-editor-after-apply.png`、`A1-editor-versions.png`、`A1-cowriter-empty-after-delete.png`、`A1-reading-card-hover.png`、`A1-materials-failed-row-1440.png`、`A1-materials-pdf-ready.png`、`A1-materials-assigned.png`
- reduce 动画：`A1-reduce-motion-list.png`、`A1-reduce-motion-reading.png`
- R-09：`A1-r09-workspace-1440.png`、`A1-r09-scroll-up.png`、`A1-r09-drawer-1100.png`、`A1-r09-workspace-390.png`
- 量测 JSON：`a1-phase1-viewport.json`（三视口溢出）、`a1-phase2b-writing.json`（写作交互+断言前提）、`a1-phase2c-reading.json`（阅读/材料交互+390 失败态）、`a1-phase3-focus-reduce.json`（焦点+长标题+reduce）、`a1-phase3r-reduce-reading.json`（reduce 对照）、`a1-phase4-r09.json`（R-09 全项）
- 静态核查命令输出已逐条转录至上表证据列（git diff/grep 结果均为 0 或明确值）。

## 资源释放

- 5174 已于验收结束后停止（`Stop-Process` 杀掉监听进程），端口已释放；验收临时脚本已从仓库根清除，工作树仅余本报告与 A1-shots/ 产物。
