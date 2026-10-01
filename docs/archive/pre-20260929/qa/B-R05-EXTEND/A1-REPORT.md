# B-R05-EXTEND-A1 独立验收报告（v1）

- 候选：`82871fa` ｜ 起点：`3f968b0` ｜ 验收时间：2026-09-18（本报告落盘前实测完成）
- 验收者：Independent-Acceptor ｜ 资源：端口 5174（本批归属队长，验收期间独占；**验收结束已停止进程并释放**）
- 结论：**needs_revision**（2 项 fail，均为 390×844 视口下笔记本模块的候选引入回归；其余全部通过或高于 390 不可见）

## 前置核查

| 核查项 | 结果 | 证据 |
| --- | --- | --- |
| 工作树包含候选实现且实现者已停止写入 | pass | `git status`：无未提交源码/测试改动（仅 `qa/space-r05-20260918/` 队长产物 untracked）；HEAD=`82871fa`，分支 `codex/replica-review-20260908` |
| `tests/` 在 3f968b0→82871fa 零改动 | pass | `git diff 3f968b0 82871fa --stat -- tests/` 输出 0 行 |
| `apps/web/src/features/space/styles/space.css` 零改动 | pass | 同上命令，0 行 |
| `apps/web/src/styles/globals.css` 零改动 | pass | 同上命令，0 行 |
| 工作树相对候选未再改产品文件 | pass | `git status --porcelain apps/web/src tests/` 空 |
| §7 裁定 1：rail 内保留「新建笔记本」项 | pass | `NotebooksSection.tsx:255-265`（`space-scope-item` + Plus + 「新建笔记本」，在 `nav[aria-label="笔记本列表"]` 内）；实测 rail 项含「新建笔记本」 |
| §7 裁定 2：记录操作未合并为菜单 | pass | 组件中无 `MoreHorizontal/MoreVertical/DropdownMenu/role="menu"`（grep 0 命中）；三个 icon-button 保留（见逐项 2） |
| §7 裁定 3：未改任何测试文件 | pass | 上面 `git diff --stat -- tests/` 0 行 |
| 新 CSS 无 `!important` | pass | `grep -c "!important"`：knowledge.css=0，notebooks.css=0 |
| 新 CSS 选择器作用域 | **见差异记录** | 严格按「以 `.kb-page`/`.kb-detail`/`.nb-page` 起头」口径解析：knowledge.css=0 处违规；notebooks.css 有 17 处以 `.nb-*` 起头而非 `.nb-page` 起头（`.nb-badge*`、`.nb-pop-in`、`.nb-notice*`、`.nb-banner*`），详见「与实现者结论的差异」第 2 条。任务卡 §2.3 写「类前缀 `.nb-*`」、附录 A 写「一律以 `.nb-page` 起头」，两处口径本身不一致；这些选择器仍带 `nb-` 前缀不会波及本批四页之外，判定为**文档口径歧义，非样式外溢缺陷**，交队长裁定 |

## 逐项结果

结果列只用 pass / fail / not_run。证据中 `A1-shots/` 指 `docs/qa/B-R05-EXTEND/A1-shots/`。

| # | 验收项 | 结果 | 命令/操作 | 证据 |
| --- | --- | --- | --- | --- |
| 1 | 三视口 1440×900：四页无横向溢出/重叠/截断异常，与 after/ 一致 | pass | `node docs/qa/B-R05-EXTEND/A1-shots/a1-check.mjs screenshots` + `scrollWidth-clientWidth` 实测 | 四页 `scrollW-clientW=0`；1440 截图与 `after/` 逐张目视一致（差异仅我种子记录数，见差异记录第 4 条） |
| 2 | 三视口 1920×1080：同上 | pass | 同上 | 四页 `scrollW-clientW=0`；截图一致 |
| 3 | 三视口 390×844：知识库列表/详情页 | pass | 同上 | 溢出=0；长文档名正确省略号截断（kb-detail-390x844.png）；页签两行折行可读 |
| 4 | 390×844：笔记本列表 rail 可用性 | **fail** | Playwright 实测 `getBoundingClientRect` | rail 项宽 **447px**（rail 350px、视口 390px），长名称项右缘 467px 被视口硬裁剪，计数徽标被推出视口外；`space-scope-item-name` 为 nowrap+ellipsis 但按钮本身未约束最小宽，无法收缩。起点 3f968b0 同位置为两行换行显示正常（before/notebooks-390x844.png 对照）。详见「失败项最小复现」F1 |
| 5 | 390×844：笔记本详情内容区排布 | **fail** | 实测记录行内部布局 | 记录行标题 `space-session-title` 宽 **0px**（不可见），类型徽章被挤成每字一行的竖排（宽 38px），时间戳（145px，`flexShrink:0` 常驻行头）挤压 `flex:1` 标题所致。起点时间戳在独立第二行无此问题。详见 F2 |
| 6 | after/ 与我的截图一致性 | pass | 逐字节对比 12 张全页截图 | 0 张字节相同（截图时间戳类随机噪声）；布局目视一致；notebook-detail 差异为我种子把 rec-1 显式挂在 nb-monthly（记录数 2 vs 1），非产品差异；**关键：after/ 自己的 notebook-detail-390x844.png 同样呈现 #5 缺陷**（标题不可见、徽章竖排），证明是候选真实缺陷而非我的种子差异 |
| 7 | 键盘可达：知识库页签/卡片/主按钮 | pass | `a1-check.mjs a11y`（Tab×21 步进 + `document.activeElement` 采样） | Tab 序列到「载入演示数据→新建知识库→知识库2→检索引擎6→课程标准库→空种子库」全部可达；首焦点 `outline: solid 2px rgb(37,99,235)`（蓝色焦点环可见） |
| 8 | 键盘可达：详情页分区/文档行操作钮 | pass | `activeElement` 聚焦实测 | 分区 5 钮可达；`button[aria-label^="移除文档"]` focusable=true |
| 9 | 键盘可达：笔记本 rail 项/记录行操作钮/展开钮 | pass | 同上 | 编辑/移动或复制/删除/展开 4 类按钮 focusable 均 true |
| 10 | 详情页 `nav[aria-label="知识库分区"]` 五钮 exact 文本 | pass | a11y 脚本 | `["文档","登记文档","外部来源","索引","设置"]` 与期望完全一致；nav count=1 |
| 11 | 列表页页签 accessible name 含「知识库」「检索引擎」子串 | pass | `getByRole('tab')` 采集 | `["知识库2","检索引擎6"]`（徽标数字以空格分隔计入 name，spec:219 子串匹配成立） |
| 12 | 焦点环可见 | pass | 截图 `*-focus.png` 12 张 + outline 实测 | `outline: solid 2px rgb(37,99,235)`；rail 项 `focus-visible` 有 ring 样式（notebooks.css:21-25） |
| 13 | 减少动画：kb-pulse 被压制 | pass | `reducedMotion:'reduce'` 上下文 `getComputedStyle` 实测 | `.kb-status-dot.processing`：`animationName=none, duration=1e-05s(0.01ms), iterationCount=1`；对照组（无 reduce）`kb-pulse 1.4s` |
| 14 | 减少动画：nb-pop-in 被压制 | pass | 展开记录行后实测 | reduce 下 `animationName=none, duration=1e-05s`；对照 `nb-pop-in 0.2s` |
| 15 | 减少动画：指示条过渡/hover 位移被压制 | pass | 实测 | rail current 项 `::before` transitionDuration=1e-05s；卡片 transitionDuration=1e-05s（prop=none） |
| 16 | 页签切换（知识库↔检索引擎）真实点击 | pass | click + aria-selected | 两个方向 `aria-selected=true`，面板内容切换（检索引擎面板显示「本地引擎/内置检索（未接入）」） |
| 17 | 搜索框：>6 库出现 | pass | 8 库种子 | `input[type=search]`=1，输入「批量库3」过滤后卡片=1；2 库种子下=0（按 >6 条件正确隐藏） |
| 18 | 空态（清空 localStorage） | pass | 空 localStorage 访问 | 文案「还没有知识库」+ 图标（6 个 svg）+ 主行动「新建知识库」均在（kb-list-empty-1440.png） |
| 19 | 状态圆点分色（处理中=蓝、空=灰） | pass | computed backgroundColor | `.kb-status-dot.processing`=rgb(37,99,235) 蓝；默认（空库）=rgb(110,110,110) 灰 |
| 20 | 详情页五分区切换 | pass | 逐个点击 | 5 钮均能点击且 `current` class 正确迁移到点击项（active 标记为 class 而非 aria-selected，与 space.css 设计语言一致） |
| 21 | 文档行二段移除确认：出现「确认移除？」+ 确认/取消 | pass | 点击「移除文档 X」 | `.kb-confirm-label`=「确认移除？」出现，`确认移除文档 X`/`取消移除文档 X` 两钮出现（kb-detail-remove-confirm-1440.png） |
| 22 | 二段确认：点取消复原不删除 | pass | 点「取消移除文档 X」 | 确认 UI 消失、行操作恢复、文档仍在（before/after count 不变） |
| 23 | 二段确认：点确认真实删除 | pass | 确认删除 | 文档行卡片 2→1，目标行消失 |
| 24 | 进行中「全部解析并索引」disabled | pass | 种子含 `status:'parsing'` 文档 | `disabled=true`（工具栏「处理中 1」）；来源：`KnowledgeBaseDetailSection.tsx:290 busy = summary.active > 0` |
| 25 | 「撤销解析」未点击 | pass（按要求未点） | — | 未触发，种子状态未被修改 |
| 26 | 笔记本 rail 选中切换 + 指示条 | pass | 点击长名项 | URL 变 `/notebooks/nb-long`；current 项 `::before` content=""、宽 2.5px、蓝 rgb(37,99,235)、opacity 1；非 current 项 content=none |
| 27 | 记录行展开（点击箭头）+ 进场动画 | pass | 点击展开钮 | aria-expanded false→true；展开区 `.nb-pop-in` 挂载且 animationName=nb-pop-in |
| 28 | 记录行 hover 背景变化 | pass | hover 前后 computed | `rgba(247,247,247,0.98)`→`rgb(247,247,247)`（notebooks.css:127-129 `:hover` surface 色） |
| 29 | 三操作钮 aria-label | pass | DOM 采集 | 「编辑记录 X」「移动或复制记录 X」「删除记录 X」逐字存在（每条记录行一组；同一笔记本 2 条记录时同 label 各出现一次，e2e 按行容器定位不冲突） |
| 30 | 深链 `/notebooks/does-not-exist`：只 1 个 role=alert | pass | `locator('[role="alert"]')` 计数 | Playwright 计数=2，但第 2 个是 Next.js 框架自带 `next-route-announcer`（shadow DOM 内空 div，非本批渲染）；**应用渲染的 alert 仅 1 个**（`.nb-notice.is-error`），spec:531 的 `getByRole('alert').filter({ hasText: '链接指向的笔记本不存在' })` 严格定位 count=1，文案精确匹配，含「返回笔记本列表」链接（count=1）。集成修复点成立（详见差异记录第 5 条） |
| 31 | 深链 alert 文案与返回入口 | pass | 同上 | 文本含「无法打开这个笔记本」「链接指向的笔记本不存在，可能已被删除。」，「返回笔记本列表」链接 href=/notebooks |
| 32 | KB 新建（含重名拒绝） | pass | 真实点击流程 | 新建「验收新建库」出现在卡片列表；重名「课程标准库」被拒：错误横幅「已存在同名知识库，请换一个名称。」、列表未新增 |
| 33 | KB 改名同步 URL | pass | 设置分区保存修改 | 「课程标准库」→「课程标准库B」后地址栏 `/knowledge-bases/课程标准库B`（router.replace 生效） |
| 34 | KB 设为默认库 | pass | 点击「设为默认库」 | 横幅「已将「备用库」设为默认库。聊天知识来源选择不受影响（仍为范围声明）。」 |
| 35 | KB 文档登记（file input） | pass | `setInputFiles` | 横幅「已登记 1 个文档，正在模拟解析…」；文档分区出现 `a1-regression-doc.md` 行 |
| 36 | KB 外部来源登记/移除 | pass | 表单填写+按钮 | 登记后 `https://example.com/a1-test` 出现；点「移除来源」后消失 |
| 37 | NB 新建 | pass | rail「新建笔记本」+ Modal | 新建「验收笔记本」出现在 rail |
| 38 | NB 编辑（改名） | pass | 编辑 Modal | rail 内更名为「验收笔记本B」 |
| 39 | NB 导出 Markdown | pass | download 事件 | 下载文件名 `月度整理.md`（acceptDownloads 上下文） |
| 40 | NB 记录展开显示「打开原会话」 | pass | 种子 metadata.sessionId + IndexedDB 会话 | href=`/chat/seed-session-1`，与 spec:446 期望一致 |
| 41 | NB 删除记录 | pass | window.confirm 接受 | 记录行消失，横幅「已删除记录「月度对话记录」。」 |
| 42 | NB 删除笔记本后地址栏回 /notebooks | pass | 删除非默认笔记本 | URL=`http://127.0.0.1:5174/notebooks`（router.replace 生效） |
| 43 | 未触发真实删除用户数据 | pass | 全程独立 browser context + localStorage/IndexedDB 种子 | 无任何操作触及真实用户数据或 5173/8000 |
| 44 | 控制台错误 | pass（一处既有噪声） | console 监听 | 仅 `favicon.ico` 404：`git diff 3f968b0 82871fa -- apps/web/public/` 为空，起点即缺 favicon，非候选引入；无 JS 运行时错误 |

## 失败项最小复现

### F1：390×844 笔记本列表 rail 长名称项溢出被硬裁剪（候选引入）

- **触发条件**：390×844 视口访问 `/notebooks`，rail 内存在长名称笔记本（种子「一个很长的笔记本名称用来检验窄视口下侧栏名称截断行为是否正常」，与任务卡 shoot.mjs 种子相同）。
- **期望**：长名称按 `notebooks.css:55-60` 的 `overflow:hidden + text-overflow:ellipsis` 在 rail 内省略号截断，rail 项与计数徽标完整可见（起点 3f968b0 行为：名称两行换行完整显示）。
- **实际**：`space-scope-item` 宽 447.2px（rail 350px、视口 390px），项右缘 467px 超出视口被硬裁剪，`.count` 徽标（left=447）完全不可见。`notebooks.css:7-9` 将 rail 提到 `flex-basis:250px`，390 下 `@media(max-width:760px)` 改为 `flex-direction:row + flex-wrap:wrap`（space.css:736-748），item 的 min-content 宽度被 nowrap 名称撑到 447px，flex-shrink 无法低于 min-content，导致溢出容器且 `body` 无横向滚动 → 内容被 `overflow` 裁剪而非省略号。
- **证据**：`docs/qa/B-R05-EXTEND/A1-shots/notebooks-390x844.png`（长名右侧被裁、计数徽标不可见）、`docs/qa/B-R05-EXTEND/before/notebooks-390x844.png`（起点两行换行正常）；实测值：`{itemWidth: 447.2, nameTextOverflow: "ellipsis", nameWhiteSpace: "nowrap", railWidth: 350}`。
- **影响**：390 窄视口下长名笔记本的记录计数不可读，名称截断异常（硬裁剪而非省略号），违反任务卡 §5「长文案截断不得回退」。
- **首败命令**：`node docs/qa/B-R05-EXTEND/A1-shots/a1-check.mjs screenshots`（输出 `offenders=BUTTON.space-scope-item right=467`）。

### F2：390×844 笔记本详情记录行标题被挤成 0 宽、类型徽章竖排（候选引入）

- **触发条件**：390×844 视口访问 `/notebooks/nb-monthly`（任何含记录的笔记本详情）。
- **期望**：记录行标题可见（必要时省略号截断），徽章与时间戳正常排布（起点行为：标题在行头、时间戳在独立第二行）。
- **实际**：`NotebooksSection.tsx:562-569` 将时间戳从独立 `space-meta-row` 第二行移到行头 `.space-session-top` 内并 `flexShrink:0`（约 145px）+ 徽章（38px）+ 三个操作钮（95px）+ 展开钮，挤压 `flex:1 + nowrap` 的标题 `space-session-title` 至 **宽度 0px**（完全不可见）；徽章被压成每字一行竖排（宽 38px）。行内可交互信息只剩时间戳/徽章/操作钮，用户无法看到记录标题。
- **证据**：`docs/qa/B-R05-EXTEND/A1-shots/notebook-detail-390x844.png`；实现者自己的 `docs/qa/B-R05-EXTEND/after/notebook-detail-390x844.png` 同样呈现该缺陷（行头只见「对话」竖排+时间戳，标题缺失）；实测 `{titleWidth: 0, titleWhiteSpace: "nowrap", badgeWidth: 38, timeWidth: 145}`。
- **影响**：390 视口下记录行核心信息（标题）不可读，属任务卡 §5「加载/空/错误/搜索/切换/hover/focus/禁用/长文案截断不得回退」的截断回退。
- **首败命令**：对 `docs/qa/B-R05-EXTEND/A1-shots/notebook-detail-390x844.png` 目视 + 上述 Playwright `getBoundingClientRect` 实测。

## 未执行项与原因

- 无整项未执行。两点口径说明：
  1. 未运行 `npm run test:e2e` 全量（属队长资源与职责；本验收以黑盒浏览器实测覆盖了争议点 spec:531 与相关定位前提，未动 e2e 基线）。
  2. 未对参考实现 `F:\DeepTutor` 逐像素比对动画参数（任务卡 §5 只要求「参考有来源的参数」已在 CSS 注释中登记且 MOTION_MATRIX 归队长；我验证的是动画真实生效与 reduced 压制，不宣称动画观感与参考完全一致）。
- 未点击「撤销解析」（按任务卡要求，避免改种子状态；按钮存在性由源码与「全部解析并索引」同区确认）。

## 与实现者结论的差异

1. **390 视口笔记本两处截断缺陷为新增 fail**：实现者提交信息称「三视口前后 48 张」证据齐备，但 before/after 截图本身（`after/notebooks-390x844.png`、`after/notebook-detail-390x844.png`）已客观呈现 F1/F2 缺陷而未被判为不合格。这是本验收与 I2/队长结论的实质差异。
2. **notebooks.css 选择器作用域口径**：严格按附录 A「一律以 `.nb-page` 起头」解析有 17 处 `.nb-*` 起头的选择器（`.nb-badge*`、`.nb-pop-in`、`.nb-notice*`、`.nb-banner*`）；任务卡 §2.3 又写「类前缀 `.nb-*`」。这些选择器均带 `nb-` 前缀、不会外溢到本批四页之外，判定为任务卡内部口径歧义而非缺陷，建议队长下次修订统一表述（不改本批产物也可）。
3. **深链 alert 计数**：实现者称「收敛为仅 ConsoleNotice 单 role=alert」，属实——应用层只渲染 1 个 alert；Playwright 裸计数为 2 是因 Next.js `next-route-announcer`（框架级、shadow DOM、空文本）恒在，spec:531 的 filter 定位不受影响。此差异是定位器口径说明，非问题。
4. **我的截图与 after/ 字节级 0/12 相同**：截图含时间戳/随机噪声无法逐字节一致；布局目视一致。notebook-detail 1440 记录数差异源于我种子将 rec-1 显式指定 `notebookId:'nb-monthly'`（shoot.mjs 的 rec-1 未带 notebookId，产品可能按默认笔记本归集），非产品差异，已在逐项 6 记录。
5. 其余实现者宣称（tab accessible name 子串、五分区 exact 文本、rail「新建笔记本」保留、三操作钮 aria-label、二段确认、parse-all disabled、改名 URL 同步、删除笔记本 URL 回退、导出/回链）均实测复现通过，无差异。

## 证据清单

新截图（`docs/qa/B-R05-EXTEND/A1-shots/`，新建目录，未改动 before/after 既有文件）：

- 三视口×四页全页截图 + 焦点截图（24 张）：`kb-list-1440x900.png`、`kb-list-1440x900-focus.png`、`kb-detail-1440x900.png`、`kb-detail-1440x900-focus.png`、`notebooks-1440x900.png`、`notebooks-1440x900-focus.png`、`notebook-detail-1440x900.png`、`notebook-detail-1440x900-focus.png`，及 `1920x1080`、`390x844` 同名系列
- `kb-list-empty-1440.png`（空态：图标+「还没有知识库」+主行动）
- `kb-detail-remove-confirm-1440.png`（二段移除确认：「确认移除？」+ 确认/取消）
- `results.json`（a1-check.mjs 首轮自动断言记录）
- `a1-check.mjs`（本次验收自写脚本，只读产品代码、只写本目录）

实测数据（Playwright computed style / getBoundingClientRect，正文已引用）：F1 rail 项 447.2px/右缘 467；F2 标题 0px/徽章 38px/时间戳 145px；reduce 下 kb-pulse、nb-pop-in、指示条 `::before`、卡片 transition 均 1e-05s；对照组 kb-pulse=1.4s、nb-pop-in=0.2s。

静态核查命令与输出（正文已引用）：`git diff 3f968b0 82871fa --stat -- tests/`（0 行）、`-- apps/web/src/features/space/styles/space.css apps/web/src/styles/globals.css`（0 行）、`grep -c "!important"`（0/0）、选择器解析脚本（knowledge 0 处 / notebooks 17 处 `.nb-*` 起头）。

## 收尾

- 5174 服务已停止（进程已终止，端口已释放）——本报告落盘后执行，见回报。

---

## v2 复验（候选 19b514c）

- 复验时间：2026-09-18 ｜ 复验者：Independent-Acceptor（同 v1）｜ 资源：5174（本轮独占，**复验结束已停止进程并释放**）
- 复验方式：聚焦复验（非全量重验）。先静态核对 `git diff 82871fa 19b514c --stat`：仅 2 个产品文件（`notebooks.css` +34 行、`NotebooksSection.tsx` ±5 行）+ 4 张 390 截图重拍；`tests/`、`space.css`、`globals.css`、`features/knowledge/` 在该 diff 中 **0 行**（`--stat | wc -l` = 0）。工作树干净（`git status --porcelain apps/web/src tests/` 空）。
- 复验脚本：`docs/qa/B-R05-EXTEND/A1-shots/a1-v2.mjs`（自写，隔离上下文种子：长名笔记本 + 长标题记录）。

| # | 复验项 | 结果 | 实测值 | 证据 |
| --- | --- | --- | --- | --- |
| V1 | F1：390 `/notebooks` rail 项不再溢出 | pass | 长名项 `right=370`（≤390）、宽 350=容器宽；队长量测 370 一致 | `A1-shots/v2-notebooks-390x844.png` |
| V2 | F1：计数徽标可见 | pass | `.count` `right=357`（视口内、宽>0） | 同上 |
| V3 | F1：名称省略号截断 | pass | `.space-scope-item-name` `text-overflow:ellipsis + nowrap + hidden`，`scrollWidth > clientWidth`（实际触发截断，名宽 293px）；截图见「…」收尾 | 同上 |
| V4 | F2：390 详情标题可见（非 0 宽） | pass | 长标题记录 `space-session-title` 宽 **96px**（v1 为 0px），省略号截断；普通标题「月度对话记录」完整可见 | `A1-shots/v2-notebook-detail-390x844.png` |
| V5 | F2：徽章单行 | pass | `.nb-badge` 宽 66px、高 24px（单行；v1 为 38px 宽竖排） | 同上 |
| V6 | F2：时间戳换第二行 | pass | `space-session-top` `flex-wrap:wrap`（390 下）；titleTop=713 < timeTop=749（第二行）、时间戳宽 316px 独占整行 | 同上 |
| V7 | 新增溢出回归：390 两页全页扫描 | pass | `/notebooks` 与 `/notebooks/nb-monthly` 均 `scrollWidth-clientWidth=0`、超出视口元素数 **0**（修前 56，与队长量测一致） | a1-v2.mjs 输出 |
| V8 | 新增溢出回归：1440 两页全页扫描 | pass | 两页均 `pageOverflow=0`、`offenderCount=0` | a1-v2.mjs 输出 |
| V9 | 1440 宽视口不回退：时间戳仍在行头 | pass | `space-session-top` `flex-wrap:nowrap`；titleTop=312 ≈ timeTop=314（同行）；长标题行标题 89px 省略号截断、时间戳同行 | `A1-shots/v2-notebook-detail-1440x900.png` + 实测 |
| V10 | 1440 宽视口不回退：rail 项与标题排布与 v1 一致 | pass | 长名项名称+描述两行完整、无截断（`scrollWidth=clientWidth`），rail 布局与 v1 `after/notebooks-1440x900.png` 目视一致；**注**：我在 a1-v2.mjs 里的 `itemWidth<=300` 断言是脚本阈值写错（v1 的 DOM 宽度同为 447px，非回归），以截图与截断行为判定为准 | `A1-shots/v2-notebooks-1440x900.png` vs `after/notebooks-1440x900.png` |
| V11 | 1440 交互不回退：rail 切换/指示条/展开/操作钮 | pass | 切换 URL→`/notebooks/nb-long`；current 项 `::before` 2.5px 蓝条；展开钮 aria-expanded false→true、`.nb-pop-in` 生效；「编辑记录」钮存在 | a1-v2.mjs + 补充实测 |
| V12 | 深链应用层 role=alert 仍为 1 | pass | 排除 `next-route-announcer` 后应用层 alert=1；spec:531 严格定位（`filter({hasText:'链接指向的笔记本不存在'})`）count=1；「返回笔记本列表」count=1 | 补充实测 |
| V13 | `.space-scope-item` 内「新建笔记本」仍可定位 | pass | `nav[aria-label="笔记本列表"] button.space-scope-item`（hasText 新建笔记本）count=1（spec:494 定位前提保持） | 补充实测 |
| V14 | 抽查：知识库两页 390 未受影响 | pass | `/knowledge-bases` 与 `/knowledge-bases/课程标准库` 均 `pageOverflow=0`、`offenderCount=0`（本候选未改 knowledge 模块，抽查通过） | 补充实测 |

### v2 附注

- `nb-row-time` 修复方式核对：宽视口 `.nb-page .nb-row-time { flex-shrink:0 }` 承接原内联样式（`NotebooksSection.tsx` 内联 `flexShrink:0` 已移除），≤760px 断点内 `flex-basis:100% + order:10` 换行；`space-bank-layout { align-items:stretch }` 仅 ≤760px 生效，与 space.css 断点一致，宽视口不受影响——与任务卡附录 A「断点一致、仅本页收窄」的边界相符。
- 本轮 diff 未新增 `!important`（新增块核对），未改新断言相关 aria-label/文案。
- v1 报告的其它结论（可访问性、reduce 动画、回归项）不在本轮 diff 触及范围内，维持 v1 判定，未重跑。

**v2 最终结论：pass**（14/14 通过；v1 两项 fail 均确认修复，无新增回归；无需再次介入）。

## 收尾（v2）

- 5174 服务已停止（进程已终止，端口已释放），见 v2 回报。
