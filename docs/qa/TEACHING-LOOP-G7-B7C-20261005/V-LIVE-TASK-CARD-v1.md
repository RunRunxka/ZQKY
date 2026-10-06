# V-LIVE 独立验收任务卡 v1（live 接入失败边界，非作者）

- ID/版本：V-LIVE/v1。起点：live 接入实现已冻结（文件：`scripts/teaching-quality/{controlled_proof,controlled_host,controlled_provider,controlled_guard,controlled_trial,trial_result_check}.py` 与 `tests/test_controlled_live_v1.py`）。**你只读产品/工具源码，不修改；只写 `docs/qa/TEACHING-LOOP-G7-B7C-20261005/v00-live/`。**
- 目的：在**真实发送之前**独立核验失败边界与不可自签授权。真实发送由 CTRL 在本卡通过后进行；本卡**不得**发起任何真实模型调用、不得使用真实凭据、不得出网（tokenizer 自检除外，用已下载件）。
- 环境：Windows/Git Bash；`apps/api/.venv/Scripts/python.exe -B`；pytest 需 per-file 单跑（各测试模块自带隔离 guard，不能同进程混跑）。

## 必须独立完成的判据（自己写探针，不 import 作者测试当 oracle）

1. **授权不可自签**：`human-authorization-C01-v1.json` 结构/绑定核验；伪造 authorizationId、改 scope、fixture 名称、缺 provenance、`acceptedOption` 非注册值 → 必须 `AUTHORIZATION_INVALID`/`FIXTURE_NOT_LIVE`；任意 JSON/布尔/文件 SHA 单独不能通过 `build_live_host`（scope 漂移 → `SCOPE_DRIFT`）。
2. **proof 边界**：错误 model/host/protocol/handle → 拒绝；wire 缺 reasoning 参数、cap≠16384、多/零 cap → 拒绝；正确 wire → `input_upper` 等于官方 tokenizer+chat template 的独立计数（你自己复算，至少 2 个不同 wire，包含中文与长文本），`output_upper=16384`、`reasoning_upper=0`、`other_upper=0`；tokenizer 件 hash 必须等于仓库常量与官方 zip 解出件。
3. **usage 边界**：官方维度（cache hit/miss、prompt/completion details）接受且归一一致；未知维度、cache 不一致、reasoning>completion、input/output/total 超预留 → 各自拒绝且码正确。
4. **传输/端点**：`verify_live_transport` 拒绝 retries≠0 与非 httpx2 transport；`verify_live_endpoint` 拒绝 http、loopback、端口 9。
5. **live guard**：只允许 `api.deepseek.com:443` 的 DNS/连接；其他 host/端口、正式 `.local-data`/`.env` 读取、非 TEMP SQL 全部拒绝；离线 guard（无 live_endpoint）仍全禁网络。
6. **账本**：独立复算 attempts/预算/预留守恒；`maxAttempts` 与 `maxTotalTokens` 越界拒绝；换 label/重启/损坏账本行为与既有 fixture 判据一致（可用既有 ledger 测试的独立反例）。
7. **结果入口**：live 正例（带注册 billingProof）通过；proof 种类/tokenizer/model/wire 绑定/usage 维度/超上界任一漂移都拒绝；fixture 快照改标 live 仍被拒。
8. **负向对照**：用旧 QA 冻结的 `controlled_trial.py`（`docs/qa/TEACHING-LOOP-G6-B7B-20261005/opening-bytes/...` 若缺则从 `git show b7f99ab:scripts/teaching-quality/controlled_trial.py`）证明其 live 分支硬拒（`AUTHORIZATION_MISSING`/`BILLING_BOUND_UNSUPPORTED`），而现版在缺 receipt/tokenizer 时同样拒绝、只有具备 receipt+tokenizer 才进入 host 构建（用不存在的 receipt 触发 `AUTHORIZATION_INVALID` 等，不真实发送）。
9. 运行作者既有 5 个工具测试文件（各自单跑、各自 env）并记录结果；任何失败区分“作者自检失败”与“独立发现缺陷”。
10. 资源：全部子进程/日志关闭；无出网（除本地 tokenizer 读与 DNS 允许项）；TEMP 保留；报告 PID/argv/退出。

## 交回

`v00-live/V-LIVE-RESULT-v1.md` + `v00-live/V-LIVE-RECEIPT-v1.json`（命令 argv/PID/起止/退出/日志 SHA、逐判据 pass/fail、任何缺陷与首败原样）。不得修改工具/产品/旧 QA；不得真实发送。
