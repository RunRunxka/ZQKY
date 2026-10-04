# G3／限定B6 后续代码审查

2026-10-04，北京时间。用户请求“review代码，给出下一批”。现场main@6cb6a40db890390f0261d547213e319040f64785，审查对象为[限定B6候选](../TEACHING-LOOP-G3-B6-20261004/CANDIDATE-B6-r1.json)的实际字节。本轮只读产品，新增隔离窄探针、材料核查和下一批文档；未修产品、运行G4/B7-A、启动服务/浏览器、调用模型、Git写入或部署。

## 结论

确认 **4项P2：2项B5继承产品问题、2项质量工具缺口**。没有确认G3两项修复或B6 metadata/report-owner修复新引入回归。旧G3及限定B6关闭保持，不追改原收据或首败；原计划B6/B7整体、真实模型/教师评价/Word-WPS与RAG-REL的待验边界保持。

建议下一执行批 **G4四项修复及独立验收 → B7-A质量工具与有限试评接入**。已有15匿名案例、四DOCX和13页实际PDF继续引用，不重新搭建业务模块或重复生成同一准备包。提示词见[下一批正文](../../design/teaching-loop-v1/B7_总控启动提示词_20261004.md)。

## B6F-R01／P2：恢复缓存写失败后缺少公开重试入口

主位置：[ServerControls.tsx:17](../../../apps/web/src/features/lesson-plan/components/ServerControls.tsx:17)；关联[EditorContext.tsx:57](../../../apps/web/src/features/lesson-plan/model/EditorContext.tsx:57)、[LeaveProtection.tsx:48](../../../apps/web/src/features/lesson-plan/components/LeaveProtection.tsx:48)。

有效后台教案会话中setItem暂时失败一次，会设cache_error，正文被锁、保存按钮禁用、离开对话框save/keep/discard全部禁用。恢复Storage并公开读取相同最新后台版本后仍未解锁，教师没有直接恢复入口。同条件下调用已有hook.save却能先写完整恢复包再发送一次保存，说明底层可恢复能力和公开UI不一致。

实际LessonPlanWorkspace正确行为案例失败；配对直接save对照通过，实际公开JSON正文备份也通过，全部11字段与内存新稿相同。**输入仍在内存且正文JSON可导出，不称永久丢失；正文JSON不是context/unknown完整原操作恢复包。** 间接改变来源或另建副本等绕行不替代直接重试。

三个关联文件与B5旧冻结源SHA相同，为本次新发现的沿用问题。修复须区分坏缓存读取blocked和有效会话写失败，公开重试先保存当前完整恢复包；不能统一解除cache_error、覆盖坏字节、清unknown操作或跳过CAS。

证据：[编辑报告](edit/REVIEW.md)、[正确行为首败](edit/cache-retry-qa2.log)、[最终3例含备份](edit/cache-retry-with-backup-qa3.log)、[精确旧源归属](edit/prior-same-source.json)。本轮为jsdom及隔离Storage，不冒称真实浏览器新跑。

## B6F-R02／P2：显式清除在途教材核验后旧证据复活

位置：[SourcePanel.tsx:139](../../../apps/web/src/features/lesson-plan/components/SourcePanel.tsx:139)，采用条件在112/124行。

首次evidence为null，教师点核验；verify响应在途时点“清除已选教材切片”，仍只是changeInputs(evidence:null)，不撤销读取owner。清除前后selection/value签名相同，旧核验返回后重新采用已取消教材。其他前提有效时，ProposalPanel会将这份scope/evidenceRefs纳入下一生成包；后台不能从有效证据判断教师曾取消它。

真实SourcePanel组件独立正确行为首败；精确B5r8同源组件亦复现，为沿用问题。年级、跨document/store/session、教师要求变化三个当前守卫通过，B6五项作者回归也通过；这项不否定B6 loading/pending-report改进。

修复显式核验意图代次，清除即使null→null也撤销旧读取；在getSource与verify两个await后核同一活跃意图/会话。保留metadata与source独立所有权，清除后新核验正常采用。

证据：[来源报告](sources/REVIEW.md)、[当前完整首败](sources/run-r1.log)、[完整JSON](sources/run-r1.json)。在途改下一段参数或更换教材也能采用最初提交片段，但“改待添加参数是否撤销已发核验”语义尚未约定，本轮仅观察，**不把另外两项强假设失败列为已确认缺陷**。

## B6Q-R01／P2：质量汇总漏一例仍宣称PASS15

位置：[finalize_review_v3.py:106](../TEACHING-LOOP-G3-B6-20261004/b6-quality/finalize_review_v3.py:106)，输入遍历46行。

工具只遍历SUMMARY.results，未先校验冻结预期集合完整性，汇总却硬编码caseCount15、technicalStructure=PASS15、docxStructure=PASS15。新目录中仅删原C15 result，保持其余14真实原件，用字节相同脚本及stdlib只读四库核对，成功返回14条results和PASS15；stdout同时caseCount14/docxStructurePassed15。

这是未来重复使用工具的失败闭合缺口。**原offline-third全部15例另经完整独立核查，本次也核15材料通过，不推翻旧准备关闭。** 不能仅把15替换为len(results)：应以冻结manifest与显式scope核唯一ID全集/子集，缺/额外/重复即失败，实际计数由检查生成。

证据：[质量报告](quality/REVIEW.md)、[14例反证](quality/FINALIZER-COUNTEREXAMPLE.json)、[字节相同复制运行器](quality/proof_finalizer.py)。原样本库/旧结果只读，新汇总仅写本审查目录。

## B6Q-R02／P2：非法live范围预检给出READY

位置：[review_tool.py:15](../TEACHING-LOOP-G3-B6-20261004/b6-quality/review_tool.py:15)。

字符串caseIds、重复/未知ID、bool样本数、对象profile，以及没有token上限的NaN/Infinity费用，七种非法输入均直接exit0/READY。原校验依赖真值和len；Python bool等于1、NaN<=0为false，无法证明类型/预算范围有效。正确形状对照exit0，缺输入对照exit2。

工具只有离线预审，**没有live执行器、没有真实调用、没有收费越权**；问题是错误的范围就绪信号。下一批新工具严格JSON/根对象/字符串/唯一已知案例数组/非bool正整数样本数/有限正预算；真实执行另核模型身份与预算，不能把一次READY当授权。

证据：[AUDIT及9个输入](quality/AUDIT.json)、[新范围原件](quality/scopes/)。每次network/main/env皆0，不重试原被拒额外HTTP身份核查。

## 实跑与边界

| 本轮检查 | 实际结果 | 说明 |
| --- | --- | --- |
| 六个既有编辑/G3/操作文件 | 137/137，新单轮 | [编辑报告](edit/REVIEW.md)，原两项本次未复现 |
| 原G3全字段边界 | 5/5，新单轮 | 当前恢复/body/context/隐式写入口/高CAS等 |
| 新缓存公开重试及对照/备份 | 1fail/2pass，完整3例 | 正确行为仍失败；两个对照不抵消它 |
| B6来源作者文件 | 5/5 | metadata迟交/pending-report/discard等 |
| 来源四项明确行为 | 3pass/1fail | 另两参数观察失败仍在原完整日志，不当产品缺陷 |
| 原15材料独立离线核查 | 15例重算/匿名wire/SHA/字段保持/DOCX CRC及收据evidence通过 | [AUDIT](quality/AUDIT.json)，不是重跑15生产API或真实模型 |
| 工具反证 | 14被标PASS15；7非法范围被READY | 均无live；仅表示已证明缺口，不是修复通过 |
| 开工/收尾保全 | 942/3464/33/2161/1056各组、11087历史QA逐字节检查 | [BASELINE](BASELINE.json)、[FINAL](FINAL-VERIFICATION.json)；六份现行文档delta单列 |

缓存和B5来源复制探针初轮各有React/JSX准备错误，原日志和源码保留，修本轮QA后才使用实际业务断言；质量stdlib审查首轮Windows stdout编码失败，显式UTF8后成功。首败不删、不拼绿、不把QA准备错误当产品缺陷。

**本轮未执行**：全量check/type/lint/build/API/E2E、真实浏览器、真实模型/教师评价、Word-WPS原生排版、PDF重做、Qdrant/正式迁移/额外压力。产品未改，已有1286/153/14及13PDF页等按原批精确引用，不能写成本轮新跑。后端/DDL/恢复/导出代码相对B5候选字节未变，不机械重跑无关后端全量。

被拒额外HTTP身份核查未重试，未启动监听服务、管理用户进程或打开用户编辑会话。原G3/B6收据、v2原任务/伪代码与旧QA保持。本轮仅权威进度/接手/索引说明后续审查，原字节快照见authority-before。

## 下一批

[G4→B7-A总控提示词](../../design/teaching-loop-v1/B7_总控启动提示词_20261004.md)已写到四项伪代码、可写边界、负例与真实浏览器验收，以及明确模型范围后的C10～C13有限试评。真实模型、真人评价和Word/WPS结果各自分栏；缺输入时先完成四项修复与离线工具，不伪造质量通过，不自动关闭原计划B6/B7或RAG-REL。
