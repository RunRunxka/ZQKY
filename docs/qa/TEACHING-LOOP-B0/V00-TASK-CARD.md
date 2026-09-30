# TEACHING-LOOP B0 · V00 独立验收任务卡（只读）

- 版本：v1.0；建立：2026-09-30；验收者：独立验收 Agent（只读产品代码）
- 候选：B0 工作树（起点 `main@301fc356493db21d187ab85f32fd49dfffdc51ef`；冻结指纹见 `README.md`）
- 交付：`docs/qa/TEACHING-LOOP-B0/V00-REPORT-01.md`；探针放 `docs/qa/TEACHING-LOOP-B0/V00-probes/`
- 结果格式：每项 `pass` / `fail` / `not_run`，附**命令、退出码、关键输出片段、证据路径**；
  fail 必须给最小复现与首败证据（命令 + 输出 + 行号），**不要**替实现者修复。

## 边界

- 只读产品代码；探针自建在证据目录；不修改 `apps/**`、`scripts/**`、`docs/API.md` 等任何现行文件；
  不提交、不推送、不改 `.env`、不碰正式 `.local-data`（探针一律 `tmp_path` / 临时目录 + `ZQKY_DATA_DIR`）。
- 不跑 e2e/build 之外的资源重活：本批无页面改动，`npm run build` 由总控负责；你需要时可用
  `NODE_OPTIONS=--no-experimental-webstorage npx vitest run <file>` 做**定向**前端验证。
- 后端 `cd apps/api && uv run python -m pytest <file> -q`；独立探针可放 `V00-probes/` 并在报告里给运行命令。

## 必验项（逐项给结论）

| 编号 | 验收内容 | 建议手段（可自选更强的） |
| --- | --- | --- |
| V1 迁移登记 | ①重复 apply 不改变既有行/不重复登记；②中途失败迁移整体回滚（表未建、未登记）且修复后重跑成功；③篡改 `schema_migrations.sha256` 后 apply/verify 报 `SCHEMA_MIGRATION_DRIFT`；④**旧库采纳**：手工造一个没有 `schema_migrations`、但已有题库表的库 → apply 后基线被登记且既有行逐字节不变 | 自写探针脚本（不复用实现者测试的断言） |
| V2 启动门控 | ①垃圾文件/缺必需表/漂移 → 拒绝且**不重建**；②拒绝后文件句柄已释放（Windows 可删）；③缺文件放行且**不创建**库文件 | 自写探针 |
| V3 任务协议 | ①claim 递增 attempt、换 token；②未过期租约重复 claim → 409 `JOB_BUSY`；③租约过期后可接管；④心跳失权 → 返回 False 且旧 lease `complete` 抛 `LEASE_LOST`，库内结果为空；⑤取消：queued 立即 cancelled；running 置标志后 `complete` 不发布（结果不落库、状态 cancelled）；⑥`reconcile_interrupted` 只收敛 running 且幂等；⑦`retry` 保留 frozen_input/model_snapshot/input_hash 且 attempt 不变；⑧**并发上限**：独立探针证明同时进入 executor 的重任务 ≤2、模型任务 ≤1（含"等待名额期间租约不失效"这一不变量） | 自写探针（假时钟/短租约 + 计数执行器） |
| V4 提交幂等 | ①同键同 hash 重放：apply 只执行一次、返回原结果；②同键不同 hash → 409 `SUBMISSION_CONFLICT`；③`expected_revision` 不符 → 409 `REVISION_CONFLICT` 且 `exc.details["currentRevision"]` 正确；④apply 抛错 → 业务表与 submission 表都无写入；⑤非法 `table` → 422 | 自写探针 |
| V5 受管资产 | ①内容寻址 + 重复写入幂等；②篡改/缺失分别报 `ASSET_CORRUPT`/`ASSET_MISSING`；③`..`/绝对路径/盘符/错误长度键一律 422 且不创建目录；④登记行 `ref()` 为 camelCase | 自写探针 |
| V6 四库备份恢复 | ①四库 + 资产 create→verify→restore 全链路（恢复目录四库可读、`require_data_root_ready` 通过、资产逐文件散列对账）；②**缺一个库** → create 失败（清单 `status:"failed"`、说明缺哪个库、CLI 非 0、stdout 无"备份完成"）；③篡改资产字节 → verify 失败；④恢复时资产缺失 → restore 失败且 `restore-state.json` 为 `incomplete`；⑤旧 `schemaVersion:2`/legacy 清单仍可 verify/restore | 优先独立构造（可参考既有测试的 Fake Qdrant 手法，但结论必须来自你自己的构造） |
| V7 前端客户端 | ①409/422 信封的 `details`（currentRevision/issues）能到 `ApiError.details`；②`AbortError` 原样抛出且 `isAbortError` 为真（不变成 `SERVICE_UNAVAILABLE`）；③`apiRequestBlob` 返回 `{blob, fileName}`（RFC5987 解码）且失败转 ApiError；④`observeJob` 轮询至终态、`expectedAttempt` 不符返回 null、abort 返回 null | 定向 vitest（自写用例或 `npx vitest run` + 自建探针文件放证据目录） |
| V8 公共任务路由 | `GET/POST /api/v1/workflow-jobs/...`：字段 camelCase、404 `JOB_NOT_FOUND`、非法域 422、未装配 503、取消幂等、`queued/running` 重试 409 `JOB_NOT_RETRYABLE`、终态重试回 queued | 真 FastAPI + `tmp_path` 数据根（`TestClient`） |
| V9 声明抽查 | 抽查 5 条**事实性声明**是否与代码一致，例如：API.md 的四库路径/任务路由/kinds 白名单/取消语义；AGENTS.md 的迁移纪律；PROJECT_GUIDE §11 的并发上限与收敛范围；任务卡 §3.5 的列清单与 `app/core/migrations/` 实际 SQL | 读代码 + 命令输出 |
| V10 断言"有牙齿" | 挑 2 处关键断言做**变异实验**（例如把 `lease_seconds` 或 `cancel_requested` 判定临时改成错误值，在**你自己的工作副本**里跑，证明相关用例会失败；随后还原并复算文件散列证明未污染候选） | 变异 + 还原 + 散列对账 |

## 报告要求

- 开头给候选指纹（`git diff` 摘要 + 关键文件 sha256，与 `README.md` 的冻结指纹对账）。
- 每项结论 + 证据（命令/退出码/输出摘录/文件）；未执行项写 `not_run` 与原因。
- 真实模型调用、真实 DOCX/XLSX 解析、人工教学质量均为 `not_run`（本批无业务模块）。
- 发现问题的分级：`fail`（产品/契约缺陷） / `observation`（口径或文档问题） / `not_run`。
  对每条 fail 给最小复现；不得修改候选文件。
