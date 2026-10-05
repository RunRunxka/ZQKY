# B7B-X v1 执行方案（先行冻结）

负责人 B7B-X；起点 main@b7f99ab。ROOT OPENING SHA 676831c8b441388108c80d1ffaecc15c239c66b0155ed40b021843ac2f3c738f 放行。

仅新增 scripts/teaching-quality/controlled_*.py、tests/test_controlled_*.py、README-controlled-trial-v1.md；本 executor/ 为独占证据。原 common/prepare/aggregate/preflight、生产服务、Provider、提示词、接口、迁移与锁文件只读。

生产 prepare/build_request/execute 经实例 Resolver 返回装饰句柄；原 Provider.complete 与真实三协议 HTTP 序列化通过单实例 Transport 审计。actual wire 进入 underlying transport 前持久预留，禁止第二次发送；不从旧 QA import 服务或 fixture builder。新 TEMP 按原手写 case-specs 建固定来源，生产确认/报告/教案候选及 JobEngine 实际执行；不是旧物理库恢复。

CLI mode 为 dry-run/live；证据 kind 为 fixture/live。dry-run 的 HTTP MockTransport 明确 fixture。live 先核独立人类授权、精确 scope、所选模型能力证明。本批无真实模型/预算授权及可核模型计费证明，live registry 为空，发送 0；提供可信 proof 后的 DI 执行接口，但不宣称任意模型 ready。

CLI control-state namespace 固定为本批 executor/control-state，不接受外部 ledger-root，不从 run/output label 推导。一个 authorization identity 对应一个 ledger，scope immutable；换 scope 不能新建 ledger。fixture namespace 同样固定；测试库只用专属 tmp_path。未来跨批 namespace 移交需要保留原账本，不能靠新批路径重置旧授权。

预算为发送前可信上界预留；已知合格 usage 才结算释放差额。raw HTTP usage 与 Provider 原文先落证据，候选 JSON/finish/length/发布失败仍保留计费事实。未知、取消、异常响应、超预留、日志失败保留预留并 STOP。reserved/dispatched 重启转 unknown，不重发。OS 独占锁覆盖整个授权执行；进程结束释放锁，账本保留。

fixture proof 只说明受控 adapter/transport 的计量语义，不作为真实模型 tokenizer、价格或 reasoning 上界依据。live 无输入/输出/reasoning/其他收费可核依据即拒绝，费用模式无冻结价格/币种/汇率即拒绝，不猜字符 token 或费率。

自检后停止写入，交 ROOT 冻结与独立 V00；首败、每轮 argv/PID/起止/elapsed/exit/SHA/guards 另存，不拼轮。真实模型、教师、原生页核、RAG-REL 继续 pending/not_run/OPEN。
