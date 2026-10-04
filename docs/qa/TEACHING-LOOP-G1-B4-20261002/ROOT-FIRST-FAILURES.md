# 本批首败记录

旧报告、失败日志及探针原文保持不变。本文件只登记新批记录；实现者首败链接见各 RESULT。

| 记录 | 实际结果与处理 |
| --- | --- |
| root OMML 首次命令 | 误用不存在的 apps/web/vitest.config.ts，启动失败exit1，未执行测试。原stderr在工具输出保留，未生成本地root/omml-first.log；此前误称有该stdout文件，D00实物核查后明确更正，不补造原日志。 |
| root OMML 第二次命令 | 配置改为根 vitest.config.ts，但测试过滤器误指 components/rich-content；无测试 exit1，root/omml-r2.log。核 rg 文件清单后正确路径 components/ui，一次8项通过，root/omml-r3.log。 |
| root typecheck 首次 | 新 ScorePanel.test.tsx 夹具五处可空 mapping TS18049，exit2，root/g1-typecheck-first.log。交原写入者补夹具类型守卫；产品行为断言不变。 |
| G1-FE | 首轮正确行为3fail/13pass、默认批次身份暂失2fail/49pass、ESLint 1warning；日志与修复记录见 g1-fe/RESULT.md。 |
| G1-SCORE | 首輪36pass/2fail为测试误将身份列当API score/meta cells；修正为原表JSON+固定人次核验，未改生产服务；完整首败见 g1-score/RESULT.md。 |
| G1-QB | snake_case/camelCase内部投影漏读11fail/8pass、同包重复两题2fail，均修复保留原日志；既有版本化测试1fail/96pass为新增并存算法行数，CTRL登记精确例外并分别核两个版本，旧指纹不变。见 g1-qb/RESULT.md。 |
| 冻结覆盖修正 | QA冻结过滤器把安全apps/api/.env.example也排除了。保留r1原825项清单，新增r2共826项；共同825项SHA完全不变，只补一项配置覆盖，无产品代码变化。各独立验收者追加r2全量核查，未虚报重新跑行为测试。 |
| 本批前端启动 | 工具拒绝创建5174 Next测试服务进程，只有blocked by policy理由，无产品测试结果；未换命令/工具绕过。已请求用户手动启动，真实浏览器及适用E2E待外部条件；实际8001组件链另行验证不冒称浏览器。 |
| CTRL收尾SQL对账首次 | 独立真API链包含甲/丙/丁3人次，root误把整矩阵预期写成甲一人3格，assert失败；诊断日志[root/closed-check-first.log](root/closed-check-first.log)保留9格实际行，原夹具[root/closed-check-first-source.py](root/closed-check-first-source.py)保留。未改产品或测试数据库。 |
| CTRL收尾SQL对账第二次 | 更正人数后又写反丙/丁原CSV得分，exit1；[日志](root/closed-check-final.log)、[原夹具](root/closed-check-second-source.py)保留。按独立原CSV重新核对并修正仅QA预期表，最终[日志](root/closed-check-accepted.log)exit0，完整9格与甲800/丙1000/丁800一致，四库完整性ok/外键零异常。 |

每次通过计数仅对应单次命令，不累加多轮，不以测试夹具修正替代产品反例关闭。G1 独立状态另见 G1-CLOSE-MATRIX。
