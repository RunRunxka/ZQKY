# B5R-R07-STATIC-DIAG-v1 — 本地教案快速导航回归

- 负责人：/root/b5_r06_review；诊断对象：ROOT r5 原完整 153 first 的两例失败。
- 确认 P2 R07：普通本地教案在 600ms 自动保存窗口内立即点侧栏，原先“先 flush 再导航”被统一离开保护变成必须人工回答的弹窗；即使随后保存成功，导航仍不继续。
- 不是已确认的 global guard 拒绝成功 flush：普通本地 leave ask 根本没有先调用 flush，而是创建未决人工 promise。B5 真实后台 8 的通过不能替代旧本地导航验收。
- 仅新增本报告 MD／JSON；未修改产品、QA、旧证据或权威文档，未运行测试、HTTP、浏览器、服务或 Git。

## 原轮结果与保全

ROOT 原完整回执 PID 14660，exit 1，391550.724 ms，childClosed／logsClosed true，UTC 2026-10-03T12:47:21.324423+00:00 结束；153 实际 151 通过／2 失败／0 skip／0 flaky。两例分别是 lesson-plan.spec.ts:33（失败断言 :38）与 navigation.spec.ts:54（失败断言 :59），原 10 秒 URL expect 保持，返回往返、恢复和打印样式后续断言未执行，不能算通过。

回执 SHA-256 6295170aab6a49841d65ff3aa64659a25ce61bfec624fc5de6c0bc037d78e5a0；原 results.json SHA-256 04d8ed09a857f6d99fa8e916aaaa8252281a1890ed252fee30b918c37a08d766。r5 候选 SHA-256 14405cb6374181599ead4db1dc0cb3e8051c5de858121e4045f3e202e4362891。

本审查 UTC 2026-10-03T12:51:08.381034+00:00 独立核 raw SHA：source 938、executable QA 2419、冻结契约 33、build 2004 均与 r5 零漂移。候选后续修复另冻结，本报告只诊断该失败候选，不验收未来改码。

## 两原 trace 与错误页

两 ZIP 均独立读取并 CRC 校验无错误，操作本身实际完成：

- chat：title fill @5185 在 313801.819 ms 结束；侧栏 click @5187 在 313807.312–313842.460 ms，填完仅 5.493 ms 即点导航。after-click 313845.510 ms 的 DIALOG 属性为 __playwright_dialog_open_: modal，URL 仍 /lesson-plans。原 URL expect 直到 323857.368 ms 失败；323861.669 ms 快照显示“已保存到本机”，最终错误页仍有“离开当前教案”与四决策按钮。trace SHA-256 7b52a63d8f15126735bebee6e7ff946b65ce93a9f22dce44d6d13e21e7a649ba。
- papers：title fill @1024 在 340281.751 ms 结束；click @1026 在 340294.900–340326.796 ms，差 13.149 ms。after-click 340329.368 ms 显示同一 modal／原 URL；原 expect 至 350336.160 ms 失败，350338.694 ms 已显示“已保存到本机”，错误页弹窗仍开。trace SHA-256 601fe3c7b44a622267e1153092bafeecbc5c5aa05820322b846c561f60c52580。

这不是按钮未触发，也不是扩大等待时间可以修复的普通慢导航：保存成功未解析该人工 promise；页面继续等取消／保存／缓存／放弃按钮。trace 不含本地 localStorage 原始落库包，本报告把成功状态解释为 persistence onSaved 的 UI 证据，不声称独立重跑了恢复断言。

## 静态因果链

1. module AGENTS 要求“600ms防抖，离开路由/卸载前刷新”；frontend AGENTS 要求公共壳调用模块保存接口后再切路由；module README 也说明路由先 flush。保留的 opening LessonPlanWorkspace.tsx:47 是 beforeNavigate={flushDraft}。
2. 当前 LessonPlanWorkspace.tsx:52 在有全局 provider 时不再传旧 beforeNavigate，由 LeaveProtection 注册 ask。WorkspaceShell.tsx:104 起执行 requestNavigation，guard 许可后才调用 router.push。
3. LeaveProtection.tsx:15 把 now.localPending() 与 backend dirty／unknown／busy、坏稿及后台创建操作统一纳入人工判断；:17 直接 setOpen(true) 并返回 resolver promise，没有先调用 local flush。:19 的 finish 仅由人工按钮／cancel 执行；保存状态改变没有 finish 路径。
4. EditorContext.tsx:47–59 对本地启用 useDraftPersistence，flushDraft 绑定 local.flushDraft；useDraftPersistence.ts 的订阅已 enqueue 最新 store revision，成功 onSaved 会显示“已保存到本机”。autosave.ts 的 600ms timer 仍 flush，但不会解决 LeaveProtection 的独立 promise。
5. createDraftWriter.flush 本身串行等待 running 并继续 drain 最新 pending；失败会保留 pending。global navigation guard 的 ask callback／注册在本地 documentId 不变时稳定，且 mounted／epoch／registration／entry 检查继续有效。本诊断没有找到需要放宽这些身份保护的证据。

因此源码与原 trace 对同一原因互相印证：本地正常保存的 leave 行为回归。DocumentGateway 的同文档／历史切换、sequence／alive 检查与后台 unknown／CAS 防护不需要据这两失败改动。

## 建议 ROOT 窄作者范围

主实现仅 apps/web/src/features/lesson-plan/components/LeaveProtection.tsx；作者回归可写 apps/web/src/features/lesson-plan/lesson-workspace.test.tsx。当前主文件 SHA-256 为 11ffd5e0fcf4dd5976f85cd2f656ded93196e106850711646701a02d3a160a8c。不建议扩大至全局 guard、DocumentGateway、writer、共享壳、锁文件或原 e2e。

对普通本地模式恢复先 await flushDraft 的行为，成功且当前来源／编辑实例仍有效才许可原导航；异步 flush 要等待在途写并 drain 后续最新编辑，失败仍留当前页／待写稿。保留坏稿、打印快照、本地后台创建 busy／unknown、真正 backend dirty／conflict／unknown 的原保护与人工决策；不可把 server 的安全分支一并自动放行。异步期间实例更换、卸载、另一个操作、打印等变化仍需当前身份复核；不放宽 global mounted／epoch／注册检查。

适合作者的行为回归：快速本地写入后离开无需额外弹窗且写入完成先于导航；延迟写入＋继续编辑时保存最新版本；失败／坏稿保持；backend pending／unknown 保持；卸载／身份变化不重放旧导航、连续触发不产生多次离开。独立浏览器应重跑原两条正确行为及完整适用门禁，原 body、URL／恢复／打印断言、45秒单例与10秒 expect 不改、不豁免、不拼旧151绿。

本报告是诊断与建议，不是 R07 或 B5 关闭记录。后续实现／自检／独立复验由 ROOT 分配。

