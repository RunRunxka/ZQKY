# G5 后续审查入口

2026-10-05。原G5两项修复保持，新正常ACK误删外来包P2尚未修复。进度以 [CURRENT_STATUS](../../CURRENT_STATUS.md) 为准，以下只保存本次事实。

- [总审查、实跑与边界](REVIEW.md)
- [恢复归属反例及71项窄回归](recovery/REVIEW.md)
- [严格空反馈18次CLI及当前273包实核](tools/REVIEW.md)
- [B7-B真实实现依赖](next/REVIEW.md)
- [下一批提示词](../../design/teaching-loop-v1/B7B_总控启动提示词_20261005.md)
- [开工基线](BASELINE.json) / [最终保全](FINAL-AUDIT.json)

新8场景是4对照通过、4正确行为失败；不称全部通过。原窄回归71通过，工具18=4正常14预期硬拒。完整工程/浏览器/模型/教师/原生页核本次未跑。产品只读，旧QA/原计划不改；提示词已编写，修复和B7-B均未启动。
