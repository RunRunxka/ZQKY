'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { GuardedLink } from '@/services/navigation-guard';
import type { PracticeDraftItem, PracticeSetView, PracticeReviewRequest, PracticeSuggestions, PracticeSuggestion, PracticeNode } from '@/contracts/b4';
import type { RichContentV2 } from '@/contracts/teaching-loop';
import { b4Api } from '@/services/teaching-loop-b4-api';
import { getQuestionAsset } from '@/services/question-bank-api';
import { asApiError, useFrozenSubmission } from '@/features/assessments/hooks';
import { ErrorNotice, SubmissionNotice, RichReview, surfaceBlocks, nameOrShortId, shortId } from '@/features/learning-analysis/ui';
import { ConstraintsFields } from './ConstraintsFields';
import { itemFromSuggestion, moveItem, withNode } from './draft';
import { ApiError } from '@/services/api-client';
import { initialPracticeSession, readPracticeSession, writePracticeSession, recoveryKey, type PracticeSession, type PracticeSaveContent, type PracticeEditingHandle } from './session';
import type { MutableRefObject } from 'react';

export function PracticeEditor({ view, services, onSaved, onLocked, sessionHandle }: {
  view: PracticeSetView; services: typeof b4Api; onSaved: (view: PracticeSetView) => void; onLocked: (locked: boolean) => void;
  sessionHandle?: MutableRefObject<PracticeEditingHandle | null>;
}) {
  const session = useRef<PracticeSession>(initialPracticeSession(view));
  const [items, setItems] = useState(() => structuredClone(view.currentRevision.draftItems));
  const [constraints, setConstraints] = useState(() => structuredClone(view.currentRevision.constraints));
  const [serverRevision, setServerRevision] = useState(view.revision);
  const [dirty, setDirty] = useState(false);
  const [cacheReady, setCacheReady] = useState(false);
  const [cacheError, setCacheError] = useState('');
  const cacheBlocked = useRef(false);
  const loadGeneration = useRef(crypto.randomUUID());
  const contextKey = `practice|${view.practiceSetId}`;
  const currentContext = useRef(contextKey); currentContext.current = contextKey;
  const known = useRef({ revision: view.revision, id: view.currentRevision.practiceRevisionId, practiceSetId: view.practiceSetId });
  if (known.current.practiceSetId !== view.practiceSetId) known.current = { revision: view.revision, id: view.currentRevision.practiceRevisionId, practiceSetId: view.practiceSetId };
  const viewRef = useRef(view); viewRef.current = view;
  if (view.revision > known.current.revision) known.current = { revision: view.revision, id: view.currentRevision.practiceRevisionId, practiceSetId: view.practiceSetId };
  const [suggestions, setSuggestions] = useState<PracticeSuggestions | null>(null);
  const [candidateCache, setCandidateCache] = useState<Record<string, PracticeSuggestion>>({});
  const [suggesting, setSuggesting] = useState(false);
  const [suggestionError, setSuggestionError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState('');
  const [manualRevisionId, setManualRevisionId] = useState('');
  const alive = useRef(true);
  const suggestGeneration = useRef(0);
  const suggestAbort = useRef<AbortController | null>(null);
  const suggestBusy = useRef(false);
  const saving = useRef<string | null>(null);
  const reviewing = useRef<string | null>(null);
  const save = useFrozenSubmission<PracticeSaveContent, PracticeSetView>();
  const review = useFrozenSubmission<PracticeReviewRequest, PracticeSetView>();
  const recoverSave = save.recoverFrozen, releaseSave = save.release;
  const recoverReview = review.recoverFrozen, releaseReview = review.release;
  const receivedOperations = useRef<Array<{ operationId: string; practiceSetId: string; revision: number; revisionId: string; current: boolean }>>([]);
  const locked = !cacheReady || cacheBlocked.current || save.phase === 'unknown' || review.busy || review.phase === 'unknown';
  const pending = save.busy || review.busy || suggesting;
  const identityConflict = (view.revision === session.current.serverRevision && view.currentRevision.practiceRevisionId !== session.current.serverRevisionId) || (!!session.current.identityConflict && view.revision <= session.current.identityConflict.revision);
  const baselineChoiceRequired = view.revision > session.current.serverRevision || identityConflict;
  function persist() {
    if (cacheBlocked.current || !cacheReady) return false;
    try { writePracticeSession(localStorage, session.current); setCacheError(''); return true; }
    catch (cause) { setCacheError(`恢复缓存写入失败：${(cause as Error).message}。输入保留，发送已暂停。`); return false; }
  }
  useEffect(() => {
    alive.current = true;
    loadGeneration.current = crypto.randomUUID();
    saving.current = null; reviewing.current = null;
    session.current = initialPracticeSession(viewRef.current);
    cacheBlocked.current = false; setCacheReady(false); setCacheError('');
    setItems(session.current.items); setConstraints(session.current.constraints); setServerRevision(session.current.serverRevision); setDirty(false);
    releaseSave(); releaseReview();
    try {
      const restored = readPracticeSession(localStorage, viewRef.current.practiceSetId);
      if (restored && (restored.dirty || restored.saveOperation || restored.reviewOperation || restored.identityConflict)) {
        session.current = restored;
        setItems(structuredClone(restored.items)); setConstraints(structuredClone(restored.constraints));
        setServerRevision(restored.serverRevision); setDirty(restored.dirty);
        if (restored.serverRevision > known.current.revision) known.current = { revision: restored.serverRevision, id: restored.serverRevisionId, practiceSetId: restored.practiceSetId };
        if (restored.saveOperation && !recoverSave(restored.saveOperation)) throw new Error('原保存操作恢复失败');
        if (restored.reviewOperation && !recoverReview(restored.reviewOperation)) throw new Error('原审核操作恢复失败');
        setNotice('已恢复此练习的独立本机稿；未知操作须显式重试原包，恢复不会自动保存或审核。');
      }
      setCacheReady(true);
    } catch (cause) { cacheBlocked.current = true; setCacheError(`恢复缓存读取失败：${(cause as Error).message}。原字节未覆盖，保存已暂停。`); }
    return () => { alive.current = false; suggestGeneration.current += 1; suggestAbort.current?.abort(); };
  }, [contextKey, recoverSave, recoverReview, releaseSave, releaseReview]);
  useEffect(() => { onLocked(pending || locked); return () => onLocked(false); }, [pending, locked, onLocked]);
  useEffect(() => {
    if (!session.current.dirty && !session.current.saveOperation && !session.current.reviewOperation && !session.current.identityConflict && cacheReady && !cacheBlocked.current && view.revision >= session.current.serverRevision && (view.revision > session.current.serverRevision || view.currentRevision.practiceRevisionId === session.current.serverRevisionId)) {
      session.current = { ...initialPracticeSession(view), editGeneration: session.current.editGeneration };
      setItems(structuredClone(view.currentRevision.draftItems)); setConstraints(structuredClone(view.currentRevision.constraints)); setServerRevision(view.revision);
    }
  }, [view, cacheReady]);
  useEffect(() => {
    const leave = (event: BeforeUnloadEvent) => {
      if (session.current.dirty || session.current.saveOperation || session.current.reviewOperation) {
        persist(); event.preventDefault(); event.returnValue = '';
      }
    };
    const hide = () => { if (session.current.dirty || session.current.saveOperation || session.current.reviewOperation) persist(); };
    window.addEventListener('beforeunload', leave); window.addEventListener('pagehide', hide);
    return () => { window.removeEventListener('beforeunload', leave); window.removeEventListener('pagehide', hide); };
  });
  useEffect(() => {
    if (!sessionHandle) return;
    const handle: PracticeEditingHandle = {
      practiceSetId: view.practiceSetId,
      get dirty() { return session.current.dirty; },
      get busy() { return !!saving.current || !!reviewing.current || suggestBusy.current; },
      get unknown() { return !!session.current.saveOperation || !!session.current.reviewOperation; },
      save: saveDraft,
      keep: persist,
      discard() {
        if (saving.current || reviewing.current || session.current.saveOperation || session.current.reviewOperation || cacheBlocked.current) return false;
        try { localStorage.removeItem(recoveryKey(view.practiceSetId)); }
        catch (cause) { setCacheError(`放弃修改失败：${(cause as Error).message}。原稿仍保留。`); return false; }
        session.current = initialPracticeSession(viewRef.current); setItems(session.current.items); setConstraints(session.current.constraints); setServerRevision(session.current.serverRevision); setDirty(false); return true;
      },
    };
    sessionHandle.current = handle;
    return () => { if (sessionHandle.current === handle) sessionHandle.current = null; };
  });
  function edit(next: PracticeDraftItem[]) {
    session.current = { ...session.current, editGeneration: session.current.editGeneration + 1, dirty: true, items: structuredClone(next) };
    setDirty(true); setItems(next); persist();
  }
  function changeConstraints(value: typeof constraints) {
    session.current = { ...session.current, editGeneration: session.current.editGeneration + 1, dirty: true, constraints: structuredClone(value) };
    setDirty(true); setConstraints(value); setSuggestions(null); persist();
  }
  async function suggest() {
    if (suggestBusy.current || baselineChoiceRequired) return;
    suggestBusy.current = true; setSuggesting(true); setSuggestionError(null); setNotice('');
    suggestAbort.current?.abort();
    const controller = new AbortController(); suggestAbort.current = controller;
    const token = ++suggestGeneration.current;
    const generation = session.current.editGeneration;
    try {
      const result = await services.suggestPractice(view.practiceSetId, { expectedRevision: session.current.serverRevision, constraints: structuredClone(session.current.constraints) }, controller.signal);
      if (!alive.current || token !== suggestGeneration.current) return;
      if (session.current.editGeneration !== generation) setNotice('约束或选题已变化，旧请求的建议未采用。请重新获取建议。');
      else { setSuggestions(result); setCandidateCache((previous) => ({ ...previous, ...Object.fromEntries(result.items.map((item) => [item.questionRevisionId, item])) })); }
    } catch (cause) { if (alive.current && token === suggestGeneration.current && !controller.signal.aborted) setSuggestionError(asApiError(cause)); }
    finally { if (alive.current && token === suggestGeneration.current) { suggestBusy.current = false; setSuggesting(false); } }
  }
  function acceptBaseline(result: PracticeSetView) {
    if (result.practiceSetId !== view.practiceSetId || result.revision < known.current.revision) {
      setNotice('原操作已收到回执；服务器已知版本或固定身份较新，本地输入与版本保持。'); return false;
    }
    if ((result.revision === known.current.revision && result.currentRevision.practiceRevisionId !== known.current.id) ||
      (result.revision === viewRef.current.revision && result.currentRevision.practiceRevisionId !== viewRef.current.currentRevision.practiceRevisionId)) {
      session.current.identityConflict = { revision: result.revision, knownRevisionId: known.current.id, receivedRevisionId: result.currentRevision.practiceRevisionId };
      setNotice('原操作回执固定身份冲突；输入和已知版本保持，新的写入暂停，请对照服务器固定修订。'); return false;
    }
    known.current = { revision: result.revision, id: result.currentRevision.practiceRevisionId, practiceSetId: result.practiceSetId };
    session.current = { ...session.current, serverRevision: result.revision, serverRevisionId: result.currentRevision.practiceRevisionId };
    setServerRevision(result.revision); return true;
  }
  async function saveDraft(): Promise<boolean> {
    if (saving.current || reviewing.current || session.current.reviewOperation || !cacheReady || cacheBlocked.current || (baselineChoiceRequired && save.phase !== 'unknown')) return false;
    const sendingIdentity = crypto.randomUUID(); saving.current = sendingIdentity;
    let explicitFailure = false;
    try {
      const receipt = await save.submitWithReceipt({ expectedRevision: session.current.serverRevision, items: session.current.items, constraints: session.current.constraints }, (frozen) => {
        session.current.saveOperation = frozen;
        if (!persist()) { explicitFailure = true; throw new ApiError('RECOVERY_CACHE_FAILED', '发送前无法保存原操作恢复包，请修复本机缓存后重试。', 503, true); }
        return services.patchPracticeDraft(view.practiceSetId, { ...frozen.payload, submissionId: frozen.submissionId }).catch((cause: unknown) => { if (asApiError(cause).status !== 0) explicitFailure = true; throw cause; });
      }, { contextKey, originalEditGeneration: session.current.editGeneration, loadGeneration: loadGeneration.current });
      if (!receipt) {
        if (!alive.current || currentContext.current !== contextKey) return false;
        // Unknown retains the synchronous operation cache; explicit errors can be edited and retried.
        if (explicitFailure) { session.current.saveOperation = null; persist(); }
        return false;
      }
      receivedOperations.current.push({ operationId: receipt.operation.operationId, practiceSetId: receipt.result.practiceSetId, revision: receipt.result.revision, revisionId: receipt.result.currentRevision.practiceRevisionId, current: receipt.current });
      if (!receipt.current || !alive.current || receipt.operation.metadata?.contextKey !== currentContext.current) return false;
      session.current.saveOperation = null;
      if (!acceptBaseline(receipt.result)) { persist(); return false; }
      if (receipt.operation.metadata.loadGeneration === loadGeneration.current && session.current.editGeneration === receipt.operation.metadata.originalEditGeneration) {
        session.current.items = structuredClone(receipt.result.currentRevision.draftItems); session.current.constraints = structuredClone(receipt.result.currentRevision.constraints); session.current.dirty = false;
        setItems(session.current.items); setConstraints(session.current.constraints); setDirty(false); setNotice('草稿已保存。审核需要另行确认。');
      } else setNotice('发送的草稿已保存；之后的编辑仍保留，尚未保存，请再次保存后审核。');
      persist(); onSaved(receipt.result); return !session.current.dirty;
    } finally { if (saving.current === sendingIdentity) saving.current = null; }
  }
  async function reviewDraft() {
    if (reviewing.current || saving.current || cacheBlocked.current || (baselineChoiceRequired && review.phase !== 'unknown')) return;
    const sendingIdentity = crypto.randomUUID(); reviewing.current = sendingIdentity;
    let explicitFailure = false;
    try {
      const receipt = await review.submitWithReceipt({ submissionId: '', expectedRevision: session.current.serverRevision }, (frozen) => {
        session.current.reviewOperation = frozen;
        if (!persist()) { explicitFailure = true; throw new ApiError('RECOVERY_CACHE_FAILED', '发送前无法保存审核恢复包。', 503, true); }
        return services.reviewPractice(view.practiceSetId, { ...frozen.payload, submissionId: frozen.submissionId }).catch((cause: unknown) => { if (asApiError(cause).status !== 0) explicitFailure = true; throw cause; });
      }, { contextKey, originalEditGeneration: session.current.editGeneration, loadGeneration: loadGeneration.current });
      if (receipt) receivedOperations.current.push({ operationId: receipt.operation.operationId, practiceSetId: receipt.result.practiceSetId, revision: receipt.result.revision, revisionId: receipt.result.currentRevision.practiceRevisionId, current: receipt.current });
      if (!receipt && explicitFailure && alive.current && currentContext.current === contextKey) { session.current.reviewOperation = null; persist(); }
      if (receipt?.current && alive.current && receipt.operation.metadata?.contextKey === currentContext.current) {
        session.current.reviewOperation = null;
        const accepted = acceptBaseline(receipt.result); persist();
        if (accepted) onSaved(receipt.result);
      }
    } finally { if (reviewing.current === sendingIdentity) reviewing.current = null; }
  }
  function adopt(suggestion: PracticeSuggestion) {
    const key = crypto.randomUUID();
    edit([...items, itemFromSuggestion(suggestion, key, items.length + 1)]);
  }

  return <section className="b4-section" aria-label="练习草稿编辑">
    <h2>选题与计分结构</h2><p className="b4-hint" title={`分析运行 ${view.currentRevision.analysisRunId} · 练习修订 ${view.currentRevision.practiceRevisionId}`}>来源报告 {nameOrShortId(view.currentRevision.sourcePaperTitle, view.currentRevision.analysisRunId)} · 编辑版本 {serverRevision} · {dirty ? '有未保存修改' : '当前草稿已保存'}。正式题建议不会自动写入练习。</p>
    {cacheError && <p className="space-banner error" role="alert">{cacheError}</p>}
    <p className="b4-hint">未保存稿按练习独立保留在本机；刷新、关闭或浏览器返回后可恢复，未知保存只重放原包。固定历史不覆盖恢复稿。</p>
    {view.revision > serverRevision && <div className="space-banner" role="alert">服务器已有编辑版本 {view.revision}，本地输入保留。<button className="space-button" disabled={pending || locked || identityConflict} onClick={() => { session.current.serverRevision = view.revision; session.current.serverRevisionId = view.currentRevision.practiceRevisionId; session.current.identityConflict = null; setServerRevision(view.revision); persist(); setNotice('已采用最新CAS版本；本地编辑仍保留，请核对后保存。'); }}>保留输入并采用最新版本</button></div>}
    {identityConflict && <div className="space-banner error" role="alert">固定身份冲突：同编辑版本的修订ID不同。输入和原CAS保留，新的保存、建议及审核暂停；请刷新服务器练习并对照，不能直接采用不一致身份。<p className="b4-meta">原固定修订 {session.current.serverRevisionId} · 读取修订 {view.currentRevision.practiceRevisionId}{session.current.identityConflict && ` · 冲突回执 ${session.current.identityConflict.receivedRevisionId}`}</p></div>}
    {baselineChoiceRequired && <details><summary>对照服务器固定修订与分值</summary><p className="b4-meta" title={`练习修订 ${view.currentRevision.practiceRevisionId}`}>服务器 r{view.revision} · {shortId(view.currentRevision.practiceRevisionId)} · 题量约束 {view.currentRevision.constraints.count}</p>{view.currentRevision.draftItems.map((item, index) => <p key={item.itemKey}>第{index + 1}题 · {item.questionRevisionId} · 整题 {item.maxScore}分；{item.itemStructure.nodes.map((node) => `${node.questionNo}：${node.maxScore ?? '不计分'}`).join('；')}</p>)}</details>}
    <ConstraintsFields value={constraints} onChange={changeConstraints} disabled={locked} />
    <div className="b4-actions"><button className="space-button" disabled={pending || locked || baselineChoiceRequired} onClick={() => void suggest()}>获取正式题建议</button><GuardedLink className="space-button" href={`/question-bank?returnPracticeSetId=${encodeURIComponent(view.practiceSetId)}#generation`}>缺题时手动补题并校对</GuardedLink></div>
    {suggesting && <p role="status">正在按明确约束查找正式题…</p>}<ErrorNotice error={suggestionError} />
    {suggestions && <section aria-label="正式题建议与缺口"><h3>正式题建议：{suggestions.selectedCount} / {suggestions.requestedCount}</h3>
      <p className="b4-hint">覆盖：{Object.entries(suggestions.coverage).map(([id, count]) => `${view.currentRevision.targetKnowledgePoints.find((p) => p.knowledgePointId === id)?.name ?? id} ${count}`).join('；') || '无覆盖'}</p>
      {suggestions.gaps.length > 0 ? <div className="space-banner" role="alert"><strong>仍有缺口</strong>{suggestions.gaps.map((gap, index) => <p key={index}>{gap}</p>)}<p>请调整明确约束或完成已有题库补题审核链，不会自动放宽或调用模型。</p></div> : <p>后端未报告缺口。</p>}
      {suggestions.items.map((suggestion) => <details key={suggestion.questionRevisionId}><summary>正式题 {suggestion.questionId} · {suggestion.reason}</summary><CandidateContent suggestion={suggestion} />
        <p className="b4-meta">固定题修订 {suggestion.questionRevisionId} · {suggestion.questionType ?? '题型未标注'} · {suggestion.difficulty ?? '难度未标注'} · {suggestion.answerState}</p>
        <p>{suggestion.knowledgePoints.map((p) => `${p.name}（${p.knowledgeRevisionId}）`).join('、')}</p>
        <button className="space-button" disabled={locked || pending || items.some((item) => item.questionRevisionId === suggestion.questionRevisionId)} onClick={() => adopt(suggestion)}>作为一计分叶加入，随后复核结构</button>
      </details>)}
    </section>}
    <details><summary>手动加入已知正式修订</summary><p className="b4-hint">只接受已确认题修订；请显式填写题面块、计分结构和正式知识点。保存时由后端核查，审核前完整审阅服务端题面。</p>
      <label className="b4-field">固定题修订ID<input aria-label="手动固定题修订" disabled={locked} value={manualRevisionId} onChange={(event) => setManualRevisionId(event.target.value)} /></label>
      <button className="space-button" disabled={locked || pending || !manualRevisionId.trim()} onClick={() => { const key = crypto.randomUUID(); edit([...items, { itemKey: key, questionRevisionId: manualRevisionId.trim(), ordinal: items.length + 1, itemStructure: { nodes: [{ nodeKey: `${key}-1`, parentNodeKey: null, questionNo: String(items.length + 1), ordinal: 1, isScored: true, maxScore: '1', knowledgePointIds: [], sourceBlockIds: [] }] }, maxScore: '1', selectedKnowledgePointIds: [] }]); setManualRevisionId(''); }}>加入并填写结构</button>
    </details>
    {items.length === 0 && <p>草稿还没有选题，请显式采用正式题建议。</p>}
    {items.map((item, index) => <DraftItemEditor key={item.itemKey} item={item} index={index} count={items.length} locked={locked}
      suggestion={candidateCache[item.questionRevisionId]}
      fixedContent={view.currentRevision.items.find((candidate) => candidate.itemKey === item.itemKey)?.content}
      onChange={(next) => edit(items.map((old, position) => position === index ? next : old))}
      onMove={(direction) => edit(moveItem(items, index, direction))}
      onRemove={() => edit(items.filter((_, position) => position !== index).map((old, position) => ({ ...old, ordinal: position + 1 })))} />)}
    {notice && <p role="status" className="b4-hint">{notice}</p>}
    <SubmissionNotice submission={save} /><SubmissionNotice submission={review} />
    <div className="b4-actions"><button className="space-button primary" disabled={!cacheReady || cacheBlocked.current || save.busy || review.busy || review.phase === 'unknown' || (baselineChoiceRequired && save.phase !== 'unknown')} onClick={() => void saveDraft()}>{save.phase === 'unknown' ? '重试原草稿保存' : '保存草稿'}</button>
      <button className="space-button primary" disabled={!cacheReady || cacheBlocked.current || pending || save.phase === 'unknown' || (review.phase !== 'unknown' && (dirty || items.length === 0 || baselineChoiceRequired))} onClick={() => void reviewDraft()}>{review.phase === 'unknown' ? '重试原审核提交' : '独立审核此草稿'}</button></div>
    <p className="b4-hint">保存不等于审核。审核固定题目、计分叶、材料、知识点及答案；审核后改动需要建立新草稿。</p>
  </section>;
}

function CandidateContent({ suggestion }: { suggestion: PracticeSuggestion }) {
  const loadAsset = useCallback((assetId: string, signal: AbortSignal) => getQuestionAsset('question', suggestion.questionId, assetId, signal), [suggestion.questionId]);
  return <RichReview content={suggestion.content} loadAsset={loadAsset} assetScope={`${suggestion.questionId}|${suggestion.questionRevisionId}`} />;
}

function DraftItemEditor({ item, index, count, locked, suggestion, fixedContent, onChange, onMove, onRemove }: {
  item: PracticeDraftItem; index: number; count: number; locked: boolean; suggestion?: PracticeSuggestion; fixedContent?: RichContentV2;
  onChange: (item: PracticeDraftItem) => void; onMove: (direction: -1 | 1) => void; onRemove: () => void;
}) {
  const content = suggestion?.content ?? fixedContent;
  const blockOptions = content ? surfaceBlocks(content) : [];
  const pointOptions = suggestion?.knowledgePoints;
  const updateNode = (position: number, patch: Partial<PracticeNode>) => onChange(withNode(item, position, patch));
  const splitIds = (text: string) => text.split(/[,，]/).map((value) => value.trim()).filter(Boolean);
  return <article className="b4-item" aria-label={`练习第${index + 1}题`}><h3>第{index + 1}题 · 固定修订 {item.questionRevisionId}</h3>
    <div className="b4-actions"><button className="space-button" disabled={locked || index === 0} onClick={() => onMove(-1)} aria-label={`第${index + 1}题上移`}>上移</button><button className="space-button" disabled={locked || index === count - 1} onClick={() => onMove(1)} aria-label={`第${index + 1}题下移`}>下移</button><button className="space-button" disabled={locked} onClick={onRemove} aria-label={`移除第${index + 1}题`}>移除</button></div>
    <fieldset disabled={locked}><div className="b4-fields"><label className="b4-field">整题满分（十进制文本）<input aria-label={`第${index + 1}题整题满分`} inputMode="decimal" value={item.maxScore} onChange={(event) => onChange({ ...item, maxScore: event.target.value })} /></label></div>
      <p className="b4-hint">整题满分须与计分叶合计一致；父题不计分。分值与结构由服务端核验，不分摊知识点得分。</p>
      {pointOptions ? <div className="b4-checks" aria-label={`第${index + 1}题知识点`}>{pointOptions.map((point) => <label key={point.knowledgePointId}><input type="checkbox" checked={item.selectedKnowledgePointIds.includes(point.knowledgePointId)} onChange={(event) => onChange({ ...item, selectedKnowledgePointIds: event.target.checked ? [...item.selectedKnowledgePointIds, point.knowledgePointId] : item.selectedKnowledgePointIds.filter((id) => id !== point.knowledgePointId) })} />{point.name}</label>)}</div>
        : <label className="b4-field">选定正式知识点ID（逗号分隔）<input aria-label={`第${index + 1}题知识点ID`} value={item.selectedKnowledgePointIds.join(',')} onChange={(event) => onChange({ ...item, selectedKnowledgePointIds: splitIds(event.target.value) })} /></label>}
      {item.itemStructure.nodes.map((node, position) => <div key={node.nodeKey} className="b4-node"><strong>结构节点 {position + 1}</strong><span className="b4-meta">{node.nodeKey}</span>
        <div className="b4-fields"><label className="b4-field">题号<input aria-label={`第${index + 1}题节点${position + 1}题号`} value={node.questionNo} onChange={(event) => updateNode(position, { questionNo: event.target.value })} /></label>
          <label className="b4-field">父节点<select className="space-select" aria-label={`第${index + 1}题节点${position + 1}父节点`} value={node.parentNodeKey ?? ''} onChange={(event) => updateNode(position, { parentNodeKey: event.target.value || null })}><option value="">顶层</option>{item.itemStructure.nodes.filter((candidate) => candidate.nodeKey !== node.nodeKey).map((candidate) => <option key={candidate.nodeKey} value={candidate.nodeKey}>{candidate.questionNo}</option>)}</select></label>
          <label className="b4-field">局部顺序<input type="number" min={1} aria-label={`第${index + 1}题节点${position + 1}顺序`} value={node.ordinal} onChange={(event) => updateNode(position, { ordinal: Number(event.target.value) })} /></label></div>
        <label><input type="checkbox" aria-label={`第${index + 1}题节点${position + 1}计分`} checked={node.isScored} onChange={(event) => updateNode(position, { isScored: event.target.checked, maxScore: event.target.checked ? node.maxScore ?? '1' : null })} />该节点是计分叶</label>
        {node.isScored && <div className="b4-fields"><label className="b4-field">计分叶满分<input aria-label={`第${index + 1}题节点${position + 1}满分`} inputMode="decimal" value={node.maxScore ?? ''} onChange={(event) => updateNode(position, { maxScore: event.target.value })} /></label><label className="b4-field">计分叶正式知识点ID<input aria-label={`第${index + 1}题节点${position + 1}知识点`} value={(node.knowledgePointIds ?? []).join(',')} onChange={(event) => updateNode(position, { knowledgePointIds: splitIds(event.target.value) })} /></label></div>}
        <p className="b4-hint">显式分配题面内容，保留父题与子题材料。</p>
        {blockOptions.length > 0 ? <div className="b4-checks">{blockOptions.map((block, blockIndex) => <label key={block.id}><input type="checkbox" checked={(node.sourceBlockIds ?? []).includes(block.id)} aria-label={`第${index + 1}题节点${position + 1}题面块${blockIndex + 1}`} onChange={(event) => updateNode(position, { sourceBlockIds: event.target.checked ? [...(node.sourceBlockIds ?? []), block.id] : (node.sourceBlockIds ?? []).filter((id) => id !== block.id) })} />内容{blockIndex + 1} · {block.kind === 'paragraph' ? block.text.slice(0, 35) : ({ table: '表格', formula: '公式', image: '图片' })[block.kind]}</label>)}</div>
          : <label className="b4-field">固定题面块ID（逗号分隔）<input aria-label={`第${index + 1}题节点${position + 1}题面块ID`} value={(node.sourceBlockIds ?? []).join(',')} onChange={(event) => updateNode(position, { sourceBlockIds: splitIds(event.target.value) })} /></label>}
        <button className="space-button" disabled={item.itemStructure.nodes.some((child) => child.parentNodeKey === node.nodeKey)} onClick={() => onChange({ ...item, itemStructure: { nodes: item.itemStructure.nodes.filter((_, nodeIndex) => nodeIndex !== position) } })}>移除此节点</button>
      </div>)}
      <button className="space-button" onClick={() => onChange({ ...item, itemStructure: { nodes: [...item.itemStructure.nodes, { nodeKey: crypto.randomUUID(), parentNodeKey: null, questionNo: `${index + 1}(${item.itemStructure.nodes.length + 1})`, ordinal: item.itemStructure.nodes.length + 1, isScored: true, maxScore: '1', knowledgePointIds: [...item.selectedKnowledgePointIds], sourceBlockIds: [] }] } })}>新增结构节点 / 子题</button>
    </fieldset>
  </article>;
}
