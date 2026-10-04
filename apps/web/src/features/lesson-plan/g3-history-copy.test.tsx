import React from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { LessonRevisionView, LessonView } from '@/contracts/lesson-plans';
import { ApiError } from '@/services/api-client';
import { lessonPlanApi } from '@/services/lesson-plans-api';
import { NavigationPreference } from '@/components/layout/NavigationPreference';
import { DocumentGateway } from './components/DocumentGateway';
import { DocumentsPanel } from './components/DocumentsPanel';
import { useLessonEditor } from './model/EditorContext';
import { useLessonDocument } from './model/DocumentContext';
import { emptyData } from './model/defaults';
import { serverSessionKey } from './model/server-cache';

const router = vi.hoisted(() => ({ push: vi.fn(), replace: vi.fn() }));
vi.mock('next/navigation', () => ({ useRouter: () => router, usePathname: () => '/lesson-plans' }));
function view(version = 1, id = 'g3-copy'): LessonView {
  const revisionId = `${id}-fixed-${version}`;
  return { protocolVersion: 2, lessonPlanId: id, subjectId: 'chinese', classId: 'g3-class', revision: version, currentRevisionId: revisionId, replayed: false,
    currentRevision: { protocolVersion: 2, lessonPlanId: id, revisionId, version,
      data: { ...structuredClone(emptyData), title: `${id}当前正文`, teachingDesign: '当前长正文', reflection: '当前教师反思', process: [{ id: 'current-process', stage: '当前环节', design: '当前活动', secondary: '当前二次备课' }] },
      contentHash: `hash-${id}-${version}`, source: 'manual', contextSnapshot: { subjectId: 'chinese', classId: 'g3-class', classNameAtSave: '匿名隔离班', analysis: null },
      analysisRunId: null, acceptedProposalId: null, importEnvelope: null, selectedFields: [], processMetadata: [], reviewState: 'unreviewed', createdAt: '2026-10-04T00:00:00Z' } };
}
function history(): LessonRevisionView { return { ...view().currentRevision, revisionId: 'g3-history', version: 0, contentHash: 'history-hash', data: { ...structuredClone(emptyData), title: '历史正文', teachingDesign: '历史长正文', reflection: '历史教师反思', process: [{ id: 'history-process', stage: '历史环节', design: '历史活動', secondary: '历史二次备课' }] } }; }
function deferred<T>() { let resolve!: (result: T) => void, reject!: (cause: unknown) => void; const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; }
function Controls() {
  const editor = useLessonEditor(), doc = useLessonDocument();
  if (!editor.ready) return <p>正在恢复</p>;
  return <><DocumentsPanel />
    <input aria-label="复制课题" value={editor.data.title} disabled={editor.editingLocked} onChange={(event) => editor.set({ title: event.target.value })} />
    <textarea aria-label="复制长正文" value={editor.data.teachingDesign} disabled={editor.editingLocked} onChange={(event) => editor.set({ teachingDesign: event.target.value })} />
    <textarea aria-label="复制环节" value={editor.data.process[0]?.design ?? ''} disabled={editor.editingLocked} onChange={(event) => editor.set({ process: editor.data.process.map((item, index) => index ? item : { ...item, design: event.target.value }) })} />
    <button onClick={() => editor.undo()}>复制撤销</button><button onClick={() => editor.redo()}>复制重做</button>
    <button onClick={() => void editor.server?.save()}>复制另存</button><button onClick={() => editor.server?.chooseLatest(true)}>复制采用新基线</button>
    <button onClick={() => void doc.openDocument('g3-other')}>复制打开另一文档</button><button onClick={() => void doc.openDocument('g3-copy', 'other-history')}>复制打开另一历史</button>
    <output aria-label="复制意图">{doc.pendingCopy?.revisionId ?? '-'}</output><output aria-label="复制当前正文">{JSON.stringify(editor.data)}</output>
    <output aria-label="复制通知">{editor.toast}</output><output aria-label="复制错误">{editor.server?.error?.message}</output>
  </>;
}
function host(getLesson: typeof lessonPlanApi.getLesson, overrides: Partial<typeof lessonPlanApi> = {}) {
  const api = { ...lessonPlanApi, getLesson, getLessonRevision: vi.fn(async (_id: string, revision: string) => ({ ...history(), revisionId: revision })), listLessons: vi.fn(async () => ({ items: [], total: 0, offset: 0, limit: 50 })), ...overrides };
  return { api, workspace: render(<NavigationPreference><DocumentGateway initialLessonPlanId="g3-copy" initialRevisionId="g3-history" services={{ lessonApi: api }}><Controls /></DocumentGateway></NavigationPreference>) };
}
async function prepare() { await screen.findByLabelText('复制课题'); fireEvent.click(screen.getByRole('button', { name: '打开当前版本准备复制历史正文' })); await screen.findByRole('button', { name: '明确复制历史正文到当前编辑' }); }
const copyButton = () => screen.getByRole('button', { name: '明确复制历史正文到当前编辑' });
beforeEach(() => {
  localStorage.clear(); router.push.mockClear(); router.replace.mockClear();
  Object.defineProperty(window, 'matchMedia', { configurable: true, value: vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })) });
});
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); localStorage.clear(); });

describe('G3 history copy freezes its original intent and editing baseline', () => {
  it('late history GET preserves new title, long body, process and recovery package until a new explicit copy', async () => {
    const late = deferred<LessonView>(); const getLesson = vi.fn<typeof lessonPlanApi.getLesson>().mockResolvedValueOnce(view()).mockResolvedValueOnce(view()).mockImplementationOnce(() => late.promise).mockResolvedValueOnce(view()); host(getLesson); await prepare();
    fireEvent.click(copyButton()); expect(copyButton()).toBeDisabled(); vi.useFakeTimers();
    fireEvent.change(screen.getByLabelText('复制课题'), { target: { value: '等待中教师B课题' } }); fireEvent.change(screen.getByLabelText('复制长正文'), { target: { value: '等待中教师B长正文'.repeat(100) } }); fireEvent.change(screen.getByLabelText('复制环节'), { target: { value: '等待中教师B活动' } });
    const expected = JSON.parse(screen.getByLabelText('复制当前正文').textContent!); const raw = localStorage.getItem(serverSessionKey('g3-copy'));
    await act(async () => late.resolve(view()));
    expect(JSON.parse(screen.getByLabelText('复制当前正文').textContent!)).toEqual(expected); expect(localStorage.getItem(serverSessionKey('g3-copy'))).toBe(raw); expect(screen.getByLabelText('复制意图')).toHaveTextContent('g3-history'); expect(screen.getByLabelText('复制通知')).toHaveTextContent('重新确认复制'); expect(copyButton()).toBeEnabled();
    fireEvent.click(copyButton()); await act(async () => {}); expect(JSON.parse(screen.getByLabelText('复制当前正文').textContent!)).toEqual(history().data); expect(screen.getByLabelText('复制意图')).toHaveTextContent('-');
    fireEvent.click(screen.getByRole('button', { name: '复制撤销' })); expect(JSON.parse(screen.getByLabelText('复制当前正文').textContent!)).toEqual(expected);
  });
  it('editing then Undo during the GET is still a changed edit generation and cannot silently copy', async () => {
    const late = deferred<LessonView>(); const getLesson = vi.fn<typeof lessonPlanApi.getLesson>().mockResolvedValueOnce(view()).mockResolvedValueOnce(view()).mockImplementationOnce(() => late.promise); host(getLesson); await prepare(); fireEvent.click(copyButton()); vi.useFakeTimers();
    fireEvent.change(screen.getByLabelText('复制课题'), { target: { value: 'B后撤销' } }); fireEvent.click(screen.getByRole('button', { name: '复制撤销' })); expect(screen.getByLabelText('复制课题')).toHaveValue(view().currentRevision.data.title);
    await act(async () => late.resolve(view())); expect(screen.getByLabelText('复制课题')).toHaveValue(view().currentRevision.data.title); expect(screen.getByLabelText('复制意图')).toHaveTextContent('g3-history'); expect(screen.getByLabelText('复制通知')).toHaveTextContent('重新确认复制');
  });
  it('a double click applies once, preserves one Undo/Redo step, and normal save creates a new revision from that history', async () => {
    const late = deferred<LessonView>(); const getLesson = vi.fn<typeof lessonPlanApi.getLesson>().mockResolvedValueOnce(view()).mockResolvedValueOnce(view()).mockImplementationOnce(() => late.promise);
    const saveLesson = vi.fn<typeof lessonPlanApi.saveLesson>(async (_id, body) => ({ ...view(2), currentRevision: { ...view(2).currentRevision, data: structuredClone(body.data) } })); host(getLesson, { saveLesson }); await prepare(); fireEvent.click(copyButton()); fireEvent.click(copyButton()); expect(getLesson).toHaveBeenCalledTimes(3);
    vi.useFakeTimers(); await act(async () => late.resolve(view())); expect(JSON.parse(screen.getByLabelText('复制当前正文').textContent!)).toEqual(history().data);
    fireEvent.click(screen.getByRole('button', { name: '复制撤销' })); expect(JSON.parse(screen.getByLabelText('复制当前正文').textContent!)).toEqual(view().currentRevision.data);
    fireEvent.click(screen.getByRole('button', { name: '复制重做' })); expect(JSON.parse(screen.getByLabelText('复制当前正文').textContent!)).toEqual(history().data);
    fireEvent.click(screen.getByRole('button', { name: '复制另存' })); await act(async () => {}); expect(saveLesson).toHaveBeenCalledTimes(1); expect(saveLesson.mock.calls[0][1]).toMatchObject({ expectedRevision: 1, data: history().data }); expect(JSON.parse(localStorage.getItem(serverSessionKey('g3-copy'))!).serverRevision).toBe(2);
  });
  it.each(['document', 'history'])('late copy cannot act on a different %s identity or release its new owner', async (target) => {
    const late = deferred<LessonView>(); const getLesson = vi.fn<typeof lessonPlanApi.getLesson>().mockResolvedValueOnce(view()).mockResolvedValueOnce(view()).mockImplementationOnce(() => late.promise).mockImplementation(async (id) => view(1, id)); host(getLesson); await prepare(); fireEvent.click(copyButton());
    fireEvent.click(screen.getByRole('button', { name: target === 'document' ? '复制打开另一文档' : '复制打开另一历史' }));
    await waitFor(() => expect(screen.getByLabelText('复制课题')).toHaveValue(target === 'document' ? 'g3-other当前正文' : '历史正文'));
    const before = screen.getByLabelText('复制当前正文').textContent; await act(async () => late.resolve(view())); expect(screen.getByLabelText('复制当前正文').textContent).toBe(before); expect(screen.getByLabelText('复制意图')).toHaveTextContent('-');
  });
  it('a real CAS change keeps current input and intent, then needs manual baseline adoption before a fresh copy', async () => {
    const late = deferred<LessonView>(); const getLesson = vi.fn<typeof lessonPlanApi.getLesson>().mockResolvedValueOnce(view()).mockResolvedValueOnce(view()).mockImplementationOnce(() => late.promise).mockResolvedValueOnce(view(3)); host(getLesson); await prepare(); fireEvent.click(copyButton());
    await act(async () => late.resolve(view(3))); expect(screen.getByLabelText('复制课题')).toHaveValue('g3-copy当前正文'); expect(screen.getByLabelText('复制意图')).toHaveTextContent('g3-history'); expect(screen.getByLabelText('复制通知')).toHaveTextContent('后台基线变化'); expect(copyButton()).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '复制采用新基线' })); fireEvent.click(copyButton()); await act(async () => {}); expect(JSON.parse(screen.getByLabelText('复制当前正文').textContent!)).toEqual(history().data);
  });
  it('a failed GET retains the full draft and copy intent and releases only that request for explicit retry', async () => {
    const late = deferred<LessonView>(); const getLesson = vi.fn<typeof lessonPlanApi.getLesson>().mockResolvedValueOnce(view()).mockResolvedValueOnce(view()).mockImplementationOnce(() => late.promise).mockResolvedValueOnce(view()); host(getLesson); await prepare(); fireEvent.click(copyButton());
    const before = screen.getByLabelText('复制当前正文').textContent; await act(async () => late.reject(new ApiError('ISOLATED_READ_FAILURE', '隔离读取失败', 503, true)));
    expect(screen.getByLabelText('复制当前正文').textContent).toBe(before); expect(screen.getByLabelText('复制意图')).toHaveTextContent('g3-history'); expect(copyButton()).toBeEnabled(); expect(screen.getByLabelText('复制错误')).toHaveTextContent('隔离读取失败');
    fireEvent.click(copyButton()); await act(async () => {}); expect(JSON.parse(screen.getByLabelText('复制当前正文').textContent!)).toEqual(history().data);
  });
});
