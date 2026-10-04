# B5 独立验收与关闭矩阵

2026-10-03，CTRL负责最终结论。G2已关闭；本表仅B5，当前未关闭。共享33件冻结清单见ctrl/B5-CONTRACT-FROZEN-v1.json，prebuild-v1已冻结938源/1890QA（旧G2构建不当B5通过）。作者自检不是独立通过；所有首败和历次QA清单原件保留。

| 门槛 | 当前事实 | 独立结论 |
| --- | --- | --- |
| T90 保存、导入、CAS、receipt、相同意义去重、A→B→A、历史与owner | BE v2作者45/45；归档422修复，不改原成功receipt重放 | 未执行 |
| T90 固定来源、三协议wire隐私、预算与strict候选 | AI v2作者144/144；真实生产来源/模型serializer/JobEngine隔离技术链 | 未执行 |
| 六态任务、取消、失租、timeout、restart/retry指纹与发布同事务 | 作者私有技术链已覆盖；V00独立受控故障已准备 | 未执行 |
| 五字段完整选择、教师六字段、partial终结、reject、unknown应用与undo新版本 | BE/FE作者自检已覆盖，不等同真实四库UI链 | 未执行 |
| 本地旧稿、坏稿/读取与写失败、600ms、JSON、规则警告、撤销重做 | FE v2最终作者73例含原50；独立v3执行中 | 未执行 |
| 服务端session、操作代次、lateACK、cache、StrictMode、双标签与离开/Back | FE v2作者覆盖；独立15unit执行中，真实browser待新构建 | 未执行 |
| B5R-R01 短数字身份与可信alias/count路径碰撞 | AI v2窄修144作者通过；V00真实短号名单→固定成绩→报告v3准备 | 待复验 |
| B5R-R02 SQL literal/JSON path体检绕过 | CTRL保留quoted字节；真实变异+恢复新10例作者通过 | 待复验 |
| B5R-R03 历史复制跨Next重挂丢intent | CTRL薄page key只保留routeError，两份修前字节保持；合法analysis参数真浏览器v3准备 | 待复验 |
| B5R-R04 保存等待/unknown原生成包与source签名错配 | 独立静态确认；FE v2已停写，最终73作者通过；V00等待窗口与unknown v3执行中 | 未关闭 |
| B5R-R05 classes请求超过真实API分页上限 | 独立静态确认；FE v2完整≤200分页作者通过；V00后页目标班v3执行中 | 未关闭 |
| 0010 新库、已填B4、失败回滚重跑、旧9hash与真FK | CTRL实际DDL 30检查及原三迁移测试新19/19 | 待冻结后独立核验 |
| 四库完整备份恢复、六新表/建议/历史/资产/标准main/真实Rag证据 | CTRL恢复新1/1，六表2/3/3/2/2/2、两资产三点；完整原件保留 | 待独立核验 |
| 真实四库浏览器：成绩→报告→单班KP→后台稿→候选→partial→历史→undo→导出 | 四视口原链+丢响应/Back+双标签+历史复制准备；尚无新build | 未执行 |
| Word实际文件内容、11字段/长文/二次/符号/公式/模板hash与100msprint来源快照 | 作者结构检查；V00手写sentinel、实际download/XML和打印捕捉准备 | 未执行 |
| 390/1024/1440/1920、reduced-motion、键盘/焦点与逐图实读 | 新browser尚未运行，不能借旧图关闭 | 未执行 |
| 新完整check/API/build/原153完整E2E/14chat | 后端首轮1912pass/5fail/1既有skip保留，编码/现行QA预期修正后窄31/31；prebuild-v1 check1202/API1918+1既有skip均通过，但独立unit11/4失败后R04/R05残余待修，G2结果只历史 | 整体门槛未通过；check/build/153/14未执行 |
| 自有进程/端口/连接/browser释放、TEMP保留 | B5未起TCP；既有作者子进程已退/连接已关/新样本保留 | 待最终实际核验 |
| source/QA/33契约/build/591 G2/4136历史/next-env/精确文档后验 | 冻结清单保持；prebuild冻结已完成；新build与最终审计未执行 | 未执行 |

明确未执行：真实供应商教学质量、Word/WPS人工排版、正式Qdrant6333、正式数据迁移和超既有规模压力。隔离工程链不推断这些质量或生产验收，RAG-REL/R-14/旧CV台账保持。B5所有必要技术门槛通过并经独立核准后，CTRL才能关闭；结束后止于B5，不Git写入/推送/切分支/部署。

2026-10-03 18:38补记：prebuild-v1完整check已结束，118文件/1202单测、类型、零警告lint/build通过，exit0/110566.057ms/PID6308，938源/1890QA前后0，next-env原字节恢复；完整API1918pass/1既有规模skip、exit0/392504.479ms/PID21200，938源0。独立API42/42、exit0/40948.122ms/PID20076；unit首轮11pass/4fail、exit1/6458.522ms/PID8056。三失败是新模拟proposal缺必填jobId，v4仅补真实DTO且保留原断言；后页班case确认SourcePanel.load首100遗漏为R05残余。独立static v3又确认R04新M2生成明确失败时旧M1候选复活，准备独立正确行为首败再窄修。当前原候选/首败/新构建均保全，不进入browser，不关闭B5。证据工具二次修严格限定两live authority，589实时原件+2核准归档快照保护，原首次587+4分类及prebuild-v1不追改。

2026-10-03 18:47补记：新prebuild-v2-QA已冻结SHA5700383f93f4df0cf0ae4c2dfc4aec10bfdf38042e815941a04c051f15223aa8，source938与v1同字节，QA1892仅helper窄范围+v4新2件，build9KvS9k4O8Bs3ZampQA3-_ /2004实际8001。V00原完整16首轮14pass/2产品fail、3292.472ms/PID26248/sourceQA0；原三unknown补真实jobId后全通过，R04明确422后旧M1复活和R05后页班首败保持。所有原绑定运行已结束，CTRL已OPEN FEv3唯一写窗口，同时将静态确认的报告/练习首100同类截断纳入SourcePanel三口分页窄修；V00 v5独立新后页QA只准备，runtime等作者停写。当前不关闭B5、不起浏览器。

2026-10-03 19:02补记：FE v3已STOP，最终95/95、9473.539ms/PID22436，类型1753.949ms/lint2959.092ms零警告、源0；首94/1为新unknown文字期待错误，全部原输入/日志保持，后新95单轮全走原包/过期/采用0断言，不拼绿。独立QA v5 SHA2784016cde55ab949f563d0b0d177200a543f8e0ba2e519bc59b0df78b828ae0已停写；新prebuild-v3 SHA317395661152fc2472932223192e08252a2c7aa93c4c5f22d0dbfa1683a4fa61，938源/2193可执行QA/33冻结/954prior/4136历史，仅三FE源delta，410后台原full1918+1/API42完全同字节，原结果精确绑定但未冒称重跑。V0018新单轮执行中，结束后才新完整check/build避免next-env派生写并发；旧build9Kv不能当此次修后构建。独立实际四库只读16库完整性/FK/全行/六新表/9迁移/两blob审计通过，16连接关闭与56样本hash零变化；作者恢复实际运行与独立只读分列。browser/153/14尚未执行，B5未关闭。
