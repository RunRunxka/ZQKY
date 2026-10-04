# G2 / B5 当前执行报告

更新：2026-10-03。G2三项独立复验与全部适用门禁已通过，CTRL关闭G2；B5进入契约冻结，尚未编码。下方各轮执行过程为当时历史事实，最新关闭结论见末段。

开工 main@6aeb57280f6a7e0d7391cad4d150745479ea58ec；r21 SHA e558dfbf4af33790328c7c036edfee0aa38c1371da5cb65f6ac8c448ba7c4d39。实测 879 source、53 executableQA、5 sharedContract、2007 build、191 priorDailyEvidence 及原3043保护文件全部零漂移。当前源码879；全部历史可执行QA251，额外198并非r21分组漂移。历史QA4136文件/419625074B全部另保全；next-env原字节另存。基线 SHA 834cc083063e9cf484f46e0787ed199728ca5f39a48ecc57652fab349287342e。

开工只读检查未发现5174/8001/8002监听，原用户PID21816不存在；不是CTRL结束或重启。旧build Ji-Jz8X9yY2R_79JOPivD/2007文件及8001代理仅历史起点，不当本批新构建或新业务通过。

G2-BE已经停写，相关5文件新单轮72/72通过、exit0/24931.869ms；首轮7/1仅修新测试既有错误字段预期，完整原源/日志/根保留。公共首次3文件28/28、exit0/2239.769ms，源前后零漂移。前端首轮30断言passed但4个dialog.close异常导致exit1，首日志保留，不记通过；修后新label复验中。

公共静态复核发现 recoverFrozen 同ID/body可换首次metadata、pending导航可漏过新key注册guard两处边界，CTRL已接管修复并保留修前四源；将补原身份与新上下文拒绝用例。dirty读到更高服务端版本采用显式人工对照策略，不自动换CAS盲覆盖；未知原包仍可重放，旧receipt不倒退正文/版本/dirty。

最终作者自检：BE72/72、FE32/32、公共30/30，相关类型与零警告lint通过，全部实现者停写。完整新check：114文件1141单测/类型/零警告lint/build，exit0/151736.704ms；885绑定源前后0漂移，build`Y6c5E7notWcBElEjX1GF_`实际8001代理，next-env开工原字节恢复。首轮结果各自保持，不拼接。

冻结前独立oracle准备23组件/11真实HTTP/8浏览器，发现runner改变tempfile默认根会使QA guard误判，授权只调整OS TEMP读法并先mkdir新data；该执行前适配没有实跑或删断言，v2原源保持。之后实际首轮结果见下段。G2尚未关闭，B5未开始；真实模型质量、Word/WPS、Qdrant、正式迁移、超200×100压力未执行，不由隔离技术链推断。

G2-r1已冻结（SHA454e7bde71864cc4c3e0a276e921ce6537f7dbe9630473936f3b2f541def830e），886source/287QA/6新contract/2007build/111prior/4136历史。完整API另新根实际运行中。独立首轮unit未启动（展开全部source/QA使Windows argv过长）；API实际exit1/8162.86ms，1failed/4passed/11errors、0skip（JUnit12含teardown重复），源0漂移。错误为QA tag超长、不存在连接方法、将种子保存也计入S1receipt；原源/日志/XML保留，纯QA-v4修正待新r2，不据此关闭G2。run_command改为读取candidate全部source/QA前后，原runner字节保持。

CTRL自有真实API4060/8001、frontend manager14156/node19604/5174已启动；CIM创建时间/命令/端口见RESOURCE-OPEN-v1，真HTML含新build ID，proxyGET synthetic practice revision3与seed一致。所有根新建系统TEMP，凭证None、空教材、Qdrant16333/embedding9，无付费模型、真实草稿或用户进程起停。浏览器/E2E/聊天尚未执行；API服务启动控制台仅工具输出，未声称保存完整HTTP服务日志，实际验收轮另有完整命令日志/trace。

完整新API单轮1706 passed/1既有scale skip/0failed/error、exit0/281201.378ms（pytest280.11s），PID22640已返回，886源前后0漂移。skip明确为默认不启用T60 200×100读取压力；未删/改规模case，不据此宣称本批新压力通过。91个同根语义性临时清理均先保存完整原字节，根与会话清理保留，所有根外递归删除拒绝；历史4136原件实际审计仍0漂移。r1后续审计exit1因已登记CTRL两QA工具适配，其余source/contract/build/prior111/历史/next-env全部0；后续按QA新候选执行，不隐藏此delta。

G2-r2冻结SHAaaa4868a51ff9d9ce12f45bc08bd3084832029a4ca7f2bab5ca789b78b7c9fa8，product/contract/build与r1零差，3QA适配登记revisionHistory-v2。独立完整新单轮unit22/1、exit1/2508.342ms，等待共有分值不足以证明A对象加载完成；API10/1、0error/skip、exit1/12846.815ms，真实双同包返回409 REVISION_CONFLICT/200，确认产品并发窗口。11组四库integrity/FK通过，886source及unit287QA前后0漂移；首败/原包/源码全部保留，不以10例拼通过。BE-v2已重开修产品竞态，QA-v5只补对象身份等待，后续浏览器/E2E/聊天停止，B5未进入。

13:59北京时间CTRL写API4060专属stopFile，uvicorn完整shutdown/exit0，8001/8002只读核无监听，四库和样本保留；前端19604/5174仍保留。不结束任何用户进程。服务阶段状态以本段及CURRENT_STATUS当前事实为准，前文启动是当时历史。

独立RESULT-v2已冻结（JSON SHA81ecf1ce1ed21bbbfbe3e7c76f6bd5d80f010cb3c472f9928352ad08586f5b0d，MD SHA4a497d418d7bb839ca910b0e1c408fbb0e47000136c12e3e0c13162880a979b6）。并发首败后只读诊断S1 receipt精确1/current revision4，不能替代原双200断言；11组四库44项完整性均通过。QA-v5仅修explicit-discard等待真实A身份与完整5字段，API原并发预期、预算、超时、重试全保持；manifest SHA cc78c6e474727389ed816c5d0d8482ec98b9814d21660b1bdf46a5719412df34，已停写，未重跑。BE-v2修复中，前端/公共源码未再修改，旧首版fullAPI不作为修后结果。

BE-v2作者新单轮15/15定向、79/79原相关5文件通过，源码已停写，RESULT登记中。CTRL静态核同SQLite读快照内receipt/owner/CAS/state及准备错误后receipt复查，不把作者通过当独立验收。浏览器执行前预审另发现只等重试发包长度不能证明页面处理ACK；QA-v6仅追加两成功notice等待并保留全部原断言，manifest SHA5d4b9ea3cc35273c84c2fb60c959a1797d726b029fd202c341f8990054158149，未执行。QA-v7只加强native Back前真实SPA history stamp只读身份绑定，原Link/Back/取消/keep/save/字段/URL及预算不变，完成后再冻结新候选。

14:20前后已冻结G2-r3，SHA4cb87b15870799f638c6c48527f8fbed34013ac9c9a74a41ec09d27e42168034：886source/304QA/6contract/2007build/222prior/4136history。相对r2只有private PracticeService与新replay测试两个Python源变化；457前端文件、契约、build实际全0漂移。原1141check源885中仅上述2Python差异，原前端类型/lint/unit/build仍绑定相同源，不冒称重新check；修后完整API以新label g2-api-full-r3-first已启动，独立完整23+11新单轮另授权。v7 manifest SHA198c2216564f6a0a2e3e931a4ce5f4c5442b2ad459d605fe170ac7bbd555649c；全部实现与QA停写，运行过程中不边验边修。

r3独立完整新轮组件23/23（exit0/2712.652ms/PID15520）、真实API11/11（exit0/14043.419ms/PID18704）、44四库完整性均通过，0fail/error/skip，API1既有AnyIO warning；source886/QA304前后0漂移。immutable RESULT-v3 JSON SHA82903791f17742a8b0fc7813648d064d64a8425ff79bbec364184a90139c8323、MD SHA6329d2539be7b86db3f74da34b1007ce9af43e824488255f11f5fd2ca8a6f003。单轮真实双200、精确一次receipt与一次编辑不拼绿；旧首败均保持。

CTRL新API4204/8001，freshTEMP zqky-g2-runtime-g2-runtime-r3-1rexasx6，完整console新文件独占捕获；seedA8bcd1867e046409fab8d696f36c7cfdf/rev3。真HTML200包含buildY6c5E7notWcBElEjX1GF_，proxyGET200与seedID/CAS/固定修订完全相同，actualCIM创建/argv/端口见G2-RUNTIME-r3-IDENTITY-v1.json。旧API4060关闭事实保持；frontend19604未重启、用户进程未触碰。V00完整8例browser-r3-first已另授权，完整API仍运行；三视口/全153/chat14仍未执行，G2未关闭/B5未开始。

修后完整API已结束：1713pass/1既有scale skip/0fail/error，exit0/277533.191ms（CLI276.35s/XML276.338s），PID14028关闭，886source前后0。skip仍为既有200×100 XLSX读取基线默认关闭；不是新压力通过。

浏览器r3首轮setup失败1/其余7未run、业务执行0、trace/png0，exit1/1536.616ms；原因是worker重读config时目录guard误拒自己本轮已创建的output，原件BROWSER-RESULT-v3保持。CTRL核本地workerMain.js line60的TEST_WORKER_INDEX，将4个external配置的guard仅在main进程执行，主进程仍拒复用旧目录，原spec/断言/预算全保持。实际r3 audit exit1仅4QA差异，source/contract/build/prior222/4136历史/next-env全0；新r4 SHA8aa0d1aabddeb53c851c2cbc9ec316373578dd4a5df85392e5e254c92259039d，886/304/6/2007/293/4136。23/11与fullAPI1713和前端check/build逐文件绑定同产品/相关QA，不冒称重跑。

r4浏览器完整新单轮8/8，0skip/fail/retry，CLI12316/worker8492关闭，exit0/11352.817ms（JSON10578.404ms）；source886/QA304前后0。BROWSER-RESULT-v4 JSON SHA28f4085b84c27a3824f7c173753c71e6f782faf329b91972c322da768fc1ef61，8trace/8原PNG保留。两真实200/201fetch后abort、原包重放成功notice与3/B保留、真实SPA native Back cancel/keep/save等均实际通过。

CTRL三视口完整3/3，exit0/3709.292ms/PID4172关闭，390×844/1024×768/1440×900、reduced-motion、focus/Escape保留5通过，6原PNG另存。原14PNG精确bytes核对、11trace全CRC通过；CTRL实际view8，V00另卡读全部14。真实TCP四库只读完整性/FK全通过；S1receipt精确1/currentCAS6=原expected5+1/服务端旧2，noteA精确1且ID同原201、B未追加，连接关闭。原JSON附文本/图片可由报告恢复；一次辅助清单误输出inline base64，随后改为只输出元数据并原bytes提取，没有修改原报告/图。

API4204专属stopFile正常关闭/exit0，8001释放、数据根和console保留。新stream8836/8001+8002显式替身与新TEMP运行，frontend19604保持同build，真health/proxy200与CIM见G2-STREAM-r4-IDENTITY-v1.json。原完整153新label g2-e2e-full-r4-first已启动；chat14/最终收口尚未执行。G2尚未关闭，B5没有编码；回归期间仅只读清点T90/F30既有端口。

只读辅助问题：CTRL首次猜测 services/use-submission.ts 不存在，随后rg定位实际 assessments/hooks.ts；无测试或服务重试。各Agent的路径查找包装错误按结果卡保留。

15:00前后更新：V00实际逐张view全部14/14原PNG，前后SHA0漂移，VISUAL-READ-v4 JSON SHA d292412373cf895912bf38136b699e339272e584e4b0a0bfbb18f40b1de99dde、MD SHA8399b118adcc62f329530077a8a0387d4e62313bfabccb3ddf3a78eb56744763。只对可见像素下结论，动态8/3仍为导航/键盘/保存依据。

原153 r4-first实际147pass/3fail/3did-not-run，exit1/348043.106ms，PID2360关闭；三失败分别assessments:502、question-bank-real:212/:359，均为fixture启动前8001占用，未执行相应业务断言。CTRL提前启动stream8836是运行安排失误，已向用户说明；原完整日志/JSON/XML/3trace及886source/304QA前后0漂移保持，不将147和后来窄轮拼接成153。

stream8836由其已登记专属stopFile正常关闭，06:49:42 UTC收敛service closed/serverClosed/watcherClosed，原fixture finally执行；TEMP kh4d0e0d及模型样本jf693kcs保留。实际端口只余已拥有的frontend19604/5174，8001/8002空闲。现在以新label g2-e2e-full-r4-second、新完整原153目录重跑；不改产品、原用例、预算、重试或worker数，期间不得启动其他后端。聊天14与最终收口尚未执行，G2未关闭/B5未编码。

一次只读日志读取误猜文件名*-command.log（实际*.log），随后用rg定位；未改任何文件或重试服务。当前权威状态与接手入口同步r4和各轮实际事实，历史原件不改。

第二原完整153新单轮153pass/0fail/skip/flaky/retry，一例1attempt，exit0/365786.625ms（JSON365067.158ms），PID2312关闭；886source/304QA前后0漂移，原24spec范围及预算不变。受影响六项在这一完整单轮实际执行，不拼接首轮147。两轮完整标题identity聚合SHA99559df9ab1e5dfbde46b922e6580f3ac47715e959b592a34d4f532c1888350e；24spec原body均同r4，聚合SHA dc1e49fb85f799202f049cae8cadc19352cc8530838b2b1c5ab6b3f3ca5d1259。原R14用例这轮通过仍不证明跨批恒绿或根因。

新自有stream25228只在full153结束、8001/8002释放后启动，新TEMP与真health/proxy200/同build身份绑定。原两spec14chat完整14pass/0fail/skip/flaky/retry，exit0/46437.740ms（JSON45644.257ms）、PID24884关闭，886source/304QA前后0漂移。原26PNG由spec outputPath直接写入且未attach；CTRL首次仅枚举附件得0，保留MANIFEST-v1，改用真实artifacts枚举得26并新增MANIFEST-v2，不修改原图。原三协议/取消/恢复/公式/20k50k/滚动正确行为由运行断言支持，性能数值仅本次采样。

stream25228、frontendmanager14156/child19604均通过自己的专属stopFile收束。Stream原finally正常执行，管理器exit0；Windows owned child.terminate使前端child exit1，childClosed/logClosed为true，该码不是测试失败，不冒称child exit0。实际5174/8001/8002均无监听，登记PID含用户旧21816均已不存在；自有5服务closed、CTRL23根以及全批结构化证据40根全部exists/保留，未删除。只读数据库连接及测试浏览器worker均已关闭。G2-r4保全audit实际exit0，886/304/6/2007/293/4136历史与next-env全部0漂移；已有G2资源/门禁事实固化ROOT-G2-FULL-GATES-r4-v1，图审与最后文档收口完成前仍未关闭G2。

source措辞明确：check实际捕获456FE＋作者快照/候选另外绑定新增styles.css（SHA8fe670cbf919646e1ae91d85e4d1f3158e0209dc4b3db87d63ade328dc040d8c）=457FE。缺席check map不假报漂移或假报已由check map捕获；实际三视口和新完整153均来自含此CSS同构建。

G2收口：独立26聊天原PNG实际view26/26，图源前后0漂移，CHAT-VISUAL-r4-v1 JSON SHA4ce2af8b9a8db99ce506a172aaff7a8b03f718f67f8210ae9472dd2aa8909981、MD SHAa0903bfa3d07bd978a3610b01b75ffffc189dcaf301e75f3681a0757a29e5626。CV01浮钮遮代码、CV02控件空框/灰色、CV03停止图形静帧差异均保留既有观察边界；不据静帧关闭交互或全视觉台账。

153原case身份与24spec原byte不变，默认45s/expect10s/worker1/retry0未变。首轮3个serial未run用例未执行原test.setTimeout所以报告45s；新轮实际执行原行560/773/896而显示300s/240s/600s，属于执行状态差异，不是拓预算。

全部必要G2技术门禁与独立资源/源/QA/契约/构建/历史/next-env/文档核准后，CTRL关闭G2。B4F-R01～R03不重写原B4关闭历史；原首败、规模skip、R14与CV/RAG-REL边界保留。关闭候选文档六文件由CTRL单独冻结并交V00只读核准，只按审定字节应用，无产品/QA改动；独立结论见g2-v00/CLOSURE-r4-v1。B5接下来冻结新契约/DDL/OpenAPI，再实施，当前尚未编码。

关闭文档v1预核发现REPORT顶部当前结论仍旧，原v1稿/manifest保持；v2只修当前结论与NEXT时态，不改任何原运行事实、产品或QA。最终核准与应用采用v2精确字节。
