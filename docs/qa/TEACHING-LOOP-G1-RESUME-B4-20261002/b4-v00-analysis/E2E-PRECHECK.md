# B4-E2E-PRECHECK v1 · 只读静态预检

未发现原完整 E2E/chat integration 把 B4 学情分析或针对练习误判为规划页的过期预期，当前没有需要删除或放宽的业务断言。两份外置配置静态保留完整集合和原测试约束；CTRL已登记的chat包装器覆盖原fixture样本清理缺口，无需改原stream fixture。**未执行测试、收集、构建或服务，不记业务/浏览器验收通过。**

快照 2026-10-02T13:16:25.419452+00:00。只写本两份报告；24个 E2E spec、2个 integration spec 与8个相关源码/配置共34文件的当前SHA在JSON，未比较历史候选，文件数不代表参数化运行用例数。未读用户数据/实际temp，不改源、执行QA、配置或历史。

## 导航与规划断言

services/navigation.ts 当前登记 /learning-analysis「学情分析」与 /practices「针对练习」为ready。tests/e2e/navigation.spec.ts:5 的plannedRoutes仅为 /papers、/co-writer、/reading、/space、/templates；:16–23 的规划徽标、能力、刷新、无假form/button断言仍适用。shell-home-nav.spec.ts:73 的plannedSelf也没有B4入口。sidebar-chat-fixes/sidebar-transition沿用标签、唯一aria-current、各路由图标数组一致性，没有写死旧导航总数。chat integration只有chat-live.spec.ts:147侧栏品牌可见断言涉及导航，无B4规划状态预期。

navigation.spec.ts:34、shell-home-nav.spec.ts:52、sidebar-chat-fixes.spec.ts:3 是历史覆盖子集，尚未直接包含两新入口，这是覆盖边界而非确定失败。专属B4真实浏览器应验证两页面/导航；若追加矩阵行，应仅新增并保留原断言。本轮不需要旧预期适配，不删除或降级任何用例。

## 外置配置

| 项目 | 完整E2E | chat integration |
| --- | --- | --- |
| 原配置 | playwright.config.ts | playwright.chat.config.ts |
| 外置配置 | b4-e2e.external.config.ts | b4-chat.external.config.ts |
| 继承与完整绝对目录 | :13 ...original，:14 tests/e2e | :12 ...original，:13 tests/integration |
| 原测试约束 | fullyParallel=false，workers=1，test45000ms，expect10000ms | 同左 |
| use | 原baseURL5174、channel、retain-on-failure、viewport1440×900 | 原baseURL5174、channel、retain-on-failure |
| 变化 | :15 webServer undefined；新本批run路径；list/json/junit | :14 webServer undefined；新本批run路径；list/json |

没有testMatch/testIgnore/grep/grepInvert/projects/shard/retries/use覆盖；spec代码和断言未被配置替换。原各spec的test.setTimeout（books120/150/180s、assessments180/240/300/600s、question-bank180s）和视频test.use保持，逐行见JSON。未找到only/skip/fixme；未执行--list。run标签均限制^[a-z0-9-]+$。

webServer取消使原自动起停与启动超时不再执行，生命周期交用户/CTRL管理；这个明确差异不能写成webServer全字段相同。测试/expect超时和workers仍继承原件。原scripts/test-chat.mjs自动build并运行旧config，不是本次external入口，源码仍原样保留。

## keep-data 与实际chat启动计划

真实CLI外层需带ZQKY_KEEP_TEST_DATA=1，external config不自行设flag。assessments.spec.ts:105与question-bank-real.spec.ts:80记录新根；stopBackend先等自有child close与logStream close，失败就保留。路径归属核验后，assessments:249–251、question-bank:164–166记录childClosed/logClosed并return，后续默认rm分支不执行。该静态事实不是已经运行的资源收据。

原tests/fixtures/stream_backend.py:216为TemporaryDirectory(prefix='zqky-chat-test-')、:230无条件cleanup，无keep分支。CTRL实际计划使用b4-root/stream_backend_keep.py：:15–20先核test/本批新temp/16333/embedding9；:34–37只拦截精确prefix，:28用mkdtemp在data.parent建自有子目录，:31–32 cleanup只记retained，类没有TemporaryDirectory finalizer。其他prefix委托原实现，:41–42以__main__跑原fixture，:44恢复工厂。当前fixture只访问name/cleanup，包装器兼容；原HTTP/SSE/上游/8001和8002逻辑未重写，保留缺口被该实际启动计划覆盖。

最小建议仅为通过已登记wrapper实际启动，并由CTRL记录真实PID、8001/8002、新root、日志和退出。不需要改原stream_backend；本轮未启动wrapper、检查端口/进程或验证实际样本保留。

未执行：Playwright收集、全E2E/integration、专属B4真实浏览器、build、wrapper及全部服务、进程/端口归属与退出、Word/WPS像素。报告完成后停写，适用门禁留给CTRL。
