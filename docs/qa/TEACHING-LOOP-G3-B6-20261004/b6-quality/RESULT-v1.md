# B6 教学质量准备结果 v1

时间：2026-10-04T14:21:47.045319+08:00。**15匿名病例质量准备完成、离线结构技术PASS；教学质量仍teacher_review_pending，live_run待输入，RAG-REL OPEN。** 本卡停写等待独立审查，不关闭原B7，也不以替身内容评分。

现行运行基线为 CANDIDATE-B6-base-v1，SHA `c04c01bdd0dbedf85e7f0aba81d4ed92c8cad50ec5fea7d232ef896081e19ca1`；941源码、共享契约33、build q84e精确引用G3关闭后起点。本路所有实际命令前后source与base图相同、本路ownQA0漂移。后续SourcePanel产品改动需新冻结；本包属于原base，不能冒称未来构建上重跑。

## 样本与手写规则

输入和字面expected在业务调用前冻结；case-specs SHA `353e56e4f756403b8fb724b73613a2138d9d8a71ca460b3df6143e597497dd55`。prepare_cases.py不导入app/aggregate/provider，字面计数及逐学生状态表由独立QA按授权规则列举，未冒充真实教师提交或真人评价。每例expected.json及student-state-table.json保留；每个case-bound-v3.json固定run/score/paper/KP/教材/题修订全列SQL与canonical SHA、原件/normalized/source-map Blob SHA及输入→匿名wire→raw→候选→选择→结果→DOCX SHA。原case.json和expected不重写。

needs与incomplete可重叠，incomplete与noEvidence可重叠；分母仅为有recorded的被选唯一学生。C04/C15分母0均ratio=null，C07显式只选同学生第二人次。综合题只给关联提示；历史className=null和缺班名说明，当前classNameAtSave没有补成历史事实。

教材为旧只读隔离QA中自写有理数片段/题目，不复制正式教材或学生档案。C10正例、C11第一句窄边界、C12范围外、C13缺请求证明依据分别列示；C15学生noEvidenceCount另列。ImmutableSource可复用已核缓存，本包不声称每次生成都重读磁盘bytes；后验只读Blob核验不等于新检索拒答验收。

| 案例 | 人工字面目标计数 selected/valid/needs/incomplete/noEvidence/full/num/den/ratio | 单例不足 |
| --- | --- | --- |
| C01 单知识点失分 | 1/1/1/0/0/0/1/1/1.0 | 仅一个匿名样本，不能外推长期能力或班级总体结论。 |
| C02 有效零分 | 1/1/1/0/0/0/1/1/1.0 | 有效0需课堂诊断，零分本身不揭示具体错因。 |
| C03 失分与缺失并存 | 1/1/1/1/0/0/1/1/1.0 | 失分与信息不全重叠；必须补齐缺失资料，不能加为两人。 |
| C04 全部缺考免考 | 2/0/0/2/2/0/0/0/null | 两名均无recorded，分母0/null，不能给教学能力标签。 |
| C05 多知识点综合题 | 1/1/1/0/0/0/1/1/1.0；1/1/1/0/0/0/1/1/1.0 | 综合题关联两KP，不能判断是哪一步失误。 |
| C06 多班报告明确单班 | 1/1/1/0/0/0/1/1/1.0 | 报告两班但生成仅目标班；不能外推另一班。 |
| C07 同学生显式选择第二人次 | 1/1/0/0/0/1/0/1/0.0 | 显式第二人次，不能自动取最高分或累计两学生。 |
| C08 历史成绩未记录班名 | 1/1/1/0/0/0/1/1/1.0 | 历史班名缺失，不能从当前班名补写固定事实。 |
| C09 题库覆盖缺口 | 1/1/1/0/0/0/1/1/1.0 | 真实suggestions selected0/gaps2；未新建或审核正式题。 |
| C10 教材正例常用课时 | 1/1/1/0/0/0/1/1/1.0 | 自写正面片段只验证材料链；真实模型相关性和教学效果待人审。 |
| C11 教材边界与五分钟 | 1/1/1/0/0/0/1/1/1.0 | 首句窄边界不支持运算律证明，5分钟活动可实施性待教师确认。 |
| C12 教材范围外主题 | 1/1/1/0/0/0/1/1/1.0 | 范围外主题仅有结构合法引用；本包不证明真实检索或模型拒答。 |
| C13 教材没有所请求依据 | 1/1/1/0/0/0/1/1/1.0 | 加法片段无乘法分配律证明；不能把引用存在当论断有依据。 |
| C14 部分字段与教师六字段保持 | 1/1/1/0/0/0/1/1/1.0 | 整个process含secondary被选择替换；教师六字段和未选三字段保持，课堂可行性待人审。 |
| C15 缺失与无证据重叠 | 1/0/0/1/1/0/0/0/null | 同一人missing同时incomplete/noEvidence，不能按互斥人数相加。 |

## 实际执行与首败

完整新TEMP单轮15例：offline-third command PID24716、9005.51ms exit0；实际Python workload PID24108、7884.848ms。Windows venv启动器PID与工作进程PID分别记录。保留数据根 `C:\Users\96022\AppData\Local\Temp\zqky-b5-b6-quality-offline-third-nfyoaa05\data`，main导入前env=test/PYTHONUTF8；Settings.credentials_file=None。真实标准create_app/four catalogs/固定分析/模型profile resolver/fingerprint/匿名白名单/Provider序列化/六态JobEngine/应用与固定修订均实际执行，**只有Provider上游HTTP transport与手写回复替身**。TestClient日志的8001请求为进程内ASGI transport，无TCP监听，也无正式环境、外部调用或模型下载。

每例15次合法Provider transport调用；每例字面8计数与ratio吻合，目标单班/所选KP进入wire，已知匿名样本身份未进入wire，五字段或partial应用及教师六字段/未选字段逐项保全。C09真实建议selected0、两个缺口文本，候选exercises不是新建已审核题。原固定score/report前后相同。结构PASS不评价替身教学内容。

docx-marker-first使用bundledNode24 PID17588、49.499ms exit0，expected15/docx，**仅成功运行一次**；seed辅助原卷/练习导出属隔离fixture过程。实际15固定教案buildDocx导出 PID20368、281.407ms exit0，模板和export.ts散列完整冻结。readonly bindings第三版 PID14760、196.952ms exit0，全15 ZIP CRC/XML正文11字段投影/全process文本/内部rels及课型勾选均已核。没有称15份DOCX渲染通过；四样本PDF和排版由导出lane另验。

首轮offline-first PID24944 exit1是QA错误关闭标准catalog装配；第二轮PID26480 exit1是QA施测快照字段映射错误。原源码v1/v2、日志、首败JSON、TEMP均保留，v3修QA，产品与字面expected不改。第三版15一次完整通过，未拼早先结果。后验首轮误将完整normalizedTextSha256当所选slice SHA，在窄边界处失败；已保留前十部分绑定，第二轮防覆写闸门拒绝覆盖。新v3生成全十五新绑定一次通过。正确语义是完整规范化文档SHA与selectedSliceSHA分列，没有教材产品缺陷结论。

## 真实模型和真人评审

live-missing-scope-first PID10948、71.844ms按设计exit2：缺modelProfileId、model、明确case数量和token/费用上限时拒绝，没有HTTP、main导入或正式.env读取。review_tool.py只做离线范围审查，合法范围仍由CTRL通过现有Provider执行；不另起prompt管道、不切默认模型。真实profile/模型/样本数/预算未提供，本批live_run待输入。metadata每例保留非敏感fingerprint、实际SYSTEM_PROMPT SHA版本、caseHash、duration、usage/failure/raw。usage token值null是未执行真实模型/替身没有实际计费信息，不捏造数值。

RUBRIC.md提供8维0～3真人量规，先单列来源/分母/虚假引用/非法字段/分钟/身份/自动发布硬失败，再由教师解释学情、依据相关性、KP覆盖、活动检测、可实施性和控制保持。feedback-offline-third.csv/md共15例，reviewer、日期、全部分数和真人结论为空。替身不能自评，JSON正确不能给教师教学质量PASS。

## 文件入口与STOP

- [最小执行与评审说明](README.md)、[量规](RUBRIC.md)、[手写规则](EXPECTED-RULES.md)。
- [逐例汇总](RESULTS-offline-third-v1.json)、[病例目录](runs/offline-third/quality-cases/)、[反馈CSV](feedback-offline-third.csv)、[反馈MD](feedback-offline-third.md)。
- [15实际DOCX文件SHA清单](exports/offline-third/DOCX-MANIFEST.json)，只属于结构级QA中间材料。

**作者STOP。** 仅新增本路QA/材料，产品、其它lane、旧QA与权威文档未写；无Git、TCP服务或外部调用。质量准备待独立复核，真人、live、Word/WPS、RAG相关性、正式迁移/压力结论均单独保留。
