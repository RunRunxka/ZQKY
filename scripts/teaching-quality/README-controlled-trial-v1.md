# 受控教学试跑执行器 v1

本入口只为受控试跑提供离线技术条件。`--mode dry-run` 使用新 TEMP、自有匿名固定来源、真实生产 prepare/build_request/execute、proposal、JobEngine 和三协议 Provider；HTTP 最终发送进入明确标记的 MockTransport。fixtureWireSends 是替身传输边界次数，realModelCalls 为 0。成功只说明本批 fixture 技术检查，不说明真实模型教学质量、教师接受、原生软件打开或任意模型预算能力。

## 本批命令

从仓库根目录执行，scope 文件须明确 modelProfileId、modelId、caseIds、sampleCount、maxAttempts、maxTotalTokens。fixture profile/model 固定为 `controlled-fixture-profile` / `controlled-fixture-model`，不读取正式配置或凭证。

```powershell
& apps/api/.venv/Scripts/python.exe scripts/teaching-quality/controlled_trial.py --mode dry-run --scope <离线scope.json> --output <全新输出目录> --label <新label> --fixture-authorization <稳定离线授权ID> --protocol openai-chat
```

其余协议为 openai-responses、anthropic-messages。只读案例规格默认使用既有 B6 case-specs；从生产模块和当前文件直接构造新自有来源，不导入旧 QA builder。每个新 label 输出 trial-result.json、账本快照、实际生产冻结输入、wire、raw、usage、attempt、job、candidate 及自动化整字段选择/应用证据。自动化 selectionActor=qa，teacherStatus/nativeStatus 仍为 pending。不会重建原 15 案例导出包，docx ref 为 null。

--case-specs 只接受原文件的相同字节副本，固定 SHA 为 `353e56e4f756403b8fb724b73613a2138d9d8a71ca460b3df6143e597497dd55`；DI 入口再核每个 case 的原 canonical 事实和选择。改要求、人数/预期计数、caseId、selectedFields 或换规格文件均拒绝，不等结果检查才发现输入漂移。

`--mode live` 是显式的拒绝入口：缺已核真人授权返回 AUTHORIZATION_MISSING；提供任意 authorization 文件路径仍返回 BILLING_BOUND_UNSUPPORTED，因为本批没有可信授权接入和真实模型账费证明注册。该路径不把用户 JSON 当授权，不读取给定授权文件、正式 .env/config/data，不解析凭证、不创建真实 Provider 请求，发送为 0。退出 2 保留 REFUSAL.json；不能把这项拒绝当作任意 live 模型已支持。

## 账本与上界

CLI 的控制状态根固定为 `docs/qa/TEACHING-LOOP-G6-B7B-20261005/executor/control-state`，不接受 --ledger-root，也不由 --output/--label 派生。子目录由稳定 authorizationId 散列确定。同授权 scope 字节不可变；改 scope 拒绝，不能用另一个 scopeHash 建空账本。换 run/label 延续累计 attempts、已核 usage 和不确定预留。OS 排他锁覆盖读取、预留、发送和落盘，进程退出才释放。账本任何结构/身份/整数/状态/attempt/总量损坏均拒绝，不作空库。

上游可能发送前，完整预留严格持久化并回读，然后将单次可能发送状态持久化。实际生产 HTTP body/endpoint 每次核验，禁止 Provider 内部追加发送、重定向或重试。未核 usage、超上界、取消、超时及日志失败保留全额预留并停止剩余范围；进程重启看到 reserved/dispatched/responded 转 unknown 并停，不自动重发。已知业务 JSON/结构/length 失败保留早于这些验证落盘的真实 fixture usage，并消耗该次 attempt。成功请求原生产 receipt 重放新增 Provider 0。

fixture 上界只对应有限替身 usage：input 1000、输出为原协议 cap、reasoning/other 0。它不是 tokenizer 或真实模型收费证明。真实模型必须分别证明输入、输出、reasoning 和其他收费项的完整上界，绑定最终 wire SHA/profile/model/proof facts；不猜字符 token 或默认费率。当前成本预算能力没有冻结价格/币种/汇率证明，maxCostCny 硬拒绝。

`AuthorizedScope`、`BillingProof.prove`、`BillingBound.verify`、`execute_case` 是未来可信宿主的 DI 接口。宿主需先独立核验真人授权/固定控制状态根，再注入真实 production handle/reader、模型特定账费证明及原型不变的 AsyncHTTPTransport(retries=0)。本批 live 注册为空；接口反证只证明不支持会拒绝，不证明某个真实模型已可运行。Mock/custom/subclass/retries transport、回环/9 端口和 fixture identity 不能转签 live。宿主不能从任意可写 JSON、自报布尔或换控制状态根取得授权；修改本地代码/删除控制状态是可信宿主管理边界，本工具不宣称对操作系统所有者防篡改。未来批次迁移 namespace 必须承接原授权账本，不能重置额度。

当前 usage 结算只接受可核的 input/output（及一致 total）形状；额外收费 usage 字段一律不支持。未来真实模型还须验证其 usage 与全部收费项的对应语义，并完成可信 host/凭证绑定；不能仅提供上界数字或补一份 scope 就宣称可以直接 live。

## 证据与自检

artifact ref 的 SHA 是文件字节 SHA；wireSHA 亦是 wire.json 字节 SHA。账费证明内部的 wire_sha 单独使用 canonical(body) SHA，不混作文件 SHA。upstream-usage.json 在原 Provider 解析返回体前记录 usage 及 HTTP 字节 SHA，不记录 headers 或原 HTTP 包。Provider.text 若命中凭证/PII，不落原文；保留 hash 并停止。生产 SYSTEM_PROMPT、隐私检查、fingerprint、固定来源再验证仍执行。

所有生产导入前建立 test 环境与新 TEMP，credentials_file=None。guard 分列合法生产导入/TEMP SQL 和 asyncio 内部 self-pipe；禁止正式 env/data/DB、未隔离 app.main、真实网络尝试。不同完整自检轮各保留 argv/PID/起止/elapsed/exit/SHA/原日志，首败不删除，不拼轮报全绿。本批证据入口为 `docs/qa/TEACHING-LOOP-G6-B7B-20261005/executor/`；schema 见 SCHEMA-v1.md。

```powershell
& apps/api/.venv/Scripts/python.exe -m pytest scripts/teaching-quality/tests/test_controlled_executor.py -q --disable-warnings -o asyncio_mode=auto
```

全站 check / e2e 不由本 Python 卡重复触发；ROOT 统一执行仓库门禁与最终冻结。真实模型、真人教师、新原生 DOCX/PDF/RAG-REL 验证未执行，原因是未给相应输入和授权。
