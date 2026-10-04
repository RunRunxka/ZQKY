# B4 根共享首败记录

实现自检记录，不冒充最终稳定候选或独立验收。原各轮日志/命令/样本保留，不合并计数。

| 记录 | 实际原因与处理 |
| --- | --- |
| b4-root/foundation-first～third | 重建时外部触发器暂时引用旧卷表；新analysis复合FK引用了不存在的三列或score/paper唯一键。按实际schema修正RebuildPlan同事务卸载/恢复相关触发器，以score/assessment及assessment/paper真复合FK取代；第四新样本迁移两次通过。 |
| foundation-pytest首轮 | root装配用了并不存在的QuestionBankService.read_asset；改为明确注入既有question_bank.rich.read_asset。首轮AttributeError原件保留，随后9项自检通过。 |
| migrations-regression-first | 8个旧测试期望只列到0007，没有包含追加0008/0009；实际迁移/业务断言没有失败。保留两测试改前副本，只更新完整applied列表，第二轮38通过。 |
| T80 ninth | root新增来源严格闸门时误写 practice_item_knowledge.practice_item_id，真实列为item_id；该SQLite错误会在确认文件卷时编译触发器暴露，原日志保留。两处已精确纠正，受影响作者/root自检另起新轮，不沿用eighth成功证明新版。 |
| shared-v13-first | root命令误用了不存在的test_database_foundation.py，pytest退出4、零业务用例执行；不得记产品fail或pass。查实际文件后第二轮9文件57通过，退出0，5153.769ms。 |
| full-api-first | 单轮1694通过/1失败/1规模门控skip，264.17s。旧B0 workflow_jobs fixture 假设 export 未注册，queued retry应409；B4真实注册export后，现行B3/G0契约允许显式补调度registered queued，故返回200。保留完整首轮log/精确命令与旧测试原字节副本；仅将该B0 fixture显式设空执行器注册表，原409/终态retry/冻结输入等全部业务断言不改。真实registered export的公共retry仍由T80实际全HTTP链及注册表测试验，不改产品路由/引擎，不关闭真实补调度能力。 |

完整题号与材料identity的收口修正见B4-CONTRACT-v1.3-ERRATA及T80各轮日志；自己的作者自检仍待稳定候选交叉独立验收。后续若有新首败在本文件补录对应独立记录，旧日志不覆盖。

独立A首轮：总控首次发卡把候选路径误写到b4-root；执行者先只读找出本批顶层同SHA候选，业务执行前纠正。随后first退出1、0完整场景、32实际HTTP：404 ANALYSIS_NOT_FOUND合法省略details，QA共用helper误要求所有错误五键。schemas/errors.py与可选DTO一致，属于QA前提过严；保留首轮全部日志及源前副本，只允许修正共用必填为code/message/requestId/retryable，422字段定位要求不变，另冻后全轮重跑。不能把之前已执行的部分oracle断言合计为完整场景通过。

统一check-v14-first：真实typecheck退出2，7849.943ms；题库ReviewWorkspace已接收returnPracticeSetId，内部ReviewSession未传入/解构却引用该变量。属root共享前端集成缺陷，未到lint/unit/build；并非F独立18例或专属作者14例失败。next-env生成后已精确恢复现场原字节。补齐子会话prop传递，新增实际确认后普通路径/带特殊字符返回上下文两项组件验证；另冻后完整check。完整API-v14-first同期1695通过/1规模门控skip、279.14s/280805.307ms，候选r2；后端与API测试没因这个前端传prop修正改变，后续须明确共同源绑定，不冒称重跑。

统一check-v14-second：r3真实exit1、96796.762ms；typecheck/lint通过（零警告），Vitest单轮111文件中109通过/2失败，1102通过/2失败，81.84秒；build未执行。导航现行ready两B4入口遗漏于旧期望表，已补齐期望并新增两路径解析断言；转班通知在等待甲消失后立即同步读取失败，尚在独立受控诊断，不先记为产品或间歇失败。next-env again精确恢复现场原字节。

nav-r3-fix-first：root窄测试误指定不存在的apps/web/vitest.config.ts，exit1/378.693ms，零业务用例执行。原日志/收据/样本保留；这次收据引用r3作为修复起点，当时navigation.test.ts已修改，不是稳定r3的行为结果，也不算导航业务fail/pass。后续须冻新候选后使用真实根vitest.config.ts。

R06独立受控诊断：r4-diagnostic单轮3/3通过、exit0/2176.98ms，877/36/5前后零漂移。pending两GET门时甲仍在、合法乙草稿保留；transfer原负向wait首次成功时notice=false/loading=false/乙仍在，证明ready render→notice effect的短暂窗口。本轮await负向wait返回后notice已true，未再次重现原同步getByTestId首败，不能混写为同一失败复现。等待正向notice后原11完整matcher语义全部通过；因此原测试仅新增findByTestId等待，原断言不改，产品不改。修前原字节副本已保留，r5新候选完整check第三轮另执行。

browser-real-first：r5真实1例失败，exit1/20454ms，报告12全题富证据的12图片预期为0。真实图片GET返回404 PAPER_ASSET_NOT_FOUND（本修订图片块未引用）；完整trace/PNG/error-context/流与seed新样本保留，后续补题/练习/导出/回流未执行。root确认既有资产路由已支持path，仅放行本修订paper_source_blocks image引用；seed却只建富paper_items，没有source_blocks，属于夹具未建立完整授权来源上下文，不能通过放宽产品授权来绕过。QA源须另卡修复、旧源原字节保存、独立补审、重冻、全新seed再验。首轮自有backend PID3500经stopfile优雅退出0，完整application shutdown与日志散列登记；用户手动5174/PID24248不结束。

browser-real-second：r6单轮1失败、exit1/8697ms。报告12图片、三视口、备注、真实缺口及主动补题请求/17项本样本PII排除已执行；首断言为导入按钮click后同步读取page.url为null，trace实际RSC目标200且稍后已经试题校对页。QA-R08只增精确import+returnPracticeSetId导航await，保留原115 matcher和原同步match/notnull。原spec字节、完整trace216条CRC通过/上下文关闭证据保留。后续真实GET import记录500/21字节Internal Server Error，仍单独保留，不能假称没有其它错误；首败后发生，标准后端log没有该GET/500，root停止后端在browser退出79秒后，不能归因root停止。独立归因和受影响复验仍待验。

r09-clone-import-get-first：root复制本轮合成样本到新临时根，显式Settings漏allowed_origins，exit1、零业务请求；根保留且登记启动错误。second已补该字段，但TestClient默认testserver被Host门控400，未进入导入业务；完整实际400信封/日志及新根保留。third显式allowed_origins及base_url回环，标准main同一真实import GET返回200/1草稿；原jjraqnst样本前后全文件SHA完全相同，新副本独立保留，无监听、无正式数据。third是根诊断、不替代真实浏览器或独立验收，不将未复现500删除。

browser-real-third：内层完整用例1通过、child exit0/24628ms，业务链与所有下载完成；外层 run.py 回显包含“›”，GBK stdout编码产生UnicodeEncodeError，outer exit1。原 receipt/完整stdout stderr/log/trace保存；只在 runner 增 stdout/stderr UTF8 reconfigure，原命令/断言不改，重冻后第四轮新样本实际 child/outer均exit0、1完整通过/29702ms。第二轮500仍留案，不由第四单次绿证明恒无间歇。

R09/R10 真反例：标准main真实题owner local-user与练习筛选local不匹配，独立4例1通过/3失败；公开单题外归属get/patch/delete可读写删除，独立2例2失败。修复后分别原4通过、原2通过，作者4通过，全API1698通过/1规模门控skip。原低层local seed/作者标准main夹具按实际服务owner适配，未改正式历史owner或放宽reader。

P owner-fixed-first：修后原64场景首轮0通过/1失败/63未执行，通用helper造题仍用local；仅该表达式改为真实QBankService.owner_id，其他测试源与全部原断言保留。owner-fixed-second单轮64通过/81904ms，不合并首轮执行数。

R11组件首轮2失败/0通过/3629.593ms，前置事实/成功任务和旧源Abort均正确，精准在历史“已准备”失败；R12 mobile-visual-first真实exit1/3265.256ms，对比度1.013659399低于4.5，完整trace/8截图/零写请求。两项修前证据均保留，CTRL 三个前端文件修复另冻r12，不把旧r5构建验成新源码。产品修复在独立测试真实退出后进行；独立实际post于14:40:13 UTC已零漂移，随后三文件归新候选。

check-ui-fixed-first：r12单轮exit1/14247.66ms，typecheck通过，lint一条exhaustive-deps警告（resource依赖）违反零警告门槛，unit/build未执行。next-env现场字节精确恢复；原完整命令/log/新根保留。P独立2例与F18已完成且post全零后，仅将稳定reload函数明确解构、依赖相同函数值，另冻r13。不能把lint失败写成整check已通过。

## 原完整E2E real-first / B4-R13

新r13 build单轮原24spec/153case=152pass/1fail/0skip/0flaky，153尝试全部retry0，exit1/379467.171ms。case117真实入库200后回题库library仍false，实际最终双#library；剩余case118及其后全部原case通过。原断言和日志/JSON/JUnit/105条目完整trace/截图/3后端新根保留。前后878/43/5/2007零漂移；8001/8002全部释放，用户PID3820未改。新B4-R13导航卡及正确行为QA先红测再修复，不能把该轮记成功或用旧G1全绿替代。

R13独立修前红测仅一次2fail/3343.414ms；产品修复后原QA第一次green单轮1pass/1QA环境错误1388.763ms，真实Modal挂载时jsdom无showModal，后续断言未执行，不能记第二例产品失败或成功。仅登记补新QA原生dialog模拟、保留原2defs/全部asserts，另冻后新单轮复验。红測post原包装NameError首败保留，原后审确已完成但缺包装收据字段不补造；新授权post-closure实际203ms/exit0。未重跑红测。r15仅冻结未执行，启动前校正新作者测试真实关闭按钮名称后另冻r16，不覆写r15。

第六owned API释放预检最初exit1：ConvertFrom-Json把ISO时点转换DateTime，字符串比较误判创建时点（6/7位小数），stopfile未写、未结束任何进程。实际CIM PID27880/创建时点UTC ticks与argv同ready，改值比较后verified-own stopfile优雅退出0/session28668、日志exclusiveclosed、8001/8002free。首阻断与第二未完成guard保留tool输出，不计产品回归。

原stream仅JSON预备阶段：首次compile语法检查exit1/0.2405475s，三处内联字符串newline转义有误；服务未启动/未import main，首次prepared字节保存stream-api-first-prepared-before.txt。修正三处转义后compile成功，当时仍prepared-not-started，argv新值及前SHA保留；未更改stream fixture/QA/产品。这不是聊天业务fail/pass。

## 最新全量 E2E 与用户暂停

full-e2e-real-fixed-first实际原24spec/153case=152pass/1fail/0skip/0flaky、153attempt/retry均0；Node17920自然exit1、497986.093ms，原日志/JSON/JUnit/889条完整CRC+SHA trace保留。唯一首败原books-commit-safety267行second strip，120000ms期待0实际1；第一书完成及完成前两笔记保存通过，失败后最终跨tab笔记/双ID/锁断言未执行。独立第二页DOM明确interrupted/继续生成，触发根因/恢复未证实，不归咎未捕获的lease/write-lock，不把台账间歇忽略。题库原两例及全部后续断言已通过，旧r13导航首败保留。

root随后启动新隔离stream PID23268/8001+8002，原fixture与三个synthetic协议不变。用户此时要求先暂停，只执行已核身份自有stopfile关闭，原fixture finally实际返回、session30406 exit0、log647B独占关闭、端口释放、user5172保持；原14聊天Playwright没有执行，不能记通过/失败或以服务启动当业务验收。

暂停文档第一次apply_patch准备将同一B4-REPORT先Delete再Add，工具校验拒绝「multiple operations target」，未写任何文件；随后用明确文档写入更新当前报告/交接，不涉及产品/可执行QA。此为文档工具准备错误，不计业务首败，也不是自动审批policy拒绝。
