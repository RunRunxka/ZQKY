# G4-Q v2 作者结果：停止写入，待独立验收

2026-10-05。任务为B6Q-R01/R02新可复用离线工具，不修改原脚本、原15输出、expected、后端产品、契约、依赖或正式API。最终工具字节及证据清单见[结果JSON](RESULT-v1.json)；本卡没有关闭G4或释放B7-A。

当前完整作者单轮为[author-r4](author-r4-command.json)，PID21068、4133.811ms、exit0，**52/52**。三个工具与专属测试前后SHA零漂移；原quality的324份文件逐字节零漂移。物理TEMP四库sqlite在本次开工检查时均不存在，前后仍不存在，原因未知；不据父目录存在称文件保留或本轮源库通过。

| 行为 | 本单轮实际结果 |
| --- | --- |
| 原15全集少C15 | 非0；可见CASE_SET_MISMATCH含missing C15，没有PASS发布 |
| 重复结果、额外未知/未选已知ID、缺/重复DOCX manifest记录 | 均非0；先核精确集合，不以len(results)冒充完成 |
| 缺result/DOCX实际文件、SHA不符、错误源根、坏ZIP | 均失败；坏ZIP另以一致SHA的新矛盾输入直验结构，仍BAD_ZIP |
| 已冻结来源记录canonical错、固定源行ID错、缺完整行 | 均非0；构造新矛盾SHA索引不生成expected，不能靠散列存在通过源身份核验 |
| 正确15全集材料 | PID20268、exit0；15技术结构/15实际DOCX结构；未选列表为空 |
| 明确14案例范围 | PID4440、exit0；14/14，C15单列unrun；没有将C15写成通过 |
| 显式readonly-catalogs模式 | PID16844、exit2；旧sqlite缺失拒绝，不迁移或重建旧TEMP |
| 七种原非法scope及空白/错误类型/预算/attempt/非JSON/重复键/secret/未知字段 | 均非0，字段定位；不存在模型执行器 |
| 正确全集/子集scope、明确maxAttempts=2形状 | 仅SCOPE_PREFLIGHT_PASSED_FOR_HUMAN_REVIEW_ONLY；模型未验证、预算未执行、无授权生成；maxAttempts改变scope hash，额外尝试仍须明确人类授权 |
| 输出重复label | 非0，第一份RESULT的SHA保持；不覆盖首败 |

三份工具是[common.py](../../../../scripts/teaching-quality/common.py)、[scope_preflight.py](../../../../scripts/teaching-quality/scope_preflight.py)、[aggregate_review.py](../../../../scripts/teaching-quality/aggregate_review.py)，测试为[test_quality_tools.py](../../../../scripts/teaching-quality/tests/test_quality_tools.py)。所有路径/manifest/SHA/集合/输出label显式输入；工具不依赖历史QA脚本、不导入app.main，不联网或读取.env。聚合读取手写case-specs SHA353e56…和用户冻结候选f79ac…的artifact SHA；逐项核原case/expected/input/frozen/wire/raw/candidate/选字段/applied/export，完整11字段/process/secondary、teacher6与未选字段、固定context/修订/sourceLabel、匿名白名单及已知身份、精确四阶段分钟和全部目标KP依据别名。

[双模式v2解释](G4-Q-v2.md)由ROOT明确：本单轮正例使用frozen-source-binding，核case-bound-v3精确冻结SHA、全列canonicalSHA、固定ID及外键/矩阵与冻结输入关联、Blob散列证明，输出physicalSourceCheck=not_run_source_temp_unavailable。它是新材料核查，**没有本轮四库或Blob物理读取**。原物理证明只引用[旧独立审查](../../TEACHING-LOOP-G3-B6-20261004/b6-exports/review-quality/RESULT-v1.md)，不重写原收据；readonly-catalogs要求显式隔离TEMP并且缺文件硬失败。未来真实执行必须另核当前真实源、scope/hash、resolver模型指纹及可执行总预算，不能只相信READY字符串。

首轮[author-r1](author-r1.log)保留：PID20896、373.984ms、exit5、0测试setup error，因旧sqlite不存在。r2为43/43；补充行为反证后r3为52/52；补强来源行关联后r4新完整52/52，验收只引用当前r4，不拼不同轮片段。一次apply_patch外层JavaScript引号语法错误在执行前终止，未写文件；工具结果原件仍在会话，后续正确patch再全轮执行。

独立重跑用新不存在的目录：

~~~powershell
$env:PYTHONUTF8='1'
$env:PYTHONIOENCODING='utf-8'
$env:AUTHOR_RUN_DIR='<新的绝对证据目录>'
python -B -m unittest discover -s scripts/teaching-quality/tests -v
~~~

Python应使用仓库可用3.12或bundled运行时。若原15冻结材料不存在必须失败，不重建或从结果反填expected。每个真实CLI命令/PID/退出码/耗时/前后SHA及失败RESULT在runs/author-r4逐项保存。

未执行：真实模型（用户本批明确仅离线）、真人教师评分、Word/WPS原生排版、全量后端/恢复/Qdrant、正式数据/部署/Git；不属于本卡的新工程或浏览器门禁由ROOT另管。live0、teacher_review_pending、native not_run、RAG-REL OPEN。没有服务或浏览器进程；所有CLI子进程与日志句柄关闭，测试TEMP保留。工具、测试及本卡全部证据STOP，等待独立V00。
