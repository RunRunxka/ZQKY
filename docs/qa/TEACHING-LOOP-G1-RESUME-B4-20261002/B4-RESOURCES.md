# B4 暂停资源清单

2026-10-03按用户要求暂停。此清单只证明暂停时自有资源收口和样本保留，**不关闭B4，不把原14聊天记为执行**。机器可读完整路径、来源散列与时间见 [JSON](B4-RESOURCES.json)，动态观察见 [CTRL收据](b4-root/PAUSE-RESOURCE-CLOSURE.json)。

| 资源 | 实际状态与操作边界 |
| --- | --- |
| 用户前端5174 | PID5172，2026-10-02T23:46:46.5737930+08:00创建，node scripts/run-web.mjs start 5174；暂停时监听仍在。用户持有，Agent未结束/重启 |
| root聊天stream8001/8002 | PID23268，经身份/创建时间/完整argv/新owned根核对，仅写其stopfile；session30406自然exit0，original fixture finally实际返回，两个端口释放 |
| stream日志 | 647B，独占打开后关闭；SHA 38f77dc3881d90144a625d937d9844f047fd64fbb73543dec13116555fb54821。日志实际包含后端停止/server return/nested retained/original finally returned |
| 第六真实browser后端 | PID27880已优雅exit0，原shutdown/log独占关闭和31407B散列保留；用户5172保持 |
| 最新原全E2E | CLI17920自然exit1，152pass/1fail；assessments PID27244/new0iG2Lv与question-bank PID24640/newT3x3id均childClosed/logClosed后登记保留，四库存在；首败不删除 |
| 最近自有PID复核 | 23268/27880/11984/17920/27244/24640/23380/28092/536/28208共10个在暂停观察时均不存在；没有结束未知PID |
| 新系统临时根 | 独立metadata登记82个top-level根，CTRL只再次检查顶层存在性，82/82存在/保留；不枚举子数据/扫描正式库/删除。完整路径与原receipt来源见JSON |
| stream额外nested模型样本 | outer zqky-b4-stream-first-osjh6eaz中的zqky-chat-test-fhc80vjr存在/保留；不将nested多算为第83个顶层根 |
| 浏览器与连接 | 第六和E2E的上下文/子进程按实际原receipts闭合；暂停未新开浏览器或数据库连接。各截图/trace/ZIP保留，不扩大未观察到的单独request.dispose事件 |
| 协作Agent | P/F/A原任务均已报告收口停写、无资源持有；文档只读复核仅为暂停文档检查，无产品/QA/测试/服务 |

独立 [RESOURCE-PREP-R17](b4-v00-analysis/RESOURCE-PREP-R17.md) 登记365份metadata和82根，其stream starting是当时历史观察，保持原文；CTRL当前final收据补足真实退出，不能追改独立旧时点。正式.env/.local-data/真实凭证/用户浏览器草稿未在暂停时读写，旧六拒删根未触碰。原1150证据与来源/构建/next-env保护见 [暂停审计](b4-root/PAUSE-AUDIT.json)。

## 自动审批拒绝保留

两个本批空根zqky-b4-v00-hfjs_jp7、zqky-b4-v00-650zrqob的清理，以及第六补充BROWSER-real-sixth-TASK-CARD.md/json写入，均被自动审批在执行前以blocked by policy拒绝；没有更具体理由，不推测。没有重试、换工具/Agent绕过；两根保留，两被拒卡仍未创建。已有合法实际第六RESULT/receipt不属于被拒计划卡。

初始Agent前端启动亦被blocked by policy拒绝，随后用户手动启动。该限制持续有效，未来恢复不得由Agent自行启动/结束/重启5174。没有递归删除任何新/旧根，也没有将资源保留当成等待清理许可；仅等待用户恢复任务。
