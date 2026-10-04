# B6 来源面板独立代码审查

任务 SOURCES-REVIEW v1，负责人 g3b6_sources_review，2026-10-04。只读产品，唯一写入范围为本目录。现场 main@6cb6a40db890390f0261d547213e319040f64785。

结论：**1 个已复现 P2 问题，属于 B5r8 继承；没有确认 B6 新增来源读取回归。** B6 新增作者五项本轮 5/5；独立明确语义的四项为3pass/1fail。教材参数变化的两项反例仅列行为观察，不当作确认缺陷。

## 已确认问题

**[P2] 首次教材核验在途时，“清除已选教材切片”不能撤销旧响应。**

- 当前代码：`apps/web/src/features/lesson-plan/components/SourcePanel.tsx:139`，按钮只执行 `changeInputs({ evidence: null })`，没有使正在核验的读取 owner 失效。
- 采用条件：同文件 `:112` 捕捉 `{ selection, value }`，`:124` 比较这两个输入的稳定签名。首次读取前 `evidence` 为 null，教师明确清除后仍为 null，因此签名相同，旧读取仍有 owner，迟到核验被采用。
- 独立复现：实际打开真实 SourcePanel → 选择 g7 / edition / first 固定教材 / `[0,10)` → 点击“读取并核验教材切片” → `verifyLessonEvidence` 已调用但响应保持在途 → 点击“清除已选教材切片” → 释放旧响应。期望 `inputs.evidence === null`，实际恢复为 first / revision-first / `[0,10)` 的教材证据对象；首败原完整对象在 `run-r1.log` 和 `run-r1.json`。
- 实际影响：教师已取消的教材依据重新显示。`ServerControls.tsx:20` 将同一 inputs 交给 ProposalPanel；在其他生成前提有效时，`ProposalPanel.tsx:82` 会把这份 evidence 的 `scopeSnapshot/evidenceRefs` 带入新生成包。后台可以核验该证据有效，却无法知道教师曾明确取消。
- 归属：冻结 B5r8 的 SourcePanel SHA 为 `66c816abe01e12b680eed2776723e979d2bf184c87de4daff45bf2971a151337`。对其精确源码用同一 oracle 跑 B5 独立组件，亦复现同一清除失败；**不能标记为 B6 新增回归，不能否定已通过的 B6-R01 metadata 修复。**
- 建议下一小批：将显式清除纳入来源读取撤销，保留 document/store/session/discard 与 metadata 的独立守卫。先补保留此首次 null→null 清除反例，再验证 getDocumentSource 与 verifyLessonEvidence 两个阶段都不会复活来源、显示旧错误或启动后续读取。无需改后台或真实模型。

## 本批差异与实际执行

已读根/前端/教案 AGENTS、CURRENT_STATUS 最新限定关闭块、模块 README、B6 最终收口矩阵与来源独立签核。B5 精确基线来自 `docs/qa/TEACHING-LOOP-G2-B5-20261003/b5-fe/f30-v6-unit-r1-source/apps/web/src/features/lesson-plan/components/SourcePanel.tsx`，并逐 SHA 对照 B5r8 清单；未采用更早 f30-v2 近似件。

当前 SourcePanel SHA `bb4399c57492ea1a7b96ded0dc79a9f1aab5e648417ea2618fd83aa1aad1d9c8` 与 B6 最终冻结件精确相同。`b6-source-loading.test.tsx` SHA `f5abdabc0aec0183cf3dc69833578faab6072db94f39531c6d28f62f44b74d74` 亦相同。`lesson-plan-sources-api.ts` SHA `218700e6f2f12d32c77752753a3ad965a3e06fd3ffce1119b303c46279503158` 在 B5/B6/现场三者相同。

B6 本模块真实新增差异是 metadata/source 两套 epoch、pending-report Symbol owner、mode/document/store/live session 身份守卫、discard 使旧读取失效，以及分段读取后确认 owner；不是重新实现来源 API。源码差分另存 `B5r8-to-current.diff.txt`。

| 实跑轮次 | 结果 | 解释 |
| --- | --- | --- |
| 当前 r1，Node26.2.0 / Vitest3.2.4 / `NODE_OPTIONS=--no-experimental-webstorage` / 0retry / no-cache | 作者5/5；独立6中3pass、3fail；总8pass/3fail，exit1，3495ms | 清除为已确认问题；另外两 fail 为尚无明确产品语义的参数观察，不能算3个缺陷 |
| B5 baseline r1 | 6个准备错误，exit1，718ms | 独立复制件在 QA 目录没有继承 apps/web 的 automatic JSX runtime，React 未定义；保留首轮日志，不能算业务失败或通过 |
| B5 baseline r2 | 完整六项1pass/5fail，exit1，1590ms | 仅把独立 config 的 JSX 改为 automatic，与前端运行时一致；oracle 原字节保持。清除与参数观察均继承。B5 年级失效后仍会继续后端核验，以及跨 document/store/session 采用旧响应；当前两项守卫均通过，体现 G3/B6 改进 |

当前 r1 原作者五项分别核 metadata 迟交后报告完成/loading结束、明确不关联、连续刷新最新 owner、pending B 意图不被刷新 A 撤销、discard 后旧 metadata/cache/save 不复活；全部通过。独立当前正例核年级更换拒绝旧 source、document/store/session 更换拒绝旧 evidence、教师要求更改保留新输入且拒绝旧 evidence；全部通过。

所有测试只调用隔离 API 替身，不启动服务或浏览器，不访问真实缓存/凭证。真实 SourcePanel 的 DOM 与回调执行，Context 的会话契约为手写替身；不据此宣称真实 persistence/后端/真人教学验收。本轮产品 SourcePanel SHA before/after 相同；新作者原测试未改。每轮日志、JSON 和命令/时间/耗时在本目录，无自动重试或首败拼绿。

## 只列观察，不判缺陷

在核验在途时把切片终点从10改20，或教材 first 改为 second，当前仍会采用点击核验当时 first / `[0,10)` 的旧响应。B5 同行为。这两项 oracle 曾假设“修改待添加参数即撤销提交”，首轮为 fail；但页面支持累计多片段，切换参数也可被解释为准备下一片段，已核验来源另有可见列表。缺少明确的“参数编辑必须取消已发核验”约定，**不把这两项强假设当成已确认代码问题**；若下一批要调整，先规定交互语义。

完整 check/build/E2E、真实 HTTP、真实模型、浏览器与人审本轮均未执行：当前任务是只读代码审查与窄 oracle，产品未改，不重复已有门禁或旧被拒身份 HTTP 动作。
