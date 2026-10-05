# B6-R01 独立来源元数据/报告读取正确行为 v1

责任人 g3_v00。可写仅此 `review-source`；不写产品、作者测试或共享配置。源实现仍在作者准备，本文不是稳定候选通过报告。独立组件 QA 停写，等待 ROOT 冻结后执行，八例目前均 `not_run`。

本 QA 使用真实 SourcePanel 与真实 DOM change/toggle/click；只替换 API 与编辑/文档 Context 的会话边界，以独立手写模型/分类/报告/KP 判断控件和意图。首次操作实际打开 details 并触发 toggle，不依赖 jsdom 对关闭 details 内元素的角色可访问性。会话 stub 的 capture/isCurrent/setContext 只提供既有公开身份契约；本 QA 不冒称证明真实 persistence/cache/服务器保存，后者仍由原 G3 独立整 Workspace/业务浏览器门禁及本次 ROOT 适用回归验证。

| 编号 | 必须正确的公开行为 | 核对 |
| --- | --- | --- |
| S01 | metadata pending 时教师明确不关联学情，正常接收模型/教材分类并结束loading | context保持null，不迟到重选A，GET run0 |
| S02 | metadata refresh pending时教师选B并选KPB | 模型分类完成、loading释放、B/KPB保持，不重复自动GET A |
| S03 | 用户先选B且GET pending，后刷新metadata并先完成 | 已发生B意图不被自动初始化A撤销；B释放后显示B，GET序列A/B |
| S04 | 两轮metadata倒序、旧轮迟到失败 | 最新模型仍在，无旧error/永久loading |
| S05 | 明确discard撤销旧metadata | 旧结果无采用/context无写，教师要求/分钟保持，新会话refresh可用 |
| S06 | document/store/session更换后旧metadata迟到 | 新模型保持，不带旧document选项/error |
| S07 | 当前metadata真实失败后明确retry | 可见错误、loading释放、唯一输入保持，retry正常完成 |
| S08 | metadata pending期间编辑教师要求/时长 | 完整输入保持、不自动选模型、loading正常结束 |

原 shared epoch 的真实已登记风险：来源操作递增同一epoch使旧metadata无法采用且finally无法释放loading。分离metadata/source计数仍必须保留 document/store/mode/session/discard/refresh 所有权。

新代码静态待核风险（非actualfail）：如果metadata开始时已有B GET pending，metadata捕捉的selectionEpoch会等于B意图代次；metadata先返回时context仍A，单靠“metadata开始后epoch没有变化”可能触发自动selectRun(A)，使B失权。S03为独立反例。无需用UI禁操作或在QA等待所有metadata完来避开。

ROOT执行命令应使用独立config、Node --no-experimental-webstorage、0retry、完整八例收据/PID/时长与原首败保存。之后只读核实际日志和稳定源SHA，未执行前不宣称pass。
