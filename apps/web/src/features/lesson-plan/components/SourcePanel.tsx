'use client';
import { useEffect, useRef, useState } from 'react';
import type { AnalysisRunView, ClassReportRow, Page, PracticeRevisionView, PracticeSetView } from '@/contracts/b4';
import type { ClassView } from '@/contracts/roster';
import type { DocumentSummary, TextbookTaxonomy } from '@/contracts/textbook';
import type { ModelProfileView } from '@/contracts/model-settings';
import type { LessonEvidenceView } from '@/contracts/lesson-plans';
import { asApiError, stablePayloadKey } from '@/features/assessments/hooks';
import { useLessonDocument } from '../model/DocumentContext';
import { useLessonEditor } from '../model/EditorContext';
import type { ConfirmedQuestionRevision } from '@/services/lesson-plan-sources-api';

export interface GenerationInputs { modelProfileId: string; requirements: string; durationMinutes: number; evidence: LessonEvidenceView | null; questionRevisionIds: string[]; practiceRevisionIds: string[]; classReady: boolean }
export const initialGenerationInputs: GenerationInputs = { modelProfileId: '', requirements: '', durationMinutes: 40, evidence: null, questionRevisionIds: [], practiceRevisionIds: [], classReady: false };
export function SourcePanel({ value, onChange }: { value: GenerationInputs; onChange: (value: GenerationInputs) => void }) {
  const doc = useLessonDocument(), editor = useLessonEditor();
  const [classes, setClasses] = useState<ClassView[]>([]), [taxonomy, setTaxonomy] = useState<TextbookTaxonomy | null>(null), [profiles, setProfiles] = useState<ModelProfileView[]>([]);
  const [runs, setRuns] = useState<AnalysisRunView[]>([]), [run, setRun] = useState<AnalysisRunView | null>(null), [runClasses, setRunClasses] = useState<string[]>([]);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]), [practiceRevisions, setPracticeRevisions] = useState<PracticeRevisionView[]>([]);
  const [questions, setQuestions] = useState<ConfirmedQuestionRevision[]>([]), [questionTotal, setQuestionTotal] = useState(0);
  const [gradeId, setGrade] = useState(''), [editionId, setEdition] = useState(''), [documentId, setDocument] = useState('');
  const [start, setStart] = useState(0), [end, setEnd] = useState(1000), [error, setError] = useState(''), [loading, setLoading] = useState(false), [opened, setOpened] = useState(false);
  const alive = useRef(true), epoch = useRef(0), metadataEpoch = useRef(0), pendingReport = useRef<symbol | null>(null);
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current += 1; metadataEpoch.current += 1; pendingReport.current = null; }; }, []);
  const selection = doc.selection;
  const latest = useRef({ selection, value, doc, editor }); latest.current = { selection, value, doc, editor };
  const discarded = editor.server?.discardGeneration ?? 0;
  const seenDiscard = useRef(discarded);
  useEffect(() => {
    if (seenDiscard.current === discarded) return;
    seenDiscard.current = discarded; epoch.current += 1; metadataEpoch.current += 1; pendingReport.current = null;
    setRun(null); setRunClasses([]); setPracticeRevisions([]); setError(''); setLoading(false);
    const inputs = { ...latest.current.value, evidence: null, questionRevisionIds: [], practiceRevisionIds: [], classReady: false };
    latest.current = { ...latest.current, value: inputs }; onChange(inputs);
  }, [discarded, onChange]);
  function beginRead(kind: 'source' | 'metadata' = 'source') {
    const counter = kind === 'metadata' ? metadataEpoch : epoch;
    const origin = latest.current, token = ++counter.current, selectionEpoch = epoch.current;
    const session = origin.editor.server?.captureSession() ?? null;
    const isOwned = () => alive.current && token === counter.current && latest.current.doc.mode === origin.doc.mode &&
      latest.current.doc.documentId === origin.doc.documentId && latest.current.editor.store === origin.editor.store;
    const isCurrent = () => isOwned() && (!origin.editor.server || origin.editor.server.isCurrentSession(session));
    return { origin, token, session, selectionEpoch, isOwned, isCurrent };
  }
  function changeInputs(patch: Partial<GenerationInputs>) {
    const next = { ...latest.current.value, ...patch };
    latest.current = { ...latest.current, value: next };
    onChange(next);
  }
  function updateSelection(next: typeof selection, eligible = !!next.context && run?.runId === next.context.analysisRunId && runClasses.includes(next.classId), read?: ReturnType<typeof beginRead>) {
    if (read && !read.isCurrent()) return false;
    const current = latest.current;
    if (current.editor.server && !current.editor.server.setContext(next.context, read?.session ?? current.editor.server.captureSession())) return false;
    const changed = stablePayloadKey(next) !== stablePayloadKey(current.selection);
    const inputs = { ...current.value, evidence: changed ? null : current.value.evidence, classReady: eligible,
      questionRevisionIds: next.subjectId !== current.selection.subjectId ? [] : current.value.questionRevisionIds,
      practiceRevisionIds: next.context?.analysisRunId !== current.selection.context?.analysisRunId ? [] : current.value.practiceRevisionIds };
    epoch.current += 1;
    latest.current = { ...current, selection: next, value: inputs };
    current.doc.setSelection(next); onChange(inputs); return true;
  }
  async function readPages<T>(owner: ReturnType<typeof beginRead>, label: string, read: (query: { offset: number; limit: number }) => Promise<Page<T>>) {
    const items: T[] = []; let total: number | null = null;
    do {
      if (!owner.isCurrent()) return null;
      const offset = items.length;
      const page = await read({ offset, limit: 200 });
      if (!owner.isCurrent()) return null;
      if (!Number.isSafeInteger(page.total) || page.total < 0 || page.offset !== offset || page.items.length > 200 || offset + page.items.length > page.total || (total !== null && total !== page.total)) throw new Error(`${label}分页返回不一致；未采用不完整来源，请刷新重试。`);
      total = page.total;
      if (page.items.length === 0 && offset < total) throw new Error(`${label}分页缺失；未将读取失败当空报告。`);
      items.push(...page.items);
    } while (items.length < total!);
    return items;
  }
  async function load() {
    const owner = beginRead('metadata'), pendingAtStart = pendingReport.current; if (!owner.isCurrent()) return; setLoading(true); setError('');
    try { const [classList, tax, models, reports] = await Promise.all([readPages<ClassView>(owner, '班级列表', (query) => doc.sources.listClasses({ status: 'active', ...query })), doc.sources.taxonomy(), doc.sources.listProfiles(), readPages<AnalysisRunView>(owner, '固定学情列表', (query) => doc.sources.listRuns(query))]);
      if (!owner.isCurrent()) return;
      if (!classList || !reports) return;
      setClasses(classList); setTaxonomy(tax); setProfiles(models); setRuns(reports.filter((item) => item.reportReady)); setLoading(false);
      const current = latest.current.selection;
      const initial = current.context?.analysisRunId ?? doc.initialAnalysisRunId;
      if (initial && !pendingAtStart && !pendingReport.current && owner.selectionEpoch === epoch.current) await selectRun(initial, current.context?.selectedKnowledgePointIds);
    } catch (cause) { if (owner.isCurrent()) setError(asApiError(cause).message); }
    finally { if (owner.isOwned()) setLoading(false); }
  }
  async function selectRun(id: string, selected?: string[]) {
    const owner = beginRead(); if (!owner.isCurrent()) return; setError('');
    const intent = Symbol('report-read'); pendingReport.current = intent;
    try { if (!id) { if (updateSelection({ ...latest.current.selection, context: null }, false, owner)) { setRun(null); setRunClasses([]); } return; }
      const [next, report, practices] = await Promise.all([doc.sources.getRun(id), readPages<ClassReportRow>(owner, '固定报告班级', (query) => doc.sources.listClassesReport(id, query)), readPages<PracticeSetView>(owner, '固定练习列表', (query) => doc.sources.listPractices({ analysisRunId: id, ...query }))]);
      if (!owner.isCurrent()) return;
      if (!report || !practices) return;
      const current = latest.current.selection;
      if (!next.reportReady || (current.subjectId && next.subjectId !== current.subjectId)) throw new Error('必须选择同学科的 ready 固定学情报告');
      const fixed = practices.flatMap((practice) => practice.revisions).filter((revision) => revision.state === 'reviewed' && revision.subjectId === next.subjectId);
      const kept = (selected ?? (current.context?.analysisRunId === id ? current.context.selectedKnowledgePointIds : [])).filter((id) => next.knowledgePoints.some((point) => point.knowledgePointId === id));
      if (!updateSelection({ ...current, subjectId: current.subjectId || next.subjectId, context: kept.length ? { analysisRunId: id, selectedKnowledgePointIds: kept } : null }, kept.length > 0 && report.some((row) => row.classId === current.classId), owner)) return;
      setRun(next); setRunClasses([...new Set(report.map((row) => row.classId))]);
      setPracticeRevisions([...new Map(fixed.map((revision) => [revision.practiceRevisionId, revision])).values()]);
    } catch (cause) { if (owner.isCurrent()) setError(asApiError(cause).message); }
    finally { if (pendingReport.current === intent) pendingReport.current = null; }
  }
  async function loadDocuments() {
    const owner = beginRead(); if (!owner.isCurrent()) return; setError('');
    try { if (!selection.subjectId || !gradeId || !editionId) throw new Error('先明确学科、年级与版本'); const list = await doc.sources.listDocuments({ subjectId: selection.subjectId, gradeId, editionId }); if (owner.isCurrent()) setDocuments(list.documents.filter((item) => !!item.currentRevision && !item.deletedAt)); }
    catch (cause) { if (owner.isCurrent()) setError(asApiError(cause).message); }
  }
  async function loadQuestions(more = false) { const owner = beginRead(); if (!owner.isCurrent()) return; setError(''); try { if (!selection.subjectId) throw new Error('请先明确学科'); const page = await doc.sources.listConfirmedQuestionRevisions(selection.subjectId, { offset: more ? questions.length : 0, limit: 50 }); if (owner.isCurrent()) { setQuestions((old) => more ? [...old, ...page.items] : page.items); setQuestionTotal(page.total); } } catch (cause) { if (owner.isCurrent()) setError(asApiError(cause).message); } }
  async function verifySlice() {
    const owner = beginRead(), captured = stablePayloadKey({ selection, value }); if (!owner.isCurrent()) return; setError('');
    try { const chosen = documents.find((item) => item.documentId === documentId); if (!chosen?.currentRevision || !Number.isSafeInteger(start) || !Number.isSafeInteger(end) || start < 0 || end <= start || end - start > 6000 || end > chosen.currentRevision.charCount) throw new Error('请选择真实教材固定修订的有效切片（每段最多6000字符）');
      const span = await doc.sources.getDocumentSource(chosen.currentRevision.revisionId, start, end);
      if (!owner.isCurrent()) return;
      if (span.documentRevisionId !== chosen.currentRevision.revisionId || span.charStart !== start || span.charEnd !== end) throw new Error('教材切片固定身份不匹配');
      const old = value.evidence;
      const slices = [...(old?.evidenceRefs ?? []).map((ref) => ({ documentRevisionId: ref.documentRevisionId, charStart: ref.charStart, charEnd: ref.charEnd })), { documentRevisionId: span.documentRevisionId, charStart: start, charEnd: end }];
      if (slices.length > 6 || slices.reduce((sum, slice) => sum + slice.charEnd - slice.charStart, 0) > 16000) throw new Error('最多6段，合计16000字符');
      const ids = [...new Set([...(old?.scopeSnapshot.selection.documentIds ?? []), documentId])];
      const verified = await doc.api.verifyLessonEvidence({ selection: { gradeId, subjectId: selection.subjectId, editionId, documentIds: ids }, slices });
      if (owner.isCurrent() && stablePayloadKey({ selection: latest.current.selection, value: latest.current.value }) === captured) changeInputs({ evidence: verified });
    } catch (cause) { if (owner.isCurrent()) setError(asApiError(cause).message); }
  }
  const immutable = doc.mode !== 'local';
  return <details className="lesson-server-panel" onToggle={(event) => { if (event.currentTarget.open && !opened) { setOpened(true); void load(); } }}>
    <summary>班级、固定学情与生成来源</summary><div className="lesson-panel-body">
      <p className="lesson-help">生成使用教师明确选择的固定报告、知识点和核验教材；候选不会直接修改正文。</p>
      <div className="lesson-source-grid">
        <label>学科<select aria-label="教案学科" disabled={immutable} value={selection.subjectId} onChange={(event) => { setRun(null); updateSelection({ ...selection, subjectId: event.target.value, context: null }); }}>{!selection.subjectId && <option value="">请选择学科</option>}{taxonomy?.subjects.map((subject) => <option key={subject.id} value={subject.id}>{subject.label}</option>)}{selection.subjectId && !taxonomy?.subjects.some((item) => item.id === selection.subjectId) && <option value={selection.subjectId}>{selection.subjectId}</option>}</select></label>
        <label>单一班级<select aria-label="教案班级" disabled={immutable} value={selection.classId} onChange={(event) => updateSelection({ ...selection, classId: event.target.value })}><option value="">请选择班级</option>{classes.map((item) => <option key={item.id} value={item.id}>{item.name}</option>)}{selection.classId && !classes.some((item) => item.id === selection.classId) && <option value={selection.classId}>{selection.classId}</option>}</select></label>
        <label>固定 ready 学情<select aria-label="固定学情报告" value={run?.runId ?? selection.context?.analysisRunId ?? ''} onChange={(event) => void selectRun(event.target.value)}><option value="">不关联学情</option>{runs.filter((item) => !selection.subjectId || item.subjectId === selection.subjectId).map((item) => <option key={item.runId} value={item.runId}>{item.paperTitle} · {item.scoreRevisionId} · {item.runId}</option>)}{run && !runs.some((item) => item.runId === run.runId) && <option value={run.runId}>{run.paperTitle} · {run.scoreRevisionId} · {run.runId}</option>}{!run && selection.context && !runs.some((item) => item.runId === selection.context!.analysisRunId) && <option value={selection.context.analysisRunId}>{selection.context.analysisRunId} · 固定来源（待核验）</option>}</select></label>
        <label>模型档案<select aria-label="教案生成模型" value={value.modelProfileId} onChange={(event) => changeInputs({ modelProfileId: event.target.value })}><option value="">请选择模型档案</option>{profiles.map((profile) => <option key={profile.id} value={profile.id}>{profile.displayName} · {profile.modelId}</option>)}</select></label>
      </div>
      {run && <fieldset><legend>明确选择知识点（最多50项）</legend>{runClasses.length > 0 && !runClasses.includes(selection.classId) && <p role="alert">所选班级不在固定报告中，生成暂停。</p>}{run.knowledgePoints.map((point) => <label className="lesson-check" key={point.knowledgePointId}><input type="checkbox" checked={selection.context?.analysisRunId === run.runId && selection.context.selectedKnowledgePointIds.includes(point.knowledgePointId)} onChange={(event) => { const old = selection.context?.analysisRunId === run.runId ? selection.context.selectedKnowledgePointIds : []; const ids = event.target.checked ? [...old, point.knowledgePointId] : old.filter((id) => id !== point.knowledgePointId); if (ids.length > 50) { setError('最多50个知识点'); return; } updateSelection({ ...selection, context: ids.length ? { analysisRunId: run.runId, selectedKnowledgePointIds: ids } : null }); }} />{point.name} <small>{point.knowledgeRevisionId}</small></label>)}</fieldset>}
      <div className="lesson-source-grid"><label>课堂时长（分钟）<input aria-label="课堂时长" type="number" min={5} max={180} value={value.durationMinutes} onChange={(event) => changeInputs({ durationMinutes: Number(event.target.value) })} /></label><label>教师要求<textarea aria-label="教案生成要求" aria-describedby="lesson-requirements-privacy" value={value.requirements} onChange={(event) => changeInputs({ requirements: event.target.value })} /><small id="lesson-requirements-privacy" className="lesson-help">请勿填写学生姓名、学号或人员 ID；已知身份将被阻断，系统不能保证识别全部个人信息。</small></label></div>
      <fieldset><legend>真实教材切片</legend><div className="lesson-source-grid"><label>年级<select aria-label="教材年级" value={gradeId} onChange={(event) => { epoch.current += 1; setGrade(event.target.value); setDocuments([]); setDocument(''); changeInputs({ evidence: null }); }}><option value="">请选择年级</option>{taxonomy?.grades.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label><label>教材版本<select aria-label="教材版本" value={editionId} onChange={(event) => { epoch.current += 1; setEdition(event.target.value); setDocuments([]); setDocument(''); changeInputs({ evidence: null }); }}><option value="">请选择版本</option>{taxonomy?.editions.map((item) => <option key={item.id} value={item.id}>{item.label}</option>)}</select></label></div>
        <button className="button subtle" onClick={() => void loadDocuments()}>读取可选教材</button><label>教材固定修订<select aria-label="教材固定修订" value={documentId} onChange={(event) => setDocument(event.target.value)}><option value="">请选择教材</option>{documents.map((item) => <option key={item.documentId} value={item.documentId}>{item.title} · {item.currentRevision?.revisionId}</option>)}</select></label>
        <div className="lesson-source-grid"><label>切片起点<input aria-label="切片起点" type="number" min={0} value={start} onChange={(event) => setStart(Number(event.target.value))} /></label><label>切片终点<input aria-label="切片终点" type="number" min={1} value={end} onChange={(event) => setEnd(Number(event.target.value))} /></label></div><button className="button subtle" onClick={() => void verifySlice()}>读取并核验教材切片</button><button className="button subtle" onClick={() => changeInputs({ evidence: null })}>清除已选教材切片</button>
        {value.evidence?.evidence.map((item) => <details key={item.evidenceId}><summary>{item.title} · {item.documentRevisionId} · [{item.charStart}, {item.charEnd})</summary><pre>{item.text}</pre><small>{item.normalizedTextSha256}</small></details>)}
      </fieldset>
      <fieldset><legend>已确认固定题（可选，最多20题）</legend><button className="button subtle" onClick={() => void loadQuestions()}>读取已确认固定题</button>{questions.filter((question) => question.subjectId === selection.subjectId).map((question) => <label className="lesson-check" key={question.questionRevisionId}><input type="checkbox" checked={value.questionRevisionIds.includes(question.questionRevisionId)} onChange={(event) => { const old = latest.current.value.questionRevisionIds; const ids = event.target.checked ? [...old, question.questionRevisionId] : old.filter((id) => id !== question.questionRevisionId); if (ids.length > 20) { setError('最多20个固定题'); return; } changeInputs({ questionRevisionIds: ids }); }} />{question.stemMarkdown.slice(0, 120)} <small>{question.questionRevisionId}</small></label>)}{questions.length < questionTotal && <button className="button subtle" onClick={() => void loadQuestions(true)}>继续读取已确认固定题</button>}</fieldset>
      <fieldset><legend>已审核固定练习（可选，最多5份）</legend>{practiceRevisions.map((revision) => <label className="lesson-check" key={revision.practiceRevisionId}><input type="checkbox" checked={value.practiceRevisionIds.includes(revision.practiceRevisionId)} onChange={(event) => { const old = latest.current.value.practiceRevisionIds; const ids = event.target.checked ? [...old, revision.practiceRevisionId] : old.filter((id) => id !== revision.practiceRevisionId); if (ids.length > 5) { setError('最多5份固定练习'); return; } changeInputs({ practiceRevisionIds: ids }); }} />{revision.title} · {revision.practiceRevisionId}</label>)}</fieldset>
      {loading && <p role="status">正在读取真实来源…</p>}{error && <p role="alert">{error}</p>}<button className="button subtle" onClick={() => void load()}>刷新来源列表</button>
    </div></details>;
}
