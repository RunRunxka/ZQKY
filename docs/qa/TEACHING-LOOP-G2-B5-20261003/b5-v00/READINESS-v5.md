# B5-V00 v5 来源分页准备

CTRL 在 v4 完整16首轮结束后明确授权新 v5 独立补充，FEv3 正在窄修，产品不能 runtime 验。v1–v4 字节与失败原件均保留。只新增 `v5/unit/source-lists.test.tsx`、config、本卡、静态结果与清单。

active unit 为 `v5/unit/vitest.config.ts`，继承原 unit10、v4完整6，再加2，总18。原 R04 的422/503循环、来源变化/unknown/recovery/A→B→A、后页班级断言全部不改。API42、browser8、seed 仍采用 v3。

两例使用手写完整 `AnalysisRunView`、`ClassReportRow`、`PracticeSetView/PracticeRevisionView`、单题 RichContent 与固定题引用，按当前契约逐字段构造；没有借产品转换/merge 生成 oracle。用真实 SourcePanel/Provider/DocumentContext 的注入能力接口：241 ready报告最后固定报告可选且明确KP/单班可用；同一固定run的241 reviewed练习最后固定revision可勾选，保持该run身份。真实分页形状 offset/limit/total/items，越过200页必取到且每次limit≤200；故障发生在后页，首次空环境不得显示前页半份可选来源，明确重试后完整列表恢复。报告/练习两个测试各先故障再重试；若首阶段失败，其后步骤未执行，不用分支跳过掩盖失败。

仅静态 transpile/AST 与私有 fixture type diagnostics；不运行框架 collection/产品。等待 FE 停写及 ROOT 新 candidate 冻结后，以全18单轮执行。原API42不在此准备阶段重复调用。

```powershell
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$env:NODE_OPTIONS = '--no-experimental-webstorage'
& 'apps/api/.venv/Scripts/python.exe' 'docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/run_command.py' --label '<CTRL new immutable label>' --candidate '<CTRL newly frozen candidate>' -- 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/vitest/vitest.mjs' run --config 'docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/v5/unit/vitest.config.ts' --reporter=json --outputFile='docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/<new private output>/results.json'
```

静态完成：Node24.19.0，PID27972，exit0，1302.24ms，transpile与v5私有type diagnostics均0，AST18，旧v1–v4清单byte drift均0，证据 `preparation/prepare-v5-second.json`。首次静态发现 testing-library role options不支持 `exact`，首失败JSON原件保留；封存前只移除该无效属性，字符串name本身维持完整精确匹配，未改预期。

本版 runtime、browser、框架收集均 **未执行**；不启停服务，不写产品/旧QA/预算，不读取正式数据。完成静态后停写并报告 READY。
