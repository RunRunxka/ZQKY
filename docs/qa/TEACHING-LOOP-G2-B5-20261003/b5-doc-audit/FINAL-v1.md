# B5 精确文档独立核准 v1

独立审查者 `/root/b5_final_doc_audit` 未参与产品实现。批准总控按下表原字节应用七份文档；没有 P1/P2，`approvedToApplyExact=true`。审查时 LIVE 仍为 manifest beforebytes；只有 ROOT 应用与后验后才记录 B5 关闭。本报告不执行应用，不开启下一阶段。

Manifest：`1a73b1ccaef5522d095ac0cf5e64dfd0ed48684cbe2c9d7fd3fec30509e324e3`。候选 B5-r8：`c33c85698ba2be8e6b08fe432305622bf3635a1bc5bb0cc515472996ebbe2007`，构建 `FVU-OXmtBh9WBSHehixfE`，实际代理 8001。

| 精确应用路径 | after SHA256 |
| --- | --- |
| docs/CURRENT_STATUS.md | `75e6206f27eba3b64ad5a8cbbc39a6fc2f25723005c2baa285945a4829a86919` |
| docs/NEXT_SESSION_START.md | `8784da063506202538af1712dc0004fef0b52629ebbeced8a509a148b68bafde` |
| docs/qa/TEACHING-LOOP-G2-B5-20261003/README.md | `d4f18ac49106bde0762053c0d5c45ffc9a820ecd9e7f0e806335bad7260bdb38` |
| docs/qa/TEACHING-LOOP-G2-B5-20261003/REPORT.md | `96ef7443d091096c72f91d23b01e38fea3cb037d84cab70756084e864865cc61` |
| docs/qa/TEACHING-LOOP-G2-B5-20261003/B5-CLOSE-MATRIX.md | `5f9668c63f16325b5a854e2a05f9b7e3099803ca486be2e64216eb6236557ac4` |
| docs/README.md | `e34069692d6b68bf14494feed204828bf4dd55c0cc387af35375b8914316a06f` |
| docs/qa/README.md | `0414f07f04d2ab7507c3a567dfa67efe8bdd57d56a53ced3aa7ed9bc50e890ba` |

七个 before 与 LIVE、after 与清单 SHA/长度全部一致；140 个相对文件链接实际存在。15 项清单证据散列一致。最新源码 938、可执行 QA 文件 3061、冻结契约 33、构建 2004、既有本批 1702、历史 4136、原 G2 589 加 2 核准归档及 next-env 均只读零漂移。QA 文件数量与测试数量分开，稳定 API/ROUTES/PROJECT/模块 README 与根及模块 AGENTS 沿用 PREP-v5 已核原字节。

完整 check 为 118 文件/1256 单测，PID 22916，107857.642ms；原独立组件 27、完整浏览器 8、原全量 153、原聊天 14 均是修后新完整单轮，PID/用时分别为 27472/5529.201ms、18596/43533.495ms、13224/367124.838ms、29548/42953.884ms。完整 API 1918+1 原规模 skip 与独立 API42 是本批先前实跑，PID/用时为 21200/392504.479ms 与 20076/40948.122ms，410 后台/测试/脚本/模板逐文件原前后及最终候选同字节，未冒称 R08 修后重跑。R01～R08 各行与原授权九类最低条件已按最终证据完整核对。

22 B5 与 26 聊天图实际逐张审读、4 Word/4 冻结打印/6 完整备份、fresh188 附件与 8 指针核查和原固定业务对象后验分列。恢复分为 ROOT 实际四库 restore 与独立只读 16 库/2 blob/56 SHA；独立读取未写成独立整套恢复实跑。真实模型教学质量、WPS 人工分页/实际 PDF、正式 Qdrant/迁移、超基线压力均明确未执行。CV01～03 与 RAG-REL/跨批 R-14 保留。

额外 HTTP 身份动作被 policy 拒绝的原 not_run 收据保留，没有换工具、端口、命令或 Agent 重试。原完整浏览器是既定已批准验收，当前实际服务构建由其原 trace 离线 HTML/静态字节核实。历史首败、环境误变量零收集、旧审计谓词错误与 fresh 全量重算各自保留，未拼轮关闭。

资源 v2 `7bdfa87281e2d6459542dbb15887d9353a0f722aadc6561d5eb221467d711d56` 与最终各独立 STOP 合并核实：10 服务关闭、72 命令完成、81 日志独占读后 Dispose、182 引用 TEMP 保留、3 测试端口空闲、无自有残留，用户进程未触碰。早期独立资源快照当时尚待 V00 离线关闭，后续 STOP/连接关闭和 v2 已补齐；没有把早期快照夸写为当时全部关闭。

唯一 P3 建议：CURRENT_STATUS after 第 127 行 CV01～03 与旧问题表之间的空行可能使该行呈独立 pipe 段。事实与链接准确可读，不阻止原 v1 七份字节核准；后续如调整格式，需形成另一个明确字节版本。

仅新增本 FINAL-v1 JSON/MD；没有改产品、执行 QA、权威或 proposed 文档、旧证据，没有运行测试/HTTP/服务/Git或导入 app.main，没有创建 Agent，没有连接 SQLite，没有生产 merge oracle。STOP。
