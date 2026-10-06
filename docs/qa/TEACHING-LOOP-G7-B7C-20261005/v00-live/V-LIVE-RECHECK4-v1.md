# V-LIVE 复验 4 v1（proof 输入上界余量策略，v5 首发前最后一轮）

- 验收者：V-LIVE（独立）；日期：2026-10-06
- 背景：v4 首发（runLabel `live-r3-C01`）HTTP 200，API `prompt_tokens=726` 高于官方计数 698（+28），未加余量的 `input_upper=698` 触发 `USAGE_OUT_OF_BOUND`，账本按设计 STOP（费用已发生，如实记录）。修复：上界 = 官方计数 + 余量，对账硬拒保持不变。
- **结论先行：pass。余量公式独立复现、真实 C01 wire 独立重计 698（与 CTRL 一致）、新上界 768 ≥ 观测 726、margin 事实入 proof_facts 且经 proofSHA 哈希绑定、结算硬拒未放宽。无回归、无未登记变化。本轮零出站。**

## 1. 候选核对 — pass

与 `V-LIVE-RECHECK3-v1.json` 对比，11 个候选文件中**恰好 2 个变化**，其余 9 个逐字节不变：

| 文件 | v4（RECHECK3） | v5（本轮） | 状态 |
| --- | --- | --- | --- |
| controlled_proof.py | 588ee15a…6a8a6ca | **`52cb9311efd829f1a2ecc73af3f57b77d045a7dd77b24d8cb7d25f583cfd8a88`** | CHANGED |
| tests/test_controlled_live_v1.py | aa9350ca…f6e7a4 | **`0f2aae88ad7047aea1f30222e693cb90f9b931ac98418554488045c6773281a3`** | CHANGED（作者的余量断言，配套测试） |
| 其余 9 个 | — | 与 RECHECK3 收据一致 | unchanged |

diff 核对（`controlled_proof.py`，逐行）：
- 常量：`COUNT_MARGIN_RATIO=0.10`、`COUNT_MARGIN_ABS=16`（:66-67），`RECONCILIATION_EVIDENCE` 字典（:68-77）；
- `input_upper_for(count) = count + max(16, ceil(10%*count))`（:82-84，函数内局部 `import math`）；
- `prove()` 改用 `raw_count = official_token_counter(...)(wire)`，`input_upper = input_upper_for(raw_count)`（:128-129）；
- facts 新增 `marginPolicy` 与 `reconciliationEvidence`，并把 `frozenInputUpper` 改为 `frozenInputCount`/`frozenInputUpper` 两个字段（:131-137）；
- `wireSHA/caps/reasoning_upper=0`、结算 `usage>预留 → USAGE_OUT_OF_BOUND` 均未动。

## 2. 行为复验 — pass（probe7，19/19，scratch 收据、DNS stub、零出站）

探针自带独立计数器（jinja2 模板渲染 + 官方 tokenizer.json encode，不经 `controlled_proof` 代码）：

| # | 断言 | 结果 |
| --- | --- | --- |
| 1 | 余量公式：三条合成 wire（短中文/中英混合/长文）`input_upper == count + max(16, ceil(10%*count))`，margin 随计数从 16→绝对值档正确切换 | pass（3 条 + reasoning/other==0 共 6 项） |
| 2 | **真实 C01 wire**（`b7c/live-r3-C01/C01/wire.json`，文件 SHA `fb9e8442…c1aa` 与对账文件一致）：我的独立重计 = **698**，与 CTRL/对账文件一致 | pass |
| 3 | 新 `input_upper = 698 + max(16, 70) = 768` ≥ 观测 API `prompt_tokens=726`；同时确认旧上界 698 < 726（原触发路径复核） | pass |
| 4 | `proof_facts.marginPolicy`：ratio=0.10、absoluteAdd=16 | pass |
| 5 | `proof_facts.reconciliationEvidence`：tokenizerCount=698、apiPromptTokens=726、delta=28、wireFileSHA256、包含关系确认（completion 9664 ≥ reasoning 8176）、离线候选校验记录——与 `LIVE-C01-RECONCILIATION-v1.json` 数字一致 | pass |
| 6 | margin 事实的持久化：`bound.proof_facts` 含 marginPolicy/reconciliationEvidence，`proofSHA = sha(proof_facts 全量)` 哈希绑定（persisted `billing-proof.json` 文档内嵌常量，余量事实经 proofSHA 提交，`boundProofSHA` 记入账本票据——设计如此，非缺陷，已记录） | pass |
| 7 | **结算边界严格**：`prompt_tokens = 768`（恰等于上界）接受；`prompt_tokens = 769`（上界+1）→ `USAGE_OUT_OF_BOUND`；reasoning ≤ completion 仍接受 | pass |

对账文件交叉核对：`upstream-usage.json`（sha `13ac9652…8569` 与对账一致）rawUsage `prompt_tokens=726 = cache hit 512 + miss 214`，`completion_tokens=9664 ≥ reasoning_tokens=8176`，HTTP 200，`realModelCalls=1`、`stopReason=USAGE_OUT_OF_BOUND`——与 CTRL 叙述一致。

## 3. 回归 — pass

| 测试文件 | 结果 | exit | 日志 |
| --- | --- | --- | --- |
| tests/test_controlled_live_v1.py（含作者新增余量断言 :94-99） | 7 passed in 1.37s | 0 | logs/author-test-live-r5.log |
| tests/test_controlled_executor.py | 73 passed in 19.59s | 0 | logs/author-test-executor-r5.log |

## 4. 出站记录

**本轮零出站**：probe7 stub 了 `resolve_endpoint_addresses`，全程无 DNS/TCP/HTTP；scratch 收据，v1–v4 真人收据未触碰；`control-live/` 四个账本目录复验前后未新增。

## 5. 备注

- 余量上界 768 的含义：官方计数 698 + 10% 余量 70。若 provider 偏差再次超过 10%，结算硬拒会按设计 STOP——余量策略不掩盖真实的上界失守，只是给确定性计数加上可复核的缓冲。
- margin 事实进入 `proof_facts`（即进入 `proofSHA`/`boundProofSHA`），但不在 `billing-proof.json` 文档字段中显式出现。对账时如需人读余量依据，可从对账 JSON 与本报告获得；如 CTRL 希望文档字段直读，需要再动 `trial_result_check.LIVE_PROOF_FIELDS`（本卡范围外，仅提示）。
- probe7 初版 harness 有 4 处自我断言写法错误（containment 字符串比对、接受语义标记），修正后 19/19；候选行为自始正确。

## 6. 判定

**pass。** 候选可在 v5 首发时使用（收据单次授权语义同前）。
