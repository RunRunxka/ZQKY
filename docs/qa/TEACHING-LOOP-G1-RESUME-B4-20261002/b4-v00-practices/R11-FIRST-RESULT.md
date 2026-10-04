# B4-R11-FE-DIAG v1 — r11-first

冻结候选 `CANDIDATE-b4-r11-visual-diagnostic.json`（SHA256 `9d46ff61a027b342db19b8f5ee975a14418fb38817a6d1ec1dd410fc7b56c781`）单轮实际 **0 pass / 2 fail / 0 setup error / 0 skip**，exit 1。两项正确行为断言都明确复现 R11：所选报告事实已经更新，固定报告历史的同一 run 仍显示“尚未准备”。本轮为独立诊断红测，未关闭缺陷或声称修复验收通过。

| 场景 | 已实际通过的前置条件 | 首败 |
| --- | --- | --- |
| 新建 A queued → succeeded | 固定创建输入一致；任务成功可见；报告事实与证据区域出现 | `r11-run-a` 历史按钮仍“尚未准备”，预期“已准备” |
| 切换来源和 run，再手动刷新 B | 旧 A observation 的 signal 已 aborted；迟到 A success 未覆盖 B 来源、成绩、报告；手动刷新后 B 报告事实出现 | `r11-run-b` 历史按钮仍“尚未准备”，预期“已准备” |

第二例的旧结果过滤断言位于失败之前，已实际执行通过；失败之后的最终历史否定断言没有执行，不据此另计通过场景。QA 保留真实 `useObservedJob` 和 `useAsyncResource`，只用明确的 DTO/API 响应及任务事件控制组件输入，不调用生产聚合逻辑，不宣称这是 HTTP 或浏览器验收。

两个场景分别耗时 1126.956 ms 和 1104.2794 ms；Vitest 总计 3.11 s，现有隔离 wrapper 记录 3629.593 ms。运行时为现有 `C:\Program Files\nodejs\node.exe` v26.2.0，Vitest v3.2.4。此绝对路径已通过实际 `Get-Command node.exe` 的 `Source` 核对，并修正 summary 路径 metadata；没有重跑或改动原日志、收据。实际 child PID 28248 已退出；wrapper status=complete、exit=1；运行后 PID 不存在，105888 字节日志可独占打开，证明日志写入句柄已关闭。日志由既有 wrapper 合并保存真实 stdout 和 stderr，未伪称分别捕获。

唯一新外层临时根 `C:\Users\96022\AppData\Local\Temp\zqky-b4-r11-first-48fr7gb0` 全部保留。外层环境由已冻结 `b4-root/run_check.py` 设置 test / UTF8 / 新 data 根 / 空教材目录 / Qdrant 16333 / embedding 9 / `NODE_OPTIONS=--no-experimental-webstorage` / `ZQKY_KEEP_TEST_DATA=1`；本轮是 jsdom 组件测试，没有启动业务 app 或监听服务，没有建立四库、触及正式凭证或操作用户前端。

候选前、后分别核全部 878 产品文件、43 可执行 QA 文件、5 契约文件，均 0 漂移。完整证据为 `r11-first-pre.json`、`r11-first-post.json`、`r11-first-results.json`、`R11-FIRST-SUMMARY.json`，及根下 `b4-root/r11-first-command.json` / `b4-root/r11-first.log`。日志保留完整首败 DOM 和堆栈；工具展示被截断不影响本地完整日志。未重试，未修改任何 QA/产品/配置源。

准确已执行命令（cwd 为仓库根）：

```powershell
& 'apps/api/.venv/Scripts/python.exe' 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-root/run_check.py' --label r11-first --candidate 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/CANDIDATE-b4-r11-visual-diagnostic.json' -- node.exe node_modules/vitest/vitest.mjs run --config docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-v00-practices/vitest.r11.config.ts --reporter=verbose --reporter=json --outputFile=docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-v00-practices/r11-first-results.json
```

补充时序：上述 post 是运行结束后实际完成的核验快照，其时间见 `r11-first-post.json.at`，不是对后续修复状态的推断。CTRL 收到红测 child 退出通知后另行修改 `LearningAnalysisWorkspace.tsx`、其作者单测和样式，并冻结 r12 修复候选；这些后续产品改动不属于本次 red 运行，也不改变已经保存的实际 pre/post 收据。本方执行 QA 源持续未改。

红测报告已闭合，按新卡等待/执行另 label 的独立修复复验；原红测文件和计数保持保留。
