# B4-T70 v1.3 作者受影响复验 · ready / stopped

CTRL 指派：共享 paper_practice_confirm 补题号/ordinal/parent/正式题修订/知识点集合的一一冻结覆盖后，仅修本作者 lineage fixture 缺 question_revision_id 的种子写入。原 RESULT.md/SOURCE-MANIFEST.json/EVIDENCE-MANIFEST.json 和全部旧 ready/失败输出均原样保留，复验不是独立验收。

唯一区域变更是 apps/api/tests/test_analysis_lineage.py 一条 INSERT…SELECT：明确 JOIN 同 practice_revision 的 practice_selection 并复制真实 s.question_revision_id='question-r' 到 paper_items.question_revision_id。原 source 字节副本 lineage-v1.before.txt 匹配前 ready SHA；完整精确行差异/散列见 diff-v1.3.json。所有业务断言原字节行均相同，6产品Python、其余6测试Python、QA运行脚本均不改；未写任何共享/迁移/契约文件。

按原六 test 文件新标签 pytest-v1.3 单轮实际 **21 passed，exit0，pytest 8.87s，命令10116ms**。精确Python绝对exe/argv/cwd/env、stdout/stderr/PID/新temp、起止时间见 pytest-v1.3-receipt.json。stderr含预期故障注入警告和进程内HTTP/lifespan日志，不是外部服务监听。v1.3本轮无首败；历史首败未覆盖，也不将多轮计数相加。

200×100完整20k主体、100页每200真实 HTTP全遍历、所有 evidenceId/participant/item 笛卡尔积及 rich/material/assets仍通过。硬件同 hardware.json：i5-14600KF 14核20线程/Windows11/Python3.12.14。新测性能见 pytest-v1.3-performance.json：首调用aggregate9.86ms/第二调用9.74ms（3s门槛），seed208.43ms/read74.33ms/accept195.24ms/job计算+同txn封存609.41ms/100页+筛选4459.08ms；pure冷指此样本首调用，未声称冷OS缓存。

原 fixture→ready practice→confirmed practice paper→真实 conversion mappings→同固定卷后来新T30施测/成绩→T70 的三条 practiceRevisionId/itemId 与 originalQuestionRevisionIds 断言，均通过新迁移的一一来源 gate。相应全套取消/旧租约/失败回滚/immutable/replay/历史null/四态/explicit-attempt/notes/HTTP/全20k证据也在同一轮通过，没有改断言绕 gate。

新OS根 zqky-b4-analysis-pytest-v1.3-2830d157f0b648a798a2064da0258a7e 全保留；自有Python PID22992实际已退出，stdout/stderr均在退出后真实独占打开成功，证明本轮writer已释放（resources-v1.3.json）。任意间接app.main前已指定test/temp/UTF8/Qdrant16333/embedding127.0.0.1:9/空temp教材源/credentialsNone；HTTP用进程内 create_app fixture。无外部API/前端/监听启动，无未知/旧六目录清理，无Git写入。

SOURCE-MANIFEST-v1.3.json：仍14可执行源，唯一批准变更是上述fixtureSQL；EVIDENCE-MANIFEST-v1.3.json记录此轮新增原件及以前原件当前SHA，不改旧manifest。完整共享foundation另由CTRL复验。本作者 **ready，已经停止全部产品/测试/QA可执行源及证据写入，等待最终稳定候选独立验收**；B4总体门禁尚由CTRL继续。
