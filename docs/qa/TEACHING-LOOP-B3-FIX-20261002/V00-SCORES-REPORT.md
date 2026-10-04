# V00-SCORES 独立验收（r3通过，后续只读一致性追加）

**结论：本子任务负责的 T60 成绩、出勤/刷新、固定原卷身份、教学迁移散列与题库富内容后端验收通过。最终冻结 r3 的165项在验收前后均165/165一致，0漂移；自行构建的47项成绩与24项富内容探针合计71 passed、1 warning，exit0，21.36s。三类独立发现的阻塞问题均已由总控修复，并通过原正确行为断言。**

冻结件 `FROZEN-CANDIDATE-r3.json`；证据 `V00-SCORES-probes/hashes-r3-before.json`、`hashes-r3-after.json`、`logs/v00-scores-final-r3.txt`。本报告支持限定范围的独立验收，不代替总控全量检查、浏览器/视觉或V00-G0的迁移/公共任务结论。

负责人 `/root/v00_scores`，没有参与实现。仅新增本报告、V00-SCORES-probes 和 v00-scores 日志；没有产品、契约、原测试、权威文档或 Git 写入，没有监听端口、构建或全量 npm 命令。

初始读取实际为 r2（158/158 字节散列一致），副本 `V00-SCORES-probes/frozen-reviewed-r2.json`，首次核对 `hashes-before.json`。根 Agent 收到下列三类阻塞缺陷后暂停该候选定版，自行修复并另冻结r3；验收者始终未修改产品。r3的变化边界另经源代码复核：Decimal仅用精确tuple/界限检查；PATCH读阶段与提交短事务复核冻结context；重复行问题进入真实RowMatch/阻断清单。确认保留服务端四态/承认闸门和不可变矩阵。

## 独立首败：正确行为断言

| 编号 | 实证 | 根因 | 首败证据 |
| --- | --- | --- | --- |
| V00-S01 | CSV C2=`1e9999999` 返回500；`1e-9999999`和超28位有效尾数返回201，可推导0或丢失小数；必须定位422且零批次/正式写入 | Decimal 默认 context 乘100产生 overflow、underflow、rounding | `logs/v00-scores-numeric-first.txt` exit1，4 failed；`numeric-first-http.json` |
| V00-S02 | 新补考人次后 PATCH 0分直接返回200并改变预览范围；预览计算后确定性交错校正出勤，PATCH仍返回200并增加批次锁 | PATCH 缺少原预览上下文检查与提交短事务施测/active/base CAS | `logs/v00-scores-patch-context-first.txt` exit1，2 failed；`patch-context-first-http.json` |
| V00-S03 | 同一真实人次的两物理行(1,2,3)/(2,3,5)确认200，正式矩阵只有第一行分数，第二行被静默丢弃；手工把两行指定同一人次同样可确认 | `issues_by_row`累计重复行冲突，却没有进入返回的 RowMatch/阻断清单 | `logs/v00-scores-duplicate-first.txt` exit1，1 failed；`duplicate-first-http.json`含最终错误矩阵 |

未修改上述断言迎合现状。有限超满分数的错误分类按稳定契约为 SCORE_CELL_OVER_MAX；极小非零和多于百分精度的小数为 SCORE_CELL_INVALID。有效尾随零和精确`1e-2`仍必须得到123和1单位。

## 已完成的独立范围

- T60 真 HTTP、真实临时四库、受管 XLSX/CSV和真实成绩服务。仅前置已确认三叶原卷复用 ScoresHarness 的迁移后 SQL 固定种子；不是业务成功替身。
- 五人次×三叶全矩阵：recorded(0)、缺考、免考、真正 missing、缺行完整覆盖，逐类服务端权威承认，精确 Decimal 总分，固定 paperRevisionId。
- C/c及身份/分数/总分/出勤占列、未知/GB18030身份人工映射、同工作表物理表头重提取和修正坐标保留、前导零、原件/校正/有效格证据。
- full matrix seal 后注入失败整体回滚；同键重放先于 stale versions；同键不同输入冲突；同键并发只产生一个事实；双导入不同键竞争只保留赢家。
- recorded空白/缺考/免考修正定位422零写入；有效0修正建立完整新版本，新增补考人次显式 missing，旧 JSON/全矩阵不变，固定原卷身份、修正审计和 alias 路由可读。
- 参测出勤修改只有 attendance列，审计同事务；bump 后故障回滚和同键重放；GET过期承认范围保持；refresh明确独立校验import/assessment/base且保留修正。
- 公式无缓存定位422；真实缓存视图125单位且保留`=1+0.25`原文本和受管原件散列；同名/多个人次不自动猜；物理行/列/人次归属及分页bounds。
- 跨施测active指针、draft active指针均被真实 DB 外键/confirmed触发器阻断；PRAGMA foreign_key_check为空，integrity_check全部返回ok。

前27例有界独立链：`logs/v00-scores-other-first.txt`，27 passed/4 deselected/1 warning，exit0，8.61s。扩充首次12例：11 passed/1 failed，失败为 V00-S03，日志 `v00-scores-expanded-first.txt`。最终完整47例全部通过，另含重复身份表头进入手工恢复、active/base漂移不可通过refresh换base。

## 题库富内容独立验证

`test_rich_independent.py`由验收者自行构造结构化内容、真实 PNG 字节、合并表格、共享材料和OMML。先行17例：`logs/v00-scores-rich-r1.txt`，17 passed/1 warning，exit0，4.97s；再增加7例，最终24例全部通过。

核实三种 managed/legacy存储适配、字节SHA/魔数/媒体类型、当前引用/owner限制；富内容权威与四个Markdown域的冲突定位；显式null转换保留旧修订JSON和blob；仅改共享材料/跨度/图片尺寸改变derived-v1且不改旧指纹；受管文件损坏不从兼容副本回退；确认缺字节零题/零submission、同键重放不读文件；预检文件IO在SQL写事务/PublicationCoordinator之外；预检后草稿revision变化不发布。

追加实证：4种非法资产键在文件IO前拒绝；真实却未被当前内容引用的资产在IO前404；富内容拆分与接受AI建议返回定位到content.richContent的422，拒绝建议不改内容/revision。该AI应用边界使用Harness明确注入的inline organizer与受控Provider，确实调用Provider1次；其200 succeeded行为不冒充公共JobEngine的202 queued创建/公共retry链，后者由总控/G0真实引擎夹具验收。

首轮3失败14通过是独立探针把catalog内部snake_case当HTTP camelCase读取。改为用实际GET JSON作为新修订输入，未改产品、验证要求或派生指纹。首轮日志保留 `logs/v00-scores-rich-first.txt`。追加7例首轮6通过1失败，是上述inline Harness状态码误假设202；根据已读实际装配改为严格断言200 succeeded/1次Provider调用，再验证富内容apply闸门，没有修改产品。首败保留 `logs/v00-scores-rich-expanded.txt`，窄复验 `v00-scores-rich-ai-r1.txt`为1 passed，exit0。

## 迁移与边界

`migration-hashes.json`：HEAD保持6aeb57280f6a7e0d7391cad4d150745479ea58ec，教学0001–0007的7个注册散列逐一与HEAD声明相同；教学迁移、base、runner文件仅工作树CRLF/仓库LF差异，规范化后逐字节相同。现有固定原卷关系和矩阵复合FK可导出paperRevisionId，无新增迁移需求。

真实已填B2数据、多班/多人次保留、0007复制/换表/恢复trigger/FK/integrity所有结果/回滚可重跑等由独立V00-G0负责，避免交叉重复宣称。

所有独立脚本在任何 app.main导入前设置绝对OS临时ZQKY_DATA_DIR与ENV=test，Harness显式临时设置与测试内存凭证；没有读取正式.env/正式库，没有真实供应商/Qdrant请求。后续pytest使用独占basetemp；删除测试临时目录前检查resolve为OS temp直接子目录及精确独占名称，使用同一Python流程。Bootstrap和本进程tests.conftest临时目录在会话fixture中关闭；5个独占basetemp已经边界核查并删除，其中最终3目录核查结果见`temp-cleanup.json`。早期默认pytest保留目录遵循pytest保留机制，没有为了清理而遍历删除共享pytest会话。所有TestClient已关闭，无监听端口，没有结束其他进程。

未执行：根全量check/API/e2e、200×100重跑、真实浏览器/视觉、正式数据迁移、真实供应商质量、Word/WPS、Qdrant（总控/其他独立验收负责或不属本子任务）。此报告不以窄测试代替这些检查。

## 命令

共同设置：`PYTHONIOENCODING=utf-8`；`PYTHONPATH=<workspace>/apps/api`。解释器`apps/api/.venv/Scripts/python.exe`，pytest路径`docs/qa/TEACHING-LOOP-B3-FIX-20261002/V00-SCORES-probes/<file>`，均`-o addopts= -q --tb=short --show-capture=no`。

1. score文件`-k decimal_context` → exit1，4 failed。
2. score文件`-k 'not decimal_context'` → exit0，27 passed。
3. score文件`-k 'patch_stale_context or patch_rechecks_context'` → exit1，2 failed。
4. score文件`-k 'formula_cache or same_name or retake_not or physical_patch or page_bounds or confirmed_gate'` → exit1，11 passed/1 failed。
5. score文件`-k actual_duplicate_physical` → exit1，1 failed。
6. rich文件全体 `--basetemp C:/Users/96022/AppData/Local/Temp/zqky-v00-rich-20261002-1342` → exit1，14 passed/3探针观察错误。
7. rich文件全体 `--basetemp C:/Users/96022/AppData/Local/Temp/zqky-v00-rich-20261002-1343` → exit0，17 passed。上述两目录经边界核查后已删除。
8. rich文件追加`-k 'arbitrary_asset or unreferenced_real or rich_split or rich_ai'`、独占1354 basetemp → exit1，6 passed/1 Harness状态码假设失败；修正后`-k rich_ai`、1355 basetemp → exit0，1 passed。
9. **最终：同一命令同时指定`test_score_independent.py test_rich_independent.py`，独占`--basetemp C:/Users/96022/AppData/Local/Temp/zqky-v00-score-rich-final-r3` → exit0，71 passed/1 warning，21.36s。** 唯一warning是既有Starlette TestClient的anyio BlockingPortal弃用提示。

验收完毕，停止写入。若总控改变被冻结产品或契约，需按新候选重新复核相应范围。

## r4最终一致性追加（V00-SCORE-FINAL v2）

本节保留r3实际执行的71项独立探针结论；没有重复运行产品测试。r4冻结167项，核对前167/167匹配，核对后165/167匹配，实际有两项E2E测试变化：`tests/e2e/assessments.spec.ts`和`question-bank-real.spec.ts`。原核对结果分别保存于`V00-SCORES-probes/hashes-r4-before.json`和`hashes-r4-after.json`，未将漂移改称零。总控确认这是浏览器首败后的受控spec修正，并另冻结r5；不是成绩/富内容产品、契约或迁移变化。

r3→r4只有三项Python测试差异：`test_jobs_engine.py`改变租约fixture的推进方式；`test_rag_sessions.py`将TTL行为绑定独立任务钟；`test_scores_confirm.py`严格采用已公开的显式refresh流程。前两项由总控/G0相关验收负责。新增到r4 manifest的两个既有测试文件并非新增业务模块；其余r3已冻结文件散列原样保留，没有产品/契约/迁移变更。

已只读审阅`test_participant_added_after_preview_requires_refresh`实际修改：

1. 新增补考后旧confirm严格409 SCORE_ASSESSMENT_REVISION_CONFLICT，删除原先409/422二选一断言。
2. 有效旧context PATCH严格409，比较真实score_imports/score_import_rows验证零修改；保留空补丁422。
3. 明确POST `/score-imports/{id}/refresh`携带旧import revision、新assessment revision、原base，成功后revision和previewVersion各增加1。
4. 使用fresh revision将物理row2指定原人次，随后按当前assessment revision、精确新人次missing3承认确认；原人次仍为200/300/500，新人次三叶都是missing。

这修正的是旧测试把PATCH当隐式refresh的过期口径，与独立V00-S02所关闭的边界一致，未放宽承认或CAS。该测试没有事先封存旧正式版本，因而没有假称覆盖历史版本不变；后者仍由r3独立完整修正/补考链及既有专属刷新回归证明。refresh后尚未人工消歧的两个attempt可能产生6个missing，测试只在明确指定原人次后断言3个，符合实际身份规则。

只读核验总控完整API日志`logs/root-api-final-r4.txt`和实际JUnit`root-api-final-r4.xml`：1523 passed、1 warning、exit0，207.40s；XML tests=1523、failures/errors/skipped=0，包含上述refresh测试，耗时0.653s，结构化核验另存`root-api-r4-verified.json`。`root-check-r3.txt`记录108个文件/1069项前端单测与后续生产构建完成；不把这当成本验收者重新执行的检查。

再次执行纯迁移声明散列读取，没有导入app.main或启动lifespan：`migration-hashes-r4.json`确认0001–0007的7个注册SHA全部与6aeb57280f6a7e0d7391cad4d150745479ea58ec基线相同；teaching/base/runner文件依旧仅LF/CRLF编码差异，规范化后内容相同。固定paperRevisionId可从不可变施测关系/矩阵FK读取，仍无新增迁移需求。

范围结论：r4成绩/富内容后端及迁移散列保持一致，没有本范围剩余阻塞；r4整体manifest因上述两项spec变化不能宣称验收后全部一致。真实浏览器/规模/视觉与完整E2E仍由总控完成并在最终证据中登记，本追加不提前宣称其通过。

## r5范围继承核对

总控另存`FROZEN-CANDIDATE-r5.json`，没有覆盖r4原件。r4→r5 delta恰好上述两个E2E spec，所有产品、Python测试、迁移与构建配置散列不变。`hashes-r5-before.json`与`hashes-r5-after.json`在本次只读追加前后各167/167一致，0漂移。因此本报告的r3成绩47项/富内容24项独立实测、r4显式refresh测试口径与API1523项证据可继承到r5；没有重复运行未变化产品测试。

两个spec调整由总控登记真实浏览器首败后修正：名单/DOCX上传改经已配置8001的真实Next同源代理，以保留磁盘File字节；题库遵循内容修改回到needs_review的既定规则，先保存原稿，再单独标已校对并严格验证PATCH收据。该浏览器重跑仍由总控负责，本范围核对不提前写入通过结论。

本子任务最终状态：r5后端范围继承验收通过，没有未关闭的成绩或富内容后端阻塞；停止写入。
