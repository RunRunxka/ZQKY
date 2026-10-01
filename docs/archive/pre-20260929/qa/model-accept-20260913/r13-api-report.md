# R-13 后端 API 层核查报告（B-MODEL-ACCEPT-R13-API v1）

- 任务卡：B-MODEL-ACCEPT-R13-API v1
- 合同版本：contract-v1（冻结 2026-09-13）
- 候选：HEAD `3dfc2fa2d90c7ceaeb953c38138165abfb9a1757`
- 范围：仅后端 API 层；浏览器首可见时间由队长测，本报告不含
- 产物：`_work/accept-model-v1/r13/probe_r13_api.py`、`results.json`、`REPORT.md`

## 0. 结论速览（证据分级）

| 结论 | 证据类型 | 出处 |
| --- | --- | --- |
| 普通（非流式）接口返回单个 JSON，不是 SSE | 真实供应商 | `results.json → real.normal` |
| SSE 流式接口事件序列正常，短问题成功 | 真实供应商 | `results.json → real.sse` |
| R-13 复现：长问题 + 默认预算零正文 `EMPTY_RESPONSE` | 真实供应商 | `real.tiers.*.a_default` |
| 显式关推理：默认预算出正文但 `finishReason=length`（截断） | 真实供应商 | `real.tiers.*.b_reasoning_off` |
| 受控 8192 + 关推理：`finishReason=stop`（完整结束） | 真实供应商 | `real.tiers.*.c_budget8192` |
| 普通调用被 SSE 体冒充会失败（判别器有效） | 隔离/MockTransport | `results.json → selftest.first_failure_preserved` |
| 正式 `.env` 与 `.local-data/model-config.json` 运行前后不变 | 隔离 | `results.json → isolation` |

**明确区分**：第 1–5 行是**真实供应商（api.deepseek.com）通过**；第 6–7 行是**隔离/MockTransport 通过**，不能当作真实上游结论。

## 1. 命令与退出码

| 命令 | 退出码 | 说明 |
| --- | --- | --- |
| `apps/api/.venv/Scripts/python.exe _work/accept-model-v1/r13/probe_r13_api.py --mode selftest` | 0 | Mock 上游，零真实调用 |
| `apps/api/.venv/Scripts/python.exe _work/accept-model-v1/r13/probe_r13_api.py --mode real` | 0 | 真实低调用量：短问题 6 次 + 长问题 7 次 |
| `... --mode all` | 0 | 自检 + 真实一次跑完（可复跑） |

脚本可复跑：已存在的 `results.json` 会被读回，仅覆盖本轮重跑的 section，因此单跑 `--mode selftest` 不会丢失真实结果。真实调用每档 1 次，问题固定，无重试。

## 2. 隔离证明（正式文件 md5 前后不变）

| 文件 | 运行前 md5 | 运行后 md5 | 不变 |
| --- | --- | --- | --- |
| `apps/api/.env` | `c56f6ffbbbc45bb99f04ce339d270f61` | `c56f6ffbbbc45bb99f04ce339d270f61` | 是 |
| `.local-data/model-config.json` | `5fc6552bdec0f20424f896c46cc5e08b` | `5fc6552bdec0f20424f896c46cc5e08b` | 是 |

隔离手段与断言（`probe_r13_api.py`，均在运行中 `assert`）：

- 配置：`shutil.copyfile` 正式 JSON 到 `tempfile.TemporaryDirectory`；`assert repo.path != 正式路径`。
- 凭证：`load_env_into_memory()` 只读正式 `.env` 进**内存** `SecretStore()`（`env_path=None`），
  `assert secrets.scope == 'process'`、`assert secrets._env_path is None`。
- 应用：`create_app(settings, repository=repo, secret_store=secrets)`，
  `assert app.state.load_env_credentials is False`（生命周期不会回写正式 `.env`）。
- 密钥不回显：报告中只出现键名 `ZQKY_API_KEY_<连接ID>` 与 `len=35`，无明文。
- 端口：应用固定 `8021`；Mock 上游用 OS 随机端口；`assert 8021 not in (8001, 5174)`。

## 3. 普通（非流式）vs SSE 的区分证据

关键点：上一轮 `r13_*.normal` 实际打的是 `POST /chat/stream`，是 SSE 体。本轮改用真正的非流式端点并加判别器
`looks_like_normal(content_type, raw)`：`content-type` 不含 `text/event-stream`、体不以 `event:`/`data:` 开头、且能被解析为单个 JSON 对象。

### 3a. 真实：`POST /api/v1/model-profiles/{id}/test`，`stream:false`

| 模型 | http | content-type | 单 JSON 对象 | isSSE | ok | finishReason | textChars | latencyMs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| deepseek-v4-pro | 200 | `application/json` | 是 | 否 | true | stop | 5 | 1948 |
| deepseek-flash | 200 | `application/json` | 是 | 否 | true | stop | 5 | 1109 |

### 3b. 真实：直接 `provider.complete`（上游 `/chat/completions` 非流式）

| 模型 | 问题 | finishReason | textChars | inputTokens | outputTokens | elapsedMs |
| --- | --- | --- | --- | --- | --- | --- |
| deepseek-v4-pro | 短 | stop | 5 | 92 | 46 | 1505 |
| deepseek-flash | 短 | stop | 5 | 39 | 62 | 1028 |

### 3c. 结构对照（请求体，真实调用前构建）

| 模型 | 普通体含 `stream` | 普通体含 `stream_options` | SSE 体 `stream=true` | 普通体注入的推理字段 |
| --- | --- | --- | --- | --- |
| deepseek-v4-pro | 否 | 否 | 是 | `reasoning_effort`, `thinking` |
| deepseek-flash | 否 | 否 | 是 | `reasoning_effort` |

### 3d. 隔离/Mock：判别器首败复现与修复验证

- 首败（原始 AssertionError，已保留在 `results.json`）：
  把 `/chat/stream` 的 SSE 体喂给普通判别器 →
  `实际 content-type='text/event-stream; charset=utf-8'，体前缀=b'event: message.start\\ndat'`。
  这复现了上一轮"用短 SSE 调用冒充普通调用"的错误。
- 修复验证：Mock 上游非流式体的 `content-type=application/json`、单 JSON，判别器通过。
- 上游请求体标志：Mock 记录到 `stream=null`（普通）与 `stream=true`（SSE）两类调用，证明两条路径在协议层就不同。

### 3e. SSE 短问题成功路径（真实）

| 模型 | 事件序列（压缩） | textChars | reasoningChars | firstTextMs(服务端) | finishReason | elapsedMs |
| --- | --- | --- | --- | --- | --- | --- |
| deepseek-v4-pro | `message.start → reasoning.delta×62 → text.delta×3 → usage → message.end` | 5 | 110 | 2100 | stop | 2101 |
| deepseek-flash | `message.start → reasoning.delta×69 → text.delta×3 → usage → message.end` | 5 | 278 | 1179 | stop | 1190 |

## 4. 三档对照（长问题，SSE 路径；每档每模型各 1 次真实调用）

档位定义（在**临时副本** profile 上设置，不动正式）：

- a 默认：`maxOutputTokens=null`、`reasoningEnabled=null` → 请求落到 `DEFAULT_CHAT_MAX_OUTPUT_TOKENS=2048`
- b 显式关推理：`reasoningEnabled=false`，预算仍 2048
- c 受控预算：`reasoningEnabled=false`（**与 b 同推理态**，为隔离"预算"单变量），请求体 `maxOutputTokens=8192`

| 模型 | 档 | 生效预算 | reasoning | finishReason | 正文 | 推理字数 | 零正文 | 截断 | 完整结束 | 首正文ms | 耗时ms | 结果 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pro | a | 2048 | null | 无(`null`) | 0 | 2738 | 是 | 否 | 否 | 无 | 33999 | `EMPTY_RESPONSE` |
| pro | b | 2048 | false | length | 3210 | 0 | 否 | **是** | 否 | 982 | 31794 | 截断 |
| pro | c | 8192 | false | stop | 8433 | 0 | 否 | 否 | **是** | 1465 | 101343 | 完整 |
| flash | a | 2048 | null | 无(`null`) | 0 | 2671 | 是 | 否 | 否 | 无 | 13473 | `EMPTY_RESPONSE` |
| flash | b | 2048 | false | length | 3033 | 0 | 否 | **是** | 否 | 900 | 13997 | 截断 |
| flash | c | 8192 | false | stop | 4585 | 0 | 否 | 否 | **是** | 718 | 19130 | 完整 |

补充普通路径对照（真实，flash 直连 `complete`，长问题，预算 2048，推理默认）：

| 模型 | 路径 | 预算 | finishReason | 正文 | 零正文 | 耗时ms | 备注 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| flash | 非流式 `complete` | 2048 | length | 0 | 是 | 13630 | 非流式 `_complete` 不做 `EMPTY_RESPONSE` 诊断，只回 `finishReason=length` + 空正文 |

读法（如实，不粉饰）：

- a 档零正文是**默认预算被推理吃光**，属于 R-13 现象；错误信封 `EMPTY_RESPONSE` 给出可操作提示，未伪装成成功。
- b 档出现正文但 `finishReason=length`，是**截断**，按约束**不得当作完整成功**。
- c 档 `finishReason=stop` 才算完整结束；这是**提高预算**而非"关掉推理让它过"，且 b 的对照证明关推理本身只解决"零正文"、不解决"截断"。
- 非流式与 SSE 对"零正文 + length"的处理不同（前者只回 finishReason，后者抛 `EMPTY_RESPONSE`），已分别记录，未混为一谈。

## 5. 首次可见时间的口径

- 本报告 `firstTextMs` 是**服务端**观测：SSE 内首个 `text.delta` 到达探针的毫秒数（pro 2100 / flash 1179）。
- 它**不等于浏览器首可见时间**；后者由队长在隔离浏览器中测，本报告不涉及、不推断。

## 6. not_run 项与原因

| 项 | 状态 | 原因 |
| --- | --- | --- |
| 浏览器首可见时间、浏览器交互/视觉 | not_run | 按任务分工由队长测，本任务禁动浏览器 |
| `/test` 端点的 b/c 档（长问题 / 2048 / 8192） | not_run | 端点硬上限：`ProfileTestRequest.maxOutputTokens` ≤1024 且服务端 `min(body, TEST_MAX_OUTPUT_TOKENS=256)`，无法表达 2048/8192；预算对照改在 SSE + 一次非流式 `complete` 做 |
| 非流式 `complete` 的 b/c 档 | not_run | R-13 是 SSE 路径现象；为保持真实调用低量，非流式只跑 a 档作对照 |
| 推理字数的非流式观测 | not_run | 非流式响应体不含 `reasoning_content`，服务端无法从 `LLMResponse` 观测 |
| 现有 profile `maxOutputTokens=384000`（flash 正式配置）的真实表现 | not_run | 不在本任务三档契约；且临时副本统一置 `null` 以保证档位可控 |
| anthropic / responses / 其它 37 个供应商 | not_run | 超出 R-13 后端 API 层范围 |
| 产品代码、docs、Git 提交 | 未改动 | 任务约束：只写 `_work/accept-model-v1/r13/`，不 commit |

## 7. 服务进程与资源释放

- 探针内 uvicorn 服务（8021）与 Mock 上游（随机端口）均在 `finally`/`stop_server` 中 `should_exit` 并 `thread.join`；`TempDirectory` 退出即删。
- 脚本为一次性进程，运行结束即退出，不常驻、不监听端口、不留下后台任务。
