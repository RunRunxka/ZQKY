# R11 r13 最终候选独立复验 — r11-final-first

冻结候选 `CANDIDATE-b4-r13-ui-final.json`（SHA256 `68b9222de673e2abd6601c1001a6198b3e8e1d84276a1a1a483d2a1885f2327b`）按原 QA 新 label 单轮实际 **2 pass / 0 fail / 0 setup error / 0 skip**，exit 0。原 2 场景、21 个 `expect` 调用和配置字节全部未改。本轮对应 CTRL 在 r12 复验闭合后处理稳定 reload 解构及 lint 警告的新候选，独立于此前 red / fixed 两轮；旧日志、JSON、收据、报告和临时根完整保留，没有拼接计数、重试或覆盖。

实际通过：新建 queued 报告观察到任务成功后，同一 run 的固定报告历史变为“已准备”；切换来源与报告后旧 observation 被取消，迟到旧终态未覆盖当前 B 列表或报告；手动刷新 B 后其报告事实及历史同步已准备。两个完整场景分别耗时 153.5738 ms、91.0412 ms。

Vitest 1.12 s；wrapper 记录实际 1653.261 ms。现有 Node v26.2.0 / Vitest v3.2.4，`Get-Command node.exe` 实际解析首项 Source 为 `C:\Program Files\nodejs\node.exe`，summary 使用该实际字符串。child PID 19708 已退出，wrapper status=complete / exit=0；PID 实际不存在，914 字节日志可独占打开，输出流/日志已闭合。原收据保存完整 argv、cwd、外层隔离环境和开始/结束时间；现有 wrapper 合并完整 stdout/stderr，未伪称分开捕获。

前、后实际逐项核全部 878 产品文件、43 可执行 QA、5 契约文件，均 0 漂移；post 时间为 `2026-10-02T14:53:14.401302+00:00`。本轮 QA 源 SHA 仍为：test `f5d4f896518a01ade85fb815243288132cef4af82edb034d83c70374c9480b7b`，config `9a2b7d15d90e7ef57a789cce48401fb98891099f63114f76b2923c52eb10f409`。

新 OS 外层临时根 `C:\Users\96022\AppData\Local\Temp\zqky-b4-r11-final-first-135aj4ao` 保留。外层在启动子进程前设置 test / UTF8 / 新 data 根 / 空教材根 / Qdrant 16333 / embedding 9 / `NODE_OPTIONS=--no-experimental-webstorage` / `ZQKY_KEEP_TEST_DATA=1`；本轮仅 jsdom 真实组件与 hook 加受控 literal API/任务事件，不启动业务 app/服务或监听、不触及正式凭证或用户前端。本结论仅限 R11 正确组件行为，完整 E2E 尚未执行，仍等待新前端、第五轮独立浏览器/mobile 和 CTRL 后端释放及单独放行。

完整实际证据：`r11-final-first-pre.json`、`r11-final-first-post.json`、`r11-final-first-results.json`、`R11-FINAL-FIRST-SUMMARY.json`，根下 `b4-root/r11-final-first-command.json` 和 `b4-root/r11-final-first.log`。仓库根 cwd 已执行准确命令：

```powershell
& 'apps/api/.venv/Scripts/python.exe' 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-root/run_check.py' --label r11-final-first --candidate 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/CANDIDATE-b4-r13-ui-final.json' -- node.exe node_modules/vitest/vitest.mjs run --config docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-v00-practices/vitest.r11.config.ts --reporter=verbose --reporter=json --outputFile=docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-v00-practices/r11-final-first-results.json
```

报告闭合后，本方所有文件与执行停写，等待 CTRL 后续门禁。
