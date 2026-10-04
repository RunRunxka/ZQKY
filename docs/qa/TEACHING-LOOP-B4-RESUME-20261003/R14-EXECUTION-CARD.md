# B4-R14-V00-20261003 v1.3 · 两条独立真实UI单轮

负责人 P（独立执行与结果卡），CTRL（来源冻结/前端身份/最终验收），A（独立静态审核）。待r21所有source/QA停止、共同源与原asserts/timeouts静态核查、QA type/lint通过、现有5174实际身份核验后由CTRL显式放行，本卡不是执行结果。

唯一新范围 `b4-v00-e2e/r14-recovery.spec.ts` 的两条180000ms真实UI场景：正常生成0 Continue与明确合法模拟整页失败后1真正Continue，均独立验证stored ready/finished、所有页可读、同runId、笔记/ID、native held/pending0、legacy null、独立trusted click与helper清理四flag。不得通过种入ready或直接写localStorage伪造成功。原UI显式本地模拟身份必须保留。

helper完成与原strip count0同时等待；shared deadline不扩原120s或180s预算。失败保留/rethrow，不删assert、不加retry、sleep、reload或把interrupted当成功。两例都完成才通过，不拼合多轮。trace=on与JSON/JUnit/三阶段截图/独立fact附件均在今日r14-fixed-first，配置直接原config继承仅限定新独立scene/webServerundefined/输出/trace。

正式单轮由今日run_check.py label `r14-independent-fixed-first`、candidate `docs/qa/TEACHING-LOOP-B4-RESUME-20261003/CANDIDATE-r21.json` 运行：

`C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe node_modules/@playwright/test/cli.js test --config docs/qa/TEACHING-LOOP-B4-RESUME-20261003/r14.external.config.ts`

当前用户5174 PID21816/r17实际proxy8001仅使用与只读核验，P不能启动/结束服务或触碰用户会话。隔离Playwright新context和newOS run_check root，formal环境/凭证/真实草稿/旧样本均不得读取或写入。执行前后candidate.py audit分别写unique r21 audit；唯一run保留merged UTF8 stdout/stderr、真实PID/exit/ms/candidateSHA、全部失败和artifact。结束后结果卡登记实际attempt/pass/fail/retry/skip、独立点击0/1、真实存储/DOM/锁与cleanup、6张图路径与SHA（CTRL逐张查看）、两trace完整zip CRC/entry/SHA、所有新sample路径保留。

本轮不授权原153或14聊天，后者另卡；不得自行修source/QA、换候选或重跑，失败先报CTRL。止B4/noGit/noB5/no外部。

执行必须经今日run_check.py：三external config真实run/绝对输出目录在Popen前核唯一；已有输出只拒绝，不删除、不换label覆盖。异常仅等待/必要结束该次自有Popen句柄并关闭stdout/log，后续CTRL另核spec自有descendants/API端口，未实核不能声称全部释放。

此卡为busy恢复判据v2窄修后的新单轮；需ZQKY_B4_R14_RUN=fixed-first，全新r14-fixed-first输出，原r14-first 1/1及全部终态未执行边界保留。当前两UI未放行，待CTRL实际r21全来源audit/type/lint/独立审查/前端身份核验后显式放行；不因为故障首轮后期compilation截图就免终态验收。
