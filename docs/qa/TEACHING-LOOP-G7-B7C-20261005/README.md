# G7 两项修复与 B7-C 缺项交接（2026-10-05）

本批按用户 G7→B7-C 指令执行：[G7 两项 P2 修复并独立限定技术关闭](#关闭结论)；随后按用户下达的 **B + 保留推理 + 探针** 选项实现单模型 live 接入（host/proof/结果入口）并用用户材料跑**闭环测试**。B7-C 的真实发送在独立验收通过后执行一次（见下文）。

## 关闭结论

| 分支 | 状态 | 收据 |
| --- | --- | --- |
| G7-A R-G6-WRITE-OWNER-01（写入归属闸门） | 修复 + 非作者独立限定技术关闭 | [CTRL-CLOSE-v1.json](CTRL-CLOSE-v1.json)、[V-G7-A 结果](v00/V-G7-A-RESULT-v1.md)、[V-G7-B 结果](v00/browser/V-G7-B-RESULT-v1.md) |
| G7-B R-B7B-NATIVE-01（原生页图严格解码） | 修复 + 非作者独立限定技术关闭 | 同上 + [依赖登记](dependency/REGISTER-pillow-v1.md) |
| B7-C 单模型 live 接入（host/proof/结果入口） | 已实现 + 4 轮独立验收；B+保留推理+探针口径 | [B7C-GAP-v1.md](B7C-GAP-v1.md)、[SCOPE-INPUT](b7c/SCOPE-INPUT-deepseek-flash-v1.md)、[发现登记](b7c/LIVE-FINDINGS-v1.md) |
| **首次真实受控试评** | **成功**：C01 1 次调用，HTTP 200，用量 726/8022/8748（reasoning 6546 含于输出），settled 8748 ≤ 预留 17152，`live_technical_pass` + 结果入口 `RESULT_INTEGRITY_PASS` | [LIVE-RESULT-v1.json](b7c/LIVE-RESULT-v1.json)、[对账证据](b7c/LIVE-C01-RECONCILIATION-v1.json)、运行 `b7c/live-r4-C01/` |
| 闭环测试（用户材料，隔离真实后端） | **单轮 0 偏差**：denominators 18/19/19/19、needs 4/9/6/6，96 学生行/8 班级行与 expected.json 全等；回流后 needs→0 | [收据](loop-test/RESULT-v1.json)、[材料清单](loop-test/MATERIALS-v1.json)、[运行脚本](tools/loop_test.py) |
| 教师 / Word-WPS 原生 | 仍 pending / not_run | — |
| RAG-REL 及原 B6/B7 整体、R14/CV01～03/OBS-LP-MODE-LABEL | 保持 OPEN/未关闭 | — |

## 基线变更归因（其它会话提交）

开工 main@`b7f99ab`；会话期间用户侧提交 `0cc6094`（docs/qa 忽略+白名单）与 `1f1b7b3`（含本批 G7 修复/Pillow 登记与另一会话的"恢复阻塞/生成意图"特性）。所有产品文件 mtime 早于本批 20:48 的门禁轮，门禁覆盖该提交内容；本批不在 Git 上做任何写入。详见 [PRESERVATION-v1.json](PRESERVATION-v1.json)。

## 首次真实受控试评（成功，2026-10-06）

- 运行 `live-r4-C01`（授权 v5，authorizationId `b6e1e9b5…`，scope `365a7c93…` 与前四本账一致）：1 次无重试 HTTPS 调用，HTTP 200，用时 39s；用量 `prompt_tokens 726 / completion_tokens 8022（reasoning_tokens 6546）/ total 8748`，attempt `settled`（settled 8748 ≤ reserved 17152）；guard `forbiddenNetworkAttempts=0`、正式数据/凭证读 0、未导入 app.main。
- 工件闭合：frozenInput/raw/wire/usage/attempt/job/candidate/selectedFields/applied/billingProof/replay 全部在 `b7c/live-r4-C01/C01/`；结果入口独立核验 `RESULT_INTEGRITY_PASS`（technical_pass、fixedFacts pass、应用保护 `pass_qa_selection`、raw `hash_bound_text`、teacher/native pending、RAG-REL OPEN）。
- 探针科学结论：`reasoning_tokens ≤ completion_tokens` 两次实证（8176≤9664、6546≤8022）→ 保留推理的输出上界可核；官方分词器计数比 API 实计低约 4%（698 vs 726）→ 余量策略 `count + max(16, 10%)`；离线生产校验该候选 parse/normalize/validate_for_apply 全过。
- 边界：C01 为匿名案例（非用户班级）；teacher 须真人评审该候选；Word/WPS 未导出（`docx not_run_new_docx_not_requested`）；此成功不等于教学质量、原 B6/B7 整体或 RAG-REL 关闭。
- 知情成本：v4（10390 tokens）+ v5（8748 tokens）已知计费 ≈19138；v3 出站后客户端超时，上游计费未知。

## 关键证据

- 实现记录（before/after SHA 与边界）：[G7-IMPLEMENTATION-v1.md](G7-IMPLEMENTATION-v1.md)
- 受影响旧夹具登记（含旧 QA 只读与实测 8 例前置失败）：[REGISTER-affected-G6-fixtures-v1.md](REGISTER-affected-G6-fixtures-v1.md)
- 开工基线：[OPENING-v1.json](OPENING-v1.json)（main@b7f99ab、B7B-offline-r1 `08e71f7d…`、972/3771/33/970、build `wsH0-uD7VDC2ACYsbiRfS`、next-env `0f7062…`）
- 门禁：[edit/BUILD-EVIDENCE-v1.json](edit/BUILD-EVIDENCE-v1.json)（check r1 间歇 1 例、r2/r3 全绿、build `49nH0q5IXMfFQTcg4mpIR`/proxy8001、next-env 恢复）、[全量 e2e 174/174](edit/e2e-full-r1.log)、[旧 QA 首败](first-failures/oldqa-regression-r1.json)
- 独立验收：V-G7-A（[结果](v00/V-G7-A-RESULT-v1.md)/[收据](v00/V-G7-A-RECEIPT-v1.json)）12/12 审查者探针 + 24/24 自写探针（负向对照 12/24 失败）+ 页图三反例硬拒与正例/多页；V-G7-B（[结果](v00/browser/V-G7-B-RESULT-v1.md)/[收据](v00/browser/V-G7-B-RECEIPT-v1.json)）同源双页 r2b 4/4、r2（trace:on）断言全过但 runner 收尾超时（工具 finding F-G7B-02）、r1 首败为脚本断言错误保留
- V-LIVE（[结果](v00-live/V-LIVE-RESULT-v1.md)/[收据](v00-live/V-LIVE-RECEIPT-v1.json)）：live 接入的授权/proof/usage/传输/guard/账本/结果入口独立验收 9 项 pass、负向对照 fail；独立发现 F1（非对象 receipt → TypeError）、F2（guard 漏拦仓库根 `.local-data`）、F3（tokenizer 缺失不早拒，走到读凭据/预留后才失败）；三项已修复并通过复验触发自检，复验收据见 `v00-live/V-LIVE-RECHECK-*`
- **授权账本事件（透明记录）**：v1 收据（`human-authorization-C01-v1.json`，authorizationId `6981131a…`）的 C01 预留（17082）被验收者的负向对照运行（`vl-cur-n`）记为 `unknown`——该运行的发送被 live AuditGuard 拦截（`forbiddenNetworkAttempts=1`，无出网、无费用）；按 STOP 规则 v1 账本（`b7c/control-live/22f47cf5…`）保留且不续跑，首次真实发送改用范围完全相同的 v2 收据（`human-authorization-C01-v2.json`，authorizationId `09633de7…`，scope SHA 不变 `365a7c93…`，provenance 明确记载 v1 事件）
- 分词器与计数：官方 `deepseek_v4_tokenizer.zip` 固定件（SHA `89085f12…`），chat template + tokenizer.json 可复现计数（[自检](b7c/tokenizer/official_token_counter.py)）

## 边界

G7 只关闭两项的限定技术范围；live 接入的 proof 属"探针口径"（官方未声明 `max_tokens` 是否含推理，按用户显式接受的首发对账策略执行）；闭环测试为隔离实例真实后端 + 虚构材料，不触碰正式数据根；教师/原生/RAG-REL 与原始台账未关闭。未提交、未推送、未切分支、未部署。

