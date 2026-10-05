# V00-P v1 独立产品验收

2026-10-05；负责人 g4_v00_product。只读产品、旧 QA、权威文档与 Git；仅写本目录。用户限定离线工具与验收准备：真实模型 0、教师评分 pending、Word/WPS 原生排版 not_run。

开工已读用户 G4 授权、根/web/lesson AGENTS、教案模块说明、CURRENT_STATUS、OPENING-v1 与 TASK-CARDS-v1，保留外部 main@b7f99ab UI/GSAP。Next 资料取本地安装版本的 Server and Client Components。G4-S 作者 STOP SHA 0fa3acc0bc0f8f3ff35e2fa5aa013f05b6dd8f72256c163002926188faa31a1e；G4-E 尚待作者 STOP，故本方案与手写 oracle 准备不计通过，也不先跑漂移候选。

## 手写正确行为

| 边界 | 公共动作与独立预期 |
| --- | --- |
| 临时 quota | 真实 LessonPlanWorkspace 编辑→失败→公开重试；完整11字段/process.secondary/context/source/全部操作先持久化且读回一致，0 HTTP；随后显式保存仅一次，并能离开 |
| 持续失败/静默丢写 | 公开多次重试仍锁正文/保存，全部新稿和原身份保留、0 HTTP；读回不一致也不能解锁 |
| 发送前原包 | 捕获首次失败写中的冻结包；恢复后 submissionId/payload/metadata/edit/ACK/CAS 全等，显式原包重放只发一次 |
| unknown | 第一次实际请求失去响应；缓存写再失败→恢复只持久化；显式重放原 submissionId 与 payload，不能生成新身份 |
| known ACK | 已收到明确成功但清理写失败；公开恢复清理只更正缓存，HTTP 总数仍1，ACK 与 CAS 保持 |
| 冲突 | 已知后台较新后恢复缓存进入人工对照，本机正文及旧 CAS 保持，恢复本身0 HTTP |
| 读取损坏 | 原字节/读异常不可覆盖；恢复入口不可发送，不把坏包当空库 |
| 跨文档 | 旧重试迟交不解锁新会话，不回退其 CAS/正文 |
| create/import | 发送前冻结失败发布 recoveryBlocked，三种离开写决策均拒绝；公开原操作缓存重试释放的仅为同身份写失败；明确 ACK 清理不重复创建 |
| generate/apply/reject | 可信原包失败后，恢复不 release/重建身份；generate 首次 selectionKey/sourceEpoch 不被后来输入粘贴替换；读取坏包继续阻断；apply/reject 重放及可信 ACK 清理保持原契约 |
| 教材 clear | getSource 和 verify 两阶段 × 当前 evidence 空/非空；明确清除即使 null→null 撤销旧结果/错误；双清除、新核验可采用 |
| 其他来源 | clear 仅撤销教材 intent，不取消题库/练习列表/metadata/report owner；题/练习选择及教师输入保留 |
| 原守卫 | grade/edition、文档/store/session/discard 不采用旧来源；documentId/start/end 参数编辑继续原“准备下一片段”语义，不新增取消约定 |

公共工作台的发送动作只点击公开按钮，观察完整注入 Storage 和手写 API 替身；读值探针不得调用私有 save/recovery 作为通过证据。操作 hook 窄反例仅补接口边界，不替代公共 UI。替身验证不是本次真实后端/浏览器。

ROOT 的 v00/browser/g4.spec.ts 与 source-clear.spec.ts 只读核 oracle：实际 route.fetch 响应持有/清除/释放，新来源生成请求不得带已清来源；四视口与键盘恢复、真实全正文/历史数量需实际运行后单列。V00-P 不开服务、浏览器、网络、app.main 或 .env。

## 稳定候选与结果记录

等待 ROOT 提供全部产品 STOP SHA 与正式候选，运行前后逐文件 SHA 对比。每轮独立完整执行，保存命令、PID、起止、耗时、退出码、JSON 单轮计数及原日志；首败不覆盖。遇产品失败先报 ROOT，不修产品/放宽 oracle；修复后新冻结并运行新完整单轮。既有 Source8/B6 作者及 G3/edit 回归可按影响单独单轮引用，不拼各轮通过片段。完整 check、当前174 E2E和真实故障浏览器由 ROOT 集成，未执行的项目明确未执行与原因。
