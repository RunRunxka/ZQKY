import React, { useState } from 'react';
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { LessonEvidenceView, LessonGenerationReceipt, LessonProposalView, LessonView } from '@/contracts/lesson-plans';
import { lessonPlanApi } from '@/services/lesson-plans-api';
import { ApiError } from '@/services/api-client';
import { NavigationPreference } from '@/components/layout/NavigationPreference';
import { LessonPlanWorkspace } from './LessonPlanWorkspace';
import { DocumentGateway } from './components/DocumentGateway';
import { DocumentsPanel } from './components/DocumentsPanel';
import { ProposalPanel } from './components/ProposalPanel';
import { ServerControls } from './components/ServerControls';
import { LeaveProtection } from './components/LeaveProtection';
import { initialGenerationInputs } from './components/SourcePanel';
import { LessonPlanProvider, useLessonEditor } from './model/EditorContext';
import { useLessonDocument } from './model/DocumentContext';
import { useServerPersistence } from './model/useServerPersistence';
import { browserOperationRecovery, useLessonOperation } from './model/useLessonOperation';
import { createLessonStore } from './model/store';
import { emptyData } from './model/defaults';
import { initialServerCache, LEGACY_KEY, serverSessionKey, writeServerCache } from './model/server-cache';

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => router, usePathname: () => '/lesson-plans' }));
vi.mock('@/services/workflow-jobs-api', () => ({ observeJob: vi.fn(async () => null), retryObservationWindow: (view: { attempt: number }) => ({ minAttempt: view.attempt, maxAttempt: view.attempt + 1 }), retryJob: vi.fn(), cancelJob: vi.fn() }));
const analysis = { analysisRunId: 'g4-run', inputHash: 'g4-input', scoreRevisionId: 'g4-score', paperRevisionId: 'g4-paper', className: null, classNameNote: '匿名固定班', knowledgePoints: [{ knowledgePointId: 'g4-kp', knowledgeRevisionId: 'g4-kp-fixed', name: '教学依据', role: 'primary' as const }] };
function view(id = 'g4-a', version = 1): LessonView {
  const revisionId = `${id}-fixed-${version}`;
  return { protocolVersion: 2, lessonPlanId: id, subjectId: 'chinese', classId: 'g4-class', revision: version, currentRevisionId: revisionId, replayed: false,
    currentRevision: { protocolVersion: 2, lessonPlanId: id, revisionId, version, data: { ...structuredClone(emptyData), title: '教师原课题', totalLessons: '2', currentLessonNo: '1', lessonTypes: ['review', 'new', 'review'], otherTypeText: '原课型', coreCompetencies: '原素养', keyPoints: '原重点', teachingDesign: '长设计'.repeat(12), process: [{ id: 'teacher-stage', stage: '原环节', design: '原活动'.repeat(12), secondary: '原二次备课'.repeat(12) }], exercises: '原练习', reflection: '教师反思' }, contentHash: `hash-${version}`, source: 'manual', contextSnapshot: { subjectId: 'chinese', classId: 'g4-class', classNameAtSave: '匿名固定班', analysis }, analysisRunId: analysis.analysisRunId, acceptedProposalId: null, importEnvelope: null, selectedFields: [], processMetadata: [], reviewState: 'unreviewed', createdAt: '2026-10-05T00:00:00Z' } };
}
function bag() {
  const values = new Map<string, string>(); let fault: ((key: string, raw?: string) => boolean) | null = null, removeFault = false;
  const storage = { getItem: vi.fn((key: string) => values.get(key) ?? null), setItem: vi.fn((key: string, raw: string) => { if (fault?.(key, raw)) throw new Error('隔离quota'); values.set(key, raw); }), removeItem: vi.fn((key: string) => { if (removeFault) throw new Error('隔离cleanup'); values.delete(key); }), clear: () => values.clear(), key: (index: number) => [...values.keys()][index] ?? null, get length() { return values.size; } } satisfies Storage;
  return { values, storage, fail: (test: typeof fault) => { fault = test; }, failRemove: (value: boolean) => { removeFault = value; } };
}
function api(overrides: Partial<typeof lessonPlanApi> = {}) {
  return { ...lessonPlanApi, getLesson: vi.fn(async (id: string) => view(id)), listLessons: vi.fn(async () => ({ items: [], total: 0, offset: 0, limit: 50 })), saveLesson: vi.fn<typeof lessonPlanApi.saveLesson>(async (id, body) => ({ ...view(id, 2), currentRevision: { ...view(id, 2).currentRevision, data: structuredClone(body.data) } })), ...overrides };
}
function workspace(storage: Storage, services = api()) { return render(<NavigationPreference><LessonPlanWorkspace initialLessonPlanId="g4-a" services={{ lessonApi: services, recoveryStorage: storage }} /></NavigationPreference>); }
function ControlledServerForm() {
  const editor = useLessonEditor();
  return <><label>受控课题<input value={editor.data.title} onChange={(event) => editor.set({ title: event.target.value })} /></label><ServerControls /></>;
}
function ControlledServerHost({ current, storage, services }: { current: LessonView; storage: Storage; services: typeof lessonPlanApi }) {
  return <NavigationPreference><DocumentGateway services={{ lessonApi: services, recoveryStorage: storage }}><LessonPlanProvider session={{ server: { view: current, api: services, storage } }}><ControlledServerForm /></LessonPlanProvider></DocumentGateway></NavigationPreference>;
}
beforeEach(() => {
  localStorage.clear(); router.push.mockReset(); router.replace.mockReset();
  Object.defineProperty(window, 'matchMedia', { configurable: true, value: vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })) });
  vi.stubGlobal('ResizeObserver', class { observe() {} disconnect() {} unobserve() {} });
  Object.defineProperty(HTMLDialogElement.prototype, 'showModal', { configurable: true, value() { this.setAttribute('open', ''); } });
  Object.defineProperty(HTMLDialogElement.prototype, 'close', { configurable: true, value() { this.removeAttribute('open'); } });
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.unstubAllGlobals(); vi.restoreAllMocks(); localStorage.clear(); });

describe('G4-E public full recovery cache retry', () => {
  it('writes and verifies all body/context/source before enabling explicit save and leave', async () => {
    const store = bag(), services = api(), original = initialServerCache(view()); original.source = 'rule'; writeServerCache(store.storage, original);
    workspace(store.storage, services); await screen.findByLabelText('课题'); store.fail((key) => key === serverSessionKey('g4-a'));
    fireEvent.change(screen.getByLabelText('课题'), { target: { value: '教师唯一新课题' } }); expect(screen.getByLabelText('课题')).toBeDisabled();
    const expected = { ...view().currentRevision.data, title: '教师唯一新课题' };
    store.fail(null); fireEvent.click(screen.getByRole('button', { name: '重试恢复缓存' }));
    await waitFor(() => expect(screen.getByLabelText('课题')).toBeEnabled());
    const envelope = JSON.parse(store.values.get(serverSessionKey('g4-a'))!); expect(envelope.data).toEqual(expected); expect(envelope.context).toEqual(original.context); expect(envelope.source).toBe('manual'); expect(envelope.operations).toEqual(original.operations); expect(services.saveLesson).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '保存后台稿' })); await waitFor(() => expect(services.saveLesson).toHaveBeenCalledTimes(1)); expect(vi.mocked(services.saveLesson).mock.calls[0][1].data).toEqual(expected); expect(vi.mocked(services.saveLesson).mock.calls[0][1].context).toEqual(original.context);
    fireEvent.click(screen.getByRole('button', { name: '学习问答' })); await waitFor(() => expect(router.push).toHaveBeenCalledWith('/chat')); expect(services.saveLesson).toHaveBeenCalledTimes(1);
  });
  it('continuous failure and a lying write stay locked with zero HTTP', async () => {
    const store = bag(), services = api(); workspace(store.storage, services); await screen.findByLabelText('课题'); store.fail(() => true);
    fireEvent.change(screen.getByLabelText('课题'), { target: { value: '保持内存全部正文' } }); fireEvent.click(screen.getByRole('button', { name: '重试恢复缓存' })); await screen.findByText(/恢复缓存重试失败/); expect(services.saveLesson).not.toHaveBeenCalled(); expect(screen.getByLabelText('课题')).toHaveValue('保持内存全部正文');
    store.fail(null); store.storage.setItem.mockImplementation(() => {}); fireEvent.click(screen.getByRole('button', { name: '重试恢复缓存' })); await screen.findByText(/完整恢复包核验不一致/); expect(screen.getByLabelText('课题')).toBeDisabled(); expect(services.saveLesson).not.toHaveBeenCalled();
  });
  it('can recover in the actual leave dialog without navigation or HTTP until the teacher chooses save', async () => {
    const store = bag(), services = api(); workspace(store.storage, services); await screen.findByLabelText('课题'); store.fail(() => true); fireEvent.change(screen.getByLabelText('课题'), { target: { value: '离开前唯一新稿' } });
    fireEvent.click(screen.getByRole('button', { name: '学习问答' })); await screen.findByRole('dialog', { name: '离开当前教案' }); expect(screen.getByRole('button', { name: '保存成功后离开' })).toBeDisabled(); store.fail(null);
    fireEvent.click(screen.getByRole('button', { name: '重试恢复缓存后继续处理离开' })); await waitFor(() => expect(screen.getByRole('button', { name: '保存成功后离开' })).toBeEnabled()); expect(router.push).not.toHaveBeenCalled(); expect(services.saveLesson).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '保存成功后离开' })); await waitFor(() => expect(router.push).toHaveBeenCalledWith('/chat')); expect(services.saveLesson).toHaveBeenCalledTimes(1); expect(vi.mocked(services.saveLesson).mock.calls[0][1].data.title).toBe('离开前唯一新稿');
  });
  it('bad original bytes refuse retry and remain exact with no write', async () => {
    const store = bag(), services = api(); store.values.set(serverSessionKey('g4-a'), '{bad original'); workspace(store.storage, services); await screen.findByLabelText('课题'); expect(screen.getByRole('button', { name: '重试恢复缓存' })).toBeDisabled(); expect(store.storage.setItem).not.toHaveBeenCalled(); expect(store.values.get(serverSessionKey('g4-a'))).toBe('{bad original'); expect(services.saveLesson).not.toHaveBeenCalled();
  });
  it('a recovered cache with a known newer CAS still requires manual comparison', async () => {
    const store = bag(), services = api(), lessonStore = createLessonStore(), hook = renderHook(({ current }) => useServerPersistence(lessonStore, { view: current, api: services, storage: store.storage }), { initialProps: { current: view() } });
    store.fail(() => true); act(() => lessonStore.getState().set({ title: '冲突前新稿' })); hook.rerender({ current: view('g4-a', 4) }); store.fail(null); await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(true); });
    expect(hook.result.current.syncState).toBe('conflict'); await act(async () => { expect(await hook.result.current.save()).toBe(false); }); expect(services.saveLesson).not.toHaveBeenCalled(); expect(lessonStore.getState().data.title).toBe('冲突前新稿'); expect(hook.result.current.cache?.serverRevision).toBe(1);
  });
  it('a retry resumed after document switch never unlocks or overwrites the new session', async () => {
    const store = bag(), services = api(), lessonStore = createLessonStore(), hook = renderHook(({ current }) => useServerPersistence(lessonStore, { view: current, api: services, storage: store.storage }), { initialProps: { current: view() } });
    store.fail(() => true); act(() => lessonStore.getState().set({ title: 'A唯一输入' })); store.fail(null); let retry!: Promise<boolean>;
    act(() => { retry = hook.result.current.retryRecoveryWrite(); hook.rerender({ current: view('g4-b') }); }); await act(async () => { expect(await retry).toBe(false); }); expect(hook.result.current.cache?.documentId).toBe('g4-b'); expect(lessonStore.getState().data).toEqual(view('g4-b').currentRevision.data); expect(store.values.has(serverSessionKey('g4-b'))).toBe(false); expect(services.saveLesson).not.toHaveBeenCalled();
  });
  it('an unsent original save packet is persisted first and later edits do not replace its identity', async () => {
    const store = bag(), services = api(); workspace(store.storage, services); await screen.findByLabelText('课题'); fireEvent.change(screen.getByLabelText('课题'), { target: { value: '原保存完整正文' } });
    store.fail((key, raw) => key === serverSessionKey('g4-a') && !!JSON.parse(raw!).operations.save); fireEvent.click(screen.getByRole('button', { name: '保存后台稿' })); const recovery = await screen.findByRole('button', { name: '重试恢复缓存' }); await waitFor(() => expect(recovery).toBeEnabled()); expect(services.saveLesson).not.toHaveBeenCalled(); store.fail(null); fireEvent.click(recovery);
    const retry = await screen.findByRole('button', { name: '重试原保存包' }); await waitFor(() => expect(retry).toBeEnabled()); const original = JSON.parse(store.values.get(serverSessionKey('g4-a'))!).operations.save; expect(services.saveLesson).not.toHaveBeenCalled(); fireEvent.change(screen.getByLabelText('课题'), { target: { value: '恢复后的后来正文' } }); fireEvent.click(retry); await waitFor(() => expect(services.saveLesson).toHaveBeenCalledTimes(1)); expect(vi.mocked(services.saveLesson).mock.calls[0][1]).toEqual({ ...original.payload, submissionId: original.submissionId }); expect(screen.getByLabelText('课题')).toHaveValue('恢复后的后来正文'); expect(JSON.parse(store.values.get(serverSessionKey('g4-a'))!).editRevision).toBeGreaterThan(JSON.parse(store.values.get(serverSessionKey('g4-a'))!).acknowledgedEditRevision);
  });
  it('settled pre-send failure enables the public cache retry and refresh without sending or changing the frozen packet', async () => {
    const store = bag(), services = api(); workspace(store.storage, services); await screen.findByLabelText('课题');
    fireEvent.change(screen.getByLabelText('课题'), { target: { value: '异步结算后的完整原稿' } });
    const failedWrites: string[] = [];
    store.fail((key, raw) => {
      if (key !== serverSessionKey('g4-a') || !JSON.parse(raw!).operations.save) return false;
      failedWrites.push(raw!); return true;
    });
    fireEvent.click(screen.getByRole('button', { name: '保存后台稿' }));
    const recovery = await screen.findByRole('button', { name: '重试恢复缓存' });
    await waitFor(() => { expect(recovery).toBeEnabled(); expect(screen.getByRole('button', { name: '读取后台最新版本' })).toBeEnabled(); });
    expect(services.saveLesson).not.toHaveBeenCalled(); expect(failedWrites).toHaveLength(1);
    const original = JSON.parse(failedWrites[0]), reads = vi.mocked(services.getLesson).mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: '读取后台最新版本' }));
    await waitFor(() => expect(services.getLesson).toHaveBeenCalledTimes(reads + 1));
    expect(recovery).toBeEnabled(); expect(services.saveLesson).not.toHaveBeenCalled();
    store.fail(null); fireEvent.click(recovery);
    await waitFor(() => expect(screen.getByRole('button', { name: '重试原保存包' })).toBeEnabled());
    const durable = JSON.parse(store.values.get(serverSessionKey('g4-a'))!);
    expect(durable).toEqual(original); expect(durable.data.title).toBe('异步结算后的完整原稿');
    expect(durable.context).toEqual(initialServerCache(view()).context); expect(services.saveLesson).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '重试原保存包' }));
    await waitFor(() => expect(services.saveLesson).toHaveBeenCalledTimes(1));
    expect(vi.mocked(services.saveLesson).mock.calls[0]).toEqual(['g4-a', { ...original.operations.save.payload, submissionId: original.operations.save.submissionId }]);
  });
  it('a late old-document save does not unlock the current public recovery controls or replace its input', async () => {
    const store = bag(), completion: { resolve?: (value: LessonView) => void } = {};
    const saveLesson = vi.fn<typeof lessonPlanApi.saveLesson>(() => new Promise<LessonView>((resolve) => { completion.resolve = resolve; })), services = api({ saveLesson });
    const host = render(<ControlledServerHost current={view()} storage={store.storage} services={services} />);
    fireEvent.change(screen.getByLabelText('受控课题'), { target: { value: 'A已发送的原稿' } });
    fireEvent.click(screen.getByRole('button', { name: '保存后台稿' }));
    await waitFor(() => expect(saveLesson).toHaveBeenCalledTimes(1));
    host.rerender(<ControlledServerHost current={view('g4-b')} storage={store.storage} services={services} />);
    await waitFor(() => expect(screen.getByLabelText('受控课题')).toHaveValue('教师原课题'));
    store.fail((key) => key === serverSessionKey('g4-b'));
    fireEvent.change(screen.getByLabelText('受控课题'), { target: { value: 'B唯一新输入保持阻断' } });
    const recovery = screen.getByRole('button', { name: '重试恢复缓存' }), before = store.storage.setItem.mock.calls.length;
    expect(recovery).toBeDisabled(); expect(screen.getByRole('button', { name: '读取后台最新版本' })).toBeDisabled();
    await act(async () => { completion.resolve!(view('g4-a', 2)); await Promise.resolve(); });
    expect(recovery).toBeDisabled(); expect(screen.getByRole('button', { name: '读取后台最新版本' })).toBeDisabled();
    expect(screen.getByLabelText('受控课题')).toHaveValue('B唯一新输入保持阻断');
    expect(screen.getByRole('alert')).toHaveTextContent('恢复缓存写入失败');
    expect(store.storage.setItem.mock.calls).toHaveLength(before); expect(store.values.has(serverSessionKey('g4-b'))).toBe(false);
    expect(saveLesson.mock.calls[0][0]).toBe('g4-a'); expect(saveLesson).toHaveBeenCalledTimes(1);
  });
});

describe('G4-E original operation recovery guards', () => {
  it.each(['create', 'import', 'generate', 'apply', 'reject'])('%s pre-send recovery keeps the exact frozen packet across later arguments', async (kind) => {
    const store = bag(), key = `g4-operation-${kind}`, context = `lesson|g4-a|${kind}`, send = vi.fn<(operation: unknown) => Promise<{ ok: boolean }>>(async () => ({ ok: true })); store.fail(() => true);
    const hook = renderHook(() => useLessonOperation(context, browserOperationRecovery(key, store.storage))); await act(async () => { await hook.result.current.run({ title: '原完整载荷', fields: ['process'] }, send, 7, 'first-load'); }); const original = structuredClone(hook.result.current.pending);
    expect(send).not.toHaveBeenCalled(); expect(hook.result.current.recoveryKind).toBe('write'); store.fail(null); await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(true); }); expect(send).not.toHaveBeenCalled(); expect(JSON.parse(store.values.get(key)!).operation).toEqual(original);
    await act(async () => { await hook.result.current.run({ title: '后来参数', fields: ['exercises'] }, send, 9, 'later-load'); }); expect(send).toHaveBeenCalledTimes(1); expect(send.mock.calls[0][0]).toEqual(original); expect(store.values.has(key)).toBe(false);
  });
  it('known ACK cleanup retries storage only and does not convert success into unknown', async () => {
    const store = bag(), send = vi.fn<(operation: unknown) => Promise<{ ok: boolean }>>(async () => ({ ok: true })), hook = renderHook(() => useLessonOperation('lesson|g4-a|apply', browserOperationRecovery('g4-ack', store.storage))); store.failRemove(true);
    await act(async () => { await hook.result.current.run({ original: 'body' }, send, 3); }); expect(hook.result.current.state).toBe('succeeded'); expect(hook.result.current.pending).toBeNull(); expect(hook.result.current.recoveryKind).toBe('cleanup'); expect(hook.result.current.resultUnknown).toBe(false); const before = store.values.get('g4-ack'); expect(before).toBeTruthy();
    store.failRemove(false); await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(true); }); expect(send).toHaveBeenCalledTimes(1); expect(hook.result.current.state).toBe('succeeded'); expect(store.values.has('g4-ack')).toBe(false);
  });
  it('a corrupt read remains blocked and does not overwrite the original bytes', async () => {
    const store = bag(); store.values.set('g4-bad-op', '{bad'); const hook = renderHook(() => useLessonOperation('lesson|g4-a|reject', browserOperationRecovery('g4-bad-op', store.storage))); await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(false); }); expect(hook.result.current.recoveryKind).toBe('read'); expect(store.storage.setItem).not.toHaveBeenCalled(); expect(store.values.get('g4-bad-op')).toBe('{bad');
  });
  it('unknown HTTP replays the original operation after a failed cache write during retry', async () => {
    const store = bag(), send = vi.fn().mockRejectedValueOnce(new ApiError('RESPONSE_LOST', '未收到HTTP结果', 0, true)).mockResolvedValueOnce({ ok: true }), hook = renderHook(() => useLessonOperation('lesson|g4-a|apply', browserOperationRecovery('g4-unknown', store.storage)));
    await act(async () => { await hook.result.current.run({ selectedFields: ['process'], expectedRevision: 1 }, send, 2); }); const original = structuredClone(hook.result.current.pending); expect(hook.result.current.resultUnknown).toBe(true);
    store.fail(() => true); await act(async () => { await hook.result.current.run({ selectedFields: ['exercises'], expectedRevision: 3 }, send, 8); }); expect(send).toHaveBeenCalledTimes(1); expect(hook.result.current.resultUnknown).toBe(true); store.fail(null); await act(async () => { expect(await hook.result.current.retryRecoveryWrite()).toBe(true); }); await act(async () => { await hook.result.current.run({}, send, 12); }); expect(send.mock.calls[1]).toEqual(send.mock.calls[0]); expect(send.mock.calls[1][0]).toEqual(original);
  });
  it('late recovery verification cannot clear the next operation session', async () => {
    const store = bag(), send = vi.fn(), verification: { resolve?: (value: boolean) => void } = {}, verifyWrite = () => new Promise<boolean>((resolve) => { verification.resolve = resolve; }); store.fail(() => true);
    const hook = renderHook(({ context }) => useLessonOperation(context, { ...browserOperationRecovery(`g4-late-${context}`, store.storage), verifyWrite }), { initialProps: { context: 'lesson|g4-a|apply' } }); await act(async () => { await hook.result.current.run({ first: true }, send, 1); }); store.fail(null); let pending!: Promise<boolean>; act(() => { pending = hook.result.current.retryRecoveryWrite(); }); hook.rerender({ context: 'lesson|g4-b|apply' }); await act(async () => { verification.resolve!(true); expect(await pending).toBe(false); }); expect(hook.result.current.pending).toBeNull(); expect(hook.result.current.recoveryBlocked).toBe(false); expect(store.values.has('g4-late-lesson|g4-b|apply')).toBe(false); expect(send).not.toHaveBeenCalled();
  });
});

function DocumentHarness() { const doc = useLessonDocument(), editor = useLessonEditor(); return <><button onClick={() => doc.setSelection({ subjectId: 'chinese', classId: 'g4-class', context: null })}>明确文档来源</button><DocumentsPanel /><LeaveProtection /><button onClick={() => void doc.leave.current?.()}>尝试离开</button><output aria-label="当前正文">{JSON.stringify(editor.data)}</output></>; }
describe('G4-E document operation public recovery', () => {
  it.each(['create', 'import'] as const)('%s public cache recovery precedes the one original HTTP request', async (kind) => {
    const store = bag(), operationKey = `zhiqikeyuan:lesson-plan:operation:v1:${kind}`, send = vi.fn<(body: unknown) => Promise<LessonView>>(async () => view('g4-created')), services = api(kind === 'create' ? { createLesson: send } : { importLocalLesson: send });
    const old = JSON.stringify({ schemaVersion: 1, revision: 4, updatedAt: '2026-10-05T00:00:00Z', data: view().currentRevision.data }); store.values.set(LEGACY_KEY, old); store.fail((key) => key === operationKey);
    render(<NavigationPreference><DocumentGateway services={{ lessonApi: services, recoveryStorage: store.storage }}><DocumentHarness /></DocumentGateway></NavigationPreference>); fireEvent.click(screen.getByRole('button', { name: '明确文档来源' })); fireEvent.click(screen.getByRole('button', { name: kind === 'create' ? '创建空白后台教案' : '导入完整旧本地稿到后台' })); await screen.findByText(/尚未发送HTTP/); expect(send).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '尝试离开' })); await screen.findByRole('dialog', { name: '离开当前教案' }); expect(screen.getByRole('button', { name: '保存成功后离开' })).toBeDisabled(); fireEvent.click(screen.getByRole('button', { name: '取消离开，继续编辑' })); store.fail(null);
    fireEvent.click(screen.getByRole('button', { name: kind === 'create' ? '重试创建操作恢复缓存' : '重试导入操作恢复缓存' })); await screen.findByRole('button', { name: kind === 'create' ? '重试原创建包' : '重试原导入包' }); const original = JSON.parse(store.values.get(operationKey)!).operation; expect(send).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: kind === 'create' ? '重试原创建包' : '重试原导入包' })); await waitFor(() => expect(send).toHaveBeenCalledTimes(1)); expect(send.mock.calls[0][0]).toEqual({ ...original.payload, submissionId: original.submissionId }); expect(store.values.get(LEGACY_KEY)).toBe(old);
  });
  it('a known create ACK with cleanup failure keeps the session until public cleanup without another create', async () => {
    const store = bag(), createLesson = vi.fn<typeof lessonPlanApi.createLesson>(async () => view('g4-created')), services = api({ createLesson }); store.failRemove(true);
    render(<NavigationPreference><DocumentGateway services={{ lessonApi: services, recoveryStorage: store.storage }}><DocumentHarness /></DocumentGateway></NavigationPreference>); fireEvent.click(screen.getByRole('button', { name: '明确文档来源' })); fireEvent.click(screen.getByRole('button', { name: '创建空白后台教案' })); await screen.findByRole('button', { name: '重试创建操作恢复缓存' }); expect(createLesson).toHaveBeenCalledTimes(1); expect(router.push).not.toHaveBeenCalled(); expect(screen.queryByText(/原操作结果未知/)).not.toBeInTheDocument();
    store.failRemove(false); fireEvent.click(screen.getByRole('button', { name: '重试创建操作恢复缓存' })); await waitFor(() => expect(router.push).toHaveBeenCalledWith('/lesson-plans?lessonPlanId=g4-created')); expect(createLesson).toHaveBeenCalledTimes(1); expect(store.values.has('zhiqikeyuan:lesson-plan:operation:v1:create')).toBe(false);
  });
});

const scope = { schemaVersion: 2 as const, selection: { gradeId: 'grade', subjectId: 'chinese', editionId: 'edition', documentIds: ['textbook'] }, documents: [{ documentId: 'textbook', documentRevisionId: 'textbook-fixed', metadataRevisionId: 'meta-fixed' }], embeddingGenerationId: 'embedding-fixed', scopeHash: 'scope-fixed' };
const refs = [{ evidenceId: 'evidence-fixed', documentRevisionId: 'textbook-fixed', normalizedTextSha256: 'sha-fixed', charStart: 0, charEnd: 10 }];
const evidence: LessonEvidenceView = { scopeSnapshot: scope, evidenceRefs: refs, evidence: [] };
function receipt(): LessonGenerationReceipt { return { lessonPlanId: 'g4-a', inputHash: 'g4-input', job: { domain: 'teaching', kind: 'lesson_generate', jobId: 'g4-job', attempt: 1, state: 'succeeded', result: { lessonPlanId: 'g4-a', proposalId: 'g4-proposal' }, error: null }, replayed: false }; }
function proposal(): LessonProposalView { return { protocolVersion: 2, lessonPlanId: 'g4-a', proposalId: 'g4-proposal', jobId: 'g4-job', baseRevisionId: 'g4-a-fixed-1', baseServerRevision: 1, inputHash: 'g4-input', modelFingerprint: 'g4-model', state: 'pending', patch: { coreCompetencies: '候选核心', keyPoints: null, teachingDesign: null, process: [], exercises: null }, budget: { durationMinutes: 40, stages: ['introduction', 'exploration', 'practice', 'conclusion'].map((phase, index) => ({ processId: `stage-${index}`, phase: phase as 'introduction', minutes: 10, knowledgeAliases: ['K1'], activity: '活动', check: '检查', evidenceAliases: ['E1'] })) }, evidence: [], generationSource: { analysis, classId: 'g4-class', selectedKnowledgePoints: analysis.knowledgePoints, modelProfileId: 'g4-model', scopeSnapshot: scope, evidenceRefs: refs, requirements: '首次教师要求' }, selectedFields: [], acceptedRevisionId: null, createdAt: '2026-10-05T00:00:00Z', decidedAt: null, replayed: false }; }
function ProposalHarness() { const editor = useLessonEditor(), [inputs, setInputs] = useState({ ...initialGenerationInputs, modelProfileId: 'g4-model', requirements: '首次教师要求', evidence, classReady: true }); return <><button onClick={() => setInputs({ ...inputs, modelProfileId: 'later-model', requirements: '后来教师要求' })}>更改后来来源</button><output aria-label="实际正文">{JSON.stringify(editor.data)}</output><output aria-label="恢复状态">{JSON.stringify({ state: editor.server?.syncState, notice: editor.server?.notice, busy: editor.server?.busy, exclusive: editor.server?.exclusive, revision: editor.revision, cacheRevision: editor.server?.cache?.editRevision })}</output><ProposalPanel inputs={inputs} /></>; }
function proposalHost(store: Storage, services: typeof lessonPlanApi) { return render(<NavigationPreference><DocumentGateway initialLessonPlanId="g4-a" services={{ lessonApi: services, recoveryStorage: store }}><ProposalHarness /></DocumentGateway></NavigationPreference>); }
describe('G4-E proposal public recovery wiring', () => {
  it.each(['server', 'signature'])('first generate %s write failure retains first source signature through later inputs', async (failure) => {
    const store = bag(), generateLessonProposal = vi.fn<typeof lessonPlanApi.generateLessonProposal>(async () => receipt()), services = api({ generateLessonProposal, getLessonProposal: vi.fn(async () => proposal()) }), generationKey = 'zhiqikeyuan:lesson-plan:generation:v1:g4-a';
    proposalHost(store.storage, services); const start = await screen.findByRole('button', { name: '保存当前稿并生成 AI 候选' }); await waitFor(() => expect(start).toBeEnabled()); store.fail((key) => key === (failure === 'server' ? serverSessionKey('g4-a') : generationKey)); fireEvent.click(start); await screen.findByRole('button', { name: '重试生成操作恢复缓存' }); expect(generateLessonProposal).not.toHaveBeenCalled(); fireEvent.click(screen.getByRole('button', { name: '更改后来来源' })); store.fail(null);
    fireEvent.click(screen.getByRole('button', { name: '重试生成操作恢复缓存' })); await waitFor(() => expect(screen.getByRole('button', { name: '重试原生成包' })).toBeEnabled()); const original = JSON.parse(store.values.get(generationKey)!).operation; expect(generateLessonProposal).not.toHaveBeenCalled(); fireEvent.click(screen.getByRole('button', { name: '重试原生成包' })); await waitFor(() => expect(generateLessonProposal).toHaveBeenCalledTimes(1)); expect(generateLessonProposal.mock.calls[0][1]).toEqual({ ...original.payload, submissionId: original.submissionId }); expect(original.payload).toMatchObject({ modelProfileId: 'g4-model', requirements: '首次教师要求' }); await screen.findByText(/已过期：编辑或来源发生变化/);
  });
  it('generation receipt cache cleanup preserves its known job and never re-calls the provider endpoint', async () => {
    const store = bag(), generateLessonProposal = vi.fn<typeof lessonPlanApi.generateLessonProposal>(async () => receipt()), services = api({ generateLessonProposal, getLessonProposal: vi.fn(async () => proposal()) }); proposalHost(store.storage, services); const start = await screen.findByRole('button', { name: '保存当前稿并生成 AI 候选' }); await waitFor(() => expect(start).toBeEnabled()); store.fail((key, raw) => key.includes('generation:v1') && JSON.parse(raw!).receipt !== null); fireEvent.click(start);
    await screen.findByRole('button', { name: '重试生成操作恢复缓存' }); await screen.findByText(/固定候选 g4-proposal/); expect(generateLessonProposal).toHaveBeenCalledTimes(1); store.fail(null); fireEvent.click(screen.getByRole('button', { name: '重试生成操作恢复缓存' })); await waitFor(() => expect(screen.queryByRole('button', { name: '重试生成操作恢复缓存' })).not.toBeInTheDocument()); expect(generateLessonProposal).toHaveBeenCalledTimes(1); expect(JSON.parse(store.values.get('zhiqikeyuan:lesson-plan:generation:v1:g4-a')!).receipt).toEqual(receipt()); expect(JSON.parse(store.values.get(serverSessionKey('g4-a'))!).operations.generate).toBeNull();
  });
  it.each(['apply', 'reject'] as const)('%s public recovery preserves the original decision and sends it once', async (kind) => {
    const store = bag(), send = vi.fn<(...args: unknown[]) => Promise<LessonView | LessonProposalView>>(async () => kind === 'apply' ? { ...view('g4-a', 2), currentRevision: { ...view('g4-a', 2).currentRevision, data: { ...view().currentRevision.data, coreCompetencies: '候选核心' } } } : { ...proposal(), state: 'rejected' as const }), services = api({ generateLessonProposal: vi.fn(async () => receipt()), getLessonProposal: vi.fn(async () => proposal()), ...(kind === 'apply' ? { applyLessonProposal: send as typeof lessonPlanApi.applyLessonProposal } : { rejectLessonProposal: send as typeof lessonPlanApi.rejectLessonProposal }) });
    proposalHost(store.storage, services); const start = await screen.findByRole('button', { name: '保存当前稿并生成 AI 候选' }); await waitFor(() => expect(start).toBeEnabled()); fireEvent.click(start); await screen.findByLabelText('采用核心素养'); if (kind === 'apply') fireEvent.click(screen.getByLabelText('采用核心素养')); store.fail((key) => key === serverSessionKey('g4-a')); fireEvent.click(screen.getByRole('button', { name: kind === 'apply' ? '仅采用所选完整字段' : '明确拒绝候选' })); await screen.findByRole('button', { name: kind === 'apply' ? '重试采用操作恢复缓存' : '重试拒绝操作恢复缓存' }); expect(send).not.toHaveBeenCalled(); store.fail(null);
    const recoveryButton = screen.getByRole('button', { name: kind === 'apply' ? '重试采用操作恢复缓存' : '重试拒绝操作恢复缓存' }); await waitFor(() => expect(recoveryButton).toBeEnabled()); fireEvent.click(recoveryButton); const retry = await screen.findByRole('button', { name: kind === 'apply' ? '重试原采用包' : '重试原拒绝包' }); await waitFor(() => expect(retry).toBeEnabled()); const original = JSON.parse(store.values.get(serverSessionKey('g4-a'))!).operations[kind]; fireEvent.click(retry); await waitFor(() => expect(send).toHaveBeenCalledTimes(1)); if (kind === 'apply') expect(send.mock.calls[0][2]).toEqual({ expectedRevision: original.payload.expectedRevision, baseRevisionId: original.payload.baseRevisionId, selectedFields: original.payload.selectedFields, submissionId: original.submissionId }); else expect(send.mock.calls[0][2]).toEqual({ submissionId: original.submissionId }); const body = JSON.parse(screen.getByLabelText('实际正文').textContent!); expect(body.reflection).toBe(view().currentRevision.data.reflection); expect(body.process).toEqual(view().currentRevision.data.process);
  });
});
