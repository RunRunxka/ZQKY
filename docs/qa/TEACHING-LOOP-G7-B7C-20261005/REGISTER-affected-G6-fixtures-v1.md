# CTRL 登记：G6 夹具受 G7 写入闸门影响的逐项说明 v1

2026-10-05。本文件只登记事实与正确行为依据，不修改旧 QA 原文。G7 变更：`useLessonOperation.ts` 的正常发送前写入与公开 write 重试共用同一 `writeOwnedPackage` 归属闸门（R-G6-WRITE-OWNER-01 最小修复）。写入前若共享键已被另一完整原包占用，则拒绝写入、本次不发送 HTTP、保持原字节并阻断，等待教师显式处置。

## 依据

- 变更判据：[G6/B7-B 后续审查](../TEACHING-LOOP-G6-B7B-REVIEW-20261005/REVIEW.md) 第 1 节；采纳 G6 审查建议“正常 write 和公开 write retry 统一：空包或完整同包允许；foreign、坏、不可读拒写并阻止本次 HTTP”。
- 用户指令：“旧 G6 的‘两页面均可先后占同一键并发发送’夹具前置会被新写入闸门改变。CTRL 登记受影响 apps/web 测试文件/断言与正确行为依据，E 做必要最小前置调整；旧 QA 只读，需复制到新 QA 建立对应新探针。保持 ACK 收到 foreign 包时不得删除的独立 oracle，用隔离构造的合法替换状态验证，而非靠已被禁止的第二次正常写入取得前置。不得删除 foreign 保护断言、改变产品正确行为或拼轮计绿。”

## 受影响的文件与断言

### 1. `apps/web/src/features/lesson-plan/g6-cache-owner.test.tsx`（开工原字节 SHA `aeb56be7c3cf58f6ed0c48a82a30e0f97ab151f5695a1d2ac81c1497750a97be`，原文见 `opening-bytes/`）

模板 A：``${kind} A %s preserves B unknown raw bytes, full body, source and context with one send each``（2 kind × 2 结局 = 4 例）。

- 旧前置：A、B 两 hook 同键空载 → A 正常发送（A 包在键）→ B 正常发送覆盖为 B 包。
- 变更后行为：B 的正常写入读到 A 的完整合法原包 → foreign → B 不写、不发 HTTP、进入 recoveryBlocked。旧前置不再合法。
- 正确行为依据：A 的结果未知时，B 不得替换 A 的持久恢复身份；双页并发发送必须以“先写者优先、后写者被保护性阻断”呈现。
- 允许的最小调整：B 的合法完整包改为**隔离构造**（生产 `stablePayloadKey` / `validateOperation` 形状，直接放入存储），保留模板中 A 侧全部 foreign 保护断言（ACK 不删除 foreign 字节、A 保持阻断、不额外写入/删除、不额外 HTTP、成功/失败回执仍保留在 cleanupOutcome）。不得删除 foreign 保护断言。B 发送相关断言在本模板不再可达，删除的是不可达前置而非保护判据；B-unknown→A-被阻断的 oracle 在新 QA 新探针与新增模块测试中覆盖。
- 新 QA 对应探针：`v00/` 下非作者探针（复制本批同目录新探针）。

模板 B：``${kind} after B explicitly ends A %s legally completes storage-only cleanup``（4 例）。

- 旧前置：A 先占键并发送 → B 正常发送覆盖（现被禁止）→ A ACK 撞 foreign 阻断 → B 明确结束腾空 → A 重试写入成功。
- 正确行为依据：先在键者（B）结果未知时，后到者（A）被阻断；B 显式重放并收到明确回执后清理自己的包；键为空后 A 的公开 write 重试才允许恢复原包并仅解锁、不自动发送。这同时是“foreign 处理完成后当前键为空，允许原操作恢复”的正例。
- 允许的最小调整：改为 B 先发送并 unknown → A 首次正常 run 被阻断（A 新增 HTTP 0）→ B 显式重放同一 submission/完整 payload/metadata 并明确成功清理 → A `retryRecoveryWrite()` 返回 true、写入 A 自己冻结的原包、仍不发送。保留“仅解锁不重发”的核心断言。

### 2. 旧浏览器夹具 `docs/qa/TEACHING-LOOP-G6-B7B-20261005/v00/browser/g6.spec.ts`（旧 QA，只读，不改）

- 该 spec 的 8 例“两页先后占同一键并发发送”前置同样受新闸门改变。
- 旧 QA 不重跑、不修改；本批新 QA 另写同源双页新 spec：同一全新隔离 BrowserContext 内两 Page、真实同源 localStorage；B 先实际发送后 unknown → A 首次操作读到 B 原字节 → A 新增 HTTP 0、不解锁、B 原字节保持 → B 显式重放/恢复保持自己的 submission 与完整载荷 → B 明确结果清理后 A 才可恢复原包并仅解锁。

### 3. 旧 QA 探针实测受影响清单（实现后窄回归实测，非猜测）

用 G6 审查自带回归配置（`docs/qa/TEACHING-LOOP-G6-B7B-REVIEW-20261005/cache/vitest.config.ts`）在修复后实测：10 文件 **131 通过 / 8 失败**，失败集中在两个旧 QA 文件的“两次合法正常写入同键”前置，全部为已登记前置改变，非产品回归：

| 旧 QA 文件（只读） | 失败例 | 变更依据与新正确行为 |
| --- | --- | --- |
| `docs/qa/TEACHING-LOOP-G5-REVIEW-20261005/recovery/full-cache-owner.test.tsx` | `create/import tab A success/failure ACK must preserve tab B unknown packet after two legitimate starts`（4 例） | 旧前置要求 A、B 两个 hook 先后正常写入同键；新闸门下 B 的第二次正常写入必须被阻断（HTTP 0、A 原字节保持）。新 QA 对应探针改由隔离构造 B 合法包 + A 被阻断，保留“A 不得清除 foreign”核心 oracle。 |
| `docs/qa/TEACHING-LOOP-G6-B7B-20261005/v00/owned-ack.test.tsx` | `create/import explicit success/422 foreign finishes its own packet before A public storage-only cleanup recovers`（4 例） | 同上：B 的覆盖式正常写入不再合法。新 QA 对应探针改为“foreign 包隔离构造 → A ACK 被阻断 → foreign 显式结束腾空 → A 公开清理重试仅清存储/恢复”，保留全部 foreign 保护与不重发断言。 |
| `docs/qa/TEACHING-LOOP-G6-B7B-20261005/v00/browser/g6.spec.ts` | 8 例“两页先后占同一键并发发送”（尚未在本批重跑，按静态前置判定） | 新 QA 新浏览器 spec 用同一 BrowserContext 两 Page 写新正确链（B 先 unknown → A 被阻断 HTTP 0 → B 显式重放 → B 清理后 A 恢复原包仅解锁）。 |

其余 8 个回归文件 131 例（含审查者 12 场景 write-owner 探针、G4-B7A-REVIEW 探针、G5 v00 recovery、产品 G4/G5/server-session 等）在修复后全部通过，未被新闸门削弱。

首败原始输出：`first-failures/oldqa-regression-r1.json` 与 `.log`。

### 4. 审查者 write-owner 探针实测

- 12 场景探针：8 对照（空键/自有/坏包/不可读 + 空键重试/自有重试/坏包与不可读重试）+ 4 反例（create/import × 正常首发 foreign / write 重试 foreign）。
- 其前置在变更后仍合法（A 首次写失败时键为空；B 在空键上先写；A 后到读到 B）。
- 处置：原字节复制到本批新 QA（记录原 SHA），非作者原样运行；4 反例必须转绿，8 对照保持绿；不改探针 oracle。

## 三分类处置与首败保留

1. 已登记前置改变 → 按上述最小调整，不删保护断言；
2. 未登记的新失败 → 先判断是否产品回归，是则修产品，不是则登记后调整；
3. 与 G7 无关的既有间歇（R-14、R-18 等）照台账处理，不拼轮计绿。

首败日志、旧 QA 原件、旧候选一切字节保持；本批只在新 QA 目录追加证据。
