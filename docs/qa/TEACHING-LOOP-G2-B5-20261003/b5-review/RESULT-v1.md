# B5-REVIEW v1 初轮结果

2026-10-03；独立静态审查完成，释放席位供 T90-AI v2 修复。详细触发/预期/实际/文件行与最小反例见 [STATIC-REVIEW-v1.md](STATIC-REVIEW-v1.md)，SHA `787707abd88e9c702a5f37c63c02cc65b077cb585d5badf7480ff2d0d98e3a18`。

- B5R-R01（P2）：合法短数字学号与必发匿名别名/匿名统计值碰撞。当前 AI v1 未修；CTRL 已决定原作者新 v2 私有修复。
- B5R-R02（P2）：SQL 字面量/JSON path 被 lower 后漏过结构体检。CTRL 在审查期间已授权修复；原件保存 `ctrl/lesson-schema-gate-before-literal-v2.bin`。CTRL 回报公共 9 + B5 DB/恢复 1，新完整 10/10、exit0/3552.456ms、5 源零漂移，并有两种真实 SQLite 变异被拒绝。该结果是 CTRL 自检回报，本审查**没有独立执行或将其关闭**；原缺陷判定保留，稳定候选再由独立 V00 复核。

源绑定合计 56 件。开工 22 私有文件与 BE v2 / AI v1 作者清单一致；终点私有源零漂移。唯一前后差异为 CTRL 已授权的 R02 修复：lesson_schema_gate.py `cebb4e31d3c0e2527a53acdb4555129e77bf765326f9dfdfc354b37466382c4d` → `bd2a61e7d283635016cb28fa21496c0e5c10b81185d0bea8615541ac71856cbc`。

前清单 SHA：`SOURCE-BEFORE-v1.json` = `10925bfe9dcb9af3b0a40b3af9d5e6a2c9fe3947af5d2ec194c811e2492e68ae`；补充 CTRL 前清单 = `0b543f0fcb55fb0c5f183f3a0ea2c46d3a87864ab03d073cca40c472ab54db42`；后清单 = `821f6ade879d89cd465f513eafb837f3ddd7ecf49c7227980b2015e2c661bfab`。

没有其他已经确认但未即时提交的具体缺陷。FE/session/nav/cache/export 等留待停写候选继续只读窄审；不据本轮静态阅读批准完整 B5。未执行 oracle、业务/浏览器门禁、任何 TCP、迁移/恢复、模型调用或 Git；未访问正式数据/凭证/真实草稿；写入仅本 b5-review 目录的新报告和清单。
