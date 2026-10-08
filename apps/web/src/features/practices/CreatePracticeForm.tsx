'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import type { AnalysisRunView, PracticeCreateRequest, PracticeSetView } from '@/contracts/b4';
import { b4Api } from '@/services/teaching-loop-b4-api';
import { useFrozenSubmission } from '@/features/assessments/hooks';
import { SubmissionNotice, nameOrShortId, stampText } from '@/features/learning-analysis/ui';
import { ConstraintsFields, defaultConstraints } from './ConstraintsFields';

export function CreatePracticeForm({ run, services = b4Api, onCreated, onLocked }: {
  run: AnalysisRunView; services?: typeof b4Api; onCreated: (view: PracticeSetView) => void;
  onLocked?: (locked: boolean) => void;
}) {
  const [title, setTitle] = useState('');
  const [targets, setTargets] = useState<string[]>([]);
  const [constraints, setConstraints] = useState({ ...defaultConstraints });
  const submission = useFrozenSubmission<PracticeCreateRequest, PracticeSetView>();
  const locked = submission.busy || submission.phase === 'unknown';
  useEffect(() => { onLocked?.(locked); return () => onLocked?.(false); }, [locked, onLocked]);
  const ready = run.reportReady && run.job.state === 'succeeded';
  const uniqueKnowledge = run.knowledgePoints.filter((point, index, points) => points.findIndex((item) => item.knowledgePointId === point.knowledgePointId) === index);
  async function submit() {
    const result = await submission.submit({ submissionId: '', analysisRunId: run.runId, title: title.trim(), targetKnowledgePointIds: targets, constraints },
      (frozen) => services.createPractice({ ...frozen.payload, submissionId: frozen.submissionId }));
    if (result) onCreated(result);
  }
  return <section className="b4-section" aria-label="创建针对练习">
    <h2>选择目标，创建针对练习</h2><p className="b4-hint" title={`分析运行 ${run.runId}`}>依据固定报告「{nameOrShortId(run.paperTitle, run.runId)}」{run.createdAt ? ` · ${stampText(run.createdAt)}` : ''}。先选择需要练习的知识点，再核对正式题与缺口。</p>
    {!ready && <p role="status">报告尚未准备好，不能创建练习。</p>}
    <fieldset disabled={locked || !ready}>
      <label className="b4-field">练习标题<input aria-label="练习标题" maxLength={200} value={title} onChange={(event) => setTitle(event.target.value)} /></label>
      <div className="b4-checks" aria-label="练习目标知识点">{uniqueKnowledge.map((point) => <label key={point.knowledgePointId}>
        <input type="checkbox" aria-label={`练习目标 ${point.name}`} checked={targets.includes(point.knowledgePointId)} onChange={(event) => setTargets((previous) => event.target.checked ? [...previous, point.knowledgePointId] : previous.filter((id) => id !== point.knowledgePointId))} />
        <span>{point.name}<small className="b4-meta">固定修订 {point.knowledgeRevisionId}</small></span>
      </label>)}</div>
      <ConstraintsFields value={constraints} onChange={setConstraints} />
    </fieldset>
    <SubmissionNotice submission={submission} />
    <button className="space-button primary" disabled={submission.busy || !ready || (submission.phase !== 'unknown' && (!title.trim() || targets.length === 0))} onClick={() => void submit()}>
      {submission.phase === 'unknown' ? '重试原创建练习提交' : '创建针对练习'}
    </button>
    {submission.result && <p className="b4-chain"><Link href={`/practices?practiceSetId=${encodeURIComponent(submission.result.practiceSetId)}`}>打开新练习：{submission.result.title}</Link></p>}
  </section>;
}
