# B5-STATIC v3：冻结候选最终窄修复审

2026-10-03；独立审查者 `/root/b5_review`，不参与实现。本轮结论：**R04 仍有一项 P2 可复核残余：新生成请求明确失败后，旧候选可能重新变为可应用。** 已即时报 CTRL，CTRL 只读确认，稳定候选与本轮证据保持，后续先补独立反例，再新版本修复/验收。R01/R02/R03/R05 的原具体反例未再确认静态残余；这些观察不构成独立 runtime 关闭。

起点候选 `CANDIDATE-B5-prebuild-v1.json`，SHA `eeab0e2f6f58ea982d4ea9e1556fa43569061e79e4a42ba10d30dcb0d17c0246`；main@6aeb57280f6a7e0d7391cad4d150745479ea58ec 来自冻结卡，本轮未执行 Git。实际逐项绑定 938 source、1890 executableQA、33 contract，未运行任何产品、测试、服务、模型、数据库、TCP 或完整门禁，未复制/新增/修改任何可执行源码或 QA。仅新增本目录 v3 非可执行报告与 JSON 证据。

## R04 残余 · P2：新请求失败使旧候选借新签名复活

位置：`apps/web/src/features/lesson-plan/components/ProposalPanel.tsx:90,95`；陈旧判定 `:61`；采用准入 `:104,127`；实际失败语义 `apps/web/src/features/assessments/hooks.ts:300-318` 与 `model/useLessonOperation.ts:39-49`。

触发：M1 已有成功生成、pending 的候选 P1，并已勾选可用字段。只把模型 M1 改为 M2，不修改正文/context，不改变 server CAS/editRevision/loadGeneration。P1 此时正确显示 stale。教师点击新生成，flush 成功且选择稳定；HTTP 前 `generation.current` 正确登记新 operation O2、M2 的 selectionKey/sourceEpoch/edit/load，但 P1 和旧 selected 仍保持。新请求收到明确 422 或其他已知错误，useFrozenSubmission 返回 null/failed，没有成功 receipt。

预期：P1 始终属于原 M1/O1，来源变化后仍过期；新请求失败不能使旧候选重新适用于 M2，不能向 apply 发 HTTP。

实际：清空旧 proposal/selected 仅发生在 `receipt?.current` 成功分支（:95）。失败后 P1 保留，但陈旧判定已经使用 O2 的 M2 身份（:90 替换了 generation.current）。:61 不要求 generation.receipt 存在，也不校验旧 proposal.jobId 属于其 operation/job。新 generation 的 selectionKey/sourceEpoch/edit/load 都与当前相同，P1.baseRevisionId 又仍等于未变的 server baseline，因此 stale=false。旧勾选字段保持，:104/:127 允许把 P1 采用到当前稿。显示的固定候选 P1 虽有 M1 来源详情，准入状态却以 M2 签名判断；后端 CAS 不补救，因为只换模型没有创建新正文版本。

最小独立反例建议：生成 M1/P1，勾字段；改 M2，确认 P1 stale；第二次 generate 返回明确 ApiError(status=422)，确认 P1 仍 stale 或已经从当前交互移除，点击 apply 不得发送。再覆盖第二次请求的 unknown、缓存写入失败、旧 job terminal/GET 迟到，候选必须始终绑定其自身的原 operation/source。HTTP 前保存新来源签名是必要修复；需要同时隔离旧 proposal，或让每个 proposal 的陈旧判断使用其对应的固定生成身份。**本轮是源码确定性推导，没有执行该反例。**

缺陷源 SHA：ProposalPanel.tsx `1f0f281a1695fe12a1c6274da07b9605213a55ec6bd9d0412c85f5762fbaf61d`；源绑定与 FE v2 私有清单、冻结候选相同。归属 FE 后续新卡，不追改 FE v2 的 73/73 或本轮稳定候选。

## 原 R01–R05 与指定边界的静态观察

| 范围 | 观察与限度 |
| --- | --- |
| R01 | AI v2 privacy 的 alias/count/minutes 只豁免严格结构路径，自由文本保留已知姓名/短号/ID 与明确身份标记阻断。最终 wire 经实际 body 序列化/解析后精确核三协议消息、键、固定 system、严格 user JSON 与 frozen payload 相等；未知 tools/messages/keys 拒绝。candidate 在严格 validator 后核每个自由文字路径。未见原碰撞残余，不等于三协议 runtime 独立通过。 |
| R02 | schema gate :16-21 仅折叠引号外空白，保持 quoted literal/JSON path/SQL case；实际 CREATE 声明比较与 FK 检查保持。原 ai_applied 与 JSON path 大小写变异不再等价，未见窄修新静态问题；没有执行 SQLite/gate/restore。 |
| R03 | page key 仅 routeError，doc/revision/analysis 改变不会因此销毁 Gateway。navigateDocument :55-64 在 leave 后核 alive 与 origin sequence，成功后统一安装 copy/null；openLocal 同核。copyHistory :81 只接受当前同 doc/fixed revision，leave 取消不安装 intent。换 doc/history/local 清 intent，props 改变也清；history→current 的已同步 props 保留同文档 intent，内层 Provider 负责新的编辑会话。迟到 A 的 leave 不能覆盖 props 已进入的 B。原跨文档 intent 与合法 analysis key 重挂反例未见残余；真实 Next/back/copy→undo→save 仍待 oracle。 |
| R04 原两反例 | 点击前冻结 selection/inputs/key/sourceEpoch/edit/load/doc；flush 后 :75-76 任一身份变化便取消。HTTP 前 :88-90 同时保存原 FrozenSubmission 与原来源签名，unknown retry :80 校验完整原 operation，不取当前签名；A→B→A 用 epoch 保持 stale。原等待/unknown 反例的具体原因已消除，但上列“新请求失败复活旧候选”仍阻塞。 |
| R05 | classesReport 每页 limit200，以已读行数推进 offset，按 total 读完后去重 classId；每页检查 epoch、safe total、offset、越界、total 改变及缺失空页。第201行目标班级可由完整页路径得到；失败可见，不以空报告通过。要求输入 :95 已有个人信息/适用边界说明及 aria-describedby。未见原 limit1000 残余；没有发送真实 API 请求。 |
| generation 双缓存 metadata | ProposalPanel :52 validateOperation，:53 与 server-cache operations.generate 比较完整 stablePayloadKey(operation)，包含全部首次 metadata；unknown send :80 再深等，失败暂停而不覆盖原缓存。useFrozenSubmission.recoverFrozen :340-344 同 ID/payloadKey/context/edit/load 都匹配才恢复。因此同 ID、不同 originalEditGeneration/loadGeneration 不能借签名重绑；这只证明该精确比较路径存在，不声明所有缓存破坏 runtime 已通过。 |

作者结果读取及实际源核对：FE v2 PRIVATE-MANIFEST 43 件、AI v2 MANIFEST 12 件、BE v2 MANIFEST 11 件均与当前真实源匹配，drift=[]。RESULT 所报 FE 73/73、AI144/144、BE45/45 均为作者运行；本轮没有独立复跑。初轮/首败、原 v1/v2 结果和冻结件未改。

## G2 原证据路径归类核对（不是产品测试）

读取 B5-CTRL-EVIDENCE-PATH-DELTA-v1、baseline 与当前 candidate/tool，并实际核原 SHA。baseline SHA `a6f8a79a4c080270f20e5890a03e606b2b9c4a7449cab3c780064fd1b430a67a` 未改，G2-CLOSED-r4-v1 的实际 SHA 等于 baseline 登记。

按授权边界实际逐项核对：**589 件仍按原路径核原 hash，另仅 README/REPORT 两件用 G2-DOC-CLOSE-CANDIDATE-v2/after 的已核准原快照核原 hash，合计591件 originalDrift=[]。** 其中 G2-CLOSE-MATRIX/TASK-CARDS 的 live 原字节与 baseline 完全相同，两份冗余 after 快照也相同。README/REPORT 的原快照分别为 `3b9a37b43253932b8d6861c3aee92e62520eacc3f8ac62d78ab138216cf7e680` / `522f24b833204b810db385ebe94c3add10491c6aaf6f30e90f24ea082ecbcf8c`，与 baseline、authority 声明一致。

当前工具 :59-68 实际把 g2Evidence 与 authorityDocumentsAtStart 交集四件都归为 live authority，输出 **587+4**，比卡中只允许 README/REPORT 两件的 **589+2** 更宽。当前未发生矩阵/任务卡原件漂移，但它们不应因此被默许走 archive 保护而放宽 live 原字节。已报 CTRL，CTRL 确认并安排 check 后新的窄工具版本，原 baseline、关闭 receipt/manifest 与 candidate v1 保持。该证据工具范围观察不是产品运行失败；后续须核新工具恰只例外两条路径。

本次采样时 README/REPORT 当前 hash 已与 prebuild card 中的 currentSHA 不同；保留两份具体前后 hash 于 EVIDENCE-CLASSIFICATION-v3.json。它们是 CTRL 当前权威文档更新，不能记为历史原字节被改，也不能冒称当前文档与冻结 currentSHA 完全一致；新文档候选/独立审计须绑定实际增量。四件已核准 after 原快照全部保持。

## 本次起止 hash 与停写边界

SOURCE-BEFORE-v3.json 是实际起点采样，当时 CTRL 完整 check/build 正在执行；唯一相对 candidate 差异为 next-env.d.ts，Next 临时生成 SHA `1862ac4bbbc5192d4bf562161df66ea547ed3e67173100656ab606ae9797db2b`。CTRL 报告 check 已结束并恢复原件后，本审查 SOURCE-AFTER-v3.json 再次实际核全部 938/1890/33，与 candidate 逐项 **candidateDrift=[]、missing=[]**。起止之间仅 next-env 恢复到原 SHA `0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc`；产品/1890QA/33contract 起止漂移 0。不能把包含该派生文件的完整起止集合写成绝对零漂移，例外已单独准确登记。candidate 文件本身 SHA 前后不变。

报告/结果只说明静态复审。check/API、独立正确行为、真实 Next/API/三协议 wire、并发/恢复/导出/视觉及整批门禁均未由本审查执行。正式 .env/.local-data/凭证/真实草稿/Qdrant/付费模型、Git、服务/TCP 均未访问/操作。新增 v3 结果停写后不追改，等待后续新稳定候选再复核。
