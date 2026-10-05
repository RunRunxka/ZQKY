# 当前状态与实施主线

更新：2026-10-03。当前建设主线以 **2026-09-29（含）之后**的教材 RAG 与教学闭环任务为准。本文件是唯一进度、问题台账和下一动作入口；稳定规则见 [PROJECT_GUIDE](PROJECT_GUIDE.md)，阅读顺序见 [文档索引](README.md)。旧正文已逐字节保存为 [整理前状态快照](archive/snapshots/20261001-docs-focus/docs/CURRENT_STATUS.md)。

<a id="current-task"></a>
## 1. 当前任务与下一动作

**2026-10-03，G2已关闭；B5修后FE v3已停写，独立18组件/42真实API通过，新完整check的1224单测/类型/零警告lint/build通过。新构建EuGU-xptkS4Dv7wiXoxD4实际代理8001，r1冻结938源/2193可执行QA/33契约/2004构建。真实浏览器原完整8首轮1pass/7fail，trace确认KP异步空集合及相对locator问题、课题/历史定位与clean初始缓存观察错误；原件保持，V00仅准备QA v6，无产品改动，B5未关闭。**

当前批次 [TEACHING-LOOP-G2-B5-20261003](qa/TEACHING-LOOP-G2-B5-20261003/README.md)保存 [报告](qa/TEACHING-LOOP-G2-B5-20261003/REPORT.md)、[任务卡](qa/TEACHING-LOOP-G2-B5-20261003/TASK-CARDS.md)、[契约](qa/TEACHING-LOOP-G2-B5-20261003/G2-CONTRACT-v1.md)与[关闭矩阵](qa/TEACHING-LOOP-G2-B5-20261003/G2-CLOSE-MATRIX.md)。开工 main@6aeb57280f6a7e0d7391cad4d150745479ea58ec，r21 的879源/53 QA/5契约/2007构建/191当日证据及原3043组零漂移，另保全4136历史QA。正式数据、凭证与真实草稿不访问，不提交/推送/切分支/部署；每日记录按北京时间更新。

当前稳定候选 [G2-r4](qa/TEACHING-LOOP-G2-B5-20261003/CANDIDATE-G2-r4.json)，SHA `8aa0d1aabddeb53c851c2cbc9ec316373578dd4a5df85392e5e254c92259039d`：886源/304可执行QA/6契约/2007构建/293既有本批证据/4136历史。r2 独立并发首败409/200后，BE-v2修复同一SQLite读取快照的收据与CAS竞态；r3独立完整23/23组件、11/11真实API与44四库完整性检查通过。r4只修4个Playwright配置的worker重复读取输出目录guard，主进程仍拒复用旧目录，原用例、断言与预算不变，产品源/契约/构建同r3。r1～r3、QA-v1～v7、各轮首败与候选均保留。

工程结果：原完整check的114文件/1141单测、类型、零警告lint、build通过，exit0/151736.704ms；G2修后完整API新轮1713通过/1既有规模skip，exit0/277533.191ms，886源前后0漂移。原check显式捕获456前端；新增CSS另由作者快照与r1～r4候选绑定同字节，合计457前端及同构建，仅后来2个Python文件有已登记差异，未冒称重跑check；原1706 API结果仅历史。构建 `Y6c5E7notWcBElEjX1GF_`，实际代理8001，next-env原字节已恢复。

独立真实浏览器 r4 完整新单轮8/8通过，exit0/11352.817ms；真实200/201后丢响应、原包重放保留新3/B、练习切换/历史/公共导航/刷新/原生Back均有正确行为断言。CTRL三视口390×844、1024×768、1440×900完整3/3通过，exit0/3709.292ms；14原PNG和11trace完整保留，CTRL实际view8、V00实际view14，图源前后0漂移，不将静帧当键盘/Back/生命周期证明。真实TCP四库 integrity/FK通过，S1收据精确1且CAS只增1，备注A精确1、B未追加，连接已关闭。

原全量153首轮为147通过/3失败/3未运行，exit1/348043.106ms；三处失败均为真实后端fixture启动前8001被CTRL提前启动的聊天替身8836占用，业务断言未执行。这是CTRL运行安排失误，完整原JSON/XML/日志/trace与源绑定保留，不据147关闭回归。8836已经通过专属stopFile正常退出，8001/8002释放；全新 `g2-e2e-full-r4-second` 原完整153已153/153通过，exit0/365786.625ms，零失败/跳过/重试，886源/304QA前后0漂移，原24spec/body/预算不变。原两spec14聊天也已新单轮14/14通过，exit0/46437.740ms，零跳过/重试；26原图已全部独立view，前后SHA0漂移，CV01–03静帧观察保留，不宣称全视觉PASS。

当前自有前端manager14156/node19604、真实API4060/4204与聊天替身8836/25228均已关闭，5174/8001/8002无监听，40隔离临时根全部保留。前端管理器exit0、受控Windows child stop码1，childClosed/logClosed true，不冒称child自然exit0。开工原用户21816不存在，没有结束用户进程；接手须再核实际PID/创建时间/argv/端口，不凭本文数字操作。用户已授权后续CTRL管理自有测试前端，具体自动审批拒绝不绕过。

B5准备期当时的实际结果（历史，随后冻结及当前进度见下文）：[共享契约v1](qa/TEACHING-LOOP-G2-B5-20261003/B5-CONTRACT-v1.md)已编制Python/TS DTO、薄transport、v1类型兼容re-export与0010未登记DDL。类型检查exit0/3355.246ms、零警告lint exit0/1472.115ms；12接口静态OpenAPI与19正例/5错误信封/12严格拒绝DTO通过，不是已实现API。初始current pointer已用CAS/version四列真FK保护。DDL预检首败发现公共transaction的COMMIT延迟FK失败未回滚；原日志/修前源保留，CTRL已修入口，2连接测试通过；新DDL预检新库/有数据B4库/故障整体回滚重跑和owner/CAS/immutable/integrity/FK通过，exit0/396.014ms。当时独立审查仍在核共享契约，尚未冻结或派三个模块实现。

随后实际进展：独立[B5静态审查](qa/TEACHING-LOOP-G2-B5-20261003/g2-v00/B5-CONTRACT-REVIEW-v1.md)批准，27登记文件前后0漂移；CTRL冻结33件清单SHA `8a19686b7b6ce6ed91e47d43c23e95bed1baccd9c2c372a5783fecd2f414d9db`。v2类型3181.656ms、lint1186.611ms、nullable回归3例和新DDL第三轮447.920ms通过，原准备期DDL/静态OpenAPI及提交失败首败保持。T90-BE由g2_be、T90-AI由b5_ai、F30-L由g2_fe按唯一文件归属并行实施；oracle未参与实现，后续稳定候选另验。0010已追加登记，原9声明不改；版本感知schema gate及恢复门控已接入、B0 required表保持，两个生产RAG口与固定reviewed练习读取已落。CTRL公共基础首轮8pass/1QA错误（引用不存在的TextbookCatalog方法），修前test/完整log/XML保持；新完整9/9通过，exit0/2156.701ms，私有绑定10源0漂移，SettingsNone/新TEMP/连接关闭/样本保留。整体B5业务与浏览器仍待稳定集成，不能据作者自检关闭。

2026-10-03 17:05补记：CTRL迁移三测试适配新单轮19/19，exit0/3058.583ms、8私有源0漂移；公开运行装配/固定题选择第三轮3/3，exit0/2751.3ms、6源0漂移，前两轮为QA误用属性/信封/读取口而失败，原字节/日志/XML保持。BE新单轮44/44、AI81/81作者已停写；仍须冻结后独立复验，不能据作者通过关闭B5。补充接口/归属见[B5-CTRL来源装配卡](qa/TEACHING-LOOP-G2-B5-20261003/B5-CTRL-SOURCE-RUNTIME-DELTA-v1.md)。

2026-10-03 17:25补记：四库离线恢复新轮1/1、exit0/2601.856ms，六B5表实际2/3/3/2/2/2行，2资产/3向量点、原9hash与教学全表/知识题库逐行不变，标准main重装能读应用后教案和生产教材证据。首轮QA收尾误用QdrantAdmin客户端工厂而exit1，原件保持；进程退出关闭剩余连接，后轮显式关闭Scene。独立静态两P2已登记[B5集成修复卡](qa/TEACHING-LOOP-G2-B5-20261003/B5-CTRL-FIX-DELTA-v1.md)：短数字身份碰撞由AI v2修中；SQL literal/JSON路径大小写体检绕过已由CTRL修，公共9+恢复1新10/10、exit0/3552.456ms。BE归档新包422窄修45/45、导航7/7作者通过。FE补深链/invalid route/旧空串和真实leave；尚未冻结/整体独立验，B5不关闭。

2026-10-03 17:47补记：AI v2完整144/144、exit0/62043.581ms（12源0漂移），FE完整50/50、exit0/7330.244ms及类型/零警告lint通过，私有作者均停写，仅待独立验。AI首轮93/48失败为新短号fixture自由教学段落仍含真实数字，原件保持，修新fixture经生产封存无数字文本，不放宽产品隐私阻断。CTRL与FE只读核实B5R-R03历史待复制正文会因薄route key跨revision变化重挂丢失；CTRL保全原路由后缩key到analysis/error，Gateway已有props同步与文档Provider key负责文档身份。V00新增真实Next复制/undo/save场景，独立静态v2审查及QA v2准备中；尚未冻结整体或完成新构建。

2026-10-03 17:52补记：独立静态v2确认R04生成await保存/unknown重试会把旧M1请求标成新M2签名，R05来源面板classes limit1000超过真实公开API上限200而阻断报告选择；FE v2已获私有窄修卡，原v1 50结果保留。R03首修对合法历史URL带analysis参数仍可能重挂，CTRL已另保全首修并将page key再缩到仅routeError；V00 v1/v2静态QA已封存，v3另增真实历史复制、等待/unknown模型变化及严格分页反例，不追改v1/v2。整体产品和QA仍未稳定冻结，不关闭B5。

2026-10-03 18:14补记：V00 QA v3已封存36文件，SHA9de788939c8b1fc856eaa8407e58e7a439a2fdf9d4fb5e81d10ad834fa4cf569；API42/unit15/browser8共65只是静态展开、语法0诊断，框架收集与产品测试未执行。CTRL服务helper已切v3种子，尚未起TCP。FE v2窄修已编码，准备71例作者检查。后台BE/AI已停写，CTRL单独绑定410后端/测试/脚本/模板文件SOURCE SHA91436c66d2b323956e97dc5e9b60e38e2e2cd0d69497114d65afd28f71051ee6，完整后端工程回归正在新隔离根运行且已见失败；不是整批候选或独立通过，后续须归因修复并与最终候选精确绑定。根指南与模块稳定规范旧概述已保全后更新，提前文档独立审查中。

2026-10-03 18:32补记：FE v2最终73/73、exit0/8274.231ms，类型1719.499ms、零警告lint2832.717ms均通过并停写，原迟到leave和generation缓存metadata首败保持。完整后端SOURCE-v1工程首轮1912pass/5fail/1既有规模skip、exit1/371244.395ms；三失败为父Python GBK读取UTF-8 CLI，两失败为旧planned/501预期。启动前显式UTF8并保全后适配两项现行契约，窄轮v2 30/1为新QA误断成功header；新单轮v3 31/31、exit0/27908.894ms/410源0漂移，未据窄轮关闭fullAPI。prebuild-v1已冻结SHA eeab0e2f6f58ea982d4ea9e1556fa43569061e79e4a42ba10d30dcb0d17c0246，938源/1890可执行QA/33冻结/847既有本批/4136历史；build仍G2旧2007件，不当B5新构建。第一次冻结因两live authority Windows路径归类误阻断，原baseline与关闭快照不改，589原证据+2核准归档原件继续保全，见证据路径delta。完整新check/build/API和独立42API/15unit已派执行；真实browser与153/14未执行。

2026-10-03 18:38补记：prebuild-v1完整check已结束，118文件/1202单测、类型、零警告lint/build通过，exit0/110566.057ms/PID6308，938源/1890QA前后0，next-env原字节恢复；完整API1918pass/1既有规模skip、exit0/392504.479ms/PID21200，938源0。独立API42/42、exit0/40948.122ms/PID20076；unit首轮11pass/4fail、exit1/6458.522ms/PID8056。三失败是新模拟proposal缺必填jobId，v4仅补真实DTO且保留原断言；后页班case确认SourcePanel.load首100遗漏为R05残余。独立static v3又确认R04新M2生成明确失败时旧M1候选复活，准备独立正确行为首败再窄修。当前原候选/首败/新构建均保全，不进入browser，不关闭B5。证据工具二次修严格限定两live authority，589实时原件+2核准归档快照保护，原首次587+4分类及prebuild-v1不追改。

2026-10-03 18:47补记：新prebuild-v2-QA已冻结SHA5700383f93f4df0cf0ae4c2dfc4aec10bfdf38042e815941a04c051f15223aa8，source938与v1同字节，QA1892仅helper窄范围+v4新2件，build9KvS9k4O8Bs3ZampQA3-_ /2004实际8001。V00原完整16首轮14pass/2产品fail、3292.472ms/PID26248/sourceQA0；原三unknown补真实jobId后全通过，R04明确422后旧M1复活和R05后页班首败保持。所有原绑定运行已结束，CTRL已OPEN FEv3唯一写窗口，同时将静态确认的报告/练习首100同类截断纳入SourcePanel三口分页窄修；V00 v5独立新后页QA只准备，runtime等作者停写。当前不关闭B5、不起浏览器。

2026-10-03 19:02补记：FE v3已STOP，最终95/95、9473.539ms/PID22436，类型1753.949ms/lint2959.092ms零警告、源0；首94/1为新unknown文字期待错误，全部原输入/日志保持，后新95单轮全走原包/过期/采用0断言，不拼绿。独立QA v5 SHA2784016cde55ab949f563d0b0d177200a543f8e0ba2e519bc59b0df78b828ae0已停写；新prebuild-v3 SHA317395661152fc2472932223192e08252a2c7aa93c4c5f22d0dbfa1683a4fa61，938源/2193可执行QA/33冻结/954prior/4136历史，仅三FE源delta，410后台原full1918+1/API42完全同字节，原结果精确绑定但未冒称重跑。V0018新单轮执行中，结束后才新完整check/build避免next-env派生写并发；旧build9Kv不能当此次修后构建。独立实际四库只读16库完整性/FK/全行/六新表/9迁移/两blob审计通过，16连接关闭与56样本hash零变化；作者恢复实际运行与独立只读分列。browser/153/14尚未执行，B5未关闭。

下一动作：V00另版QA v6封存后新候选/新隔离API完整重跑8，原失败保持；通过后原完整153/14及资源/保全/精确文档后验。所有必要门槛通过才关闭B5，持续更新当日文档。

以下保留已关闭B4批的历史执行事实：[TEACHING-LOOP-B4-RESUME-20261003](qa/TEACHING-LOOP-B4-RESUME-20261003/README.md)，实际结果见[报告](qa/TEACHING-LOOP-B4-RESUME-20261003/REPORT.md)、[矩阵](qa/TEACHING-LOOP-B4-RESUME-20261003/CLOSE-MATRIX.md)。每日记录按北京时间独立建立，旧首败/收据/冻结件保持；昨日暂停已由用户恢复。

稳定候选[r21](qa/TEACHING-LOOP-B4-RESUME-20261003/CANDIDATE-r21.json)，SHA `e558dfbf4af33790328c7c036edfee0aa38c1371da5cb65f6ac8c448ba7c4d39`：879source/53可执行QA/5契约/2007build，3043历史文件＋191已完成今日证据保护。相对r20只有helper删除161B/3行busy误判和candidate工具扩大已完成证据捕捉；生产书籍代码、原assert/标题/预算未改。独立窄审STATIC_READY，联合六TS类型0/725.347ms、lint0/1221.149ms；前后来源/构建/全部保护0漂移，next-env原字节保留。build `Ji-Jz8X9yY2R_79JOPivD`实际proxy8001；main@6aeb57280f6a7e0d7391cad4d150745479ea58ec未切换/未提交。

今日R14独立首轮r20为1通过/1失败、exit1/36491.677ms：一次真实点击4ms后busy被helper误当执行恢复，故障最终ready/身份/锁断言未执行；首败完整保留，82DOM审查区分相邻旧interrupted与稍后compilation截图，不推断锁因果。r21固定后完整新单轮2通过/exit0/38236.733ms、0跳过/重试：normal0次/fault1次trusted Continue，两书ready/finished、各8ready页、原笔记/ID/sameRun、native0/0/legacyNULL及cleanup四flag均实际通过。两trace159/182entry CRC全通过、6图由CTRL逐张view；实际expectrecords44/59均completed，不冒称静态matcher数为运行断言数。跨批R-14仍保留，不据单绿宣称触发根因或恒绿。

原2spec14chat今日实际单轮14通过/exit0/43832.314ms、0跳过/重试，已独立核标题/每例1attempt/三协议/取消/推理公式/20k50k/滚动，性能只是采样。26图全部实际view、前后SHA不变，CV01指定滚动静帧代码遮字与CV02/03控件像素观察见[逐图报告](qa/TEACHING-LOOP-B4-RESUME-20261003/b4-v00-docs/CHAT-VISUAL-v1.md)；保留chat视觉基准，不据静图判断交互逻辑或宣称全视觉PASS。B4三视口依据为其独立完整学情/练习链与手机补屏原件。

**原24spec153case今日完整新单轮153通过/153attempt、0失败/跳过/重试/flaky，exit0/371554.846ms。** JSON报告用时370811.109ms，UTC02:52:46.521175开始；原第7双书target20624ms/180000预算通过，两个helper正常分支continue0/0、真实ready/cleanup全true，原笔记/双ID/无锁顺序代码完整且case body通过，无首错/关闭异常。全绿原retain-on-failure实际ZIP0、JSON没有steps字段，不虚构执行断言数。昨日两轮152/1及r20首轮1/1各自原件保留，不拼绿、不豁免；新输出[b4-e2e-resume-first](qa/TEACHING-LOOP-B4-RESUME-20261003/b4-e2e-resume-first/results.json)继承原全目录/预算/workers/retry0。来源/QA/build/3043/191前后全0，实际变量ZQKY_B4_QA_RUN=resume-first，没有默认脚本自启或重建。

以下为已完成历史执行的精确共同源绑定，未冒称今日重跑：451FE/367实际业务BE与2007build同r17，完整check111文件1110单测/type/lint/build exit0/104383.649ms；API1698通过+1规模skip/270.40s；T70独立8完整场景/165HTTP、200×100全证据与分页；T80完整64通过/81904ms、四库迁移/备份恢复/双DOCX与模板/转换→T60→新T70；R09/10/11/12及R13原两独立/21expect与作者74回归通过，第六完整实际B4browser1/24925ms及手机8补屏通过。G1原八项与接续浏览器2/全量153已独立关闭，旧[G1关闭报告](qa/TEACHING-LOOP-G1-RESUME-B4-20261002/G1-REPORT.md)和全部首败原件不改。

原B4收口时：用户明确「下次不再需要我手工启动了」，后续隔离测试前端由CTRL负责启动和管理；当时用户PID21816/5174 creationUtcTicks639265864014910140/argv/r17实际HTML身份保持。原自有stream21412已guarded stopFile、原fixture finally返回/exit0、8001/8002释放、日志独占关闭、样本保留。本次G2开工现场无该用户PID或5174监听，不能把历史归属当现况。所有新测试根、历史根与旧六拒删根保留；正式.env/data/凭证/真实草稿不访问。具体自动审批拒绝仍不换工具/端口/Agent绕过。

原B4下一动作当时为停止，P/F收口与文档窄delta均已通过，CTRL已关闭B4；随后只读review与提示词也已完成。当前用户已下发新G2→B5授权，实际执行以本节顶部为准；不重复已关闭G1/B4或自动Git写/推送/部署。[每日同步约定](qa/TEACHING-LOOP-B4-RESUME-20261003/DOCUMENT-SYNC.md)不构成定时自动续跑授权。

## 2. B3 审查关闭台账

以下各项均保留原隔离复现，原B3-FIX批状态为 **修复并独立复验关闭**。逐项正确行为、原RV01–11及独立新增成绩/任务/提交/窄屏缺陷见[历史关闭矩阵](qa/TEACHING-LOOP-B3-FIX-20261002/G0-CLOSE-MATRIX.md)和三份V00报告；不修改旧审查原文。

| 编号 | 优先级 | 已确认问题 |
| --- | --- | --- |
| B3-R01 | P1 | 新建补题 queued@0→attempt 1 被前端误判接管，停止观察，候选入口不出现 |
| B3-R02 | P1 | 文件缺考标记加剩余空白被前端算成伪 missing，合法成绩无法确认 |
| B3-R03 | P2 | C/c 绕过物理列唯一校验，正式成绩可被封存为错误分数 |
| B3-R04 | P2 | 同表修正 headerRow 不重建行集合，真实表头仍被当成学生行 |
| B3-R05 | P2 | 身份表头未识别但计分列可识别时上传 500，无法进入人工映射 |
| B3-R06 | P2 | GB18030 成绩 CSV 使用替换解码，中文身份与状态证据乱码 |
| B3-R07 | P2 | recorded 修正携带空白/缺考/免考文本时返回纯文本 500 |
| B3-R08 | P2 | 旧施测创建响应在面板卸载后仍更新父级选择，覆盖新上下文 |
| B3-R09 | P2 | 失权整理轮的失败 checkpoint 写入无原租约 CAS，可覆盖新轮进度 |
| B3-R10 | P2 | 模型名额等待时取消，取得名额后仍发起模型调用 |

表中10项描述原审查问题，原B3-FIX批各项已通过独立正确行为断言；原失败日志/JSON保留。“冻结自洽”不是关闭依据，本轮G1结果另见下节及新批实际执行记录。

### 2.1 G1八项正确行为与接续整体门禁已关闭：B3F-R01–R08

2026-10-02，旧r7只读审查确认以下8项P2。本批G1已修复，并在冻结候选上通过新独立正确行为断言；不是原B3-R01–R10的重开编号，不改写[原审查](qa/TEACHING-LOOP-B3-FIX-REVIEW-20261002/REVIEW.md)。下表保留原问题描述，逐项新收据见[八项矩阵](qa/TEACHING-LOOP-G1-B4-20261002/G1-CLOSE-MATRIX.md)。原批当时未执行真实浏览器和E2E；接续批已完成并关闭整体G1，见下方新关闭报告。

| 编号 | 已独立验证修复的原问题 |
| --- | --- |
| B3F-R01 | 进入承认后继续编辑未保存分数，仍能确认旧矩阵 |
| B3F-R02 | 映射保存迟到 200 擦掉同一批次上的后续编辑 |
| B3F-R03 | 先访问施测再补名单，返回施测仍显示旧学生集合 |
| B3F-R04 | 超长 XLSX 分数被静默截断后解析为合法值并封存 |
| B3F-R05 | 成功发布不核租约到期；失败收敛用等写锁前时间 |
| B3F-R06 | 旧轮终态后的收尾窗口中 retry 200 queued，但新轮未调度 |
| B3F-R07 | 共同材料不同的题仍用旧指纹当重复，跳过或拒绝新题 |
| B3F-R08 | 合法 OMML 分隔公式有多个参数时只呈现首项，无不支持提示 |

原批独立正确行为与工程回归分别登记，原批当时浏览器门禁未执行。2026-10-02 接续批已补实际浏览器与适用全E2E，并关闭G1，最新[关闭报告](qa/TEACHING-LOOP-G1-RESUME-B4-20261002/G1-REPORT.md)优先；旧证据原文保持。长CSV字段解析错误信封已定向补测；畸形XLSX dimension仍为观察项，不夸称全部文件质量已覆盖。

### 2.2 B4后续审查三项，G2已关闭

2026-10-03，r21只读复查新增问题，编号与旧B4-R01～R13不同。**三项修复已通过G2独立23组件/11API/8真实浏览器，并完成全153、14聊天及最终收口，CTRL已关闭G2**；原B4阶段门禁与关闭原件不追改。详细原代码行与失败反例见[原REVIEW](qa/TEACHING-LOOP-B4-REVIEW-20261003/REVIEW.md)，本批新结果见第1节入口。

| 编号 | 优先级 | 当前问题与关闭方向 |
| --- | --- | --- |
| B4F-R01 | P2 | 切练习/历史卸载编辑器，未保存输入静默丢失；须统一保存/取消/明确放弃或隔离恢复稿 |
| B4F-R02 | P2 | unknown重试重新捕获编辑代次，旧练习ACK覆盖新分值，旧备注ACK清新备注；冻结首次代次与上下文，ACK不回退新输入/服务端基线 |
| B4F-R03 | P2 | 草稿PATCH无提交幂等，首写成功后原包重放409；补稳定提交身份或明确读取核对恢复协议，不盲采用新CAS重写 |

额外观察：公式样貌题号在XLSX被投影为formula，但真实T60回导正确；多共同材料统一前置缺少可见题组归属，仅静态观察。两项未定为阻塞缺陷，不能冒称成绩错误或材料错配。已有65窄回归与新增4学情探针通过，不覆盖上述失败路径。

## 3. 当前能力与建设边界

| 模块 | 已有实现 | 当前边界 |
| --- | --- | --- |
| 学习问答与模型管理 | 真实三协议 SSE、模型连接/目录/发现、凭证后端管理 | 真实供应商证据按具体模型与场景判断，不能以注册数量当通过数量 |
| 教材资料库与 RAG | 真实上传/解析/目录/修订/索引；混合检索、证据验证、可恢复轮次；生产走 RagV2Service | 相关性拒答闸门仍待完善；人工教学质量未验；历史本地登记只读 |
| 独立知识点库 | 身份/不可变修订/父树/别名/教材依据、表格导入和候选确认、真实页面 | AI 候选不自动发布，教材依据不可用不能当作没有依据 |
| 题库 | 独立库、导入与校对、正式知识点关联/筛选、AI 整理/补题候选、六态/公共retry、富内容 | 人工先保存新内容再审核后发布；真实 AI 教学质量未验 |
| 名单、原卷、施测 | 班级/学生/归属历史；DOCX 富解析/人工确认；固定原卷与参测快照 | 不自动评分、不识别评分点；修改已确认卷建立新修订 |
| 成绩工作区 | 完整名单/原卷工作区；XLSX/CSV小题得分、四态/服务端承认、总分/出勤校正与显式刷新、确认原包重放、修正/不可变历史/分页 | 200人次×100叶基线验证；不补零/不反推/不自动评分；真实供应商与正式数据迁移未验 |
| 教案工作台 | 本地规则填充、编辑/草稿恢复、Word 与打印/PDF 导出 | 已有实现须保留；B5后台保存与AI建议源码正在集成，整体独立验收未完成 |
| 学情报告与练习回流 | T70/T80、两页面、受管双DOCX/成绩模板与转换；原独立四库HTTP/完整浏览器/迁移/备份恢复已通过，B4已关闭 | 后续只读审查B4F-R01～R03已由G2修复并独立关闭，见2.2；原r21的两UI2/14chat14/全153及首败保持；AI教案属B5，实施中待独立验收 |
| 书籍、课程 | 保留本地内容/进度和课程会话联动 | 书籍生成仍是显式本地模拟，不作为本轮实施核心 |
| 写作、阅读、学习空间、智能组卷、模板中心 | 规划根页 | 旧已移除子路由不恢复；规划页不返回假成功 |

## 4. 9 月 29 日起的批次索引

| 批次 | 交付与后续状态 | 证据入口 |
| --- | --- | --- |
| RAG-QUALITY v1.1，09-29 | 图片文本投影、首答预算、证据窗口、模型选择、可验证备份恢复；独立复验附条件通过 | [批次报告](qa/RAG-QUALITY-v1/README.md)、[原批规格](archive/snapshots/20261001-docs-focus/docs/PLAN.md) |
| B0，09-30 | 四库、迁移、受管资产、任务协议、提交幂等与公共客户端 | [B0](qa/TEACHING-LOOP-B0/README.md) |
| B1，09-30 | 富内容、知识点后端、名单后端 | [B1](qa/TEACHING-LOOP-B1/README.md) |
| B2，10-01 | 原卷、题库增量、施测、知识点前端；原审查 RV01–RV11 由 B3 G0 修复 | [B2](qa/TEACHING-LOOP-B2/README.md)、[B2 审查](qa/TEACHING-LOOP-B2-REVIEW-20261001/REVIEW.md) |
| B3，10-01 | G0、成绩后端、五步工作区、题库前端原交付；后续审查10项由10-02本批修复 | [原交付](qa/TEACHING-LOOP-B3/REPORT.md)、[后续审查](qa/TEACHING-LOOP-B3-REVIEW-20261001/REVIEW.md) |
| B3修复/补齐，10-02 | G0/R01–10及独立新增缺陷复验；完整真实链与规模通过；API1523/check1069/E2E153全过，r7后验168项零漂移 | [本批报告](qa/TEACHING-LOOP-B3-FIX-20261002/REPORT.md)、[命令](qa/TEACHING-LOOP-B3-FIX-20261002/EVIDENCE-COMMANDS.md)、[首败](qa/TEACHING-LOOP-B3-FIX-20261002/ROOT-FIRST-FAILURES.md) |
| B3修复后代码审查，10-02 | r7开工168/168一致；另有8项P2待修，含成绩/编辑/名单刷新/租约/重试/查重/公式；仅审查与启动词 | [审查与证据](qa/TEACHING-LOOP-B3-FIX-REVIEW-20261002/REVIEW.md)、[下一阶段提示词](design/teaching-loop-v1/B4_总控启动提示词.md) |
| G1+B4当前轮，10-02 | G1八项独立行为通过，check1088/API1599通过；浏览器/E2E启动阻断未执行，整体G1未完成，B4未开工 | [状态报告](qa/TEACHING-LOOP-G1-B4-20261002/REPORT.md)、[八项与阶段矩阵](qa/TEACHING-LOOP-G1-B4-20261002/G1-CLOSE-MATRIX.md) |
| G1后续代码复查，10-02 | 本范围无新增可复现缺陷，新增边界及窄回归通过；续验配置与B4缺失导出/班名快照明确，未执行浏览器或B4 | [审查](qa/TEACHING-LOOP-G1-REVIEW-20261002/REVIEW.md)、[续验提示词](design/teaching-loop-v1/G1续验与B4启动提示词_20261002.md) |
| G1接续与B4暂停，10-03 | G1已关闭；r17 check1110/第六完整B4浏览器通过，最新原E2E152/1书籍中断，原14聊天未执行；按用户要求暂停 | [暂停交接](qa/TEACHING-LOOP-G1-RESUME-B4-20261002/B4-PAUSE-HANDOFF.md)、[B4报告](qa/TEACHING-LOOP-G1-RESUME-B4-20261002/B4-REPORT.md) |
| B4每日接续，10-03 | r21固定两UI2/原14chat14/原全153新单轮153实际通过；源构建保全0漂移，独立来源/资源/文档收口通过，CTRL已关闭B4 | [今日报告](qa/TEACHING-LOOP-B4-RESUME-20261003/REPORT.md)、[今日矩阵](qa/TEACHING-LOOP-B4-RESUME-20261003/CLOSE-MATRIX.md) |
| B4后续审查，10-03 | r21核对；三项新P2待G2，新增4学情探针/65窄回归通过；仅审查与提示词，未修产品或启动B5 | [审查](qa/TEACHING-LOOP-B4-REVIEW-20261003/REVIEW.md)、[G2+B5提示词](design/teaching-loop-v1/B5_总控启动提示词_20261003.md) |
| 文档整理，10-01 | 已完成归档和现行说明修正，保全/引用/独立文档复核通过，未改产品 | [本次记录](qa/DOCS-FOCUS-20261001/README.md) |

## 5. 验证记录与如实边界

- B3 原交付：后端 1405 例收集，一轮全绿，其余遇 R-19；check 97 文件/927 单测及 build 通过；全量 E2E 149 过/1 败为 R-14，隔离 3/3。以上是原交付的历史运行，不是本次文档整理重跑。
- 后续只读审查：既有窄回归 89 passed、1 skipped；独立成绩/任务反例和实际组件诊断复现 10 项问题。诊断测试通过表示复现成功，不是产品修复通过。
- 旧B3-FIX批10-02真实浏览器成绩确认响应丢失后同包深等重放、修正v2/v1详情与完整矩阵不变、题库Provider替身→候选→人工审核→确认/KP检索及实际公共retry已通过；200×100真实确认、50行分页首屏336ms/翻页339ms。该批三视口1440/1920/390像素、键盘及reduced-motion通过；原G1批当时尚未重跑浏览器，不能沿用旧结论；接续G1已另验浏览器及完整E2E关闭。真实模型/Word/WPS/Qdrant和人为教学质量未执行。
- 正式数据根的迁移/业务状态不从旧报告推断。本次没有启动正式应用、检查或迁移正式库；需要时按当前授权和隔离要求核对。
- 10-01文档整理仅验证文件保全与说明；10-02原B3-FIX批另建修复证据并实跑API1523、check1069及build、浏览器6项、E2E153项通过。原G1批另跑check1088/API1599+1skip及新独立正确行为，当时浏览器/E2E未执行；接续批现已实际完成并关闭G1。旧冻结件保持原文，候选与权威文档后验分别登记，不重算旧件隐藏差异。

## 6. 仍需保留的跨批问题

| 编号 | 状态 | 边界与依据 |
| --- | --- | --- |
| RAG-REL | 未关闭 | 09-29 质量集的 10 个边界问题仍返回 ok，缺相关性拒答闸门；[RAG 质量报告](qa/RAG-QUALITY-v1/README.md) |
| R-13 | 未关闭 | 特定真实模型推理预算样本出现零正文或 length 截断，不擅自关推理或无界加预算；完整旧台账在状态快照 |
| R-14 | 未关闭、跨批间歇 | 旧批写锁/interrupted与两轮152/1首败保留；r21窄QA判据适配后独立正常/一次Continue恢复及原153完整通过，最终笔记/ID/锁检查完成；未证明产品触发根因或恒绿，不豁免旧台账；[本轮只读调查](qa/TEACHING-LOOP-G1-RESUME-B4-20261002/b4-v00-browser/R14-STATIC-FIRST-FAILURE.md)、[旧证据](archive/pre-20260929/qa/UX-PERF-CLOSEOUT-20260923/r14/REPRO-EVIDENCE.md) |
| R-15 | 09-29 已关闭 | 旧 settings selector 按 contract-v1 修正，test:chat 14/14；不能继续沿用旧表中的未关闭状态 |
| R-18 | 未关闭、跨批间歇 | EmbeddingPanel 单测对并行加载时序敏感，不能靠重试或放宽断言宣布修复 |
| R-19 | 本批测试时钟问题关闭 | 只替换service模块任务钟，保留真实jieba冷加载/asyncio和50ms TTL；独立精确50ms/70ms过期、容量/重启2条通过，全量API1523通过；自动janitor扫描时序未测，未改生产TTL |

旧缺陷、已移除模块和历史首败的完整原文见 [归档索引](archive/README.md)，不在此继续铺开旧 H1–H6 路线。


2026-10-03 19:26补记：G2已关闭；B5修后FE v3已停写，独立18组件/42真实API通过，新完整check的1224单测/类型/零警告lint/build通过。新构建EuGU-xptkS4Dv7wiXoxD4实际代理8001，r1冻结938源/2193可执行QA/33契约/2004构建。真实浏览器原完整8首轮1pass/7fail，trace确认KP异步空集合及相对locator问题、课题/历史定位与clean初始缓存观察错误；原件保持，V00仅准备QA v6，无产品改动，B5未关闭。 独立18 exit0/2361.519ms/PID15572，新check exit0/106554.366ms/PID4448/118文件1224例。完整API1918pass/1既有规模skip、独立42与修后三FE之外410后台逐文件同字节绑定，未冒称重跑。r1 browser exit1/216349.337ms/PID18580，源938/QA2193/build2004前后0；1例真实丢保存回执/继续B/nativeBack/原包恢复通过，另7例失败不拼绿。原件见b5-v00/results/EXEC-R1-BROWSER-FIRST-v1.md与R1-TRACE-ATTRIBUTION-v2.json。五图已独立逐张view，Word/打印未执行，原成绩/报告/班级/练习四GET深等不变。自有API23196已专属stop正常退出，样本保留；自有前端manager16464/node27964仍同构建运行，8002未起。待QA新封存/新候选与新隔离API后重新完整8，再原153/14、资源/保全/精确文档后验。
