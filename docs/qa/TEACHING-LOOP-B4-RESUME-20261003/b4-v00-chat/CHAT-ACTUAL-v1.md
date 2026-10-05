# CHAT-ACTUAL v1 · 原14聊天实际单轮独立核对

结论：原live6 + reasoning8 **14 passed，14 attempts，retry/skip/flaky/fail=0**。每个原标题、原文件/行和45000ms timeout逐项吻合；唯一CLI/PID22384实际exit0，外层43832.314ms，Playwright JSON43106.461ms。子进程、stdout、完整UTF8合并日志关闭收据为真；原NO_COLOR/FORCE_COLOR警告完整保留，不宣称日志无warning。

r20 SHA：`fd6c32fb69d215c8d4cb5a36ceb9fa94253c0afedc248974257cdc636bd5b267`。原两spec/config/fixture和今日执行工具仍匹配冻结SHA与准备报告；原四文件与r17/r19同源。独立重算451件FE文件SHA均匹配r20，451件也与r17逐项同SHA（chat feature91件）。CTRL真实前后audit879/53/5/2007/3043及prior85、next-env均0漂移；此处仅读CTRL audit，未冒称核对者执行了完整oracle。

| ID | 原实际标题 | 单次耗时ms | actual status / retry |
| --- | --- | ---: | --- |
| L01 | 教学问答模型 经真实代理在最后分块释放前显示中文 | 1787 | passed / 0 |
| L02 | Responses 模型 经真实代理在最后分块释放前显示中文 | 740 | passed / 0 |
| L03 | Anthropic 模型 经真实代理在最后分块释放前显示中文 | 922 | passed / 0 |
| L04 | 停止关闭实际上游，新会话无晚到文本 | 909 | passed / 0 |
| L05 | 长回答 Markdown 公式与响应式布局 | 1035 | passed / 0 |
| L06 | 模型发现追加、默认模型同步、表单冲突保留 | 1748 | passed / 0 |
| R01 | 教学问答模型：推理先显示，正文出现后折叠，公式与恢复正常 | 2147 | passed / 0 |
| R02 | Responses 模型：推理先显示，正文出现后折叠，公式与恢复正常 | 2093 | passed / 0 |
| R03 | Anthropic 模型：推理先显示，正文出现后折叠，公式与恢复正常 | 1996 | passed / 0 |
| R04 | 正文公式：text.delta 原文逐字保留并在流中、终态及刷新后渲染 | 2025 | passed / 0 |
| R05 | 正文开始后推理继续增量：用户重开后仍跟随，手动上滚不被抢占 | 7495 | passed / 0 |
| R06 | 性能：20k 推理 + 正文公式受控流 | 5148 | passed / 0 |
| R07 | 性能：50k 推理 + 正文公式受控流 | 6170 | passed / 0 |
| R08 | 推理滚动：流式跟随、主动上滚暂停与回到底部恢复 | 7321 | passed / 0 |

原正向覆盖包括三协议首段在末段前显示、真正上游取消与新会话无晚到文本、Markdown/多视口公式、模型发现/默认冲突、三协议推理先显示/折叠/恢复、body.delta原文逐字和IndexedDB保留、20k/50k原长流断言及滚动跟随。覆盖详情沿用不可变PREP，JSON逐例关联原正向断言；没有删场景或重试。

实际JSON不含expect steps，原通过trace按retain-on-failure未留ZIP；因此不给虚构执行assert数字。26原PNG均存在，签名/尺寸/hash已核，本文未实际视觉审图，不借文件存在宣称视觉全通过。45000ms总单例与10000ms expect原值不变，局部180000ms仍受总单例限制。JSON证实workers1/fullyParallelfalse/retries0/repeat1/webServer null；原use继承Windows msedge表达式，JSON未serialize resolved channel，本文不扩证据。

性能stdout观察20k字符21020、50k字符52568、两例KaTeX errors0；frameP95约5.7ms、longtask0等仅此次合成样本采样。源码正向断言是目标长度/delta逐字/公式错误，不将这些指标宣称真实模型SLA。R08观察上滚top123→123、bottomGap169、返回底部gap0，但该例暂停几何原本只有采样；R05另有scrollTop不被抢占的正向断言且passed。

CTRL stream PID21412完整日志真实记录原HTTP上游三协议200、owned server return、原fixture finally returned与nested样本retained。stream收据exit0/598978.378ms；原finally是server.shutdown+temporary.cleanup，没有server_close。guarded stopfile及closed收据确认PIDgone、8001/8002free、用户frontend21816保留，所有样本保留。核对者只读该收据，未执行HTTP/端口或服务生命周期。

聊天证据完整收口后停写。原准备报告和首次日志/JSON不改；书籍R14独立失败仍单独处理，本报告不关闭B4或进入B5。
