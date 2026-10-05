import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '@/services/api-client';
import { stablePayloadKey, type FrozenSubmission, type SubmissionReceipt } from '@/features/assessments/hooks';
import type { LessonCreateRequest, LessonImportRequest, LessonPlanData, LessonView } from '@/contracts/lesson-plans';
import { browserOperationRecovery, useLessonOperation, type OperationRecovery } from './model/useLessonOperation';
import { validateOperation } from './model/server-cache';

type Kind = 'create' | 'import';
type Payload = Omit<LessonCreateRequest, 'submissionId'> | Omit<LessonImportRequest, 'submissionId'>;
const kinds = ['create', 'import'] as const;
const context = (kind: Kind) => `lesson|new|${kind}`;
const selected = { analysisRunId: 'g7-fixed-analysis', selectedKnowledgePointIds: ['g7-kp'] };
function data(tab: string): LessonPlanData {
  return { title: `G7独立${tab}完整课题`, totalLessons: '3', currentLessonNo: '2', lessonTypes: ['review', 'new'], otherTypeText: '中文课型<>', coreCompetencies: `${tab}素养`, keyPoints: `${tab}重点`, teachingDesign: `${tab}设计`.repeat(6), process: [{ id: `${tab}-process`, stage: '环节', design: `${tab}活动`.repeat(4), secondary: `${tab}二次备课` }], exercises: `${tab}练习`, reflection: `${tab}反思` };
}
function payload(kind: Kind, tab: string): Payload {
  const common = { subjectId: 'chinese', classId: 'g7-isolated-class', context: structuredClone(selected) };
  return kind === 'create' ? { ...common, data: data(tab), source: 'manual' } : { ...common, draft: { schemaVersion: 1, revision: 13, updatedAt: '2026-10-05T06:00:00+08:00', data: data(tab) } };
}
function view(tab: string): LessonView {
  const id = `g7-${tab}`;
  return { protocolVersion: 2, lessonPlanId: id, subjectId: 'chinese', classId: 'g7-isolated-class', revision: 1, currentRevisionId: `${id}-r1`, replayed: false,
    currentRevision: { protocolVersion: 2, lessonPlanId: id, revisionId: `${id}-r1`, version: 1, data: data(tab), contentHash: `${id}-hash`, source: 'manual', contextSnapshot: { subjectId: 'chinese', classId: 'g7-isolated-class', classNameAtSave: '隔离班', analysis: null }, analysisRunId: null, acceptedProposalId: null, importEnvelope: null, selectedFields: [], processMetadata: [], reviewState: 'unreviewed', createdAt: '2026-10-05T00:00:00Z' } };
}
function bag() {
  const values = new Map<string, string>(); let readFault = false, refuseWrite = false;
  const storage: Storage = { getItem: vi.fn((key: string) => { if (readFault) throw new Error('G7 isolated read failure'); return values.get(key) ?? null; }), setItem: vi.fn((key: string, raw: string) => { if (refuseWrite) throw new Error('G7 isolated quota failure'); values.set(key, raw); }), removeItem: vi.fn((key: string) => { values.delete(key); }), clear: () => values.clear(), key: (index) => [...values.keys()][index] ?? null, get length() { return values.size; } };
  return { values, storage, failRead: (value: boolean) => { readFault = value; }, refuseWrite: (value: boolean) => { refuseWrite = value; } };
}
function deferred<T>() { let resolve!: (value: T) => void, reject!: (cause: unknown) => void; const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; }
function operation(kind: Kind, tab: string, contextKey: string, editGeneration = 3, load = `${tab}-load`): FrozenSubmission<Payload> {
  return { operationId: `g7-${kind}-${tab}`, submissionId: `g7-${kind}-${tab}`, payloadKey: stablePayloadKey(payload(kind, tab)), payload: payload(kind, tab), metadata: { contextKey, originalEditGeneration: editGeneration, loadGeneration: load } };
}
function mount(kind: Kind, store: ReturnType<typeof bag>, recovery?: (base: OperationRecovery) => OperationRecovery) {
  const key = `zhiqikeyuan:lesson-plan:operation:v1:${kind}`, identity = context(kind);
  const hook = renderHook(() => useLessonOperation<Payload, LessonView>(identity, recovery ? recovery(browserOperationRecovery(key, store.storage)) : browserOperationRecovery(key, store.storage)));
  return { hook, key, identity };
}
async function ack(pending: { reply: { resolve: (value: LessonView) => void; reject: (cause: unknown) => void }; waiting: Promise<SubmissionReceipt<Payload, LessonView> | null> }, outcome: 'success' | '422' | 'unknown', tab = 'A') {
  await act(async () => { if (outcome === 'success') pending.reply.resolve(view(tab)); else if (outcome === '422') pending.reply.reject(new ApiError('INVALID_SELECTION', `${tab}明确422`, 422, false)); else pending.reply.reject(new ApiError('NETWORK', `${tab}回执丢失`, 0, true)); await pending.waiting; });
}
async function start(hook: ReturnType<typeof mount>['hook'], kind: Kind, tab: string) {
  const reply = deferred<LessonView>(), send = vi.fn<(operation: FrozenSubmission<Payload>) => Promise<LessonView>>(() => reply.promise);
  let waiting!: Promise<SubmissionReceipt<Payload, LessonView> | null>;
  act(() => { waiting = hook.result.current.run(payload(kind, tab), send, tab === 'A' ? 2 : 3, `${tab}-original-load`); });
  await waitFor(() => expect(send).toHaveBeenCalledTimes(1));
  return { reply, send, waiting, operation: send.mock.calls[0][0] };
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('G7 owned write gate covers normal send and public write retry', () => {
  for (const kind of kinds) {
    it(`${kind} empty key writes the frozen package before HTTP and explicit success cleans it`, async () => {
      const store = bag(), { hook, key, identity } = mount(kind, store), pending = await start(hook, kind, 'A');
      const raw = store.values.get(key)!; validateOperation(JSON.parse(raw).operation, identity);
      expect(JSON.parse(raw).operation).toEqual(pending.operation);
      await ack(pending, 'success');
      expect(store.values.has(key)).toBe(false); expect(pending.send).toHaveBeenCalledTimes(1);
    });
    it(`${kind} quota first write adds no HTTP and keeps the own operation recoverable`, async () => {
      const store = bag(); store.refuseWrite(true);
      const { hook, key } = mount(kind, store), send = vi.fn();
      await act(async () => { await hook.result.current.run(payload(kind, 'A'), send, 2, 'A-original-load'); });
      expect(send).not.toHaveBeenCalled(); expect(store.values.has(key)).toBe(false);
      expect(hook.result.current.recoveryKind).toBe('write'); expect(hook.result.current.recoveryBlocked).toBe(true); expect(hook.result.current.cacheError).toContain('尚未发送HTTP');
      const packet = hook.result.current.pending!; validateOperation(packet, context(kind));
      store.refuseWrite(false);
      await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(true); });
      expect(JSON.parse(store.values.get(key)!).operation).toEqual(packet); expect(send).not.toHaveBeenCalled();
      const replay = vi.fn<(operation: FrozenSubmission<Payload>) => Promise<LessonView>>(async () => view('A'));
      await act(async () => { await hook.result.current.run(payload(kind, 'A'), replay, 2); });
      expect(replay).toHaveBeenCalledTimes(1); expect(replay.mock.calls[0][0].submissionId).toBe(packet.submissionId); expect(replay.mock.calls[0][0].payloadKey).toBe(packet.payloadKey);
    });
    it(`${kind} later foreign unknown owner blocks a first run without HTTP or byte replacement`, async () => {
      const store = bag(), a = mount(kind, store), b = mount(kind, store);
      const pendingB = await start(b.hook, kind, 'B'); const rawB = store.values.get(b.key)!;
      await ack(pendingB, 'unknown', 'B');
      expect(b.hook.result.current.resultUnknown).toBe(true);
      const sendA = vi.fn();
      await act(async () => { expect(await a.hook.result.current.run(payload(kind, 'A'), sendA, 2, 'A-original-load')).toBeNull(); });
      expect(sendA).not.toHaveBeenCalled(); expect(store.values.get(a.key)).toBe(rawB);
      expect(a.hook.result.current.recoveryKind).toBe('write'); expect(a.hook.result.current.recoveryBlocked).toBe(true); expect(a.hook.result.current.resultUnknown).toBe(false);
      expect(a.hook.result.current.cacheError).toContain('已属于另一原操作'); expect(a.hook.result.current.cacheError).toContain('尚未发送HTTP');
      expect(b.hook.result.current.pending).toEqual(pendingB.operation); expect(store.values.get(b.key)).toBe(rawB);
    });
    it(`${kind} quota failure then foreign unknown owner refuses the public write retry and preserves bytes`, async () => {
      const store = bag(); store.refuseWrite(true);
      const a = mount(kind, store), b = mount(kind, store);
      const sendA = vi.fn();
      await act(async () => { await a.hook.result.current.run(payload(kind, 'A'), sendA, 2, 'A-original-load'); });
      const packetA = a.hook.result.current.pending!; expect(a.hook.result.current.recoveryKind).toBe('write');
      store.refuseWrite(false);
      const pendingB = await start(b.hook, kind, 'B'); const rawB = store.values.get(b.key)!;
      await ack(pendingB, 'unknown', 'B');
      const writes = vi.mocked(store.storage.setItem).mock.calls.length;
      await act(async () => { expect(await a.hook.result.current.retryRecoveryWrite()).toBe(false); });
      expect(store.values.get(b.key)).toBe(rawB); expect(store.storage.setItem).toHaveBeenCalledTimes(writes);
      expect(a.hook.result.current.recoveryBlocked).toBe(true); expect(a.hook.result.current.pending).toEqual(packetA); expect(sendA).not.toHaveBeenCalled();
      expect(b.hook.result.current.resultUnknown).toBe(true); expect(b.hook.result.current.pending).toEqual(pendingB.operation);
    });
    it(`${kind} own package recovered on mount permits normal replay with the unchanged complete identity`, async () => {
      const store = bag(), own = operation(kind, 'A', context(kind));
      store.values.set(`zhiqikeyuan:lesson-plan:operation:v1:${kind}`, JSON.stringify({ schemaVersion: 1, operation: own }));
      const { hook, key } = mount(kind, store);
      await waitFor(() => { expect(hook.result.current.ready).toBe(true); expect(hook.result.current.pending).toEqual(own); });
      const replay = vi.fn<(operation: FrozenSubmission<Payload>) => Promise<LessonView>>(async () => view('A'));
      await act(async () => { await hook.result.current.run(payload(kind, 'A'), replay, 2); });
      expect(replay).toHaveBeenCalledTimes(1); expect(replay.mock.calls[0][0]).toEqual(own);
      const written = JSON.parse(vi.mocked(store.storage.setItem).mock.calls.at(-1)![1] as string);
      expect(written.operation).toEqual(own); expect(store.values.has(key)).toBe(false);
    });
    it(`${kind} corrupt or unreadable stored bytes after a failed write stay protected on retry`, async () => {
      for (const fault of ['corrupt', 'unreadable'] as const) {
        const store = bag(); store.refuseWrite(true);
        const { hook, key } = mount(kind, store), send = vi.fn();
        await act(async () => { await hook.result.current.run(payload(kind, 'A'), send, 2); }); const packet = hook.result.current.pending!;
        const raw = fault === 'corrupt' ? '{G7 protected source' : JSON.stringify({ schemaVersion: 1, operation: packet }); store.values.set(key, raw);
        if (fault === 'unreadable') store.failRead(true);
        store.refuseWrite(false); const writes = vi.mocked(store.storage.setItem).mock.calls.length;
        await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(false); });
        expect(store.values.get(key)).toBe(raw); expect(store.storage.setItem).toHaveBeenCalledTimes(writes); expect(hook.result.current.recoveryBlocked).toBe(true); expect(hook.result.current.pending).toEqual(packet); expect(send).not.toHaveBeenCalled();
        cleanup(); vi.restoreAllMocks();
      }
    });
    it(`${kind} foreign context package blocks the normal run and is never overwritten`, async () => {
      const store = bag(), { hook, key } = mount(kind, store);
      const foreign = operation(kind, 'A', `lesson|new|other-${kind}`); store.values.set(key, JSON.stringify({ schemaVersion: 1, operation: foreign }));
      const raw = store.values.get(key)!, send = vi.fn();
      await act(async () => { expect(await hook.result.current.run(payload(kind, 'A'), send, 2)).toBeNull(); });
      expect(send).not.toHaveBeenCalled(); expect(store.values.get(key)).toBe(raw); expect(hook.result.current.recoveryBlocked).toBe(true);
      expect(JSON.parse(raw).operation.metadata.contextKey).toBe(`lesson|new|other-${kind}`);
    });
    it(`${kind} failed verifyWrite keeps the retry blocked without sending`, async () => {
      const store = bag(); store.refuseWrite(true);
      const verify = vi.fn(async () => false);
      const { hook, key } = mount(kind, store, (base) => ({ ...base, verifyWrite: verify })), send = vi.fn();
      await act(async () => { await hook.result.current.run(payload(kind, 'A'), send, 2); }); const packet = hook.result.current.pending!;
      store.refuseWrite(false);
      await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(false); });
      expect(verify).toHaveBeenCalledTimes(1); expect(store.values.get(key)).toBe(JSON.stringify({ schemaVersion: 1, operation: packet })); expect(hook.result.current.recoveryBlocked).toBe(true); expect(send).not.toHaveBeenCalled();
    });
    it(`${kind} prepare exception adds no HTTP and foreign packages never run prepare`, async () => {
      const store = bag(), prepare = vi.fn();
      const { hook, key } = mount(kind, store, (base) => ({ ...base, prepare })), send = vi.fn();
      const foreign = operation(kind, 'B', context(kind)); store.values.set(key, JSON.stringify({ schemaVersion: 1, operation: foreign }));
      await act(async () => { await hook.result.current.run(payload(kind, 'A'), send, 2); });
      expect(prepare).not.toHaveBeenCalled(); expect(send).not.toHaveBeenCalled(); expect(store.values.get(key)).toBe(JSON.stringify({ schemaVersion: 1, operation: foreign }));
      cleanup(); vi.restoreAllMocks();

      const store2 = bag(), hook2 = mount(kind, store2, (base) => ({ ...base, prepare: () => { throw new Error('G7 prepare failure'); } })).hook, send2 = vi.fn();
      await act(async () => { await hook2.result.current.run(payload(kind, 'A'), send2, 2); });
      expect(send2).not.toHaveBeenCalled(); expect(store2.values.size).toBe(0); expect(hook2.result.current.recoveryBlocked).toBe(true); expect(hook2.result.current.cacheError).toContain('G7 prepare failure');
    });
    it(`${kind} unmount during prepare prevents the write and the send`, async () => {
      const store = bag();
      const key = `zhiqikeyuan:lesson-plan:operation:v1:${kind}`, identity = context(kind);
      const holder: { unmount: () => void } = { unmount: () => {} };
      const hook = renderHook(() => useLessonOperation<Payload, LessonView>(identity, { ...browserOperationRecovery(key, store.storage), prepare: () => holder.unmount() }));
      holder.unmount = hook.unmount;
      await waitFor(() => expect(hook.result.current.ready).toBe(true));
      const send = vi.fn();
      await act(async () => { await hook.result.current.run(payload(kind, 'A'), send, 2); });
      expect(send).not.toHaveBeenCalled(); expect(store.values.size).toBe(0);
    });
  }
});
