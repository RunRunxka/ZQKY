# B7-C 真实调用缺项与代码定位交接 v1（STOP，real0）

2026-10-05。**结论：本批没有可信真实授权与范围，也没有模型专属完整上界证明；按用户指令“范围缺失不猜测，不调用真实模型”，B7-C 不执行真实发送。真实调用 0、attempts 0、预算消耗 0、unknown 预留 0。** 本文件只登记事实、现行代码位置与用户需补的最小输入，不制造“离线 B7 准备已完成”，不扩成通用 live 平台。

## 1. 授权核验（CTRL 按本次直接人类指令核验）

- 本次直接人类指令（G7→B7-C 提示词正文）**未填写**范围表：`modelProfileId / modelId / caseIds / sampleCount / maxAttempts / maxTotalTokens（或费用上限）/ 真实调用授权` 均为空。原文只写“在用户给定目标模型与范围内执行 B7-C”，未给出任何具体值。
- 指令同时明确：“真实调用需要当前人类明确授权、模型专属完整上界证明和可信宿主三项同时满足；范围缺失不猜测，不调用真实模型。”
- 因此 `trustedHost.verifyActualHumanInstruction(currentHumanRequest)` 在本次输入上 **不成立**：没有可核验的授权收据来源、没有稳定 `authorizationId`、没有不可变 scope。任意 JSON、`human_verified=true`、文件 SHA 或 `--live` 开关都不是授权来源（`controlled_scope.py:38-45` 的布尔只是声明位，本批未用它生成任何收据）。
- 现状实测（新 TEMP/新输出目录，无网络、无凭证、无正式库；`b7c/`）：
  - 无授权：`--mode live` → `AUTHORIZATION_MISSING`，exit 2，realModelCalls 0（`b7c/live-refusal-no-auth/REFUSAL.json`）。
  - 提供任意 JSON 作为 `--authorization`：→ `BILLING_BOUND_UNSUPPORTED`，exit 2，realModelCalls 0（`b7c/live-refusal-no-proof/REFUSAL.json`）；该 JSON 未被当作授权，仅证明“任意文件不能自签”。

## 2. 当前 live 能力与缺项的精确位置

| 能力 | 现行状态 | 代码位置 |
| --- | --- | --- |
| live CLI 入口 | 显式硬拒（无 proof/授权接入） | `scripts/teaching-quality/controlled_trial.py:188-193` |
| 宿主 DI 缝（生产 prepare/build_request/execute、JobEngine、三协议 Provider、无重试 transport） | 已有接口，但仅供受信宿主注入 | `controlled_trial.py:49-60`（`execute_case` 文档串）、`:73-99`（executor 注入）、`:131-168`（fixture host `dry_run`） |
| scope 形状与预算上限字段 | 已实现（`maxTotalTokens` 模式；费用模式拒绝） | `scripts/teaching-quality/common.py:127-139`、`controlled_scope.py:71-81` |
| 人类授权校验 | **缺可信实现**：`AuthorizedScope.validated` 只检查字符串与布尔，无来源验证 | `controlled_scope.py:38-45` |
| 模型计费证明注册表 | **缺**：只有 `UnsupportedLiveProof`（永远拒绝）与 `FixtureBillingProof`（仅 fixture，`noRealModelSupport: true`） | `controlled_scope.py:84-101` |
| 最终 wire 与证明绑定 | wire SHA、输出 cap、input/output/reasoning/other 上界检查已实现 | `controlled_scope.py:71-81`（`BillingBound.verify`） |
| live transport 策略 | 已实现：必须是未改装的 `httpx.AsyncHTTPTransport`、`_retries == 0`、HTTPS 非回环、排除 fixture 端口 9 | `controlled_provider.py:55-67` |
| 发送守卫/预留结算/未知保留 | 已实现（单次发送、预留、无法确认不归零） | `controlled_provider.py:142-180` |
| 授权账本（跨 label 累计、重启、损坏拒绝、排他锁） | 已实现；namespace 固定为 `docs/qa/TEACHING-LOOP-G6-B7B-20261005/executor/control-state` | `controlled_trial.py:22`、`controlled_ledger.py:56-59` |
| 离线 guard（禁网络/正式 env/正式库/main） | 已实现 | `controlled_guard.py:1-40` |
| 生产配置/凭证读取入口（live 应复用） | 已存在，未接线：`apps/api/app/services/model_config_service.py`（profile）、`apps/api/app/core/secrets.py`（`SecretStore`）、`apps/api/app/services/model_auth.py`、`apps/api/app/services/model_runtime.py`（`resolve_frozen_model`/`build_provider`/`fingerprint_of_handle`） | 见文件 |
| 结果入口 live provenance | 明确拒绝 live 结果（`LIVE_RESULT_SUPPORT_UNREGISTERED`）；未注册真实来源/usage 证明接入 | `trial_result_check.py:225-229`（`manifest_check` live 分支） |

## 3. 用户需补的最小事实（缺一不可，任一缺失即保持 real0）

1. `modelProfileId`（后端已配置 ID）与 `modelId`（实际模型 ID，与 profile 一致）。
2. 精确 `caseIds`（原 15 案例中的完整 ID 列表）与等长 `sampleCount`。
3. `maxAttempts`（每例上限，失败与可能送达上游的发送均计入）。
4. `maxTotalTokens`（可执行的整轮累计上限；费用模式当前不支持，若只接受费用上限，需要先交付所选模型价格/币种/收费项证明与实现）。
5. 明确文字授权“按上述范围调用真实模型”；范围变更需新授权。
6. 一个**可信宿主**：可从本次人类指令/可验证授权上下文核验授权并按 `authorizationId` + 不可变 scope 开账本（不能由任意 JSON、布尔或文件 SHA 自签）；密钥不进入 scope/材料/日志。
7. 所选模型**专属 proof**：最终发送 input 的可信上界、output cap 在该模型/协议的真实语义、reasoning/cache/其他 token 是否包含与是否可限制、返回 usage 各维归一与核账方式；只能用官方协议事实与可复现计数/能力证据，不能字符估计/默认费率/仅填数字。
8. （仅在用户选择本地模型时）Ollama 等本地宿主的真实模型与计数/usage 能力证明、精确 endpoint 策略与独立反证。

教师评价与 Word/WPS 原生页核可独立并行，不阻塞已获准的 live 技术试评；但原 B6/B7 整体不能因本批或未来单模型试评自动关闭。

## 4. 本批边界

- 未重写 `controlled_ledger` / 旧 `aggregate/preflight/prepare` / 生产业务 prompt；未新增业务 API、迁移或依赖（Pillow 仅为页图解码登记，见 `dependency/REGISTER-pillow-v1.md`）。
- 未迁移/改动任何既有授权账本；本批未打开固定 control namespace（live 拒绝发生在开账本之前）。
- 未使用、未记录任何真实凭证；无网络出站；正式业务数据库、真实草稿与 6333 未读写。
- 结果入口的“live provenance/usage proof 接入”（R 卡第二阶段）因无真实模型与真实发送，保持 not_run；未单改 evidenceKind 或把 fixture 转签 live。
