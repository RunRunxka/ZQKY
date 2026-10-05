# B4-T70-PREP v0 · 只读调查完成 / ready 等待正式契约

负责人 `/root/g1_resume_e2e`。2026-10-02，现场 `main@6aeb57280f6a7e0d7391cad4d150745479ea58ec`。已读根/API/web规则、第三附件的收紧规则、14d072ff…附件四至八、v2 T70及固定验收样本，并核本批G1-REPORT：G1已关闭。本文件是给CTRL的实现交接建议，**不冻结共享契约、不说明任何T70 API已可用**；没有修改产品、执行测试、导入app、启动服务/构建或做Git写入。当前读完ready停写，等待CTRL正式任务卡。

## 已核实的源码事实

| 现行代码 | 可复用能力 / 必须注意 |
| --- | --- |
| `repositories/teaching/scores.py:ScoreRepository.get_revision_in/require_revision_in` | 返回该修订独有的participant_snapshot、item_snapshot、paper_revision_id、confirmed state；不需要active指针。 |
| 同文件`matrix_cells_in` | 一次SQL读取该修订全矩阵，返回recorded/missing/absent/exempt与整数units，损坏明确500；可传显式选人集合。T70还需独立核全矩阵笛卡尔积完整、无多格/越界/分数超过固定满分，缺格不得补missing。 |
| `contracts/scores.py:ScoreParticipantSnapshot` | 固定participantId/studentId/studentNo/name/classId/attemptNo/attendance，**没有className**。最小T70按固定classId分组，className=null并给“该成绩未记录班名”的说明，不读当前classes表补历史。 |
| 同文件`ScoreItemSnapshot` | 固定itemId/itemPath/maxScoreUnits；总分继续只在所有计分叶recorded时有值。 |
| `repositories/teaching/papers.py:ItemRecord/ItemKnowledgeRecord` | 固定content、source_locator，知识点ID/修订/name_snapshot/role/source。`list_items_in`批量取题和关联，`list_blocks_in`取固定来源块/共同材料；避免逐格查库。 |
| `services/papers/reader.py:ConfirmedPaperReaderAdapter.read` | 按固定确认修订读取，标题取title_snapshot，计分叶及知识点/题面正确；返回类型**没有source_locator或全来源块**。不能用它的窄视图代替全题证据；T70自己的只读snapshot模块从PaperRepository取得完整字段，不修改既有reader。 |
| `contracts/papers.py:PaperItemView/PaperSourceBlockView/PaperRevisionContentView` | 已有完整题内容、来源坐标、共同材料/源块及固定revision标题视图。不能把旧“只未归属来源块”当完整报告证据。 |
| `services/papers/service.py`确认闸门 | 计分叶题面与共同材料、受管资产引用已核完整；旧确认快照读取仍必须对损坏结构显式失败。资产字节/散列验证放SQL/协调锁外。 |
| `services/jobs/engine.py:JobOutcome`及`JobStore.complete` | `publish(conn)`与job succeeded/result同教学库事务，原lease/attempt/token/expiry/cancel先校验，发布抛错整体回滚。直接复用。 |
| `main.py:JOB_KINDS` | teaching白名单**已有analysis**，无需再起kind；Registry还没有analysis_service注册装配。需CTRL接线service及router，register uses_model=False。 |
| `services/submissions/service.py` | make_command/execute_command规范JSON身份，owner+operation+submission，命中先replay，异hash409，未命中才apply；command_submissions已存在。 |
| `JobStore.create`与`TeachingCatalog.write_transaction` | **create自开独立写连接，当前没有create_in**；不得在analysis创建的写事务里嵌套调用create，否则等待自身锁，或拆成两事务留下半job/run。CTRL需提供共享create_in端口或冻结等价的单一同事务创建端口。 |
| teaching迁移0001–0007 | 当前没有analysis表；追加由CTRL写。workflow_jobs已有；不创建第二任务表或engine，不改旧SQL/hash。 |

## 建议的精确实现文件范围

待CTRL任务卡授权后，T70新文件：

- `apps/api/app/services/analysis/__init__.py`：build/export入口。
- `apps/api/app/services/analysis/service.py`：创建/查询/备注、注册analysis executor、纯输入检查与同事务发布闭包。
- `apps/api/app/services/analysis/snapshot.py`：只读固定成绩与原卷完整输入、选择验证、规范排序/hash准备、固定源/资产描述。
- `apps/api/app/services/analysis/aggregate.py`：无DB/IO/模型的any_loss_v1纯计算，不导入当前名单/知识点服务。
- `apps/api/app/repositories/teaching/analysis.py`：单一分析仓储，所有同事务写入用`*_in(conn,...)`，分页读回/损坏检查。
- `apps/api/app/api/v1/analysis.py`：薄router，服务未装配503，有界线程执行同步DB读取，job调度在事件循环；按CTRL冻结DTO响应。
- 专属测试建议 `apps/api/tests/analysis_support.py`、`test_analysis_rules.py`、`test_analysis_service.py`、`test_analysis_http.py`、`test_analysis_jobs.py`、`test_analysis_performance.py`。不修改既有业务测试或共享fixtures。

不写main.py、共享contracts/schemas、公共客户端、迁移、JobEngine/Registry/资产/富内容/PublicationCoordinator、导航、锁、权威说明。若读查发现这些端口需改，只向CTRL提交事实/建议。

## 需要CTRL先冻结的共享端口与DTO

1. `AnalysisCreateRequest/Receipt`及RunView、SelectionSnapshot、FrozenParticipant、ClassReportRow、StudentReportRow、EvidenceRow、NoteRequest/NoteView与Page，全部camelCase/内部snake_case；每个必需字段、分页、错误details、success/replay/reuse语义固定后才写。
2. 创建请求固定 `{submissionId,scoreRevisionId,selectedParticipantIds,ruleCode:"any_loss_v1"}`，assessmentId在路径且参与身份。选人非空且全来自此成绩；同studentId至多一个attempt，重复participantId也拒绝定位422，不能偷偷去重或偷选最新/最高。
3. 区分**提交请求hash**与**完整inputHash**：前者对固定请求ID/显式选择/规则的排序规范包计算，可先查成功submission；后者包含固定score/paper、全部冻结事实和规则版本，禁止current名字/active/时间戳/凭证。这样旧原包成功重放不被当前资产缺失或新活动状态检查挡住。若CTRL采用单hash，则先从原提交指向的封存run恢复原输入验证身份，同样不能先读易变源再replay。
4. 需要shared `JobStore.create_in(conn, kind, frozen_input, owner_id, job_id, ...)`，与现有create共用校验/编码/状态规则。创建run+job+submission一次事务；提交后才schedule。异常零半run/job/submission。新增公共端口由CTRL写并回归，T70不复制任务创建内核。
5. `AnalysisReadyReader`或服务公开`read_ready_report(run_id,owner_id)`交给T80，返回固定subject/score/paper/inputHash、可选KP固定修订/名称及报告证据身份；目标只能来自该ready报告。T80不读T70内部私有表或重新聚合。
6. 跨practice回流lineage的字段/reader待CTRL冻结：T70证据需固定practiceRevisionId/practiceItemId→paperItemId→score cell identity，不能猜尚未建立的转换表名；原文件卷lineage为空有明确含义。
7. 409建议REPORT_NOT_READY/SUBMISSION_CONFLICT等，422 ANALYSIS_SELECTION_INVALID/RULE_UNSUPPORTED/SCORE_NOT_CONFIRMED/SCORE_ASSESSMENT_MISMATCH，500明确SNAPSHOT_CORRUPT/ANALYSIS_DATA_CORRUPT；不ready不回空Page，未知filter目标拒绝。具体名字与HTTP状态由CTRL冻结，现阶段不新增契约常量。

## 规则、固定输入与证据存储建议

纯计算预建 `cells[(participantId,itemId)]`、`leafById`和`kp→fixedLeafIds`。所有分数和满分为整数units，recorded(0)有效。每participant×KP：有recorded失分优先needs_consolidation；无recorded为no_evidence；无失分且有效格不足为incomplete；全有效满分full_credit。`informationIncomplete = validCount < expectedCount`独立，因此失分+missing同时保留；另返四态计数，不能仅统计missing而忽略absent/exempt。

班级聚合以score固定classId和显式唯一学生集合为基准。每KP分母是至少一格recorded的人数、分子needs人数，0分母value=null；选中人数/valid/needs/informationIncomplete/noEvidence/fullCredit分别列出，不声称互斥总和。ratio numerator/denominator始终整数，value由后端输出，不影响input身份。总分只把每计分叶加一次，仅全recorded可见，不能从多KP结果相加。

建议把证据主体设计为每个**被选participant×计分叶**恰一条，内含固定KP关联列表；KP筛选命中关联，但不重复主体计数。200×100基线为20,000条主体，非仅失分证据。无KP的合法叶也留证据，不参与KP比率。用每run≤100条独立item快照保存完整rich/source_locator/共同材料/受管资产描述，再让20,000证据关联它，读DTO合成完整题面；不每格重复拷贝富图文造成数百MB和性能取巧。多KP关联本身另有固定links，DTO保留多关联及“综合题失分关联，具体错因待教师确认”。

创建时读取该确认score自己的全matrix及participant/item快照，和其固定paper全部items/blocks；核所属assessment、确认state、叶集合/itemPath/满分/矩阵数量，取得固定KP修订/名称。不调用current roster/active score/current KP名字；旧KP归档不改变旧固定事实。相同KP ID若在同固定卷出现不同修订/名称，需明确拒绝损坏或固定多身份处理，不能任意覆盖；建议以KP ID为分组且核同卷身份一致。

输入按stable participantId/itemId/KP ID与revision规范排序，整数字段不bool，JSON key规范化。保留score自己的全部可选人次、实际选择及完整matrix，不以新版施测参测表填缺。inputHash绑定固定快照；新submission但相同owner/inputHash重用已有run/ready结果，不重算制造新结论；非ready是否返回原job供显式公共retry由CTRL明确，不自动偷起第二轮。

## DDL建议与封存检查（仅建议，CTRL登记）

最小结构建议analysis_runs（固定IDs/owner/inputHash/inputJSON/job/ready标志）、analysis_item_snapshots及固定KP links、analysis_student_results、analysis_class_results、analysis_evidence、analysis_teacher_notes。如CTRL合并results表，需scope/discriminator与查询索引，仍支持真实分页。runs→同assessment的score与paper关系用现行复合FK；job真实FK及owner匹配，T80 practice引用run真实FK。KP跨库引用只能服务校验+固定快照，不造SQLite跨库FK。

输入从创建即不可改；ready后run/result/item/link/evidence不能UPDATE/DELETE，封存后对子表INSERT同样拒绝，直接插入ready run需拒绝（业务只先pending再在同事务写完整子表后封存）。ready transition校验预期participant/leaf/result/证据数量与引用身份，不能只检查一张结果表非空。notes独立追加表，只允许ready、本报告内participant/KP目标、非空有限长度；同submission重放原note，异包409，禁止UPDATE/DELETE，不改事实。

run公开运行状态建议由job六态派生，报告独立`reportReady`，避免第二个running/failed状态与job漂移。JobOutcome.publish里短事务写全部结果/全证据再封存ready；job终态由原complete同事务推进。纯计算、rich预检、资产字节读取均在SQL写事务及publication锁外；任何publish异常/lease失权/cancel都不留ready或部分结果。T70读取既有已确认同库快照不必核当前跨库活动状态，也不得在JobStore已持SQL锁时反向再拿PublicationCoordinator导致锁顺序死锁；若CTRL要求锁，应冻结统一外层顺序而不是实现者自造锁。

## 有意义的测试与200×100计划

- 手写A/B/C/D固定oracle：Q1=2 K1、Q2=3 K1/K2、Q3=5 K2，K1有效3需2/K2有效3需1，A9、D8、B/Cnull；核全部12主体证据及关联，非只错题。补loss+missing、有效0、全missing/exempt、双attempt显式不同选择、跨班、无历史className。
- 真实四库/TestClient创建固定score；非法空选/重复ID/同学生双attempt/他卷他assessment/非confirmed/损坏matrix/unknown filter定位。改当前名字转班、KP改名归档、active变化/新score/newattempt后旧input/result/evidence逐项相同；强制读异常不退空成功。
- 原包丢响应replay、同键异hash、同input新submission重用、创建run/job/submission故障零半行；ready/result/children直接INSERT/UPDATE/DELETE拒绝，notes追加及幂等。输入JSON损坏500。
- 真JobEngine/Registry执行cancel/lease expiry/旧attempt与发布中途故障；作业失败/取消/重启后原冻结input公共retry，结果+ready+job同tx。一条可控fault钩子/monkeypatch给测试，不生产假成功。
- 规模样本200唯一学生×100计分叶，完整20,000 matrix和证据；至少多KP叶检查关联不双计主体/总分。记录CPU/RAM、冷/暖样本准备耗时、快照读取、纯aggregate、publish、HTTP分页分别时间。3秒指标只对纯分析；输入/输出数量、所有页无漏/重、末页/筛选/稳定顺序单独核，超目标据实定位，不删证据/改样本减负。
- 实现者只运行专属pytest；CTRL稳定B4候选统一API/check/构建/E2E及迁移/备份。独立V00另写oracle和错误变体，不能调用aggregate作为预期函数。当前所有T70测试均**未执行（只读PREP）**。

## 当前交接状态

无外部阻塞，等待CTRL明确DTO、DDL、共享job同事务创建及T80 ready/lineage端口后发正式v1任务卡。当前已经停写；不把方案说明当实现或独立验收完成。
