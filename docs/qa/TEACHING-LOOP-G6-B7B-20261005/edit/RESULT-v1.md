# G6-E v1 author result — STOP writes, pending independent V00

Normal explicit success/422 ACK and public storage-only cleanup retry now share one full FrozenSubmission ownership check. They require the same live mounted context/load before reading and before deleting, validate a non-null cached package, compare the complete original package, and read back null. Foreign, corrupt and unreadable cache remains protected. The hook retains this operation's success receipt or explicit failure, blocks unsafe continuation and exposes its existing public recovery path; acknowledged HTTP is not repeated. DocumentsPanel remains unchanged and success still continues through its original leave protection.

Product write scope: only `apps/web/src/features/lesson-plan/model/useLessonOperation.ts`; new module behavior test: `apps/web/src/features/lesson-plan/g6-cache-owner.test.tsx`. All other product, old QA, shared hooks/contexts, authority documents and Git remain outside author write scope. New evidence is exclusively this `edit/` directory. Product before bytes are preserved in `original-eight-first/before/`; source diff is `PRODUCT-DELTA-v1.diff`.

| Scope | SHA256 |
| --- | --- |
| Original preserved hook | e2997e925e65b831d75aacc7286e895f1c5371abe6d456438e380164fba8604d |
| Final hook | 16f38d8348b4dfd57b64b3e0f3374d6770ee936388d128ab4bc1ee1bfdc550b4 |
| Final new 83-case test | aeb56be7c3cf58f6ed0c48a82a30e0f97ab151f5695a1d2ac81c1497750a97be |
| RESULT-v1.json | ed701d052f8adfd90c367fe7064e1c34605b5e88ff12134ea6389dfec7b6b4bf |

New original-eight-first reproduced **4 own pass / 4 foreign fail**, PID21992, 2026-10-05T17:00:40.496666+08:00 to 17:00:41.899588+08:00, 1402.894ms, exit1. Exact original code/log/report, argv/PID/time/product-QA hashes and fresh TEMP remain preserved. No pre-change failing assertion was changed.

Final complete second round is **16 files, 274/274**, PID5052, 2026-10-05T17:10:11.460148+08:00 to 17:10:43.033854+08:00, 31572.087ms, exit0, zero failed/pending/todo, product and executed QA SHA unchanged during the round. It contains new83, original8 and unchanged regression183 in this one run; it is not assembled from earlier passes. Evidence: `final-complete-second/command.json`, `run.log`, `vitest.json`.

Coverage includes create/import × success/422 own/foreign, B unknown exact raw bytes and each A/B send once, complete eleven body fields and secondary, subject/class/context/source, whole import envelope, operation/submission/first edit/load identity, B explicit completion followed by A legal storage-only cleanup, corrupt/invalid/unreadable/null cache, ineffective deletion/read-back failure, unmounted/late/cross-document results and actual committed session invalidation between read and delete. Original G5 continuous success/failure, public recovery, generate/apply/reject, source and history behavior passes unchanged.

The first complete 274 round was **272 pass / 2 new-QA timing failures**, preserved at `final-complete-first/`. The callback scheduled `rerender` inside async act, leaving the old session committed until after read/remove. ROOT authorized a two-line new-QA-only correction: import `flushSync` and synchronously commit that callback's context/load change before returning from the read. This simulates an already committed session change, not a queued uncommitted rerender. Product and correct oracle did not change. Preserved before bytes, SHA and exact diff are `QA-FIRST-FAILURE-v1.json` and `QA-TIMING-DELTA-v1.diff`; the new complete second round reruns every case instead of borrowing 272 prior passes.

Final full-project non-incremental TypeScript check passed, PID25964, 12420.841ms, exit0; scoped hook/new-test ESLint passed with max-warnings0, PID25792, 5047.714ms, exit0. Both bind final hook/test and unchanged next-env bytes; exact argv/start/end/SHA are in `typescript-final-second/command.json` and `lint-final-second/command.json`. No Next typegen/build was invoked by the author.

Every command uses a fresh retained TEMP and NODE_OPTIONS=--no-experimental-webstorage. New behavior tests inject fresh isolated Storage; old tests execute in fresh jsdom environments. Subprocesses and log handles returned closed; no services, browsers, real drafts, models, credentials, formal data or Git actions were used. All first failures and TEMP are retained.

Limitations: localStorage read/remove is not a cross-process atomic CAS; the fix protects the observed replacement before reading and does not prove all extremely narrow races solved. Author component verification is not independent acceptance. Complete check/new build/shared-origin two-Page browser/full E2E are **not_run by G6-E**, assigned ROOT/V00. Teacher, native Word/WPS, live model and RAG-REL conclusions are outside this result. Independent technical close is **pending**, not signed by the author.

G6-E has finished self-check and STOPPED all product/test/evidence writing at this result. ROOT may freeze the candidate and release independent V00.
