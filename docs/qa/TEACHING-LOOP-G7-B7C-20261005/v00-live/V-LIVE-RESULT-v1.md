# V-LIVE 独立验收结果 v1（live 接入失败边界，非作者）

- 验收者：V-LIVE（独立，非作者；只读产品/工具源码，未修改任何产品、工具、旧 QA）
- 日期：2026-10-06；任务卡：`V-LIVE-TASK-CARD-v1.md`（TEACHING-LOOP-G7-B7C-20261005）
- 结论先行：**10 项判据中 9 项 pass，1 项 fail（判据 8 的一部分）**；独立发现 3 个缺陷（F1/F2/F3），其中 F3 属于"缺 tokenizer 文件时未硬拒、反而静默进入发送路径被 guard 拦下"的边界缺陷，建议 CTRL 在真实发送前安排修复并重跑本卡对应探针。

## 0. 候选身份（验收起点冻结）

- 仓库 HEAD：`1f1b7b3`；候选为工作区文件（git status 显示工具目录有修改/新增，与本卡起点一致）。
- 候选 SHA-256：11 个工具/测试文件，验收开始与结束时逐字节一致；**完整值以 `V-LIVE-RECEIPT-v1.json` 的 `candidateSHA256` 字段为准（机器生成，杜绝手抄误差），此处不再复列表格**。

- 官方件：tokenizer.json `89085f12…9614`、tokenizer_config.json `841f8cf1…b1cb`。三方一致核验通过（仓库常量 = 官方 zip 解出件 = 探针重算；zip 原件 sha `e7310d1d…e495`，解包与仓库内 `b7c/tokenizer/extracted/` 逐字节一致）。
- 授权件：`b7c/human-authorization-C01-v1.json` sha `8880d438…8a99`；范围件 `b7c/live-scope-C01-v1.json` sha `4d64be3c…271`。
- 本卡全程：真实模型调用 0 次成功出网、未读取任何凭据值、未出网（除 guard 内白名单 DNS 判定，均被拒或仅本地判定）。唯一一次"wire 已构建、guard 拒网"的发送尝试见 F3，属缺陷复现路径，由 guard 阻止，无数据离开本机。

## 1. 逐判据结论

### 判据 1：授权不可自签 — pass（但含缺陷 F1，见 §2）

探针 `probes/probe1_authorization.py`（27 项，26 pass / 1 FAIL）：

- 独立复算 `authorizationId = SHA256(canonical{scopeSHA, acceptedOption, instruction})`，与授权件一致；scope 件与 receipt.scope 规范化一致；`acceptedOption == "B + 保留推理 + 探针"`。
- 16 个伪造变体全部以注册码拒绝：改 authorizationId / scope.modelId / maxTotalTokens / caseIds / acceptedOption / probeAccepted=false / provenance 缺失、非 CTRL、空 source / instruction 改写或空白 / schemaVersion / 多余字段 / authorizationId 传布尔或"receipt 文件自身 sha"→ `AUTHORIZATION_INVALID`；modelId/modelProfileId 含 fixture/mock/isolated → `FIXTURE_NOT_LIVE`。
- `build_live_host` 层：运行 scope 与 receipt scope 漂移（maxTotalTokens 20000→30000）→ `SCOPE_DRIFT`；任意 JSON（`{"yes":true,...}`）作 receipt → `AUTHORIZATION_INVALID`；布尔 `true` 作 receipt → **未按注册码拒绝（F1）**。
- 日志：`logs/probe1.log`。

### 判据 2：proof 边界 — pass

探针 `probes/probe2_proof.py`（22 项全 pass）：

- **独立复算**（我用 jinja2+tokenizers 直接加载官方件，不经生产 proof 代码）：短中文 wire `input_upper=7`；中英混合长文本（约 2000+ 字符）wire `input_upper=6214`。生产 proof 返回值与我的复算**完全一致**，且同 wire 复算确定性成立、不同 wire 计数可区分。`output_upper=16384`、`reasoning_upper=0`、`other_upper=0` 全部一致。
- 拒绝路径：wire model 漂移 / handle model 漂移 → `MODEL_CONFIG_DRIFT`；scope profile 漂移 / host 漂移 / protocol 漂移 → `PROOF_UNSUPPORTED`；缺 reasoning 参数 → `PROOF_UNSUPPORTED`；cap=4096 / cap=0 / 双 cap 键 / 零 cap 键 → `WIRE_CAP_DRIFT`；fixture 授权 → `FIXTURE_NOT_LIVE`；tokenizer 件缺失 / 文件中部字节篡改 → `PROOF_UNSUPPORTED`。
- tokenizer 件 hash：proof 常量 = trial_result_check 常量 = 官方 zip 解出件 = 仓库 extracted 件（四方一致）。
- 日志：`logs/probe2.log`。

### 判据 3：usage 边界 — pass

探针 `probes/probe3_4_usage_transport.py`（18 项 usage 相关全 pass）：

- 官方正例（prompt/completion/total + cache hit/miss + prompt_tokens_details.cached_tokens + completion_tokens_details.reasoning_tokens）接受且归一 `inputTokens/outputTokens/totalTokens` 与生产一致。
- 拒绝：未知维度 / 未知 detail 键 → `USAGE_UNCERTAIN`；cache hit+miss ≠ prompt → `USAGE_UNCERTAIN`；reasoning > completion → `USAGE_OUT_OF_BOUND`；input/output/total 超预留 → `USAGE_OUT_OF_BOUND`（total 恰好等于 total_upper 时接受，边界正确）；缺 completion / 布尔 / 负数 / total 不一致 → `USAGE_UNCERTAIN`；无 policy 时未知维度仍拒。
- 日志：`logs/probe3_4.log`。

### 判据 4：传输/端点 — pass

同探针（10 项 transport/endpoint 全 pass）：

- `verify_live_transport`：retries=0 原生 AsyncHTTPTransport 接受；retries=1 / MockTransport / 子类 transport → `LIVE_TRANSPORT_UNSUPPORTED`。
- `verify_live_endpoint`：http / 127.0.0.1 / localhost / 端口 9 / fixture.invalid → `FIXTURE_NOT_LIVE`；https 公网接受。

### 判据 5：live guard — pass（但含缺陷 F2，见 §2）

探针 `probes/probe5_guard.py`，四个独立子进程模式：

- live-guard：白名单 DNS（api.deepseek.com:443）允许并计数；example.com / 深度伪造域 / 端口 80 全拒。
- offline-guard：无 live_endpoint 时一切网络（DNS + connect）全拒。
- conn-guard：live 主机非 443 端口、其他公网地址 connect 全拒。
- fs-guard：正式 `apps/api/.env` 读取拒、TEMP SQL 允许、仓库树 SQL 拒；**仓库根 `.local-data/model-config.json` 读取未被拒（F2）**。

### 判据 6：账本 — pass

探针 `probes/probe6_ledger.py`（19 项全 pass）：

- 独立复算：settled 1300 后 committed=1300（settled 取代 reserved）、attempts={C01:1}、预算余量 18700；与账本快照一致。
- 越界：二次 reserve → `ATTEMPTS_EXHAUSTED`；范围外 case → `CASE_NOT_AUTHORIZED`；reserve 超总预算 / 二次 reserve 超剩余 → `BUDGET_INSUFFICIENT`；settle 超预留 → `USAGE_OUT_OF_BOUND`；重复 dispatch → `MULTIPLE_SENDS_FORBIDDEN`。
- 行为：换 label 同授权 → 尝试上限照旧、runLabel 不被改写；重启遇未结算 → 置 unknown + `RESTART_UNSETTLED_RESERVATION` + 后续 `TRIAL_STOPPED`；三处损坏（settled 超 cap、attempts 与 tickets 不符、scope 漂移）→ `LEDGER_CORRUPT`/`SCOPE_DRIFT`；cost-only scope → `COST_BOUND_UNSUPPORTED`；并发第二 owner → `LEDGER_BUSY`。

### 判据 7：结果入口 — pass

探针 `probes/probe7_result_entry.py`（11/11，真实 CLI 子进程，guard 四项计数全 0）：

- **live 正例**（我自建合成证据：注册 billingProof、cache/reasoning 官方维度、proof 上界与 usage 对齐）→ `RESULT_INTEGRITY_PASS`，exit 0。
- 10 个漂移全部拒绝（exit 2）：proof kind / tokenizer sha → `LIVE_PROOF_UNREGISTERED`；model 漂移 / wire 绑定 / usage 超上界 → `IDENTITY_MISMATCH` 族；usage 未知维度 / reasoning 超界 → 对应错误；wire 缺 cap / 缺 reasoning → `LIVE_PROOF_UNREGISTERED`；**fixture 快照改标 live → `FIXTURE_NOT_LIVE`**。
- 日志：`logs/probe7.log`（每条含 argv/exit/RECEIPTS 路径）。

### 判据 8：负向对照 — fail（缺陷 F3；其余负向对照 pass）

- **旧冻结版 hard-refuse 验证 pass**：从 HEAD `1f1b7b3` 提取旧 `controlled_trial.py`（sha `50dad45e…2843`，连同当时同目录 4 个 sibling 模块放入 TEMP），`--mode live`：无 `--authorization` → `AUTHORIZATION_MISSING`；给了真实 receipt（无 tokenizer 概念）→ `BILLING_BOUND_UNSUPPORTED`。exit 2，REFUSAL 落盘，零导入零发送。任务卡给的 `b7f99ab` 路径不存在该文件（该文件首次入树于 1f1b7b3），G6-B7B opening-bytes 快照也无 scripts 目录，故用 1f1b7b3 提取件。
- 现版缺 receipt → `AUTHORIZATION_MISSING`、缺 `--tokenizer` 参数 → `BILLING_BOUND_UNSUPPORTED`，均为发送前硬拒。
- **FAIL 项（F3）**：receipt 正常 + `--tokenizer` 指向**不存在的文件**时，CLI 不在入口硬拒，而是继续完成 receipt 校验、**读取正式凭据**、构建生产 handle、完整跑完 C01 教案准备、构建真实 wire、进入 GuardedProvider.prove——此时 `PROOF_UNSUPPORTED` 在 job 执行器内部抛出，被生产 JobEngine 捕获为 `JOB_FAILED`（"任务执行失败（内部错误）"），CLI 输出 `{"status":"live_technical_fail","realModelCalls":1,"fixtureWireSends":0}` 退出 2。真实发送被 AuditGuard 的网络钩子阻止（guard 计数 forbiddenNetworkAttempts=1、allowedLiveConnects=0），无数据离开本机，但：注册错误码 `PROOF_UNSUPPORTED` 未到达 CLI/证据面；产物带 `realModelCalls:1` 的"发送尝试"语义；与旧版"硬拒在前"的姿态相比是边界回退。证据：`logs/probe8.log`、`logs/cur-e-repro.log`、TEMP `v-cur-n/`（guard.json/trial-result.json/ledger-snapshot.json）。

### 判据 9：作者 5 个工具测试文件 — pass（各自单跑、各 env）

| 测试文件 | env | 结果 | exit | 日志 |
| --- | --- | --- | --- | --- |
| tests/test_controlled_live_v1.py | （无额外要求） | 7 passed in 1.40s | 0 | logs/author-test-live.log |
| tests/test_controlled_executor.py | （无额外要求） | 73 passed in 23.55s | 0 | logs/author-test-executor.log |
| tests/test_prepare_review.py | AUTHOR_RUN_DIR=仓库内新目录 v00-live/author-prepare-1（首次误放 TEMP 下导致 60 failed——该测试的 fixture 相对路径契约要求 run dir 在 artifactRoot 内，作者自己的 run 也是仓库内 `b7c/author-run-r2/`；复跑修正后通过） | 49 passed + 34 subtests | 0 | logs/author-test-prepare.log |
| tests/test_quality_tools.py | AUTHOR_RUN_DIR=仓库内新目录 v00-live/author-quality-1 | 52 passed | 0 | logs/author-test-quality.log |
| tests/test_trial_result_v1.py | B7B_R_RUN_DIR=仓库内新目录 v00-live/author-result-1 | 12 passed | 0 | logs/author-test-result.log |

作者自检全绿；我的独立发现（F1/F2/F3）均为作者测试未覆盖的路径，非作者自检失败。

### 判据 10：资源收据 — pass

- 所有子进程带 argv/PID/exit 记录（RECEIPT.json 汇总）；pytest、CLI、探针全部前台等待并回收。
- 出网：仅判据 5 guard 探针做了本地 socket API 级判定（拒绝即抛出，无实际连接）；F3 复现中 guard 拒绝了唯一一次连接尝试；**无任何字节到达外部主机**。
- TEMP 全部保留（44 个 `zqky-*`/`v-live-*` 目录），RECEIPT.json 记录关键路径；作者三个 RUN_DIR 在 `v00-live/` 下保留。

## 2. 独立发现的缺陷（交 CTRL 安排修复；本验收未改任何代码）

### F1（中）：布尔 receipt 触发未处理 TypeError，绕过注册错误码

- 最小触发：`--authorization` 指向内容为 `true` 的 JSON 文件（或任何非对象 JSON 顶层值）。
- 预期：`AUTHORIZATION_INVALID` 硬拒并落 REFUSAL.json（与任意 JSON 顶层对象、数组的行为一致）。
- 实际：`strict_json`（common.py:41）接受任何 JSON 顶层值；`HumanAuthorizationReceipt.load`（controlled_host.py:52）在 `set(document)` 处抛 `TypeError: 'bool' object is not iterable`。`controlled_trial.main` 只捕获 `CheckError`（controlled_trial.py:257），因此无 REFUSAL.json、无结构化错误码，进程以裸 traceback 退出 1。
- 影响：拒绝行为仍然发生（不会误授权、不会发送），但错误边界不被注册码覆盖，且工具契约（"refused 必有 REFUSAL.json"）被打破。修复建议：`load` 在 `set(document)` 前加 `require(type(document) is dict, ...)`。
- 证据：`logs/f1-bool-cli.log`、`logs/f1-bool-cli2.log`、`logs/probe1.log`（probe `host.bool-authorization-rejected`）。

### F2（中低）：live guard 的正式数据只覆盖 `apps/api/.local-data`，不覆盖仓库根 `.local-data`

- 最小触发：live guard 安装后读取 `<repo>/.local-data/model-config.json`。
- 预期：`PermissionError("formal data forbidden")`（生产正式数据根是 `<repo>/.local-data`——`apps/api/app/core/config.py:19 DEFAULT_DATA_DIR = REPO_ROOT/".local-data"`，且 `build_live_host` 读的 FORMAL_CONFIG 就在这里）。
- 实际：`AuditGuard.audit` 的 open 分支只对 `self.repository/"apps"/"api"/".local-data"`（controlled_guard.py:53-54）抛错；仓库根 `.local-data` 读取被放行。
- 影响：live 运行期间任何代码（含间接导入链）都能静默读正式学情/题库/模型配置数据，违背"正式 .local-data 拒读"的判据字面要求。修复建议：guard 的 formal 路径改为 `self.repository/".local-data"`（或两处都拦）。
- 证据：`logs/probe5-fs-guard.log`（probe `read.formal..local-data/model-config.json.refused` FAIL）。

### F3（高，建议真实发送前必修）：tokenizer 文件缺失不硬拒，静默走到发送边缘

- 最小触发：`controlled_trial.py --mode live --authorization <真实 receipt> --tokenizer <不存在的路径>`（其余同正常调用）。
- 预期：入口硬拒（如 `PROOF_UNSUPPORTED`/`BILLING_BOUND_UNSUPPORTED`），零凭据读取、零 wire 构建、REFUSAL.json 落盘——与"缺 `--tokenizer` 参数"的行为一致。
- 实际：tokenizer 仅在 `DeepseekFlashProbeProof.prove()` 内部验证（controlled_proof.py:105-106），而 prove 在 job 执行器内才被调用。时序变为：receipt 校验通过 → **SecretStore 读取正式 `apps/api/.env` 凭据** → 解析 handle → 完整 C01 教案准备（TEMP SQL）→ 构建真实 wire（model=deepseek-flash, max_tokens=16384, reasoning_effort=max）→ ledger reserve（预留 17082）→ prove 抛 `PROOF_UNSUPPORTED` → 被生产 JobEngine（engine.py:277 `except Exception:`）吞成 `JOB_FAILED` → CLI 打印 `{"status":"live_technical_fail","realModelCalls":1}` exit 2。真实 HTTP 发送被 AuditGuard 拦截（forbiddenNetworkAttempts=1），无出网，但证据面出现 `realModelCalls:1` 的发送尝试语义、账本留下 unknown 票据（账本从此永久停止——保守正确），且 `PROOF_UNSUPPORTED` 未出现在任何证据/错误面。
- 影响：这是"只有具备 receipt+tokenizer 才进入 host 构建"判据的直接违反——现版是"具备 receipt + tokenizer **参数字符串**就进入"，tokenizer 件的验证被推迟到凭据读取与 wire 构建之后。修复建议：`build_live_host` 在读取凭据前调用一次 tokenizer 哈希校验（或 CLI 入口校验 `--tokenizer` 文件存在+哈希）。
- 证据：`logs/cur-e-repro.log`、`logs/probe8.log`（probe `current.live.tokenizer-file-missing`）、TEMP `v-cur-n/`（wire.json/billing-proof.json 不存在但 frozen-input.json+wire.json 存在、guard.json forbiddenNetworkAttempts=1、ledger unknown 票据）。

## 3. 未执行项

- 真实模型调用/真实出网/凭据值读取：本卡禁止，未执行（F3 路径中凭据被 guard 保护读取由生产 SecretStore 完成，验收者未读取其值）。
- `docs/qa/TEACHING-LOOP-G6-B7B-20261005/opening-bytes/` 中冻结 `controlled_trial.py`：不存在（快照无 scripts），改用 `git show 1f1b7b3:` 提取件（任务卡 b7f99ab 备选同样不含该文件，已在 §1 判据 8 说明）。
- 未验证任何前端/视觉项：本卡不涉及。

## 4. 资源收据摘要

- 关键子进程：pytest×5、受控 CLI×9（旧 2 + 现 7）、探针×8、trial_result_check×11——argv/PID/exit 全记录于 RECEIPT.json。
- TEMP 保留：`C:\Users\96022\AppData\Local\Temp\{zqky-v-live-*,zqky-controlled-*,zqky-v-offline-*,zqky-v-conn-*,zqky-v-fs-*,zqky-v-live-ledger-*,zqky-v-live-result-*,zqky-v-live-negctl-*,v-cur-n,v-live-frozen-controlled-trial-1f1b7b3.py,v-live-old-manual-*}` 等 44 项，全部未清理。
- 日志与探针脚本 SHA 见 RECEIPT.json；所有产物位于 `docs/qa/TEACHING-LOOP-G7-B7C-20261005/v00-live/`。

## 5. 交回判定建议（供 CTRL 参考，非验收者决定）

- F3 修复前不应放行真实发送（真实发送的第一步就会在"tokenizer 件异常"场景失去硬拒保护）。
- F1、F2 为小改动（各 1-2 行守卫），可与 F3 一并修复后由 V-LIVE 仅重跑 probe1/probe5/probe8 复验。
