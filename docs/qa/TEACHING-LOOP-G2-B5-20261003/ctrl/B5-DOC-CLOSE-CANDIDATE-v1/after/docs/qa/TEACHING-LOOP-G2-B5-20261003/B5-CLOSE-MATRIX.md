# B5独立验收与关闭矩阵

更新：2026-10-03 22:03。**G2和B5全部必要技术门禁、独立验收、资源退出及精确文档核准完成，CTRL已关闭本批，当前停止。** 授权止于B5；不自动开始下一阶段，不提交/推送/切分支/部署。

全部行均以修后[B5-r8](CANDIDATE-B5-r8.json)和逐文件绑定为依据；不拼修前r5或多轮绿结果。938source/3061可执行QA文件/33冻结/2004build，FVU-OXmtBh9WBSHehixfE/8001。独立组件27、浏览器8、原153和14为新完整单轮；后台410精确绑定本批早先API1918+1/42，未重跑。

| 门槛 | 正确行为与实际证据 | 最终结论 |
| --- | --- | --- |
| G2前置 | 23组件/11真实API/44四库核查/8浏览器/原153与14、[G2已批准关闭](ctrl/G2-CLOSED-r4-v1.json) | 已关闭，原件不追改 |
| T90保存/历史/导入/owner/CAS/receipt | [独立42API](b5-v00/results/EXEC-FIRST-ROUNDS-v1.md)、[410源前后绑定](ctrl/B5-R8-API-EXACT-BINDING-v1.json)；并发同包/异包409、后期旧receipt、A→B→A、真归属FK/不可变/同正文上下文语义；新8含双标签/unknown/保新输入 | 独立技术验收通过 |
| AI固定输入/隐私/strict/租约/原子发布 | 42API含最终3协议wire、短号身份、20非法patch、固定报告/单班/证据/fingerprint、timeout/retry/cancel/失权/重启/发布失败；[新8](b5-v00/results/EXEC-r8-browser-first-v2.md)真实四库装配生成 | 技术链通过；真实供应商教学质量未执行 |
| 教师五字段选择与六项不变 | 新8手写oracle：partial2/未选3/teacher6，候选终结/原包恢复、undo新修订、历史固定；fresh188与8指针检查 | 独立技术验收通过 |
| 前端session/cache/unknown/迟到ACK/Back | [原27同字节](b5-v00/results/EXEC-r8-unit-second-INDEPENDENT-v1.md)及新8：完整旧键/11字段、原metadata、readFailure不空覆盖、dirty明确处理/新输入保留/旧ACK不倒退 | 独立正确行为通过 |
| R01短号隐私与R02 quoted体检 | 42API短号最终wire、4实际quoted变异startup/recovery拒绝 | 两反例关闭 |
| R03历史copy intent | 新8真实Next历史复制、A/B/取消/放弃/历史/本地clear、6公共backup全部11字段 | 反例关闭 |
| R04原包签名与旧M1复活 | 原27保存await/unknown、换模型、422/503失败不得复活旧候选；新8完成真实生成/采纳 | 反例关闭 |
| R05三口分页 | 原27严格≤200、241后页、空页/总数变更失败/retry，四视口真实单班固定来源 | 反例关闭 |
| R06迟到来源擦教师输入 | 原27与新8四视口保留model/duration/requirements及正确固定事实 | 反例关闭 |
| R07本地flush导航 | 原27真实600ms writer/快导航/慢写续编/失败显式retry；[原153](b5-review/E2E-R8-INDEPENDENT-v1.md)两原case628/453ms完整通过 | 反例关闭，原151/2首败保留 |
| R08 busy→unknown弹窗刷新 | 原27同字节全部提示/原包/缓存/11字段/save0/router0/cancel后验通过；[静态](b5-review/R08-STATIC-v1.md)核ref+state/ownerlease/StrictMode/不重建session | 反例关闭，原26/1首败保留 |
| 旧本地全路径兼容 | 原27与原153完整新单轮覆盖600ms串行、失败/坏稿、规则警告、JSON/undo/refresh/Word/print；v1与ProcessItem/旧key保留 | 适用回归通过 |
| 四库迁移/恢复 | [实际restore](ctrl/B5-RECOVERY-PROOF-v1.json)、fullAPI含演练、[独立16库只读](b5-v00/results/RECOVERY-READ-AUDIT-v1.md)：六新表全行/教案候选历史/2blob/3隔离向量点/旧9hash/FK/完整性 | 隔离技术验收通过；正式迁移/Qdrant未执行 |
| Word/打印/视觉 | 全22 B5原图实际view，4DOCX ZIP/XML/长secondary/11字段/teacher6、4冻结print/6backup；[26聊天逐图](b5-v00/results/CHAT-R8-VISUAL-v1.md)保留CV01～03 | 结构/行为验收通过；WPS人工分页/实际PDF未执行，非全视觉PASS |
| check/API/全量/chat | check118文件1256/type/lint0/build；API1918+1和42精确410；原153/153及14/14新单轮exit0，无skip/retry/flaky | 必要工程门禁通过，API原规模skip单列 |
| 资源/样本/保全 | [资源v2](ctrl/B5-RESOURCE-CLOSED-r8-v2.json)、[独立资源](b5-review/RESOURCE-R8-INDEPENDENT-v1.md)、[保全](AUDIT-B5-r8-final-preservation-v1.json)：10serviceclosed/72commandcomplete/81log独占读/182Temp保留/三portfree/全部SQLiteclosed | 通过，用户进程未结束 |
| 精确文档/停止 | [before/after清单](ctrl/B5-DOC-CLOSE-CANDIDATE-v1/MANIFEST.json)独立核准后原字节应用；CURRENT/NEXT/API/ROUTES/PROJECT/moduleAGENTS一致，无Git写入 | 本批关闭，止于B5并停止 |

付费真实模型质量、Word/WPS人工分页/PDF保存、正式6333/正式数据迁移、超已有基线压力明确not_run。200人次×100叶UI实际通过不等于后台重型skip通过。RAG-REL/R-14/CV及原首败保持；额外HTTP被blocked by policy拒绝仍not_run未重试。所有阶段性矩阵旧描述原字节见[整理前快照](ctrl/B5-DOC-CLOSE-CANDIDATE-v1/before/docs/qa/TEACHING-LOOP-G2-B5-20261003/B5-CLOSE-MATRIX.md)。
