# B6 质量准备代码与证据只读审查

2026-10-04；负责人 g3b6_quality_review。范围：限定 B6 的质量 runner、预写 oracle、匿名输入/固定来源、评审材料和最终关闭证据。产品、旧 QA、权威状态文档、Git、服务与正式环境未写；所有新增文件只在本目录。没有真实模型或外部调用，没有读取凭证。最新批没有 `REPORT.md`，按真实入口 README、最终矩阵与关闭收据审查，不把文件不存在列为缺陷。

结论：发现 **2 项 P2 质量工具缺口**，应先修新批评审工具，再开展真实模型试评。既有 `offline-third` 的 15 例完整证据经本轮独立重算和散列核查通过；两项工具缺口不推翻该批准备关闭，也不等于产品回归、真实模型收费越权或教学质量通过。

## Q01 / P2：缺少一个病例结果仍输出 PASS15

位置：[finalize_review_v3.py](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G3-B6-20261004/b6-quality/finalize_review_v3.py:106>) 第 106～107 行；输入消费在第 46 行。脚本只遍历 `SUMMARY.results`，没有先核该数组的唯一病例集合、声明计数和 DOCX manifest 是否完整一致；输出却固定 `caseCount=15`、`technicalStructure=PASS15`、`docxStructure=PASS15`。

反证：[FINALIZER-COUNTEREXAMPLE.json](FINALIZER-COUNTEREXAMPLE.json)。把原 SUMMARY 复制到新审查目录，**只删去 C15 的 result**，保留原 `caseCount=15` 和原 15 份 DOCX manifest，复制其余 14 例输入。运行逐字节相同的原 finalizer（原件与复制品 SHA 均 `a67b967d…`），只以 stdlib `mode=ro/query_only` 提供其只读 SQLite 入口，原四库及原 DOCX 只读。14 例真实核对完成后脚本成功返回；新输出有 **results 14 条、caseCount 15、两项 PASS15**，stdout 还同时出现 `caseCount=14` 与 `docxStructurePassed=15`。原文件和既有 15 例未改。复现脚本为 [proof_finalizer.py](proof_finalizer.py)，全部输入与输出保存在本目录 `runs/fourteenproof` 和对应新 feedback/RESULTS。

影响：以后结果收集截断/漏项时，此 finalizer 能把不完整样本包标为完整准备通过。既有独立 audit-r3 另有 `len(pack.cases)==summary.caseCount==technicalStructurePassed==15` 和逐全例核查，既有 15 条仍真实完整；此处是可复用 finalizer 的失败闭合缺口。

修复建议：在写任何 PASS/反馈表前，以冻结病例清单校验 `SUMMARY.results`、目录、manifest 和所有声明计数的集合/长度/无重复一致；结论计数由核验后的实际结果生成。少一例、多一例、重复 ID、零例、错误 case hash 必须非零退出并保留首败，不能写 PASS。

## Q02 / P2：非法 live 范围进入 SCOPE_REVIEW_READY

位置：[review_tool.py](<H:/备份xuexi/智启课源/docs/qa/TEACHING-LOOP-G3-B6-20261004/b6-quality/review_tool.py:15>) 第 15～20 行。范围校验使用真值与 `len(caseIds)` 相等，未校验病例数组/元素类型、病例 ID 白名单和唯一性，也未排除 bool 样本数、非字符串 profile/model 或非有限费用。Python 的 `NaN <= 0` 为 false，因此仅提供 NaN 费用也能过“正费用”分支。

反证：[AUDIT.json](AUDIT.json) 的 `preflightProbes`；[scopes](scopes/) 中均为新建的非敏感试探输入。原工具直接执行时，字符串 `caseIds="C10" / sampleCount=3`、重复 `C10,C10`、不存在的 `C99`、`sampleCount=true`、对象类型 profile、无 token 上限且费用 NaN 或 Infinity，**7 项均 exit0 / SCOPE_REVIEW_READY_CTRL_EXECUTION_REQUIRED**。合法形状对照也 exit0；缺输入对照 exit2。每次均 `networkCalls=0 / mainImported=false / formalEnvRead=false`。

影响边界：该工具只是离线预检，**本批没有 live 执行器**，文档和输出明确真实执行及预算落实仍属 CTRL；上述反证没有触发真实调用或越过付费授权。问题是下一批会获得错误的“范围准备就绪”信号，不能将其用作调用准入依据。

修复建议：要求根对象、非空字符串 profile/model、非空唯一病例 ID 数组且属于冻结清单、`type(sampleCount) is int` 并等于数组长度；token 上限为正整数，费用为正有限数，拒绝 JSON 的 NaN/Infinity 与错误类型。合法范围仍只出预审结论；真实连接/模型一致性与预算执行须在现有 Provider 调用入口另行核验，不猜正式配置。

## 既有材料核查

本轮 [audit_quality.py](audit_quality.py) 仅使用 stdlib，独立按原逐学生 alias、明确 attempt、目标单班、计分叶/KP 关联重算全部 15 例，与运行前手写 expected 全等。C02 有效 0、C03 needs/incomplete 重叠、C04/C15 零分母 null、C05 综合题两 KP、C06 仅目标班、C07 仅第二人次、C09 真题库缺口、5/40/45 分钟和 partial/five whole fields 均有材料。预写 `prepare_cases.py` 只导入 pathlib/copy/json，没有用产品聚合或候选反填 oracle；语义支持标签仍是 QA 的手写分类，需教师确认。

原完整输入→匿名 wire→候选→字段选择→应用结果及绑定 SHA 全部通过；匿名用户 wire 等于冻结白名单 payload，已知隔离学生身份 token 未入 wire；教师字段与未选字段逐字段保持。15 个实际 DOCX 的 manifest SHA 与 ZIP CRC通过。闭合收据列出的 evidence SHA 全部与当前原件相同。原 providerTransportCalls 15 例各 1 次、合计 15；真实模型 0，usage 为空。原“每例15次”误写已在独立勘误中明确，无需重写旧报告。

15 行 feedback 的评审者/日期/八维分数/硬失败/真人结论均为空；量规先判硬失败再评分，没有用平均分抵消硬失败。C10～C13 分列正例/窄边界/范围外/缺请求依据，C15 的学生成绩无证据另列，RAG-REL 保持 OPEN。原四导出样本和 13 实际 PDF 页与 Word/WPS 原生排版分列；此次没有原生 WPS 检查，也不把未执行项列为代码 bug。

本轮未重跑产品 API/check/E2E、真实模型、真人教学评分或 Word/WPS。原 SQL/Blob 完整来源核查引用既有独立材料；额外 counterexample 只只读核原四库 14 例，不能改称全15新 SQL/Blob验收。审查脚本首轮曾因 Windows stdout 编码失败；显式 UTF8 后完整成功，属于本审查工具适配。

## 建议下一批可执行范围

1. **B6-Q1：评审工具失败闭合**。在新 QA 批次目录新增有版本的预审/finalizer，修 Q01/Q02，保留旧批全部原件；产品与检索算法不改。独立验收先固定所有负例应失败，再新完整15正例通过；病例集合、分母、匿名 wire、原包/SHA、调用次数、五字段与 teacher6 必须同时保持。
2. **B6-Q2：最小真实质量试评准备**。冻结 C10～C13 的支持/不支持理由，由教师逐例填写原文位置和理由；在得到明确 profile/模型/病例数/token或费用上限后，沿现有匿名 Provider 做每例一次的小范围真实运行，保留原输出、指纹、prompt SHA、caseHash、实际 usage/失败。缺教师或模型范围继续记待输入，不自动补真人评分；发现实际内容硬失败才另开单一最小产品修复卡。
3. **原生排版人工卡**。复用已冻结的四 DOCX/13页 PDF 材料，由实际 Word/WPS 记录版本、逐页意见和页码。将 native 结果与浏览器打印 PDF 分列，不能因 PDF 通过宣称 WPS 分页通过。

本轮只形成审查和下一批建议，未启动上述实施。原 B6/B7 整体、RAG-REL、真人/live/原生排版边界保持。
