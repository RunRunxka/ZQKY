# B5-V00 v3 准备封存

v1/v2 全部字节保持。v3 增量均位于 `v3/`（及本卡、静态证据/清单），active Python 测试为 `v3/api`，active unit config 为 `v3/unit/vitest.config.ts`，active browser config 为 `v3/browser/external.config.ts`。原 API 42 断言完整保留，仅改隔离种子 helper；原 unit 10 完整保留，新增 5；原 browser 主链四视口、unknown、dual-tab 六例完整保留，历史复制升级及新增隔离共 2。**静态展开共 65：API 42、unit 15、browser 8**。框架收集未执行，不能把 AST 数量当作已运行通过。

v3 Python compile/AST 和 TS transpile/AST 零诊断、源前后无漂移；Node v24.19.0，PID 28632，exit 0，325.917 ms。`preparation/prepare-v3.json` 为静态证据，完全没有产品测试或 TCP 启停。

修正的短学号 fixture：仍由真实 HTTP 建 studentNo=1 名单、固定成绩、ready 报告、固定题和 reviewed practice；POST 知识点输入的名字改为手写中文无数字，教材经同生产 parser/blob/catalog 发布并断言规范正文无数字。只有短学号场景的模型回复使用“候选活动甲/乙/丙/丁”和“候选二次甲/乙/丙/丁”；生成别名 K1/E1/new:N1、聚合数字和预算保持。三协议真实 wire 成功与 genuine 身份自由文本拒绝预期没有放宽，不 mock report/业务 fetch。

新增 unit 通过实际 LessonPlanProvider/useServerPersistence/ProposalPanel/useLessonOperation 检查：保存 flush 中 source/model A→B；未知原 M1 的同包重试而当前 M2 候选必须过期；未知包重载后保守过期；A→B→A 最终 signature 相同仍过期/apply 禁止；241 条真实边界形状的来源 fixture 分页，每页 limit≤200，班级/固定报告均读取后页且最后班可选择 KP 并 eligible。来源 API 为显式 unit 能力注入；这些 unit 不是浏览器真实网络声明。原四视口 browser 继续通过真实 classes HTTP 与 KP 选择覆盖运行装配。

新增/升级 browser 走真实 Next：历史 URL 明带 analysisRunId，准备复制回 current URL 同时移除 history/analysis 参数，手写 rule/manual 全 11 字段、dirty、undo/redo、另存新 v3/v4、旧 fixed v1/v2/v3 不变；另一例验证未确认 copy intent A→B 不把 A 替换进 B，取消 dirty leave 保留 A，真正离开到 B/history/local 后 intent 清除，回 current 没有遗留确认按钮，全 11 字段和后台固定对象保持。仅复制检查期间暂停浏览器 autosave 计时；没有替换业务 HTTP 或增加超时/重试/预算。

**CTRL runtime 请切到 `b5-v00/v3/browser/seed_runtime.py`**；控制器的接口、fresh app、共享 MemorySecretStore、install/restore 均保持。普通 browser 也应使用 v3 无数字 KP/教材种子；普通模型回复保持 v1 原值，只有 studentNo=1 场景用无数字回复。CTRL 独占 `serve_b5.py`，V00 没有修改它。

冻结候选后的入口示例（candidate 与 label 由 CTRL 确认，每轮新输出）：

```powershell
& 'apps/api/.venv/Scripts/python.exe' 'docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/run_b5_api.py' --label b5-v00-r1-api-first --candidate '<CTRL stable candidate>' 'docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/v3/api'
$env:NODE_OPTIONS = '--no-experimental-webstorage'
& 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/vitest/vitest.mjs' run --config 'docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/v3/unit/vitest.config.ts' --reporter=json --outputFile='docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/run-r1-unit-first/results.json'
$env:B5_V00_RUN = 'r1-browser-first'
$env:B5_V00_SEED_JSON = '<absolute CTRL v3 isolated service seed JSON>'
& 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/@playwright/test/cli.js' test --config 'docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/v3/browser/external.config.ts'
```

Node 命令经 CTRL runner 绑定 candidate、源前后、命令/env/PID/exit/count/ms/首败。API 新 OS TEMP/None credential/空教材/16333/9/KEEP_TEST_DATA，全部 logs/samples 保留。Browser retries 0、原 45s/10s 预算、全程 trace、四视口逐图；原服务和输出不可复用删除。已执行产品 **not_run：等待 CTRL stable CANDIDATE-B5-rN 与作者停写**；真实供应商质量/Word-WPS 人工排版/正式 Qdrant/正式迁移均未执行。

2026-10-03：B5-V00 v3 自身 QA 源码停写；执行揭示 QA 错误先保全并报告，另开 revision。产品缺陷交 CTRL，不改产品或弱化断言。
