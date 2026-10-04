# B6 质量准备独立验收 v1

更新时间：2026-10-04T14:44:48.839735+08:00。责任人 g3_v00，未参与质量样例作者工作。**质量准备与技术结构独立签收；真人教学质量仍 teacher_review_pending，live_run待输入，RAG-REL OPEN。** 本卡STOP。

独立完整离线审计 PID22064，171.391ms，exit0：全15例同一新审计轮完成，183条实际只读四库来源SQL全列比对、教材原件/完整normalized/source-map Blob与选中slice散列、原expected及输入→wire→raw→候选→字段选择→固定正文→15DOCX散列核对；作者目录318文件本轮前后0差异。审计不导入app、不启TCP、不调用模型，四个数据库只读句柄均关闭。

## 手写规则和逐学生事实

预写case-specs SHA `353e56e4f756403b8fb724b73613a2138d9d8a71ca460b3df6143e597497dd55`。prepare_cases.py仅导入pathlib/copy/json，LOSS/FULL/GAPS及特殊表为字面手写；业务执行脚本在每例API之前保存expected与student-state-table，没有用生产aggregate或候选反填oracle。本人从这些独立手写原始状态重新按唯一alias、明确attempt、目标单班、计分叶和KP关联逐人核算，不调用生产聚合。

| 案例 | 独立 selected/valid/needs/incomplete/noEvidence/den/ratio（每KP） | 结构事实 | 教学质量 |
| --- | --- | --- | --- |
| C01 | 1/1/1/0/0/1/1.0 | actualpass | teacher_review_pending |
| C02 | 1/1/1/0/0/1/1.0 | actualpass | teacher_review_pending |
| C03 | 1/1/1/1/0/1/1.0 | actualpass | teacher_review_pending |
| C04 | 2/0/0/2/2/0/None | actualpass | teacher_review_pending |
| C05 | 1/1/1/0/0/1/1.0；1/1/1/0/0/1/1.0 | actualpass | teacher_review_pending |
| C06 | 1/1/1/0/0/1/1.0 | actualpass | teacher_review_pending |
| C07 | 1/1/0/0/0/1/0.0 | actualpass | teacher_review_pending |
| C08 | 1/1/1/0/0/1/1.0 | actualpass | teacher_review_pending |
| C09 | 1/1/1/0/0/1/1.0 | actualpass | teacher_review_pending |
| C10 | 1/1/1/0/0/1/1.0 | actualpass | teacher_review_pending |
| C11 | 1/1/1/0/0/1/1.0 | actualpass | teacher_review_pending |
| C12 | 1/1/1/0/0/1/1.0 | actualpass | teacher_review_pending |
| C13 | 1/1/1/0/0/1/1.0 | actualpass | teacher_review_pending |
| C14 | 1/1/1/0/0/1/1.0 | actualpass | teacher_review_pending |
| C15 | 1/0/0/1/1/0/None | actualpass | teacher_review_pending |

C02 recorded0仍有效；C03 needs/incomplete同一人重叠；C04 absent/exempt与C15 missing的零分母均null，incomplete/noEvidence重叠没有加成人数。C05综合题两KP给关联失分，材料明确不推断具体步骤错因；C06报告两班只取明确目标班进入wire；C07同学生两个attempt只选第二次，完整ID→alias/attempt/出勤/原矩阵核对，未自然累计两个学生。固定历史className=null/“该成绩未记录班名”保持，没有用教案当前classNameAtSave补写历史。

## 匿名wire、采用与DOCX

每例实际用户wire JSON恰与固定匿名modelPayload深等，所有冻结personalTokens不在wire；所选单班KP计数逐项等于手写重算。完整raw回复/候选五整字段和process各stage/design/secondary保留；只选字段与完整候选相等、未选字段及教师六字段逐字段相等，当前教案仍unreviewed；分钟整数分配逐项等于手写预算并合计5或常用课时。

十五实际DOCX逐ZIP CRC、全部XML/rels内部目标、完整11字段投影、前两环节/其余环节及每个secondary全部严格核对。此为现有buildDocx结构输出，不是实际Word/WPS逐页渲染；质量15份的Word/WPS排版not_run。本批另外四例公开UI导出和13实际PDF页的证据在 [导出结果](../RESULT-v1.md)。

引用作者 [计数勘误](../../b6-quality/RESULT-CORRIGENDUM-v1.md)：准确为**15例各1次，共15次Provider HTTP transport替身调用；真实模型/外部调用0**。原报告措辞“每例15次”未改写，原reportSHA与勘误原件核对一致。usage input/output=null，不能称实际模型消费。实际完整offline第三轮/marker/15DOCX导出/新v3源绑定/live缺输入五收据前后源941精确等于base、各自ownQA0漂移；本卡不把后续SourcePanel build冒称已新跑。

## 量规和待真人项目

8维量规包含事实解释、教材支持/相关性、KP覆盖、活动/检测、分钟可实施性、教师控制、内容准确与后续练习反馈；先判来源/分母/引用/非法字段/预算/身份泄漏/未审自动发布硬失败。15行feedback的reviewer/date/8维分数/硬失败/原文位置/真人结论全部空白，caseHash及bound_v3 SHA对应真实原件，没有伪造教师评价。

缺live范围的真实预审PID10948/71.844ms按设计exit2，缺profile/model/cases/数量/token或费用上限，network0/main未导入/正式.env未读。review_tool仅导入argparse/json/pathlib，合法范围也只给CTRL执行前准备；不另起prompt管道。真实模型与真人、Word/WPS、RAG拒答/语义、正式迁移/Qdrant/压力未执行，不能据技术结构关闭原B7。

## 自己的审计首败

r1已完整保存源/receipt/log：前5例后C06的ID原顺序/规范排序差异使自己的列表等值断言失败；新r2改用完整集合/长度/无重复与逐ID alias/attempt/原四态矩阵映射，保留全部选人核查。r2前10例后C11失败是自己错误将normalizedTextSha256（完整文档）当slice SHA；作者v3本来正确，新r3分别核全blob和精确18字slice，两种身份都保留。未修改作者任何文件，也未把两部分绿色拼入本结论；只签收完整新r3十五例。

实际执行、逐人重算、全部散列/原件inventory、首败、勘误与未执行边界见 [RESULT-v1.json](RESULT-v1.json)。
