# V-LIVE 复验 3 v1（host 等待策略 TRIAL_CLIENT_WAIT_SECONDS=300，发送前最后一轮）

- 验收者：V-LIVE（独立）；日期：2026-10-06
- 背景：v3 授权首发（runLabel `live-r2-C01`）出站后 32 秒客户端超时（产品非流式默认 30s，`apps/api/app/providers/llm/base.py:27`，该档案 reasoning=max 响应超 30s，已记 `b7c/LIVE-FINDINGS-v1.md`）。修复为试评专用等待 300s。本轮复验该最小变更。
- **结论先行：pass。wire 未变（SHA 逐字节一致）、等待只作用于客户端、CTRL 自检证据全部独立复现。无回归。本轮无任何真实模型调用，无 DNS，无出站（连无凭据 GET 都没做——本卡未要求，probe6 全程 DNS 已 stub）。**

## 1. 候选核对 — pass

与 `V-LIVE-RECHECK2-v1.json` 对比，11 个候选文件中**恰好 2 个变化**，其余 9 个逐字节不变：

| 文件 | v3（RECHECK2） | v4（本轮） | 状态 |
| --- | --- | --- | --- |
| controlled_host.py | 450abc8a…de4948 | **`0bfeb76a2660e8308ae745c9b2e517c1136f19505e2c35a82155548ad9a9c25a`** | CHANGED |
| controlled_trial.py | 2353f326…17e826a | **`329e45be7d0a9b89bad16f050d9ce913d06bd4408b947ae675459412417e826a`** | CHANGED |
| 其余 9 个（proof/provider/guard/checker/common/scope/ledger/fixtures/tests/test_controlled_live_v1.py） | — | 与 RECHECK2 收据一致 | unchanged |

diff 逐行核对：
- `controlled_host.py`：新增常量 `TRIAL_CLIENT_WAIT_SECONDS = 300.0`（:39）；`build_live_host` 解析生产 handle 后用 `dataclasses.replace` 两层替换 `handle.config.timeoutSeconds`（:129-130），未触碰 apiKey/baseUrl/推理参数。注释说明 wire 不含等待参数（属实现描述，行为以 §2 探针验证为准）。
- `controlled_trial.py`：`live_run` 在 `write_artifact(output, "trial-result.json")` 之前、**开账本（`with TrialLedger(...)`）之前**写 `host.json`（:143-147），字段 schemaVersion/authorizationId/receiptSHA/modelId/modelProfileId/configIdentity/clientWaitSeconds/wireUnchanged 全部在位。
- 无夹带逻辑变更。

## 2. 行为复验 — pass（probe6，scratch 收据，DNS 已 stub，零出站）

用自建 scratch 收据（CTRL provenance 格式要求 + 自算 authorizationId，非 v1/v2/v3 任一收据；其 instruction 明示"never send"）直接 import 调 `build_live_host`：

| # | 断言 | 结果 |
| --- | --- | --- |
| 1 | `TRIAL_CLIENT_WAIT_SECONDS == 300.0` | pass |
| 2 | 返回 handle 的 `config.timeoutSeconds == 300.0` | pass |
| 3 | handle.modelId / profileId 仍为注册值 | pass |
| 4 | `config_identity` 因等待变化 | pass |
| 5 | **CTRL 声明的 identity 对独立复现**：30s→`cf427bfe6486cf12555519767c0ff40c598c04176ad458ddb58dd8ea13cfbb07`、300s→`adc4a2908af789cb62d748b342da9116dfe474b05fb0426b4525f88a4e8d35a0`，与 CTRL 自检逐字符一致 | pass |
| 6 | **wire 未变**：同一合成请求（SYSTEM_PROMPT + 合成 user 载荷、max_tokens=16384）在 30s 与 300s 配置下 `wireSHA` 均为 `d7fb8f22ebd9865cbbb6a55b3b45fcf81f89614ff15797e42c70516230523aab` | pass |
| 7 | wire 仍含 `max_tokens=16384`、`reasoning_effort=max` | pass |
| 8 | wire JSON 中不出现 "300"（等待纯客户端，不进协议体） | pass |
| 9 | `live_run` 源码中 host.json 写入先于账本打开（静态序验证） | pass |
| 10 | host.json 七字段齐备 | pass |

CTRL 自检证据复核结论：`wireSHA 612c4b29…`/`proofSHA dbe06524…` 是其真实首发链路上的值，我的 scratch 链路构造不出同值（合成请求必然不同），但**同一请求跨 30s/300s 的 wireSHA 不变性**（本轮核心判据）已独立证明，且 identity 对与 CTRL 完全一致——这只有在解析同一生产档案、替换同一 timeout 字段时才会发生，交叉印证其自检可信。

## 3. 回归 — pass

| 测试文件 | 结果 | exit | 日志 |
| --- | --- | --- | --- |
| tests/test_controlled_live_v1.py | 7 passed in 1.34s | 0 | logs/author-test-live-r4.log |
| tests/test_controlled_executor.py | 73 passed in 19.76s | 0 | logs/author-test-executor-r4.log |

## 4. 出站记录

**本轮无出站**：probe6 在 import 后立即把 `controlled_host.resolve_endpoint_addresses` 替换为返回 TEST-NET 的 stub，全程无 DNS、无 TCP、无 HTTP；scratch 收据 + stub DNS 下 `build_live_host` 仍会读正式 `.local-data` 配置与 `.env` 凭据（host 构建的固有行为，只读、不回显、不发送），这是本轮唯一对正式文件的接触。

## 5. 交回

| 项 | 值 |
| --- | --- |
| 候选 host.py | `0bfeb76a2660e8308ae745c9b2e517c1136f19505e2c35a82155548ad9a9c25a` |
| 候选 trial.py | `329e45be7d0a9b89bad16f050d9ce913d06bd4408b947ae675459412417e826a` |
| probe6 退出码 / 日志 SHA | 0 / `016984089ef81a742c974f5a90beb27eef9078b2e75c1b132fa7097075f685d9` |
| 回归 | live 7 passed；executor 73 passed（日志 SHA 见 JSON） |
| 真实模型调用 | 0 |
| TEMP 保留 | `zqky-v-recheck3-*`（scratch 收据与 results.json） |

**判定：pass。** 等待策略修复未改变 wire、未改变计费上界（wireSHA 不变即 proof 输入上界不变）、只影响客户端等待。无未登记变化，CTRL 可发 v4 首发（收据消耗语义同 RECHECK2 §5：每次首发授权一次性）。
