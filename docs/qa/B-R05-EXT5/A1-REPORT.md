# B-R05-EXT5-A1 独立验收报告（v1）

- 候选：a9c28ea ｜ 起点：7b2ba5e ｜ 验收时间：2026-09-19 23:55 前后（全程约 70 分钟）
- 验收者：Independent-Acceptor ｜ 资源：5174（验收期间独占；已在收尾释放，见文末）
- BUILD_ID 核对：`apps/web/.next/BUILD_ID` = `eYs-YyFDf0XQJugH8zZcO`，mtime 2026-09-19 22:20:02 +0800，与任务卡一致；验收期间未重新 build。
- 结论：**pass**（0 fail；无 needs_revision 项）

验收方式说明：本环境 Browser Use 工具对子代理不可用（`Browser is not available in subagent`），改用项目自带的 playwright-core（只读 import，不改动）编写独立脚本 `C:\Users\96022\AppData\Local\Temp\a1e5-accept.mjs`，通过真实浏览器（msedge channel）逐项操作页面；所有截图写 `A1-shots/`，未改动任何产品源码、测试、CSS、矩阵与权威文档，未 git add/commit。

## 逐项结果

| # | 验收项 | 结果 | 命令/操作 | 证据 |
|---|---|---|---|---|
| 0a | 候选与工作区状态 | pass | `git rev-parse HEAD`→a9c28ea…；`git status --porcelain`→0 行（干净）；分支 codex/replica-review-20260908 | 本节记录 |
| 0b | 保护区文件零改动 | pass | `git diff 7b2ba5e..a9c28ea --name-only` 过滤 `reading.css/reading-store/reading-ingest/space.css/globals.css/motion.css/playwright.config.ts` → 全部不存在；`git show a9c28ea --stat` 71 文件中仅 ReadingWorkspace.tsx + 新 reading-ws.css + 四个 space Section + 新 space-sections.css + 文档/截图 + reading.spec.ts | 命令输出 |
| 0c | 探针残留 | pass | `git diff 7b2ba5e..a9c28ea -- 'apps/web/**' 'tests/**'` 新增行 grep `__p`/`__wheelArrived`/`console.log` → 0 命中 | 命令输出 |
| 0d | 新 CSS 审计 | pass | reading-ws.css：`!important` 计数 1，但唯一命中在第 3 行注释文本「零 !important」内，代码区 0；space-sections.css：0。两文件均无 `@media print`、无 `prefers-reduced-motion` 规则（仅注释提及）；全部选择器以 `.reading-ws-page` / `.space-sections-page` 前缀起头（grep 反向验证 0 命中）；引用的 `--radius-sm/--line/--bg/--ink/--muted/--blue/--green/--surface/--shadow-card/--ease-standard` 与 `.space-spin` 均在 globals.css / space.css / motion.css 中存在 | 命令输出 |
| 0e | §8.2「不做」项确认未做 | pass | diff 无参考式聊天完整复用、无滚动 80px 语义（`>= 90` 阈值仍在，见 #3）、replaceState/replace 计数 old=new=2（无 URL 历史降级）、CLI 无搜索/详情/分页、角色卡无 hover 显隐 | 命令输出 |
| 1 | 三视口视觉与布局 | pass | 独立脚本实测 1440×900 / 1920×1080 / 390×844 ×（阅读工作区 + space 四子页）：`documentElement.scrollWidth <= innerWidth` 全部成立（20 项无溢出）；截图与 `after/` 目视比对一致（reading-workspace 三视口、space 四页 1440，逐张目检通过；新 chip「1 个会话」「N 个会话」「N 道题」与 after/ 呈现一致） | A1-shots/reading-workspace-{1440x900,1920x1080,390x844}.png、space-*-*.png ×12 |
| 2 | R-09 五例不回退 | pass | `npx playwright test tests/e2e/reading.spec.ts -g "R-09"` → **5/5 passed (7.5s)**；`-g "R-09 滚动跟随" --repeat-each=10` → **10/10 passed (27.0s)**（实现者声明 10/10 一致）；全量 reading.spec 17/17 (19.1s) | 本节命令输出（运行记录见文末「证据清单」） |
| 2b | R-09 用例语义逐条核对 | pass | reading.spec.ts:425 滚动跟随：`expect.poll(...scrollTop).toBeLessThan(60)`——阈值仍是 **< 60**，仅 `expect`→`expect.poll`（diff 逐行核对，无其他断言改动）；:465 会话导航（pushState/后退到 B/前进回 A、草稿同步）语义未变；:497 迟到事件（旧轮落旧会话、新会话无痕）未变；:524 取消收尾（保留已生成+「（已取消）」标注、不串新会话）未变；:550 移动端抽屉（reduce 动画、上滚保持、回到最新、切换历史）未变。spec 全文件 diff 仅 425 行附近 +3 行注释/改写 | `git show a9c28ea -- tests/e2e/reading.spec.ts` |
| 3 | 阅读工作区交互保护区 | pass | ① diff hunk 清单逐块核对：import Loader2、reading-ws.css import、3 处根/工具条/tab className、tab 标题包 span+spinner、reader-head/companion-head className 化、**dismissedTurnError/dismissedSessionError 两个新 state**、**userScrolledAwayRef/programmaticScrollRef 两个新 ref**、follow-bottom effect（新增 `userScrolledAwayRef` 短路与 programmaticScrollRef 记录，依赖数组未变）、onScroll 回调（新增 programmatic 窗口判断，**90px 阈值语义保留**：`away = ... >= 90`，old 为 `< 90` 开跟随，等价）、回到最新 onClick（新增 ref 记录+清窗口）。② `syncSessionUrl` 函数体 old/new diff 为空；popstate handler、`finalizedTurnsRef`(3)、`retryTurn`(2)、`abortsRef`(7)、`draftOwnerRef`(4) 出现次数与上下文未变；`handleScroll` 函数体 diff 为空 | `git diff 7b2ba5e..a9c28ea -- apps/web/src/features/reading/ReadingWorkspace.tsx`；old/new 全文提取比对 |
| 3b | 保护区行为实测（浏览器人工） | pass | 上滚：wheel -600 后 top=0，流式增量继续后仍 top=0、dist=254（不被拉回）；「回到最新」：点击后伴生 dist=0，正文容器 scrollTop 与整页 scrollY 均保持 0→0 不变；会话切换：新建会话 push `/sessions/rss-*`，切回 A 后 goBack→URL/选择器/草稿恢复 B，goForward→恢复 A+草稿；材料 tab（1 个 reading-ws-tab 渲染正常）、书签按钮点击成功、双击选区后选区工具栏可见 | 脚本 M2/M3/M4/M5/M6a/M6b/M6c；A1-shots/reading-scroll-held-1440.png |
| 4 | R-10 来源回链 | pass | e2e：chat-source-links.spec.ts **21/21**、chat-message-locate.spec.ts **12/12**（未改 spec）；人工：注入 `zhiqikeyuan:quiz-bank`（sessionId=sess-a）+ IndexedDB `zhiqikeyuan-chat`，「查看出处会话」链接存在，href=`/chat/sess-a?message=accx-msg`（真实 sessionId + messageId，无 ?mode=mock）；「来源会话已不存在」提示路径由 e2e「来源会话已删除」用例覆盖通过 | 脚本 S2e；测试输出 |
| 5 | /space 四子页交互 | pass | `npx playwright test tests/e2e/space-pages.spec.ts` → **8/8 passed (5.3s)**（运行时出现 127.0.0.1:8000 ECONNREFUSED 日志为既有 API 探测噪声，用例全过，与起点行为一致）；人工逐页：搜索（filtered=1）、重命名（renamed=1）、归档（已归档筛选可见 chip=1）、重开；题库收藏/错题范围/演示载入幂等（2→2）/新建分类/删除（left=0）；角色查看/编辑/删除/演示幂等（4→4）；CLI 安装→「已启用→已停用」切换→卸载（gone=true）。断言锚点原样：`搜索会话历史`、`会话名称`、`关闭提示`、`新分类名称`、`移动到分类`、`查看出处会话`、`编辑/删除/查看`、`已启用/已停用` 均在源码与页面中确认存在 | 脚本 S1a–S4c；A1-shots/space-*-interactions.png ×4 |
| 6 | 键盘焦点与可访问性 | pass | Tab 走查：阅读工作区 25 步内 24 次聚焦可见控件、焦点环（outline 2px / box-shadow）可见；space 子页 15 步内 15 次聚焦、焦点环可见。重名复查：新 aria-label `关闭伴生错误提示`/`关闭会话错误提示` 在源码中各仅 1 处（ReadingWorkspace.tsx:1545、:1489），全库无既有同名控件；页面上正常会话态计数为 0（横幅未出现时按钮不渲染，属条件渲染语义正确，非冲突） | 脚本 K1/K2/K3；A1-shots/focus-walk-space.png |
| 7 | 减少动画 | pass | `reducedMotion: 'reduce'` 实测计算样式：阅读工作区 .space-button transition-duration=`1e-05s`（=0.01ms，motion.css `transition-duration:0.01ms!important` 全局压制生效，globals.css 同类规则双保险）；space 子页按钮与卡片 transition-duration 均为 `1e-05s`；tab spinner（.space-spin）动画同被该规则压制。新增 CSS 未自带 reduced-motion 覆盖，依赖全局机制，行为符合设计 | 脚本 RM1/RM2；A1-shots/reduced-motion-reading.png |
| 8 | 窄视口 390 深度实测 | pass | 阅读工作区 390×844：`.reading-ws-tab-label` 计算样式 text-overflow=ellipsis + overflow hidden + nowrap（N1 实测通过），页面 scrollWidth 无溢出；移动抽屉：伴生抽屉打开→背板点击关闭（count=0），导航抽屉打开→背板关闭，与 R32 交互一致；space 四子页 390 溢出检查 4/4 通过（基线 0 未变差） | 脚本 N1/N1b/N2/N2b/N3/N3b、V-*-390x844；A1-shots/reading-390-*-drawer.png |
| 9 | 错误态与关闭行为 | pass（部分等效覆盖） | 深链 `/reading/demo-reading-ws/sessions/no-such-session` → 错误横幅「链接指向的会话不存在，已切换到最近会话。」出现 → 点「关闭会话错误提示」→ 隐藏 → 再深链另一个不存在会话 `another-missing` → 新错误重新显示（实现者的「按错误文本比较」设计实测成立）。**关闭后 error 数据未清除**：横幅关闭按钮 onClick 仅 `setDismissedSessionError(sessionError)`（源码核对），error state 本体与重试入口未动；turn error 因本地模拟服务无法在 UI 稳定触发失败轮次，turn-error 分支的关闭/重试在浏览器实测标 **not_run**（源码审查确认 dismiss 只影响可见性、retryTurn 按钮独立存在，与横幅实现同一模式） | 脚本 M7a/M7b/M7c；A1-shots/reading-error-banner-1440.png；ReadingWorkspace.tsx:1092-1105/1482-1497/1529-1552 |
| 10 | 静态核查汇总 | pass | 见 0b/0c/0d/0e；另确认 `space.css:726 .space-spin` 与 `@keyframes space-rotate` 为既有定义（新 CSS 仅引用）；`playwright.config.ts` 零改动 | 同上 |

## 失败项最小复现

无 fail 项。

## 未执行项与原因

| 项 | 结果 | 原因 |
|---|---|---|
| turn error（伴生回复失败）横幅的关闭+重试浏览器实测 | not_run | 伴生回复为本地模拟服务，正常路径不产生 turn.error；无法在 UI 稳定构造失败轮次。源码审查已确认 dismiss 机制与 sessionError 横幅同一实现（仅比较文本隐藏视觉，不动 error 数据、retryTurn 按钮独立可用），sessionError 路径已实测通过 |
| 无凭证供应商真实调用 | not_run | 按任务边界，本批为纯前端视觉/交互批，不涉及真实供应商调用 |
| 参考组件逐像素对照 | not_run（部分） | 参考库 `F:\DeepTutor\web\components\reading\workspace\`（ReadingCompanion/ReadingWorkspace/WorkspaceChrome）与 `components/space/`（ChatHistorySection/PersonasSection/QuestionBankSection）存在；CLI 参考在 `components/cli-apps/CliAppsSection.tsx`（不在 space 目录）。本验收以「与 after/ 一致 + 无溢出 + 交互可用」为口径，未做像素级对参考比对（任务卡口径为一致性核对） |

## 与实现者结论的差异

1. **R-09 压测数字一致**：实现者声明 5/5 与 repeat-each=10 → 10/10；实测相同（10/10，27.0s）。
2. **无结论冲突**。两点补充观察（非 fail）：
   - `space-pages.spec.ts` 运行时持续打印 `127.0.0.1:8000 ECONNREFUSED` 的 WebServer 日志（既有 API 健康探测噪声），用例 8/8 通过，起点行为一致，不属本批回归。
   - `reading-ws.css` 注释自称「零 !important」，文件中 `!important` 字符串出现 1 次但位于注释文本内，代码区确为 0；计数口径已在 #0d 记录，避免后续误读。
3. 实现者称「阅读 spec 17/17」——实测一致（19.1s）。

## 证据清单

- 截图目录：`H:\备份xuexi\智启课源\docs\qa\B-R05-EXT5\A1-shots\`（25 张：三视口 ×6 页、交互态 ×4、错误横幅、滚动保持、焦点走查、减少动画、390 两抽屉）
- 验收脚本（只读副本，位于临时目录，不入库）：`C:\Users\96022\AppData\Local\Temp\a1e5-accept.mjs`（55/55 pass 输出全文已在会话记录）
- 关键源码核对点：
  - `H:\备份xuexi\智启课源\apps\web\src\features\reading\ReadingWorkspace.tsx`（1092-1105 注释、1229-1246 follow-bottom effect、1482-1497 sessionError 横幅、1502-1517 onScroll、1529-1552 turnError 横幅、1556-1575 回到最新）
  - `H:\备份xuexi\智启课源\apps\web\src\features\reading\styles\reading-ws.css`
  - `H:\备份xuexi\智启课源\apps\web\src\features\space\styles\space-sections.css`
  - `H:\备份xuexi\智启课源\tests\e2e\reading.spec.ts:425-462`（R-09 滚动跟随，阈值 `< 60`）
  - `H:\备份xuexi\智启课源\apps\web\src\services\chat-source.ts:15`（conversationSourceHref）
  - `H:\备份xuexi\智启课源\apps\web\.next\BUILD_ID`（eYs-YyFDf0XQJugH8zZcO）
- 命令运行记录（本验收会话输出，逐条可复核）：
  - `npx playwright test tests/e2e/reading.spec.ts -g "R-09"` → 5 passed (7.5s)
  - `npx playwright test tests/e2e/reading.spec.ts -g "R-09 滚动跟随" --repeat-each=10` → 10 passed (27.0s)
  - `npx playwright test tests/e2e/reading.spec.ts` → 17 passed (19.1s)
  - `npx playwright test tests/e2e/space-pages.spec.ts` → 8 passed (5.3s)
  - `npx playwright test tests/e2e/chat-source-links.spec.ts chat-message-locate.spec.ts` → 21 passed + 12 passed
  - 独立浏览器脚本 → pass=55 fail=0 total=55

## 资源释放说明

验收期间 5174 由本验收者独占（先手动启动后改为 playwright 托管复用）。收尾已执行任务卡指定命令停止监听进程，并复核 `netstat` 确认 5174 无 LISTEN——**端口已释放**。
