'use client';

import { Fragment, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useEntrance } from '@/components/motion/useEntrance';
import Link from 'next/link';
import type { AnalysisCreateRequest, AnalysisReceipt, AnalysisRunView, EvidenceRow, NoteRequest, NoteView } from '@/contracts/b4';
import type { RichContentV2 } from '@/contracts/teaching-loop';
import { b4Api } from '@/services/teaching-loop-b4-api';
import { ApiError } from '@/services/api-client';
import { getAssessment, getPaperAsset, getScoreRevision, listAssessments, listClasses, listScoreRevisions } from '@/services/assessments-api';
import { asApiError, useAsyncResource, useFrozenSubmission } from '@/features/assessments/hooks';
import { useObservedJob } from '@/services/use-workflow-job';
import { CreatePracticeForm } from '@/features/practices/CreatePracticeForm';
import { ErrorNotice, ReadNotice, SubmissionNotice, Pagination, JobStatus, RichReview, isRichContent, observationLabel, statusLabel, attendanceLabel, scoreText, classDisplay, shortId, stampText } from './ui';
import '@/components/layout/space.css';
import './styles.css';

export interface LearningAnalysisWorkspaceProps {
  initialAssessmentId?: string | null;
  initialScoreRevisionId?: string | null;
  initialRunId?: string | null;
  services?: typeof b4Api;
}

/**
 * 固定报告的展示名（名称优先）：原卷标题 + 报告创建时间；
 * 标题缺失不猜造，两者都缺失才回落 `runId` 短号。
 */
function reportLabel(run: { paperTitle?: string | null; createdAt?: string | null; runId: string }): string {
  const title = typeof run.paperTitle === 'string' ? run.paperTitle.trim() : '';
  const stamp = run.createdAt ? stampText(run.createdAt) : '';
  if (title && stamp) return `${title} · ${stamp}`;
  if (title) return title;
  return stamp || shortId(run.runId);
}

export function LearningAnalysisWorkspace({ initialAssessmentId = null, initialScoreRevisionId = null, initialRunId = null, services = b4Api }: LearningAnalysisWorkspaceProps) {
  const pageRef = useRef<HTMLDivElement>(null);
  useEntrance(pageRef, { preset: 'page' });
  const [assessmentId, setAssessmentId] = useState(initialAssessmentId ?? '');
  const [revisionId, setRevisionId] = useState(initialScoreRevisionId ?? '');
  const [participantIds, setParticipantIds] = useState<string[]>([]);
  const [runId, setRunId] = useState(initialRunId);
  const [runsOffset, setRunsOffset] = useState(0);
  /** 报告列表归档筛选：默认只看未归档；打开后不传 archived（全部）。 */
  const [showArchived, setShowArchived] = useState(false);
  /** 二次确认的归档/恢复目标；确认前不发任何写请求。`label` = 原卷标题 + 时间（名称优先，不用 runId）。 */
  const [archiveTarget, setArchiveTarget] = useState<{ runId: string; archived: boolean; label: string } | null>(null);
  const [archiveBusy, setArchiveBusy] = useState(false);
  const [archiveError, setArchiveError] = useState<ApiError | null>(null);
  const [archiveNotice, setArchiveNotice] = useState('');
  const archiveBusyRef = useRef(false);
  const archiveAlive = useRef(true);
  const [assessmentOffset, setAssessmentOffset] = useState(0);
  const [childLocked, setChildLocked] = useState(false);
  const create = useFrozenSubmission<{ assessmentId: string; body: AnalysisCreateRequest }, AnalysisReceipt>();
  const locked = create.busy || create.phase === 'unknown' || childLocked;
  const assessments = useAsyncResource((signal) => listAssessments({ offset: assessmentOffset, limit: 50 }, signal), `analysis-assessments|${assessmentOffset}`);
  const revisions = useAsyncResource((signal) => assessmentId ? listScoreRevisions(assessmentId, signal) : Promise.resolve(null), `analysis-revisions|${assessmentId}`);
  const revision = useAsyncResource((signal) => revisionId ? getScoreRevision(revisionId, signal) : Promise.resolve(null), `analysis-source|${revisionId}`);
  /**
   * 班名只读映射（仅供展示）：固定成绩快照只冻结 `classId`、不含班名，
   * 展示名按 `classes` 实时映射；映射不到或读取失败才回落短号并注明原因，不伪造名称、不把失败当空名单。
   */
  const classDirectory = useAsyncResource((signal) => listClasses({ limit: 200 }, signal), 'analysis-class-directory');
  const classNames = useMemo(() => new Map((classDirectory.lastData?.items ?? []).map((item) => [item.id, item.name] as const)), [classDirectory.lastData]);
  const classNoteFallback = classDirectory.state.phase === 'failed' ? '班名读取失败，显示短号' : '该成绩未记录班名';
  const runs = useAsyncResource((signal) => services.listAnalysisRuns({ assessmentId: assessmentId || undefined, scoreRevisionId: revisionId || undefined, offset: runsOffset, limit: 20, ...(showArchived ? {} : { archived: false }) }, signal), `analysis-runs|${assessmentId}|${revisionId}|${runsOffset}|${showArchived ? 'all' : 'active'}`);
  const reloadRuns = runs.reload;
  const source = revision.lastData;
  const validSource = source?.assessmentId === assessmentId && source.state === 'confirmed' && !!source.paperRevisionId;
  const sourceReady = validSource && revision.state.phase === 'ready';

  useEffect(() => { archiveAlive.current = true; return () => { archiveAlive.current = false; }; }, []);

  async function createRun() {
    const result = await create.submit({ assessmentId, body: { submissionId: '', scoreRevisionId: revisionId, selectedParticipantIds: participantIds, ruleCode: 'any_loss_v1' } },
      async (frozen) => {
        const receipt = await services.createAnalysisRun(frozen.payload.assessmentId, { ...frozen.payload.body, submissionId: frozen.submissionId });
        if (receipt.scoreRevisionId !== frozen.payload.body.scoreRevisionId || receipt.job.domain !== 'teaching' || receipt.job.kind !== 'analysis') throw new ApiError('ANALYSIS_IDENTITY_MISMATCH', '分析收据与固定成绩身份不一致。', 500, false);
        return receipt;
      });
    if (result) { setRunId(result.runId); runs.reload(); }
  }

  /**
   * 归档/恢复一份固定报告：归档只写 archivedAt，报告与快照一概不动。
   * 失败保留原目标与提示，不伪装成功；结果未知时重按确认即重发同一请求（后端幂等）。
   * 回执提示按名称优先用「原卷标题 + 时间」，不用 runId。
   */
  async function changeArchive(target: { runId: string; archived: boolean; label: string }) {
    if (archiveBusyRef.current) return;
    archiveBusyRef.current = true;
    setArchiveBusy(true); setArchiveError(null); setArchiveNotice('');
    try {
      const result = target.archived ? await services.archiveAnalysisRun(target.runId) : await services.restoreAnalysisRun(target.runId);
      if (!archiveAlive.current) return;
      if (result.runId !== target.runId) throw new ApiError('ANALYSIS_ARCHIVE_IDENTITY_MISMATCH', '归档回执与目标报告不一致，未刷新列表。', 500, false);
      setArchiveTarget(null);
      setArchiveNotice(target.archived ? `已归档报告「${target.label}」：列表入口隐藏，报告与快照保留且仍可查看。` : `已恢复报告「${target.label}」：重新出现在未归档列表。`);
      reloadRuns();
    } catch (cause) {
      if (archiveAlive.current) setArchiveError(asApiError(cause));
    } finally { archiveBusyRef.current = false; if (archiveAlive.current) setArchiveBusy(false); }
  }

  return <div ref={pageRef} className="space-page learning-analysis-page">
    <header className="space-header" data-motion-reveal><h1>学情分析</h1><p className="space-description">从一次已确认成绩中核对本次需巩固依据，形成针对练习。报告依据固定版本，不计算长期掌握概率。</p></header>
    <main className="space-content">
      <section className="b4-section" aria-label="固定成绩与人次选择" data-motion-reveal>
        <h2>选择固定成绩与参测人次</h2>
        <ReadNotice resource={assessments} label="施测列表" />
        <div className="b4-fields"><label className="b4-field">施测<select className="space-select" aria-label="分析施测" disabled={locked} value={assessmentId} onChange={(event) => { setAssessmentId(event.target.value); setRevisionId(''); setParticipantIds([]); setRunsOffset(0); }}>
          <option value="">明确选择一次施测</option>
          {assessmentId && !assessments.lastData?.items.some((item) => item.assessmentId === assessmentId) && <option value={assessmentId}>{assessmentId}</option>}
          {assessments.lastData?.items.map((item) => <option key={item.assessmentId} value={item.assessmentId}>{item.title} · {item.heldOn}</option>)}
        </select></label>
          <label className="b4-field">固定成绩修订<select className="space-select" aria-label="分析成绩修订" disabled={locked || !assessmentId} value={revisionId} onChange={(event) => { setRevisionId(event.target.value); setParticipantIds([]); setRunsOffset(0); }}>
            <option value="">明确选择历史成绩版本</option>
            {revisionId && !revisions.lastData?.items.some((item) => item.revisionId === revisionId) && <option value={revisionId}>{revisionId}</option>}
            {revisions.lastData?.items.filter((item) => item.state === 'confirmed').map((item) => <option key={item.revisionId} value={item.revisionId}>v{item.version} · {item.revisionId}</option>)}
          </select></label></div>
        {assessments.lastData && <div className="b4-actions"><button className="space-button" disabled={locked || assessmentOffset === 0} onClick={() => setAssessmentOffset((n) => Math.max(0, n - 50))}>上一页施测</button><button className="space-button" disabled={locked || assessmentOffset + 50 >= assessments.lastData.total} onClick={() => setAssessmentOffset((n) => n + 50)}>下一页施测</button></div>}
        {assessmentId && <ReadNotice resource={revisions} label="成绩历史" />}
        {revisionId && <ReadNotice resource={revision} label="固定成绩" />}
        {source && !validSource && <p className="space-banner error" role="alert">该修订不属于所选施测、尚未确认或缺少固定原卷身份。请核对入口，不会改用当前生效成绩。</p>}
        {sourceReady && <>
          <p className="b4-chain" title={source.paperRevisionId ? `成绩修订 ${source.revisionId} · 原卷修订 ${source.paperRevisionId}` : `成绩修订 ${source.revisionId}`}>成绩 v{source.version} · {shortId(source.revisionId)} → 原卷 {shortId(source.paperRevisionId)}</p>
          <p className="b4-hint">每名学生至多选择一个人次；补考必须明确选择对应人次。缺考、免考不会补成0分。</p>
          <fieldset disabled={locked}><legend>明确选择参测人次</legend><div className="b4-checks">
            {(source.participantSnapshot ?? []).map((participant) => { const display = classDisplay(classNames.get(participant.classId) ?? null, participant.classId, classNoteFallback); return <label key={participant.participantId}>
              <input aria-label={`分析人次 ${participant.name} ${participant.attemptNo}`} type="checkbox" checked={participantIds.includes(participant.participantId)} onChange={(event) => setParticipantIds((previous) => event.target.checked
                ? [...previous.filter((id) => !(source.participantSnapshot ?? []).some((candidate) => candidate.participantId === id && candidate.studentId === participant.studentId)), participant.participantId]
                : previous.filter((id) => id !== participant.participantId))} />
              <span>{participant.name} · 人次{participant.attemptNo} · {attendanceLabel[participant.attendance]}<small className="b4-meta">学号 {participant.studentNo ?? '未记录'} · 班级 {display.label} · {display.meta}</small></span>
            </label>; })}
          </div></fieldset>
          {(source.participantSnapshot ?? []).length === 0 && <p role="alert">这份固定成绩没有参测快照，不能创建分析。</p>}
        </>}
        <p className="b4-hint">规则：任一关联小题有效得分低于满分，标为“本次需巩固”（any_loss_v1）。综合题具体错因仍由教师确认。</p>
        <SubmissionNotice submission={create} />
        <button className="space-button primary" disabled={create.busy || childLocked || (create.phase !== 'unknown' && (!sourceReady || participantIds.length === 0))} onClick={() => void createRun()}>{create.phase === 'unknown' ? '重试原分析提交' : '创建本次报告'}</button>
      </section>

      <section className="b4-section" aria-label="固定报告历史" data-motion-reveal><h2>固定报告历史</h2><ReadNotice resource={runs} label="报告列表" />
        <label><input type="checkbox" aria-label="显示已归档" checked={showArchived} disabled={locked} onChange={(event) => { setShowArchived(event.target.checked); setRunsOffset(0); setArchiveTarget(null); setArchiveError(null); setArchiveNotice(''); }} />显示已归档</label>
        <p className="b4-hint">{showArchived ? '当前不筛选归档状态：同时列出未归档与已归档报告，便于核对与恢复。' : '当前只看未归档报告；已归档报告不出现在这里，可用上方开关查看。'}</p>
        {archiveNotice && <p className="b4-hint" role="status">{archiveNotice}</p>}
        <ErrorNotice error={archiveError} />
        {archiveError && <button className="space-button" onClick={reloadRuns}>刷新列表对照服务器</button>}
        {runs.state.phase === 'ready' && runs.lastData?.items.length === 0 && <p>此来源还没有分析报告。</p>}
        <div className="b4-list">{runs.lastData?.items.map((item) => <Fragment key={item.runId}>
          <button className={`space-button${runId === item.runId ? ' primary' : ''}`} title={`报告 ${item.runId} · 成绩修订 ${item.scoreRevisionId} · 原卷修订 ${item.paperRevisionId}`} disabled={locked} onClick={() => setRunId(item.runId)}>
            {reportLabel(item)}<span className="b4-meta">成绩修订 {shortId(item.scoreRevisionId)} · 报告 {shortId(item.runId)} · {item.reportReady ? '已准备' : '尚未准备'}</span></button>
          <div className="b4-actions">
            <button className="space-button" disabled={locked || archiveBusy} onClick={() => setArchiveTarget({ runId: item.runId, archived: !item.archivedAt, label: reportLabel(item) })}>{item.archivedAt ? '恢复' : '归档'}</button>
            {item.archivedAt && <span className="space-chip amber">已归档</span>}
            {archiveTarget?.runId === item.runId && <>
              <span className="b4-hint" role="alert">{archiveTarget.archived ? '归档只隐藏列表入口，报告与快照保留且仍可查看；不会删除报告、证据或备注。' : '恢复后该报告重新出现在未归档列表，内容与快照保持原样。'}</span>
              <button className="space-button primary" disabled={archiveBusy} onClick={() => void changeArchive({ runId: item.runId, archived: archiveTarget.archived, label: archiveTarget.label })}>{archiveBusy ? '正在提交…' : archiveTarget.archived ? '确认归档' : '确认恢复'}</button>
              <button className="space-button" disabled={archiveBusy} onClick={() => setArchiveTarget(null)}>取消</button>
            </>}
          </div>
        </Fragment>)}</div>
        <Pagination page={runs.lastData} offset={runsOffset} onOffset={setRunsOffset} disabled={locked} />
      </section>
      {runId && <AnalysisRunPanel key={runId} runId={runId} services={services} onLocked={setChildLocked} onHistoryReload={runs.reload} />}
    </main>
  </div>;
}

function AnalysisRunPanel({ runId, services, onLocked, onHistoryReload }: { runId: string; services: typeof b4Api; onLocked: (locked: boolean) => void; onHistoryReload: () => void }) {
  const resource = useAsyncResource((signal) => services.getAnalysisRun(runId, signal), `analysis-run|${runId}`);
  const { reload: reloadReport } = resource;
  const refreshReport = useCallback(() => { reloadReport(); onHistoryReload(); }, [reloadReport, onHistoryReload]);
  const run = resource.lastData;
  const [copiedIds, setCopiedIds] = useState(false);
  const [locks, setLocks] = useState({ facts: false, practice: false });
  const factsLock = useCallback((value: boolean) => setLocks((previous) => previous.facts === value ? previous : { ...previous, facts: value }), []);
  const practiceLock = useCallback((value: boolean) => setLocks((previous) => previous.practice === value ? previous : { ...previous, practice: value }), []);
  const anyLocked = Object.values(locks).some(Boolean);
  useEffect(() => { onLocked(anyLocked); return () => onLocked(false); }, [anyLocked, onLocked]);
  const job = useObservedJob('teaching', { onTerminal: refreshReport });
  const { adopt, reset } = job;
  const adopted = useRef('');
  const receipt = resource.lastData?.job;
  useEffect(() => {
    if (!receipt || receipt.domain !== 'teaching' || receipt.kind !== 'analysis') return;
    const identity = `${receipt.jobId}|${receipt.attempt}|${receipt.state}`;
    if (adopted.current === identity) return;
    adopted.current = identity; adopt(receipt);
  }, [receipt, adopt]); // 固定身份去重，终态重读不再次创建观察。
  useEffect(() => () => { reset(); onLocked(false); }, [reset, onLocked]);
  /** 复制完整 ID（不是短号）：剪贴板不可用或被拒时静默，短号文本仍可手动选中复制。 */
  async function copyRunIds() {
    if (!run) return;
    try {
      if (!navigator.clipboard?.writeText) return;
      await navigator.clipboard.writeText(`runId=${run.runId}\nscoreRevisionId=${run.scoreRevisionId}\npaperRevisionId=${run.paperRevisionId}`);
      setCopiedIds(true);
    } catch {
      /* 复制失败：不报错、不改状态；ID 短号保留可选 */
    }
  }
  return <section aria-label="所选固定报告">
    <ReadNotice resource={resource} label="所选报告" />
    {run && <>
      <div className="b4-chain">
        <Link href={`/assessments?assessmentId=${encodeURIComponent(run.assessmentId)}&step=history`}>{reportLabel(run)}</Link>
        <span className="b4-meta">成绩修订 {shortId(run.scoreRevisionId)} · 报告 {shortId(run.runId)} · 原卷修订 {shortId(run.paperRevisionId)}</span>
        <button className="space-button" onClick={() => void copyRunIds()}>{copiedIds ? '已复制' : '复制 ID'}</button>
      </div>
      {run.archivedAt && <p className="space-banner" role="status">该报告已归档（<span className="space-chip amber">已归档</span>）：报告「{reportLabel(run)}」与快照保留、仍可查看；后端拒绝据已归档报告新建练习，如需创建请先在报告历史恢复。</p>}
      <JobStatus job={job} />
      {(run.job.domain !== 'teaching' || run.job.kind !== 'analysis') && <ErrorNotice error={new ApiError('ANALYSIS_IDENTITY_MISMATCH', '报告任务所属业务不一致。', 500, false)} />}
      <button className="space-button" onClick={refreshReport}>刷新报告状态</button>
      {!run.reportReady && <p role="status">报告尚未准备好，不能读取事实或创建练习。</p>}
      {run.runId === runId && run.reportReady && run.job.state === 'succeeded' && run.job.domain === 'teaching' && run.job.kind === 'analysis' && <>
        <p className="b4-chain"><Link href={`/lesson-plans?analysisRunId=${encodeURIComponent(run.runId)}`}>以本次固定学情准备教案</Link><span>进入后选择单一班级与目标知识点，再由教师发起调整建议。</span></p>
        <ReportFacts key={runId} run={run} services={services} onLocked={factsLock} />
        {run.archivedAt ? <p className="b4-hint">已归档报告不能新建练习；在报告历史恢复后此入口自动恢复。</p> : <CreatePracticeForm run={run} services={services} onLocked={practiceLock} onCreated={() => undefined} />}
      </>}
    </>}
  </section>;
}

function ReportFacts({ run, services, onLocked }: { run: AnalysisRunView; services: typeof b4Api; onLocked: (locked: boolean) => void }) {
  const tabPanelRef = useRef<HTMLDivElement>(null);
  const [tab, setTab] = useState<'classes' | 'students' | 'evidence' | 'notes'>('classes');
  useEntrance(tabPanelRef, { preset: 'panel', triggerKey: `${run.runId}|${tab}` });
  const [classId, setClassId] = useState('');
  const [participantId, setParticipantId] = useState('');
  const [knowledgePointId, setKnowledgePointId] = useState('');
  const [offset, setOffset] = useState(0);
  const [notesLocked, setNotesLocked] = useState(false);
  const updateNotesLock = useCallback((locked: boolean) => { setNotesLocked(locked); onLocked(locked); }, [onLocked]);
  const query = { classId: classId || undefined, participantId: participantId || undefined, knowledgePointId: knowledgePointId || undefined, offset, limit: 50 };
  const queryKey = JSON.stringify(query);
  const classes = useAsyncResource((signal) => tab === 'classes' ? services.listAnalysisClasses(run.runId, query, signal) : Promise.resolve(null), `analysis-classes|${run.runId}|${tab}|${queryKey}`);
  const students = useAsyncResource((signal) => tab === 'students' ? services.listAnalysisStudents(run.runId, query, signal) : Promise.resolve(null), `analysis-students|${run.runId}|${tab}|${queryKey}`);
  const evidence = useAsyncResource((signal) => tab === 'evidence' ? services.listAnalysisEvidence(run.runId, query, signal) : Promise.resolve(null), `analysis-evidence|${run.runId}|${tab}|${queryKey}`);
  const assessment = useAsyncResource((signal) => getAssessment(run.assessmentId, signal), `analysis-paper-owner|${run.assessmentId}`);
  const loadAsset = useCallback(async (assetId: string, signal: AbortSignal) => {
    const detail = assessment.lastData;
    if (!detail || detail.assessment.paperRevisionId !== run.paperRevisionId) throw new Error('固定原卷身份尚未核对，无法读取图片。');
    return (await getPaperAsset(detail.assessment.paperId, run.paperRevisionId, assetId, signal)).blob;
  }, [assessment.lastData, run.paperRevisionId]);
  const classIds = [...new Set(run.participants.map((participant) => participant.classId))];
  /** 冻结班级 id → 该班任一人次的密封班名（班名缺失时为 null，展示回落短号 + note）。 */
  const sealedClass = (id: string) => run.participants.find((participant) => participant.classId === id);
  const points = run.knowledgePoints.filter((point, index, all) => all.findIndex((p) => p.knowledgePointId === point.knowledgePointId) === index);

  return <section className="b4-section" aria-label="报告事实与证据"><h2>本次固定依据</h2>
    <p className="b4-hint">后端记录：{run.selectionSnapshot.uniqueStudentCount}名学生 · {run.selectionSnapshot.participantCount}人次 · {run.selectionSnapshot.leafCount}计分叶。空白/缺考/免考与有效0分区分，信息不全可与需巩固重叠。</p>
    <div className="space-tabs" role="tablist" aria-label="学情报告视图">{(['classes', 'students', 'evidence', 'notes'] as const).map((value) => <button key={value} disabled={notesLocked} role="tab" aria-selected={tab === value} aria-controls={`analysis-${value}`} id={`analysis-tab-${value}`} className={tab === value ? 'current' : ''} onClick={() => { setTab(value); setOffset(0); }}>{({ classes: '班级依据', students: '学生依据', evidence: '全部题证据', notes: '教师备注' })[value]}</button>)}</div>
    {tab !== 'notes' && <div className="b4-fields">
      <label className="b4-field">冻结班级<select className="space-select" aria-label="报告班级筛选" value={classId} onChange={(event) => { setClassId(event.target.value); setOffset(0); }}><option value="">全部班级</option>{classIds.map((id) => { const sealed = sealedClass(id); const display = classDisplay(sealed?.className, id, sealed?.classNameNote); return <option key={id} value={id}>{display.label} · {display.meta}</option>; })}</select></label>
      <label className="b4-field">参测人次<select className="space-select" aria-label="报告人次筛选" value={participantId} onChange={(event) => { setParticipantId(event.target.value); setOffset(0); }}><option value="">全部人次</option>{run.participants.map((p) => <option key={p.participantId} value={p.participantId}>{p.name} · 人次{p.attemptNo}</option>)}</select></label>
      <label className="b4-field">冻结知识点<select className="space-select" aria-label="报告知识点筛选" value={knowledgePointId} onChange={(event) => { setKnowledgePointId(event.target.value); setOffset(0); }}><option value="">全部知识点</option>{points.map((point) => <option key={point.knowledgePointId} value={point.knowledgePointId}>{point.name}</option>)}</select></label>
    </div>}
    {tab === 'classes' && <div ref={tabPanelRef} role="tabpanel" id="analysis-classes" aria-labelledby="analysis-tab-classes"><ReadNotice resource={classes} label="班级依据" />
      {classes.lastData && <><div className="b4-table-wrap" tabIndex={0} aria-label="班级依据表，可横向滚动"><table className="b4-table"><caption className="visually-hidden">班级知识点事实（后端结果）</caption><thead><tr><th>班级与知识点</th><th>选定 / 有效</th><th>本次需巩固</th><th>信息不全</th><th>无有效依据 / 满分</th><th>需巩固比例</th></tr></thead><tbody>
        {classes.lastData.items.map((row) => { const display = classDisplay(row.className, row.classId, row.classNameNote); return <tr key={`${row.classId}|${row.knowledgePoint.knowledgePointId}`}><th scope="row">{display.label}<span className="b4-meta">{display.meta}</span>{row.knowledgePoint.name}<span className="b4-meta">{row.knowledgePoint.knowledgeRevisionId}</span></th><td>{row.selectedCount} / {row.validCount}</td><td>{row.needsCount}</td><td>{row.incompleteCount}</td><td>{row.noEvidenceCount} / {row.fullCreditCount}</td><td>{row.denominator === 0 ? '暂无有效依据' : <>{row.numerator} / {row.denominator}<span className="b4-meta">后端比例 {row.ratio ?? '未提供'}</span></>}</td></tr>; })}
      </tbody></table></div>{classes.lastData.items.length === 0 && <p>没有符合筛选条件的班级依据。</p>}<Pagination page={classes.lastData} offset={offset} onOffset={setOffset} /></>}
    </div>}
    {tab === 'students' && <div ref={tabPanelRef} role="tabpanel" id="analysis-students" aria-labelledby="analysis-tab-students"><ReadNotice resource={students} label="学生依据" />
      {students.lastData && <><div className="b4-table-wrap" tabIndex={0} aria-label="学生依据表，可横向滚动"><table className="b4-table"><caption className="visually-hidden">学生知识点观察（后端结果）</caption><thead><tr><th>人次与知识点</th><th>本次观察</th><th>有效 / 应有依据</th><th>四态计数</th><th>有效得分</th><th>全部题证据</th></tr></thead><tbody>{students.lastData.items.map((row) => { const display = classDisplay(row.participant.className, row.participant.classId, row.participant.classNameNote); return <tr key={`${row.participant.participantId}|${row.knowledgePoint.knowledgePointId}`}><th scope="row">{row.participant.name} · 人次{row.participant.attemptNo}<span className="b4-meta">班级 {display.label} · {display.meta}</span>{row.knowledgePoint.name}</th><td>{observationLabel[row.observation]}{row.informationIncomplete && <span className="b4-meta">信息不全（独立标记）</span>}</td><td>{row.validCount} / {row.expectedCount}</td><td>{Object.entries(row.stateCounts).map(([state, count]) => <span key={state} className="b4-meta">{statusLabel[state as keyof typeof statusLabel]} {count}</span>)}</td><td>{scoreText(row.totalScoreUnits)} / {scoreText(row.totalMaxScoreUnits)}</td><td><button className="space-button" onClick={() => { setParticipantId(row.participant.participantId); setKnowledgePointId(row.knowledgePoint.knowledgePointId); setTab('evidence'); setOffset(0); }}>查看全部依据</button></td></tr>; })}</tbody></table></div>{students.lastData.items.length === 0 && <p>没有符合筛选条件的学生依据。</p>}<Pagination page={students.lastData} offset={offset} onOffset={setOffset} /></>}
    </div>}
    {tab === 'evidence' && <div ref={tabPanelRef} role="tabpanel" id="analysis-evidence" aria-labelledby="analysis-tab-evidence"><ReadNotice resource={evidence} label="全部题证据" /><ReadNotice resource={assessment} label="原卷资产身份" />
      {evidence.lastData?.items.map((row) => <EvidenceDetail key={row.evidenceId} evidence={row} loadAsset={loadAsset} />)}
      {evidence.lastData?.items.length === 0 && <p>没有符合筛选条件的题证据。</p>}<Pagination page={evidence.lastData} offset={offset} onOffset={setOffset} />
    </div>}
    {tab === 'notes' && <div ref={tabPanelRef} role="tabpanel" id="analysis-notes" aria-labelledby="analysis-tab-notes"><TeacherNotes run={run} services={services} onLocked={updateNotesLock} /></div>}
  </section>;
}

function EvidenceDetail({ evidence, loadAsset }: { evidence: EvidenceRow; loadAsset: (assetId: string, signal: AbortSignal) => Promise<Blob> }) {
  const raw = evidence.content.richContent ?? evidence.content;
  // 固定纸卷历史允许没有version/origin；只是把既有结构字段交给公共renderer，不生成题目内容。
  const candidate = { ...raw as Record<string, unknown>, version: 2, sharedMaterials: (raw as Record<string, unknown>).sharedMaterials ?? evidence.sharedMaterials,
    stemBlocks: (raw as Record<string, unknown>).stemBlocks, optionBlocks: (raw as Record<string, unknown>).optionBlocks ?? {},
    answerBlocks: (raw as Record<string, unknown>).answerBlocks ?? [], explanationBlocks: (raw as Record<string, unknown>).explanationBlocks ?? [],
    assets: (raw as Record<string, unknown>).assets ?? evidence.assets,
    origin: (raw as Record<string, unknown>).origin ?? { originalAssetId: '', originalSha256: '', sourceLocator: evidence.sourceLocator } };
  const rich: RichContentV2 | null = isRichContent(candidate) ? candidate : null;
  return <details><summary>{evidence.participant.name} · 人次{evidence.participant.attemptNo} · {evidence.itemPath} · {statusLabel[evidence.status]} {scoreText(evidence.scoreUnits)} / {scoreText(evidence.maxScoreUnits)}</summary>
    <p className="b4-meta">成绩 {evidence.scoreRevisionId} · 原卷 {evidence.paperRevisionId} · 计分叶 {evidence.itemId}</p>
    <p>{evidence.knowledgePoints.map((point) => `${point.name}（${point.knowledgeRevisionId}）`).join('、') || '未关联知识点'}</p>
    {evidence.associationNote && <p className="b4-hint">{evidence.associationNote}</p>}
    {evidence.knowledgePoints.length > 1 && <p className="b4-hint">综合题失分关联，具体错因待教师确认。</p>}
    {rich ? <RichReview content={rich} loadAsset={loadAsset} assetScope={`${evidence.paperRevisionId}|${evidence.itemId}`} /> : <p role="alert">固定题面结构暂无法识别，请核对原卷；没有生成替代题面。</p>}
    <details><summary>原始来源与回流映射</summary><pre className="b4-meta">{JSON.stringify(evidence.sourceLocator, null, 2)}</pre>{!rich && <pre className="b4-meta">{JSON.stringify(evidence.content, null, 2)}</pre>}<p className="b4-meta">{evidence.practiceRevisionId ? `练习修订 ${evidence.practiceRevisionId} → 练习题 ${evidence.practiceItemId} → 原卷题 ${evidence.itemId} → 本成绩单元 → 证据 ${evidence.evidenceId}` : '来源为原文件卷。'}</p></details>
  </details>;
}

function TeacherNotes({ run, services, onLocked }: { run: AnalysisRunView; services: typeof b4Api; onLocked: (locked: boolean) => void }) {
  const [note, setNote] = useState('');
  const [participantId, setParticipantId] = useState('');
  const [pointId, setPointId] = useState('');
  const [offset, setOffset] = useState(0);
  const submission = useFrozenSubmission<NoteRequest, NoteView>();
  const editGeneration = useRef(0);
  const loadGeneration = useRef(crypto.randomUUID());
  const mounted = useRef(true);
  const contextKey = `analysis-note|${run.runId}`;
  const currentContext = useRef(contextKey); currentContext.current = contextKey;
  const [appendNotice, setAppendNotice] = useState('');
  const receivedOperations = useRef<Array<{ submissionId: string; runId: string; noteId: string }>>([]);
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; }; }, []);
  const notes = useAsyncResource((signal) => services.listAnalysisNotes(run.runId, { offset, limit: 50 }, signal), `analysis-notes|${run.runId}|${offset}`);
  const locked = submission.busy || submission.phase === 'unknown';
  useEffect(() => { onLocked(locked); return () => onLocked(false); }, [locked, onLocked]);
  async function append() {
    const receipt = await submission.submitWithReceipt({ submissionId: '', participantId: participantId || null, knowledgePointId: pointId || null, note: note.trim() }, (frozen) => services.createAnalysisNote(run.runId, { ...frozen.payload, submissionId: frozen.submissionId }),
      { contextKey, originalEditGeneration: editGeneration.current, loadGeneration: loadGeneration.current });
    if (!receipt) return;
    receivedOperations.current.push({ submissionId: receipt.operation.submissionId, runId: receipt.result.runId, noteId: receipt.result.noteId });
    if (!receipt.current || !mounted.current || receipt.operation.metadata?.contextKey !== currentContext.current || receipt.result.runId !== run.runId) return;
    if (receipt.operation.metadata.loadGeneration === loadGeneration.current && editGeneration.current === receipt.operation.metadata.originalEditGeneration) {
      setNote(''); setAppendNotice('原备注已追加。');
    } else setAppendNotice('原备注已追加；发送后的新备注仍保留，尚未追加。');
    notes.reload();
  }
  /** 备注归属显示（名称优先）：用 run 内的姓名/知识点名映射，映射不到才短号。 */
  const participantText = (id: string | null) => {
    if (!id) return '整份报告';
    const owner = run.participants.find((participant) => participant.participantId === id);
    return owner ? `${owner.name} · 人次${owner.attemptNo}` : shortId(id);
  };
  const pointText = (id: string | null) => {
    if (!id) return '全部知识点';
    const point = run.knowledgePoints.find((candidate) => candidate.knowledgePointId === id);
    return point ? point.name : shortId(id);
  };
  return <><p className="b4-hint">备注只追加教师判断，固定成绩与报告结论不变。</p><ReadNotice resource={notes} label="教师备注" />
    {notes.lastData?.items.map((item) => <article className="b4-job" key={item.noteId}><p>{item.note}</p><span className="b4-meta" title={[item.participantId && `人次 ${item.participantId}`, item.knowledgePointId && `知识点 ${item.knowledgePointId}`].filter(Boolean).join(' · ') || undefined}>{item.createdAt} · {participantText(item.participantId)} · {pointText(item.knowledgePointId)}</span></article>)}
    {notes.lastData?.items.length === 0 && <p>还没有教师备注。</p>}<Pagination page={notes.lastData} offset={offset} onOffset={setOffset} />
    <div className="b4-fields"><label className="b4-field">备注人次<select className="space-select" aria-label="备注人次" value={participantId} disabled={locked} onChange={(event) => { editGeneration.current += 1; setParticipantId(event.target.value); }}><option value="">整份报告</option>{run.participants.map((p) => <option value={p.participantId} key={p.participantId}>{p.name} · 人次{p.attemptNo}</option>)}</select></label><label className="b4-field">备注知识点<select className="space-select" aria-label="备注知识点" disabled={locked} value={pointId} onChange={(event) => { editGeneration.current += 1; setPointId(event.target.value); }}><option value="">全部知识点</option>{run.knowledgePoints.map((p) => <option key={p.knowledgePointId} value={p.knowledgePointId}>{p.name}</option>)}</select></label></div>
    <label className="b4-field">教师备注<textarea aria-label="教师备注内容" value={note} disabled={submission.phase === 'unknown'} onChange={(event) => { editGeneration.current += 1; setNote(event.target.value); }} /></label>
    {appendNotice && <p className="b4-hint" role="status">{appendNotice}</p>}
    <SubmissionNotice submission={submission} /><button className="space-button primary" disabled={submission.busy || (submission.phase !== 'unknown' && !note.trim())} onClick={() => void append()}>{submission.phase === 'unknown' ? '重试原备注提交' : '追加教师备注'}</button>
  </>;
}

export default LearningAnalysisWorkspace;
