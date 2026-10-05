# V-G7-A 独立验收任务卡 v1（组件反例 + 页图反例，非作者）

- ID/版本：V-G7-A/v1
- 起点：候选已冻结（本批产品源码 SHA 见 `edit/CANDIDATE-sources-prebuild-v1.json`；check r3 全绿、build `49nH0q5IXMfFQTcg4mpIR`、next-env 已恢复开工字节）。**本卡开始后产品源码停止写入；你只读产品，发现缺陷只报告不修复。**
- 可写范围：只写 `docs/qa/TEACHING-LOOP-G7-B7C-20261005/v00/`（自有 QA）。旧 QA、产品源码、权威文档一律只读。
- 语言/工具：Windows + Git Bash；Node 单测用 `NODE_OPTIONS=--no-experimental-webstorage`；Python 用 `apps/api/.venv/Scripts/python.exe -B`。
- 停止点：写完 `v00/V-G7-A-RESULT-v1.md` + JSON 收据（含每条命令的 argv/PID/起止/退出/日志 SHA/源 QA 前后 SHA）后停止；不改产品、不提交、不推送。

## 任务 1：审查者 write-owner 探针原样转绿（核心反例）

1. 把 `docs/qa/TEACHING-LOOP-G6-B7B-REVIEW-20261005/cache/write-retry-owner.test.tsx` **逐字节**复制到 `v00/probes/write-retry-owner-frozen.test.tsx`，记录原文件 SHA256 与复制件 SHA256（应相同）。
2. 在 `v00/` 写外置 vitest 配置（alias `@`→`apps/web/src`，jsdom，setupFiles `tests/setup.ts`，retry:0，cacheDir 在 v00 内），原样运行该探针：
   - 期待 **12/12 通过**（8 对照 + 4 反例：create/import × 正常首发 foreign / write 重试 foreign）。
   - 保存 vitest JSON + 日志；如未全绿，如实记录并停止扩大（不要去改产品）。
3. 交叉复核：用审查者原配置 `docs/qa/TEACHING-LOOP-G6-B7B-REVIEW-20261005/cache/vitest.config.ts` 完整跑一轮（只读；它会引用旧 QA 文件）。期待 **131 通过 / 8 失败**，失败必须是 `REGISTER-affected-G6-fixtures-v1.md` §3 登记的两个旧 QA 文件（G5-REVIEW full-cache-owner 4 例、G6 v00 owned-ack 4 例），原因都是“两次合法正常写入同键”的旧前置；任何**其它**失败都要作为未登记项报告。

## 任务 2：新正确行为独立探针（自己写，别抄作者测试）

在 `v00/probes/` 新写你自己的探针（可用与生产 hook 相同的 `browserOperationRecovery` + `useLessonOperation`，内存 Storage；不要 import 作者新测试文件当 oracle），至少覆盖：

1. **create 与 import 各一遍**：两 hook 先加载空键 → B 先正常发送并结果未知（status 0）→ A 首次正常操作读到 B 的完整合法原包：
   - A 的 send 必须 **0 次调用**；A 不得写入/覆盖键；B 的原字节（逐字节）保持；B 的 `pending`/`resultUnknown` 保持；A 进入阻断并可见原因（`cacheError` 含“另一原操作”）；A 不得自动解锁。
2. **quota 失败重试入口**：A 首次写入失败（HTTP 0）→ B 正常写入并 unknown → A 存储恢复后 `retryRecoveryWrite()` 必须 **false**、B 原字节逐字节保持、A 保持阻断、A 的 `pending` 仍是自己原包。
3. **空键/同自有包正例**：A 写失败后键为空 → 重试 true、写入 A 自己原包逐字段相等、**不发送 HTTP**、随后显式重放（同 payload）复用同一 `submissionId/payloadKey/metadata`；键上放 A 自己的完整包时正常重放允许。
4. **保护类**：坏包（非 JSON/坏身份）、不可读（getItem 抛错）、verifyWrite 为 false、prepare 抛错、跨 context 合法包、卸载后，都不写入、不发送、原字节保持。
5. **B 的原包恢复/显式重放**：B（挂载时读到自己的包）显式重放必须保持原 `submissionId`、完整 payload、metadata 逐字段不变。

每条断言写清“正确行为依据”（引用 `REGISTER-affected-G6-fixtures-v1.md`）。全部通过后把 JSON/日志/SHA 收据写入 `v00/`。

## 任务 3：页图可解码三反例与正例（CLI 级）

1. 把这三份**旧反例运行包**逐文件复制到 `v00/page-image/oracles/{25,26,27}/`（源目录 `docs/qa/TEACHING-LOOP-G6-B7B-REVIEW-20261005/results/runs/25-native-header-only-png|26-native-header-only-jpeg|27-native-header-only-webp`），记录每份 `synthetic-page.png` 原 SHA256 与字节数；**不要修改**复制件的任何字节。
2. 对每份运行包，用新输出目录执行：
   `apps/api/.venv/Scripts/python.exe -B scripts/teaching-quality/trial_result_check.py --kind native --manifest <copy>/trial-result.json --manifest-sha <实际SHA> --case-specs docs/qa/TEACHING-LOOP-G3-B6-20261004/b6-quality/case-specs.json --case-specs-sha 353e56e4f756403b8fb724b73613a2138d9d8a71ca460b3df6143e597497dd55 --return-file <copy>/returned.json --return-sha <实际SHA> --output-dir <v00 内不存在的新目录>`
   - 期待 **exit 2**、`error.field == "page.evidence"`、`error.code ∈ {IMAGE_DECODE_FAILED, IMAGE_RESOURCE_OUT_OF_BOUND, IMAGE_FORMAT_MISMATCH}`；旧的“native_return_integrity_pass”必须不再出现。
3. 正例与扩展反例（自己造包，不重制旧 273 包）：以 `21-native-good` 运行包为模板复制到 `v00/page-image/`，仅替换页图并同步更新 `returned.json` 的 `pages[*].evidence.sha256`（与文件名扩展名）：
   - 合法可解码 PNG、JPEG(.jpg)、JPEG(.jpeg)、WebP：exit 0、`detail.status == "native_return_integrity_pass"`、`native == "native_pending"`、`createsNativeApproval == false`；再做一份 **2 页**（PNG+WebP）返回验证多页正常。
   - 反例：零字节、截断正文、坏 CRC（改 IDAT 数据字节不改 CRC）、格式/扩展名错配（PNG 字节命名 .jpg）、PDF 伪装、超资源（IHDR 改大且修正 IHDR CRC）：全部 exit 2 且 `error.field == "page.evidence"`。
   - 合法合成小图只作工具对照；不得写成“真实页核/Word-WPS 打开通过”。
4. 运行 `scripts/teaching-quality/tests/test_trial_result_v1.py`（作者专属测试，`B7B_R_RUN_DIR` 指向新 TEMP）做交叉对照并记录结果（它是作者自检，不替代你的独立探针）。

## 交回格式

`v00/V-G7-A-RESULT-v1.md`：每条判据 → 实际命令 → 实际结果（pass/fail/not_run）→ 证据文件路径与 SHA；另附 `v00/V-G7-A-RECEIPT-v1.json`（机器可读）。任何失败/未执行都必须如实列出，不得拼轮计绿；不得修改产品、旧 QA 或权威文档。
