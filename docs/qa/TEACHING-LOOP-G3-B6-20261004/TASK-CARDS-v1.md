# G3→限定B6任务卡 v1

日期：2026-10-04；ROOT独占权威文档/共享契约/迁移/锁与集成。现场main@6cb6a40，旧r8 HEAD保持原身份。完整授权来自用户附件9c072f16-e318-4b90-b2bb-0e77e693b3b6。不开下一模块，不提交/推送/切分支/部署。

| ID/负责人 | 依赖与可写范围 | 行为验收 / 结果格式 |
| --- | --- | --- |
| G3-IMPL-v1 / g3_impl | 开工归因放行；仅lesson-plan/model/useServerPersistence.ts、components/DocumentsPanel.tsx与同模块新增g3-persistence/g3-history-copy行为测试；新增impl证据。其他同模块文件须先登记，公共navigation/contracts/迁移禁止写 | 明确放弃封存全部写入口且删除失败保输入；新编辑恢复保存；历史迟到不盖稿/清intent；正常复制Undo/Redo另存；自检、首败、文件SHA、not_run、STOP |
| G3-V00-v1 / g3_v00 | 独占新v00目录，产品只读；ROOT持有服务，稳定停写候选之后复验 | 原两正确行为、独立异步矩阵、真实延迟Next路由/实际业务GET、完整正文/缓存/后端版本不变、四viewport/focus/reduced-motion；逐例收据、原图、trace、STOP |
| G3-BOUNDARY-v1 / g3_boundary_review | 独占新boundary目录；只读产品/缓存/服务计数与作者候选，禁止旧QA写入 | 全字段/可信基线/epoch、双击/换文档/换intent/CAS/Undo语义；独立结果含pass/fail/not_run与具体行；STOP |
| G3-CTRL-v1 / ROOT | 启动身份/保全归因、公共单写、候选/构建/完整E2E、资源、权威文档 | 必需技术检查实际通过后独立关闭G3；否则不进入B6 |
| B6-CTRL-v1 / ROOT及后续三路 | 仅G3 CLOSED后派发；已有T30/T60/T70/T80/T90复用 | 剩余需求矩阵、最小真实全链、固定JSON/SQL对账、原同源恢复引用；12匿名质量case手工oracle/rubric/执行器/feedback、4导出样本与试用说明；真实模型/教师/WPS/PDF独立状态 |

开始前记录原938/3061/33/2004/1702与旧QA9196逐文件；73开发构建缓存差异已准确归因，生产构建保持。新QA/临时根另列，文件数不当测试数。产品停止写入后冻结再独立验收；产品再改重冻并跑受影响验证，文档delta单列。

### G3-IMPL-v2追加登记（同一G3-R01修复边界）

r1实际SourcePanel反例已失败，旧业务读取改变恢复上下文、重建缓存并新增save1。登记可写已有useServerPersistence.ts及新增components/SourcePanel.tsx、同模块g3行为测试；DocumentsPanel r1保持。读取捕获身份/每await核live身份/成功discard代次恢复UI，拒绝旧回调且允许新教师来源操作。原r1与新反例首败逐字节保存；r2停写后重冻check/独立原两+15+全字段及新反例/真实浏览器/全E2E。
