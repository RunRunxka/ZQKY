# B5-V00 QA v10 / R07 准备与停写

授权 B5-V00-QA-v10-TASK.md。仅新增私有 unit/config、静态/收集/保全材料；原 v1–v9、产品、原完整153两失败 spec/assert/预算和公共契约均未修改。没有新 agent、HTTP、浏览器、服务或 Git 操作。

active unit 改为 v10/unit/vitest.config.ts，四个原 include 原样继承，原19标题与原实际19单轮完全相同、原文件 rawSHA 不变；仅新增8，总27。API42仍 v3/api，browser仍 v9/browser/external.config.ts 原完整8，seed仍 v3/browser/seed_runtime.py；ROOT serve_b5.py 无需改动。

新增测试使用真实 NavigationGuardProvider、LessonPlanWorkspace、DocumentGateway、LeaveProtection、编辑器和600ms串行本地 writer。仅替换 Next 的导航目的边界、可逆 jsdom dialog/viewport 平台适配与显式 repository/dependency ports；没有 mock guard/leave/editor/store/merge，没有调用生产 merge 或作者 oracle。正常场景通过公开表单填写手写最新11字段（含两个完整 ProcessItem 和教师六字段），deferred repository 在成功后调用真实旧键 localDraftRepository.save；独立 ledger 与手写数据核对 save-before-router，不能以状态文字代替旧键完整内容。

8项为 chat/papers 各一快速导航、600ms在途A后新编辑B的两次串行保存、失败保留原字节/全部最新输入及显式重试成功后才离开、空串与截断JSON坏稿各一、真实导入在途及丢回执、恢复的完整原导入 unknown。后两项核强制flush0/导航0/不可放弃、原恢复包不被最新输入改写。未新增同模块 openDocument 独立单例；该共享 leave 决策仍需既有完整 browser 与153修后新单轮实际验收。

静态 final Node24.19 PID21936 exit0/1597.837ms，新QA类型/语法诊断0，导入源码类型诊断0。首静态错误原件保留：误用了 Playwright 的 role exact 选项；仅新v10移除该不支持选项，Testing Library name字符串自身精确匹配。实际规划入口名称为“智能组卷（规划中）”。可逆 dialog/viewport 适配为 jsdom 缺省平台方法，不改变保护逻辑。

实际 Vitest list：PID19468 exit0/2215.780ms，完整27=原19+新增8，业务断言执行0。原19与 results/run-prebuild-v4-unit-first/results.json 的实际标题逐项同集合；没有把原19结果拼入27结果。collect command/JSON/log均保留。

保全：原v9清单201件、原candidate QA2419件、冻结33件均 rawSHA0变化。source938对r5实际差异为FEv5两件（LeaveProtection/workspace作者测试）及ROOT fullcheck/build期间临时next-env派生；对 ROOT B5-PRODUCT-SOURCE-v5 仅临时next-env差异。没有宣称938仍与r5同字节。ROOT新build正在派生，旧2004 build不作修后运行证明；本卡未做build期间全目录审计。修前 LeaveProtection 从已封存独立R07原源记录还原为 .bin，校验SHA与原r5完全一致，不作为可执行源或作者oracle。

原完整153首轮151pass/2fail及两trace/R07证据原件保留，原r5完整8通过归属原r5候选。v10业务runtime明确 not_run：必须等本版STOP、ROOT next-env精确恢复及新whole source/QA候选，完整27新单轮，然后新build候选完整8/153/14。测试预算10000ms原值，未添加重试/skip/only或调整浏览器45s/10s预算。

已执行的 collect 命令（仅收集，不执行测试）：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:NODE_OPTIONS='--no-experimental-webstorage'
& 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/vitest/vitest.mjs' list --config 'docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/v10/unit/vitest.config.ts' --json 'docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/v10/COLLECT-v10-first.json'
```

未来完整27 runtime命令，以下占位须ROOT新授权/新候选确定，尚未执行：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:NODE_OPTIONS='--no-experimental-webstorage'
& 'apps/api/.venv/Scripts/python.exe' 'docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/run_command.py' --label '<ROOT fresh unit label>' --candidate '<ROOT new stable source/QA candidate>' -- 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/vitest/vitest.mjs' run --config 'docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/v10/unit/vitest.config.ts' --reporter=json --outputFile='docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/results/<ROOT fresh private dir>/results.json'
```

STOP：清单/结果封存后全部私有可执行QA停写停跑，等待ROOT新候选授权。无自有连接、服务、浏览器或子agent。额外HTML身份policy拒绝继续 not_run，未绕过；人工Word/WPS、付费provider和正式Qdrant仍为允许 not_run。
