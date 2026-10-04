# R11 独立修复复验 — r11-fixed-first

冻结候选 `CANDIDATE-b4-r12-ui-fixed.json`（SHA256 `07a8900807a6cd58c4a5231c2f9dc0bfabd034bd7ea4366644617de4a28cfc54`）按原 QA 单轮实际 **2 pass / 0 fail / 0 setup error / 0 skip**，exit 0。原 2 个场景、21 个 `expect` 调用及配置字节全部保留；没有改断言或重试。此前 `r11-first` 实际 2 fail 的首败日志、JSON、临时根和报告完整保留，未覆盖。

正确行为实际通过：新建 queued 报告观察到任务成功后，同一 run 的固定历史变为“已准备”；切换来源与报告后旧 observation 被取消，迟到旧任务未覆盖当前 B 列表或报告；手动刷新 B 报告后，报告事实及 B 历史同步为已准备。两项完整场景分别耗时 160.1512 ms、106.8407 ms。

Vitest 总计 1.12 s，隔离 wrapper 实际记录 1622.397 ms；现有 Node v26.2.0 / Vitest v3.2.4，外层 `NODE_OPTIONS=--no-experimental-webstorage`。实际 `Get-Command node.exe` 的 `Source` 为 `C:\Program Files\nodejs\node.exe`，已修正 summary 的绝对路径 metadata；没有重跑或改动原日志、收据。child PID 22212 已退出，wrapper status=complete、exit=0；PID 实际不存在，915 字节完整日志可独占打开，记录流已闭合。既有 wrapper 合并保存真实 stdout/stderr，未伪称分别捕获。

运行前与运行后全量核冻结 878 产品、43 可执行 QA、5 契约文件，均 0 漂移；post 实际时间 `2026-10-02T14:43:01.674146+00:00`。两个 QA 源 SHA256 仍分别为 `f5d4f896518a01ade85fb815243288132cef4af82edb034d83c70374c9480b7b` 和 `9a2b7d15d90e7ef57a789cce48401fb98891099f63114f76b2923c52eb10f409`。

新外层临时根 `C:\Users\96022\AppData\Local\Temp\zqky-b4-r11-fixed-first-dr8f79m9` 全部保留。现有 wrapper 设置 test、UTF8、新 data 根、空教材目录、Qdrant 16333、embedding 9 和资源保留 opt-in；本轮为真实组件与 hook 配合受控 literal API/任务事件的 jsdom 测试，没有运行业务服务、监听端口、读取正式凭证或操作用户前端。其结论仅限 R11 组件正确行为，不替代真实 HTTP、浏览器或完整 B4 门禁。

完整证据：`r11-fixed-first-pre.json` / `r11-fixed-first-post.json` / `r11-fixed-first-results.json` / `R11-FIXED-FIRST-SUMMARY.json`，以及根下 `b4-root/r11-fixed-first-command.json` / `b4-root/r11-fixed-first.log`。完整准确单轮命令（仓库根 cwd）：

```powershell
& 'apps/api/.venv/Scripts/python.exe' 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-root/run_check.py' --label r11-fixed-first --candidate 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/CANDIDATE-b4-r12-ui-fixed.json' -- node.exe node_modules/vitest/vitest.mjs run --config docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-v00-practices/vitest.r11.config.ts --reporter=verbose --reporter=json --outputFile=docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-v00-practices/r11-fixed-first-results.json
```

报告已闭合，本方所有源与结果停写，等待 CTRL 完整后续门禁。
