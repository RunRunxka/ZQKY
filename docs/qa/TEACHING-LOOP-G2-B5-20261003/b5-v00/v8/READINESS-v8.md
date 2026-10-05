B5-V00 QA v8 · READY · STOP（仅准备）

产品和所有 v1–v7 原件不写。新可执行文件仅 v8/browser/external.config.ts、history-copy.spec.ts、independent.spec.ts。API42保持v3/api，unit19保持v7/unit/vitest.config.ts；真实浏览器 seed 仍 v3/browser/seed_runtime.py，ROOT runtime controller 不必改 helper。

完整browser8与45s test /10s expect / retries0 / workers1 /四viewport reducedMotion /Tab focus+Escape以及所有11字段、teacher6、部分采纳、history/undo/save、unknown原包、CAS、Word/print与6backup oracle均保留。仅修两处实际trace证明的QA调度：intent首次真实current GET/UI确认后、首公开JSON下载之前 pause 原03:00:01，之后不再调clock；unknown初始干净后台UI确认后、A fill之前安装并pause04:00:01冻结600ms autosave，让原手动提交+真实200丢响应可控，不forceclick、不删断言。

静态Node24/TypeScript diagnostics0/private diagnostics0，AST unit19/browser8；Playwright --list实际8/results0，未启动浏览器/业务HTTP，新的OS TEMP保留。完整逐行diff及原块字节对等审查见results/V8-LINE-DELTA-v1.diff/json、V8-DELTA-SELF-REVIEW-v1.json。最初审查谓词误把原未改window.print的afterprint dispatch当新增，原失败记录保留，改为dispatch增量检查后绿，可执行QA未因此修改。

真实运行须等待ROOT含v8新候选和新隔离API seed，并使用独占新label/output目录；不能沿用r3旧QA candidate声称清单一致。以下runner参数已只读核实际argparse：

```powershell
$env:PYTHONUTF8='1'; $env:PYTHONIOENCODING='utf-8'
$env:NODE_OPTIONS='--no-experimental-webstorage'
$env:B5_V00_RUN='<ROOT新独占label>'
$env:B5_V00_SEED_JSON='<ROOT新绝对seed路径>'
Remove-Item Env:PLAYWRIGHT_JSON_OUTPUT_FILE -ErrorAction SilentlyContinue
& 'apps/api/.venv/Scripts/python.exe' 'docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/run_command.py' --label '<ROOT新独占runner-label>' --candidate '<ROOT新candidate路径>' -- 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/@playwright/test/cli.js' test --config 'docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/v8/browser/external.config.ts'
```

不执行服务/Git/正式数据/付费模型，不重试之前policy拒绝的额外HTML identity。只读原计划traceHTML/static证明served build身份。r3首轮6pass2timeout和全部图/4Word/4print/1backup/8trace/三协议wire保留，不拼绿。STOP。
