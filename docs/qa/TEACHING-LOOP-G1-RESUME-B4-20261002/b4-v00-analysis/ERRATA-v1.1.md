# B4-V00-A v1.1 · 独立 QA 错误信封前提修正

CTRL 在保全首轮后明确授权最小适配。首轮候选 a1 SHA95e10b6cb927422688a21a163477e275dc70619c99dff9f4a2c06a1e87ae50af、原探针 SHA3d53f20accd92867a93121b4b74727404ae232f6291efcd9736df83818ae5822；原字节另保存 probe-analysis.first-source.txt，哈希相同。run-first 的所有44原始日志／JSON与原样本保留。

唯一执行源变更：probe_analysis.py 的 http() 通用错误信封必填键从 code/message/requestId/retryable/details 改为 code/message/requestId/retryable。现行 ApiErrorEnvelope.details 可空且 error_response 只输出非空 details；404 合法省略，因此首轮通用断言过严。

field 参数对应的 details.issues[0].field 定位检查保持原样，非 ready、409、422状态及code、message/requestId非空、全部业务 literal oracle／证据／错误变体／故障与性能断言保持不变。未改产品、共享契约、fixture、bench、launcher。

本 v1.1 只准备源码，不执行第二轮。可执行源新哈希见 SOURCE-MANIFEST-v1.1.json；完成后停写，等待CTRL另冻新A候选与二轮执行卡。首轮独立业务状态仍未通过，未将准备解析当作业务通过。
