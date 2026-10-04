# B5-STATIC v4：FE v3 稳定窄修复审

2026-10-03；独立审查者 `/root/b5_review`，不参与实现。结论：**本次静态复审未确认新增 P1/P2 产品缺陷；R04 v3 残余“新请求失败使旧候选复活”的具体原因已消除。** 这不是 R01–R05 的独立运行关闭，也不是 B5 整批通过。未执行任何测试、产品脚本、服务、TCP、模型、数据库或 Git；未复制源码，未新增/修改可执行 QA 或产品。只新增本目录 v4 非可执行报告与 JSON。

起点候选为 `CANDIDATE-B5-prebuild-v3.json`，SHA `317395661152fc2472932223192e08252a2c7aa93c4c5f22d0dbfa1683a4fa61`。实际起点与终点分别逐项核 **938 source / 2193 executableQA / 33 contract**，均与候选匹配；本轮 startEndDrift=[]、candidateDrift=[]、missing=[]。候选文件 SHA 前后相同，next-env.d.ts 两次采样均为原 SHA `0f70629890b72a0a82e91972cc032c04b658b26c265373cb711cf576bfbf8fcc`，未观察到临时生成。后续 CTRL 授权 check/build 的派生生成/恢复应另卡记录，不属于本次已停写终点。

## 本次三文件变化与 R04 残余复核

相对 v3 静态审查终点的 938 个 source，实际仅授权三件不同：

| 文件 | 修后 SHA-256 |
| --- | --- |
| components/ProposalPanel.tsx | 8cf4d6b9be01348425ba3b71b5c188e3c980d04baadb1f18b65579675f96e02b |
| components/SourcePanel.tsx | e42ff4957820485991dc73319427233023646e81078d4ccf69cb0fa6cafdafe6 |
| lesson-workspace.test.tsx | b29872f0400472179089c413a2850c3f16862bb1cd771f87dad86f70e198d723 |

以上均在 `apps/web/src/features/lesson-plan/`。精确前后 SHA 见 SOURCE-AFTER-v4.json 的 sourceDeltaFromPriorReview；旧 v3 审查原件保持。

ProposalPanel.tsx:25 新增 proposalGeneration；:47 只在实际候选 GET 返回并通过 alive/requestEpoch、当前 operation、receipt/job、doc/proposal 固定身份检查后，`structuredClone(active)` 保存这个候选自己的完整首次 generation 身份。:62-64 的 stale 从与 proposalId 匹配的固定 clone 读取，并要求该 receipt.jobId 等于 proposal.jobId，再核 sourceEpoch、selectionKey、original edit/load 与 baseRevisionId。

因此 M1 候选 P1 与 M2 新生成 operation O2 分离：:93 替换当前 generation 的 M2 身份，不改变 P1 的 proposalGeneration clone。新请求 422/503/unknown，或 HTTP 前/后缓存写入失败，P1 仍按原 M1/sourceEpoch/edit/load 判断；来源已经变化，P1 保持 stale，:107/:130 的 apply 准入不放行。原勾选可以保留，但 :128 对 stale 字段禁用，明确失败仍能拒绝旧候选。新请求成功 :98 清掉旧候选及其 clone，后续新 GET 才建立新候选身份。未见原 v3 复活路径残余。

同时保留原修复：点击时 clone selection/inputs 与首次 edit/load/source；flush 后 :78-79 核所有变化，A→B→A 用 sourceEpoch 维持过期；unknown :83 对完整 FrozenSubmission 深等，HTTP 前 :91 登记完整原 operation 与原签名。恢复 :55 比较双缓存整个 operation（包含全部首次 metadata），同 ID、不同 edit/load 不会重绑。旧 job/GET 在 :43,:47 要求与当前 generation 对应，不能借迟到结果替换新上下文。上述是源码观察，本轮没有执行 422/503/unknown/cache/late GET 反例。

## 四类分页与 R05 复核

SourcePanel.tsx:28-40 统一私有 readPages，每页请求 offset=已读 items 长度、limit200；每个响应先核 alive/epoch，再核 safe 非负 total、准确 offset、最多200、总行数不越界、跨页 total 一致和空页无进展。只有完整读到 total 才返回完整 items；取消返回 null，异常进入可见错误路径。

:43 的 active classes 与 analysis runs、:55 的 classesReport 与 practice sets 四个口全部使用此 helper。active 参数传递保持，ready/reviewed 过滤在完整页读取后发生。classesReport 先读班级×KP 全部行，再去重 classId，不把前200行中同班重复知识点当成200个班；practice revisions 以固定 revisionId 去重。load/selectRun 的 Promise.all 成功后还核 epoch/null，后页错误不会采用半份列表。实际公开适配 workspace-services→assessments/b4 transport 直接传 query，此处上限遵守真实 API。

教材/模型使用既有完整数组端口，confirmed fixed question 每50条由显式“继续读取”推进，未被改成假空结果。教师要求旁保留已知身份阻断适用边界与 aria-describedby。当前源未确认新分页缺口；list total 中途真实变化会可见失败，而不是声称跨页数据库快照一致。本轮没有实际请求241条列表、后页错误或真实 API。

只读新增作者测试，观察其保留原73并新增22，覆盖旧候选在422/503/unknown/cache后 stale/selected/APPLY0、unknown 原包深等，以及第241班/ready报告/reviewed练习、后页失败矩阵与 refresh/unmount 迟到。FE RESULT-v3 所报95/95是作者运行，本审查没有运行该测试，不能以其结构或收据代替独立 oracle。

## 其余 R01–R05 的限度

- R01：AI v2 12件与作者清单真实源匹配，privacy/preparation/service/validation 未变化；沿 v3 已读路径，严格结构 alias/count/minutes 与自由文字阻断分开，最终三协议 wire 精确核 messages/keys/system/strict user JSON，candidate 在严格 validator 后做路径检查。未确认新具体残余，不作三协议独立 runtime 通过声明。
- R02：literal-preserving schema gate 与冻结迁移源未变化；引号内 literal/JSON路径大小写保持、引号外空白折叠及 FK 检查仍在。未确认原绕过残余，没有执行 SQLite mutation/gate/restore。
- R03：root page/Gateway 与 v3 审查终点同 SHA；page key仅routeError、leave后alive/sequence保护、同doc/fixed revision复制身份、成功导航才安装intent及其它导航清intent保持。未确认原合法analysis重挂、跨doc intent或迟到leave残余；真实 Next/back/copy→undo→save仍须独立浏览器验证。
- R04：原等待/unknown反例及 v3 新请求失败复活残余的具体原因已静态复核消除，未独立运行关闭。
- R05：四口完整分页窄修已读，未确认新增具体缺陷，未独立请求 API。

FE v3 43件、AI v2 12件、BE v2 11件作者源清单分别与当前实际源匹配，全部 drift=[]。FE95/95、AI144/144、BE45/45是作者证据。没有把旧四库作者证据或独立 SQL 审计当本审查运行结果；本轮未执行任何 SQL。

## 证据与停写

SOURCE-BEFORE-v4.json / SOURCE-AFTER-v4.json 保存本次完整实际采样与起止差异。SOURCE-AFTER 还绑定三作者 manifest、实际 RESULT 和旧 v3 报告/结果 SHA；旧报告仍为 `f27ff52d4a1801d30c8d4e86451e3bd380c842d828563aca74ed10eba91fe9f0`，旧结果仍为 `bd5f0e01bec0fdac4ef867d51552a876ebfe5f3970eda0876b24e353adac4331`。

只读核当前 b5_candidate.py:59-65 已把 authority 例外精确限定 README/REPORT，候选字段为 immutableG2Count589、authorityPreservation2，v3 的587+4过宽分类原因已窄修。此处只核工具源码/候选 metadata，未在 v4 再执行 G2 证据审计；589+2逐项原 SHA 的独立读取证据仍见 EVIDENCE-CLASSIFICATION-v3.json，不追改 baseline、原关闭 manifest/receipt/candidate。

未执行：独立 unit/API/browser/wire/恢复/并发/导出/视觉、全 check/build/API/e2e/chat 和整批门禁（卡禁止，仅允许只读静态复审）。正式 .env/.local-data/凭证/真实草稿/Qdrant/付费模型、Git、服务/TCP 未访问或操作。结果写入后停写；后续 runtime 结果由 V00 与 CTRL 在精确稳定候选另卡绑定，本报告不作整批业务批准。
