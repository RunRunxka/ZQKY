# B4-R14-V00-20261003 v1.2：r20 原两UI首单轮结果

实际 **1通过、1失败**，R14恢复门禁未通过。只执行授权的2条场景一次；attempts=2、retry=0、skip=0、flaky=0。未执行原153全量或原14聊天；未重跑、未改源码、未启停任何服务或用户前端。故障场景首败完整保留，不能以正常分支通过代替恢复分支验收。

候选 CANDIDATE-r20.json SHA fd6c32fb69d215c8d4cb5a36ceb9fa94253c0afedc248974257cdc636bd5b267；P pre/post AUDIT-r20-r14-p-before.json / AUDIT-r20-r14-p-after.json均实际exit0，879source/53QA/5contracts/2007build/3043protected/prior85全零漂移，next-env原字节与原基线身份一致。外部配置原workers=1、msedge、1440×900、webServer=undefined；两用例原180000ms总预算，120000ms完成等待和既有绝对deadline未改变。

|真实场景|状态|耗时ms|真实Continue|最终事实|
|---|---|---:|---:|---|
|正常生成|passed|16866|独立capture0；helper attempt0/click0|ready/run finished，同run，笔记、全部book IDs与原样本相同，8页均ready，native held0/pending0/legacy null，书库可阅读|
|整页故障|failed|16099|独立capture1可信事件；helper attempt1/click1|helper在单次click后4ms拒绝；ready/最终笔记/ID/locks后置断言未执行|

Playwright report duration35146.016ms；wrapper wallTime36491.677ms。CLI PID16548，worker22516；CLI child exit1/自然关闭，stdoutClosed/logsClosed=true。独立CIM复核两PID均不存在，8001/8002无监听。用户21816仍存在，creationUtcTicks=639265864014910140、原run-web start5174命令未变。新OS根 C:\Users\96022\AppData\Local\Temp\zqky-b4-r14-independent-first-hilt3szg 真实保留；test环境/UTF8/空教材根/16333/embedding9/credentials null/KEEP1均在原收据登记。此为浏览器本地模拟UI，不声称创建四业务库或业务后端子进程。原stdout/stderr按wrapper设计合并捕获到日志，完整日志SHA af25e0eccf8d4a87b72e4fece6030fdc6ddf2d11a24f0c2d5f04afa20eafecab；另有实际独占只读打开的关闭证据。

正常书 bk-murr60s4-kbv6hu / p2 pg-murr60v6-1e7471 / run run-murr60v7-w6hyfl。笔记“正常生成中的真实第二页笔记。”从真实UI保存；独立存储读取及真实textbox/书库可阅读断言通过。helper cleanup=ready/resourcesReleased/observerDisconnected/timerCleared/listenersRemoved均true，contextClosed=false，failure=null/cleanupErrors=[]，独立click listener已移除。成功分支未进入故障注入条件和每click循环；零click循环的断言没有执行。

故障书 bk-murr6duq-tp9tlg / p2 pg-murr6dyh-779ea4 / run run-murr6dyh-d0ccvd。真实UI勾选“注入整页失败”，failPages=1，初次生成最终run stopped、全书compiling，恰一页error、其余7页ready；保存笔记“明确中断后保存的真实第二页笔记。”后确认同书同p2。独立事件atMs1790993330064：isTrusted=true、目标路径准确、stage“生成已中断（无执行器在跑）”、disabled=false，事件rawBooks仍为同run stopped和准确笔记。helper末Observation atMs1790993330068：compiling、准确note、attempt1/click1，reason“interrupted again after one Continue”；差4ms。首败在helper242，P208 Promise.all的result先拒绝；并行P210 strip=0等待随后因测试收尾关闭context而记录error，不能记为耗尽120s或第二独立主失败。

故障cleanup实际resultStatus=failed/failure=原首Error，resourcesReleased/observerDisconnected/timerCleared/listenersRemoved均true，contextClosed=false，cleanupErrors=[]、P cleanupFailures=[]；独立click listener真实移除。这些失败路径metadata被保留，但其成功路径assert未执行。P213～252及成功条件273～283均未执行；没有after/result/finalLocks。故障ready-reader/ready-library两图未生成，实际截图为4张（正常3，故障before1）。

从原0-trace.trace：click call151 start35153.983/end35166.381；after151 snapshot35167.613出现disabled“正在继续…”；before153 snapshot35169.979出现enabled“继续生成”；controller.next call153返回上述首Error。末after158 snapshot35179.272仍引用此前DOM。A独立还原全82个frame snapshots的共享观察为：busy之前、busy期间、恢复enabled之后和末尾stage均仍为interrupted，无preparation/compilation快照。完整stage引用与时间线以A自身报告为独立证据。当前证据不能认定恢复成功，也不能直接推断产品锁或执行器根因。helper把busy“正在继续…”置resumed是只读代码事实，尚不能据此预设产品无问题。

实际断言路径来源是每trace的test.trace before.method=expect与同callId after配对（含poll外层/内部各一记录），不是静态raw matcher数量，也不是新增业务案例。normal实际44条trace expect记录全部completed，43个源行；fault实际21条（20completed、1并行收尾error），20个源行，详见R14-FIRST-ASSERTION-PATHS.json。所有最终note/ID/locks和cleanup成功assert在normal执行，fault如上未执行。

两trace中央目录/EOCD俱在，标准库ZipFile.testzip及逐entry完整解压CRC成功、逐entry SHA已登记R14-FIRST-ARTIFACTS.json：normal162entries/6539097B/SHA 2bf3cb046e5ac7ba0d5f4f920de307b60a9bb97a0bd9abd9189445d4a4c643f2；fault159entries/6960834B/SHA 63a7effc1e8cde0e8d55f28e699e7f57d27969d93ce2470f254344d6886ede4f。JSON/JUnit/所有附件/trace和error-context均保留。正常case与故障case采用不同新隔离browser context，trace各有实际Close context完整after记录；worker浏览器fixture收尾实际完成。截图仅提供原件及SHA，CTRL负责逐图视觉阅读。

准确原命令（在仓库根运行；完整argv/cwd/env/start/exit/PID/耗时见原command.json）：

~~~powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:ZQKY_KEEP_TEST_DATA='1'
$env:PLAYWRIGHT_CHANNEL='msedge'
$env:ZQKY_B4_R14_RUN='first'
& 'apps/api/.venv/Scripts/python.exe' 'docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-root/run_check.py' --label r14-independent-first --candidate 'docs/qa/TEACHING-LOOP-B4-RESUME-20261003/CANDIDATE-r20.json' -- 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/@playwright/test/cli.js' test --config 'docs/qa/TEACHING-LOOP-B4-RESUME-20261003/r14.external.config.ts'
~~~

P执行已结束，执行源保持停写。报告结论是首单轮失败，等待CTRL归因及下一张正式任务卡；不关闭R14/B4。
