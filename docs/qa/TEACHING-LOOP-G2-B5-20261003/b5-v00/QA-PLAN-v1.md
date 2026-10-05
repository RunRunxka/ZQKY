# B5-V00 v1 — 独立验收准备

负责人 `/root/b5_v00`，2026-10-03，main@6aeb57280f6a7e0d7391cad4d150745479ea58ec。可写仅本目录；未参与 B5 产品实现。依据完整 `ctrl/USER-REQUEST.original.txt`、B5-CONTRACT-v1、B5-TASK-CARDS-v1、冻结清单 SHA `8a19686b7b6ce6ed91e47d43c23e95bed1baccd9c2c372a5783fecd2f414d9db` 及来源运行 delta。

当前状态：准备 QA，产品独立运行 **未执行**；等待 CTRL 明确稳定 CANDIDATE-B5-rN 且全部产品作者停写。旧作者测试只作隔离 fixture/接口了解，预期字段、版本计数、失败结果与保留规则由 V00 手写。不得以生产 merge 函数作 oracle。

| ID | 独立反例与正确结果 | 证据 |
| --- | --- | --- |
| V-SAVE | v1/旧 key 无损显式导入；并发同包一次、异包409、旧CAS新操作409、A→B→A；相同正文/来源意义去重、context变化另版本；replay先于新归档/IO/CAS/模型事实 | 真FastAPI请求/响应、四库行快照/收据计数 |
| V-DB | owner无泄漏、指针归属+version真FK、固定revision/input/payload/decision拒改删、初始pointer保护、COMMIT和publish故障整体回滚 | SQL故障原件、FK/integrity |
| V-AI | 三协议真实wire已知姓名/学号/人员ID/备注均不入模；单班KP匿名计数；固定score/paper/run/KP/教材/题/练习身份 | 每次最终provider序列化请求、冻结input |
| V-VALIDATE | 4phase/全KP/alias/minutes完整；unknown/null/path/index/假ref/超预算/截断/非法unicode可见失败、零candidate | 原输入/终态/候选计数 |
| V-JOB | 六态/heartbeat排队/取消/失租零发布；restart仅显式retry；retry原input与fingerprint、漂移拒绝；timeout与publish回滚 | 独立受控时钟/任务行/三协议transport |
| V-APPLY | 五完整field选择与六teacher字段保留；未选逐字段不变；partial终结/reject幂等；unknown旧apply receipt不倒退；历史只读、undo新稿另存 | 手写旧/新集合、revision/decision/receipt |
| V-SESSION | pending继续输入、unknown原包深等/原代次、旧ACK/更高baseline、不倒退；双标签CAS/cache故障；dirty/unknown切doc/history/公共route/原生Back；StrictMode/keyboard | 独立unit、真实browser trace与请求日志 |
| V-EXPORT | 中文/11field/长正文/二次/符号/公式；当前与历史/冲突标签数据同snapshot；100ms延迟print固定正文；真Word zip/XML内容 | 下载文件SHA/XML、打印捕捉 |
| V-BROWSER | 固定成绩→ready报告→单班/KP→后台稿规则/人工保存→隔离候选→diff选择apply→历史→undo另存→Word/print；原score/report/practice不改 | 390×844、1024×768、1440×900、1920×1080逐图实际view，reduced-motion、键盘、trace |

真实浏览器种子入口 `browser/seed_runtime.py:seed_for_browser(app,manifest_path,client=...)` 不导入app.main、不起停端口。CTRL先新OS TEMP/ENV/Settings(None)/空教材/16333/9，再标准create_app。可复用 seed_api_loop 仅作HTTP业务初始化；教材在同标准catalog经生产parser/封存blob/manifest/ready代写初始fixture事实，由生产 `/lesson-plans/evidence/verify` 重建固定refs。模型profile通过真实HTTP创建，真实resolver/fingerprint/provider serializer保留，TransportFixture仅MockTransport，无模型监听端口，不mock业务fetch。CTRL seed TestClient关闭后须同root新create_app再serving；保持active client时可直接传入，fixture install/restore生命周期由CTRL持有。

依赖端口仅 CTRL 自有真实API8001与新build代理5174；V00不启动/停止TCP。Node24 `C:/Users/96022/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe`，unit `NODE_OPTIONS=--no-experimental-webstorage`。API新label经 CTRL `ctrl/run_b5_api.py --candidate <stable>` 保全命令/env/PID/exit/计数/ms/源前后与完整失败日志；测试与sample不复用删除。任一产品缺陷给CTRL接管，不改断言/预算/product。

结果卡需逐项区分准备/已执行/未执行：candidate SHA、源码与契约前后、command/env/PID/exit/count/ms、首败原件、每图view/trace、下载内容、连接/进程释放及保留根。真实供应商教学质量、Word/WPS人工排版、正式Qdrant、正式数据迁移列未执行及原因；工程check/API/153/14和迁移备份恢复由CTRL绑定各自独立收据，V00检查后不冒称自己执行。
