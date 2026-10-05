# G5-E v1 作者结果：STOP，待独立验收

2026-10-05（Asia/Shanghai），负责人 g4_s。授权仅 R-G4-RECOVERY-01；开工 `OPENING-v1.json` SHA `c8449d9a8ff5ba144f0ba460e213228e3d64e6c79af03f2bd7b6dcd162a251b4`。本报告属于作者自检，不关闭 G5，不代替 ROOT 新构建、真实浏览器或独立验收。最终精确产品/QA/日志 SHA、实际 argv/PID/UTC 时间/elapsed/exit 见 [RESULT-v1.json](RESULT-v1.json) 和各轮 `command.json`。

## 改动与影响

仅修改 `apps/web/src/features/lesson-plan/model/useLessonOperation.ts` 与 `components/DocumentsPanel.tsx`；新增同模块 `g5-cleanup-outcome.test.tsx`，以及本目录专属配置/命令记录器/证据。保留共享 `useFrozenSubmission` 的历史成功 result 语义，未写共享 hooks、DocumentContext/Gateway/LeaveProtection、ProposalPanel、ServerControls、useServerPersistence、API、契约、依赖锁或根进度文档。

现有 submit callback 捕获实际本次 FrozenSubmission，明确 cleanup 记录分为 success（本次 current receipt）和 failure（本次 operation/error），并绑定 contextKey 与拥有者 load。发送前写失败与结果未知保留原包流程；不从旧 render 的 frozen 或历史 result 推断本次结果。重试保持布尔接口、原拥有者 ref、会话、写后读回与 verifyWrite 守卫；cleanup 若读到同 context 但不同完整操作包则拒绝删除，null 仍允许验证已清理的内存状态。DocumentsPanel 在重试前捕获该次 outcome，仅该次 success receipt 可走原 `openDocument`/离开保护；明确失败只清理缓存并解锁，无 HTTP 或导航。

## 首败原件与修正归因

| 轮次 | 实际结果 | PID / elapsedMs / exit | 归因 |
| --- | --- | --- | --- |
| original-counterexample-first | 原正确行为 1 failed | 21848 / 1927.7793 / 1 | 原反例未经改动，重现 cleanup 后误导航 first-created；两次 HTTP 已先核实 |
| new-sequences-first | 新创建/导入 × 422/409，4 failed | 9084 / 2113.7779 / 1 | 完整正文、二次备课、context/source/选择、第二包身份和两 HTTP 先通过；只在 cleanup 后误导航第一次成功文档 |
| author-first | 新完整 26：23 passed / 3 failed | 20932 / 3797.5439 / 1 | 2 项证明同 context 异 operationId 缓存不能删除，已加本次完整包核验；1 项新 QA 加载尚未完成时点击，补加载 context 前置等待，不改行为期望 |
| author-second-complete | 全部 126：112 passed / 14 failed | 20940 / 4559.3677 / 1 | 新聚合配置遗漏旧 V00 探针所用 `esbuild.jsx=automatic`；14 项均 React 未定义、未进入业务断言。只修新配置，旧 QA 不改 |
| author-third-complete | 全部 126 passed | 21428 / 6129.5596 / 0 | JSX 配置修正后完整轮，不拼前轮片段 |
| types-first | TypeScript exit 2 | 21196 / 9149.3089 / 2 | 新 QA 的无形参 mock 被读取 calls[0][0]，TS2493；仅补 FrozenSubmission 参数类型，原数据/断言/产品不改 |
| author-fourth-complete | 最终全部 126 passed / 10 files | 3568 / 5479.4123 / 0 | 最终 QA 字节重新完整单轮，retry=0，skip=0，todo=0 |
| lint-final | 三件源码/QA，0 warning | 12776 / 2337.7950 / 0 | --max-warnings 0 |
| types-final | 全前端非增量类型检查通过 | 21932 / 8351.1545 / 0 | --noEmit --incremental false，未写 tsbuildinfo |

首败/失败日志、JSON、原测试/配置/产品字节保存在对应新轮目录与 `first-frozen/`。原审查反例与旧 QA 保持原字节；未改旧断言、未静默 retry 或将失败计入成功。Node 实际版本 v24.19.0，所有测试设置 NODE_OPTIONS=--no-experimental-webstorage。实际 child/log 均关闭。

最终封印 helper 首次漏写 UTF-8 读取编码，在 Windows 默认 GBK 下读取 JSON 抛 UnicodeDecodeError；此时 RESULT-v1.json 尚未写。提交的 helper 文本和原 Traceback 保留于 `FINAL-SEAL-FIRST-v1.py.txt` / `FINAL-SEAL-FIRST-FAILURE-v1.json`，inline PID/elapsed 未捕获，明确不补造。只为 helper 的 read_text 增加 UTF-8，随后重新整包核对，产品、QA、126 判据及最终完整轮均不改、不重跑、不拼轮。

## 最终 126 覆盖

- 新 26：创建/导入连续成功取消→422/409 失败清理，仅保留当前全部 11 字段及 secondary/context/source/selection、原 v1 导入信封与两次 HTTP；第二次成功只打开第二次 receipt；成功清理后的新编辑仍可取消切换；双点击、路由切换/卸载；当前失败包 actual operation/submission/edit/load 绑定；发送前 0 HTTP 后显式原包重放；unknown 全包重放；迟到 verify 跨 context/卸载；坏/读失败缓存不覆盖；异操作完整包不删除。
- 原 37 恢复：`g4-recovery.test.tsx` + `model/server-session.test.tsx`，包括 generate/apply/reject 的公开缓存恢复、首次来源签名、生成已知 job、不额外 HTTP、原决策及教师字段保留。
- 原 60 来源/历史：g4-source-intent 29、旧独立 source-intent 14、b6-source-loading 5、g3-source-session 5、g3-history-copy 7；保留 metadata/source epoch、待加片段语义和历史复制守卫。
- 原清理对照 2 与未改原 stale-ack 1。

每轮 `before.json`/`after.json` 实核：两产品在命令期间不变，自身 QA 不变、7 件共享只读源码不变，开工旧 QA 22207 件均逐 SHA 无漂移。最终非增量类型检查和 lint 均针对最终字节。完整仓库候选及并行 Q/ROOT 改动的集成后验由 ROOT 负责；不将自身七件守卫冒充全部 959 源码无变化。

## 独立重跑

从仓库根使用项目 Vitest，设置 NODE_OPTIONS=--no-experimental-webstorage，运行 `node node_modules/vitest/vitest.mjs run --config docs/qa/TEACHING-LOOP-G5-20261005/edit/vitest.config.ts --reporter verbose`。独立运行须另设新证据 label/输出，不能覆写本报告轮次；可复制该配置到独立目录并使用独立 cacheDir。完整已执行精确命令绑定最终 `author-fourth-complete/command.json`。

完整 check/build、API、E2E、真实浏览器/真实模型、教师/Word-WPS/物理来源库本代理未执行，由 ROOT 按适用门禁执行或保留边界。未启动服务、读取 .env、导入 app、访问正式 API/DB、生成旧材料或操作 Git；未删除任何 TEMP/旧 QA。原 G4/B7-A 正常历史收据保持，B7-B/原 B6-B7/RAG-REL 未关闭。产品与作者 QA 至此 STOP，等 ROOT 冻结及独立验收。
