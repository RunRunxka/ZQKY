# B-R05-EXT4-A1 独立验收报告（v1）

- 候选：`d54bd93` ｜ 起点：`b0b24fa` ｜ 验收时间：2026-09-19
- 验收者：Independent-Acceptor ｜ 资源：端口 5174（验收期间独占，验收结束已停止监听并释放）
- 环境：生产预览 `node scripts/run-web.mjs start 5174`（`apps/web/.next` 即候选构建，BUILD_ID `MnDuNbjJNJaU1vwsT_K1_`）；Playwright 1.58.2 + channel `msedge`（153.0.4234.32，与 `playwright.config.ts` 同款）。browser-use 技能限主智能体使用，子智能体不可用，改用项目 e2e 同款 Playwright 真实驱动浏览器，仍为真实 GUI 点击/键盘操作。
- 前置核对：HEAD 即 `d54bd93`，工作树干净；实现者已停止写入（无未提交改动）；参考仓库 `F:\DeepTutor` 未读写。
- 结论：**pass**（无 fail 项）

## 环境准备声明（依测试规范）

- 种子注入：教案草稿用 `tests/fixtures/lesson-plan.json` 经 `addInitScript` 注入 `zhiqikeyuan:lesson-plan:v1`（与 `lesson-plan.spec.ts:5-12` 同源）；损坏草稿场景单独 context 注入 `invalid-json`。设置页不注入数据。
- 模型区成功态用 `page.route` mock 5 个 `/api/v1/*` 端点（数据形态复用 `tests/e2e/model-settings.spec.ts` 的既有替身），仅路由层拦截、不写正式 `.env`、不触碰 `.local-data`。真实供应商调用本批不适用（无凭证），见 not_run。
- 以上均为环境准备；准备完成后为纯黑盒 GUI 操作，无 JS 注入改状态。

## 逐项结果

| # | 验收项 | 结果 | 命令/操作 | 证据 |
|---|---|---|---|---|
| 0 | 候选/版本/资源归属 | pass | `git rev-parse HEAD` → `d54bd93`；`git status --porcelain` 空；`git show --stat d54bd93` 与任务卡一致 | 本报告前置核对段 |
| 1a | 设置页 1440/1920/390 `scrollWidth<=innerWidth` | pass | 三视口实测 evaluate；1440/1920/390 均 true | check1 输出；`A1-shots/a1-settings-{1440,1920,390}.png` |
| 1b | 设置页 390 历史溢出归零 | pass | 页面级 `<a>` 溢出扫描 = []（before 宣称 2 处 → 0）；条带 `.settings-index` clientW 389 / scrollW 394 / overflowX auto，属条带内滚动；全元素页面级溢出（剔除合法条带内滚动）= [] | check1 输出；`a1-settings-390.png` |
| 1c | 教案页 1440/1920/390 `scrollWidth<=innerWidth` | pass | 三视口实测均 true；无元素重叠/异常截断（截图目检） | check5/check6 输出；`a1-lesson-{1440,1920,390}.png` |
| 1d | 与 `after/` 一致性 | pass | 独立重截 6 组同视口图与 `after/` 逐像素比对（容差 8/通道）：diffPixels 全部 0（0.0000%） | 逐像素比对输出（比对脚本内存比对，未落盘产物） |
| 2a | 设置页 Tab 可达：导航/搜索/清除/分区控件 | pass | Tab 遍历 12 步：5 个索引链接 → 重试 → 搜索 MCP → 添加 MCP → 搜索 Skill → 添加 Skill；索引导航项 `:focus-visible` 计算样式 outline 2px solid rgb(37,99,235) | check1/check2 输出；`a1-settings-1440-focus-nav.png` |
| 2b | 搜索框 focus 态 | pass | `:focus` 计算样式（160ms 过渡完成后）：borderColor rgb(37,99,235)、box-shadow 3px 蓝软环。注：同步读取会读到过渡起点值，非缺陷 | check3 输出；`a1-settings-search-focus.png` |
| 2c | 教案页焦点环 | pass | 课题输入框 `:focus-visible` outline 3px；Tab 顺序覆盖大纲/表单/预览工具栏 | check5 输出；`a1-lesson-1440.png` |
| 2d | 既有断言前提：aria-current / nav 名 / switch / 减少动画 label | pass | `[aria-current="location"]` 唯一且随导航点击跟随（点击 MCP 后落在 MCP 项，滚动后 scroll-spy 落在「模型与连接」，与 e2e 语义一致）；`nav[aria-label="设置分类"]` 唯一；`role="switch"+aria-checked` 添加 MCP 后 false→true→reload 保持 true；`getByLabel('减少动画', {exact:true})` 可定位可勾选 | check4/check10 输出 |
| 2e | 教案锚点类名仍在 DOM | pass | `.subject-cell`1、`.save-status`1、`.fill-warnings`1（填充流程中出现）、`.process-editor`4、`.paper`2、`.print-text`13、`.secondary-cell`4、`.approval-line`1、`.paper-footer`2、`.preview-pane`1、`.storage-alert`1（损坏草稿场景） | check5/check6/check7b 输出 |
| 3a | 「清除搜索」唯一性 | pass | 输入后 `getByRole('button',{name:'清除搜索'})` count=1；空态与有数据态均唯一；无输入时 count=0（按钮条件渲染） | check1/check3/check8 输出 |
| 3b | 未增加同名控件 | pass | 「重试」在无后端错误态 count=1（未增加，历史为 1）；「添加连接」错误态 count=0、mock 成功态 count=2（基线 2，未增加）；「添加 MCP/添加 Skill」各 1 | check1/check2/check7b/check8 输出 |
| 3c | 教案页无新增控件 | pass | diff 中教案仅加 className 与 CSS；交互实测无新增按钮；导出菜单项名称与既有一致（导出 PDF/导出 Word/备份草稿） | git diff + check6 输出 |
| 4a | 减少动画-系统 `prefers-reduced-motion: reduce` | pass | 计算样式实测：设置页搜索框/索引链接 transitionDuration 1e-05s（被压制）；教案 segmented/icon-button 0s | check4 输出 |
| 4b | 减少动画-本地 `html[data-motion=reduced]` | pass | 勾选「减少动画」后 `data-motion=reduced`；设置页导航/输入过渡 1e-05s；教案导出菜单 animationDuration 1e-05s（lesson-menu-in 被压制，animationName 保留但时长 0.01ms）；恢复勾选后 `data-motion=system` 且 checkbox 回到基线 false | check4/check9 输出 |
| 4c | 教案 toast/导出菜单动画与全局机制 | pass | 正常态导出菜单 animationName=lesson-menu-in、0.18s（keyframes 已加载）；系统 reduce 下 animationName=none、0s（浏览器层面取消）；本地 reduce 下时长 1e-05s。两种机制均实测计算样式，非仅 CSS 存在性 | check5/check8/check9 输出；`a1-lesson-export-menu.png` |
| 5a | 索引导航点击跳转 + aria-current 跟随 | pass | 点击 MCP → URL `settings#mcp`、区块滚至 top=90、aria-current 跟随 | check4 输出；`a1-settings-mcp-active.png` |
| 5b | 搜索过滤 + 清除回焦 + 无结果空态 | pass | 输入不匹配词 → 链接 0 + 空态「没有匹配的设置项」；点击清除 → 值清空、焦点回「搜索设置」输入框（实测 activeElement aria-label） | check3 输出；`a1-settings-search-noresult.png` |
| 5c | 外观「减少动画」开关切换（恢复基线） | pass | 轨道灰→绿、滑块 translateX(16px)、显示偏好已保存；已恢复基线（见 4b） | check4 输出；`a1-settings-toggle-on.png` |
| 5d | MCP/Skills 分区渲染 + 关于文案 | pass | 模拟模式提示、搜索框、添加按钮、虚线空态卡齐备；关于文案「界面参考 DeepTutor v1.6.5。模型管理保留现有真实服务；MCP 与 Skills 当前为本地模拟管理…」 | check4 输出；`a1-settings-about.png` |
| 5e | 教案交互链 | pass | 填课题→`.save-status`「已保存到本机」→reload 值恢复；大纲勾选 active 跟随；要求填充→识别→警告「未识别内容」→确认填入→撤销恢复 | check6 输出；`a1-lesson-draft-restored.png`、`a1-lesson-fill-warnings.png` |
| 5f | 导出菜单打开（动画）→关闭 | pass | 打开 0.18s 进场动画（见 4c）；点击「关闭导出菜单」backdrop 后菜单移除、aria-expanded=false。备注：Escape 不关闭该菜单——ExportMenu 无 Escape 处理器且本批对该文件零改动，属既有行为，非回退 | check7b 输出（check7 首跑 Escape 路径超时即为该既有行为，已按设计路径 backdrop 复测） |
| 6a | 模型区错误态（无后端） | pass | 「无法读取模型设置：后端服务不可用。」+「重试」按钮可见；`/api/v1/model-catalog`、`model-providers` 各 1 次 500 | check2 输出；`a1-settings-models-error.png` |
| 6b | 模型区零改动静态核查 | pass | `git diff --name-only b0b24fa d54bd93`：`features/model-settings/**`、`features/chat/**` 不在列表（NONE-FOUND） | git diff 输出 |
| 6c | 模型区成功态全链路（mock） | pass | mock 5 端点：卡片「DeepSeek 主账号」、5 高危锚点全在（`打开 DeepSeek 主账号 的详情`、`用于问答`、dialog aria-label「连接 · DeepSeek 主账号」、`^Base URL` label、discovery checkbox）、发现「来自上游实时接口」、已添加禁用/新模型可选、「用于问答」触发且仅触发 1 次 model-defaults 写入（打开卡片 0 次） | check7b/check10 输出；`a1-models-mock-{list,detail,discovery}.png` |
| 6d | 真实供应商调用（无凭证） | not_run | 不持有任何真实供应商凭证；任务卡 2.1 亦禁止写 `.env` | — |
| 7a | 草稿保存/刷新恢复 | pass | 填「A1验收课题 · 草稿链路」→ 已保存到本机 → reload 后输入框与 `.subject-cell` 均恢复 | check6 输出；`a1-lesson-draft-restored.png` |
| 7b | 损坏草稿不覆盖 | pass | 种 `invalid-json` → `.storage-alert`「原草稿读取失败，自动保存已暂停。备份当前内容并替换旧草稿」；编辑后 1s localStorage 仍为 `invalid-json` 原样 | check7b 输出；`a1-lesson-storage-alert.png` |
| 7c | Word 导出有效 | pass | 捕获 download：`教案-A1验收课题 · 草稿链路.docx`，118115 字节，`PK` 魔数 true；并用项目 `scripts/verify-template.mjs` verifyDocx 全项 true（tblPr/tblGrid/tcPr/trHeight/sectPr/noUnfilledTags） | check6 输出；`A1-shots/a1-export-sample.docx` |
| 7d | PDF 弹窗（不调起打印） | pass | 「导出 PDF」→ dialog 含「另存为 PDF」；以「关闭」按钮关闭，未触发打印 | check6 输出；`a1-lesson-pdf-dialog.png` |
| 7e | 跨页返回草稿恢复 | pass | 教案→「学习问答」（`.chat-page` 可见）→「教案工作台」→ 课题值保留 | check6 输出；`a1-lesson-crosspage-return.png` |
| 7f | 导出/草稿链路零行为变化 | pass | 本批 diff 未触及 DraftRepository/Word 映射/print（见 8a）；实测保存/恢复/损坏保护/Word 结构全通过，行为与既有 e2e 断言一致 | 8a + 7a-7e |
| 8a | 静态核查-禁区零改动 | pass | diff 文件列表仅 5 个产品文件（LessonPlanWorkspace.tsx、lesson-visual.css、ExtensionManager.tsx、SettingsWorkspace.tsx、settings-extend.css）+ 证据；`tests/`、`globals.css`、`space.css`、`motion.css`、`print.css`、`services/pagination.ts`、`model/*`、`assets/`、`settings.css`、`lesson-plan.css`、`model-settings/**`、`chat/**` 全不在 diff | `git diff --name-only b0b24fa d54bd93` 输出 |
| 8b | 新 CSS 前缀/!important/@media print | pass | settings-extend.css 顶层选择器全部 `.settings-*`/`.settings-page` 作用域或 `.extension-manager` 后代（该类仅 ExtensionManager.tsx 使用，不触模型区）；lesson-visual.css 全部 `.lesson-*`/`.lesson-page`。剥离注释后真实 `!important` 计数两文件均 0（命中处均为注释文字）；`@media print` 均为 0（命中处均为注释文字）；注释内无 `*/` 提前闭合序列 | grep + 剥注释统计输出 |
| 8c | §8.2「不做」项确认未做 | pass | 无导航分组折叠（索引仍 5 项平铺）；无页级草稿工具栏/横幅；无 Overview 状态条/就绪面板/语言开关/Tour/草稿时间戳（DOM 无对应元素，`关于` 文案保持既有）；教案预览缩放无过渡（`.paper` transitionDuration 0s，zoom-label 仅 hover 色 0.15s）；模型区结构/CSS 未动（8a/6b） | check4/check5 输出 + 截图目检 |

## 失败项最小复现

无 fail 项。

## 未执行项与原因

| 项 | 结果 | 原因 |
|---|---|---|
| 真实供应商模型调用（目录/发现/认证/推理真链路） | not_run | 验收环境无任何真实供应商凭证；任务卡 2.1 禁止写正式 `.env`。模型区成功态以既有 e2e 同款 mock 替身验证 UI 链路（6c），**mock 通过不等于真实供应商通过** |
| 真实后端下的模型区 | not_run | 5174 仅启前端（任务卡资源分配），未启动 `apps/api` |
| 打印实际调起 / page.pdf 产物 | not_run（按任务要求） | 任务卡明确「不实际调起打印，可只验证弹窗文案」；既有 e2e 已覆盖 page.pdf |
| `npm run build` / e2e 全量复跑 | not_run | 任务卡声明 `.next` 已是候选构建（实测 BUILD_ID 在位、页面服务正常、6 组截图与 after/ 逐像素一致佐证构建即候选）；e2e 全量归队长，且实现者已报告 154/154 |
| 阅读模块 R-09 flaky 用例复核 | not_run | 与本批两页无交集（本批 diff 零改动阅读模块，静态核查 8a 佐证）；属实现者已记录事项 |

## 与实现者结论的差异

1. 实现者称「顺带：390 视口设置页既有 2 处 `<a>` 溢出在候选下实测归零」——**独立复测确认**：页面级 `<a>` 溢出为 0，条带内横向滚动（scrollW 394 vs clientW 389）属任务预告的合法状态，与宣称一致。
2. 实现者称两 CSS「零 !important（仅注释内提及）」「lesson-visual.css 无 @media print」——**独立复测确认**：`grep` 各有 1 处字面命中，但均在注释内；剥离注释后真实计数为 0，与宣称一致。
3. 补充观察（非缺陷、非回退）：导出菜单不响应 Escape 关闭。`ExportMenu.tsx` 本批零改动、无该处理器，属既有行为；设计关闭路径为「关闭导出菜单」backdrop，实测正常。记录备查，不构成本批问题。
4. 其余实现者宣称（模型区零改动、教案锚点保留、禁区分界、动画参数对齐 chat 180ms 档）均独立验证通过，无出入。

## 证据清单

- 报告：`H:\备份xuexi\智启课源\docs\qa\B-R05-EXT4\A1-REPORT.md`（本文件）
- 截图与产物：`H:\备份xuexi\智启课源\docs\qa\B-R05-EXT4\A1-shots\`
  - `a1-settings-1440.png`、`a1-settings-1920.png`、`a1-settings-390.png`（三视口全页）
  - `a1-settings-1440-focus-nav.png`、`a1-settings-search-focus.png`、`a1-settings-search-noresult.png`、`a1-settings-search-filtered.png`
  - `a1-settings-mcp-active.png`、`a1-settings-about.png`、`a1-settings-toggle-on.png`
  - `a1-settings-models-error.png`（无后端错误态）
  - `a1-models-mock-list.png`、`a1-models-mock-detail.png`、`a1-models-mock-discovery.png`、`a1-models-mock-default.png`（mock 成功态链路）
  - `a1-lesson-1440.png`、`a1-lesson-1920.png`、`a1-lesson-390.png`
  - `a1-lesson-export-menu.png`、`a1-lesson-pdf-dialog.png`
  - `a1-lesson-draft-restored.png`、`a1-lesson-fill-warnings.png`、`a1-lesson-outline-checked.png`、`a1-lesson-crosspage-return.png`
  - `a1-lesson-storage-alert.png`（损坏草稿）
  - `a1-export-sample.docx`（Word 导出产物，118115 字节，verifyDocx 全项 true）
- 实测数据：`C:\Users\96022\AppData\Local\Temp\a1e4-check{1..10}.json`（脚本 `/tmp/a1e4-check*.cjs`，均不落仓库）
- 一致性比对：独立重截 6 组与 `docs/qa/B-R05-EXT4/after/` 同名图逐像素 0 差异（比对为脚本内存比对，未生成额外文件）

## 资源释放说明

验收完成后已停止 5174 监听进程（定位 PID 2772 后 `taskkill /F` 停止，复测 `netstat` 无 5174 LISTEN），端口已释放；未修改任何产品源码、测试、CSS、矩阵、STATUS、TASK-CARD、E4-GAP-LIST、README；未执行 git add/commit；未改动 `before/`、`after/`、`shoot.mjs`。
