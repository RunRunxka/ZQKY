# B5-V00 QA v6 准备与停写卡

任务：B5-V00-QA v6，仅新的完整 browser8 副本、配置与证据；v1–v5 和产品均不改。ROOT 正式任务卡 B5-V00-QA-v6-TASK.md SHA c5fcc7f38d6a52a48a43d15e3f2e03b397af1c4ead3c73858851db0086cced82。原 r1 八例首轮 1通过/7失败及全部 trace/log/样本完整保留；本版是新 QA 修正，不把旧首败写成通过。

active browser 为 v6/browser/external.config.ts，两份完整 spec 收集8。active API42仍 v3/api；unit18仍 v5/unit/vitest.config.ts；runtime seed仍 v3/browser/seed_runtime.py，ROOT serve_b5.py 无需更改。没有重新执行产品或 API/unit。新实际浏览器必须等 ROOT r2 冻结、新隔离8001 seed与明确执行授权，前端为 ROOT 保留的 EuGU-xptkS4Dv7wiXoxD4 构建/proxy8001；实际身份与字节绑定以新 r2 为准。

修正：四主场景等待固定报告和该 run 的练习真实 GET200，严格等待真实KP checkbox数等于seed后全部check，新增导入完整正文/analysisRunId/context scoreRevision/KP身份深等；fieldset has 相对legend scope纠正。dual-tab 课题 exact:true；history过程教学设计/二次备课选真实exact textbox。clean不存在恢复cache时，通过公开JSON备份真实下载，schemaVersion1/data深等手写完整11字段；前后URL/cache原字节不变，已有cache仍先深等。dirty/copy/undo/redo的cache断言原样保留。完整8、原生成/partial/teacher6/未选字段/history/undo新保存/Word/100ms冻结print、keyboard Tab/焦点/Escape、四viewport reducedMotion均保留。

预算保持 test45000ms/expect10000ms/retries0/workers1/fullyParallelfalse/traceon；没有轮次拼绿或单case替代完整8。新结果目录在 b5-v00/results/run-{B5_V00_RUN}，config禁止已有JSON/artifacts复用；ROOT runner的log/receipt保存在ctrl独占新label。

静态诊断：Node24.19.0 PID28520，exit0，1025.849ms，transpile/private type diagnostics0，AST8。真实Playwright --list：PID25936，exit0，913.534ms，完整8/results0，未启动browser/业务HTTP/TCP。collection 使用只读保留的r1 seed作模块数据加载，真实执行将使用ROOT新r2绝对seed；不能把collection写成runtime。

收集实际命令（已完成，不复跑同label）：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:NODE_OPTIONS='--no-experimental-webstorage'
$env:B5_V00_RUN='v6-collect-first'
$env:B5_V00_SEED_JSON='H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/b5-runtime-r1-seed.json'
$env:PLAYWRIGHT_JSON_OUTPUT_FILE='H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/results/v6-collect-first.report.json'
& 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/@playwright/test/cli.js' test --list --reporter=json --config 'docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/v6/browser/external.config.ts'
```

未来实际入口（尚未执行，三个占位符必须由ROOT新授权确定；执行前清除collection专用PLAYWRIGHT_JSON_OUTPUT_FILE，保留默认JSON/XML/list三报告）：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:NODE_OPTIONS='--no-experimental-webstorage'
$env:B5_V00_RUN='<ROOT fresh browser run label>'
$env:B5_V00_SEED_JSON='<ROOT new r2 absolute seed JSON>'
Remove-Item Env:PLAYWRIGHT_JSON_OUTPUT_FILE -ErrorAction SilentlyContinue
& 'apps/api/.venv/Scripts/python.exe' 'docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/run_command.py' --label '<ROOT fresh immutable receipt label>' --candidate '<ROOT new frozen r2 candidate>' -- 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/@playwright/test/cli.js' test --config 'docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/v6/browser/external.config.ts'
```

完整逐行delta保留 results/V6-LINE-DELTA-v1.diff/.json。独立子审查 results/V6-DELTA-READ-AUDIT-v1.md SHA371f848f0f478d11a14babb04e783369f893e535d9cd4630ca9d7120e58c33d3，已STOP，无删减业务断言/预算放宽。原v5清单54件SHA0变化，产品r1清单938件SHA0变化。全部静态stdio/JSON/新TEMP保留。

覆盖边界：API42/18unit已实际单轮通过，browser仍原1/7，新v6 runtime未执行；完整8的四viewport候选/history逐图、真实Word内容/ZIPXML、冻结print仍必须实际做。ROOT153后chat14及最终资源退出/源QA构建/旧历史保全/权威文档后验仍待执行。四库作者实际restore1与V00独立16只读连接全行/blob/hash核对分列，不能写成V00重新runtime恢复。允许not_run：Word/WPS人工排版/实际另存PDF、付费provider教学质量、正式Qdrant/正式数据迁移与既有超规模压力；这些边界不能豁免隔离真实Word下载/print门槛。恢复与全技术门槛细项见独立coverage报告。

STOP：本卡与v6清单封存后V00及子审查停止写入和执行。没有服务/Git/正式数据/凭证动作，等ROOT新冻结候选授权。
