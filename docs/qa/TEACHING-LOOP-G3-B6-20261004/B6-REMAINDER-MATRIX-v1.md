# B6 需求与剩余检查矩阵 v1

起点：2026-10-04 13:52 G3 已独立技术关闭，现行候选 G3-r2-qa5，main@6cb6a40。本矩阵先于三路 B6 新运行形成。B0～B5 既有业务与原任务保持，原 B6/B7 不据部分交付整体关闭。

来源：[G3关闭](G3-CLOSE-v1.md)、[原B5关闭矩阵](../TEACHING-LOOP-G2-B5-20261003/B5-CLOSE-MATRIX.md)、[后端410精确绑定](ctrl/G3-API-UNCHANGED-BINDING-v1.json)。表中“待新跑”不代表已通过，教师评价与替身技术运行分开。

| 需求 | 现行实现及原证据 | 本批实际剩余与责任 | 当前状态 |
| --- | --- | --- | --- |
| 固定成绩、ready报告、单班/KP | T60/T70四态与any_loss_v1、learning-analysis；原B4/B5固定JSON及真实8链路 | 用单班单KP走最小新完整链，显式score/run/class/KP修订绑定 / 集成 | 待新跑 |
| 后台教案及已确认教材/题/审核练习 | T90、lesson-plans、lesson-sources及生产RagV2；原42API、真实8 | 沿用既有创建、证据核验与真实Provider流水线，仅HTTP Transport替身；冻结全部来源映射 / 集成 | 待新跑，真实模型另列 |
| 五整字段选择与教师六字段 | 现有proposal原包终结、partial/Undo/历史；原8已查partial2/未选3/teacher6 | 增补五整字段全部选择的实际应用，新固定版本；六字段手写哨兵不变 / 集成 | 待新跑 |
| 练习回流与新成绩、新报告 | T80 reviewed练习→模板/原卷→施测→教师小题成绩→新ready报告，既有真实业务 | 新链实际完成，课堂字符串与正式练习对象分列，不引入AI改卷/概率 / 集成 | 待新跑 |
| 历史事实不可变 | 四库固定修订与source snapshots；原完整JSON不变 | 原成绩/报告/练习/教案历史完整JSON及SQL全列；变更题库/归档KP/改班名后旧body/context/label/map不变，新失效来源调用前拒绝/provider0 / 集成 | 待新跑 |
| 保存unknown/CAS/模型漂移/取消失权/原包 | 原独立42API、27组件、真实8及G3新2/15/8/27/14；后端410与旧成功运行精确绑定 | 无新增产品影响时精确引用，不机械重跑旧probe；若新增缺口或失败再单独补 / CTRL、集成 | 原同源引用 |
| 四库、Blob离线一致性恢复 | 原B5实际恢复proof及独立16只读库/全部行/2Blob；0010及旧迁移散列 | 无DDL/恢复代码改动，逐文件SHA绑定旧证据；Qdrant替身与SQLite/Blob真恢复明确分列 / CTRL | 待绑定；本批不重跑恢复 |
| 教材缓存措辞与相关性 | ImmutableSource已验证缓存可复用；scope/revision/classification/owner/deletion仍核；RAG-REL OPEN | 正例/边界/范围外/无依据案例分开；不宣称每次重读bytes，不以相似阈值关台账 / 质量 | RAG-REL保持OPEN |
| 匿名质量案例及手写oracle | 既有匿名白名单/provider指纹/promptVersion；旧替身文本仅技术证据 | ≥12固定匿名case/expected/输入与输出/选字段/结果SHA，统计重叠与零分母、综合题不臆造错因、5分钟及常用预算 / 质量 | 待准备与执行 |
| Rubric、逐例不足与feedback | 尚无本批教师教学评分 | ≥6维，硬失败与人审分开；CSV/MD可填；执行器拒绝缺profile/model/数量/预算的live调用 / 质量 | teacher_review_pending |
| 真实Provider教学质量 | 原技术流水线/三协议wire不等于真实模型质量 | 用户未给明确live范围，本批完成offline材料与review工具，冻结非敏感指纹/用量等记录字段 / 质量 | live_run待输入，不读正式.env |
| 四当前固定DOCX及打印/PDF | 既有docxtemplater/原模板、冻结printSnapshot；原4DOCX结构与4打印，实际PDF/WPS未验 | 短课、长正文+长secondary、多环节、中文特殊字符四新样本；正文/来源/模板/文件SHA、全字段/关系/字体/合并；实际PDF保存及逐页render若工具可用 / 导出 | 待新跑；Word/WPS人工另列 |
| 教师试用说明 | B0～B5已有全部所需业务 | 名单/原卷/成绩→单班学情→五字段→审核练习/导出→分数回流；四态、需巩固边界、local/backend/unknown/CAS/备份及模式文案观察 / 导出 | 待材料 |
| 工程/视觉/资源/原计划状态 | G3新完整check1281/原153/true14四视口与焦点/reduced-motion已验；全diff无shared shell/chat改动 | 无新产品代码不重复无关build/API/chat；有变更重新冻结受影响门禁；CV01～03/R14/环境观察保持。最后自有资源关闭/旧证据与文档后验 / CTRL | G3已关闭；限定B6进行中；原B7未关闭 |

正式6333、正式迁移、超既有范围压力不在本批运行；未执行写明原因。真实Word/WPS排版缺工具或人工时先交可打开样本和逐页清单，明确not_run。B6技术链通过、质量准备完成、live/teacher_review/实际排版各有独立结论。
