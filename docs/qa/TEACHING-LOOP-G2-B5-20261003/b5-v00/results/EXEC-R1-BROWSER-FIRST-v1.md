# B5-V00 r1 真实浏览器首轮

原完整8单轮：**1 passed / 7 failed / 0 skipped/flaky**。PID18580，exit1，216349.337ms；原45s/10s、retries0、workers1未改。938source/2193QA before/after均exact r1候选、变化0；2004构建文件本轮后只读核变化0，build `EuGU-xptkS4Dv7wiXoxD4`。旧QA与全部失败原件保留，不拼绿。

实际通过的是“真实后台已提交但保存回执丢失→continued B→pending/unknown离开guard→保留缓存→native Back→原包重放”。两次保存body完全相同；后台v2仍是unknown A；本机cache反思continued B，editRevision2/ack0，输入未被回执覆盖。结束后独立只读4GET：旧固定score、report、classes、reviewed practice均200且与seed原值全对象exact相同，响应连接关闭。

七项首败的实际 trace 归因：

| 场景 | 实际首败及观察 | 未完成步骤 |
| --- | --- | --- |
| 390/1024/1440/1920完整链 | KP `.all()` 查询四次均返回0，KP `.check` 动作0；异步固定run/practice GET尚未完成。导入请求本身context:null，201后人工save到v2。最后等固定practicecheckbox45s超时。属于QA未等待真实来源加载，不是已选择2KP后产品丢失context。 | 来源完整、模型三协议、候选diff/partial、teacher6、撤销另存/history、Word/打印 |
| dual-tab | 真实A保存200、B保存409、B保持、Tab限定dialog、Escape取消已执行；随后 `getByLabel('课题')`非exact匹配课题与本课题总课时，strict violation。 | 显式latest基线与newsave最终版本 |
| history-copy | 真实带analysis参数的history→current URL导航、明确copy已执行，全11field cache与手写historical相等先通过；`.process-editor`的exact label教学设计查询未找到，错误快照实际textbox显示历史活动丁。需要按真实textbox role定位。 | undo/redo/save新revision及旧history不变完整流程 |
| intent isolation | clean currentA的正确UI及copyIntent按钮已显示，首次未修改的clean数据只内存hydrate，恢复cache为null；QA将持久化cache当作clean查看的前提。 | 取消留A、开B/历史/本地清intent及11field完整隔离 |

四视口固定报告图与unknown成功状态图均实际逐张通过 `view_image` 查看，原body仅无损base64解码存成PNG，未编辑像素。手机单列和长ID换行、其余侧栏/双列/居中宽版未见明显重叠；图只覆盖当时可见范围，未据此推断交互或未达成的教案链路视觉。逐图SHA/观察在 `R1-VISUAL-READ-v1.json`。

Word下载0，ZIPXML检查未执行；打印snapshot0，没有生成PDF，也未进行桌面Word/WPS人工验。候选/只读history的四视口图未生成。这些不能由固定报告图或unit通过补称通过。

机器卡 `EXEC-r1-browser-first-v1.json` SHA `dbf3406b73fcd5d6d2cc7b65225c9f0198cf698f358e25490d29d54f679a91a7` 包含全部命令/env/PID/毫秒/逐例首败/sourceQA映射摘要、JSON/XML/log及全部补充证据SHA。原8条trace、错误上下文、JSON/XML/log、新TEMP样本全部保留；childClosed/logsClosed=true。服务生命周期只有ROOT管理，本任务未启停任何TCP服务。

停止执行与可执行QA写入，已报ROOT实际空集合race与定位/clean观察问题。待ROOT授权另版QA后封存新manifest与candidate再跑完整8；原产品无需据这些首败改写。
