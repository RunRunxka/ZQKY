# B4-R14-FIRST-RUNTIME-REVIEW v1

2026-10-03，独立只读审查者 `/root/g1_resume_browser`。绑定原 r20 `fd6c32fb69d215c8d4cb5a36ceb9fa94253c0afedc248974257cdc636bd5b267`，首轮原件不改。本报告只解析已产生的 trace/JSON/DOM 附件，没有重跑或操作浏览器、服务、HTTP。

首轮实际两例 **1 pass / 1 fail / retry 0**。正常例 16866ms；故障例 16099ms；CLI/PID16548 实际 exit1，日志与 stdout 已关闭，完整外层耗时 36491.677ms。两个 trace 分别 162/159 entries，全部 ZIP CRC 正常、逐 entry SHA 留 JSON。

正常例独立原包可证：真实存储 ready/finished、同 runId、笔记/全部书籍 ID 保留，八页 ready、零次 Continue，native held/pending 为零、legacy null、helper 资源全释放。

故障例的可证时间线如下；trace 相对毫秒与独立附件 wallTime 分列，不混用不同时间基准。

| 证据 | 时间 | 实际状态 |
| --- | --- | --- |
| click 原始独立 capture | wallTime 1790993330064 | trusted=true；同 book/page；中断文案；按钮可用；原包 run=stopped，真实笔记已保存 |
| after@call@151 | trace 35167.613，wallTime 1790993330067 | 阶段仍“生成已中断”；按钮 disabled“正在继续…” |
| helper terminal | wallTime 1790993330068 | failed / “interrupted again after one Continue”；book=compiling；笔记保留；attempt1/click1 |
| before@call@153 | trace 35169.979，wallTime 1790993330069 | 阶段仍“生成已中断”；按钮再次 enabled“继续生成” |
| 最后 DOM trace snapshot | 35179.272，wallTime 1790993330079 | 同中断文案与可用 Continue，没有编译阶段快照 |
| error-context 附件 | test.trace attach 35386.461 | 单独页面快照已呈“正在逐章编译…”、“暂停生成”，首失败页“排队”；具体抓取时点没有单独时间戳 |

独立还原全部 82 个 DOM 快照的节点引用树；点击后的已记录 DOM 快照都未呈准备/编译阶段。点击至 helper 失败仅 **4ms**。原 helper SHA `cb6407c8045c35dc0ae54915c9854b0ab9275b17f9654ef3aa9dbfedfee0a072` 与 r20 清单相同，其 134–135 行把禁用的“正在继续…”直接设成 `resumed=true`。

实际组件的 Continue 显示条件是 `!working`；按钮 busy/disabled 由 `resuming` 控制，二者含义不同。BooksRoute 在等待 resumeRun 前设 busy，并在 finally 清 busy。故现有证据支持 helper 将请求 busy 当作执行已恢复、又在旧 UI 提交过渡中提前判“再次中断”。内部 resumed 变量未直接记录，快照也不是每次 mutation 全量采样，因此不将未采样的瞬间状态作绝对排除。

稍后的 error-context 可证页面曾呈编译 UI，不能用其替代 35169 时点，也不能单凭其证明持久 run.running、真正恢复完成或最终 ready。helper terminal 仅记录 book status/note，没有采样点击后的 run 状态或 cursor；原包 stopped 是点击前的状态。不能据此推断写锁/租约原因，亦不能认证真正“恢复后又中断”。

故障例 cleanup 实际 observer/timer/listener 均释放、资源 released=true、cleanupErrors=[]，但 resultStatus=failed。真实后置 ready/finished、全部页、笔记/ID、终态 locks 断言没有执行；原 count0 等待在 context 关闭时以仍有一个 strip 收尾，不能把 cleanup 通过写成业务通过。

窄修正建议：busy 只表示请求进行中，不据此设置 resumed；只有点击后可证的实际执行阶段/同目标运行进展或 working 确认才启用“再次中断”判据。继续保留唯一真实点击、所有错误拒绝、原绝对 deadline 和完整 ready/笔记/ID/锁断言，不 retry UI、不增预算、不把 interrupted 当成功。作者须等待 CTRL 原14聊天门禁及自有 stream 收口后另卡写入，新候选冻结再独立两例复验。原153尚未放行。

所有原输入 SHA、两例完整事实原包、trace entry CRC/SHA、DOM 时间线及实际命令 exit/ms 留 JSON。只读解析第一版对无属性节点的处理报 IndexError，未写报告或改原件；按真实 snapshotRenderer `nodeAttrs || {}` 规则修正解析器后完整读取成功。没有执行新 QA 或产品代码。

报告完成后停止 source/trace 读取与写入。B4 仍未关闭；并行原14聊天是 CTRL 的另一个门禁，本报告没有审验其结果。
