# B4-CHAT-V00-20261003 v1 · 原14场景只读准备

状态：**prepared / 实际未执行**。独立核对者只读原源码与今日工具，唯一写入本目录MD/JSON；没有测试、浏览器、HTTP、服务生命周期操作或资源持有。

候选r20 SHA：`fd6c32fb69d215c8d4cb5a36ceb9fa94253c0afedc248974257cdc636bd5b267`。登记879源、53可执行QA、5契约、2007构建文件、3043旧保护证据及85件今日先前证据。构建ID `Ji-Jz8X9yY2R_79JOPivD`、8001代理来自冻结清单，本文没有据此宣称用户前端HTTP就绪。r19未放行执行；最新CHAT执行卡v1.2已明确r20。

原live/reasoning两spec、原chat config和stream fixture的磁盘SHA均匹配r20，且与r17/r19同源。r19→r20共同source/contracts/build无变化；可执行QA仅今日candidate.py与另一R14独立spec变化，聊天工具完全不变。详见JSON输入SHA。

## 原场景与正确行为覆盖

| ID | 原标题 | 原正向断言覆盖 |
| --- | --- | --- |
| L01 | 教学问答模型 经真实代理在最后分块释放前显示中文 | 首段精确中文在末块释放前可见，上游stats.last为null；停止按钮可见；释放后精确末段及发送按钮可见；刷新后首段恢复可见 |
| L02 | Responses 模型 经真实代理在最后分块释放前显示中文 | 首段精确中文在末块释放前可见，上游stats.last为null；停止按钮可见；释放后精确末段及发送按钮可见；刷新后首段恢复可见 |
| L03 | Anthropic 模型 经真实代理在最后分块释放前显示中文 | 首段精确中文在末块释放前可见，上游stats.last为null；停止按钮可见；释放后精确末段及发送按钮可见；刷新后首段恢复可见 |
| L04 | 停止关闭实际上游，新会话无晚到文本 | 首段中文可见后点击停止；poll真实上游stats.cancelled=true；新会话空态可见，answer-markdown数量0 |
| L05 | 长回答 Markdown 公式与响应式布局 | 首段/末段可见，KaTeX挂载、answer-table数量6；1440/1024/390宽逐次无横向溢出、输入框可见；390宽chat-main实际宽度>350 |
| L06 | 模型发现追加、默认模型同步、表单冲突保留 | 详情与嵌套发现dialog正确显示/隐藏；已存在alpha禁用；beta可选，添加后checked且disabled；全局默认从教学模型切beta，详情显示用于问答/已选状态；真实并发PUT成功后UI保存冲突alert；未保存新名称保留；关闭/刷新后原教学默认和alpha/beta存在，未保存名称数量0；1440/1024/390头部/品牌或侧栏可见且无横向溢出 |
| R01 | 教学问答模型：推理先显示，正文出现后折叠，公式与恢复正常 | 推理先展开，正文first尚null；推理闭合KaTeX3/display2、opacity1、代码美元原文、未闭合尾段raw、错误0；补齐后KaTeX4/raw0；首段正文出现后自动折叠，末段last尚null；正文KaTeX2/错误0；用户重开后终态保持展开；刷新后自动折叠；重开恢复推理，390宽无横向溢出 |
| R02 | Responses 模型：推理先显示，正文出现后折叠，公式与恢复正常 | 推理先展开，正文first尚null；推理闭合KaTeX3/display2、opacity1、代码美元原文、未闭合尾段raw、错误0；补齐后KaTeX4/raw0；首段正文出现后自动折叠，末段last尚null；正文KaTeX2/错误0；用户重开后终态保持展开；刷新后自动折叠；重开恢复推理，390宽无横向溢出 |
| R03 | Anthropic 模型：推理先显示，正文出现后折叠，公式与恢复正常 | 推理先展开，正文first尚null；推理闭合KaTeX3/display2、opacity1、代码美元原文、未闭合尾段raw、错误0；补齐后KaTeX4/raw0；首段正文出现后自动折叠，末段last尚null；正文KaTeX2/错误0；用户重开后终态保持展开；刷新后自动折叠；重开恢复推理，390宽无横向溢出 |
| R04 | 正文公式：text.delta 原文逐字保留并在流中、终态及刷新后渲染 | 流中KaTeX8/display2/errors0，首公式/表格/代码美元/未闭合尾段正确；上游bodyDeltas拼接逐字等于bodyRaw；DOM数量/raw类/CSS/KaTeX字体正向断言；补齐后KaTeX11/raw0/escaped raw不可见/正确尾公式仅1；终态上游逐字文本、闭合尾段与原公式保留；实际IndexedDB conversation原始message.content逐字匹配，连接close；刷新后KaTeX11/errors0 |
| R05 | 正文开始后推理继续增量：用户重开后仍跟随，手动上滚不被抢占 | 正文出现后折叠；用户重开推理，40行可见且gap<32；真实wheel上滚后内容总高度增加、scrollTop不变、gap>32；真实wheel回底poll gap<32，47行可见，终态发送按钮可见 |
| R06 | 性能：20k 推理 + 正文公式受控流 | 推理样本文字、正文KaTeX可见、发送按钮终态可见；渲染字符数>=目标；上游reasoningRaw长度严格等于目标；reasoningDeltas/bodyDeltas逐字拼接等于各自Raw，KaTeX错误0 |
| R07 | 性能：50k 推理 + 正文公式受控流 | 推理样本文字、正文KaTeX可见、发送按钮终态可见；渲染字符数>=目标；上游reasoningRaw长度严格等于目标；reasoningDeltas/bodyDeltas逐字拼接等于各自Raw，KaTeX错误0 |
| R08 | 推理滚动：流式跟随、主动上滚暂停与回到底部恢复 | 10行可见；18轮最新行10–27可见，samples.every(inner.gap<32&&latestText)=true；上滚后poll内容高度继续增长；真实wheel回底poll gap<32；终态发送按钮可见 |

## 配置及受控服务边界

原单例45000ms、expect10000ms、workers=1、fullyParallel=false、trace=retain-on-failure。原配置没有retry/repeat设置，唯一命令没有重试/重复参数，期望默认0/1；后续以实际JSON为准。channel保留原表达式：PLAYWRIGHT_CHANNEL优先，否则Windows为msedge。外部配置保留原use，只覆盖绝对testDir、webServer=undefined和今日list+JSON/artifacts输出；不调用默认test:chat的启服/build。

两性能例原局部发送按钮expect 180000ms仍受全局45000ms限制。20k/50k合成文本长度、delta逐字拼接与KaTeX错误是正向断言；帧间隔、long task、首渲染/流耗时是采样，没有真实模型性能SLA门槛。R08上滚scrollTop/底部间隙仅打印/截图，不能描述成已正向证明保持不动；R05另有总高度增加、scrollTop不变与gap>32断言。

浏览器通过Next真实代理与正式FastAPI访问8002受控真实HTTP上游。三协议正文/推理/终态分别使用openai-chat choices delta+[DONE]、responses output/reasoning delta+response.completed、anthropic text/thinking delta+message_stop。固定密钥、模型与回答为明确合成测试样本，不是生产模型回答或真实凭证。

CTRL stream_service在Settings/app导入前设置fresh系统临时根、ZQKY_ENV=test、empty教材、QDRANT16333、embedding9、UTF8，并正向检查credentials_file=None。Settings.from_env仅读环境，test时不形成正式.env路径；原create_app收到显式SecretStore关闭load_env_credentials。核对者未导入app/fixture，未读正式.env或草稿。

原fixture finally实际代码是 `server.shutdown(); temporary.cleanup()`，没有显式server_close。keep wrapper只保留原精确临时样本及恢复TemporaryDirectory；root服务保持同uvicorn host/port/log参数，stopfile优雅退出由CTRL实际收据另证。原finally返回、PID自然退出、日志闭合及8001/8002释放现在全部待执行，不把静态finally当释放证据。

## 待实际单轮后核对

原6+8是静态枚举；当前没有运行计数、断言执行数、exit或耗时。后续读真实results.json/full log/原trace及收据，核唯一14原标题、实际attempt/pass/fail/skip/retry/repeat、命令/runtime/channel/timeout和源身份。静态matcher表达式不是运行assert次数；只有实际expect steps记录才能给对应执行数，没有步骤的报告不补造。首次失败保留原件与未执行边界，不自行修复或重试。

准备收口后停写，等CTRL给正式实际执行结果。独立报告不关闭B4，不进入B5，不改R14作者证据。
