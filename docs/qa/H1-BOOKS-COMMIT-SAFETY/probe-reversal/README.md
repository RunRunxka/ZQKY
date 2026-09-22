# 原缺陷探针（修复前后对照）

- 探针原件：`original-defect-probe.test.ts` —— 由用户提供的 `_work/harden-gate-20260922/probe.test.ts` **原样复制**而来，仅修正了一处相对导入路径（`../../apps/web/...` → `../../../../apps/web/...`，因为文件位置从 `_work/` 移到本目录）。**断言与探针语义未做任何修改**。随机数据全部为本地 jsdom 临时存储，无密钥、无真实数据。
- 运行：`NODE_OPTIONS=--no-experimental-webstorage npx vitest run --config docs/qa/H1-BOOKS-COMMIT-SAFETY/probe-reversal/probe.config.ts`
- 修复前：2/2 通过（探针断言"缺陷存在"，通过 = 缺陷被复现）。
- 修复后：见 `probe-run-after-fix.txt` —— **2/2 失败**，失败原因即"缺陷假设不再成立"：
  - 探针 1 首个失败 `expected +0 to be 6`（`expect(stampReads).toBe(6)`）：写标记协议已被事务取代，不再有 6 次标记读取；其后的"幻影书籍"断言未执行到。
  - 探针 2 首个失败 `expected false to be true`（`expect(injected).toBe(true)`）：探针未 `await` 的 `createBook` 现在返回 Promise（`b.id` 为 undefined），事务判定 `missing`、从未写修订号，注入点未命中；其后的 `peerReadBack` 断言未执行到。

**探针失败不作为修复证明**。正确行为由正式回归断言：

- `apps/web/src/services/books-store.harden.test.ts`（13 例，含可控交错下"已保存内容不被旧快照覆盖"）；
- `tests/e2e/books-commit-safety.spec.ts`（4 例，真实双标签页 + 原生 Web Locks）。
