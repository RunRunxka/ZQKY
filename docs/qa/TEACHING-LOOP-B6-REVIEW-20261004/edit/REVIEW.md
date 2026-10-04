# B6 后编辑/持久化代码审查

2026-10-04；只读产品审查，现场 `main@6cb6a40db890390f0261d547213e319040f64785`。候选是 CURRENT_STATUS 中已关闭的 G3 与限定 B6 源码。读了根、前端、教案 AGENTS，以及教案模块说明、G3 关闭收据与 B6 最终矩阵。本目录之外未写产品、权威文档、旧证据或 Git；未启动服务/浏览器，未调用模型或外部网络。

## 结论

本次未复现 B5F-R01/R02，也未找到足以重开 G3 的具体反例。现行编辑链新确认 **1 项 P2**：后台恢复缓存写失败后的普通编辑、保存及离开重试被全部阻断。这项问题来自 B5 沿用代码，**不是 G3/B6 新引入回归**，不推翻原 G3 的两项修复结论。

## EDIT-R01 — [P2] 为可恢复的后台缓存写失败保留明确重试入口

主定位：`apps/web/src/features/lesson-plan/components/ServerControls.tsx:17`。

教师编辑后台教案时，只要恢复缓存 `setItem` 暂时失败一次，`useServerPersistence.ts:39–40` 会把状态设为 `cache_error`。`EditorContext.tsx:57–60` 随即把它同时解释为 `storageBlocked` 与 `editingLocked`，`ServerControls.tsx:17` 禁用“保存后台稿”，`LeaveProtection.tsx:48–50` 又禁用“保存成功后离开”“保留恢复缓存后离开”“明确放弃未保存编辑后离开”。实际 UI 没有针对后台写失败的直接恢复按钮；`EditorOverlays.tsx:144` 的恢复入口仅用于 `!server`。

可复现步骤（实际 LessonPlanWorkspace 组件、隔离 Storage）：

1. 打开正常后台教案，在教师输入期间注入一次恢复缓存写失败。新正文仍在编辑器内，后台 HTTP 保存尚未发出，缓存没有新正文。
2. 恢复 Storage 的正常写能力，点击“读取后台最新版本”；读取成功且 CAS/固定修订仍相同。
3. 正文继续禁用，“保存后台稿”继续禁用。进入离开对话框后，三种处理按钮均禁用，只能取消。
4. 正确行为 oracle 要求恢复后保留公开的显式保存重试，该断言实际失败。配对 CONTROL 在相同输入/失败/恢复条件下直接调用现有 `server.save()`，缓存先写成功，然后一次 HTTP 保存完整原正文并进入 `saved`。

影响：一次暂时的缓存写异常会把教师正常保存与离开流程锁住，教师只能先做备份并另行处理，或通过创建副本/改变来源等额外业务动作绕行。新正文保持在内存里，实际公开“导出教案→备份草稿”仍生成 JSON；本次抓取并解析下载 Blob，确认 schemaVersion=1、revision=1 与全部11正文数据字段（含 process 的 secondary）等于内存新稿，且 HTTP 保存0。**本探针没有证明已发生数据丢失，也不声称所有间接路径永远不可恢复**。JSON 正文备份不等于包含后台 context/unknown 原操作的恢复包。问题在于正常公开的直接重试流程缺失。

证据：

- [`cache-retry.test.tsx`](cache-retry.test.tsx)：EXPECTED 使用实际工作台、公开正文/最新读取/离开控件；CONTROL 使用现有持久化 hook；未修改生产源码。
- [`cache-retry-qa2.log`](cache-retry-qa2.log)：EXPECTED 在“保存后台稿仍 disabled”失败；CONTROL 通过，完整原输入被保存。
- [`cache-retry-qa2-command.json`](cache-retry-qa2-command.json)：此次完整 2 例单轮 exit 1，1 fail / 1 pass。
- [`cache-retry-with-backup-qa3.log`](cache-retry-with-backup-qa3.log)：仅追加实际 JSON 备份 oracle 后完整 3 例单轮，仍 1 fail / 2 pass；公开重试失败、直接 hook 保存与公开 JSON 备份各自通过。对应 command JSON 分列保存。
- [`prior-same-source.json`](prior-same-source.json)：ServerControls、EditorContext、LeaveProtection 与旧 B5 `f30-v6-lint-r1-source` 完全同 SHA，明确为既有问题。

建议最小修复范围：区分“读取失败/坏原字节”和“有效会话的可恢复写失败”，给后者显式重试缓存/保存入口；重试仍须先保存原恢复包，再允许 HTTP。读取坏缓存时 `useServerPersistence.ts:62` 已设置 blocked 且没有有效 cache，不能把它解释为可恢复的写失败。坏稿原字节保护、unknown 原操作/元数据、CAS 冲突和当前正文都应保持。不能统一解除所有 `cache_error` 保护。

## G3 两项复核

`useServerPersistence.ts:198–215` 的放弃流程在删缓存前撤销旧 epoch、暂停隐式写入口，成功后用可信固定基线恢复全部正文/来源并清 Undo/Redo。删失败保留原正文与缓存，旧自动入口保持暂停，明确保存或重试放弃可以恢复。`setContext` 的会话身份和 discardGeneration 配套防止旧来源响应恢复已放弃的写入。

`DocumentsPanel.tsx:65–99` 的历史复制冻结意图与正文、store/load/write/edit 身份和后台固定基线。迟到读取遇到新编辑（包括编辑后 Undo）、文档/历史切换、CAS 变化或读失败，均保留当前输入与复制意图；正常复制仍形成一次 Undo/Redo/保存操作。没有发现本次 scope 中足以重开 B5F-R02 的可复现问题。

## 实际执行

| 检查 | 本次结果 | 原件 |
| --- | --- | --- |
| 六个既有编辑/G3/操作测试文件 | **137/137**，新完整单轮 | `existing-editor-first.log`、`existing-editor-first-command.json` |
| 原 G3 全字段边界文件 | **5/5**，新完整单轮；恢复全部字段/context、隐式写入口、删除失败、高 CAS、exclusive、本地稿 | `g3-full-body-boundary-first.log`、对应 command JSON |
| 新缓存重试探针初轮 | QA 准备错误：EXPECTED 在 JSX 处 `React is not defined`；CONTROL 通过。此轮不作产品证据 | `cache-retry-first.log`、初始源码 `.txt` 原件 |
| 仅 QA JSX 准備修正后的完整 2 例 | **1 fail / 1 pass**：公开重试失败；现有 hook 恢复成功。不拼绿 | `cache-retry-qa2.log`、对应 command JSON |
| 仅追加公开 JSON 备份断言后的完整 3 例 | **1 fail / 2 pass**：相同公开重试失败；hook 原稿保存与公开11字段 JSON正文备份分别通过 | `cache-retry-with-backup-qa3.log`、对应 command JSON；QA2源码另存 `.txt` |

所有 Node 单测带 `NODE_OPTIONS=--no-experimental-webstorage`。QA2 只增加 React import 与本目录 config 的 automatic JSX；正确行为断言保持。QA3 只追加实际 JSON 备份场景，没有修改前两项断言。首次 QA 准备错误与真实产品反例均保留，不用 CONTROL/BACKUP 或其他通过项替代失败。

未执行：完整 check/type/lint/build、E2E、真实服务/浏览器/延迟网络、API、导出与模型调用。本任务为限定只读编辑审查，未修改产品且未获服务/浏览器运行范围。已有 G3/B6 浏览器/门禁证据只用于了解验收边界，本报告不冒称它们是本次新跑，也不声称候选恒绿或教学质量通过。

## 下一批建议

若总控采纳此项，先小批处理 EDIT-R01 的后台缓存写失败显式恢复入口并验证“存储仍失败则无 HTTP、恢复后完整原输入只保存一次、坏读取/坏字节不自动覆盖、unknown 原包与 CAS 不变”。该修复与真人教学评价、真实模型预算、Word/WPS 和 RAG 相关性等待验项分列。本文仅提供审查建议，不自动实施。

源码/测试前后 SHA 与 HEAD 保全见 `opening.json`、`preservation.json`、`preservation-after-backup.json`；只比较本任务开工捕捉的精确文件，不能代替全仓库保全。
