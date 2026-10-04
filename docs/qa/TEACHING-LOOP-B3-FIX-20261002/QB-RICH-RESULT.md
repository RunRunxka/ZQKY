# QB-RICH v1 结果卡

- 批次：TEACHING-LOOP B3 原授权富内容补齐。
- 实现者：scores_backend。
- 状态：ready_for_review；2026-10-02 本卡交付后停止写入，待总控与独立验收。
- 起点：共享 main@6aeb57280f6a7e0d7391cad4d150745479ea58ec；未执行 Git 写操作。
- 先行 SCORE 已交 ready_for_review，保持原候选冻结。

## 独占改动文件

1. `apps/api/app/services/question_bank/service.py`：草稿/正式题权威编辑、资产读取、派生指纹、确认事务外资产预检与版本复核、富内容拆分/合并/AI 应用保护。
2. `apps/api/app/services/question_bank/validation.py`：内容解析后调用统一富内容投影校验。
3. `apps/api/app/services/question_bank/rich.py`：已向总控登记的新增纯投影/安全资产适配 helper；不写任何库或资产。
4. `apps/api/tests/test_question_rich_content.py`：新增独占回归 39 例。
5. 本卡及 `logs/qb-rich-first.txt`、`logs/qb-rich-bounded.txt`、`logs/qb-rich-final.txt`、`logs/qb-rich-correct-behavior.txt`。

未修改 `fingerprint.py`：复用已有 derived-v1 扩展输入；历史 `content_fingerprint` 组成完全保持。
schema/TS contracts/API routes/客户端/前端/权威文档由总控及前端负责人处理；本任务未写这些文件，未引入迁移、依赖或跨库写入。

## 实际行为

- 可选 `richContent` 随既有 JSON 草稿、题目修订存储与读取。表格 cells/跨度/columnCount、LaTeX/原 OMML、共享材料、图片尺寸/引用/字节声明不丢弃；正式题修改追加修订，旧修订 JSON 不变。
- 富内容存在时是权威；stem/options/answer/explanation 的 Markdown 必须匹配确定性投影，失配给 422 `QUESTION_RICH_CONTENT_MISMATCH` 和具体字段。保留旧富内容而只编辑 Markdown 不会静默忽略。
- 旧题含 rich 时，省略 `richContent` 不能隐式清空，返回 422 `QUESTION_RICH_CONTENT_CLEAR_REQUIRED`。显式 `richContent=null` 可进入既有纯 Markdown 编辑流程。原纯 Markdown 题缺省/null 均保持兼容。
- 同步更改富内容与其投影可形成教师要求的新内容；答案按题型核对实际 choiceKeys/accepted/textMarkdown；如果额外提供答案 textMarkdown，也必须与富答案一致，不能用旧答案文本遮住改动后的有效 choiceKeys。
- 拆分、合并、接受 AI 建议属于既有原文 Markdown 流程；含 rich 时返回定位到 `content.richContent` 的 422 `QUESTION_RICH_CONTENT_EDIT_UNSUPPORTED`，正文要求先显式 `richContent=null` 转换。拒绝 AI 建议允许，内容和草稿修订不变。本轮不设计结构化区间拆分。
- derived-v1 纳入完整规范富内容、按序共享材料投影及核验后的真实图片 SHA-256；仅改表格跨度、图片尺寸或共享材料也改变派生值。历史旧指纹列及算法组成未修改。
- 新增图片仅允许 `blobs/<64位小写sha256>` 或兼容题库 bare SHA-256。受管根优先；合法 managed key 在受管根缺失时允许兼容题库 blob 适配。若受管文件存在但损坏，500 拒绝，不能靠兼容副本掩盖。
- 新 rich 每个图片引用必须恰好有唯一声明；`assetIds` 必须与全部图片引用同源。核对真实字节重算 SHA 和 PNG/JPEG/GIF/WebP/BMP 魔数类型；声明散列/类型失配、未登记字节等给 422。新纯 Markdown 图片同样要求合法键、已存在真实图片字节；保留的历史占位资产 ID 不被强行重写。
- `get_content_asset(kind, entity_id, asset_id) -> (bytes, media_type)` 只读当前 draft/question 内容实际引用；检查 draft 的 import owner 或 question owner。合法但未引用资产 404，非法路径 422。每次读重算字节散列，富内容还复核该修订冻结声明。root 已接两个 GET 路由，回归经过真实 HTTP 验证。
- 旧 Markdown 的三种合法存储适配均可读；编辑正式题后旧修订 JSON、引用及 blob 保留。当前修订移除引用后当前资产路由返回 404；不会删除旧修订/文件，也不伪造历史资产路由。旧修订仍可重新计算原派生指纹。
- 确认先查幂等既有事实，再做资产预检。预检在 PublicationCoordinator 与 SQL 写事务外，事务内消费绑定原草稿 revision 的结果并复核 CAS；草稿期间变化返回确认失败 `REVISION_CONFLICT`。真实字节损坏时整体零正式题、零 submission；同键同请求已确认重放即使文件后来缺失仍返回原结果。
- 总控先前 R09 任务租约/检查点修复保持；AI 整理、生成、恢复/任务引擎核心回归通过。

## 冻结投影规则

兼容派生文本作校验与检索；结构化显示仍消费富内容本体。

| 块或区域 | 投影 |
| --- | --- |
| 块间 | 空行，按块声明顺序 |
| paragraph | text，继承旧指纹的换行/空白规范化 |
| table | `[表格]` + 换行 + 原 cells 顺序文本以 ` | ` 拼接；结构/跨度保持在 rich |
| formula | 非空 LaTeX 为 `$$latex$$`；仅 OMML 为 `[原始公式]`；两者都空拒绝 |
| image | `![图片](assetId)` |
| choice answer | choiceKeys 按声明顺序以逗号空格拼接 |
| true/false answer | `true` / `false` |
| text answer | textMarkdown |
| sharedMaterials | 单独保存，按序投影纳入派生指纹，不强行拼进题干 |

## 首败与修复

`qb-rich-first.txt`：34 例中 31 通过、3 失败，exit 1。失败均在新增派生指纹测试的观测 SQL：误写不存在的 `revision_id` 列（也没有在该派生表上假设 question_id 的理由），不是业务候选断言失败。修复为已有 `catalog.derived_fingerprint(question_revision_id, algorithm_version="derived-v1")` 公共读取，分别核对旧、新修订派生值；保留原日志，不改迁移或仓储。

其后补充同步编辑/旧 Markdown 图片兼容回归，并在最后审阅补充 choiceKeys 与答案文本的权威一致性保护与回归，见末轮日志。

## 实际命令与结果

均从 `apps/api` 执行。每个命令由 PowerShell 包装：保存原 `ZQKY_DATA_DIR`，创建 `$env:TEMP/zqky-qb-rich-<guid>`，在任何 `app.main` 导入前设置该临时根；pytest 输出 Tee 到本批日志，保存 `$LASTEXITCODE`，finally 恢复原环境，再以保存退出码退出。所有 Harness 使用 `tmp_path` 的四库/受管根与 provider 替身；没有读取真实 `.env`，没有进入正式应用 lifespan，也没有启动监听端口。

```powershell
uv run --no-sync python -m pytest tests/test_question_rich_content.py -o addopts= -q --tb=short --show-capture=no
```

- 首轮：`logs/qb-rich-first.txt`；exit 1；31 passed / 3 failed / 1 warning；9.18s。
- 最后专属候选：`logs/qb-rich-correct-behavior.txt`；exit 0；39 passed / 1 warning；9.70s。此轮覆盖最后答案保护改动。

```powershell
uv run --no-sync python -m pytest tests/test_question_rich_content.py tests/test_question_bank.py tests/test_question_bank_confirm.py tests/test_question_bank_organize.py tests/test_question_generation.py tests/test_question_job_engine.py -o addopts= -q --tb=short --show-capture=no
```

- 修复测试观察方法后：`logs/qb-rich-bounded.txt`；exit 0；158 passed / 1 warning；36.01s。
- 追加同步编辑及旧 Markdown 图片三种存储兼容后：`logs/qb-rich-final.txt`；exit 0；162 passed / 1 warning；35.27s。最后仅变更富答案投影和新增该回归，因此额外窄跑专属 39 例，不重复无变化纯 Markdown/任务测试。
- 唯一 warning 为已有 Starlette TestClient 的 anyio BlockingPortal 弃用提示。

## not_run

- 全量 `npm.cmd run test:api`：未执行，本任务明确只跑有界回归，由总控串行全量。
- 根 `check`、TS/lint/build/Vitest/E2E、真实 UI/端口、真实模型调用：未执行，属于总控/前端独占集成验收；本卡不据后端回归宣称视觉已验收。
- 无推送、部署、提交、迁移/依赖变更、外部消息、真实凭证/正式数据访问。

交接后停止写入。独立验收可核对本卡及原日志，不覆盖旧审查目录证据。
