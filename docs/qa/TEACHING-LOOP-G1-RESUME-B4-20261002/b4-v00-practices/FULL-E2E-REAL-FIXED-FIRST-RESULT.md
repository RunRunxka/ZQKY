B4 FULL E2E real-fixed-first：原完整24 spec / 153 case单轮实跑，152通过、1失败，0跳过、0 flaky、153实际attempt且retry均0。全量门禁未通过；本报告不关闭B4。全部原集合与上一首轮逐file/title/line/column一致，JSON与JUnit均153/1/0，report errors为空。没有grep/shard/subset/list/trial/retry或超时、业务断言、源码变更。

候选 CANDIDATE-b4-r17-nav-final.json SHA256 7ee8b05c5bdacd17c3410c08f6a31b026fbcf26a895f227c9e2cb877d8b792b1；build Ji-Jz8X9yY2R_79JOPivD / 2007文件，身份SHA256 29252444df2d9fb4160c3f26b9d28baaf3b93271014a49f696883feb51ae8b93。pre与post均878产品/45可执行QA/5契约/2007build零漂移，next-env SHA256 0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc精确一致。post于2026-10-02T16:06:40.029166+00:00落盘，随后才通知CTRL门禁完成/端口释放。用户5174 PID5172（2026-10-02T23:46:46.573793+08:00创建）保持；测试CLI用既有Node24.19.0，不改用户前端Node26。

本轮唯一首败在 books-commit-safety.spec.ts:267:35（用例声明238），第二标签 .book-pipeline-strip 等待120000ms后expected 0 / actual 1，123次定位仍为1，实际用例耗时137679ms。第一标签生成条等待和此前两笔记保存轮询已越过；失败后的跨标签最终笔记/两书记录/两页无悬挂锁断言未执行。CURRENT_STATUS中R-14是该类已知未关闭跨批场景，但本轮没有证明根因，也没有将其忽略或豁免。error-context是测试主page快照，不能据该单页快照代替第二标签状态。失败完整error/stack/trace/error-context与原日志保留于本新输出，未重试。

原 question-bank-real 两例均通过；生成链5630ms，公共retry 3723ms。已完整执行原“查看已入库题目”后library aria-selected=true、数学+固定KP筛选total1/确认ID一致、1卡片人工校对内容、详情stem与formal KP、Provider1次且固定profile的全部后续断言。原附件实际receipt queued@0、terminal succeeded@1、确认1题/failures[]、Provider1次与released=true见解码JSON；原公共retry业务链也完整通过。原上一轮152/1题库首败仍保留，14个原引用证据hash零漂移（原summary与RESULT另存SHA），不把两轮拼为一次全绿。

开始2026-10-02T15:57:27.110373+00:00，完成2026-10-02T16:05:45.202304+00:00；主CLI PID17920 actual exit1、JSON 497242.205ms / wrapper 497986.093ms。UTF-8完整外层日志34476B、SHA256 d1b5c68eaf36dff0d47b5519ff95eedfb7e550439d49acc05200df71a68345cb，stdout/stderr由冻结run_check合并捕获，不能称有独立stderr空文件。冻结wrapper自身stdout/stderr.reconfigure UTF-8且为child设PYTHONUTF8=1；启动命令没有另显式设置外层PYTHONIOENCODING，CTRL提醒到达时已启动，未追溯伪称或因此重跑。原完整命令如下（cwd为仓库根）：

```powershell
$env:ZQKY_B4_QA_RUN='real-fixed-first'
$env:ZQKY_KEEP_TEST_DATA='1'
& 'apps/api/.venv/Scripts/python.exe' 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-root/run_check.py' --label full-e2e-real-fixed-first --candidate 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/CANDIDATE-b4-r17-nav-final.json' -- 'C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' 'node_modules/@playwright/test/cli.js' test --config 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-e2e.external.config.ts'
```

本轮外层新系统temp C:\Users\96022\AppData\Local\Temp\zqky-b4-full-e2e-real-fixed-first-s84utr2l保留。实际2个CREATED与2个RETAINED一一配对：assessments zqky-f20i-0iG2Lv/PID27244；question-bank-real zqky-f10-real-T3x3id/PID24640。均在真实childClosed=true/logClosed=true之后登记保留，复核PID不存在、日志可独占读取且四SQLite各存在。后验00:06:59.2663039+08时仅用户5174监听，8001/8002均空，主CLI也不存在；资源JSON保留精确时间，CTRL之后新stream服务不影响该关闭证据。默认清理分支本轮未执行；没有删除未知/旧根。准备时旧release schema KeyError在业务启动前已按实际新字段纠正；只读marker初次pattern漏DATA，现退出JSON已据原日志纠正，未增任何业务次数。

失败trace.zip 39971145B，SHA256 c12b66d8e88bafaf806abb804a0ec65d5c60d389a48da1a1e97578ebad175aa3；ZIP中央目录/EOCD可读、889个entry全解压逐项SHA与CRC验证通过，EOCD offset 39971123。没有G1曾见ZIP尾缺失现象；这一结构事实不能证明业务失败根因。所有153逐例、24文件计数、完整JSON/JUnit/命令与日志/两新temp完整资源/附件逐项及trace归档校验见本目录同前缀JSON。已停止执行与源码写入，后续聊天门禁仅待CTRL独立生命周期放行。

| 原spec | 实际例 | 通过 | 失败 |
| --- | ---: | ---: | ---: |
| assessments.spec.ts | 4 | 4 | 0 |
| books-commit-safety.spec.ts | 6 | 5 | 1 |
| books-courses.spec.ts | 7 | 7 | 0 |
| books-harden.spec.ts | 6 | 6 | 0 |
| books-pipeline.spec.ts | 14 | 14 | 0 |
| chat-composer-boundaries.spec.ts | 1 | 1 | 0 |
| chat-composer.spec.ts | 2 | 2 | 0 |
| chat-context-budget.spec.ts | 4 | 4 | 0 |
| chat-deeplink.spec.ts | 7 | 7 | 0 |
| chat-home.spec.ts | 4 | 4 | 0 |
| chat.spec.ts | 4 | 4 | 0 |
| course-resource-faults.spec.ts | 9 | 9 | 0 |
| course-sessions.spec.ts | 11 | 11 | 0 |
| knowledge-points.spec.ts | 9 | 9 | 0 |
| lesson-plan.spec.ts | 9 | 9 | 0 |
| model-settings-nesting.spec.ts | 4 | 4 | 0 |
| model-settings.spec.ts | 8 | 8 | 0 |
| navigation.spec.ts | 7 | 7 | 0 |
| question-bank-real.spec.ts | 2 | 2 | 0 |
| replica-settings.spec.ts | 1 | 1 | 0 |
| settings.spec.ts | 1 | 1 | 0 |
| shell-home-nav.spec.ts | 24 | 24 | 0 |
| sidebar-chat-fixes.spec.ts | 5 | 5 | 0 |
| sidebar-transition.spec.ts | 4 | 4 | 0 |

原完整首轮保护：FULL-E2E-REAL-FIRST-RESULT.md SHA256 aa3b03e464ef1f6302dcb277a65f66798b77657e3af7dbecc4cf606ca81ab479；SUMMARY SHA256 78a97d623867f004220ccc477e34d530c66c42033781130ff372eb2a648d21d3，引用14件旧证据零漂移。本轮只写新MD/JSON结果，不替换旧文件或执行源。
