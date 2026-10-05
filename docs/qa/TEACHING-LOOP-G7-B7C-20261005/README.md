# G7 两项修复与 B7-C 缺项交接（2026-10-05）

本批按用户 G7→B7-C 指令执行：[G7 两项 P2 修复并独立限定技术关闭](#关闭结论)；B7-C 因本次人类指令未给范围/授权、且无模型专属 proof 与可信 host，**真实调用 0**，只交付缺项与代码定位后 STOP。进度入口以 [CURRENT_STATUS](../../CURRENT_STATUS.md) 为准；本目录只保存本批证据。

## 关闭结论

| 分支 | 状态 | 收据 |
| --- | --- | --- |
| G7-A R-G6-WRITE-OWNER-01（写入归属闸门） | 修复 + 非作者独立限定技术关闭 | [CTRL-CLOSE-v1.json](CTRL-CLOSE-v1.json)、[V-G7-A 结果](v00/V-G7-A-RESULT-v1.md)、[V-G7-B 结果](v00/browser/V-G7-B-RESULT-v1.md) |
| G7-B R-B7B-NATIVE-01（原生页图严格解码） | 修复 + 非作者独立限定技术关闭 | 同上 + [依赖登记](dependency/REGISTER-pillow-v1.md) |
| B7-C 单模型真实试评 | **未执行（no scope/authorization/proof/host）**，real0 | [B7C 缺项交接](B7C-GAP-v1.md) |
| 教师 / Word-WPS 原生 | 仍 pending / not_run | — |
| RAG-REL 及原 B6/B7 整体、R14/CV01～03/OBS-LP-MODE-LABEL | 保持 OPEN/未关闭 | — |

## 关键证据

- 实现记录（before/after SHA 与边界）：[G7-IMPLEMENTATION-v1.md](G7-IMPLEMENTATION-v1.md)
- 受影响旧夹具登记（含旧 QA 只读与实测 8 例前置失败）：[REGISTER-affected-G6-fixtures-v1.md](REGISTER-affected-G6-fixtures-v1.md)
- 开工基线：[OPENING-v1.json](OPENING-v1.json)（main@b7f99ab、B7B-offline-r1 `08e71f7d…`、972/3771/33/970、build `wsH0-uD7VDC2ACYsbiRfS`、next-env `0f7062…`）
- 门禁：[edit/BUILD-EVIDENCE-v1.json](edit/BUILD-EVIDENCE-v1.json)（check r1 间歇 1 例、r2/r3 全绿、build `49nH0q5IXMfFQTcg4mpIR`/proxy8001、next-env 恢复）、[全量 e2e 174/174](edit/e2e-full-r1.log)、[旧 QA 首败](first-failures/oldqa-regression-r1.json)
- 独立验收：V-G7-A（[结果](v00/V-G7-A-RESULT-v1.md)/[收据](v00/V-G7-A-RECEIPT-v1.json)）12/12 审查者探针 + 24/24 自写探针（负向对照 12/24 失败）+ 页图三反例硬拒与正例/多页；V-G7-B（[结果](v00/browser/V-G7-B-RESULT-v1.md)/[收据](v00/browser/V-G7-B-RECEIPT-v1.json)）同源双页 r2b 4/4、r2（trace:on）断言全过但 runner 收尾超时（工具 finding F-G7B-02）、r1 首败为脚本断言错误保留
- B7-C：`b7c/live-refusal-no-auth/REFUSAL.json`、`b7c/live-refusal-no-proof/REFUSAL.json`（均 exit 2、realModelCalls 0）

## 边界

本批只关闭 G7 两项的限定技术范围：页图解码不签 Word/WPS 实际打开与排版；写入闸门不声称排除全部极窄并发竞态；live 未发生，B7-C/RAG-REL/教师/原生与原始台账均未关闭。未提交、未推送、未切分支、未部署；旧 QA/原材料/原 v2 任务与伪代码/Word 模板只读，TEMP 与所有首败保留。
