# CTRL 单次命令记录

工作目录 `H:\备份xuexi\智启课源`。后端业务解释器启动前均设置UTF8、`ZQKY_ENV=test`及本批新的系统temp `ZQKY_DATA_DIR`；不使用正式数据或旧六目录。前端均 `NODE_OPTIONS=--no-experimental-webstorage`。以下列实际核心命令，完整stdout/退出码见对应证据；重复执行的结果不相加。

| 命令／日志 | 单次结果 |
| --- | --- |
| `apps/api/.venv/Scripts/python.exe -m pytest -c apps/api/pyproject.toml apps/api/tests/test_g1_job_lease_retry.py apps/api/tests/test_jobs_engine.py apps/api/tests/test_b3_review_job_fixes.py apps/api/tests/test_tabular.py -q -o addopts='' --junitxml=docs/qa/TEACHING-LOOP-G1-B4-20261002/root/jobs-first.xml`；[日志](root/jobs-first.log)、[XML](root/jobs-first.xml) | 65 passed / 1 warning，17.68s，exit0；新租约与retry14条，既有相关回归一起执行 |
| `node node_modules/vitest/vitest.mjs run --config vitest.config.ts apps/web/src/components/ui/RichContentRenderer.test.tsx`；[日志](root/omml-r3.log) | 8 passed / 1文件，1.22s，exit0；前两次路径启动错误见首败索引 |
| `npm.cmd run typecheck`；[日志](root/g1-typecheck-first.log) | exit2，新测试夹具五处TS18049；原实现者修夹具后全check包含类型检查通过 |
| `npm.cmd run lint`；[日志](root/g1-lint-first.log) | exit0，0errors/0warnings |
| `npm.cmd run check`；[日志](root/g1-check-first.log) | exit0，typecheck/lint/109文件1088单测/build全过；单测81.80s。构建ZQKY_API_ORIGIN=http://127.0.0.1:8001，next-env随后逐字节恢复现场原件 |
| `npm.cmd run test:api`；[日志](root/g1-api-first.log) | exit0，1599 passed / 1 skipped / 1既有warning，232.67s。跳过为既有规模环境门控；G1-SCORE169单次回归已显式开启200×100通过，不合并计数 |
| `apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-B4-20261002/freeze.py freeze g1-r1` / `apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-B4-20261002/freeze.py audit g1-r1` | 原825项及后验0漂移、旧629项0漂移、next-env一致；[原清单](CANDIDATE-g1-r1.json)、[原后验](AUDIT-g1-r1.json)保留 |
| `apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-B4-20261002/freeze.py freeze g1-r2` / `apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-B4-20261002/freeze.py audit g1-r2` | r2只补安全.env.example覆盖，共826项；共同825项不变，完整后验0漂移、旧629项0漂移、next-env一致；[清单](CANDIDATE-g1-r2.json)、[后验](AUDIT-g1-r2.json) |
| `apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-B4-20261002/root/seed_browser.py`；[日志](root/browser-seed.log)、[元数据](root/browser-seed.json) | exit0，新四库经现有真实确认闸门建立固定三叶卷；临时根登记在root/browser-data.txt |
| `apps/api/.venv/Scripts/python.exe -m uvicorn teaching_loop_backend:app --app-dir tests/fixtures --host 127.0.0.1 --port 8001 --log-level info`；[日志](root/browser-api.log) | 本批PID4844实际监听8001，fixture明确credentials_file=None，真实四库业务。完成后核CIM完整命令及监听PID，仅停止本批进程；exec最终exit1为显式终止进程，不是测试失败。8001已释放，见[资源](RESOURCES.json) |
| `$env:ZQKY_API_ORIGIN='http://127.0.0.1:8001'; node scripts/run-web.mjs start 5174 2>&1 \| Tee-Object -FilePath docs/qa/TEACHING-LOOP-G1-B4-20261002/root/browser-web.log` | 自动审批拒绝创建5174前端进程，理由仅blocked by policy；未生成前端服务日志或测试结果。未换命令/工具绕过；已请求用户手动启动，浏览器验收待外部状态 |
| `node node_modules/vitest/vitest.mjs run --config docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-fe/vitest.config.ts real-api.test.tsx --outputFile.junit=docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-fe/real-api-third.xml`；[命令JSON](v00-fe/real-api-third-command.json)、[日志](v00-fe/real-api-third.log)、[收据](v00-fe/real-api-receipts.json) | 独立真API组件完整链1passed/1文件，2.21s，exit0；不替代浏览器 |
| `apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-B4-20261002/root/check_closed_data.py`；[最终日志](root/closed-check-accepted.log)、[JSON](root/closed-data-check.json) | 最终exit0，只读本批四库，完整性全部ok/外键零异常；一份正式修订与完整9格正确。root两次QA预期错误及原夹具/日志见首败索引 |

实现者完整命令见[FE](g1-fe/RESULT.md)、[SCORE](g1-score/RESULT.md)、[QB](g1-qb/COMMANDS.md)；新独立命令见[FE](v00-fe/RESULT.md)、[JOBS](v00-jobs/RESULT.md)、[SCORE/QB](v00-score-qb/COMMANDS.md)。三位独立验收均停止写入；单次计数52、53、20及另一次真API链1分别登记。

真实浏览器、三视口/键盘/reduced-motion、全量E2E与受影响聊天浏览器回归 **未执行**：必需前端启动动作被拒绝。浏览器脚本 `--list` 仅收集1例，不计执行通过。模板校验、Word/WPS、真实模型/Qdrant和B4全部门禁也未执行；本批无模板/导出资产改动，B4尚未进入。旧门禁结果不计本轮重跑。当前整体G1未完成。
