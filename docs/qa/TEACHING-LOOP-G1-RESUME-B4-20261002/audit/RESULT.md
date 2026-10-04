# G1R-AUDIT v1.1 · g1-resume-r1 独立静态审计完成 / 停写

负责人 `/root/g1_v00_fe`，2026-10-02。新任务唯一写入范围为本批 `audit/**`；原 G1 的 `v00-fe/**` 及全部旧 QA 保持只读。此结果针对 CTRL 于 17:32 冻结的 `CANDIDATE-g1-resume-r1.json`，不替代实际浏览器、视觉或完整 E2E 门禁，也不对随后未冻结的测试修订给稳定结论。

## 结论与冻结身份

独立审计 **通过**：826 项源码、10 项可执行 QA、815 项保护证据、1979 项既有构建文件，逐文件 SHA 全部零漂移。源码集合与继承的 g1-r2 完全相同；相对 g1-r2 恰两项登记改变，仅 assessments/question-bank-real E2E 的资源生命周期适配。没有本轮产品代码、契约、迁移、锁或其他原业务测试改变。

- 候选 manifest SHA256：`af918cc2fe419c4fd449f4bb8fa720e762853b07dfe110192e15dc1d615aa85c`。
- 分支/HEAD：`main@6aeb57280f6a7e0d7391cad4d150745479ea58ec`，与登记现场一致。
- BUILD_ID：`gIyYdxBPz-86QUIMw_JX2`；真实构建 routes-manifest 的 `/api/v1/:path*` 仍代理 `http://127.0.0.1:8001/api/v1/:path*`。
- `next-env.d.ts` 与本批 `next-env.original.bin` 原字节完全一致。
- 原 826 项 baseline 中的两处差异是授权适配，不被隐藏成旧 baseline 零差异；完整差异、逐文件核对与候选元数据见 [frozen-audit.json](frozen-audit.json)。

## 业务集合与资源边界

独立 TypeScript AST 严格原文比较：原 4 个 assessments 和 2 个 question-bank-real 的名称与完整 `test(...)` 调用/回调（包括断言）逐字一致，15+4 个非生命周期函数及 imports 一致，均无解析错误、无新增函数。进一步核对除了 `Backend` 接口、`startBackend`/`stopBackend` 外的全部顶层语句（36+22）一致；启动的临时根/端口、测试环境、种子脚本/数据解析、子进程 command/args 等业务值保持原样。两份 `test.afterAll` 注册原文也一致。见 [business-set-audit.json](business-set-audit.json)、[两份生命周期原文](assessments-lifecycle.json) 与 [配置/资源收据核对](config-resource-audit.json)。

人工核实生命周期差异只增加：spawn 时保存 close Promise、stdout/stderr 双 pipe 不各自提前结束共同日志、停止自有 PID 后等待 child close 再等待 log close；系统 temp 与 spec 前缀的路径校验后，`ZQKY_KEEP_TEST_DATA=1` 明确保留并打印身份，否则沿用最多六次自身根清理重试。已经退出的 PID 不再 taskkill；关闭失败明确保留目录并告警。

四份资源分支收据（两 spec 各 keep/default）与实际原日志逐条匹配，并绑定当前冻结 spec SHA；真实 afterAll 的执行脚本只替换测试注册入口并注入本轮无端口子进程，业务回调及 startBackend 未执行。keep 顺序是 child-close → log-close；default 再有 rm-own-root。全部记录验证完整 stdout/stderr 尾部落盘，保留 JSON 字段与新根/PID 一致，默认仅删除各 case 自建的新根，最终自有子进程收据为空。实现者的**该次 harness 4 passed、exit0、2145ms**得到证据支持；这是资源探针数，不是实际 FastAPI 或 E2E 业务通过数。审计者没有重跑 harness、打开这些 temp 根或启动/停止任何服务。

## 全量配置与聊天适用性

只加载配置对象，没有启动 Playwright 测试或浏览器。外部配置继承原 `fullyParallel=false`、workers=1、timeout=45000、expect timeout=10000 及完整 use（5174、1440×900、当前 msedge、retain-on-failure）。testDir 解析为同一完整 `tests/e2e`；无新增 grep/testMatch/testIgnore 或删用例设置。有效 webServer 为 undefined，不存在启动 fallback。仅输出目录和 list/JSON/JUnit 收据目标改为本批目录。未执行 `--list`，不把配置核对或收集计作业务执行。

额外 stream 集成本轮不适用；原全量 E2E 聊天 UI 仍适用。已按实际 13 项 G1 产品修改核聊天依赖：前端保守闭包 87 文件、FastAPI chat route 本地 import 闭包 19 文件，交集为空，各文件与 G1 前 SHA 一致；人工核实 ChatService/SSE/Provider/Markdown 调用路径及共享 main.py 装配未改变。完整依据见 [CHAT-APPLICABILITY.md](CHAT-APPLICABILITY.md)、[chat-dependencies.json](chat-dependencies.json)。原静态命令 exit0，首次耗时未捕获；不编造该耗时，不执行会自行重建/起端口的默认 test:chat。

## 单次命令

均在 `H:\备份xuexi\智启课源`，仅读文件/config，无 app import 或测试业务回调；日志与命令收据在本目录。计数为静态核对范围，不合并成测试通过数。

| 完整命令 | exit / 耗时 | 单次核对 / 原件 |
| --- | --- | --- |
| `apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/audit/inspect.py frozen` | 0 / 818ms | 826 source + 10 QA + 815 old evidence + 1979 build；[日志](frozen-audit.log)、[收据](frozen-command.json) |
| `node docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/audit/compare_business.mjs` | 0 / 317ms | 6 业务回调、19 非生命周期函数；[日志](business-set-audit.log)、[收据](business-command.json) |
| `node docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/audit/verify_config_resources.mjs` | 0 / 704ms | 配置继承、58 顶层语句、4 资源分支收据；[日志](config-resource-audit.log)、[收据](config-resource-command.json) |
| `node docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/audit/verify_supplement.mjs` | 0 / 138ms | 2 份真实补录命令及物理空输出日志；[日志](receipt-supplement-audit.log)、[收据](receipt-supplement-command.json) |
| `apps/api/.venv/Scripts/python.exe docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/audit/chat_dependencies.py` | 0 / 首次未捕获 | 13 产品修改、87/19 依赖；[日志](chat-dependencies.log)、[结构收据](chat-dependencies.json) |

## 发现、修正及限制

独立发现 adapt-e2e/RESULT 的两处 lint-first.log/typecheck-first.log 链接不存在，首轮 command.json 没有耗时/原始流。已立即报 CTRL，由原写入者仅修报告并真实复跑相同窄检查补证据：lint exit0/1224ms、tsc exit0/611ms，stdout/stderr 均实际 0 字节。补录实物、路径及 SHA 已独立核，原第一轮 command 保留，首轮缺失如实记载；没有伪补第一轮日志。问题已关闭，详见 [receipt-supplement-audit.json](receipt-supplement-audit.json)。

资源 harness 的首轮 QA 前置 EOF 同步超时已保留原脚本、命令、日志和新根登记；该轮 afterAll 尚未执行，不能并成四项成功。第二轮只改 QA 同步点，不改业务回调/产品行为。此独立审计没有产品行为首败；没有用审计脚本绕过独立浏览器的实际失败。

真实浏览器/视觉/完整 E2E 由 CTRL 及其他独立 Agent 执行，**本任务未执行**；截至本审计结果不能宣称 G1 全部门槛关闭或 B4 已开工。未重复 check/API/build，未读正式 .env/.local-data/凭证/用户草稿/旧六目录，未启动或停止服务/浏览器/app，未做 Git 写入。自身只运行已结束的静态审计进程，无监听、后台子进程或自建数据根残留。旧 G1/B3/新审查的 815 份原件零漂移；旧 v00-fe 不再写入。

本任务对 r1 收口并停止写入；后续若 CTRL 登记新候选，仅在收到新冻结通知后追加相应版本复核，不把未冻结修改当作已验。
