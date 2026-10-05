# G4 四项限定技术关闭（2026-10-05）

ROOT 于 13:39:48 +08:00 独立关闭 G4，四项收据见 [G4-CLOSE-v1.json](G4-CLOSE-v1.json)。稳定候选 [G4-fix-built-r2](CANDIDATE-G4-fix-built-r2.json)，SHA `f81a0684abdf734b067a731c089f798a3aabfe66a1f5d336ea1bd1506db34d6e`，构建 `VeOLFBYrp-8v24Yjm-HFi`，实际代理 8001。main/HEAD 未改，无 Git 写入。

| 发现 | 独立正确行为与证据 | 结论 |
| --- | --- | --- |
| B6F-R01 | 完整可信缓存公开重试、写入读回后解锁、11字段/secondary/context/source/原操作/ACK/CAS保护；发送前故障 busy 最小补修；create/import 离开阻断。作者 v2 158/158，独立新38整轮及新真实11均覆盖 | [独立技术关闭](G4-B6F-R01-CLOSE-v1.json) |
| B6F-R02 | clear独立intent撤销首次null及非空 getSource/verify/catch，保留题/练习/metadata owner、范围/会话/discard守卫及下一片段原语义；真实持有200响应再清除，后续实际请求仅新[10,20) | [独立技术关闭](G4-B6F-R02-CLOSE-v1.json)；仅签新payload，不把请求出现写成候选生成成功 |
| B6Q-R01 | 冻结手写manifest与授权集合；少C15/重复/额外/未知/缺结果或DOCX/SHA/坏ZIP/错误来源硬失败；正确15/15和显式14/14、C15 unrun分列；完整冻结来源绑定与当前物理缺源分开 | [独立技术关闭](G4-B6Q-R01-CLOSE-v1.json) |
| B6Q-R02 | strict JSON/模型字符串/已知唯一caseIds/非bool正整数计数、尝试和token/有限正费用；maxAttempts计入SHA；凭证和未知字段拒绝；合法仍仅人工范围审查形状 | [独立技术关闭](G4-B6Q-R02-CLOSE-v1.json)，未实现live执行/模型存在/总预算保证 |

| 适用门禁 | 实际完整轮 |
| --- | --- |
| 完整check | typecheck、lint0、125文件1354单测、build；PID16028，103985.711ms，退出0，next-env原字节恢复 |
| 独立组件 | 新第四整轮38/38，PID21664，8662.032ms；[结果](v00/product/RESULT-v2.md) |
| 独立质量工具 | 新第二整轮59/59预期结果，其中52项预期硬失败，15全集/14子集实际结构核查；[结果](v00/quality/RESULT-v1.md) |
| 新真实浏览器 | 第四完整11/11，PID10896，13636.767ms；4视口键盘焦点、实际完整cache/backend/history/原包及source payload；[独立复核](v00/browser-review/RESULT-real-v1.md) |
| 原适用真实回归 | 14/14，PID13436，44244.62ms，旧QA原字节保持 |
| 现行全量E2E | 29spec/174唯一case单轮174/174，PID11344，493859.033ms；0skip/retry/flaky/reporterErrors，原新增UI21和R14未略过；[独立复核](v00/browser-review/RESULT-full174-v1.md) |

[最终门禁后验](INTEGRITY-G4-gates-v1.json)：源码956/执行QA3493/契约33/活动生产构建970/历史QA19169全部零漂移。四个自有服务均关闭，已记录12个全量测试进程/浏览器后代的PID、出生时间与命令，结束后同实例存活0；5174/8001监听0，未知用户进程未操作，TEMP与首败保留。前端受控停止的进程退出1与已完成门禁退出0分开记录。

五份权威入口和v2计划书只增本批状态；剥离状态块后原始字节全等，PROJECT_GUIDE/API/ROUTES稳定文档未改。后端410、最新chat关联186、导出核心11与旧材料1056精确SHA引用，原1918通过+1重型skip/独立42/chat14本批未重跑。旧export/styles43有12项变化，不声称整体同源。见 [引用增量](v00/references/SOURCE-REFERENCE-v2.md)。

[首败](FIRST-FAILURES-v1.md)及收口脚本工具basename路径错误的 [发布前首败](ctrl/g4-close-first-failure-v1.json)保留；后者在任何关闭收据写出前失败，仅修正确切路径映射，原SHA断言不变。所有最终轮分别完整执行，没有拼绿或降低业务断言。

本关闭不覆盖原B6/B7整体。live=`not_run_user_offline_scope`；教师=`pending`；Word/WPS=`not_run`；旧物理源库/恢复目录缺失与1份旧VISUAL-REVIEW缺件独立记未执行。正式Qdrant/迁移、额外压力、发布部署未执行。R14、CV01～03、OBS-LP-MODE-LABEL、RAG-REL及原环境观察保留。
