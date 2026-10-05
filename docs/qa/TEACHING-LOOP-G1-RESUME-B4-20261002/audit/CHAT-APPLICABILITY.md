# G1R-AUDIT v1.1 聊天适用性

2026-10-02，独立只读核对者 `/root/g1_v00_fe`，只写本批 `audit/**`。**本轮 G1 不需新增 stream 集成；原全量 E2E 中的聊天 UI 用例仍适用。** 这是按当前实际依赖范围作出的回归选择，不是声称聊天端到端已重新通过。

相对 G1 开工 `BASELINE.json`，实际13产品改动为：后端 JobStore/JobEngine/Registry、题库 service/fingerprint/catalog 与 tabular 七文件；前端 ScoreImportReview/ScorePanel/AssessmentsWorkspace/AssessmentsPanel/RosterPanel/RichContentRenderer 六文件。没有改普通聊天/RAG、模型运行时/供应商、SSE适配、聊天 store/请求预算/会话仓储、Markdown渲染、全局样式、路由壳、共享客户端或依赖锁。

静态本地依赖核对见 `chat-dependencies.py/json/log`，没有导入/执行应用：

- `/chat` 与 `/chat/[sessionId]`、根 layout 的保守本地依赖闭包 **87文件**，包括 type import、公共壳与样式叶子；和13文件交集为空，全部87文件与G1前 SHA一致。
- FastAPI `/chat/stream` 路由的本地 import 闭包 **19文件**，和13文件交集为空，全部19文件与G1前 SHA一致。
- 核实 `features/chat/model/chat-service.ts` 经 `services/chat-stream.ts` 和 `chat-sse.ts` 处理流；FastAPI `api/v1/chat.py` 直接经 `model_runtime` 构造 Provider、消费 stream，不调用 JobEngine/JobStore。
- 核实 `Message.tsx` 使用 StreamingMarkdown/AnswerMarkdown；AnswerMarkdown 使用既有 react-markdown/KaTeX 等，不引用本次修改的 RichContentRenderer。教学富 renderer 依赖聊天 Markdown 不表示聊天反向依赖教学 renderer。
- 共享 `main.py` 启动仍会装配公共 JobEngine/注册表，但 main/lifespan 装配源未改。原冻结G1的实际 check与全量API覆盖该应用启动接线；本轮只是两个e2e资源回收适配，不引入新的聊天调用路径。

静态算法不声称证明任意运行时动态依赖；已人工核对上述实际调用路径与13文件导入边界。没有新流式失败或相关源码变化，用户新授权明确“不因无变动重复全部测试”，因此额外 `test:chat` **not_run（不适用本轮13项改动）**；不能直接执行其默认脚本，因为它会重建 `.next-test` 并自动启动5174/8001/8002，与用户持有前端及资源边界冲突。

实际命令，仓库根，UTF-8、新系统temp环境变量预先注入（脚本仅文件读取，不建业务库）：

```powershell
apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/audit/chat_dependencies.py
```

exit0，一次静态审计13改动/87前端依赖/19后端依赖；交集和源码差异均0。没有启动/停止监听、浏览器、应用、模型或上游进程；没有读取正式.env/业务库/用户草稿/旧六目录。此判断不关闭剩余真实教学浏览器、视觉和全量E2E门禁。
