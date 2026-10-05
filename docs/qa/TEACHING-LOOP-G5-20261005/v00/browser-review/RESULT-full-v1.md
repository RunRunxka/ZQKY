# G5 原 174 例实际资料独立审查 v1

174 个唯一场景、29 份原 spec 均单次通过，0 retry／skip／flaky／reporter error；174 份 trace ZIP 全部存在、CRC 完整且含 trace 与 network。各 spec 的 SHA 与本轮 built-r1 和原 B7 候选相同，原 21 条 UI、DOM／排版／触控／焦点／动画判据和截图调用完整保留。R14 双标签写不同书例实际通过，保留已知间歇边界。

实际运行是 built-r1，PID 14648，492652.953 ms，exit 0。当前 built-r2 仅两份非此门禁执行 QA 变化，源码／33 契约／970 构建全同；没有在 r2 重跑 174。独立核 [转签预览](../../GATE-TRANSFER-REVIEW-v1.json)，该预览没有关闭 G5。

全量包含 assessments 4 条与 question-bank-real 2 条真实隔离 FastAPI 场景，明确 TEMP 根与 test 环境先于 fixture 导入，credentials_file=None，模型为受控 Provider。API 日志只有启动身份行，关闭由原日志 childClosed／logClosed 标记和 ROOT 持有的 PID／出生收据证实，未杜撰 shutdown 行。本批未另跑全量 pytest；原隔离 200×100 浏览器样本不作为正式数据库压力验收。

[完整独立 JSON](RESULT-full-v1.json) 留存场景／trace SHA／29 文件／API 日志及实际命令。原 UI 使用 DOM／几何／焦点／动画断言与截图留存，并无金图差分断言；本审查未重生成图片。ROOT 的 [资源后验](../../RESOURCES-final-v1.json) 四原实例和 26 后代收据均关闭，5174／8001 监听 0，[fixture 闭合](../../RESOURCES-FIXTURE-CLOSURE-v1.json) 分列保留；审查者没有启动或关闭服务。

材料总核首次内联脚本将四项 native starter 列表误按整数比较，首败保留在 [审查适配记录](../AUDIT-INLINE-FIRST-FAILURE-v1.json)。只修列表计数，273 引用／15 空教师行／4 空 native 行要求均未改变，业务门禁未重跑。
