# B5-V00 QA v11 窄修 / STOP

ROOT明确授权：r6完整27首轮19pass/8fail，新增8均在renderWorkspace首先ReferenceError React is not defined，尚未执行本地导航/保存业务断言。仅新v11两件unit test/config副本补classic JSX真实React及可逆global React适配；产品、root setup、JSX runtime、v10及全部19/8名字/body/oracle/assert/fake/deferred/预算不改。

原r6整轮保留：PID23264 exit1/2496.954ms，source938/QA2762前后漂移0，child/log关闭、样本保留。完整JSON、log、command SHA绑定新非执行结果 results/EXEC-r6-unit-first-INDEPENDENT-v1.json。原19不能拼入后续27通过，8个初始化错误不是产品缺陷确认。

active unit为v11/unit/vitest.config.ts，完整27=原19+原v10新增8。browser仍v9完整8、API仍v3的42、seed仍v3。仅新增import React from 'react'及beforeEach的真实React global stub；既有afterEach unstubAllGlobals还原原值。配置只替换v10新增测试dir为v11，其他include/setup/jsdom/10000ms及编译runtime原样。逐行diff与逐字还原验证均保留：移除两新增行即可还原完整v10 raw bytes；config替换dir即可还原完整v10 raw bytes。

静态Node24.19 PID18580 exit0/1588.087ms，私有类型/语法及导入源诊断0。真实Vitest list PID3100 exit0/2083.515ms，完整收集27，所有19/8标题与v10收集一致，业务assertions0；没有unit runtime、HTTP、browser、服务、Git或新agent。

只读保全对r6：source938、旧QA2762、冻结33、build2004（zmNsDUHtq1oRmN-ixNctj）及旧v10清单212件全部rawSHA0变化。v11尚无真实业务通过结论，须ROOT含本版的新r7 whole候选及独占新label完整27单轮，不需修改产品或重新build。额外HTTP身份policy拒绝保持not_run，未绕过。

已执行collect命令（原输出不可复用覆盖）：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:NODE_OPTIONS='--no-experimental-webstorage'
& 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/vitest/vitest.mjs' list --config 'docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/v11/unit/vitest.config.ts' --json 'docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/v11/COLLECT-v11-first.json'
```

未来完整27 unit命令，尚未执行，以下由ROOT实际新候选/label授权替换：

```powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:NODE_OPTIONS='--no-experimental-webstorage'
& 'apps/api/.venv/Scripts/python.exe' 'docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/run_command.py' --label '<ROOT fresh unit label>' --candidate '<ROOT r7 whole candidate>' -- 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/vitest/vitest.mjs' run --config 'docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/v11/unit/vitest.config.ts' --reporter=json --outputFile='docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-v00/results/<ROOT fresh private dir>/results.json'
```

STOP：封存本版后停写全部私有可执行QA，等待ROOT新整轮。无自有连接或运行服务。
