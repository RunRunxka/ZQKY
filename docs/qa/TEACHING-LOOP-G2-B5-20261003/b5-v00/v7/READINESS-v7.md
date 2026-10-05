# B5-V00 QA v7 准备与停写卡

ROOT 明确授权在 r2 完整8首败及离线归因保全后新增 v7。可写仅 v7 与新非执行 results；v1–v6、产品、公共契约、旧结果、服务和Git均不改。R06迟到回调擦模型已由真实r2帧确认，ROOT另OPEN FEv4只改SourcePanel与lesson-workspace作者测试；当前QA准备不能执行修改中的产品。

active API42仍v3/api，seed仍v3/browser/seed_runtime.py；unit为v7/unit/vitest.config.ts（旧10+v4完整6+v5完整2+新增1=19），browser为v7/browser/external.config.ts完整8。ROOT serve_b5.py不用改；真正执行必须等待FE作者STOP/ROOT新候选、unit19新完整单轮通过和新check/build/真实API样本身份，再独立完整8；不把r1/r2的3绿拼入新轮。

新unit为迟到来源正确行为单例，手写完整Class/AnalysisRun/ClassReport/ModelProfile/LessonEvidence DTO。初次A/getRun受控pending时实际选择M2/61/手写要求，releaseA后真实UI与传入状态均须原值不擦；真正换B/getRun pending期间再改M1/74/新要求，releaseB后仍原值，而旧evidence/练习/KP清除，同学科固定题保持，必须明确勾B知识点才classReady。旧18原源码与断言逐字保留；不调用业务HTTP、不用产品merge当oracle。

四browser主链原模型select位置保持，没有在其前新增initial-run等待，也不会reselect掩盖产品擦输入。新增教材verify真实POST200、固定document/revision/字符范围等seed、真实evidence summary已在UI采用，之后才loadQuestions；生成前再确认原模型/43/要求未擦。所有旧KP/context/full11/teacher6/partial/unselected/history/undo/newsave/Word ZIPXML/100ms冻结print断言保持。

history intent只将clock.install移到第一次prepareA/真实JSON下载之前；pause仍初次clean11字段已核之后、dirtyA之前，原目标时间和所有dirty/cache/cancel/B/history/local/完整6份公开backup oracle保持。r2新page是下载后实际事件，但其URL/类型/frame未留，clock内部精确挂死成因未证明；本调整仍须runtime验证，不能由静态源码写成通过。原historycopy、unknown和dual-tab完整步骤不改。

预算：browser45000ms/expect10000ms/retry0/worker1/fullyParallelfalse/traceon；unit10000ms原值。实际输出在results/run-{freshLabel}，config拒复用JSON/artifacts。ROOT runner独占新label/candidate绑定源QA、新TEMP，所有失败原件保全。

静态final：Node24.19 PID28268/exit0/1433.639ms，transpile/private type diagnostics0，AST19unit+8browser；first PID12336/exit0/1489.745ms原件保留，追加固定教材revision断言后重新final静态。框架browser --list：PID15852/exit0/914.801ms，真实收集完整8/results0，未启动browser/HTTP/TCP。只读r2 seed用于模块收集，未来实际须ROOT新绝对seed；unit框架收集/runtime均not_run直到新稳定候选。旧v6清单67含旧v1–v5所有54件SHA0变化。FEv4授权写入中，没有宣称产品源仍匹配r2。

收集已完成命令（不复跑旧label）：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:NODE_OPTIONS='--no-experimental-webstorage'
$env:B5_V00_RUN='v7-collect-first'
$env:B5_V00_SEED_JSON='H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/b5-runtime-r2-seed.json'
$env:PLAYWRIGHT_JSON_OUTPUT_FILE='H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/results/v7-collect-first.report.json'
& 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/@playwright/test/cli.js' test --list --reporter=json --config 'docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/v7/browser/external.config.ts'
```

未来unit19完整单轮入口，以下占位必须ROOT新授权确定，尚未执行：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:NODE_OPTIONS='--no-experimental-webstorage'
& 'apps/api/.venv/Scripts/python.exe' 'docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/run_command.py' --label '<ROOT fresh unit label>' --candidate '<ROOT new stable source/QA candidate>' -- 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/vitest/vitest.mjs' run --config 'docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/v7/unit/vitest.config.ts' --reporter=json --outputFile='docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/results/<ROOT fresh private unit dir>/results.json'
```

未来browser8新完整单轮入口，必须等新build/API候选；尚未执行：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:NODE_OPTIONS='--no-experimental-webstorage'
$env:B5_V00_RUN='<ROOT fresh browser label>'
$env:B5_V00_SEED_JSON='<ROOT new absolute runtime seed>'
Remove-Item Env:PLAYWRIGHT_JSON_OUTPUT_FILE -ErrorAction SilentlyContinue
& 'apps/api/.venv/Scripts/python.exe' 'docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/run_command.py' --label '<ROOT fresh immutable receipt label>' --candidate '<ROOT new stable build/source/QA candidate>' -- 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/@playwright/test/cli.js' test --config 'docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/v7/browser/external.config.ts'
```

逐行差异 results/V7-LINE-DELTA-v1.diff/.json 已保留，自审未删除任何旧业务断言或放宽预算；按ROOT席位限制未再spawn。本版unit/runtime未执行，browser只收集。API42原单轮、原18单轮、r1/r2首败、四库作者runtime与独立16只读、所有样本分列保留。必需新完整19/8、逐图/真实Word/冻结print、ROOT153后14与最终资源/保全/文档核对仍待执行；人工Word/WPS/付费provider/正式Qdrant允许not_run。ROOT额外r2HTML/proxy请求policy拒绝保持not_run，未通过工具或Agent/端口重试。

STOP：封存本卡/清单后V00停写停跑，等ROOT新候选明确EXEC；无自有服务/浏览器/HTTP/数据库连接。
