# live 首发过程发现与处置 v1（2026-10-05）

## 发现 1：live guard 的 DNS 允许路径对 bytes 主机失效（工具缺陷，已修）

- 现象：首发（v2 授权，runLabel `live-r1-C01`）3 秒失败，`UPSTREAM_UNREACHABLE`；guard `forbiddenNetworkAttempts=1`、`allowedLiveDnsLookups=0` → 发送被自己的 guard 拦在连接前，**零出网、零费用**。
- 根因（只记录不拦截的审计诊断 `tools/socket_audit_diag.py`）：`socket.getaddrinfo` 的审计参数 host 是 **bytes**（`b'api.deepseek.com'`），旧 guard 用 `str(args[0])` 比较导致永久不匹配。
- 修复：host 兼容 str/bytes（ascii 解码、去尾点、小写），port 兼容 str/int；connect 地址同样归一；注明 Windows Proactor 下 connect 审计事件可能不发出（真正生效的是 DNS 闸门）。
- 独立复验：V-LIVE-RECHECK2-v1（允许路径真实出站证明：无凭证 `GET https://api.deepseek.com/` → 401；拒绝路径与 F2 无回归；候选 diff 恰好 guard+对应测试 2 文件）。

## 发现 2：生产非流式路径 30 秒等待上限 vs `reasoning=max`（产品级事实，本批只试评规避）

- 事实：`app/providers/llm/base.py:27` `DEFAULT_TIMEOUT_SECONDS = 30.0`；非流式 `complete()` 用 `httpx.Timeout(config.timeoutSeconds)`（`:271`），即**整次生成只等 30 秒**。`deepseek-flash` 档案为 `reasoning=max`，首发（v3 授权，runLabel `live-r2-C01`）实际出站后 32 秒客户端超时，job `UPSTREAM_TIMEOUT`，账本记 unknown（上游是否计费未知，按规则 STOP）。
- 影响：**产品自身的 AI 教案生成**（教案生成走非流式 `complete()`）在该档案下同样会 30 秒超时；流式聊天不受同一上限（`read=STREAM_TIMEOUT_SECONDS`）。
- 本批处置：试评 host 显式设置等待策略 `TRIAL_CLIENT_WAIT_SECONDS = 300`（`controlled_host.py`）——**wire 不变**（preflight 前后 `wireSHA` 均为 `612c4b29…`），config identity 变化（`cf427bfe…` → `adc4a290…`）并由 `live_run` 写入 `host.json` 记录。
- 待办建议（不在本批改产品）：将非流式生成的等待上限与所选推理档位对齐（或对长生成使用流式/心跳），否则任何 reasoning 档模型都会在真实生成时超时。

## 发现 3：输入预留 698 被真实 `prompt_tokens=726` 反证（已加余量策略）

- v4 首发（runLabel `live-r3-C01`）HTTP 200、真实响应：`prompt_tokens=726 / completion_tokens=9664 / reasoning_tokens=8176 / cache hit 512+miss 214`。
- 官方分词器对同一 wire 的计数为 698 → **官方计数是估计**（与文档"estimate only"一致），API 实计 726（+28，+4.0%）；按设计 `USAGE_OUT_OF_BOUND` → 账本保留预留并 STOP（费用已发生，如实报告）。
- 同一次调用确认 **`reasoning_tokens 8176 ≤ completion_tokens 9664`**（探针包含关系成立），且该 raw 离线通过生产 `parse/normalize/validate_for_apply`（合格候选）。证据：[LIVE-C01-RECONCILIATION-v1.json](LIVE-C01-RECONCILIATION-v1.json)。
- 修复（`controlled_proof.py`，独立复验后生效）：`input_upper = count + max(16, ceil(10%·count))`（余量策略，`proof_facts.marginPolicy` 与 `reconciliationEvidence` 逐字记录）；结算硬拒不放宽。

## 授权账本事件（五本账，均保留）

| 收据 | authorizationId | 运行标签 | 结果 | 出网/费用 |
| --- | --- | --- | --- | --- |
| v1 | `6981131a…` | `vl-cur-n`（验收者负向对照） | C01 预留 17082 → unknown | guard 拦网，无出网、无费用 |
| v2 | `09633de7…` | `live-r1-C01`（CTRL 首发） | C01 预留 17082 → unknown | guard bytes-host 缺陷拦网，无出网、无费用 |
| v3 | `63e463cc…` | `live-r2-C01`（CTRL 首发继续） | C01 预留 17082 → unknown（UPSTREAM_TIMEOUT） | 实际出站；上游是否计费未知 |
| v4 | `aa448555…` | `live-r3-C01`（首发③） | HTTP 200 真实响应；prompt 726 > 预留输入上界 698 → USAGE_OUT_OF_BOUND STOP（费用已发生） | 有出站；用量 10390 tokens |
| v5 | `b6e1e9b5…` | 待发（首发继续） | 同 scope、新身份、provenance 逐字记录 v1–v4；预检通过（上界 768、预留 17152、等待 300s、wire 不变） | — |

三本旧账本原样留存于 `b7c/control-live/`，未删除、未改 label、未重置额度；v4 为同一人类指令、同一 canonical scope 下的继续授权。
