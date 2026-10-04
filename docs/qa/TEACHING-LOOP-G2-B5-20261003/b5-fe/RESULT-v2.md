# F30-L v2 作者结果卡 — 待独立验收

负责人 g2_fe；产品停止写入 2026-10-03T10:21:37.512732+00:00。本结果仅为作者窄回归，不关闭 B5。

私有清单 `PRIVATE-MANIFEST-v2.json` SHA `9f2503c5e9e5a9ffc01cd37d2703a6d007c561872ffe0419e51f09bca90e78cf`；`BEFORE-v2.json` SHA `88340b9b4d69ea9772533efb7291f27bd7cc7f530761972cce8a828f1284342f`。v1 的 834 项原证据逐项 SHA 核对零漂移；B5 冻结 33 件及冻结清单 SHA `8a19686b7b6ce6ed91e47d43c23e95bed1baccd9c2c372a5783fecd2f414d9db` 均零漂移。ROOT 独占更新模块 AGENTS，已只读采用最新实际字节并单列，原 v1/BEFORE 不追改。

| 最后完整窄检查 | 实际结果 | PID | 单轮时间 | 源漂移 |
| --- | --- | --- | --- | --- |
| f30-v2-unit-r6 | 73/73；0 failed/0 skipped | 21592 | 8274.231 ms | 0 |
| f30-v2-types-r4 | exit 0 | 11460 | 1719.499 ms | 0 |
| f30-v2-lint-r4 | exit 0；0 warnings | 25780 | 2832.717 ms | 0 |

最终一轮 5 文件、73 例 = v1 保留 50 + v2 新增 23，非跨轮累加。Node 24 固定路径、NODE_OPTIONS=--no-experimental-webstorage；最新各轮 uncaughtExceptionRecords=0。完整 argv、环境、PID、exit/ms、sourceBefore/After、日志 SHA、首败归因与原输入快照、隔离 TEMP 保留见 RESULT-v2.json 和各 command.json。

R04：点击时捕获来源/模型、正文代次、加载身份；await flush 后任一变化取消并给出说明，不自动采用新选择或旧正文。原操作在 HTTP 前同时保存完整 FrozenSubmission 与首次 source signature/epoch；unknown 深等原包重放保留原 source/edit/load。来源或模型 A→B→A 也失效；reload 旧候选保守 stale，可查看/拒绝；教师显式新点击才创建新输入。旧 job/proposal GET 不能贴到新 generation。恢复包的同 operation ID、不同首次 metadata 会暂停，原两份缓存字节不覆盖。

R05：固定报告按真实上限 200 行逐页读取至 total；total 是班级×知识点行数，读完后去重 class IDs。每页保留请求 epoch；非法 total/offset、total 改变、越界、缺失空页或读取失败可见，未采用不完整来源。已覆盖目标班级只在第 201 行，前 200 行为同班重复 KP 行，以及后页失败/空页/非法 total/变化 total。要求输入旁显示个人信息提示并有 aria-describedby。

R03 私有补充：同一文档历史→当前 copy 快照在真实 initial props 去掉 revisionId 后保留；另开文档、另一 history、本地会清 intent。leave 取消时不安装 intent；A 的迟到确认不能覆盖已由 props 选择的 B。root page key 由 CTRL 修改，不属于本实现写入。

首失败全部保留：unit-r1 68/71 为三项测试漏设 spy；lint-r1 为测试 Context Ref 别名；unit-r3 71/72 为真实 Gateway 迟到离开跨文档问题；unit-r5 72/73 为首次恢复 metadata 只比 ID 的实现问题。后两项先添加真实反例保全失败，再改产品。修后新 label，不删除用例、不弱化断言、不延长预算；所有执行输入快照 SHA 已验证。

未执行及原因：独立 V00、真实 API/RAG/model/job 和浏览器链、全量 check/build/API/e2e/chat、真实 Next/native Back、各尺寸视觉及 Word/WPS 人工版式均由 CTRL/独立验收负责；本卡仅有限私有验证。未读写正式 .env/数据/凭证/真实草稿，没有起停服务、打开浏览器或执行 Git。

所有检查子进程与日志已关闭，全部隔离 TEMP 保留。产品写权限已释放；等待 CTRL 稳定候选和独立 V00，不把替身/单测通过当真实闭环验收。

## 本批可写产品变更

- `apps/web/src/features/lesson-plan/components/DocumentGateway.tsx`
- `apps/web/src/features/lesson-plan/components/ProposalPanel.tsx`
- `apps/web/src/features/lesson-plan/components/SourcePanel.tsx`
- `apps/web/src/features/lesson-plan/lesson-workspace.test.tsx`
