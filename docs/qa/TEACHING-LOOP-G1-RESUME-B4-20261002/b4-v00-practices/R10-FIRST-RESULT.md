# B4-R10-DIAG v1 · r10-first 单轮红测

仅新增两例、一次 CollectAll，**0 pass / 2 fail / 0 setup error / 0 skip**，exit1 / 2991ms；旧 R09 四例未重复执行且原源/完整 before 字节均保持 SHA `6c349f0600a50b183ac6f45f9cc92064230e3c1d7ee7f46b10ffbbffa0a22102`。候选 `CANDIDATE-b4-r8-r10-diagnostic.json` SHA `bac01e553be9724a9600f87594d411d1d986b5bd52152c99f48a48cbe6468779`、QA manifest `08ea4706fe0b3b9eb45007c3abaa074995d10a191249b69d94d78d62bf788e31` 前后 unchanged。

| 操作 | 正确行为 | 实际提交结果 |
|---|---|---|
| 标准 local-user 服务 PATCH foreign 正式题 | 404/QUESTION_NOT_FOUND，修订和内容不变 | 200；foreign revision 1→2，实际 revision 行1→2，题干追加“R10 未授权编辑标记。”；DB实际变化 |
| 标准 local-user 服务 DELETE foreign 正式题，正确 expectedRevision=1 | 404/QUESTION_NOT_FOUND，status保持confirmed | 204/空响应；foreign status confirmed→archived，revision仍1；DB实际变化 |

两个例各自新 standard-main 四库，初测真 T60 recorded0→T70 ready；共46实际HTTP、4道经上传/人工编辑/人工reviewed/confirm HTTP 建立的正式题（标准与foreign各两道）。正例保持标准对象，foreign 对象仅建负例与读取本人数据，恢复原 service 引用后才执行 PATCH/DELETE。

每个操作真实请求后，在失败断言**之前**通过 foreign service HTTP GET 读取结果，同时只读完整 questions/current_revision_id/status 和全部 question_revisions/content/metadata 行；`r10-first-evidence/r10-patch-*.json`、`r10-delete-*.json` 准确保存前后 DTO 与数据库。service引用已恢复，但从未撤销、回滚、重写任何已提交样本行或 owner；反例后态仍保留在新系统 temp。

两例的八次四库 integrity=ok，全部 FK violations=0。UTC 2026-10-02 14:01:07.1388785～14:01:10.2712541，Python 子 PID25060 已退出，两输出流关闭并经日志独占读取；stdout6372 bytes/stderr0 bytes（真实空文件）。新根 `C:\Users\96022\AppData\Local\Temp\zqky-b4-r10-r10-first-02d7c3dc2c47468683430b747183c80e`、全部受管资产/数据库保留。0监听，正式凭证未读，用户5174未操作。完整 argv/cwd/env/时长/退出/资源见 `r10-first-receipt.json`。

这是 R10 PATCH/DELETE 的实际提交级反例，与 R09 首轮 foreign GET200 合并证明三个单题入口的 owner gate 缺失；非夹具错误。所有执行源已停写，不重试、不改产品。本轮不是修复验收；CTRL 后续统一修复并另冻候选复验，B4未关闭。
