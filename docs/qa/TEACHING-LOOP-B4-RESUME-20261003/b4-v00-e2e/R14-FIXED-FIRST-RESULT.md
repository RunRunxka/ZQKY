# B4-R14-V00-20261003 v1.3：r21 两UI固定后独立单轮

**本轮实际2通过/0失败**，2 attempts、retry/skip/flaky均0。正常0次Continue、故障1次trusted Continue；两分支原全部成功后置实际执行，未凭strip0或后期截图代替storage终态。首轮r20的1通过/1失败、原始主Error与未执行边界全部保留，此次只收本新单轮结果；不能宣称历史间歇用例恒绿或B4全部关闭。

候选SHA e558dfbf4af33790328c7c036edfee0aa38c1371da5cb65f6ac8c448ba7c4d39；原P spec/配置/所有预算原字节不变。P pre/post r21-p-r14-fixed-before/after实际exit0，879 source/53QA/5contracts/2007build/3043protected/prior191全部零漂移。原180000总预算、120000完成等待与最早绝对deadline、无retry/reload/sleep/filter全部保持。

|分支|实际耗时ms|bookId / p2 / runId|真实终态|
|---|---:|---|---|
|正常|16829|bk-mursj3ga-gypmdd / pg-mursj3ix-sa82xp / run-mursj3ix-kiwnk2|branch normal、独立capture0、helper attempt0/click0；ready/finished/8页ready|
|整页故障|18194|bk-mursjgi6-w31rrv / pg-mursjgls-pkg7gr / run-mursjgls-1g5dhk|branch recovered、独立可信capture1、helper attempt1/click1；ready/finished/8页ready|

正常笔记“正常生成中的真实第二页笔记。”、故障笔记“明确中断后保存的真实第二页笔记。”均真实UI保存并由独立storage/真实textbox读取；与before相同、原runId不变、bookId/p2 ID固定、bookIds全集相同、页面全可读。故障场景真实UI注入1整页失败、初次明确stopped/interrupted、一页error；点击时独立事件atMs1790995619666记录isTrusted=true、disabled=false、明确interrupted、同book/p2路径、same run/stopped和准确note。真实completedAt1790995620872，1206ms后ready；不是以busy状态当执行完成。

两个原native锁断言均实际通过：held0/pending0/legacy null；reader无interrupted文案并有正确note、书库真实“可阅读”。helper cleanup两者均resultStatus ready/resourcesReleased/observerDisconnected/timerCleared/listenersRemoved=true、contextClosed=false、failure null/cleanupErrors[]；独立capture listener均真实移除，P cleanupFailures[]。原subject/final存储、note、双ID、锁及清理全部后置实际执行。

实际test.trace expect记录normal44、fault59全completed且无error，含poll外层/内部各一条；并不是静态60matcher或新增103业务案例。故障click循环中的trusted/path/stage/disabled/raw同run/note断言实际执行；正常零click循环未进入。每条callId/title/源行/start/end及两个不同新browser context完整Close context收尾在R14-FIXED-FIRST-ASSERTION-PATHS.json。

真实CLI PID16748/worker14860均退出，child/outer exit0；report duration37528.767ms，wrapper wall38236.733ms，stdout/logClosed=true，独占日志打开及自身read关闭已实际记录。8001/8002空闲，未启动业务后端；用户21816同精确creationUtcTicks639265864014910140及原run-web start5174命令保持。新OS根 C:\Users\96022\AppData\Local\Temp\zqky-b4-r14-independent-fixed-first-yuigilwk 实际保留；test/newtemp/UTF8/IOENCODING/KEEP1/16333/embedding9/空教材根/credentials null完整登记。stdout/stderr按wrapper设计合并UTF8保存，log SHA 4d5ecea13a31af8e1e16ed992eb71a14d1c977816795519e09d980d55d133ef8。

两trace完整CRC/central/EOCD通过，逐entry完整解压并记录SHA：normal159entries/6584370B/SHA78aaa76d5a6c03ec2b27fe1d258a3a9c2b213b701f0f35be9659d6fb23376508；fault182entries/8182683B/SHA2ecd49f126adffa287d3396b70b85d295cd68788dac7ad860a537ddff708699a。实际6PNG（每case before/ready-reader/ready-library）全部原路径/大小/SHA在SUMMARY.pngs与ARTIFACTS。CTRL已另行确认实际view全部6图并认可原metadata/锁/终态；P未以hash替代视觉检查。原JSON/JUnit/trace/附件与样本均不删除。

准确命令（原argv/cwd/env/start/end/PID/exit完整见b4-root/r14-independent-fixed-first-command.json）：

~~~powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:ZQKY_KEEP_TEST_DATA='1'
$env:PLAYWRIGHT_CHANNEL='msedge'
$env:ZQKY_B4_R14_RUN='fixed-first'
& 'apps/api/.venv/Scripts/python.exe' 'docs/qa/TEACHING-LOOP-B4-RESUME-20261003/b4-root/run_check.py' --label r14-independent-fixed-first --candidate 'docs/qa/TEACHING-LOOP-B4-RESUME-20261003/CANDIDATE-r21.json' -- 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/@playwright/test/cli.js' test --config 'docs/qa/TEACHING-LOOP-B4-RESUME-20261003/r14.external.config.ts'
~~~

本两UI报告已闭合，源与执行QA停写。后续原153全量按CTRL新卡另跑；此处计数不混入原153或已由CTRL执行的14聊天。
