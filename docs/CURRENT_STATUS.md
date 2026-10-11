# 当前状态与实施主线

<!-- SKELETON-RESET:20261011 -->
2026-10-11（用户裁定「只保留 chat 页，其他全部删除，推倒重做」）：**最小骨架重置落地**。归档 tag **`archive-full-v1-20261011`** 保存了此前的完整产品（教学闭环全量：Agent 融合/教案三栏复刻/学情可视化/知识点树/题库分类/施测拆页/练习 AI 出题/教材清洗，共 16+ 提交）。

**当前形态：对话 + 教学 Agent 编排 + 模型配置的最小骨架。**

- **前端**：仅 `/chat`（对话：会话管理/流式消息/附件上传/Agent 中断确认卡/产物面板/上下文小圈/思考强度切换/模型选择）与 `/settings`（外观/模型与连接/关于）。其余页面与 feature/services/contracts 全部删除。
- **后端**：仅 health / capabilities / chat / agent / model_* 路由；services 保留 agent（LangGraph 编排，**工具表为空骨架**，服务缺失时工具不注册）、model_auth/model_config_service/model_readiness/model_runtime、assets（上传落 blob）、jobs（任务引擎骨架）。业务域（教材/题库/知识点/名单/原卷/施测/成绩/学情/练习/教案/RAG/embedding）全部删除。
- **数据**：本地业务数据全清（`.local-data` 仅剩 `model-config.json` 与空 `agent/`）；模型配置保留。
- **关键实现**：chat 默认走 Agent 通道（`/agent/stream`，LangGraph + checkpointer 落 `data/agent/`），显式注入 stream 时才走 `/chat/stream` 直连；LangChain 官方包显式注入凭证（本地免 Key 占位符）+ 进程环境 `*_API_KEY` 断言。

**门禁**：后端全量 pytest **220 passed / 1 skipped**；前端 typecheck 0 / lint 0 警告 / 单测 **19 文件 178 例** / build 0。

**台账（待办）**：
- **Qdrant 集合待清**：本机 Qdrant（6333）当时未运行；启动后需删除旧教材向量集合（新骨架不使用向量库，无集合也无影响）。
- **e2e 需重写**：保留的 10 个骨架 spec 未在本次跑（旧业务 spec 已删）；`chat.spec/chat-home.spec` 断言需与新骨架（应答「对话」、无能力菜单）对齐后跑一遍。
- **模块级 AGENTS.md 待更新**：`apps/api/AGENTS.md`、`apps/web/src/features/chat/AGENTS.md` 仍含全量时期描述，重建对应模块时同步改写。
- **业务重建**：教学闭环各模块后续以「Agent 工具 + 对话内呈现」的形态逐项回归；旧实现参考一律经归档 tag 读取，不直接捞回工作区。
<!-- /SKELETON-RESET:20261011 -->
