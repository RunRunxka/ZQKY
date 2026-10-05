import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { flushSync } from 'react-dom';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/services/api-client';
import { stablePayloadKey, type FrozenSubmission, type SubmissionReceipt } from '@/features/assessments/hooks';
import type { LessonCreateRequest, LessonImportRequest, LessonPlanData, LessonView } from '@/contracts/lesson-plans';
import { browserOperationRecovery, useLessonOperation } from './model/useLessonOperation';
import { validateOperation } from './model/server-cache';

type Kind = 'create' | 'import';
type Payload = Omit<LessonCreateRequest, 'submissionId'> | Omit<LessonImportRequest, 'submissionId'>;
const kinds = ['create', 'import'] as const;
const context = { analysisRunId: 'g6-fixed-analysis', selectedKnowledgePointIds: ['g6-kp-primary', 'g6-kp-secondary'] };
function data(tab: string): LessonPlanData {
  return { title: `${tab}完整教师课题`, totalLessons: '3', currentLessonNo: '2', lessonTypes: ['review', 'new', 'review'], otherTypeText: '特殊课型、中文符号<>', coreCompetencies: '完整素养', keyPoints: '完整重难点', teachingDesign: '教师设计'.repeat(8), process: [{ id: `${tab}-process`, stage: '环节', design: '活动'.repeat(8), secondary: '完整二次备课'.repeat(8) }], exercises: '完整练习', reflection: '完整反思' };
}
function payload(kind: Kind, tab: string): Payload {
  const selection = { subjectId: 'chinese', classId: 'g6-isolated-class', context: structuredClone(context) };
  return kind === 'create' ? { ...selection, data: data(tab), source: tab === 'A' ? 'rule' : 'manual' }
    : { ...selection, draft: { schemaVersion: 1, revision: 13, updatedAt: '2026-10-05T06:00:00+08:00', data: data(tab) } };
}
function view(tab: string): LessonView {
  const id = `g6-${tab}`;
  return { protocolVersion: 2, lessonPlanId: id, subjectId: 'chinese', classId: 'g6-isolated-class', revision: 1, currentRevisionId: `${id}-r1`, replayed: false,
    currentRevision: { protocolVersion: 2, lessonPlanId: id, revisionId: `${id}-r1`, version: 1, data: data(tab), contentHash: `${id}-hash`, source: 'manual', contextSnapshot: { subjectId: 'chinese', classId: 'g6-isolated-class', classNameAtSave: '隔离班', analysis: null }, analysisRunId: null, acceptedProposalId: null, importEnvelope: null, selectedFields: [], processMetadata: [], reviewState: 'unreviewed', createdAt: '2026-10-05T00:00:00Z' } };
}
function bag() {
  const values = new Map<string, string>(); let readFault = false, removeFault = false, retainOnRemove = false;
  const storage: Storage = { getItem: vi.fn((key: string) => { if (readFault) throw new Error('G6 isolated read failure'); return values.get(key) ?? null; }), setItem: vi.fn((key: string, raw: string) => { values.set(key, raw); }), removeItem: vi.fn((key: string) => { if (removeFault) throw new Error('G6 isolated remove failure'); if (!retainOnRemove) values.delete(key); }), clear: () => values.clear(), key: (index) => [...values.keys()][index] ?? null, get length() { return values.size; } };
  return { values, storage, failRead: (value: boolean) => { readFault = value; }, failRemove: (value: boolean) => { removeFault = value; }, retainOnRemove: (value: boolean) => { retainOnRemove = value; } };
}
function deferred<T>() { let resolve!: (value: T) => void, reject!: (cause: unknown) => void; const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; }
function mount(kind: Kind, store: ReturnType<typeof bag>, verifyWrite?: () => boolean | Promise<boolean>) {
  const key = `zhiqikeyuan:lesson-plan:operation:v1:${kind}`, identity = `lesson|new|${kind}`;
  const hook = renderHook(({ identity: current }) => useLessonOperation<Payload, LessonView>(current, { ...browserOperationRecovery(key, store.storage), verifyWrite }), { initialProps: { identity } });
  return { hook, key, identity };
}
async function start(kind: Kind, hook: ReturnType<typeof mount>['hook'], tab: string) {
  const reply = deferred<LessonView>(), send = vi.fn<(operation: FrozenSubmission<Payload>) => Promise<LessonView>>(() => reply.promise);
  let waiting!: Promise<SubmissionReceipt<Payload, LessonView> | null>;
  act(() => { waiting = hook.result.current.run(payload(kind, tab), send, tab === 'A' ? 2 : 3, `${tab}-original-load`); });
  await waitFor(() => expect(send).toHaveBeenCalledTimes(1));
  return { reply, send, waiting, operation: send.mock.calls[0][0] };
}
async function acknowledge(pending: Awaited<ReturnType<typeof start>>, outcome: 'success' | 'failure', tab: string) {
  await act(async () => { if (outcome === 'success') pending.reply.resolve(view(tab)); else pending.reply.reject(new ApiError('INVALID_SELECTION', `${tab}明确422`, 422, false)); await pending.waiting; });
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('G6 complete own and foreign explicit ACK behavior', () => {
  for (const kind of kinds) {
    it.each(['success', 'failure'] as const)(`${kind} own %s clears the exact complete first package`, async (outcome) => {
      const store = bag(), { hook, key, identity } = mount(kind, store), pending = await start(kind, hook, 'A');
      expect(pending.operation.payload).toEqual(payload(kind, 'A')); expect(pending.operation.metadata).toEqual({ contextKey: identity, originalEditGeneration: 2, loadGeneration: 'A-original-load' });
      expect(JSON.parse(store.values.get(key)!).operation).toEqual(pending.operation); await acknowledge(pending, outcome, 'A');
      expect(store.values.has(key)).toBe(false); expect(hook.result.current.recoveryBlocked).toBe(false); expect(hook.result.current.resultUnknown).toBe(false); expect(hook.result.current.cleanupOutcome()).toBeNull(); expect(pending.send).toHaveBeenCalledTimes(1);
    });
    it.each(['success', 'failure'] as const)(`${kind} A %s ACK preserves an isolated legal foreign package and stays blocked`, async (outcome) => {
      const store = bag(), { hook, key, identity } = mount(kind, store), pendingA = await start(kind, hook, 'A');
      // G7：另一会话的完整合法包以隔离构造取得前置；旧夹具依赖的“第二次正常写入”已被写入闸门正确禁止。
      const foreign = { operationId: `${kind}-foreign-isolated`, submissionId: `${kind}-foreign-isolated`, payloadKey: stablePayloadKey(payload(kind, 'B')), payload: payload(kind, 'B'), metadata: { contextKey: identity, originalEditGeneration: 3, loadGeneration: 'B-original-load' } };
      validateOperation(foreign, identity);
      const rawB = JSON.stringify({ schemaVersion: 1, operation: foreign }); store.values.set(key, rawB);
      const writes = vi.mocked(store.storage.setItem).mock.calls.length, removes = vi.mocked(store.storage.removeItem).mock.calls.length;
      await acknowledge(pendingA, outcome, 'A'); expect(hook.result.current.cleanupOutcome()).toMatchObject({ type: outcome, operation: pendingA.operation });
      expect(hook.result.current.recoveryBlocked).toBe(true); expect(hook.result.current.resultUnknown).toBe(false); expect(hook.result.current.cacheError).toContain('不属于本次明确结果'); expect(hook.result.current.cacheError).toContain('不会重新发送HTTP');
      await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(false); expect(await hook.result.current.run(payload(kind, 'later'), pendingA.send, 9)).toBeNull(); });
      expect(store.values.get(key)).toBe(rawB); expect(hook.result.current.cleanupOutcome()?.operation).toEqual(pendingA.operation);
      expect(store.storage.setItem).toHaveBeenCalledTimes(writes); expect(store.storage.removeItem).toHaveBeenCalledTimes(removes); expect(pendingA.send).toHaveBeenCalledTimes(1);
      if (outcome === 'success') expect(hook.result.current.cleanupOutcome()).toMatchObject({ receipt: { result: view('A'), current: true } });
      else expect(hook.result.current.cleanupOutcome()).toMatchObject({ error: { status: 422 } });
    });
    it.each(['success', 'failure'] as const)(`${kind} after the earlier foreign owner explicitly ends A %s legally completes storage-only cleanup`, async (outcome) => {
      const store = bag(), { hook, key, identity } = mount(kind, store), pendingA = await start(kind, hook, 'A');
      const foreign = { operationId: `${kind}-foreign-isolated`, submissionId: `${kind}-foreign-isolated`, payloadKey: stablePayloadKey(payload(kind, 'B')), payload: payload(kind, 'B'), metadata: { contextKey: identity, originalEditGeneration: 3, loadGeneration: 'B-original-load' } };
      validateOperation(foreign, identity);
      const rawB = JSON.stringify({ schemaVersion: 1, operation: foreign }); store.values.set(key, rawB);
      await acknowledge(pendingA, outcome, 'A'); await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(false); });
      expect(store.values.get(key)).toBe(rawB);
      // 先在键的会话在 foreign 已存在时挂载恢复该合法包，再显式重放自己的原包并明确成功，只为自己的包腾空。
      const b = mount(kind, store);
      await waitFor(() => { expect(b.hook.result.current.ready).toBe(true); expect(b.hook.result.current.pending).toEqual(foreign); });
      const sendB = vi.fn<(operation: FrozenSubmission<Payload>) => Promise<LessonView>>(async () => view('B'));
      await act(async () => { await b.hook.result.current.run(payload(kind, 'B'), sendB, 3); });
      expect(sendB).toHaveBeenCalledTimes(1); expect(sendB.mock.calls[0][0]).toEqual(foreign); expect(store.values.has(key)).toBe(false);
      const owned = hook.result.current.cleanupOutcome(); expect(owned?.operation).toEqual(pendingA.operation);
      await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(true); });
      expect(hook.result.current.recoveryBlocked).toBe(false); expect(hook.result.current.cleanupOutcome()).toBeNull(); expect(store.values.has(key)).toBe(false);
      expect(hook.result.current.result?.lessonPlanId ?? null).toBe(outcome === 'success' ? 'g6-A' : null); expect(pendingA.send).toHaveBeenCalledTimes(1); expect(sendB).toHaveBeenCalledTimes(1);
    });
  }
});

const bodyMutations: { name: string; change: (body: LessonPlanData) => void }[] = [
  ...(['title', 'totalLessons', 'currentLessonNo', 'otherTypeText', 'coreCompetencies', 'keyPoints', 'teachingDesign', 'exercises', 'reflection'] as const).map((field) => ({ name: field, change: (body: LessonPlanData) => { body[field] += 'foreign'; } })),
  { name: 'lessonTypes', change: (body) => { body.lessonTypes = ['other', 'review']; } },
  { name: 'process', change: (body) => { body.process[0].design += 'foreign'; } },
  { name: 'secondary', change: (body) => { body.process[0].secondary += 'foreign'; } },
];
describe('G6 equality covers all frozen body fields rather than IDs alone', () => {
  for (const kind of kinds) {
    for (const mutation of bodyMutations) {
      it(`${kind} rejects same-ID valid package with different ${mutation.name} before ACK and retry`, async () => {
        const store = bag(), { hook, key, identity } = mount(kind, store), pending = await start(kind, hook, 'A'), foreign = structuredClone(pending.operation);
        mutation.change('data' in foreign.payload ? foreign.payload.data : foreign.payload.draft.data); foreign.payloadKey = stablePayloadKey(foreign.payload); validateOperation(foreign, identity);
        const raw = JSON.stringify({ schemaVersion: 1, operation: foreign }); store.values.set(key, raw); const removes = vi.mocked(store.storage.removeItem).mock.calls.length;
        await acknowledge(pending, 'success', 'A'); await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(false); });
        expect(store.values.get(key)).toBe(raw); expect(hook.result.current.cleanupOutcome()?.operation).toEqual(pending.operation); expect(store.storage.removeItem).toHaveBeenCalledTimes(removes); expect(pending.send).toHaveBeenCalledTimes(1);
      });
    }
    it.each(['context', 'subjectId', 'classId', 'loadGeneration', 'editGeneration', 'operationId'] as const)(`${kind} refuses valid same-body foreign %s`, async (field) => {
      const store = bag(), { hook, key, identity } = mount(kind, store), pending = await start(kind, hook, 'A'), foreign = structuredClone(pending.operation);
      if (field === 'context') foreign.payload.context = { ...context, selectedKnowledgePointIds: ['g6-other-kp'] };
      else if (field === 'subjectId' || field === 'classId') foreign.payload[field] = `foreign-${field}`;
      else if (field === 'loadGeneration') foreign.metadata!.loadGeneration = 'foreign-load';
      else if (field === 'editGeneration') foreign.metadata!.originalEditGeneration += 1;
      else { foreign.operationId = 'foreign-id'; foreign.submissionId = 'foreign-id'; }
      foreign.payloadKey = stablePayloadKey(foreign.payload); validateOperation(foreign, identity); const raw = JSON.stringify({ schemaVersion: 1, operation: foreign }); store.values.set(key, raw);
      await acknowledge(pending, 'failure', 'A'); await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(false); }); expect(store.values.get(key)).toBe(raw); expect(hook.result.current.cleanupOutcome()).toMatchObject({ type: 'failure', operation: pending.operation }); expect(pending.send).toHaveBeenCalledTimes(1);
    });
  }
  it('create source rule/manual difference is an ownership difference', async () => {
    const store = bag(), { hook, key, identity } = mount('create', store), pending = await start('create', hook, 'A'), foreign = structuredClone(pending.operation) as FrozenSubmission<Omit<LessonCreateRequest, 'submissionId'>>;
    foreign.payload.source = 'manual'; foreign.payloadKey = stablePayloadKey(foreign.payload); validateOperation(foreign, identity); const raw = JSON.stringify({ schemaVersion: 1, operation: foreign }); store.values.set(key, raw);
    await acknowledge(pending, 'success', 'A'); await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(false); }); expect(store.values.get(key)).toBe(raw); expect(pending.send).toHaveBeenCalledTimes(1);
  });
  it.each(['revision', 'updatedAt'] as const)('import preserves whole draft envelope when foreign %s differs', async (field) => {
    const store = bag(), { hook, key, identity } = mount('import', store), pending = await start('import', hook, 'A'), foreign = structuredClone(pending.operation) as FrozenSubmission<Omit<LessonImportRequest, 'submissionId'>>;
    if (field === 'revision') foreign.payload.draft.revision += 1; else foreign.payload.draft.updatedAt = '2026-10-05T07:00:00+08:00'; foreign.payloadKey = stablePayloadKey(foreign.payload); validateOperation(foreign, identity); const raw = JSON.stringify({ schemaVersion: 1, operation: foreign }); store.values.set(key, raw);
    await acknowledge(pending, 'success', 'A'); await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(false); }); expect(store.values.get(key)).toBe(raw); expect(pending.send).toHaveBeenCalledTimes(1);
  });
});

describe('G6 normal ACK protects invalid reads and verifies legal cleanup', () => {
  for (const kind of kinds) {
    for (const outcome of ['success', 'failure'] as const) {
      it.each(['corrupt', 'invalid-identity', 'unreadable'] as const)(`${kind} ${outcome} ACK and retry preserve %s cache without extra HTTP`, async (fault) => {
        const store = bag(), { hook, key } = mount(kind, store), pending = await start(kind, hook, 'A');
        if (fault === 'corrupt') store.values.set(key, '{G6 bad original');
        if (fault === 'invalid-identity') store.values.set(key, JSON.stringify({ schemaVersion: 1, operation: { ...pending.operation, payloadKey: 'invalid' } }));
        if (fault === 'unreadable') store.failRead(true);
        const raw = store.values.get(key), removes = vi.mocked(store.storage.removeItem).mock.calls.length;
        await acknowledge(pending, outcome, 'A'); expect(hook.result.current.recoveryBlocked).toBe(true); expect(hook.result.current.cleanupOutcome()).toMatchObject({ type: outcome, operation: pending.operation });
        await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(false); }); expect(store.values.get(key)).toBe(raw); expect(store.storage.removeItem).toHaveBeenCalledTimes(removes); expect(pending.send).toHaveBeenCalledTimes(1);
        store.failRead(false); store.values.set(key, JSON.stringify({ schemaVersion: 1, operation: pending.operation }));
        await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(true); }); expect(store.values.has(key)).toBe(false); expect(pending.send).toHaveBeenCalledTimes(1);
      });
      it(`${kind} ${outcome} ACK accepts legitimately already-empty cache`, async () => {
        const store = bag(), { hook, key } = mount(kind, store), pending = await start(kind, hook, 'A'); store.values.delete(key); await acknowledge(pending, outcome, 'A');
        expect(hook.result.current.recoveryBlocked).toBe(false); expect(hook.result.current.cleanupOutcome()).toBeNull(); expect(store.values.has(key)).toBe(false); expect(pending.send).toHaveBeenCalledTimes(1);
      });
    }
    it(`${kind} ineffective removal keeps the explicit receipt blocked until verified storage-only retry`, async () => {
      const store = bag(), { hook, key } = mount(kind, store), pending = await start(kind, hook, 'A'), raw = store.values.get(key); store.retainOnRemove(true); await acknowledge(pending, 'success', 'A');
      expect(hook.result.current.cacheError).toContain('清理后核验不一致'); expect(hook.result.current.cleanupOutcome()).toMatchObject({ type: 'success', receipt: { result: view('A') } }); expect(store.values.get(key)).toBe(raw);
      store.retainOnRemove(false); await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(true); }); expect(store.values.has(key)).toBe(false); expect(pending.send).toHaveBeenCalledTimes(1);
    });
    it(`${kind} read-back error retains known receipt and later empty cleanup never resends`, async () => {
      const store = bag(), { hook, key } = mount(kind, store), pending = await start(kind, hook, 'A'), originalRemove = store.storage.removeItem;
      store.storage.removeItem = vi.fn((name) => { originalRemove(name); store.failRead(true); }); await acknowledge(pending, 'success', 'A');
      expect(hook.result.current.recoveryBlocked).toBe(true); expect(store.values.has(key)).toBe(false); expect(hook.result.current.cleanupOutcome()).toMatchObject({ type: 'success', operation: pending.operation });
      store.failRead(false); store.storage.removeItem = originalRemove; await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(true); }); expect(pending.send).toHaveBeenCalledTimes(1);
    });
  }
});

describe('G6 delayed results keep mounted session ownership', () => {
  for (const kind of kinds) {
    it(`${kind} unmount during ACK cache read prevents the following delete`, async () => {
      const store = bag(), { hook, key } = mount(kind, store), pending = await start(kind, hook, 'A'), raw = store.values.get(key), getter = hook.result.current.cleanupOutcome;
      const read = store.storage.getItem; let armed = true;
      store.storage.getItem = vi.fn((name) => { const value = read(name); if (armed) { armed = false; hook.unmount(); } return value; });
      await acknowledge(pending, 'success', 'A'); expect(store.values.get(key)).toBe(raw); expect(store.storage.removeItem).not.toHaveBeenCalled(); expect(getter()).toBeNull(); expect(pending.send).toHaveBeenCalledTimes(1);
    });
    it(`${kind} document/load change during ACK read cannot delete or block the new session`, async () => {
      const store = bag(), originalIdentity = `lesson|g6-old|${kind}`;
      const hook = renderHook(({ identity }) => useLessonOperation<Payload, LessonView>(identity, browserOperationRecovery(`g6-session-${identity}`, store.storage)), { initialProps: { identity: originalIdentity } });
      const pending = await start(kind, hook, 'A'), key = `g6-session-${originalIdentity}`, raw = store.values.get(key), read = store.storage.getItem; let armed = true;
      store.storage.getItem = vi.fn((name) => { const value = read(name); if (armed) { armed = false; flushSync(() => { hook.rerender({ identity: `lesson|g6-new|${kind}` }); }); } return value; });
      await acknowledge(pending, 'success', 'A'); expect(store.values.get(key)).toBe(raw); expect(store.storage.removeItem).not.toHaveBeenCalled(); expect(hook.result.current.ready).toBe(true); expect(hook.result.current.recoveryBlocked).toBe(false); expect(hook.result.current.cleanupOutcome()).toBeNull(); expect(hook.result.current.pending).toBeNull(); expect(pending.send).toHaveBeenCalledTimes(1);
    });
    it.each(['success', 'failure'] as const)(`${kind} unmounted late %s cannot delete original bytes`, async (outcome) => {
      const store = bag(), { hook, key } = mount(kind, store), pending = await start(kind, hook, 'A'), raw = store.values.get(key), getter = hook.result.current.cleanupOutcome;
      hook.unmount(); await acknowledge(pending, outcome, 'A'); expect(store.values.get(key)).toBe(raw); expect(getter()).toBeNull(); expect(store.storage.removeItem).not.toHaveBeenCalled(); expect(pending.send).toHaveBeenCalledTimes(1);
    });
    it.each(['success', 'failure'] as const)(`${kind} new document before late %s is neither cleaned nor blocked by old receipt`, async (outcome) => {
      const store = bag(), { hook, key } = mount(kind, store), pending = await start(kind, hook, 'A');
      store.values.delete(key); hook.rerender({ identity: `lesson|g6-other-document|${kind}` }); const next = await start(kind, hook, 'B'), raw = store.values.get(key);
      await acknowledge(pending, outcome, 'A'); expect(store.values.get(key)).toBe(raw); expect(hook.result.current.recoveryBlocked).toBe(false); expect(hook.result.current.cleanupOutcome()).toBeNull(); expect(hook.result.current.pending).toEqual(next.operation); expect(store.storage.removeItem).not.toHaveBeenCalled();
      await act(async () => { next.reply.reject(new ApiError('NETWORK', 'new document unknown', 0, true)); await next.waiting; }); expect(store.values.get(key)).toBe(raw); expect(hook.result.current.resultUnknown).toBe(true); expect(next.send).toHaveBeenCalledTimes(1); expect(pending.send).toHaveBeenCalledTimes(1);
    });
  }
});
