# B4 实际命令与单轮结果

2026-10-03已按用户要求暂停。最新原E2E152通过/1失败（书籍第二页明确中断）；原14聊天未执行，stream曾启动后已优雅关闭。以下每个历史轮次按其实际候选/计时保留，不拼一次全绿；当前接续见[B4暂停交接](B4-PAUSE-HANDOFF.md)。

当前源码候选r17：878产品/45可执行QA/5共享契约，SHA `7ee8b05c5bdacd17c3410c08f6a31b026fbcf26a895f227c9e2cb877d8b792b1`；旧r13实际执行按原身份保留。每个runner收据保存完整argv/cwd/隔离env/PID/exit/elapsed/原日志SHA；合并stdout/stderr的runner如实标合流，F runner另保留两条原流。新系统根全部保留。表中各轮分别计数，未合并成一次测试。

| 实际执行 | 单轮结果与候选 | 原始入口 |
| --- | --- | --- |
| T70独立 `run-probe.ps1 ... -Run fixed-first` | r2，8完整场景/165真实HTTP，exit0；20k全证据/100页、1000学生KP/5班KP | `b4-v00-analysis/run-fixed-first/receipt.json`、`RESULT-fixed-first.md` |
| P完整 `run-probes.ps1 -Label owner-fixed-second ...` | r10，64通过/0失败/0skip，81904ms/exit0；16新表/7资产恢复及真实恢复后HTTP | `b4-v00-practices/OWNER-FIX-SECOND-RESULT.md`及index/summary |
| R09原4例、R10原2例修后 | r9分别4通过/4320ms与2通过/2989ms；真实foreign404/DB原样 | `b4-v00-practices`对应原runner/log/收据；R09首轮1pass3fail/R10首轮2fail保留 |
| canonical `npm run test:api`（full-api-owner-first） | r9，1698通过/1规模门控skip，270.40s、272077.419ms/exit0 | `b4-root/full-api-owner-first-command.json`与完整log；r13后端共同源精确绑定，未冒称重跑 |
| canonical `npm run check`（check-ui-final-first） | r13，typecheck/lint零警告/111文件1105单测/build通过，104654.563ms/exit0 | `b4-root/check-ui-final-first-command.json`、log、next-env receipt |
| R11 `vitest ... vitest.r11.config.ts`（r11-final-first） | r13，原2场景/21 expect，2通过/1653.261ms/exit0，pre/post0 | `b4-v00-practices/R11-FINAL-FIRST-RESULT.md`、原results.json及root命令/log |
| F原独立FE18（ui-fixed-first） | r12，18通过/2143ms/内外exit0、pre/post0；r13仅stable函数alias写法，另有新独立R11和第五真browser | `b4-v00-browser/RESULT-fe-ui-fixed-first.md` |
| seed real-fifth | r13，新0wcy3811根，child27700/1534ms/exit0，27sourceblocks/图片真实GET200/实际题owner/4DB检查通过 | `b4-v00-browser/RESULT-seed-real-fifth.md`与command/原两流 |
| B4真browser real-fifth | r13/新build，完整1通过/24647ms，child24916和outer均0，原118matcher不改 | `b4-v00-browser/RESULT-browser-real-fifth.md`、command、results、trace、chain、三下载与17PNG |
| mobile-visual-fixed-first（同一测量脚本） | r13，8补屏/0写请求、对比5.16855556/整行310px、exit0/2085.439ms | `b4-root/MOBILE-VISUAL-RESULT.md/json`、完整66条trace与截图；修前1.013659399/exit1保留 |
| 完整原E2E real-first | 152pass/1fail/0skip/0retry，exit1/379467.171ms；B4-R13导航首败保留 | `b4-root/full-e2e-real-first-command.json/log`、`b4-e2e-real-first/results.json/xml`（已实际核实） |
| 完整原聊天 first | 未执行：用户要求暂停；仅stream fixture启动并优雅exit0，原finally返回，端口释放 | `B4-CHAT-TASK-CARD.md`、external config及retained stream wrapper |

构建身份 `BUILD-IDENTITY-b4-r13.json`：ST2AWsfwxRYxFKZb_qsip，2007实际文件，SHA fb25165fa1c0d25dda45f519a8a5876094ad29815fb99bb745fd5a6fc2612d42，真实API代理8001。next-env原字节SHA0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc，构建后精确恢复。用户新frontend3820的创建/完整命令/三个实际HTML身份见root/frontend-r13-ready.json。

所有首败见B4-ROOT-FIRST-FAILURES/B4-INDEPENDENT-ISSUES和各独立原件；G1的153 E2E与API1599是独立历史，不能代替B4新增门禁。T70 A8/API1698/P64共同源绑定见独立R13-COMMON-SOURCE-BUILD-BINDING，不把未重跑项标成新执行。

## B4-R13 导航修复新增轮次

原完整E2E real-first实际152pass/1fail/0skip/0retry，exit1/379467.171ms，确认200后库标签false，actual双#library，首败完整原件保留。r14诊断878/45/5 SHA647a6607…2163d；独立正确行为红测仅一次2fail/3343.414ms。r16作者相关两文件74pass/9973.423ms，root仅7产品源范围；r15仅冻未执行，关闭按钮名称在首次执行前校正。修后原独立green-first实际1pass/1jsdom Modal环境错误1388.763ms，原断言/2it不改，仅descriptor恢复式dialog native环境适配。r17正式878/45/5 SHA7ee8b05c5bdacd17c3410c08f6a31b026fbcf26a895f227c9e2cb877d8b792b1，独立新绿2pass和新check1110/build已实测通过，用户新5174/PID5172四HTML200已核；随后第六新build完整browser已实测通过、最新原E2E152/1书籍中断，原14chat因用户暂停未执行，不沿用r13 build。

r17 新canonical check-nav-final-first实际exit0/104383.649ms，111文件1110unit/typecheck/lint0warning/build pass；original next-env原字节精确恢复0f706…fcc。新buildJi-Jz8X9yY2R_79JOPivD/2007files/actual8001、identity SHA29252444df2d9fb4160c3f26b9d28baaf3b93271014a49f696883feb51ae8b93，前后878/45/5及1150保护0漂移。用户手动停止旧5174已核，用户新manualstart已核PID5172/四HTML200；随后第六完整browser1pass/24925ms、手机8补屏exit0/2062.749ms；最新完整E2E152/1、exit1/497986.093ms，chat因用户暂停未执行。

## r17 实际新增执行与暂停

| 实际执行 | 单轮结果 | 原件 |
| --- | --- | --- |
| r13-navigation-green-fixed-first | 原2例/21expect，2pass/1382.246ms、inner/outer0，878/45/5前后0 | [r17独立绑定](b4-v00-analysis/R17-FINAL-BINDING.md)及其实际QA原receipt索引 |
| canonical check-nav-final-first | 111文件1110unit/typecheck/lint0warning/build，exit0/104383.649ms；原next-env精确恢复 | `b4-root/check-nav-final-first-command.json`、log、`BUILD-IDENTITY-b4-r17.json` |
| browser-real-sixth | 原完整118matcher，1pass/24925ms，child536/outer0；真实自动generation/确认query返回及完整回流 | [第六报告](b4-v00-browser/RESULT-browser-real-sixth.md)、原command/results/482entry trace/chain/三下载/17PNG |
| mobile-visual-nav-final-first | 8补屏、0写请求、contrast5.168555560、整行310px，exit0/2062.749ms | [手机报告](b4-root/MOBILE-VISUAL-R17-RESULT.md)、原62entry trace/8PNG |
| full-e2e-real-fixed-first | 原24spec/153case，152pass/1fail，0skip/0flaky/retry0；exit1，JSON497242.205ms/outer497986.093ms | [全量报告](b4-v00-practices/FULL-E2E-REAL-FIXED-FIRST-RESULT.md)、`b4-root/full-e2e-real-fixed-first-command.json/log`、`b4-e2e-real-fixed-first/results.json/xml` |
| stream-api-first | 仅原stream fixture隔离启动/关闭，不是14聊天执行；PID23268自然exit0/originalFixtureFinallyReturned=true、stopfile优雅退出，log647B | `b4-root/stream-api-first.json/log`、`stream-api-first-pause-stop-request.json`、[暂停资源](b4-root/PAUSE-RESOURCE-CLOSURE.json) |

最新E2E唯一首败原books267行第二页strip期待0实际1/120000ms。独立实际DOM明确interrupted及继续按钮，恢复与后续最终数据/锁断言未执行、触发根因未证实。暂停后没有业务复验或QA/产品修复；原14聊天没有测试命令收据或业务通过数。
