# 独立验收 A1 报告（UX-REGRESSION-FIX v1 / r2）

任务：UX-REGRESSION-FIX v1 / A1（第二轮 r2，只读复验；未改源码、未提交、未修复）
候选：HEAD=`bb980b8`（`4b97880` 之后仅一个 docs-only 提交，只动冻结记录自身）；构建
`.next = NuL_NLecD4av_kbxVVyOF`、`.next-test = njQBiVqaO-HJ9NSF_qXpv`（复验前）
**判定：pass（可交付）**，附 6 条口径/记录修订（已全部采纳，见下）

## 逐项结论（摘要，命令与原始观测以验收者报告为准）

| 项 | 判定 | 关键观测 |
| --- | --- | --- |
| 指纹与范围 | pass | `tip=4b97880: matched 22/22`、`tip=HEAD: matched 22/22`；status 干净；`.env`/`.local-data` 无本批改动 |
| ① 流式公式（**自写探针**，非复用批次脚本） | pass | 流式期 `katex=4 / display=2 / error=0`、`rawText="未闭合的尾段 $x + y"`、代码围栏 `echo "$HOME 与 $((1+2))"` 保持原文、`katexFont=KaTeX_Main,"Times New Roman",serif`；补齐后 `katex=5 / raw=0`；完成折叠→展开 `katex=5/error=0`；刷新 `katex=5` |
| ① 终态/异常/落库 | pass | 停止：`已停止/client-stop`、无自动重发（请求数 5→5→5）；断流：`STREAM_INTERRUPTED`；落库 `reasoning 196字 sha=f978c62d…`、`content 137字 sha=2714d5e1…` **与上游逐字节全等** |
| ① `test:chat` | pass（数字一致） | 8 passed / 1 failed；失败为既有 `chat-live.spec.ts:59`（第 62 行 `.connection-group` 超时）；`chat-reasoning` 三协议 ok 7/8/9 |
| ① 50k 性能 | pass（意图满足） | 两轮 `p95 5.7ms`、`script 3049/3071ms`、`originSelfCheck ok=true/50000`；但两轮各出现 **1 帧 > 50 ms（max 94.5/100 ms）与 1 条长任务（80 ms）** → 「0/0」未被复现 |
| ② 教案顶栏（五视口） | pass | 1920/1440/1024/430/390：`head=0`、`titleInHeader=true`、`sameRowAsExport=true`、`rows` 与批次表格逐格一致、`editorTop==headerBottom`、溢出 0；390 `brand→title 6px / title→export 11px`；766/767=6px、768=24px |
| ② lesson-plan e2e + 折叠/导出 | pass | 9 passed；第 9 例含 ≥2px 间隔与 `editorTop==headerBottom`；第 4 例 Word(`verifyDocx`)/PDF(`%PDF`)；折叠 `classToggled=true outlineStillMounted=true` |
| ③ 返回路径（**15 步亲自点击**） | pass | 15/15 步 `navCurrentCount=1 → [教材资料库]`；两页 `返回教材资料库→/knowledge-bases`；详情页既有返回保留；深链直开可返回；空列表入口可见；390 溢出 0；`异常步骤: []` |
| 全量 e2e | pass（数字与记录不同） | **201 passed / 1 failed (9.2m)**；唯一失败 `books-commit-safety:238`（第 266 行 120s 超时）＝跨批 **R-14**，快照为「生成已中断（无执行器在跑）」+「继续生成」、各章页就绪、笔记与阅读进度完好；`course-sessions` 11/11（R-17 未复现） |
| typecheck / lint / unit | pass | typecheck 0；lint 0；**裸跑 unit 21 failed / 33 passed（根因 `--localstorage-file` 未提供）**，加 `NODE_OPTIONS=--no-experimental-webstorage` 后 **54 文件 / 459 例全绿** |
| 文档口径 | pass（附修订） | R-15/R-17 仍标未关闭、R-17 机制假设标注未证实；三矩阵未升级验收状态、P-chat 明确真实供应商/RAG not_run；无夸大；r1→r2 的 `lesson-plan.css` 指纹变化经 git 证实（`897bf3c7…` → `055a9df4…`） |

## A1 点名的差异与总控处置（全部采纳，只改文档）

| # | A1 指出 | 处置 |
| --- | --- | --- |
| 1 | 「202/0」缺单次运行限定，同候选在独立复验中因 R-14 为 201/1 | 批次 README / STATUS / FROZEN 均加「本机单次运行」限定与 A1 的 201/1 事实；明确不得宣称候选恒绿 |
| 2 | 性能「0 帧 > 50 ms / 0 长任务」未被复现（两轮各 1 帧 ~95–100 ms、1 长任务 80 ms） | 改为区间并标注「同机状态相关」（本机 0/0、A1 1/1），结论（相对基线两个数量级改善）不变 |
| 3 | `npm run test:unit` 裸跑 216 例失败，记录未注明门槛 | 批次 README / STATUS / FROZEN 写清必须 `NODE_OPTIONS=--no-experimental-webstorage` |
| 4 | BUILD_ID 不是内容指纹（A1 重建得 `CVrJEslvTX8WkaJJD_9Ua`） | 冻结记录新增 `buildIdNote`，标明真正可复算的是 blob 哈希 |
| 5 | `hashSource` 的「按工作树复算会全部不符」略夸大（.ts/.tsx 即 LF） | 改为精确表述：.ts/.tsx 工作树即 LF，.css/.md/.py 为 CRLF，核验一律用 git blob |
| 6 | R-14 建议提前到收尾处理，否则每次独立复验必现 1 条红 | 本批不改（不属授权范围）；在 STATUS 的 R-14 台账与 §6 路线保留「下一批有界核查」入口 |

## A1 未执行 / 无法验证

真实供应商调用 **not_run**（无凭证；不宣称任何供应商真实流式公式验证——`test:chat` 的通过仅代表
隔离 fixture 真实代理 + 三协议适配）；硬件触摸、逐帧动画曲线、真实 RAG：not_run。
与凭证隔离/配置迁移/.env 补偿/模型发现/专用认证/预算耗尽等维度**零交集**（`features/chat/model/store.ts` 未改），
对本批不适用、未跑，不作为通过依据。未重跑 `npm run build`（会覆盖 `.next`）。

## A1 剩余风险

1. 「202/0」不应作为候选的确定结论（R-14 会在独立复验中偶现）。
2. 性能里的帧/长任务指标与机器状态相关，引用时应带区间。
3. 裸跑单测会误判失败，需固定环境变量。
4. 复验后 `.next-test` 已被 A1 按任务指示重建为 origin 8001（`CVrJEslvTX8WkaJJD_9Ua`），
   再跑 50k 性能或 8002 复现脚本前需按 origin 8002 重建。
5. 引用 r1 期 `lesson-plan.css` 相关截图/数字处需标注「已由 r2 取代」。
6. 未发现数据丢失、假成功或状态串用：停止/断流两条异常路径落库都是上游已发字节的**精确前缀**，
   停止后无自动重发，人工笔记保留。
