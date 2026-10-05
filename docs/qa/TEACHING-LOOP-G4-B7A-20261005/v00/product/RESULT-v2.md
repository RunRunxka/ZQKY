# V00-P v2：G4-E busy 补修后独立组件整轮结果

2026-10-05，g4_v00_product。**第四完整独立单轮 38/38 通过，exit 0；此结论限于新候选的 jsdom 公共组件及状态行为，不关闭 G4，不代签真实浏览器。** 作者 STOP、ROOT check/build 后才收到正式释放；本 Agent 不修产品、不改断言、不启动服务，不读正式凭证或数据。

## 候选与执行身份

候选 `CANDIDATE-G4-fix-built-r2.json` SHA `f81a0684abdf734b067a731c089f798a3aabfe66a1f5d336ea1bd1506db34d6e`，main HEAD `b7f99ab09826c68724e281d01e15215e660c1ce0`，构建 `VeOLFBYrp-8v24Yjm-HFi`，实际构建代理 8001，next-env 原 SHA `0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc`。运行前后绑定 956 source、33 contracts、970 build 与本目录 11 个文件，全部差分为零。本次实际可执行 QA 六文件均与候选 executableQaFiles 的精确 SHA 相同；另五个计划/旧结果/原字节备份属于本地额外保护快照，不混称候选执行 QA。

命令为 bundled Python `run_independent.py --node <bundled Node 24.19.0> --candidate <上述候选> --label fourth`；runner 固定 root cwd，`NODE_OPTIONS=--no-experimental-webstorage`、Vitest `--no-cache`，输出目录不得覆盖，无重试。真实 node argv 已完整保存在 [fourth/command.json](fourth/command.json)。PID 21664，开始 `2026-10-05T13:23:18.033678+08:00`，结束 `2026-10-05T13:23:26.695776+08:00`，8662.032ms，进程已退出，exit 0。

## 实际正确行为

| 独立文件 | 实际通过 | 覆盖边界 |
| --- | --- | --- |
| public-recovery.test.tsx | 14/14 | 完整 11 字段及 secondary/context/source；公开编辑/离开恢复；持续 quota 零 HTTP；写入读回；冻结原包/unknown 精确重放；已知 ACK 零重复；CAS 人工选择；坏读取原字节保护；跨文档晚响应；create/import recoveryBlocked |
| source-intent.test.tsx | 14/14 | getSource/verify 两阶段与 null/nonempty 清除；晚成功/晚错误/新 verify/年级版本/会话/discard；metadata、Q 与 practice 保留；实际两阶段及切片参数语义不改 |
| operation-recovery.test.tsx | 10/10 | generate/apply/reject 冻结原包写入及读回、unknown 重放、已知 ACK 清理、坏读取保护；公共 ProposalPanel 首次选择签名 |

实际总计 38，passed 38、failed 0、pending 0、todo 0。原 38 断言全部保留，仅 pre-send 公共用例按 [BUSY-ORACLE-v1.md](BUSY-ORACLE-v1.md) 追加 busy 结束后恢复/刷新可用、缓存尚失败时原包保存与正文保持禁用。该组全部通过；jsdom act 的合并微任务仍不能代替真实浏览器渲染时机证明。

## 原轮保留与边界

first 收集阶段 Windows glob 错误、second 的 ACK 后 oracle 三失败、third 旧产品 38/38 和 RESULT-v1 原件均未改；本 fourth 不和任何旧轮拼合。原 public QA SHA `1987ba0aa9c68659f692b506ae929c8eb625ec50c5fc88c7a7b0590b20f66562` 已留原字节备份，当前强化 SHA `ddef5aeb6775bc2c103c19a7cbef36caa7ba6137a404b367bf9f0e13848d7266`。

旧真实浏览器 third 的 9/11 首败及 [独立诊断卡](../browser-review/FINDINGS-third-v1.md) 未改：pre-send 是公开 busy 硬失败，corrupt 是未建立初始坏读前置条件的 QA 设置。修复后的真实 11 整轮、旧 14 兼容回归和完整 174 适用回归资料本 Agent **尚未收到/审核**，须随后独立签新浏览器卡；本结果不能以旧 9 例转签新产品。

本轮 API/HTTP 替身手写于独立 helpers，实际网络调用 0、app.main 未导入、正式 .env 未读、live model 0；教师评审 pending、Word/WPS not_run。SOURCE/Q/教学质量工具各自独立结果与整体 B6/B7 完成状态由 ROOT 另行核定。

证据：command SHA `40c28317a9a376c1e04bf6b904a502f1e8313941425340e93c92fc485499759a`；run.log SHA `39bc489a42f3ec49faa5b3ee60644a3bd997d242c6392be7fdbb9a722f3b70d9`；Vitest JSON SHA `fffe53c98e90194f99f16e5cd64778f680719471aa587ff8113c99d06d61c925`。结构化结果见 [RESULT-v2.json](RESULT-v2.json)。STOP，等待 ROOT 新实测材料；不修改产品或断言。
