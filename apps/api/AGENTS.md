# apps/api — FastAPI 后端

> 2026-10-12：R 系列重建完成——八个业务域已装配（与对话/Agent/模型配置并存）。
> 历史全量实现见 git tag `archive-full-v1-20261011`（取回参考的唯一入口）。

## 结构

- `app/main.py`：装配入口。核心件（模型仓储/SecretStore/认证/PublicationCoordinator/AssetStore）
  + **业务域装配循环** `_install_domain_assemblies`（按 `_DOMAIN_ASSEMBLIES` 顺序导入
  `app.services.<domain>.assembly:assemble(app, settings)`；**顺序即依赖顺序**：
  teaching 第一批 → knowledge → question_bank → teaching 成绩/学情 → practices → lesson_plans）。
- `app/api/v1/`：health / capabilities / chat / agent / model_connections / model_profiles /
  model_catalog / model_views + 八域路由 + `workflow_jobs`（共享任务路由，首个域幂等注册）
  + `export_artifacts`（产物读取分派：练习链走表、分析报告/教案走 `file_assets(kind=export)`）。
- `app/services/`：
  - `agent/`：LangGraph 编排。`graph.py` 系统提示与 `create_agent`；`runtime.py` 事件规范化
    （text/tool/wait-confirm/end/error）；`model.py` **模型工厂**（官方包显式注入凭证 + 本地免 Key
    占位符 + `assert_no_provider_env_keys`；**全模块 LLM 的模型解析入口**，受管认证
    `AGENT_MODEL_UNSUPPORTED`）；`tools.py`（13 读）/`tools_write.py`（4 导入 + 1 确认 + 1 交互）
    ——按 `app_state` 服务装配情况弹性注册，服务为 None 时不注册（不误报可用）。
  - `llm/`：**LangChain 运行层**（`prompts.py` 提示词登记带版本指纹；`runner.py`
    `run_structured/run_text`：重试≤2、失败降级候选项不抛异常）。新模块 LLM 调用一律经此。
  - 八域服务：`textbook_ingest`/`textbook_index`/`textbook_search`、`knowledge`、`question_bank`、
    `roster`/`papers`/`assessments`/`scores`/`analysis`、`lesson_plans`/`lesson_generation`/
    `lesson_streaming`、`practices`；各域自带 `assembly.py` 或 `services/teaching/assembly_*.py`。
  - 共享件：`document_parsing`（解析/清洗/切块，C4-5 页眉页脚）、`text_projection`、
    `rich_content`（docx 富内容 + OMML）、`tabular`、`rag_v2`（检索/证据/范围）、`jobs`
    （引擎 + 执行器注册表 + `assembly.register_job_store`）、`publication`（跨库发布协调）。
- `app/repositories/`：四库仓储（textbook_catalog / knowledge / question_bank / teaching）+
  `vector_store`（memory/qdrant）+ `jobs`；迁移在 `app/core/migrations/`（追加式 + 散列漂移检测，
  0014 为最新教学库迁移）。
- `app/providers/`：llm（三协议，38 供应商）+ embeddings（Ollama bge-m3）。
- `app/resources/lesson_templates/`：教案导出模板（空白 + 填充样张）。

## 纪律

- **LLM**：不直连供应商 SDK；提示词经 `PromptSpec` 登记（同版本改稿会被拒绝，必须升版）；
  结构化输出用 Pydantic 严格校验；失败降级为「候选 + 标注」，绝不静默成功。
- **写操作**：AI 只进候选；落库/发布/删除经教师确认（工具内 `interrupt` → `/agent/confirm`）。
  **学生姓名/学号不进模型**（学情一律代称）。
- SQL/IO 在 `anyio.to_thread` 有界线程；出站调用不阻塞事件循环。
- 错误统一 `AppError`（code/status/retryable）→ 错误信封；未实现路由 501、缺依赖 503，不假成功。
- 冻结件：已提交迁移的 SQL 与 `rag_v2/{retrieval,scope,source_text,evidence}.py`、
  `document_parsing/*` 不得改写；新需求走追加迁移或新版本号。
- 测试：`uv run python -m pytest`（入口坑见根 AGENTS.md）；新增能力必须带正/负用例；
  当前基线 1835 passed / 0 skipped。
