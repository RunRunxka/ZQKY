# B-R05-EXT2-A1 独立验收报告（v1）
- 候选：1ca673c ｜ 起点：de3f8b7 ｜ 验收时间：2026-09-18 20:55–21:15
- 验收者：Independent-Acceptor ｜ 资源：5174（验收期间独占，收尾已释放）
- 结论：**pass**（0 fail）

## 候选与环境核对
- HEAD = 1ca673cc2cd8d47b4975186418bc84f97f6180d5（分支 codex/replica-review-20260908），`git log` 确认起点 de3f8b7 之上仅 1 个实现提交；工作区无未提交产品源码改动。
- `git diff --name-only de3f8b7..1ca673c -- tests/ apps/web/src/styles/ .zcode/` 输出为空：tests/、space.css/globals.css/motion.css（实际路径 apps/web/src/styles/）、.zcode/ 零改动。
- 服务以 `node scripts/run-web.mjs start 5174` 启动（生产模式 next start，.next 为候选构建产物），`/lesson-plans` 就绪 200。
- 种子路径：书籍走页面「载入演示数据」按钮（幂等实测 2→2）；R-11/长文案用例按 `tests/e2e/course-resource-faults.spec.ts` 与 `shoot.mjs` 字段直写 localStorage（`zhiqikeyuan:courses`、`zqky.replica.knowledge.v1`），仅测试上下文，未触碰真实数据。
- 浏览器：仓库 Playwright 1.58.2 + msedge channel（与 playwright.config.ts 一致），无头；Browser Use 技能子智能体不可用，改用仓库自带工具链，不影响验收客观性。

## 逐项结果
| # | 验收项 | 结果 | 命令/操作 | 证据 |
|---|---|---|---|---|
| 6.1 | 提交范围：tests/、三全局 CSS、.zcode 零改动 | pass | `git diff --name-only de3f8b7..1ca673c -- tests/ apps/web/src/styles/ .zcode/`（空输出）；`git show --stat 1ca673c` 仅 5 个产品文件 + docs/qa 证据 | 本报告「候选与环境核对」 |
| 6.2 | books.css/courses.css 前缀与 !important | pass | `grep -c '!important'` 两文件均 0；courses.css 全部选择器以 `.courses-page`/`.courses-*` 起头（0 例外）；books.css 存量 3 个 `space-*` 选择器（:22/:28/:34 起）经 `git show de3f8b7:...books.css` 比对为起点已有且本批 diff 未触碰，候选新增部分均带 `.books-*`/`.books-page` 前缀 | grep 与 git diff 输出（本报告） |
| 6.3 | §7.2「不做」项未做 | pass | grep StatCard 0 结果；CoursesShelf.tsx 卡片无会话数字段（页脚仅资料数/「尚未附加资料」）；附加资料保留弹窗路径（AddResourceForm Modal）；新建入口仍为页头按钮非网格末格卡 | apps/web/src/features/courses/CoursesShelf.tsx、CourseDetail.tsx 源码 + t7-add-resource-modal.png |
| 1 | 三视口无横向溢出（4 页 × 1440/1920/390 = 12 组合） | pass | 探针脚本统计 `scrollWidth<=innerWidth` 与 `right>innerWidth` 元素：12 组合全部 scrollWidth==innerWidth、超界元素 0；截图目测层级/截断正常，与 after/ 主要页面目测一致 | A1-shots/t1-viewport-audit.json、t1-*-1440x900/1920x1080/390x844.png（12 张） |
| 2.1 | 390 下 `.books-rail` position:static、随文档流滚动 | pass | 计算样式 static、max-height none；滚动容器（.module-workspace-content）scrollTop 0→400 后 rail top 247.5→-152.5（随文档移动，未吸顶）；rail bottom 478.5 < reader top 496.5，正文同列（left 20/right 370）无挤压遮挡 | t2-rail-truncate.json、t2b-rail-scroll.json、t2b-rail-390-scrolled.png |
| 2.2 | ≥900px 宽 rail 恢复 sticky | pass | 1440 计算样式 `position: sticky; top: 16px`；1440×600 实滚验证：scrollTop 0→277 后 rail 吸顶 top=16px（宽视口不回退） | t2c-1440-scroll.json、t2d-sticky-verify（控制台输出）、t2d-sticky-1440x600-scrolled.png |
| 2.3 | 四页 390 视口 scrollWidth/超界元素 0 | pass | 见 #1 同一探针数据：4 页 390 组合均 0 | t1-viewport-audit.json |
| 2.4 | 长文案截断（ellipsis）非溢出 | pass | 课程长卡名 clientW 275/scrollW 711 ellipsis；详情长单元名 199/583 ellipsis；长资料名 64/543 ellipsis，后缀「（不可用…）」shrink-0 right=320<390 未出界；书籍长标题卡片正常换行、超界 0 | t2-rail-truncate.json、t2-longname-courses-390.png、t2-longname-course-detail-390.png、t10-longtitle-book-390.png |
| 3.1 | Tab 可达：书籍卡片/搜索/CTA/删除 | pass | 键盘 Tab 走查：新建书籍→搜索框→卡片链接→继续创建→删除→（第二卡）全部 ring=true 可见 | t3-a11y.json（booksTab）、t1-books-1440x900.png |
| 3.2 | Tab 可达：课程勾选框/移除钮/附加资料/详情按钮 | pass | 编辑→归档→删除→编辑大纲→勾选框×2→附加资料→移除钮依序到达，全部 ring=true；移除钮 focus-visible 后 opacity 稳定为 1（150ms 过渡完成）；行 hover 同样 opacity 1 | t3b-focus-course.json、t3k-transition-delay 输出、t3k-remove-focus-settled.png、t3h-remove-row-hover.png |
| 3.3 | 断言前提：nav 章节目录/aria-current/翻页 | pass | `nav[aria-label="章节目录"]` 存在含 4 链接；`aria-current="page"` 指向 p0；ArrowRight 翻至 p1；书签「签」标记计数与 books-courses.spec.ts:81 前提一致 | t3-a11y.json、t6-book-detail.json、t6-reader-page.png |
| 3.4 | 断言前提：课程文案/aria 全套 | pass | banner role=note「课程学习会话未接入」；标题「大纲（1/2 已完成，下一单元：一元一次方程）」；勾选框「标记「分数与比例」为已完成」；移除钮「移除资料 课程标准库」；后缀「（不可用：目标已删除或未载入）」；「返回课程列表」链接；progressbar now=50/min=0/max=100；「已归档课程（1）」折叠头文案 | t3-a11y.json（course-detail checks）、t7-courses-interact.json |
| 4 | 减少动画全局压制 | pass | reducedMotion:'reduce' 下卡片/进度条/资料行/移除钮/单元 transitionDuration 全部 1e-05s（globals.css:587 + motion.css:10 全局机制接管，实测计算样式非仅看 CSS） | t4-books-reduced.png、t4b-course-reduced.png、t4/t4b 控制台输出 |
| 5.1 | 书籍列表：搜索过滤/清空/两击删除/幂等/新建 busy | pass | 「分数」→1/2·匹配计数行；清空→2 恢复；删除→确认/取消钮出现，取消复原 2、确认后条目消失；演示载入 2→2 幂等；新建书籍提交 disabled=true+spin，350ms 后跳转新书 | t5-books-interact 控制台输出、t5-books-search-filtered.png、t5-books-delete-confirm.png、t5-books-after-delete.png、t5-books-create-busy.png |
| 5.2 | 书籍详情：提案 busy→大纲→编译 busy+加载提示→阅读器 | pass | draft 页确认提案 disabled+spin 后进入大纲；确认大纲 disabled+spin 且出现「正在生成章节页面（模拟编译）…」加载行，完成后进入可读书籍；就绪书续读定位 p0、侧栏当前页高亮、ArrowRight 翻页 p1、添加书签→移除书签按钮切换+侧栏 2 枚「签」 | t6-book-detail.json、t6-proposal-busy.png、t6-spine-busy-loading.png、t6-reader-page.png |
| 5.3 | 课程列表：hover/归档展开/创建 busy | pass | 卡片 hover transform translateY(-2px)+box-shadow 出现；归档折叠区展开显示归档卡；创建课程提交后跳转新课程详情 | t7-courses-interact.json、t7-courses-card-hover.png、t7-courses-archive-open.png |
| 5.4 | 课程详情：进度条联动/单元视觉/资料行显隐/附加弹窗 | pass | 勾选未完成单元后 aria-valuenow 50→100、标题变「2/2 已完成，全部完成」；单元编号 1./2.、covered 删除线 line-through、下一单元蓝底 rgb(239,245,255)；资料行 hover 移除钮 opacity 0→1（键盘 focus 同）；附加资料弹窗→附加成功提示→移除成功提示全流程 | t7-courses-interact.json、t7-course-syllabus-toggled.png、t7-add-resource-modal.png、t7-resource-detached.png |
| 5.5 | R-11 三态回归 + 重试链路 | pass | 目标已删除：不可用后缀、无错误 banner、大纲正文可见；目录读取失败：「（目录读取失败，暂无法确认）」+ 错误 banner（「知识来源目录格式不兼容，原数据已保留。」）+ 重试钮、大纲正文不被阻断；可用：label 为链接、无后缀；重试链路：失败→重试仍失败→原始损坏数据逐字节未变→修复后重试恢复为链接 | t8b-r11-faults.json、t8c-retry.json、t8-missing-target.png、t8-dir-read-fail.png、t8-available-target.png、t8c-retry-recovered.png |
| 附 | 归档课程详情抽查（/courses/demo-course-archived） | pass | 标题带「已归档」chip、按钮变「恢复」、空大纲空态文案 | t9-archived-course.png、t9 控制台输出 |

## 失败项最小复现
（无 fail。曾出现的两个疑似项均排除：）
1. 移除钮键盘聚焦后 opacity=0 疑似 focus-visible 失效——复测确认：Tab 到位后立即读 computed opacity 为 0 是 150ms transition 未完成；等待 600ms 后 opacity=1、`matches(':focus-visible')=true`。CSSOM 规则顺序正确（`.courses-resource-remove{opacity:0}` → `.courses-resource-remove:focus-visible{opacity:1}`），非缺陷。
2. 首轮 R-11 Case2/3 种子未生效——属验收脚本自身键名错误（KB 键应为 `zqky.replica.knowledge.v1`、资源需 position/addedAt 字段），修正后三态全过，与产品无关。

## 未执行项与原因
- after/ 截图像素级 diff：未做（采用打开页面实测 + 与 after/ 主要页面人工目测一致；像素 diff 对不同构建时间戳意义有限）。
- 归档折叠头 color 150ms 过渡单独采样：未单独采样（transition 存在于 courses.css:88，reduce-motion 全局压制已实测；属低风险视觉细节）。
- 控制台错误监听：probe 脚本为一次性 Playwright 直驱，未注册 console listener；以页面可见错误表现为准（全程未见错误横幅、空白区、失败占位）。
- e2e spec 未运行（任务卡明确不要求且禁止修改）；`npm run typecheck/lint/test:unit/build` 未重复执行（实现者已提交通过记录，本批产品文件仅 5 个且静态核查范围吻合，浏览器实测基于候选 .next 构建产物）。
- 本任务为纯前端本地模拟视觉推广：无真实供应商调用、无凭证路径，相关后端验收项不适用（not_applicable，不计入 not_run）。

## 与实现者结论的差异
- 无结论性差异。实现者提交说明的全部主张（前缀边界、窄视口解除 sticky、busy 态、进度条、资料行显隐、R-11 不变、§7.2 不做项）均独立复现成立。

## 证据清单
- 报告目录：docs/qa/B-R05-EXT2/A1-REPORT.md（本文件）
- 截图与 JSON：docs/qa/B-R05-EXT2/A1-shots/（12 张三视口 + 25 张交互/故障/焦点截图 + 9 个 JSON 审计数据 + probe/ 下 15 个可复跑探针脚本）
- 关键数据文件：t1-viewport-audit.json、t2-rail-truncate.json、t2b-rail-scroll.json、t2c-1440-scroll.json、t3-a11y.json、t3b-focus-course.json、t6-book-detail.json、t7-courses-interact.json、t8b-r11-faults.json、t8c-retry.json
- 5174 已释放：验收收尾执行 `Get-NetTCPConnection -LocalPort 5174 -State Listen | ... Stop-Process`，端口无监听。
