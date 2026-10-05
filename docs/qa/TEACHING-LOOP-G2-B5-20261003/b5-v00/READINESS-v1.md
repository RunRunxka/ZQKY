# B5-V00 v1 准备封存

独立 QA 自身语法检查通过：Python compile/AST 与 TypeScript transpile/AST，PID 21696、exit 0、326.582 ms、源前后无漂移。证据 `preparation/prepare-v1.json`。此检查不导入或执行产品，没有起 TCP，没有访问正式资源。静态展开测试共 **58**：API/privacy/job/R01/R02 **42**，unit **10**，真实 browser **6**（主链四视口各一个，unknown 原包恢复与双标签 CAS 各一个）。这是 AST 静态发现数量，pytest/Vitest/Playwright 框架运行与运行时收集均未执行。

CTRL `ctrl/serve_b5.py` 已只读核验匹配 helper：先隔离 env、Settings(credentials_file=None)、显式 `SecretStore()`；标准 seed app 调 `seed_for_browser` 后 seed TestClient 完成生命周期；同目录、同 memory secrets 建 fresh app；返回 fixture 可在 fresh app 安装 `.complete` 的真实 HTTP transport；关闭时 restore。seed 文件持有业务标识与教材选择，不含凭证。无额外模型端口；真实 API 8001 与新 build 前端 5174 由 CTRL 所有。

稳定候选下的命令用法（`<candidate>` 必须替换为 CTRL 已明确冻结的相对清单路径，label 每轮唯一）：

```powershell
& 'apps/api/.venv/Scripts/python.exe' 'docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/run_b5_api.py' --label b5-v00-r1-api-first --candidate '<candidate>' 'docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/api'
$env:NODE_OPTIONS = '--no-experimental-webstorage'
& 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/vitest/vitest.mjs' run --config 'docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/unit/vitest.config.ts' --reporter=json --outputFile='docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/run-r1-unit-first/results.json'
$env:B5_V00_RUN = 'r1-browser-first'
$env:B5_V00_SEED_JSON = '<absolute CTRL isolated service seed JSON>'
& 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/@playwright/test/cli.js' test --config 'docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/browser/external.config.ts'
```

Node 命令应由 CTRL command runner 绑定 candidate 源前后、env/PID/exit/count/ms；这里不启动任何服务。Browser config `webServer: undefined`、retries 0、原 45000/10000 ms 预算、全程 trace；已有输出拒复用。API runner 建新 OS TEMP、测试数据保留、禁止正式 credential/source/Qdrant。已存全部失败原件后，产品缺陷交 CTRL；若执行揭示 QA 自身错误，先报告并申请新的 QA revision，不在原 v1 上悄改。

当前产品验收全部 **not_run：等待 CTRL CANDIDATE-B5-rN 与作者停写**。真实付费模型教学质量、Word/WPS 人工排版、正式 Qdrant 检索及正式数据迁移未执行。完整工程回归、原 153/聊天14 与四库备份恢复依 CTRL 独立收据审核，不用本准备检查冒称通过。

2026-10-03：V00 v1 自身 QA 源码停写，等待候选冻结。
