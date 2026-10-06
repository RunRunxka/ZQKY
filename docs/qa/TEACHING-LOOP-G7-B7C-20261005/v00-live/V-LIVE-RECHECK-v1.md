# V-LIVE 复验 v1（F1/F2/F3 修复后最小复验）

- 验收者：V-LIVE（独立，非作者）；日期：2026-10-06
- 背景：`V-LIVE-RESULT-v1.md` 报告了 F1/F2/F3。CTRL 宣称已修复。本轮只按 RESULT §5 的最小复验范围重跑 probe1/probe5/probe8（F3 另加 CLI 级 scratch 收据复验与 control-live 快照核对），并对 F1/F2/F3 原始触发逐条复核。
- **结论先行：F1 pass、F2 pass、F3 pass。无回归，无未登记变化。** v1 报告的其余 9 项 pass 判据不受本轮影响（见 §5 回归抽查）。
- 约束遵守：本轮所有 CLI 级用例均使用**自建 scratch 收据**（各自不同 authorizationId）或无收据；v1 真人收据未再传给任何 CLI，v2 真人收据未触碰。`b7c/control-live/` 在复验前后快照一致（仍只有 v1 遗留的 unknown 账本，未新增目录/预留）。

## 0. 候选身份（复验起点）

- HEAD 仍为 `1f1b7b3`；修复发生在工作区文件。
- 与 v1 收据逐字节对比，11 个候选文件中**恰好 4 个变化**，其余 7 个不变（与修复声明范围一致）：

| 文件 | v1 SHA | v2 SHA | 状态 |
| --- | --- | --- | --- |
| controlled_host.py | 35a91135…c008f9 | `450abc8ad2fce7539162ee299b970d97c1d7c9a945afc9bbe6bfa96005de4948` | CHANGED |
| controlled_proof.py | d53c1b2d…7404ae | `588ee15af027edf28bf4c4b8ac6b4c66c722a0517d4a6ec6a8a6ca312d1d6ab2` | CHANGED |
| controlled_guard.py | 5b3aadb5…1a72260 | `db5bad13b7ab247b3095fd54290af17e04825427e9bfe1b4b050a3b62b1c2222` | CHANGED |
| controlled_trial.py | 3b33f851…e6d9f0f | `2353f326bc6295f1f6278035e74f61764ab747aba8362981000f9e570b0b3c41` | CHANGED |
| controlled_provider.py / trial_result_check.py / common.py / controlled_scope.py / controlled_ledger.py / controlled_fixtures.py / tests/test_controlled_live_v1.py | — | 与 v1 收据逐字节一致 | unchanged |

（v1 值截断显示；完整 64 位值在 `V-LIVE-RECEIPT-v1.json.candidateSHA256` 与本轮 `V-LIVE-RECHECK-v1.json.candidateSHA256`。）

修复点核对（读码确认）：
- F3：`controlled_trial.py:249` 在 `establish_isolation()` 与 `build_live_host()`（即任何配置/凭据读取）之前调用 `DeepseekFlashProbeProof(args.tokenizer).preflight()`；`controlled_proof.py:127 preflight()` 走 `official_token_counter()`，校验件存在 + 双固定 SHA。
- F1：`controlled_host.py:52` 新增 `require(type(document) is dict, ..., "AUTHORIZATION_INVALID")`；`controlled_trial.py:266` 新增 `except Exception` 兜底，写 REFUSAL.json（code=UNEXPECTED_REFUSAL 或异常自带 code）。
- F2：`controlled_guard.py` open 分支改为 `formal_roots = (repo/".local-data", repo/"apps/api/.local-data")` 双路径拦截，命中即 `forbiddenFormalDataReads += 1` 并抛 PermissionError。

## 1. F3 复验 — pass

进程级与 CLI 级（probe8v2，全部 scratch 收据）：

| 用例 | 触发 | 期望 | 实际 | 判定 |
| --- | --- | --- | --- | --- |
| F3.tokenizer-file-missing | scratch 收据 + `--tokenizer <不存在>` | exit 2、REFUSAL.json code=PROOF_UNSUPPORTED、realModelCalls=0 | 全部符合；输出目录仅含 REFUSAL.json 一个文件（无 frozen-input/wire/账本票据等中间产物） | pass |
| F3.tokenizer-file-tampered | scratch 收据 + 中部字节篡改的 tokenizer.json | 同上 | 同上（preflight 哈希拒） | pass |
| F3.control-live-unchanged | 复验前后对 `b7c/control-live/` 全目录快照对比 | 无新增目录/预留 | 前后一致（仍只有 v1 遗留目录 `22f47cf5…`，其账本 stopReason=UNKNOWN_MODEL_RESULT、attempts={C01:1}、1 张 unknown 票据原样保留） | pass |

顺带确认：scratch 收据自身绑定合法（自签但形状正确），因此拒绝确实发生在 preflight，而非收据校验——这正是 F3 要验证的时序。

## 2. F1 复验 — pass

- probe1 重跑：27/27 pass（v1 的 `host.bool-authorization-rejected` FAIL 项现实际为 `AUTHORIZATION_INVALID`）。日志 `logs/probe1-r2.log`。
- CLI 级（probe8v2）：布尔 receipt / 任意 JSON receipt / 形状正确但伪造 authorizationId 的 scratch receipt → 三者均 `AUTHORIZATION_INVALID` + REFUSAL.json + exit 2，`stderrHasTypeError=false`。
- 兜底路径确认：`except Exception` 分支存在（controlled_trial.py:266-275），本轮未实际触发它（因为 dict 守卫先拦截了非对象 receipt），但其存在使未预期异常不再裸 traceback。

## 3. F2 复验 — pass

- probe5 四模式重跑（独立子进程）：live-guard / offline-guard / conn-guard / fs-guard 全 pass。日志 `probe5-{live,offline,conn,fs}-guard-r2.log`。
- 原始触发精确复核（probe5b 计数器探针，`logs/probe5b-r2.log`）：
  - 安装 live guard 后打开 `仓库根/.local-data/model-config.json` → PermissionError("formal data forbidden")，`forbiddenFormalDataReads` 由 0 → 1；
  - 再打开 `apps/api/.local-data/...` → 计数 1 → 2（旧路径拦截未回归）；
  - 打开 `apps/api/.env` → `forbiddenFormalEnvReads` 0 → 1。
- 对照 v1：v1 中 FAIL 的 `read.formal..local-data/model-config.json` 现为 pass。

## 4. probe8v2 其余项（确认未因修复引入回归）

- `keep.no-authorization` → `AUTHORIZATION_MISSING` + REFUSAL.json，pass。
- `keep.scratch-authorization-no-tokenizer` → `BILLING_BOUND_UNSUPPORTED` + REFUSAL.json，pass。
- 全部 7 个 CLI 用例 `realModelCalls=0`、stdout/stderr 无任何 `chat/completions`+`200` 组合（无真实发送证据）。

## 5. 回归抽查（作者测试，per-file 单跑）

| 文件 | 结果 | exit | 日志 |
| --- | --- | --- | --- |
| tests/test_controlled_live_v1.py | 7 passed in 1.33s | 0 | logs/author-test-live-r2.log |
| tests/test_controlled_executor.py | 73 passed in 19.57s | 0 | logs/author-test-executor-r2.log |
| tests/test_prepare_review.py | 49 passed, 34 subtests in 22.85s | 0 | logs/author-test-prepare-r2.log |
| tests/test_quality_tools.py | 52 passed in 4.94s | 0 | logs/author-test-quality-r2.log |
| tests/test_trial_result_v1.py | 12 passed in 38.33s | 0 | logs/author-test-result-r2.log |

## 6. 未登记变化核查

- 11 个候选文件对比 v1：恰 4 变（controlled_host/proof/guard/trial），7 个逐字节不变。4 个变化文件的 git diff 内容经逐一阅读，全部对应三项修复（receipt dict 守卫与兜底 except、preflight 及其调用时序、guard 双 formal 根与 live_endpoint 计数器），未发现夹带的其他逻辑变更。
- `git status` 中 `apps/api/pyproject.toml`、`uv.lock`、`docs/CURRENT_STATUS.md`、`docs/qa/README.md` 等的修改为复验开始前已存在的工作区状态，非本轮产生，也不属于本卡候选范围；`test_trial_result_v1.py`/`trial_result_check.py`/`controlled_provider.py` 的 diff 亦在 v1 验收开始前已存在（v1 收据已冻结其当时 hash），本轮未再变化。
- `b7c/control-live/`：复验前后无变化；git 层面该目录被 `docs/qa/**` 忽略规则覆盖（.gitignore:35），与 v1 一致。
- 资源：全部子进程前台回收；无出网；TEMP 保留（`zqky-v-recheck-negctl-rsg6gtnm` 等，含 7 个用例的 argv/exit 收据 RECEIPTS.json）。

## 7. 判定

**F1 pass / F2 pass / F3 pass；无回归，无未登记变化。** 本卡判据 8 的 fail 已消解，v1 报告的 10 项判据在修复后候选上重新全绿。v2 真人收据未被消耗，真实发送可由 CTRL 放行（发不发送、何时发送仍由 CTRL 决定）。
