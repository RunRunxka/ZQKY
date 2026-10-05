// Public SourcePanel controls. Expected cancellation semantics are handwritten;
// only API responses and the document/session boundary use isolated fixtures.
import React, { useState } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { SourcePanel, initialGenerationInputs, type GenerationInputs } from './components/SourcePanel';
import type { DocumentSelection } from './model/DocumentContext';
import type { LessonEvidenceView } from '@/contracts/lesson-plans';

const holder = vi.hoisted(() => ({ doc: null as unknown, editor: null as unknown }));
vi.mock('./model/DocumentContext', () => ({ useLessonDocument: () => holder.doc }));
vi.mock('./model/EditorContext', () => ({ useLessonEditor: () => holder.editor }));
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (error: Error) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
const page = <T,>(items: T[]) => ({ items, offset: 0, limit: 200, total: items.length });
const tax = { stages: [], subjects: [{ id: 'math', label: '数学' }],
  grades: [{ id: 'g7', label: '七年级' }, { id: 'g8', label: '八年级' }],
  editions: [{ id: 'edition', label: '版本一' }, { id: 'edition-next', label: '版本二' }] };
const report = { runId: 'report-A', subjectId: 'math', reportReady: true, paperTitle: '固定匿名卷', scoreRevisionId: 'score-A',
  knowledgePoints: [{ knowledgePointId: 'kp-A', knowledgeRevisionId: 'kr-A', name: '知识点A' }] };
const source = { documentRevisionId: 'revision-first', charStart: 0, charEnd: 10, text: '固定教材第一段', normalizedTextSha256: 'fixture-sha' };
function evidence(id = 'first'): LessonEvidenceView {
  const ref = { ...source, evidenceId: `evidence-${id}` };
  return { scopeSnapshot: { schemaVersion: 2, selection: { gradeId: 'g7', subjectId: 'math', editionId: 'edition', documentIds: ['first'] },
    documents: [{ documentId: 'first', documentRevisionId: source.documentRevisionId, metadataRevisionId: 'metadata-first' }], embeddingGenerationId: 'fixture-generation', scopeHash: 'fixture-scope' },
    evidenceRefs: [ref], evidence: [{ ...ref, documentId: 'first', title: `教材证据${id}`, editionLabel: '版本一', subjectLabel: '数学',
      chapterPath: ['匿名章'], text: source.text, originalFileSha256: 'fixture-original',
      locator: { kind: 'markdown', lineStart: 1, lineEnd: 1, pageStart: null, pageEnd: null, blockStart: null, blockEnd: null }, isSuperseded: false }] };
}
function fixture(mode = 'server') {
  const f = { id: 'g4-source-one', mode, session: 1, discard: 0, store: {},
    inputs: structuredClone(initialGenerationInputs), selection: null as unknown as DocumentSelection,
    api: { verifyLessonEvidence: vi.fn(async () => evidence()) },
    sources: {
      listClasses: vi.fn(async () => page([{ id: 'class-one', name: '匿名班一' }, { id: 'class-two', name: '匿名班二' }])),
      taxonomy: vi.fn(async () => tax), listProfiles: vi.fn(async () => [{ id: 'model-one', displayName: '匿名模型', modelId: 'fixture-model' }]),
      listRuns: vi.fn(async () => page([report])), getRun: vi.fn(async () => report),
      listClassesReport: vi.fn(async () => page([{ classId: 'class-one' }])), listPractices: vi.fn(async () => page([])),
      listDocuments: vi.fn(async () => ({ documents: ['first', 'second'].map(id => ({ documentId: id, title: `教材${id}`,
        currentRevision: { revisionId: `revision-${id}`, charCount: 100 }, deletedAt: null })) })),
      getDocumentSource: vi.fn(async () => source),
      listConfirmedQuestionRevisions: vi.fn(async () => page([{ questionRevisionId: 'question-fixed', subjectId: 'math', stemMarkdown: '固定题' }])),
    },
  };
  function Harness() {
    const [selection, setSelection] = useState<DocumentSelection>({ subjectId: 'math', classId: 'class-one', context: null });
    const [inputs, setInputs] = useState<GenerationInputs>({ ...structuredClone(initialGenerationInputs), modelProfileId: 'model-one',
      requirements: '教师原要求', durationMinutes: 45, questionRevisionIds: ['question-fixed'], practiceRevisionIds: ['practice-fixed'] });
    f.selection = selection; f.inputs = inputs;
    const server = { discardGeneration: f.discard, captureSession: () => ({ id: f.id, session: f.session }),
      isCurrentSession: (s: { id: string; session: number } | null) => !!s && s.id === f.id && s.session === f.session,
      setContext: (_context: unknown, s: { id: string; session: number }) => s.id === f.id && s.session === f.session };
    holder.doc = { mode: f.mode, documentId: f.id, selection, setSelection, sources: f.sources, api: f.api };
    holder.editor = { store: f.store, server };
    return <SourcePanel value={inputs} onChange={setInputs} />;
  }
  const mounted = render(<Harness />);
  return { f, refreshIdentity: () => mounted.rerender(<Harness />), unmount: mounted.unmount };
}
async function settle() { await act(async () => {}); }
function verify() { fireEvent.click(screen.getByRole('button', { name: '读取并核验教材切片' })); }
function clear() { fireEvent.click(screen.getByRole('button', { name: '清除已选教材切片' })); }
async function ready(nonempty = false, mode = 'server') {
  const mounted = fixture(mode);
  const details = screen.getByText('班级、固定学情与生成来源').closest('details')!;
  details.open = true; fireEvent(details, new Event('toggle')); await settle();
  fireEvent.change(screen.getByLabelText('教材年级'), { target: { value: 'g7' } });
  fireEvent.change(screen.getByLabelText('教材版本'), { target: { value: 'edition' } });
  fireEvent.click(screen.getByRole('button', { name: '读取可选教材' }));
  await screen.findByRole('option', { name: '教材first · revision-first' });
  fireEvent.change(screen.getByLabelText('教材固定修订'), { target: { value: 'first' } });
  fireEvent.change(screen.getByLabelText('切片终点'), { target: { value: '10' } });
  if (nonempty) { verify(); await screen.findByText('教材证据first · revision-first · [0, 10)'); }
  mounted.f.api.verifyLessonEvidence.mockClear(); mounted.f.sources.getDocumentSource.mockClear();
  return mounted;
}
type Stage = 'source' | 'verify';
async function hold(f: ReturnType<typeof fixture>['f'], stage: Stage) {
  const lateSource = deferred<typeof source>(), lateVerify = deferred<LessonEvidenceView>();
  if (stage === 'source') f.sources.getDocumentSource.mockImplementationOnce(() => lateSource.promise);
  else f.api.verifyLessonEvidence.mockImplementationOnce(() => lateVerify.promise);
  verify(); await settle();
  expect(f.sources.getDocumentSource).toHaveBeenCalledTimes(1);
  expect(f.api.verifyLessonEvidence).toHaveBeenCalledTimes(stage === 'source' ? 0 : 1);
  return {
    release: async () => { await act(async () => { if (stage === 'source') lateSource.resolve(source); else lateVerify.resolve(evidence('late')); }); },
    fail: async () => { await act(async () => { if (stage === 'source') lateSource.reject(new Error('旧核验失败不得显示')); else lateVerify.reject(new Error('旧核验失败不得显示')); }); },
  };
}
beforeEach(() => { holder.doc = null; holder.editor = null; });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('G4-S explicit teacher evidence cancellation', () => {
  it.each([
    ['source', false, 1], ['source', true, 1], ['verify', false, 1], ['verify', true, 1],
    ['source', false, 2], ['source', true, 2], ['verify', false, 2], ['verify', true, 2],
  ] as const)('%s in flight, evidence nonempty=%s, clears=%s: no cancelled evidence adoption', async (stage, nonempty, clears) => {
    const { f } = await ready(nonempty), pending = await hold(f, stage), preserved = structuredClone(f.inputs);
    for (let count = 0; count < clears; count += 1) clear();
    expect(screen.getByRole('button', { name: '清除已选教材切片' })).toBeEnabled();
    await pending.release();
    expect(f.inputs).toEqual({ ...preserved, evidence: null });
    expect(screen.queryByText(/教材证据.*revision-first/)).not.toBeInTheDocument();
    expect(f.api.verifyLessonEvidence).toHaveBeenCalledTimes(stage === 'source' ? 0 : 1);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
  it.each([['source', false], ['source', true], ['verify', false], ['verify', true]] as const)(
    '%s late error after explicit clear, evidence nonempty=%s: does not revive an old failure', async (stage, nonempty) => {
      const { f } = await ready(nonempty), pending = await hold(f, stage); clear(); await pending.fail();
      expect(f.inputs.evidence).toBeNull(); expect(screen.queryByRole('alert')).not.toBeInTheDocument();
    });
  it.each(['source', 'verify'] as const)('%s old response cannot undo a new successful teacher verification', async stage => {
    const { f } = await ready(), pending = await hold(f, stage); clear();
    f.api.verifyLessonEvidence.mockResolvedValueOnce(evidence('new')); verify();
    await screen.findByText('教材证据new · revision-first · [0, 10)');
    expect(f.inputs.evidence).toEqual(evidence('new')); await pending.release();
    expect(f.inputs.evidence).toEqual(evidence('new'));
    expect(screen.queryByText('教材证据late · revision-first · [0, 10)')).not.toBeInTheDocument();
  });
  it.each(['source', 'verify'] as const)('%s preserves the original selection/value signature guard', async stage => {
    const { f } = await ready(), pending = await hold(f, stage);
    fireEvent.change(screen.getByLabelText('教案生成要求'), { target: { value: '教师新的完整要求<>&' } });
    await pending.release(); expect(f.inputs.evidence).toBeNull(); expect(f.inputs.requirements).toBe('教师新的完整要求<>&');
    expect(f.api.verifyLessonEvidence).toHaveBeenCalledTimes(stage === 'source' ? 0 : 1);
  });
  it.each(['grade', 'edition'] as const)('%s scope change revokes in-flight source before verification', async scope => {
    const { f } = await ready(), pending = await hold(f, 'source');
    fireEvent.change(screen.getByLabelText(scope === 'grade' ? '教材年级' : '教材版本'), { target: { value: scope === 'grade' ? 'g8' : 'edition-next' } });
    await pending.release(); expect(f.inputs.evidence).toBeNull(); expect(f.api.verifyLessonEvidence).not.toHaveBeenCalled();
  });
  it.each(['document', 'store', 'session', 'mode', 'discard'] as const)('%s ownership change rejects a late verified result', async ownership => {
    const { f, refreshIdentity } = await ready(), pending = await hold(f, 'verify');
    if (ownership === 'document') f.id = 'g4-source-two';
    else if (ownership === 'store') f.store = {};
    else if (ownership === 'session') f.session += 1;
    else if (ownership === 'mode') f.mode = 'history';
    else f.discard += 1;
    refreshIdentity(); await pending.release(); expect(f.inputs.evidence).toBeNull();
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });
  it('class selection change rejects old verification with the original selection guard', async () => {
    const { f } = await ready(false, 'local'), pending = await hold(f, 'verify');
    fireEvent.change(screen.getByLabelText('教案班级'), { target: { value: 'class-two' } });
    await pending.release(); expect(f.inputs.evidence).toBeNull(); expect(f.selection.classId).toBe('class-two');
  });
  it.each(['source', 'verify'] as const)('%s keeps edits that prepare the next fragment separate from cancellation', async stage => {
    const { f } = await ready(), pending = await hold(f, stage);
    fireEvent.change(screen.getByLabelText('教材固定修订'), { target: { value: 'second' } });
    fireEvent.change(screen.getByLabelText('切片起点'), { target: { value: '20' } });
    fireEvent.change(screen.getByLabelText('切片终点'), { target: { value: '30' } });
    await pending.release(); expect(f.inputs.evidence).not.toBeNull();
    expect(f.inputs.evidence!.evidenceRefs[0]).toMatchObject({ documentRevisionId: 'revision-first', charStart: 0, charEnd: 10 });
    expect(screen.getByLabelText('教材固定修订')).toHaveValue('second'); expect(screen.getByLabelText('切片起点')).toHaveValue(20);
    expect(screen.getByLabelText('切片终点')).toHaveValue(30);
    expect(f.api.verifyLessonEvidence).toHaveBeenCalledWith({ selection: { gradeId: 'g7', subjectId: 'math', editionId: 'edition', documentIds: ['first'] },
      slices: [{ documentRevisionId: 'revision-first', charStart: 0, charEnd: 10 }] });
  });
  it('explicit evidence clear leaves a pending report intent and its selected knowledge point usable', async () => {
    const { f } = await ready(), pending = deferred<typeof report>(); f.sources.getRun.mockImplementationOnce(() => pending.promise);
    fireEvent.change(screen.getByLabelText('固定学情报告'), { target: { value: report.runId } }); await settle(); clear();
    await act(async () => pending.resolve(report)); await screen.findByRole('checkbox', { name: /知识点A/ });
    fireEvent.click(screen.getByRole('checkbox', { name: /知识点A/ }));
    expect(f.selection.context).toEqual({ analysisRunId: report.runId, selectedKnowledgePointIds: ['kp-A'] });
    expect(f.inputs.classReady).toBe(true); expect(f.inputs.evidence).toBeNull();
  });
  it('explicit evidence clear leaves a pending fixed-question read and unrelated chosen sources intact', async () => {
    const { f } = await ready(), pending = deferred<ReturnType<typeof page<{ questionRevisionId: string; subjectId: string; stemMarkdown: string }>>>();
    f.sources.listConfirmedQuestionRevisions.mockImplementationOnce(() => pending.promise);
    fireEvent.click(screen.getByRole('button', { name: '读取已确认固定题' })); clear();
    await act(async () => pending.resolve(page([{ questionRevisionId: 'question-fixed', subjectId: 'math', stemMarkdown: '固定题' }])));
    expect(await screen.findByRole('checkbox', { name: /固定题/ })).toBeChecked();
    expect(f.inputs.questionRevisionIds).toEqual(['question-fixed']); expect(f.inputs.practiceRevisionIds).toEqual(['practice-fixed']);
  });
  it('unmount prevents a late failure or evidence change in the departed view', async () => {
    const { f, unmount } = await ready(), pending = await hold(f, 'verify'), original = structuredClone(f.inputs);
    unmount(); await pending.fail(); expect(f.inputs).toEqual(original);
  });
});
