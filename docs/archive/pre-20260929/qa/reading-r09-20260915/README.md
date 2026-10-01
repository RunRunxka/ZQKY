# R-09 阅读导航与滚动验收证据（2026-09-15）

批次：B-READING-NAV-SCROLL v1 ｜ 起点 e7cd87f ｜ 隔离端口 5174 / 构建目录 .next-test 与 .next

## 首败（修复前，隔离浏览器 + 应用自带演示数据 + 生产代码中的显式模拟 companion-service（非真实供应商调用））

| 文件 | 说明 |
| --- | --- |
| 01-first-failure-scroll-pulled-back.png | A：流式中用户上滚到顶后被增量强拉回底部（RESULT_A {"rightAfterManual":0,"top":212,"max":212}） |
| 02-first-failure-late-end-in-new-session.png | B：生成中切到新会话，新会话立即出现旧会话"生成中"块（turnBlocksInNewSession:1） |
| 03-first-failure-history.png | C：切会话用 replaceState，后退直接离开阅读板块（afterBack = /reading） |

## 修复后（同一脚本复跑 + 正式回归）

| 文件 | 说明 |
| --- | --- |
| 04-fixed-r09-user-scroll-held.png | 桌面：上滚后位姿保持、出现"回到最新"，正文与整页位置不变 |
| 04-fixed-r09-mobile-user-scroll.png | 390 视口 + reducedMotion reduce：抽屉内上滚保持、"回到最新"可用 |

## 复跑与回归结果

- 首败脚本（_work/reading-r09/r09-first-failure.spec.ts）：A/B/C 全部转为通过。
- 正式回归：tests/e2e/reading.spec.ts 的 R-09 五例全通过；完整 reading.spec.ts 17/17。
- 全量 e2e 154/154、typecheck/lint 通过、build 通过。

## 数据与资源保护

- 全程使用隔离上下文与演示数据；未触碰用户 5173 会话、官方 .env/.local-data、真实草稿。
- 仅停止本批次拥有的进程（Playwright webServer，端口 5174）。
- 截图不含密钥、令牌或真实用户数据。

## 独立验收者黑盒用例（只读留档）

- accept-r09-blackbox.spec.ts：验收者自写用例留档（原在 gitignore 的 _work/accept-r09/）
- 结果：8/8 通过；日志见提交说明。
- 说明：该文件为第三方验收证据副本，不影响 tests/ 正式测试发现范围。

后续2026-09-15方向审查补充：Node26.2使用README已有参数 `--no-experimental-webstorage` 可通过292项单测。R-09已测滚动/跨会话/导航结论保持；错误态按钮重试和重复/失效终态的受控补测见STATUS READ-RETRY/READ-END，不宣称默认服务自然复现新回归。
