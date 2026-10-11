# apps/api — FastAPI 后端（最小骨架版）

> 2026-10-11 推倒重做后：只保留对话 + Agent + 模型配置。业务域（教材/题库/知识点/
> 名单/原卷/施测/成绩/学情/练习/教案/RAG/embedding）已删除，历史实现见 git tag
> `archive-full-v1-20261011`。

## 结构

- `app/main.py`：最小装配（模型仓储/SecretStore/认证 + Agent Service + AssetStore + 路由）。
- `app/api/v1/`：health / capabilities / chat / agent / model_connections / model_profiles / model_catalog / model_views。
- `app/services/agent/`：LangGraph 编排。
  - `graph.py` 系统提示与 `create_agent`；`runtime.py` 事件规范化（text/tool/wait-confirm/end/error）；
  - `model.py` **模型工厂**：官方 provider 包显式注入凭证（本地免 Key 占位符）+
    `assert_no_provider_env_keys`（`OPENAI_API_KEY`/`ANTHROPIC_API_KEY` 不得出现在进程环境）；
  - `tools.py` / `tools_write.py`：**工具表为空骨架**——按 `app_state` 服务装配情况注册，
    服务为 None 时不注册（不误报可用）；业务重建时在此扩展。
- `app/services/jobs/`：任务引擎骨架（六态 + 租约），当前无任务类型注册。
- `app/core/`：config / secrets（凭证只经 SecretStore）/ sqlite / data_lock / migrations 机制。
- `app/providers/llm/`：三协议适配（openai-chat / openai-responses / anthropic-messages），38 供应商注册表。

## 纪律

- SQL/IO 在 `anyio.to_thread` 有界线程；出站调用不阻塞事件循环。
- 错误统一 `AppError`（code/status/retryable）→ 错误信封；未实现路由 501，不假成功。
- 测试：`uv run python -m pytest`（入口坑见根 AGENTS.md）；新增能力必须带正/负用例。
