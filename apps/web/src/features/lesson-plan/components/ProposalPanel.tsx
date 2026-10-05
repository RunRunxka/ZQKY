'use client';
import { useEffect, useRef, useState } from 'react';
import { allowedLessonFields, type AllowedLessonField, type LessonApplyRequest, type LessonGenerateRequest, type LessonGenerationReceipt, type LessonProposalView, type LessonRejectRequest, type LessonView } from '@/contracts/lesson-plans';
import { useObservedJob } from '@/services/use-workflow-job';
import { asApiError, stablePayloadKey, type FrozenSubmission } from '@/features/assessments/hooks';
import { useLessonEditor } from '../model/EditorContext';
import { useLessonDocument } from '../model/DocumentContext';
import { useLessonOperation } from '../model/useLessonOperation';
import { validateOperation, type LessonOperationKind } from '../model/server-cache';
import type { GenerationInputs } from './SourcePanel';

type GenerateContent = Omit<LessonGenerateRequest, 'submissionId'>;
type GenerationRecord = { operation: FrozenSubmission<GenerateContent>; selectionKey: string; sourceEpoch: number | null; receipt: LessonGenerationReceipt | null };
type ApplyContent = Omit<LessonApplyRequest, 'submissionId'> & { proposalId: string };
type RejectContent = Omit<LessonRejectRequest, 'submissionId'> & { proposalId: string };
const labels: Record<AllowedLessonField, string> = { coreCompetencies: '核心素养', keyPoints: '教学重点', teachingDesign: '教学设计', process: '教学过程（整段）', exercises: '针对练习' };
const jobLabels = { queued: '已排队', running: '生成中', succeeded: '生成成功，待选择', failed: '生成失败', cancelled: '已取消', interrupted: '生成中断' };
const proposalLabels = { pending: '待选择', applied: '已采用所选字段，该候选已终结', rejected: '已拒绝', stale: '已过期' };
export function ProposalPanel({ inputs }: { inputs: GenerationInputs }) {
  const doc = useLessonDocument(), editor = useLessonEditor(), server = editor.server!;
  const alive = useRef(true), requestEpoch = useRef(0);
  const [proposal, setProposal] = useState<LessonProposalView | null>(null), [selected, setSelected] = useState<AllowedLessonField[]>([]), [error, setError] = useState('');
  const generation = useRef<GenerationRecord | null>(null);
  const firstGenerationIntent = useRef<{ selectionKey: string; sourceEpoch: number } | null>(null);
  const proposalGeneration = useRef<{ proposalId: string; identity: GenerationRecord } | null>(null);
  const [restored, setRestored] = useState(false);
  const [preparing, setPreparing] = useState(false);
  const setCandidateId = doc.setCandidateId;
  useEffect(() => { setCandidateId(proposal?.proposalId ?? null); }, [proposal, setCandidateId]);
  const inputKey = stablePayloadKey({ selection: doc.selection, inputs });
  const currentInputKey = useRef(inputKey); currentInputKey.current = inputKey;
  const inputEpoch = useRef({ key: inputKey, value: 0 });
  if (inputEpoch.current.key !== inputKey) inputEpoch.current = { key: inputKey, value: inputEpoch.current.value + 1 };
  const currentSession = useRef({ documentId: doc.documentId, loadGeneration: server.loadGeneration }); currentSession.current = { documentId: doc.documentId, loadGeneration: server.loadGeneration };
  const key = `zhiqikeyuan:lesson-plan:generation:v1:${encodeURIComponent(doc.documentId!)}`;
  function persistGenerationRecord() {
    const record = generation.current;
    if (!record) throw new Error('缺少可信首次生成来源签名，原字节保持');
    const storage = doc.services.recoveryStorage ?? localStorage, raw = storage.getItem(key);
    if (raw !== null) {
      const old = JSON.parse(raw);
      if (old.schemaVersion !== 1 || typeof old.selectionKey !== 'string' || (old.sourceEpoch != null && (!Number.isSafeInteger(old.sourceEpoch) || old.sourceEpoch < 0))) throw new Error('原生成观察缓存无法可信读取');
      validateOperation(old.operation, `lesson|${doc.documentId}|generate`);
    }
    const envelope = { schemaVersion: 1, ...record };
    try {
      storage.setItem(key, JSON.stringify(envelope));
      if (stablePayloadKey(JSON.parse(storage.getItem(key)!)) !== stablePayloadKey(envelope)) throw new Error('首次生成来源签名写后核验失败');
    } catch (cause) { throw new Error(`${record.receipt ? '明确生成回执缓存写入失败' : '首次生成来源签名写入失败'}：${(cause as Error).message}`); }
  }
  const recovery = (kind: LessonOperationKind) => ({
    ready: server.ready && !!server.cache, read: () => server.cache?.operations[kind] ?? null,
    prepare(operation: FrozenSubmission<unknown>) {
      if (kind !== 'generate') return;
      if (generation.current?.operation.operationId === operation.operationId) {
        if (stablePayloadKey(generation.current.operation) !== stablePayloadKey(operation)) throw new Error('原生成操作身份不一致');
        return;
      }
      const intent = firstGenerationIntent.current;
      if (!intent) throw new Error('缺少可信首次生成来源签名');
      generation.current = { operation: structuredClone(operation) as FrozenSubmission<GenerateContent>, ...intent, receipt: null };
    },
    write(operation: FrozenSubmission<unknown> | null) {
      if (kind === 'generate' && operation === null && generation.current) persistGenerationRecord();
      server.setOperation(kind, operation);
      if (kind === 'generate' && operation) persistGenerationRecord();
    },
    verifyWrite: () => server.retryRecoveryWrite(),
  });
  const generate = useLessonOperation<GenerateContent, LessonGenerationReceipt>(`lesson|${doc.documentId}|generate`, recovery('generate'));
  const apply = useLessonOperation<ApplyContent, LessonView>(`lesson|${doc.documentId}|apply`, recovery('apply'));
  const reject = useLessonOperation<RejectContent, LessonProposalView>(`lesson|${doc.documentId}|reject`, recovery('reject'));
  const job = useObservedJob('teaching', { onTerminal(view) {
    if (!alive.current || view.state !== 'succeeded') return;
    const active = generation.current;
    if (!active?.receipt || active.receipt.job.jobId !== view.jobId) return;
    const id = view.result?.proposalId;
    if (view.result?.lessonPlanId !== doc.documentId || typeof id !== 'string' || !id) { setError('任务结果缺少当前文档的固定候选身份'); return; }
    const epoch = ++requestEpoch.current;
    void doc.api.getLessonProposal(doc.documentId!, id).then((next) => { if (alive.current && epoch === requestEpoch.current && generation.current?.operation.operationId === active.operation.operationId && generation.current.receipt?.job.jobId === view.jobId && next.jobId === view.jobId && next.lessonPlanId === doc.documentId && next.proposalId === id) { proposalGeneration.current = { proposalId: next.proposalId, identity: structuredClone(active) }; setProposal(next); setSelected([]); } }).catch((cause) => { if (alive.current && epoch === requestEpoch.current) setError(asApiError(cause).message); });
  } });
  const adopt = job.adopt;
  useEffect(() => { alive.current = true; return () => { alive.current = false; requestEpoch.current += 1; }; }, []);
  useEffect(() => {
    if (!server.ready || !server.cache) return;
    try { const raw = (doc.services.recoveryStorage ?? localStorage).getItem(key);
      if (raw !== null) { const value = JSON.parse(raw); if (value.schemaVersion !== 1 || typeof value.selectionKey !== 'string' || (value.sourceEpoch != null && (!Number.isSafeInteger(value.sourceEpoch) || value.sourceEpoch < 0)) || (value.receipt !== null && (!value.receipt?.job || value.receipt.lessonPlanId !== doc.documentId))) throw new Error('生成观察恢复记录不合法'); validateOperation(value.operation, `lesson|${doc.documentId}|generate`); generation.current = { operation: value.operation, selectionKey: value.selectionKey, sourceEpoch: value.sourceEpoch ?? null, receipt: value.receipt }; if (value.receipt) adopt(value.receipt.job); }
      if (server.cache.operations.generate && (!generation.current || stablePayloadKey(generation.current.operation) !== stablePayloadKey(server.cache.operations.generate))) throw new Error('原生成操作缺少同一完整首次来源身份，原字节保持；生成发送暂停');
      setRestored(true);
    } catch (cause) { setRestored(false); setError(`生成观察恢复读取失败：${(cause as Error).message}。原字节保持，生成暂停。`); }
  }, [server.ready, key, doc.documentId, doc.services.recoveryStorage, adopt, server.cache]);
  const busy = preparing || generate.busy || apply.busy || reject.busy;
  const recoveryBlocked = generate.recoveryBlocked || apply.recoveryBlocked || reject.recoveryBlocked;
  const setAuxiliaryBusy = server.setAuxiliaryBusy;
  useEffect(() => { setAuxiliaryBusy(busy); return () => setAuxiliaryBusy(false); }, [busy, setAuxiliaryBusy]);
  const identity = proposalGeneration.current?.proposalId === proposal?.proposalId ? proposalGeneration.current?.identity : null;
  const original = identity?.operation.metadata;
  const stale = proposal?.state === 'pending' && (!identity || identity.receipt?.job.jobId !== proposal.jobId || identity.sourceEpoch !== inputEpoch.current.value || identity.selectionKey !== inputKey || original?.loadGeneration !== server.loadGeneration || original?.originalEditGeneration !== editor.revision || proposal.baseRevisionId !== server.cache?.serverRevisionId);
  async function start() {
    setError('');
    try {
       if (busy || recoveryBlocked || !restored || server.syncState === 'conflict' || (server.unknown && generate.state !== 'unknown')) return;
      const originalOperation = generate.state === 'unknown' ? generate.pending : null;
      const captured = { selection: structuredClone(doc.selection), inputs: structuredClone(inputs), selectionKey: currentInputKey.current, sourceEpoch: inputEpoch.current.value, editRevision: editor.store.getState().revision, loadGeneration: server.loadGeneration, documentId: doc.documentId };
      let payload = originalOperation?.payload;
      if (!payload) {
        if (!captured.selection.context || !captured.selection.classId || !captured.inputs.classReady || !captured.inputs.evidence || !captured.inputs.evidence.evidenceRefs.length || !captured.inputs.modelProfileId || !Number.isSafeInteger(captured.inputs.durationMinutes) || captured.inputs.durationMinutes < 5 || captured.inputs.durationMinutes > 180) throw new Error('请先明确单一班级、ready 固定报告、知识点、核验教材和模型，并填写5–180分钟时长');
        setPreparing(true);
        let flushFailure: unknown;
        try { await server.flush(); } catch (cause) { flushFailure = cause; }
        if (!alive.current) return;
        if (currentSession.current.documentId !== captured.documentId || currentSession.current.loadGeneration !== captured.loadGeneration) throw new Error('保存等待期间文档加载身份发生变化；本次生成已取消，请重新检查当前文档。');
        if (inputEpoch.current.value !== captured.sourceEpoch || currentInputKey.current !== captured.selectionKey || editor.store.getState().revision !== captured.editRevision) throw new Error('保存等待期间正文、来源或模型发生变化；本次生成已取消，请检查当前选择后重新点击。');
        if (flushFailure) throw flushFailure;
        const baseline = server.cache!;
        payload = { baseRevisionId: baseline.serverRevisionId, baseServerRevision: baseline.serverRevision, ...captured.selection.context, classId: captured.selection.classId, requirements: captured.inputs.requirements, durationMinutes: captured.inputs.durationMinutes, modelProfileId: captured.inputs.modelProfileId, scopeSnapshot: captured.inputs.evidence.scopeSnapshot, evidenceRefs: captured.inputs.evidence.evidenceRefs, questionRevisionIds: captured.inputs.questionRevisionIds, practiceRevisionIds: captured.inputs.practiceRevisionIds };
      } else if (!generation.current || stablePayloadKey(generation.current.operation) !== stablePayloadKey(originalOperation)) {
        throw new Error('原生成操作的首次来源签名不完整，发送暂停；原恢复包保持。');
      }
       if (!originalOperation) firstGenerationIntent.current = { selectionKey: captured.selectionKey, sourceEpoch: captured.sourceEpoch };
       const receipt = await generate.run(payload, async (operation) => {
        const first = generation.current?.operation.operationId === operation.operationId ? generation.current : null;
        const selectionKey = first?.selectionKey ?? captured.selectionKey;
        const sourceEpoch = first ? first.sourceEpoch : captured.sourceEpoch;
        requestEpoch.current += 1;
         generation.current = { operation, selectionKey, sourceEpoch, receipt: null };
         const result = await doc.api.generateLessonProposal(captured.documentId!, { ...operation.payload, submissionId: operation.submissionId });
         generation.current = { operation, selectionKey, sourceEpoch, receipt: result }; return result;
      }, captured.editRevision, captured.loadGeneration);
      if (receipt?.current && alive.current) { proposalGeneration.current = null; setProposal(null); setSelected([]); job.adopt(receipt.result.job); }
    } catch (cause) { if (alive.current) setError(asApiError(cause).message); }
    finally { if (alive.current) setPreparing(false); }
  }
  async function decide(kind: 'apply' | 'reject') {
    setError('');
    try {
       if (busy || recoveryBlocked || (server.unknown && (kind === 'apply' ? apply.state : reject.state) !== 'unknown')) return;
      if (kind === 'apply') {
        const payload = apply.pending?.payload ?? (() => { if (!proposal || stale || proposal.state !== 'pending' || !selected.length || server.dirty || server.syncState === 'conflict') throw new Error('候选已过期、正文未保存或没有选择完整字段，未采用'); return { proposalId: proposal.proposalId, expectedRevision: server.cache!.serverRevision, baseRevisionId: proposal.baseRevisionId, selectedFields: selected }; })();
        server.setExclusive(true);
        const receipt = await apply.run(payload, (operation) => { const { proposalId, ...body } = operation.payload; return doc.api.applyLessonProposal(doc.documentId!, proposalId, { ...body, submissionId: operation.submissionId }); }, editor.revision, server.loadGeneration);
        if (receipt?.current && alive.current) { server.acknowledgeApplied(receipt.result, receipt.operation); setProposal((old) => old ? { ...old, state: 'applied', selectedFields: receipt.operation.payload.selectedFields, acceptedRevisionId: receipt.result.currentRevisionId } : null); }
      } else {
        const payload = reject.pending?.payload ?? { proposalId: proposal!.proposalId };
        const receipt = await reject.run(payload, (operation) => doc.api.rejectLessonProposal(doc.documentId!, operation.payload.proposalId, { submissionId: operation.submissionId }), editor.revision, server.loadGeneration);
        if (receipt?.current && alive.current) setProposal(receipt.result);
      }
      if ((kind === 'apply' ? apply : reject).lastFailure()?.status === 409) { await server.refreshLatest(); if (alive.current) setProposal((old) => old?.state === 'pending' ? { ...old, state: 'stale' } : old); }
    } catch (cause) { if (alive.current) setError(asApiError(cause).message); }
    finally { server.setExclusive(false); }
  }
  return <details className="lesson-server-panel"><summary>学情驱动 AI 候选与逐字段差异</summary><div className="lesson-panel-body">
    <button className="button primary" disabled={busy || recoveryBlocked || !restored || server.syncState === 'conflict' || (server.unknown && generate.state !== 'unknown')} onClick={() => void start()}>{generate.state === 'unknown' ? '重试原生成包' : '保存当前稿并生成 AI 候选'}</button>
    {generate.canRetryRecovery && <button className="button primary" disabled={busy || server.busy || server.exclusive} onClick={() => void generate.retryRecoveryWrite()}>重试生成操作恢复缓存</button>}
    {apply.canRetryRecovery && <button className="button primary" disabled={busy || server.busy || server.exclusive} onClick={() => void apply.retryRecoveryWrite()}>重试采用操作恢复缓存</button>}
    {reject.canRetryRecovery && <button className="button subtle" disabled={busy || server.busy || server.exclusive} onClick={() => void reject.retryRecoveryWrite()}>重试拒绝操作恢复缓存</button>}
    {job.view && <p role="status">任务：{jobLabels[job.view.state]} · 尝试 {job.view.attempt} · {job.view.jobId}</p>}
    {(job.view?.state === 'failed' || job.view?.state === 'interrupted' || job.view?.state === 'cancelled') && <button className="button subtle" disabled={!!job.pending} onClick={job.retry}>显式重试生成任务</button>}
    {(job.view?.state === 'queued' || job.view?.state === 'running') && <button className="button subtle" disabled={!!job.pending} onClick={job.cancel}>取消生成任务</button>}
    {(error || generate.cacheError || apply.cacheError || reject.cacheError || generate.error || apply.error || reject.error || job.actionError || job.observationNotice) && <p role="alert">{error || generate.cacheError || apply.cacheError || reject.cacheError || generate.error?.message || apply.error?.message || reject.error?.message || job.actionError?.message || job.observationNotice}</p>}
    {apply.state === 'unknown' && <button className="button primary" disabled={busy || recoveryBlocked} onClick={() => void decide('apply')}>重试原采用包</button>}{reject.state === 'unknown' && <button className="button subtle" disabled={busy || recoveryBlocked} onClick={() => void decide('reject')}>重试原拒绝包</button>}
    {proposal && <><p role="status">固定候选 {proposal.proposalId} · {stale ? '已过期：编辑或来源发生变化' : proposalLabels[proposal.state]} · 基于 {proposal.baseRevisionId}</p><p>预算 {proposal.budget.durationMinutes} 分钟；各环节合计 {proposal.budget.stages.reduce((sum, stage) => sum + stage.minutes, 0)} 分钟</p>
      {allowedLessonFields.filter((field) => proposal.patch[field] !== null).map((field) => <section className="lesson-field-diff" key={field}><label className="lesson-check"><input type="checkbox" aria-label={`采用${labels[field]}`} disabled={busy || stale || proposal.state !== 'pending'} checked={selected.includes(field)} onChange={(event) => setSelected(event.target.checked ? [...selected, field] : selected.filter((name) => name !== field))} />{labels[field]}（完整字段）</label><div className="lesson-diff-columns"><div><strong>当前正文</strong><pre>{field === 'process' ? JSON.stringify(editor.data.process, null, 2) : editor.data[field]}</pre></div><div><strong>AI 候选</strong><pre>{field === 'process' ? JSON.stringify(proposal.patch.process, null, 2) : proposal.patch[field]}</pre></div></div></section>)}
      <details><summary>固定来源、依据与时长</summary><p>学情 {proposal.generationSource.analysis.analysisRunId} · 成绩 {proposal.generationSource.analysis.scoreRevisionId} · 原卷 {proposal.generationSource.analysis.paperRevisionId} · 班级 {proposal.generationSource.classId} · 模型 {proposal.generationSource.modelProfileId}</p><small>固定输入 {proposal.inputHash} · 模型指纹 {proposal.modelFingerprint} · 教材范围 {proposal.generationSource.scopeSnapshot.scopeHash}</small>{proposal.generationSource.selectedKnowledgePoints.map((point) => <p key={point.knowledgePointId}>{point.name} · {point.knowledgeRevisionId}</p>)}{proposal.budget.stages.map((stage) => <p key={stage.processId}>{stage.phase} · {stage.minutes}分钟 · {stage.activity} · 检查：{stage.check} · 依据 {stage.evidenceAliases.join(', ')}</p>)}{proposal.evidence.map((item) => <details key={item.alias}><summary>{item.alias} · {item.kind} · {item.title} · {item.referenceId}</summary><pre>{item.text}</pre><small>{item.sha256}</small></details>)}</details>
      <div className="lesson-actions"><button className="button primary" disabled={busy || recoveryBlocked || stale || !selected.length || server.dirty || proposal.state !== 'pending' || server.syncState === 'conflict'} onClick={() => void decide('apply')}>仅采用所选完整字段</button><button className="button subtle" disabled={busy || recoveryBlocked || proposal.state === 'applied' || proposal.state === 'rejected'} onClick={() => void decide('reject')}>明确拒绝候选</button></div></>}
  </div></details>;
}
