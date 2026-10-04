# V00-G0 独立验收报告

任务：V00-G0 v1、追加只读审计v2、候选收口v3与最终文档一致性核查；验收者 `/root/v00_g0`，没有参与产品实现。2026-10-02。产品只读，写入范围仅本报告、`V00-G0-probes/` 与 `logs/v00-g0*`。**G0 独立技术验收通过：60 passed、1 warning、exit0，11.99s的实际执行对象为冻结r3；当前r7的后端验收按相同产品散列继承，未冒称r7重新实跑60项。** 本报告发现两项同类边界缺陷，保留原失败证据，由总控修复后以原反例断言独立通过；总控全量与浏览器结果的只读核对见末尾最终一致性结论。

## 候选与方法

- 开始候选 r1，`main@6aeb57280f6a7e0d7391cad4d150745479ea58ec`。`FROZEN-CANDIDATE-r1.json` / `FROZEN-G0.json` 当时158项，逐字节 SHA-256核对158/158、0漂移，见 `logs/v00-g0-hashes-before.json`。
- 总控在验收期间明确通知 r2 仅前端测试同步修改；随后另冻结 r3 的成绩 Decimal/过期预览/重复行、正式题目发布锁、过期heartbeat及前端提交/观察保护等变更。产品变化由总控完成，本验收者没有修改产品或根权威文档。r1历史清单保留，不把 r1 与后续已授权变更混写成0漂移。
- 最终 `FROZEN-CANDIDATE-r3.json` 165文件，独立终轮前13:47:49、终轮后13:49:19逐字节 SHA-256 **165/165，0漂移**；见 `logs/v00-g0-r3-hashes-before.json`、`logs/v00-g0-r3-hashes-after.json`。收尾HEAD仍为6aeb57280f6a7e0d7391cad4d150745479ea58ec。产品只读与同一冻结候选核查成立。
- 已读根/API/web AGENTS、CURRENT_STATUS/PROJECT_GUIDE、原 B2/B3 审查 REVIEW与EVIDENCE、全部7个B2原始探针、B3任务故障探针，以及本批任务/基线/实现结果卡。原诊断脚本未执行，原证据未覆写。
- 自建断言正确行为的 pytest 探针。复用现有 Harness 仅作为临时库、应用装配、受控 Provider 与基本样本的搭建帮助，独立构造调度故障、真实应用重启、租约身份矩阵、部分发布、归档竞态、真实0004旧库及迁移语句执行后的故障。
- 每个探针文件在任何间接 `app.main` 导入前创建系统临时根并设 `ZQKY_DATA_DIR`、`ZQKY_ENV=test`；Harness 另用pytest临时目录。TestClient实际跑FastAPI、真实路由/服务/仓储/任务引擎，8001仅请求地址，无监听服务器。受控 Provider，不访问真实模型、凭证、正式 `.env`/`.local-data`、Qdrant、教材原件或浏览器会话。

## 原审查逐项结果

| 原项 | 当前独立结果 | 实际覆盖 |
| --- | --- | --- |
| B2-RV01 | pass | 真实注册表题库失败→公共retry→attempt2终态；入队后调度异常只留queued且再次显式retry恢复；重复点击只调用新Provider一次；真实关闭/重建应用，queued无自动调用、running收敛interrupted无自动调用，显式retry@3成功；冻结输入/hash/model snapshot不变。 |
| B2-RV02 | pass | 任意resolution JSON拒绝；必要内容损失禁止exclude且全表行不变；允许不完整草稿保存，但无blocking干扰的空计分题在确认闸门422 ITEM_STEM_MISSING、零正式/提交写入；真实补录文本进固定修订并确认。无需答案/解析。 |
| B2-RV03 | pass | 自建无题号DOCX，未归属paragraph/table/OMML formula/image四类完整块逐项等于persisted block_json；合并跨度3、真实PNG字节/类型读回，未引用受管资产拒绝。 |
| B2-RV04 | pass | 真实generation等待模型名额后改配置，failed MODEL_CONFIG_DRIFT、Provider0/批次0/原指纹不变；knowledge等待漂移同样0；paper实际ProposalRunner指纹漂移与临调用取消均Provider0。 |
| B2-RV05 | pass，N02已关闭 | 中间批+失败checkpoint的wrong token/attempt、空token、bool attempt、恰好过期/超时、cancel请求、所有终态、新holder接管12类：所有表逐行完全不变。另确认过期heartbeat不续expiry、不复活原lease、旧batch仍零写。 |
| B2-RV06 | pass，N01已关闭 | paper与question确认在重核后、域事务前暂停，另线程公开归档无法先完成；提交后归档及原包历史重放正确。正式question PATCH新增知识点同样阻止归档在题库事务前完成，原失败反例已通过。 |
| B2-RV07 | pass | 草稿/正式题继承数学关联而改语文学科422定位拒绝、全题库表不变；显式清空成功，旧正式修订关联逐项不变。 |
| B2-RV08 | pass | 原09-30施测改09-01破坏09-20归属时422、原详情与归属历史不变；显式指定原attemptNo=1重确认依据后改日期200；不能以默认新补考人次代替原人次重确认。 |
| B2-RV09 | pass，引用独立前端验收 | V00-FRONTEND真实useKnowledgeJob StrictMode adopt终态一次callback/零HTTP；不把后端或普通模式测试当StrictMode证据。 |
| B2-RV10 | pass，引用独立前端验收 | V00-FRONTEND knowledge retry/cancel×成功/失败×reset/switch/unmount 12例，真实hook/client，仅fetch边界替身，旧响应零view/error/callback。 |
| B2-RV11 | pass | 确认FROZEN TITLE后新草稿改标题，固定内容DTO与reader完整对象逐项不变，补录正文仍保留；0004旧库标题回填只使用当时可变标题，不声称恢复未保存原标题。 |
| 已披露public publish rollback | pass | 三业务域question/knowledge/teaching × AppError/内部异常 × 正常失败/取消优先/新holder接管共18例。publish实际先写各自同库sentinel再抛错，业务行整体回滚；失败收敛保留原attempt/token；取消在失败处理前发生则cancelled；新holder接管并写新checkpoint后旧finalizer不覆盖。名额释放。 |
| B3-R09 | pass | 实际整理服务Provider失败→record_organize_failure入口暂停→expire/claim新attempt2并提交建议→旧失败携带本轮attempt1/token；新checkpoint进度1及suggestionIds、running/token都不变。 |
| B3-R10 | pass | generation/knowledge在唯一模型名额等待时取消，放行后Provider0、批次0、cancelled；generation下一实际模型任务成功，active_jobs0。paper执行器临调用取消0。 |

RV09/RV10来源为同批另一位未实施产品的独立验收者；最终 r3 独立前端5文件105场景通过、exit0，见 `logs/v00-frontend-r3-final.log`；其中任务观察55例，含真实三个hook StrictMode终态单次、36条retry/cancel迟到响应零副作用。该验收者另外发现的知识点首次queued@0观察F06首败保留，总控修复后最终通过并关闭。前端场景不计入本报告Python实跑数字，全B3最终结论由总控给出。

## 新发现与首败证据

1. **V00-G0-N01 / P2，r3修复并独立复验关闭：正式题目新修订关联发布锁不跨域事务。** 原 `QuestionBankService.patch_question`调用`_link_rows`时核验active，但锁随helper返回释放；实际题库事务在锁外。独立真实HTTP在catalog.patch_question前暂停，公开knowledge archive返回200后，题目PATCH仍200，新正式关联引用已归档点。首败 `logs/v00-g0-formal-link-race-first.txt`、探针`test_formal_question_new_link_publication_blocks_archive_until_domain_commit`。总控将资产/指纹预检保留锁外，关联核验和题库事务放同一question.patch临界区。r3原探针 `archiveFinishedBeforeDomainCommit=false`，两个合法操作按顺序各200，终轮通过。
2. **V00-G0-N02 / P2，r3修复并独立复验关闭：晚到heartbeat复活已过期lease。** 独立真实store/catalog+同一假时钟：30秒lease经过31秒后execution_allowed=False；原heartbeat仍True并续expiry，随后旧token的batch新增suggestion/nextBatch1。首败`logs/v00-g0-expired-heartbeat-first.txt`、`test_expired_heartbeat.py`。总控在同一短事务核有效expiry，r3原探针 `expiredHeartbeatAccepted=false`、`expiredBatchCreatedAfterHeartbeat=false`、原checkpoint不变。没有修改原反例断言降低要求。

另只读审核了总控 `test_engine_slot_wait_keeps_lease_and_blocks_takeover` 的修正：旧一次假时钟推进91秒超过3秒lease，却期待late heartbeat复活，和N02正确行为矛盾。新10次×2秒，每次到期前等真实1秒heartbeat；仍验证总20秒等待超过lease、等待续租、JOB_BUSY阻接管、max concurrent1、两任务成功和active_jobs0。旧“拿到slot后才开始heartbeat”实现仍会首轮超时失败，此修改不放宽核心业务断言。总控首败 `logs/root-review-boundaries-r3.txt` 保留，后续执行结果由总控日志负责，本验收者只审核其口径。

## 迁移独立结果

`test_independent_migrations.py`8个场景全部通过：真实0001–0004旧库直接构造已确认卷、2班、3学生、两施测、4参测（含第二人次与四态），再应用0005+0006+0007。

copy、rename、trigger、registry注入是在真实SQL已经成功执行之后抛错；另构造真实FK孤儿、integrity第一行ok第二行错误、verification不符。所有失败均完整schema、所有表行及schema_migrations登记逐项等于迁移前，foreign_keys恢复ON、FK/integrity正确，再跑原登记计划成功。确认卷不可变与施测固定卷触发器仍拒绝修改；登记计划hash漂移只读校验拒绝且全库不变。没有修改原迁移SQL或正式数据。

## 实跑命令与首轮探针修正

所有命令在仓库根，用已有 `apps/api/.venv/Scripts/python.exe`，`PYTHONUTF8=1`、`PYTHONIOENCODING=utf-8`。例如：

```powershell
& apps/api/.venv/Scripts/python.exe -m pytest docs/qa/TEACHING-LOOP-B3-FIX-20261002/V00-G0-probes/test_independent_g0.py docs/qa/TEACHING-LOOP-B3-FIX-20261002/V00-G0-probes/test_independent_migrations.py docs/qa/TEACHING-LOOP-B3-FIX-20261002/V00-G0-probes/test_expired_heartbeat.py -q -s -o addopts=''
```

| 日志 | 实际结果 | 说明 |
| --- | --- | --- |
| v00-g0-first.txt | exit1，23pass/4fail | 探针误把可保存的空草稿当应当PATCH拒绝；未知对象issue无blockId，需选实际段落；knowledge archived现契约409；GET不含create replay字段。保留首败后按真实契约修正探针，未改产品。 |
| v00-g0-second.txt | exit1，29pass/9fail | 重确认原人次漏attemptNo而新增了补考；自建0004 file_assets漏必填created_at，影响迁移8例。均为搭建错误，日志保留。 |
| v00-g0-third.txt | exit1，36pass/2fail | 故障注入误写temporary表名assessments_new；真实计划使用assessments_rebuilt。修正注入目标，仍要求明确发生故障并完整回滚。 |
| v00-g0-r4.txt | exit0，41pass/1warning，7.29s | 上述原项与迁移独立正确行为合跑。 |
| v00-g0-additional.txt | exit0，2pass/34 deselected/1warning，1.39s | 补充question确认锁与实际服务原lease失权失败交错。 |
| v00-g0-formal-link-race-first.txt | exit1，1fail/33 deselected，1.34s | 真实产品N01，不是搭建错误。 |
| v00-g0-expired-heartbeat-first.txt | exit1，1fail，1.03s | 真实产品N02，不是搭建错误。 |
| v00-g0-three-domain-publish.txt | exit0，18pass/33 deselected/1warning，3.48s | 三业务域AppError/内部异常、取消/接管/回滚独立矩阵。 |
| v00-g0-final-r3.txt | **exit0，60pass/1warning，11.99s** | 最新稳定r3，所有独立正确行为与原两条反例一次合跑。 |

warning为现有Starlette/AnyIO BlockingPortal弃用提醒。终轮60条是一次实跑，不是多次测试并集；未跳过任何独立用例。两条原失败反例与所有旧失败日志仍保留。

## not_run 与资源

- 未执行全量pytest、npm check/build/E2E、实际浏览器/三视口/人工视觉或200×100压力；由总控串行独占资源，不用本报告窄测替代。
- 未执行真实模型质量、Word/WPS、Qdrant、正式库迁移或跨进程部署；本批测试模型都是Provider替身，发布锁仅进程内保证。
- 自建线程全部join，临时数据库连接close，真实JobEngine自建任务shutdown；TestClient关闭lifespan；bootstrap TemporaryDirectory由atexit清理。pytest自管临时数据未递归删除未知路径。没有启动常驻进程、监听端口、Git写操作或外部消息。

## 追加只读时钟审计 v2

总控全量API首轮 `logs/root-api-final-r3.txt`：6 failed、1517 passed、5 warnings、208.09s。本段仅审核指定的两处时钟用例，不把G0窄验收通过写成全量通过。总控随后修改既有测试，冻结r3的60项结果仍对应上述原候选，后续测试delta由总控重新冻结与实跑。

**排队续租口径：pass（只读源码审查，未独立执行该既有用例）。** 原10×2秒循环只等待second expiry改变；second先续租后立即推进下一2秒，first心跳未被调度，first到期被取消后second拿到slot并完成，后续等待expiry改变超时。总控修正版已读：每轮advance前取first/second expiry；advance后同时要求两者仍running、attempt1、expiry严格增加且大于clock.now()；每轮额外assert只有first进入执行器且两个task均未结束。总20秒逻辑排队、JOB_BUSY阻接管、两任务成功、max_concurrent1、顺序与active_jobs0的原断言都保留。只用expiry !=不足，terminal清空expiry也可能满足；新版使用严格增加和running避免该伪通过。旧拿到slot后才开始heartbeat仍在第一轮无法满足second续租，故修正保留回归检出能力。实跑结果由总控日志负责。

**R-19容量/TTL/重启口径：pass（独立2条正确行为探针）。** 原ttl=0.05秒同时包含真实jieba冷初始化/完整检索时间，容量检查时旧轮可能早已过期，故原用例DID NOT RAISE不能归因容量闸门失效。总控修正版已读：只将 `app.services.rag_v2.service` 模块的 `time` 绑定替换为 `SimpleNamespace(monotonic=fake_now)`，不修改共享标准库 `time.monotonic`，保持asyncio/线程/检索真实运行；逻辑时钟保持到wait-user后先容量检查，再推进0.07秒，保留所有原过期、retired有界、释放容量与重启断言。TTL仍0.05，不增加TTL，不预热，不修改产品。

独立 `V00-G0-probes/test_clock_audit.py` 从临时目录、真实教材目录/封存/分块/HybridRetriever开始；替身仅既有Embedding/内存向量/概括。一次冷进程真实jieba构建0.333秒，大于原50ms TTL，仍完整得到wait-user。在逻辑0和0.049秒容量429且同轮重连不重复检索；在精确0.05秒与原0.07秒分别过期410、旧轮不隐式重跑、容量释放、retired<=4、新服务重启410。另断言共享time函数未改与事件循环时钟仍推进。**2 passed、exit0、1.64s**，`logs/v00-g0-clock-audit.txt`：

```powershell
& apps/api/.venv/Scripts/python.exe -m pytest docs/qa/TEACHING-LOOP-B3-FIX-20261002/V00-G0-probes/test_clock_audit.py -q -s -o addopts=''
```

自建探针首轮2 fail仅为额外“真实时钟推进”断言sleep3ms小于Windows时钟分辨率，日志 `v00-g0-clock-audit-first.txt`保留；改为30ms只检验asyncio时钟未冻结，与业务TTL推进无关。业务正确行为断言未放宽。独立2条不并入先前一次60项实跑，不声称是同一冻结候选62项合跑。该方法验证start->_prune的TTL、容量与重启，与原R19覆盖等价且增加精确边界；自动janitor扫描时序没有执行，原R19也未覆盖该点。

## 最终候选只读收口 v3：r7

当前冻结为 `FROZEN-CANDIDATE-r7.json`，168项；`main@6aeb57280f6a7e0d7391cad4d150745479ea58ec`。独立逐字节核对168/168、0漂移，首次14:12:52，见 `logs/v00-g0-r7-hashes-before.json`；报告收尾再核见 `logs/v00-g0-r7-hashes-after.json`。本方没有修改产品、既有测试、权威文档或Git，不启动服务、不占端口。

`logs/v00-g0-r3-r7-delta.json`记录实际差异：三Python测试（jobs_engine变更、rag_sessions与scores_confirm新纳入冻结清单）、两browser spec与一份assessments模块CSS（新纳入清单），没有移除项。这里“新纳入”是相对r3清单，不声称源文件此前不存在。r3已登记的41个 `apps/api/app/` 后端产品/迁移文件与r7逐项相同，全部在磁盘与r7 SHA一致。自建探针及使用的后端产品未变，故原G0 60项、迁移8场景、原N01/N02关闭结论继承；没有为了重复计数重跑相同产品探针。v2时钟修正版属于已审测试delta，后续总控全量实跑覆盖，不把新CSS称为全产品无变化。

以下均由总控执行，本方只读核对日志、XML或Playwright JSON；退出码0来自总控执行结果，不冒称本方运行：

| 范围 | 核对到的实际结果 | 证据与界限 |
| --- | --- | --- |
| 完整API r4 | 1523 passed、1 warning、exit0，207.40s | `logs/root-api-final-r4.txt`；`root-api-final-r4.xml` tests1523/errors0/failures0/skipped0。r7后端产品未改，继承；保留r3首轮1517pass/6fail。 |
| 全check/build r7 | typecheck、lint、108文件1069单测、Next生产构建通过，exit0 | `logs/root-check-final-r7.txt`；构建成功不代替业务/视觉。 |
| 两真实浏览器spec r7 | 6 passed、exit0，24.6s | `logs/root-browser-final-r7.txt`；`browser-final-r7/results.json` expected6/skipped0/unexpected0/flaky0。真实隔离FastAPI与HTTP，模型Provider替身；含200人次×100叶、首次补题与公共retry。 |
| 全量E2E r7 | v3核对时153项运行中，未提前记pass；最终终态核读见下一节 | 当时 `logs/root-e2e-full-r7.txt`只有进行中的逐项结果，历史核对时间与最终结果分开记录。 |

真实浏览器链截图存在并按r7目录保存；本方没有重新打开浏览器或执行人工视觉，因此不把截图文件存在当作独立视觉通过。200×100规模在总控真实浏览器日志已有成功条目，本方此前not_run仅描述自己的执行范围；供应商教学质量、Word/WPS、实际Qdrant与正式库迁移仍未执行。

只读阅读README/G0-CLOSE-MATRIX/EVIDENCE-COMMANDS，原项关闭、独立数字不相加、R19另列、真实模型/正式数据边界及全量E2E不预记pass均符合证据。向总控指出两处措辞需收紧：RV09/10列迟到200/409/422，但独立task-observation的36条迟到fetch故障实际为409，没有该组合422证据，应只写200/409或给出对应422证据；矩阵后续delta段应补r6 spec/r7 CSS，并写后端产品不变，避免让当前r7读者理解为全部产品不变。这是证据表述修正，不是新的G0产品阻塞；本方没有修改这些权威文档。

## V00-FINAL-DOC v1：最终一致性通过并停止

**结论：一致，无剩余文档或G0阻塞。** 只读完整核查本批REPORT、EVIDENCE-COMMANDS、G0-CLOSE-MATRIX、FINAL-VERIFICATION、RESOURCE-CLEANUP及CURRENT_STATUS/NEXT_SESSION_START，并核对实际XML/Playwright JSON、当前散列与资源现场。本次没有新增产品探针重跑或扩大业务验收范围；结构化结果为 `logs/v00-g0-final-doc-audit.json`。

- 计数与归属一致：API1523、check108文件1069单测与build、真实browser6、全量E2E153均为总控执行，exit0。`browser-full-r7/results.json`实际stats expected153/unexpected0/flaky0/skipped0，duration361326.657ms；递归逐条枚举153全部expected，每条results数为1，六条本批真实链在该全量里再次通过。没有把六条窄测加到153或把独立60/71/105/2相加成全量数字。
- 候选与继承一致：FROZEN-CANDIDATE-r7、FROZEN-CANDIDATE、FROZEN-G0三件均指r7/168项；FINAL-VERIFICATION的168条expected/actual与冻结件相同。原r3后端41项及迁移不变，原独立实跑可继承；r7 CSS变化明示，由独立前端实际图片/真实测量复核。r4独立167项前验全匹配、后验165匹配的两个browser spec漂移保留；r5前后167/167匹配，未冒称r4零漂移。
- 迁移与边界一致：0001–0007及登记散列没有新改，0006/0007复合FK、已确认和固定修订闸门保留，已填旧库故障/回滚/可重跑结论与本方8场景相符。现用SQLite版本独立只读返回3.53.1。正式库迁移、真实供应商教学质量、Word/WPS/Qdrant、超200×100与跨进程发布协调仍未执行，R19自动janitor扫描仍未测，其他跨批问题不随单次全绿关闭。
- 文档问题均已由总控关闭：此前矩阵RV09/10精确收为迟到200/409，r7 CSS delta补明；本轮发现CURRENT_STATUS第5节旧“全量E2E当前运行”，总控改为API1523/check1069+build/真实6/全E2E153全部通过，本方已重新读取确认。F20组件迟到422另有实际独立组件探针，不与任务hook的200/409覆盖混写。
- 最终文件保全与资源一致：当前next-env SHA为0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc，与原字节登记相同；main/HEAD未变、四旧B2/B3证据目录的tracked diff为空。独立只读端口查询8001/5174/16333无监听；六个root临时目录逐一Test-Path仍存在，和RESOURCE-CLEANUP“blocked by policy后保留”相符，本方未删除或绕过拒绝。IAB关闭/reset仅作为总控资源记录，不假称本方操作。
- 总控最终刷新后的POST-ACCEPTANCE-DOCS六项权威文件、DELIVERY-FILES的90项（含原用户next-env）已逐项对当前磁盘hash，全部匹配。收口期间曾有权威文本变化，最终后验已刷新；不将这些文档的暂时旧SHA当永久阻塞。168是冻结项数，不是改动文件数，90是该源/权威清单数，不计新QA目录内所有证据。
- 最终停B3一致：REPORT、CURRENT_STATUS、NEXT_SESSION_START、FINAL-VERIFICATION均明确B4/T70/T80/学情/AI教案/练习外键未启动，没有提交、推送、部署、分支切换；后续工作须由后续请求确定。

本轮最终逐字节r7核验见 `logs/v00-g0-final-doc-hashes-before.json`与`v00-g0-final-doc-hashes-after.json`，前后168/168、0漂移。自有报告与证据写入完成后停止，无剩余核查项。
