import React from 'react';
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { LessonView } from '@/contracts/lesson-plans';
import { lessonPlanApi } from '@/services/lesson-plans-api';
import { ApiError } from '@/services/api-client';
import { NavigationPreference } from '@/components/layout/NavigationPreference';
import { DocumentGateway } from './components/DocumentGateway';
import { DocumentsPanel } from './components/DocumentsPanel';
import { LeaveProtection } from './components/LeaveProtection';
import { useLessonEditor } from './model/EditorContext';
import { useLessonDocument } from './model/DocumentContext';
import { emptyData } from './model/defaults';
import { LEGACY_KEY, serverSessionKey } from './model/server-cache';
import { browserOperationRecovery, useLessonOperation } from './model/useLessonOperation';
import { stablePayloadKey, type FrozenSubmission } from '@/features/assessments/hooks';

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => router, usePathname: () => '/lesson-plans' }));
const analysis = { analysisRunId: 'g5-analysis-fixed', inputHash: 'g5-input', scoreRevisionId: 'g5-score-fixed', paperRevisionId: 'g5-paper-fixed', className: null, classNameNote: '隔离班', knowledgePoints: [
  { knowledgePointId: 'g5-kp-a', knowledgeRevisionId: 'g5-kp-fixed-a', name: '主知识', role: 'primary' as const },
  { knowledgePointId: 'g5-kp-b', knowledgeRevisionId: 'g5-kp-fixed-b', name: '关联知识', role: 'secondary' as const },
] };
const context = { analysisRunId: analysis.analysisRunId, selectedKnowledgePointIds: ['g5-kp-a', 'g5-kp-b'] };
const data = { ...structuredClone(emptyData), title: '完整教师课题', totalLessons: '3', currentLessonNo: '2', lessonTypes: ['review', 'new', 'review'] as typeof emptyData.lessonTypes, otherTypeText: '特殊课型', coreCompetencies: '教师素养', keyPoints: '教师重难点', teachingDesign: '长教学设计'.repeat(10), process: [{ id: 'teacher-process', stage: '教师环节', design: '原活动'.repeat(10), secondary: '完整二次备课'.repeat(10) }], exercises: '教师练习', reflection: '教师反思' };
function view(id = 'g5-current', version = 1): LessonView {
  const revisionId = `${id}-fixed-${version}`;
  return { protocolVersion: 2, lessonPlanId: id, subjectId: 'chinese', classId: 'g5-class', revision: version, currentRevisionId: revisionId, replayed: false,
    currentRevision: { protocolVersion: 2, lessonPlanId: id, revisionId, version, data: structuredClone(data), contentHash: `hash-${version}`, source: 'manual', contextSnapshot: { subjectId: 'chinese', classId: 'g5-class', classNameAtSave: '隔离班', analysis }, analysisRunId: analysis.analysisRunId, acceptedProposalId: null, importEnvelope: null, selectedFields: [], processMetadata: [], reviewState: 'unreviewed', createdAt: '2026-10-05T00:00:00Z' } };
}
function bag() {
  const values = new Map<string, string>(); let removeFault = false, writeFault = false, readFault = false;
  const storage = { getItem: vi.fn((key: string) => { if (readFault) throw new Error('G5 isolated read failure'); return values.get(key) ?? null; }), setItem: vi.fn((key: string, raw: string) => { if (writeFault) throw new Error('G5 isolated write failure'); values.set(key, raw); }), removeItem: vi.fn((key: string) => { if (removeFault && key.includes('operation:v1:')) throw new Error('G5 isolated cleanup failure'); values.delete(key); }), clear: () => values.clear(), key: (index: number) => [...values.keys()][index] ?? null, get length() { return values.size; } } satisfies Storage;
  return { values, storage, failRemove: (value: boolean) => { removeFault = value; }, failWrite: (value: boolean) => { writeFault = value; }, failRead: (value: boolean) => { readFault = value; } };
}
function Host() {
  const editor = useLessonEditor(), doc = useLessonDocument();
  return <><label>G5课题<input value={editor.data.title} onChange={(event) => editor.set({ title: event.target.value })} /></label><DocumentsPanel /><LeaveProtection /><output aria-label="G5完整状态">{JSON.stringify({ documentId: doc.documentId, data: editor.data, context: editor.server?.cache?.context, source: editor.server?.cache?.source, selection: doc.selection })}</output></>;
}
function api(send: ReturnType<typeof vi.fn>, kind: 'create' | 'import') {
  return { ...lessonPlanApi, ...(kind === 'create' ? { createLesson: send } : { importLocalLesson: send }),
    getLesson: vi.fn(async (id: string) => view(id)), listLessons: vi.fn(async () => ({ items: [], total: 0, offset: 0, limit: 50 })),
    saveLesson: vi.fn<typeof lessonPlanApi.saveLesson>(async (id, body) => ({ ...view(id, 2), currentRevision: { ...view(id, 2).currentRevision, data: structuredClone(body.data) } })),
  };
}
function host(store: ReturnType<typeof bag>, services: typeof lessonPlanApi, id = 'g5-current') {
  return render(<NavigationPreference><DocumentGateway initialLessonPlanId={id} services={{ lessonApi: services, recoveryStorage: store.storage }}><Host /></DocumentGateway></NavigationPreference>);
}
const startName = (kind: 'create' | 'import') => kind === 'create' ? '将当前正文创建为后台教案' : '导入完整旧本地稿到后台';
const recoveryName = (kind: 'create' | 'import') => kind === 'create' ? '重试创建操作恢复缓存' : '重试导入操作恢复缓存';
const operationKey = (kind: 'create' | 'import') => `zhiqikeyuan:lesson-plan:operation:v1:${kind}`;
const state = () => JSON.parse(screen.getByLabelText('G5完整状态').textContent!);
function seedLegacy(store: ReturnType<typeof bag>) {
  const raw = JSON.stringify({ schemaVersion: 1, revision: 13, updatedAt: '2026-10-05T06:00:00+08:00', data }); store.values.set(LEGACY_KEY, raw); return raw;
}
beforeEach(() => {
  router.push.mockReset(); router.replace.mockReset(); localStorage.clear();
  Object.defineProperty(window, 'matchMedia', { configurable: true, value: vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })) });
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value() { this.setAttribute('open', ''); } });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value() { this.removeAttribute('open'); } });
});

async function cancelledFirst(kind: 'create' | 'import', second: 'success' | 'failure') {
  const store = bag(), legacy = seedLegacy(store); let resolve!: (value: LessonView) => void;
  const send = vi.fn().mockImplementationOnce(() => new Promise<LessonView>((complete) => { resolve = complete; }));
  if (second === 'success') send.mockResolvedValueOnce(view(`g5-second-${kind}`));
  else send.mockRejectedValueOnce(new ApiError('INVALID_SELECTION', '第二次明确失败', 422, false));
  const services = api(send, kind), rendered = host(store, services);
  await screen.findByRole('button', { name: startName(kind) }); await waitFor(() => expect(state().selection.context).toEqual(context));
  fireEvent.click(screen.getByRole('button', { name: startName(kind) })); await waitFor(() => expect(send).toHaveBeenCalledTimes(1));
  fireEvent.change(screen.getByLabelText('G5课题'), { target: { value: '第一次请求期间的新稿' } });
  await act(async () => { resolve(view(`g5-first-${kind}`)); }); await screen.findByRole('dialog', { name: '离开当前教案' });
  fireEvent.click(screen.getByRole('button', { name: '取消离开，继续编辑' })); await waitFor(() => expect(screen.queryByRole('dialog', { name: '离开当前教案' })).not.toBeInTheDocument());
  store.failRemove(true); fireEvent.click(screen.getByRole('button', { name: startName(kind) })); const retry = await screen.findByRole('button', { name: recoveryName(kind) });
  expect(send).toHaveBeenCalledTimes(2); expect(router.push).not.toHaveBeenCalled();
  return { store, legacy, send, services, rendered, retry, original: JSON.parse(store.values.get(operationKey(kind))!).operation };
}

describe('G5 current successful cleanup uses existing leave protection', () => {
  it.each(['create', 'import'] as const)('%s opens only the second success after storage-only cleanup', async (kind) => {
    const { store, legacy, send, retry, original } = await cancelledFirst(kind, 'success');
    expect(send.mock.calls[1][0]).toEqual({ ...original.payload, submissionId: original.submissionId }); store.failRemove(false); fireEvent.click(retry);
    await waitFor(() => expect(router.push).toHaveBeenCalledWith(`/lesson-plans?lessonPlanId=g5-second-${kind}`)); expect(router.push).toHaveBeenCalledTimes(1); expect(send).toHaveBeenCalledTimes(2); expect(store.values.get(LEGACY_KEY)).toBe(legacy);
  });
  it.each(['create', 'import'] as const)('%s success cleanup still lets the teacher cancel switching and preserve later full edits', async (kind) => {
    const { store, legacy, send, retry } = await cancelledFirst(kind, 'success');
    fireEvent.change(screen.getByLabelText('G5课题'), { target: { value: '成功之后仍在当前文档继续编辑' } }); const before = state(); store.failRemove(false); fireEvent.click(retry);
    await screen.findByRole('dialog', { name: '离开当前教案' }); expect(router.push).not.toHaveBeenCalled(); fireEvent.click(screen.getByRole('button', { name: '取消离开，继续编辑' }));
    await waitFor(() => expect(screen.queryByRole('dialog', { name: '离开当前教案' })).not.toBeInTheDocument()); expect(state()).toEqual(before); expect(send).toHaveBeenCalledTimes(2); expect(store.values.get(LEGACY_KEY)).toBe(legacy);
  });
  it.each(['create', 'import'] as const)('%s duplicate cache clicks cannot send HTTP or open a successful document twice', async (kind) => {
    const { store, send, retry } = await cancelledFirst(kind, 'success'); store.failRemove(false); fireEvent.click(retry); fireEvent.click(retry);
    await waitFor(() => expect(router.push).toHaveBeenCalledWith(`/lesson-plans?lessonPlanId=g5-second-${kind}`)); expect(router.push).toHaveBeenCalledTimes(1); expect(send).toHaveBeenCalledTimes(2);
  });
  it.each(['create', 'import'] as const)('%s a route change or unmount while cleanup settles cannot navigate its old successful receipt', async (kind) => {
    const { store, send, retry, rendered, services } = await cancelledFirst(kind, 'success'); store.failRemove(false);
    act(() => { fireEvent.click(retry); rendered.rerender(<NavigationPreference><DocumentGateway initialLessonPlanId="g5-other" services={{ lessonApi: services, recoveryStorage: store.storage }}><Host /></DocumentGateway></NavigationPreference>); });
    await waitFor(() => expect(state().documentId).toBe('g5-other')); expect(router.push).not.toHaveBeenCalled(); expect(state().data).toEqual(data); expect(send).toHaveBeenCalledTimes(2);
    rendered.unmount(); expect(router.push).not.toHaveBeenCalled();
  });
});

const fullPayload = { subjectId: 'chinese', classId: 'g5-class', context, data, source: 'manual' as const };
function operationHarness(kind: 'create' | 'import', verifyWrite?: () => boolean | Promise<boolean>) {
  const store = bag(), key = operationKey(kind), contextKey = `lesson|g5-current|${kind}`;
  const hook = renderHook(({ identity }) => useLessonOperation<typeof fullPayload, LessonView>(identity, { ...browserOperationRecovery(key, store.storage), verifyWrite }), { initialProps: { identity: contextKey } });
  return { store, key, contextKey, hook };
}
describe('G5 frozen cleanup identity and recovery guards', () => {
  it.each(['create', 'import'] as const)('%s binds a failed cleanup to the actual second packet while preserving shared last-success behavior', async (kind) => {
    const { store, key, contextKey, hook } = operationHarness(kind), send = vi.fn().mockResolvedValueOnce(view('g5-first-hook')).mockRejectedValueOnce(new ApiError('CONFLICT', '明确409', 409, false));
    await act(async () => { await hook.result.current.run(fullPayload, send, 3, 'load-original'); }); store.failRemove(true);
    await act(async () => { await hook.result.current.run({ ...fullPayload, data: { ...data, title: '第二次原完整正文' } }, send, 8, 'load-second'); });
    const packet = JSON.parse(store.values.get(key)!).operation, outcome = hook.result.current.cleanupOutcome(); expect(outcome?.type).toBe('failure'); expect(outcome?.operation).toEqual(packet); expect(packet).toEqual(send.mock.calls[1][0]);
    expect(packet.metadata).toEqual({ contextKey, originalEditGeneration: 8, loadGeneration: 'load-second' }); expect(packet.submissionId).not.toBe(send.mock.calls[0][0].submissionId); expect(packet.operationId).toBe(packet.submissionId); expect(packet.payloadKey).toBe(stablePayloadKey(packet.payload));
    expect(hook.result.current.result?.lessonPlanId).toBe('g5-first-hook'); expect(hook.result.current.resultUnknown).toBe(false); store.failRemove(false);
    await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(true); }); expect(send).toHaveBeenCalledTimes(2); expect(hook.result.current.cleanupOutcome()).toBeNull(); expect(hook.result.current.result?.lessonPlanId).toBe('g5-first-hook');
  });
  it.each(['create', 'import'] as const)('%s before-send write recovery sends zero HTTP until explicit original replay', async (kind) => {
    const { store, key, hook } = operationHarness(kind), send = vi.fn<(operation: FrozenSubmission<typeof fullPayload>) => Promise<LessonView>>(async () => view()); store.failWrite(true);
    await act(async () => { await hook.result.current.run(fullPayload, send, 7, 'original-load'); }); const packet = structuredClone(hook.result.current.pending); expect(send).not.toHaveBeenCalled(); expect(hook.result.current.cleanupOutcome()).toBeNull(); expect(hook.result.current.resultUnknown).toBe(false);
    store.failWrite(false); await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(true); }); expect(send).not.toHaveBeenCalled(); expect(JSON.parse(store.values.get(key)!).operation).toEqual(packet);
    await act(async () => { await hook.result.current.run({ ...fullPayload, data: { ...data, title: '后来编辑参数' } }, send, 12, 'later-load'); }); expect(send).toHaveBeenCalledTimes(1); expect(send.mock.calls[0][0]).toEqual(packet);
  });
  it.each(['create', 'import'] as const)('%s unknown keeps the entire original packet and does not become cleanup success', async (kind) => {
    const { hook } = operationHarness(kind), send = vi.fn().mockRejectedValueOnce(new ApiError('RESPONSE_LOST', '结果未知', 0, true)).mockResolvedValueOnce(view());
    await act(async () => { await hook.result.current.run(fullPayload, send, 4, 'original-load'); }); const packet = structuredClone(hook.result.current.pending); expect(hook.result.current.resultUnknown).toBe(true); expect(hook.result.current.cleanupOutcome()).toBeNull();
    await act(async () => { await hook.result.current.run({ ...fullPayload, data: { ...data, title: '未知之后的新参数' } }, send, 9, 'later-load'); }); expect(send).toHaveBeenCalledTimes(2); expect(send.mock.calls[1][0]).toEqual(packet); expect(send.mock.calls[1][0]).toEqual(send.mock.calls[0][0]);
  });
  it.each(['success', 'failure'] as const)('%s late verification cannot unlock a new operation session or retain a usable old outcome', async (type) => {
    let resolve!: (value: boolean) => void; const { store, hook, contextKey } = operationHarness('create', () => new Promise<boolean>((complete) => { resolve = complete; }));
    const send = type === 'success' ? vi.fn(async () => view('g5-owned')) : vi.fn(async () => { throw new ApiError('INVALID', '明确失败', 422, false); }); store.failRemove(true);
    await act(async () => { await hook.result.current.run(fullPayload, send, 2, 'sent-load'); }); expect(hook.result.current.cleanupOutcome()?.type).toBe(type); store.failRemove(false); let retry!: Promise<boolean>;
    act(() => { retry = hook.result.current.retryRecoveryWrite(); hook.rerender({ identity: contextKey.replace('g5-current', 'g5-other') }); });
    await act(async () => { resolve(true); expect(await retry).toBe(false); }); expect(hook.result.current.cleanupOutcome()).toBeNull(); expect(hook.result.current.recoveryBlocked).toBe(false); expect(hook.result.current.pending).toBeNull(); expect(send).toHaveBeenCalledTimes(1);
  });
  it.each(['success', 'failure'] as const)('%s unmounted verification never completes a cleanup or publishes an outcome', async (type) => {
    let resolve!: (value: boolean) => void; const { store, hook } = operationHarness('import', () => new Promise<boolean>((complete) => { resolve = complete; }));
    const send = type === 'success' ? vi.fn(async () => view()) : vi.fn(async () => { throw new ApiError('INVALID', '明确失败', 422, false); }); store.failRemove(true);
    await act(async () => { await hook.result.current.run(fullPayload, send, 2); }); store.failRemove(false); const getter = hook.result.current.cleanupOutcome; let retry!: Promise<boolean>;
    act(() => { retry = hook.result.current.retryRecoveryWrite(); hook.unmount(); }); await act(async () => { resolve(true); expect(await retry).toBe(false); }); expect(getter()).toBeNull(); expect(send).toHaveBeenCalledTimes(1);
  });
  it.each(['corrupt', 'unreadable'] as const)('%s original cleanup cache is preserved without overwriting or extra HTTP', async (fault) => {
    const { store, key, hook } = operationHarness('create'), send = vi.fn(async () => view()); store.failRemove(true); await act(async () => { await hook.result.current.run(fullPayload, send, 2); }); store.failRemove(false);
    if (fault === 'corrupt') store.values.set(key, '{bad original'); else store.failRead(true);
    const bytes = store.values.get(key), removes = store.storage.removeItem.mock.calls.length, writes = store.storage.setItem.mock.calls.length;
    await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(false); }); expect(store.values.get(key)).toBe(bytes); expect(store.storage.removeItem).toHaveBeenCalledTimes(removes); expect(store.storage.setItem).toHaveBeenCalledTimes(writes); expect(hook.result.current.recoveryBlocked).toBe(true); expect(send).toHaveBeenCalledTimes(1);
  });
  it.each(['success', 'failure'] as const)('%s cleanup refuses to remove a different valid operation packet in the same context', async (type) => {
    const { store, key, hook } = operationHarness('create'), send = type === 'success' ? vi.fn(async () => view()) : vi.fn(async () => { throw new ApiError('INVALID', '明确失败', 422, false); }); store.failRemove(true);
    await act(async () => { await hook.result.current.run(fullPayload, send, 2); }); store.failRemove(false); const original: FrozenSubmission<typeof fullPayload> = JSON.parse(store.values.get(key)!).operation;
    const other = { ...original, operationId: 'other-owned-operation', submissionId: 'other-owned-operation' }, raw = JSON.stringify({ schemaVersion: 1, operation: other }); store.values.set(key, raw);
    const removes = store.storage.removeItem.mock.calls.length; await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(false); }); expect(store.values.get(key)).toBe(raw); expect(store.storage.removeItem).toHaveBeenCalledTimes(removes); expect(send).toHaveBeenCalledTimes(1); expect(hook.result.current.recoveryBlocked).toBe(true);
  });
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); localStorage.clear(); });

describe('G5 cleanup outcome follows the current operation', () => {
  it.each([['create', 422], ['import', 422], ['create', 409], ['import', 409]] as const)('%s successful cancelled leave then explicit %s failure cleanup preserves current full work', async (kind, status) => {
    const store = bag(), legacy = seedLegacy(store); let resolveFirst!: (value: LessonView) => void;
    const send = vi.fn().mockImplementationOnce(() => new Promise<LessonView>((resolve) => { resolveFirst = resolve; })).mockRejectedValueOnce(new ApiError(status === 409 ? 'CONFLICT' : 'INVALID_SELECTION', 'G5第二次明确失败', status, false));
    const services = api(send, kind); host(store, services); await screen.findByRole('button', { name: startName(kind) }); await waitFor(() => expect(state().selection.context).toEqual(context)); const start = screen.getByRole('button', { name: startName(kind) });
    fireEvent.click(start); await waitFor(() => expect(send).toHaveBeenCalledTimes(1));
    const firstPacket = JSON.parse(store.values.get(operationKey(kind))!).operation;
    fireEvent.change(screen.getByLabelText('G5课题'), { target: { value: '创建导入等待期间仍在编辑的教师正文' } });
    await act(async () => { resolveFirst(view(`g5-first-${kind}`)); }); await screen.findByRole('dialog', { name: '离开当前教案' });
    fireEvent.click(screen.getByRole('button', { name: '取消离开，继续编辑' })); await waitFor(() => expect(screen.queryByRole('dialog', { name: '离开当前教案' })).not.toBeInTheDocument());
    expect(router.push).not.toHaveBeenCalled(); store.failRemove(true); fireEvent.click(screen.getByRole('button', { name: startName(kind) }));
    const retry = await screen.findByRole('button', { name: recoveryName(kind) }), packet = JSON.parse(store.values.get(operationKey(kind))!).operation;
    expect(send).toHaveBeenCalledTimes(2); expect(packet.operationId).toBe(packet.submissionId); expect(packet.submissionId).not.toBe(firstPacket.submissionId);
    expect(packet.metadata).toMatchObject({ contextKey: `lesson|new|${kind}` }); expect(packet.metadata.loadGeneration).toBe(firstPacket.metadata.loadGeneration);
    expect(send.mock.calls[1][0]).toEqual({ ...packet.payload, submissionId: packet.submissionId });
    expect(packet.payload).toMatchObject({ subjectId: 'chinese', classId: 'g5-class', context });
    if (kind === 'create') expect(packet.payload).toEqual({ subjectId: 'chinese', classId: 'g5-class', context, data: { ...data, title: '创建导入等待期间仍在编辑的教师正文' }, source: 'manual' });
    else expect(packet.payload.draft).toEqual(JSON.parse(legacy));
    const before = state(), cacheBefore = JSON.parse(store.values.get(serverSessionKey('g5-current'))!);
    expect(before).toEqual({ documentId: 'g5-current', data: { ...data, title: '创建导入等待期间仍在编辑的教师正文' }, context, source: 'manual', selection: { subjectId: 'chinese', classId: 'g5-class', context } });
    store.failRemove(false); fireEvent.click(retry); await waitFor(() => expect(screen.queryByRole('button', { name: recoveryName(kind) })).not.toBeInTheDocument());
    expect(send).toHaveBeenCalledTimes(2); expect(router.push).not.toHaveBeenCalled(); expect(state()).toEqual(before);
    expect(JSON.parse(store.values.get(serverSessionKey('g5-current'))!)).toEqual(cacheBefore); expect(store.values.has(operationKey(kind))).toBe(false); expect(store.values.get(LEGACY_KEY)).toBe(legacy);
  });
});
