# G3 技术关闭 v1

ROOT 在独立签核和完整门禁后关闭 G3-R01/R02（B5F-R01/R02）。不重开原 G2/B5 编号。

| 项目 | 结果与来源 |
| --- | --- |
| 修复 | useServerPersistence、DocumentsPanel、SourcePanel 三个既有产品文件；三个新增行为测试。明确放弃撤销全部旧会话写入口和迟到来源；历史复制冻结本地输入与操作身份，正常复制仍可 Undo/Redo/另存 |
| check | 新单轮121文件1281单测、类型、lint0、生产build通过；构建 q84e_pxQoZ2_nwnws9QiI，实际proxy8001，next-env原字节恢复 |
| 独立正确行为 | 原两失败→2通过（另4条过滤未执行）；独立15、第三人8、既有27分别新单轮通过 |
| 真实浏览器 | 14/14；真实FastAPI、延迟Next路由与历史GET、全部11字段/恢复键/后台固定JSON；14完整trace、16全JSON、21实际PNG及四视口/键盘/reduced-motion已独立核查 |
| 完整适用E2E | 原24spec 153/153，第二轮全新单轮，0skip/retry/flaky；PID26492/394353.994ms。首轮152/1静态块ERR_NO_BUFFER_SPACE与诊断1分别保留，未拼绿；不证明恒绿 |
| 后端 | 410文件逐字节与旧成功运行相同；精确引用原1918pass+1重型skip及独立42；本批未重跑全API，新业务浏览器另计 |
| 聊天14 | 本批未执行；全最终diff没有公共壳/navigation-guard/chat变更，旧同源门禁绑定。原153含基本聊天场景，不冒称替代14专项 |
| 保全 | 941源码/3136执行QA/33契约/2161构建零漂移；旧9196仅当前QA索引已登记追加，其余零漂移；main@6cb6a40与next-env原字节保持 |

[独立边界签核](boundary/G3-CLOSE-AUDIT-v1.md)、[独立V00签核](v00/G3-FINAL-V00-v1.md)、[完整关闭收据及SHA](G3-CLOSE-v1.json)、[原首败](ROOT-FIRST-FAILURES.md)。

CV01～03、书籍跨批R-14、RAG-REL、静态资源环境观察与既有Outline本地模式措辞观察继续保留。旧被拒额外HTTP身份复核未执行且未重试。G3关闭只允许进入用户限定B6剩余集成和质量准备，不代表真实AI/教师教学质量、Word/WPS人工排版、正式Qdrant、迁移或原B7通过。
