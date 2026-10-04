# G3-BROWSER-B6-REVIEW-v1

本轮独立签收 **PASS_G3_14_ON_B6_BUILT_LIMITED**；作者 STOP。原 14 例在 B6 新构建的一次完整执行中全部 actualpass，0 skip/retry/flaky。独立审阅者没有重跑浏览器、改断言或动服务。

候选 `CANDIDATE-B6-R01-r2-built.json` SHA256 `530005e154a3620f4d0fc6a0a3ade36c35bbd2f8316a91b71e65b1e007a8deb0`，build `LkFgY8qsEnCOUbC11Dm1T`，942 source /33 contract /3136 原可执行 QA /2161 build。ROOT 实际执行 PID **25240**、**49437.732 ms**、exit0；[命令收据](../../ctrl/b6-g3-browser-r01-r2-first-command.json)与[结果](../../v00/results/run-b6-r01-r2-built-node24/browser-results.json)完整闭合，source/QA before-after 精确相同。三份原浏览器 QA 与 G3 冻结候选字节相同，trace:on、0 retry 未变；[绑定 seed](../../ctrl/b6-shared-r1-seed-bound-b6r2.json)实际新 build 身份明确，既有隔离 API 未重做业务 seed，不增加 HTTP 身份探针。

独立核完 **14 trace ZIP 全部 CRC/错误事件、16 原完整 JSON 附件、285 条 trace 内真实完整 API 响应**，并逐张实际 view **21 PNG**。原件逐项路径/SHA 见 [MANIFEST](g3-b6-browser-artifacts/MANIFEST.json)，完整 wire 见 [FULL-NETWORK-JSON](g3-b6-browser-artifacts/FULL-NETWORK-JSON.json)，独立全文比较见 [INDEPENDENT-FULL-JSON-CHECKS](g3-b6-browser-artifacts/INDEPENDENT-FULL-JSON-CHECKS.json)。未以截图文件存在或 trace 文件名代替审阅。

| 矩阵 | 实际完整证据与结论 |
| --- | --- |
| R01 390×844、1024×768、1440×900、1920×1080 | 实际公共导航点击，焦点/Enter 明确放弃；真实 Next `/chat` 目标分别暂扣 2075/2087/2117/2136 ms，旧树多 timer 后全 data/context 可信还原、恢复 key=null、PATCH0；后台 current/history/fixed 全 JSON before/during/after 相同。4/4 actualpass。 |
| R02 同四尺寸 | 真实历史 GET 分别 1644/1664/1661/1650 ms；新课题、6720 字正文、process/secondary、完整恢复包和 intent 保持。明确再复制后为完整历史 data，可 Undo/Redo 并明确保存新 v4，原固定历史不变。4/4 actualpass。 |
| 双击/实体键盘 | 真实重复输入只产生一次完整业务 read/编辑，后台全事实不变。1 actualpass。 |
| 真 CAS 变化 | 实际 FastAPI 从 v2 到 v3，暂扣 GET 1628 ms；拒绝旧历史覆盖、保留教师输入，后台完整新事实保持。1 actualpass。 |
| read 丢失与明确 retry | 先取得真实成功 GET 再丢失传输，intent/输入保持，可明确 retry 到本地完整 11 字段；未发生保存，后台 current 维持原值，不虚构 ACK。1 actualpass。 |
| 跨文档旧 read | 原 A 与当前 B 的全 current/history/fixed 不变，B 恢复 key null，迟到 A 不覆写 B/intent。1 actualpass。 |
| SourcePanel 旧回调与新操作控制 | 真报告 GET 1554/1559 ms、真实 Next 目标 3803/4114 ms；放弃撤销旧来源资格后完整 controls 深等，教师输入与可信 BASE body/context 保持；旧回调 PATCH0/key null。另新教师明确来源操作允许完整 data/context 保存 v2，精确1 PATCH。完整报告/成绩/fixed facts不变。2/2 actualpass。 |

trace 中实际核到 focus 20 次、键盘动作12次、reduced-motion=reduce 10 次。四尺寸对话框与按钮完整可操作、无截断，正文/固定身份/冲突提示与预期相符；长正文截图只支持所见部分，全文结论来自完整 JSON。21 图各自实际 view 的观察与 SHA 在本报告 JSON 的 `audit.visualPages`，包括四套 dialog/old-subtree/history-draft/history-v4，以及 CAS、跨文档、SourcePanel 两分支。

成功 discard 清除已核瞬态来源资格是可信还原的一部分。比较 oracle 是 discard 完成后的全部真实 source controls；旧 GET 释放后与该状态逐项深等。新操作控制是在真实 Next 路由提交前保留的旧 subtree 中完成，最终 `/chat` 成功，不记作取消/失败导航。

保留 **CV01–03、R14、RAG-REL OPEN、OBS-LP-MODE-LABEL**。1920 图已有后台固定身份，同时 OutlinePanel 既有“本地工作模式/草稿保存在当前浏览器”局部文案仍在；此文件非本轮修复，模式判据以后台固定身份与保存 ACK 为准。此卡不宣称全站视觉通过、恒绿、原 B6/B7 总体关闭、真人教学质量/真实模型/RAG-REL 通过或原生 Word/WPS 排版通过。

历史 G3 Node26 归档故障、QA import/clock 准备首败、原153首轮 ERR_NO_BUFFER_SPACE，以及本次 UI r7 收集/r8 核验时序首败均保持原叶；本轮原14是一轮完整验收，不拼多轮。独立离线读证据时有三次准备错误（空格语法、list 当 dict、把 retry 本地 copy 错认作保存）；已分别保留实际 tool 输出并在全文检查 JSON 明记，校正后整轮14完整读审通过，没有改产品/QA或重跑业务掩盖错误。

未执行：真人评分/live模型与实机 RAG-REL（待输入）；原生 Word/WPS 排版（无 native render）；全站视觉及原 B6/B7 总体验收（超出本卡）。所有正式结论仅绑定本轮限定浏览器行为与相关实际证据。隔离 TEMP 按 ROOT 收据保留；服务终止/资源签收由 ROOT 独立管理。
