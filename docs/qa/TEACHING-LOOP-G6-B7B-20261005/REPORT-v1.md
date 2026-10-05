# G6 / B7-B 本批报告 v1

[G6独立有限技术关闭](G6-CLOSE-v1.json)和[B7-B独立离线技术验收](B7B-OFFLINE-ACCEPT-v1.json)均已由ROOT确认，见[本批限定技术收据](CLOSE-v1.json)。本批止于该范围，最终文档后验、资源、完整性和封印单列后追加证据。进度入口为[CURRENT_STATUS](../../CURRENT_STATUS.md)，范围为[本批授权](../../design/teaching-loop-v1/B7B_总控启动提示词_20261005.md)。本报告不关闭原B6/B7整体，也不代填真人、原生或RAG结论。

| 分支 | 当前实核 | 证据与边界 |
| --- | --- | --- |
| G6正常ACK缓存归属 | pass，独立有限技术关闭；作者274、独立211、新浏览器16、现行174全通过 | ACK与公开cleanup共用完整FrozenSubmission归属/活会话/读回判据；两页已打开、共享真实同源localStorage；foreign/坏/不可读拒删，合法空包可结束，明确结果不重发。localStorage读取与删除不是原子CAS |
| B7-B离线技术 | pass，预算64与结果76各自新完整独立轮通过 | 新CLI/预算账本/实际wire/usage/结果返回检查；不增加API/业务表/迁移或修改生产后端、旧工具、273离线包 |
| 授权live | not_run，真实调用0 | 用户未提供明确模型、精确caseIds/sampleCount、attempt与可执行总预算授权；本修订没有模型计费proof registry和可信live host，费用模式不支持，CLI live硬拒。fixture计费证明不支持任意真实模型 |
| 教师反馈 | not_run/teacher_pending | 八维/硬失败/理由/建议与实际case/输出/候选/DOCX身份的返回接口；合成接口样例不是真人签收 |
| Word/WPS | not_run/native_pending | 原生控制不可用，原13历史PDF页不能代替实际原生页数和逐页核查；没有新真实候选导出请求，不重制旧四份 |
| RAG-REL | OPEN/not_run | 固定教材事实复核不是检索相关性验收 |

## G6实际轮次和候选身份

| 门禁 | 实际候选 | 实际结果 |
| --- | --- | --- |
| 作者原反例 | 原hook新label | 原8中4own通过/4foreign失败，精确首败保留 |
| 作者最终完整 | 作者最终hook/test | 274/274 = 新83＋原8＋原183；完整首轮272/274两项新QA提交时序失败保留，新完整轮未拼绿 |
| 总控完整check | G6-prebuild-r1 SHA80c84dd700987e1150cb549926ca9612627c7cff4d70dedb4ec0b6497676279d | PID25440、117167.873ms、exit0；127文件/1463单测/type/lint0/build，next-env精确恢复 |
| 独立组件 | G6-built-r1 SHAee0e09f012c6b710c383cf9784f69c0d6b86b506a6d06b24c5ffea3a324f198c | PID19676、30832.1052ms、211/211；16文件，83作者新例不计为独立例 |
| 浏览器首启动 | G6-built-r1 | g6-browser-r1，ROOT遗漏Node导致WinError193，child未创建/测试0；原receipt/log/TEMP与原字节另存，不计通过 |
| 浏览器首完整 | G6-built-r1 | g6-browser-r2，PID19584、30681.98ms、8旧G5pass/8新G6fail；新QA错误假设干净B已持久草稿，在完整数据检查前失败。原测试/trace保留 |
| 浏览器最终完整 | G6-built-r2 SHA70ef13ca38ed7cf7efbbb8d344b14de5ac0e1ada7b28ca79e5cb6a56896dd5c8 | g6-browser-r3，PID26972、25193.521ms、16/16、0skip/retry/flaky/globalErrors；8新同源双页＋8原G5 |
| 现行完整E2E | G6-built-r2 | g6-full-r1，PID25996、553558.534ms、174/174；原29spec/174含21UI与R14，0skip/retry/flaky/globalErrors |

G6所有实际门禁的产品、契约、构建逐SHA绑定分开保存。新build为`wsH0-uD7VDC2ACYsbiRfS`，实际文件rewrites指向8001；没有额外HTTP身份probe。check之后ROOT仅更正文档工具显示标签，built-r1之后新browser QA仅增加B原POST冻结后公开编辑、等待真实持久草稿和完整期望对照；产品与build保持，211旧实际身份不重写，不冒称全部r2重跑。执行记录器和最终资源核查器的新QA也单列，不借它们改旧业务oracle。


## B7-B独立技术轮次与实现边界

全候选为[CANDIDATE-B7B-offline-r1](CANDIDATE-B7B-offline-r1.json)，SHA `08e71f7d386e4005406209718317220506829bf9816d9d9e4bce1b934dc61988`：972source/3771执行QA/33contract/970build，文件数不是用例数。G6前端/正式后端/共享契约/build与其实际G6门禁字节相同；新增11个B7B产品/说明/测试文件另受本候选绑定。check/211/16/174各自实际G6身份保留，不冒称它们在all候选重跑。

| 门禁 | 最终完整实际轮 | 首轮与边界 |
| --- | --- | --- |
| 执行器作者 | 73测试；CLI原15生产链15 fixture/real0、已核usage3000；原quality52、prepare49＋34subtests | 作者自检；初四失败、材料启动器/TEMP与并行源码漂移完整原件保留 |
| 结果作者 | 11组84 CLI = 10正常＋74正确硬拒，实际X15材料只读交叉检查 | 首轮QA写既有副本FileExistsError保留，79中间轮与84最终轮分开 |
| [预算独立V01](v00/executor-independent/RESULT-v1.md) | full-r2，ROOT actual worker23816，34198.513ms，exit0；64/64、27 fixture边界/real0 | full-r1行为64/27/0，但锁/入口出生采venv launcher；原件保留，不倒签worker |
| [结果独立V00](v00/result-independent/RESULT-v1.md) | full-r2，ROOT actual worker25392，71962.261ms，exit0；76/76、77 checker＋1setup、18 fixture/real0 | full-r1行为76/18/0，但77 checker＋setup采launcher；原件保留 |

两独立新完整轮仅以同源CPython3.12 base和原venv site-packages取代二次启动器，冻结产品/QA/oracle未改，actual all-r1保持；运行设施差异见[原记录](ctrl/B7B-RUNTIME-IDENTITY-CORRECTION-v1.json)。最终每个checker自报PID等于Popen实际base句柄PID，锁owner15052/contender26236亦对应，GetProcessTimes/actual wait/日志关闭均实核。全部候选域前后零漂移，不拼轮或追加伪出生。

V01核三协议完整wire/endpoint/cap，发送前5096预留与已核48结算，最后余5052拒后例；坏JSON/结构/length仍计attempt/usage；坏usage、timeout/cancel/redirect/second-send/response journal未知保留并停；reserved/dispatched/responded重启不重发；同授权换run/label不清预算/attempt，损坏账本拒绝且字节保持，成功原receipt重放0。实核40个OBSERVED/200个非空artifact SHA；9个唯一settled各48、24个unknown各5096、1个pre-reserve journalfail发送0，多个独立scope不合并称单账总预算。合法imports184/TEMP SQL4661/selfpipe1，五禁止及授权路径读取实际0。

V00核10技术正常、40关联/保留反证、13teacher和13native接口oracle。新生产原15＋C14 chat＋C01 responses/anthropic共18仅fixture，分钟手写合法且不同原精确fixture数组；生产规范化/时长/KP/依据/整字段应用、教师六字段和未选字段保持，实际raw/wire/usage/attempt/job/fingerprint/candidate/ledger/hash及完整源码闭包相互绑定。setup合法imports183/TEMP SQL2146/selfpipe1，五禁止实际0；77纯checker四禁止实际0，实际productionModulesImported另存，不谎称生产导入0。原273及四冻结域一致，原receipt重放0。

新的[执行入口](../../../scripts/teaching-quality/controlled_trial.py)与[返回检查入口](../../../scripts/teaching-quality/trial_result_check.py)只新增CLI/JSON账本与专属测试/说明，复用生产链，未改正式业务API/表/迁移/依赖、旧common/aggregate/preflight/prepare或原273包。预算技术证明止于受控fixture与可信DI接口；当前CLI live硬拒、缺具体模型proof registry和trusted host/凭证绑定，费用模式不支持。合成DOCX ZIP/1像素图只是返回完整性反证，顶层teacher/native继续pending，不作真人或排版质量结论。后续范围及返回入口见[B7B交接](B7B-HANDOFF-v1.md)。

## 保全和适用历史引用

开工main@b7f99ab09826c68724e281d01e15215e660c1ce0与当前未提交工作保留。[OPENING](OPENING-v1.json)实核G5 built-r2：960source/3660执行QA/33contract/970build零漂移；本批开工执行QA含后续审查为3670。旧QA46952、原材料1056和273精确引用保持，文件数不是测试数，也不冒称旧G5时点的22207。

[历史同源绑定](HISTORICAL-REFERENCE-v1.json)逐项验证后端410、聊天/公共壳186、导出核心11与原材料1056不变，本批完整API/聊天专项/原导出重做均not_run且适用引用单列。旧导出43中12项历史漂移不整体转签；唯一旧VISUAL-REVIEW引用缺件保持MISSING_NOT_RUN，旧物理SQLite/Blob源TEMP缺失保持not_run_source_temp_unavailable，本批新TEMP生产SQL不补造旧恢复证明。

六现行文档只更新本批新增状态块，完整开工内容含v2原任务/伪代码与先前审查保持原字节；Guide/API/ROUTES/PLAN、原Word、锁文件默认不改。R14跨批间歇/CV01～03/OBS-LP-MODE-LABEL与原环境观察保持OPEN。没有正式数据/6333、Git写入/提交/推送/切分支/部署或自动下一业务模块。

## 资源与独立后验边界

G6独立原图/trace签核完成：[V00结果](v00/RESULT-v1.md)实核全部190原trace ZIP CRC、逐张查看24原PNG；7次操作后blob备份触发的额外page事件如实记录，没有第三操作owner或额外POST。[G6资源收据](RESOURCES-g6-closed-v1.json)核6已启动owned实例、1无child首启动失败与36捕获后代均闭合，5174/8001无监听，frontend自有句柄停止exit1不算门禁失败。全部原失败及TEMP保留。

[后续资源实核](RESOURCES-pre-doc-v1.json)已核10个ROOT owned收据、1个无child首败和36捕获后代闭合，5174/8001无监听；新资源工具根据组件原CIM CreationDate派生已捕获出生身份，旧G6资源v1原错误归类保留。[作者与独立子进程后核](RESOURCES-author-independent-pre-doc-v1.json)核945条原command/child引用行及首轮76个实际checker worker；这是含历史首败和重复引用的记录行数，不是945唯一进程或测试数。历史未采实际worker出生值不追溯伪补，原completed/wait与当前缺席或后期PID复用事实分列；最终r2直接绑定实际base worker。全部TEMP/原日志/首败保留，未知用户进程未动。

文档独立D00、最后资源/INTEGRITY/封印是本批目录中另存的后追加delta，不冒称由早期产品候选或已执行门禁覆盖；最终整批manifest作为停止记录。六权威状态仅新增本批块，完整开工内容保持。下一动作只等用户新指示，不自动live、原待验分支或其他模块。
