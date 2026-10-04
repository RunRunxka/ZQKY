// Independent oracle: teacher cancellation / visible coordinates own pending evidence.
// Real SourcePanel and DOM. API and session boundary are isolated handwritten fixtures.
import React, { useState } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SourcePanel, initialGenerationInputs, type GenerationInputs } from '@/features/lesson-plan/components/SourcePanel';
import type { DocumentSelection } from '@/features/lesson-plan/model/DocumentContext';

const holder = vi.hoisted(() => ({ doc: null as unknown, editor: null as unknown }));
vi.mock('@/features/lesson-plan/model/DocumentContext', () => ({ useLessonDocument: () => holder.doc }));
vi.mock('@/features/lesson-plan/model/EditorContext', () => ({ useLessonEditor: () => holder.editor }));
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => { resolve = yes; }); return { promise, resolve }; }
const page = <T,>(items: T[]) => ({ items, offset: 0, limit: 200, total: items.length });
const report = { runId: 'A', subjectId: 'math', reportReady: true, paperTitle: '固定匿名卷', scoreRevisionId: 'score-A', knowledgePoints: [{ knowledgePointId: 'kp-A', knowledgeRevisionId: 'kr-A', name: '知识点A' }] };
const tax = { stages: [], grades: [{ id: 'g7', label: '七年级' }, { id: 'g8', label: '八年级' }], subjects: [{ id: 'math', label: '数学' }], editions: [{ id: 'edition', label: '人教版' }] };
const document = (id: string) => ({ documentId: id, title: '教材'+id, currentRevision: { revisionId: 'revision-'+id, charCount: 100 }, deletedAt: null });
const source = { documentRevisionId: 'revision-first', charStart: 0, charEnd: 10, text: '教材第一段', normalizedTextSha256: 'fixture-only' };
const evidence = { scopeSnapshot: { selection: { gradeId: 'g7', subjectId: 'math', editionId: 'edition', documentIds: ['first'] } }, evidenceRefs: [{ ...source, evidenceId: 'e1' }], evidence: [{ ...source, evidenceId: 'e1', documentId: 'first', title: '教材first' }] };
function fixture(linked = false) {
  const f = { session: 1, id: 'lesson-one', store: {}, inputs: structuredClone(initialGenerationInputs), selection: null as unknown as DocumentSelection,
    api: { verifyLessonEvidence: vi.fn(async () => evidence) }, sources: {
      listClasses: vi.fn(async () => page([{ id: 'class-one', name: '匿名班级' }])), taxonomy: vi.fn(async () => tax),
      listProfiles: vi.fn(async () => [{ id: 'model-one', displayName: '匿名模型', modelId: 'fixture-model' }]),
      listRuns: vi.fn(async () => page([report])), getRun: vi.fn(async () => report), listClassesReport: vi.fn(async () => page([{ classId: 'class-one' }])), listPractices: vi.fn(async () => page([])),
      listDocuments: vi.fn(async () => ({ documents: [document('first'), document('second')] })), getDocumentSource: vi.fn(async () => source),
    } };
  function Harness() {
    const [selection, setSelection] = useState<DocumentSelection>({ subjectId: 'math', classId: 'class-one', context: linked ? { analysisRunId: 'A', selectedKnowledgePointIds: ['kp-A'] } : null });
    const [inputs, setInputs] = useState<GenerationInputs>(structuredClone(initialGenerationInputs));
    f.inputs = inputs; f.selection = selection;
    const server = { discardGeneration: 0, captureSession: () => ({ id: f.id, session: f.session }), isCurrentSession: (s: { id: string; session: number } | null) => !!s && s.id === f.id && s.session === f.session,
      setContext: (_context: unknown, s: { id: string; session: number }) => s.id === f.id && s.session === f.session };
    holder.doc = { mode: 'server', documentId: f.id, selection, setSelection, sources: f.sources, api: f.api };
    holder.editor = { store: f.store, server };
    return <SourcePanel value={inputs} onChange={setInputs} />;
  }
  const mounted = render(<Harness />);
  return { f, refreshIdentity: () => mounted.rerender(<Harness />) };
}
async function ready(linked = false) {
  const mounted = fixture(linked);
  const details = screen.getByText('班级、固定学情与生成来源').closest('details')!;
  details.open = true; fireEvent(details, new Event('toggle')); await act(async () => {});
  if (linked) await screen.findByRole('checkbox', { name: /知识点A/ });
  fireEvent.change(screen.getByLabelText('教材年级'), { target: { value: 'g7' } });
  fireEvent.change(screen.getByLabelText('教材版本'), { target: { value: 'edition' } });
  fireEvent.click(screen.getByRole('button', { name: '读取可选教材' }));
  await screen.findByRole('option', { name: '教材first · revision-first' });
  fireEvent.change(screen.getByLabelText('教材固定修订'), { target: { value: 'first' } });
  fireEvent.change(screen.getByLabelText('切片终点'), { target: { value: '10' } });
  return mounted;
}
function verify() { fireEvent.click(screen.getByRole('button', { name: '读取并核验教材切片' })); }
beforeEach(() => { holder.doc = null; holder.editor = null; });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('source intent independent review oracle', () => {
  it('explicit clear revokes an in-flight first evidence verification', async () => {
    const { f } = await ready(), late = deferred<typeof evidence>(); f.api.verifyLessonEvidence.mockImplementationOnce(() => late.promise);
    verify(); await act(async () => {}); expect(f.api.verifyLessonEvidence).toHaveBeenCalledTimes(1);
    fireEvent.click(screen.getByRole('button', { name: '清除已选教材切片' }));
    await act(async () => late.resolve(evidence));
    expect(f.inputs.evidence, '教师明确清除后不得由旧核验响应复活教材依据').toBeNull();
  });
  it('changing visible slice coordinates revokes pending old coordinates', async () => {
    const { f } = await ready(), late = deferred<typeof source>(); f.sources.getDocumentSource.mockImplementationOnce(() => late.promise);
    verify(); fireEvent.change(screen.getByLabelText('切片终点'), { target: { value: '20' } });
    await act(async () => late.resolve(source));
    expect(screen.getByLabelText('切片终点')).toHaveValue(20);
    expect(f.inputs.evidence, '当前20字符选择不能采用旧10字符核验').toBeNull();
    expect(f.api.verifyLessonEvidence).not.toHaveBeenCalled();
  });
  it('changing visible fixed document revokes pending old document', async () => {
    const { f } = await ready(), late = deferred<typeof source>(); f.sources.getDocumentSource.mockImplementationOnce(() => late.promise);
    verify(); fireEvent.change(screen.getByLabelText('教材固定修订'), { target: { value: 'second' } });
    await act(async () => late.resolve(source));
    expect(screen.getByLabelText('教材固定修订')).toHaveValue('second');
    expect(f.inputs.evidence, '第二本教材选择不能采用旧第一本教材核验').toBeNull();
    expect(f.api.verifyLessonEvidence).not.toHaveBeenCalled();
  });
  it('changing grade revokes pending source coordinates', async () => {
    const { f } = await ready(), late = deferred<typeof source>(); f.sources.getDocumentSource.mockImplementationOnce(() => late.promise);
    verify(); fireEvent.change(screen.getByLabelText('教材年级'), { target: { value: 'g8' } }); await act(async () => late.resolve(source));
    expect(f.inputs.evidence).toBeNull(); expect(f.api.verifyLessonEvidence).not.toHaveBeenCalled();
  });
  it('new document/store/session cannot adopt old verified evidence', async () => {
    const { f, refreshIdentity } = await ready(), late = deferred<typeof evidence>(); f.api.verifyLessonEvidence.mockImplementationOnce(() => late.promise);
    verify(); await act(async () => {}); f.session += 1; f.id = 'lesson-two'; f.store = {}; refreshIdentity();
    await act(async () => late.resolve(evidence)); expect(f.inputs.evidence).toBeNull();
  });
  it('teacher requirements changed during verification revoke old evidence response', async () => {
    const { f } = await ready(), late = deferred<typeof evidence>(); f.api.verifyLessonEvidence.mockImplementationOnce(() => late.promise);
    verify(); await act(async () => {}); fireEvent.change(screen.getByLabelText('教案生成要求'), { target: { value: '教师新要求' } });
    await act(async () => late.resolve(evidence)); expect(f.inputs.evidence).toBeNull(); expect(f.inputs.requirements).toBe('教师新要求');
  });
});
