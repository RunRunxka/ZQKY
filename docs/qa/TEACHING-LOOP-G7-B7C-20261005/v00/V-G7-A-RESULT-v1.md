# V-G7-A 独立验收结果 v1（组件反例 + 页图反例，非作者）

- 任务卡：`docs/qa/TEACHING-LOOP-G7-B7C-20261005/V-G7-A-TASK-CARD-v1.md`（V-G7-A/v1）
- 验收者：V-G7-A（非作者；只读产品、旧 QA、权威文档；只写 `v00/`）
- 执行时间：2026-10-05 20:59–21:06（+08:00），Windows / Git Bash
- 机器可读收据：`docs/qa/TEACHING-LOOP-G7-B7C-20261005/v00/V-G7-A-RECEIPT-v1.json`
  （SHA256 `fb0c06b42eec02b5f694fa1580019b068524f42bced4f2dc72132ae8186066f0`），内含 21 条命令的
  argv / PID / 起止时间 / 退出码 / 日志 SHA256、源文件前后 SHA、以及每条 CLI 的 RESULT 摘要。
- 运行记录（可复算）：`v00/logs/commands.tsv`（21 行）+ `v00/logs/*.log`（21 份，运行后重算日志 SHA 无漂移）。

## 0. 候选身份与环境

| 判据 | 结果 | 证据 |
| --- | --- | --- |
| `edit/CANDIDATE-sources-prebuild-v1.json` 的 7 个产品源码 SHA 与现场逐字节一致 | pass | `v00/V-G7-A-RECEIPT-v1.json` → `candidate.productSourcesMatchFreeze=true`；`readonlySourceIntegrity` 各 `actualAfter==expected` |
| `apps/web/next-env.d.ts` | pass（带说明） | 现场 `0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc`，等于 `OPENING-v1.json` 的 `openingBytes` 值（工作态），冻结 JSON 里的 `1862ac4b…` 是 build 后值；与任务卡“next-env 已恢复开工字节”一致 |
| 环境 | node v26.2.0 / vitest 3.2.4 / `apps/api/.venv/Scripts/python.exe` / Pillow 12.3.0 | `v00/V-G7-A-RECEIPT-v1.json` → `environment` |
| 只读边界 | pass | 每轮后 `find docs/qa -newer v00/marker-task1b-before -not -path '*v00*' -type f` 为空；`git status --porcelain` 行数 2310 前后不变；未做任何 Git 操作 |

## 1. 任务 1：审查者 write-owner 探针原样转绿

### 1.1 逐字节复制

| 判据 | 命令 | 结果 | 证据 |
| --- | --- | --- | --- |
| 原文件与复制件 SHA 相同 | `sha256sum` + `cmp` | pass | 原/复制均 `07b67087f9bd9563a98da8bfa566160bfe0d270102a86ed39ba6fa8a7a3de5b2`，`cmp` 退出 0；收据 `task1.frozenProbeCopy` |

复制件：`v00/probes/write-retry-owner-frozen.test.tsx`（未改一字节）。

### 1.2 原样运行（我写的外置配置）

命令（收据 label `task1-frozen-probe`，PID 729，2026-10-05T20:59:47→20:59:49，退出 0，日志 SHA `df7371a7…`）：

```
NODE_OPTIONS=--no-experimental-webstorage node node_modules/vitest/vitest.mjs run \
  --config docs/qa/TEACHING-LOOP-G7-B7C-20261005/v00/vitest.frozen.config.ts \
  --reporter=verbose --reporter=json --outputFile=.../v00/receipts/task1-frozen-probe.json
```

配置：`v00/vitest.frozen.config.ts`（alias `@`→`apps/web/src`、jsdom、setupFiles `tests/setup.ts`、retry 0、cacheDir 在 v00 内）。

**结果：12/12 通过**（task card 要求 8 对照 + 4 反例）：

| 分组 | 用例（create ×, import ×） | 结果 |
| --- | --- | --- |
| 对照（8） | 空键首发未发送可重试；自有原包可重试且身份不变；坏包/不可读后仍保护（各 2 kind × 2） | 8 pass |
| 反例（4） | 两 owner 同键：A 公开 write 重试必须保住 B 未知原字节；后到的首次正常发送不得替换已未知的 foreign 原包（各 2 kind） | 4 pass |

证据：`v00/receipts/task1-frozen-probe.json`、`v00/logs/task1-frozen-probe.log`（SHA `df7371a7b868d43e0108e3edfd7a29b5021223b2c7057944291b844a12f94ee0`）。

### 1.3 审查者原配置整轮交叉复核

命令（label `task1-reviewer-regression`，PID 589，21:00:08→21:00:30，退出 1=存在登记失败，日志 SHA `d1056fc7…`），配置 `v00/vitest.reviewer-regression.config.ts`。

**与审查者原配置的唯一偏离（已核 diff）**：`include` 列表逐条原样、alias/jsdom/setupFiles/retry/fileParallelism 原样；仅把 `cacheDir` 从只读旧 QA 的 `cache/vite-cache` 重定向到 `v00/.vitest-cache-regression`（硬约束要求旧 QA 只读），并把 `resolve('x')` 规范化为 `resolve(root,'x')`（cwd=仓库根，语义相同）。

**结果：10 文件 139 例，131 通过 / 8 失败**，与 `REGISTER-affected-G6-fixtures-v1.md` §3 完全一致：

| 文件（只读旧 QA） | 失败 | 失败断言（源码行） | 判定 |
| --- | --- | --- | --- |
| `docs/qa/TEACHING-LOOP-G5-REVIEW-20261005/recovery/full-cache-owner.test.tsx` | 4（create/import × success/failure） | `full-cache-owner.test.tsx:51:41` = `await waitFor(() => expect(sendB).toHaveBeenCalledTimes(1))`，实际 0 次 | 已登记前置：B 的“第二次合法正常写入同键”在新闸门下不再发送 |
| `docs/qa/TEACHING-LOOP-G6-B7B-20261005/v00/owned-ack.test.tsx` | 4（create/import × success/422） | `owned-ack.test.tsx:77:136` = 同一 `expect(sendB)`，实际 0 次 | 同上 |

- 未登记失败：**无**（8 例全部落在登记的两个文件、且原因均为“两次合法正常写入同键”前置）。
- 与实现者首败记录 `first-failures/oldqa-regression-r1.json` 对比：失败用例名集合**完全相同**（8=8，无差集）。
- 其余 8 文件全绿：cleanup-controls 2、stale-ack 1、G5 v00 recovery 28、g4-recovery 26、g5-cleanup-outcome 26、lesson-operation 5、server-session 11、审查者 write-retry-owner 12（合计 131）。

**任务 1 判定：pass。**

## 2. 任务 2：新正确行为独立探针（自写，未 import 作者测试）

探针：`v00/probes/g7-write-owner-independent-vga.test.tsx`（SHA 见收据 `task2.probeSHA256`）；配置 `v00/vitest.independent.config.ts`。
命令 label `task2-independent`（PID 108，21:02:41→21:02:42，退出 0，日志 SHA `2b94613a…`）。

**结果：24/24 通过**（每类 create/import 各一遍）。按任务卡 5 组，逐条断言与“正确行为依据”：

| # | 组 | 断言（我写的） | 结果 |
| --- | --- | --- | --- |
| 1 | create/import：B 先正常发送 unknown（status 0，真实调用 1 次）→ A 首次正常操作读到 B 完整合法原包 | A 的 send **0 次**；A **不写键**（setItem 计数不变）；B 原字节 `toBe` 逐字节保持；B `pending`/`resultUnknown`/phase=unknown 保持；A `recoveryBlocked=true`、`recoveryKind='write'`、`cacheError` 含“另一原操作”；`resultUnknown=false`（A 未发送）；等待微任务后仍阻断（不自动解锁） | 2 pass |
| 2 | A 首次写入被存储拒绝（HTTP 0）→ B 正常写入并 unknown → A 存储恢复后 `retryRecoveryWrite()` | 返回 **false**；B 原字节逐字节保持且 setItem 未再发生；A 仍阻断、`cacheError` 含“另一原操作”；A `pending` 仍是自己原包；send 仍 0 | 2 pass |
| 3a | A 写失败后键为空 | 重试 **true**；写入 A 自己原包且 `submissionId/operationId/payloadKey/payload/metadata` 逐字段相等（键集合也核对）；**不发送 HTTP**；解锁；随后显式重放（同 payload）复用同一 `submissionId/payloadKey/metadata` | 2 pass |
| 3b | 键上放 A 自己的完整包 | 重试 **true**、原字节逐字节不变（写入 1 次）；随后正常重放被允许并复用同一身份 | 2 pass |
| 4 | 保护类（坏包/坏身份/不可读/prepare 抛错/跨 context 合法包） | 每个：send **0**、setItem **0**、原字节保持（逐字节）、`recoveryBlocked=true`、`cacheError` 非空；坏身份与跨 context 的 `cacheError` 含“身份或载荷不合法” | 10 pass |
| 4b | verifyWrite=false（重试路径） | 重试 **false**、仍阻断、send 0；键上只有 A 自己的原包（= `rawOf(packetA)`，无 foreign 覆写）；随后 verifyWrite=true 时同一重试 **true** 且字节不变 | 2 pass |
| 4c | 卸载后重试 | 返回 **false**、setItem **0**、send 0、键保持为空 | 2 pass |
| 5 | B 挂载时读到自己的原包 → 显式重放 | 发送时 `submissionId/operationId/payloadKey/payload/metadata` 逐字段不变（`loadGeneration='vga-b-original-load'`、`originalEditGeneration=17` 未被新参数偷换）；发送瞬间原字节仍在；明确 422 后自己的包被清理 | 2 pass |

### 2.1 探针非空洞对照（我加的负向对照）

把本批 `opening-bytes/apps/web/src/features/lesson-plan/model/useLessonOperation.ts`（冻结修复前字节，SHA `16f38d83…`）复制到 `v00/probes/prefix/`（仅把 `'./server-cache'` import 改写为 `@` alias 以便解析），用 `v00/vitest.independent-prefix-negative.config.ts` 替换该模块跑同一套 24 例：

- 结果 **12 通过 / 12 失败**（label `task2-negative-control-prefix`，PID 143，退出 1，日志 SHA `feaa1578…`）。
- 失败的正是区分性用例：任务 2 组 1（foreign 首发）、组 2（重试 vs foreign）、组 4（非 JSON/坏身份/不可读/跨 context 保护）在修复前全部失败；修复前也不具备的“不写/不发”保护由此得到证伪能力。
- 收据 `task2.negativeControl`。结论：24/24 全绿不是空洞断言。

**任务 2 判定：pass。**

## 3. 任务 3：页图可解码三反例与正例（CLI 级）

### 3.1 复制三个旧反例运行包

用 `v00/tools/copy_tree_verify.py` 逐文件复制（源只读），每包 19 个文件全部 SHA 相同：

| 运行包 | 复制件 | 页图字节 | 页图 SHA256 | 全文件一致 |
| --- | --- | --- | --- | --- |
| 25-native-header-only-png | `v00/page-image/oracles/25` | 8 | `4c4b6a3be1314ab86138bef4314dde022e600960d8689a2c8f8631802d20dab6` | true |
| 26-native-header-only-jpeg | `v00/page-image/oracles/26` | 3 | `6e568e1f67fba258184c78181539e5e8fdee447e49bb706fc0ea34fbf12336a5` | true |
| 27-native-header-only-webp | `v00/page-image/oracles/27` | 12 | `44e65465e5e82733c8e5499cdd2fb106b8b703ea3f28da3b7da7f3a661267d6e` | true |

复制清单：`v00/receipts/oracle-copy-{25,26,27}.json`（含逐文件 SHA 与字节数）。

### 3.2 三反例 CLI

命令模板（`--manifest-sha`/`--return-sha` 用复制件实测 SHA；`--output-dir` 均为 v00 内不存在的新目录）：

```
apps/api/.venv/Scripts/python.exe -B scripts/teaching-quality/trial_result_check.py --kind native \
  --manifest v00/page-image/oracles/<N>/trial-result.json --manifest-sha <实测> \
  --case-specs docs/qa/TEACHING-LOOP-G3-B6-20261004/b6-quality/case-specs.json \
  --case-specs-sha 353e56e4f756403b8fb724b73613a2138d9d8a71ca460b3df6143e597497dd55 \
  --return-file v00/page-image/oracles/<N>/returned.json --return-sha <实测> \
  --output-dir v00/page-image/cli-out/oracle-<N>
```

| 反例 | 命令 label / PID / 起止 / 退出 / 日志 SHA | status | error.field | error.code | 旧 `native_return_integrity_pass` 出现 |
| --- | --- | --- | --- | --- | --- |
| 25 | `task3-oracle-25` / 250 / 21:03:59→21:04:00 / 2 / `310f645d…` | FAIL_NO_RESULT_PASS_PUBLISHED | `page.evidence` | `IMAGE_DECODE_FAILED` | **否** |
| 26 | `task3-oracle-26` / 265 / 21:04:00→21:04:01 / 2 / `a613365c…` | FAIL_NO_RESULT_PASS_PUBLISHED | `page.evidence` | `IMAGE_DECODE_FAILED` | **否** |
| 27 | `task3-oracle-27` / 280 / 21:04:01→21:04:02 / 2 / `428c06c6…` | FAIL_NO_RESULT_PASS_PUBLISHED | `page.evidence` | `IMAGE_DECODE_FAILED` | **否** |

结果均为 exit 2 且 code ∈ {IMAGE_DECODE_FAILED, IMAGE_RESOURCE_OUT_OF_BOUND, IMAGE_FORMAT_MISMATCH}；三个运行包的 `guard` 全 0（无网络/无 .env/无数据库/无 app.main）。证据：`v00/page-image/cli-out/oracle-<N>/RESULT.json`、`v00/logs/task3-oracle-<N>.log`。

### 3.3 我自己造的正例与扩展反例

构建：`v00/tools/make_page_image_packs.py`（label `task3-build-packs`，PID 296，退出 0，日志 SHA `27d97be8…`）以 `21-native-good` 为模板复制为 `v00/page-image/packs/21-native-good-template`，每个变体只替换页图并同步更新 `returned.json` 的 `pages[*].evidence.file/sha256`（其余字段不动）。构建记录 `v00/receipts/task3-pack-build.json`。

| 变体 | 页图字节 / SHA256 | 退出 | status | detail.status | native | createsNativeApproval | pages | humanVerdict |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| pos-png（PNG） | 77 / `c8f540e9…` | 0 | RESULT_INTEGRITY_PASS | native_return_integrity_pass | native_pending | **false** | 1 | needs_revision |
| pos-jpg（JPEG .jpg） | 634 / `29996ad8…` | 0 | 同上 | 同上 | native_pending | false | 1 | needs_revision |
| pos-jpeg（JPEG .jpeg） | 634 / `29996ad8…` | 0 | 同上 | 同上 | native_pending | false | 1 | needs_revision |
| pos-webp（WebP .webp） | 64 / `1aed4437…` | 0 | 同上 | 同上 | native_pending | false | 1 | needs_revision |
| pos-2page-png-webp（**2 页**：PNG + WebP） | 77 `c8f540e9…` + 64 `1aed4437…` | 0 | 同上 | 同上 | native_pending | false | **2** | needs_revision |

反例：

| 变体 | 构造 | 退出 | error.field | error.code |
| --- | --- | --- | --- | --- |
| neg-zero | 0 字节 | 2 | `page.evidence` | `IMAGE_RESOURCE_OUT_OF_BOUND` |
| neg-truncated | 合法 PNG 在 IDAT 内截断（47 字节） | 2 | `page.evidence` | `IMAGE_DECODE_FAILED` |
| neg-bad-crc | 改 IDAT 数据字节、CRC 不动 | 2 | `page.evidence` | `IMAGE_DECODE_FAILED` |
| neg-mismatch | PNG 字节命名 `.jpg` | 2 | `page.evidence` | `IMAGE_FORMAT_MISMATCH` |
| neg-pdf | `%PDF-1.4` 伪装 `.png` | 2 | `page.evidence` | `IMAGE_DECODE_FAILED` |
| neg-oversize | IHDR 改 30000×8 并修正 IHDR CRC | 2 | `page.evidence` | `IMAGE_RESOURCE_OUT_OF_BOUND` |

命令 label 分别为 `task3-pack-pos-*` / `task3-pack-neg-*`（PID 329–491，退出码如上，日志 SHA 见 `v00/logs/commands.tsv`）；每条 `RESULT.json` 在 `v00/page-image/cli-out/packs-<变体>/`，收据 `task3.packs.variants` 逐条登记。

边界声明：以上页图均为**合成小图，只作工具对照**，不构成真实页核、Word/WPS 打开或排版质量结论；native 仍为 `native_pending`、`createsNativeApproval=false`。

### 3.4 作者测试交叉对照（不替代我的探针）

```
B7B_R_RUN_DIR=<新 TEMP> apps/api/.venv/Scripts/python.exe -B scripts/teaching-quality/tests/test_trial_result_v1.py
```

label `task3-author-test`（PID 527，21:05:23→21:06:02，退出 0，日志 SHA `f57bb2f0…`）；RUN_DIR=`C:\Users\96022\AppData\Local\Temp\vga-g7-b7c-author-test-20261005210523`（运行前不存在）。

- `Ran 11 tests … OK`；`CLI-SUMMARY.json`：actualCalls 97 / expectedResults 97，guard 全 0，realModelCalls 0。
- `ORIGINALS-after.json`：273 个 material references 漂移 `[]`（无原件改动）。
- 且 `--output-dir` 已存在时拒绝、SHA 错配拒绝等作者自检项在本机通过。

**任务 3 判定：pass**（3.2/3.3/3.4 全部符合任务卡期待；唯一异常见 §4 观察 A）。

## 4. 观察项（非候选缺陷，按事实登记）

**观察 A（旧 QA 夹具陈旧）**：未改动的 `21-native-good` 复制件跑新 CLI 得 exit 2 / `page.evidence` / `IMAGE_DECODE_FAILED`。原因独立复核：该包 68 字节 `synthetic-page.png` 只打开到 1×1 LA，`image.verify()` 抛 `SyntaxError: broken PNG file (bad header checksum in b'IDAT')` —— 即旧“正例”页图本身不是完全可解码图，旧宽松检查曾放行。这正是 G7 严格解码要覆盖的缺口；后果是**后续任何再引用该旧包作为“好页图”的用法都必须替换页图**（我把正例重建为可解码小图后再跑即 exit 0）。证据：`v00/logs/task3-pack-21-native-good-template.log`、`v00/page-image/cli-out/packs-21-native-good-template/RESULT.json`。

**观察 B（verifyWrite=false 的写入顺序）**：`retryRecoveryWrite()` 先写入、后 `verifyWrite` 校验，因此 verifyWrite=false 时键上会出现该操作自己的原包（字节与 `rawOf(packetA)` 相同）。我据实断言“只出现自己的原字节、无 foreign 覆写、不发 HTTP、仍阻断”，而不是任务卡组 4 那句概括性的“不写入”；二者语义差异仅在此保护分支，不改变 foreign/坏包/不可读的“零写入”结论（后三者在组 4 中 setItem=0 已实测）。如总控认为 verifyWrite 分支也须零写入，可另行登记为待决项；本卡不据此判 fail。

## 5. 未执行项（明确列出）

- 真实模型/真实教师/Word-WPS 人工页核：本卡范围外，未涉及（页图为合成工具对照）。
- 273 份历史材料 live/native/teacher 验收：范围外，未执行；仅在作者测试中验证其哈希无漂移。
- 旧 QA `docs/qa/TEACHING-LOOP-G6-B7B-20261005/v00/browser/g6.spec.ts` 的 8 例双页浏览器前置：属 V-G7-B 任务卡；本卡未重跑（登记表 §3 亦标注“尚未在本批重跑”）。
- 审查者原配置的**字节原样**执行：未做（其 cacheDir 指向只读旧 QA；我以 include 逐条原样 + cacheDir 重定向到 v00 的方式复核，见 §1.3 偏离说明）。

## 6. 结论

| 项目 | 结果 |
| --- | --- |
| 任务 1（12/12 探针 + 131/8 登记回归） | **pass** |
| 任务 2（自写 24 例 + 负向对照 12 失败证实非空洞） | **pass** |
| 任务 3（3 反例 exit 2 + 5 正例/多页 exit 0 + 6 扩展反例 exit 2 + 作者测试 97/97） | **pass** |
| 候选是否发现需修复缺陷 | **无**（仅 §4 两条观察；观察 A 属旧 QA 夹具，观察 B 属措辞而非行为） |
| 只读边界与证据 | 全部只写 v00；源文件前后 SHA 与命令收据见 `v00/V-G7-A-RECEIPT-v1.json` |

停止点：本文件与收据写完后停止；未改产品、未改旧 QA/权威文档、未提交、未推送。
