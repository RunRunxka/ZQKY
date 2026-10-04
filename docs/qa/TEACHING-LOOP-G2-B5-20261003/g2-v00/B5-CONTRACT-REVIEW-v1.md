# B5 契约独立静态审查 v1

结论：**STATIC_CONTRACT_REVIEW_APPROVED**。当前记录字节无剩余契约冻结阻塞，可冻结并派实施卡；这不表示 B5 已实现或业务验收通过。

我逐项核对了 Python DTO、六表 DDL、TS 镜像、API transport、旧本地数据验证、聊天 RAG 重导出及现有模型/任务接口。12 个方法/路径和 40 个 OpenAPI schema 对齐。旧内容十一字段、过程四字段、schemaVersion=1、空正文/过程与课型顺序保持；新 envelope 严格校验和 2MiB 上限已明确为新增边界，拒绝时须保留原稿。

准备期发现并由 CTRL 修正的差异均已只读复核：初次 INSERT 的 current pointer/CAS 四列 FK；readable 的 Python/TS null 差异；同一 proposal 多次接受或接受后拒绝；另有 CTRL 作者探针发现的 COMMIT 延迟外键失败未回滚，现已静态确认异常回滚结构。完整原件与来源 SHA 见 JSON，不改作者首败结论。

DDL 具备真实 owner 复合外键、精确 base/CAS、不可变行触发器、accepted proposal 唯一和 terminal decision 约束。保存/应用/receipt 的整事务与故障回滚仍须实现后真实验证。原迁移模块 7 文件相对 B5 开工基线缺失/变化均 0；原 0001～0009 的 v1/v2 声明记录逐项相同。

现有模型句柄、统一 provider.complete、冻结指纹与 JobOutcome.publish 可支撑方案。尚待 CTRL 实现并装配的公共依赖是 reviewed practice reader、教材 prepare/verify evidence reader，以及绑定模型解析 callable；这属于已明确负责人和签名的实施依赖。技术运行不得在这些依赖缺失时宣称通过。

v2 OpenAPI 与成功/失败例是静态契约。19 正 DTO／5 错误 envelope／12 拒绝、30 DDL 作者检查及后续作者回归只作引用；我没有运行测试、产品导入、SQL、模型、HTTP、浏览器、服务或 Git。仅新增本 MD 和同名 JSON 后停写，待稳定 B5 候选独立验收。

| 绑定对象 | SHA-256 |
| --- | --- |
| docs/qa/TEACHING-LOOP-G2-B5-20261003/B5-CONTRACT-v1.md | c0c3231d6855e3fe9a3fd7431cf6d01441d17f38b0febd81db7f0628f5909096 |
| apps/api/app/contracts/lesson_plans.py | eb964a46c6bda93de7a4ad4144fa6b8351c5f1067b9d133d86e23aa459d8fea6 |
| apps/api/app/core/migrations/lesson_plans.py | fca99c41508188aca881f3b1363c10f6f09c97e0cd976f4c7544c82a6b1466d6 |
| apps/web/src/contracts/lesson-plans.ts | b81fc08dce0f39a318ddad2b2bead7d32f9657132872614091dbbea9b67ab5e2 |
| apps/web/src/services/lesson-plans-api.ts | bf9aae52cf632a5766b776f5e5373dc86553005fa6b0fcc845fe15b906071ce3 |
| apps/web/src/contracts/rag-v2.ts | fd0befdd6f59d46161dc843c24dcc5787ed9576d22ae771c8a77ef9ae4ebc62b |
| apps/web/src/features/lesson-plan/model/types.ts | e35c8d7c923625240235975a0c9cfa9b4d81fd512558c295688e77c281f307bb |
| apps/web/src/features/chat/model/rag-v2.ts | edd6c3150db31a1caac778800109a3cb5b9168933e28ec73dcbf3cc7d67caf5a |
| apps/api/app/core/sqlite.py | c8046087351063289b2260850d93af7df82fa6940a4c63871de347a12e1e540f |
| docs/qa/TEACHING-LOOP-G2-B5-20261003/B5-OPENAPI-v2.json | aaa531035949f1de586802af648bcf08601707bde389d9e1eda5f0cc7169260f |
| docs/qa/TEACHING-LOOP-G2-B5-20261003/ctrl/B5-WIRE-EXAMPLES-v2.json | 4be7ef8a5865c1f9d8a2bad90820a86b4187113c8ef6780f814efe6bc849a559 |

完整依赖 SHA、准备期 before/after、未执行原因与后续 oracle 输入见 B5-CONTRACT-REVIEW-v1.json。

