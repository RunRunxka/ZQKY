'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import type { AnalysisRunView, PracticeCreateRequest, PracticeSetView } from '@/contracts/b4';
import { b4Api } from '@/services/teaching-loop-b4-api';
import { createQuestionGenerationJob } from '@/services/question-bank-api';
import { useModelCatalog } from '@/features/model-settings/useModelCatalog';
import { useFrozenSubmission } from '@/features/assessments/hooks';
import { SubmissionNotice, nameOrShortId, stampText } from '@/features/learning-analysis/ui';
import { ConstraintsFields, defaultConstraints } from './ConstraintsFields';

export function CreatePracticeForm({ run, services = b4Api, onCreated, onLocked }: {
  run: AnalysisRunView; services?: typeof b4Api; onCreated: (view: PracticeSetView) => void;
  onLocked?: (locked: boolean) => void;
}) {
  const { catalog } = useModelCatalog();
  const [title, setTitle] = useState('');
  const [targets, setTargets] = useState<string[]>([]);
  const [constraints, setConstraints] = useState({ ...defaultConstraints });
  const [aiCount, setAiCount] = useState(5);
  const [aiNote, setAiNote] = useState('');
  const [aiBusy, setAiBusy] = useState(false);
  const [aiNotice, setAiNotice] = useState<string | null>(null);
  const submission = useFrozenSubmission<PracticeCreateRequest, PracticeSetView>();
  const locked = submission.busy || submission.phase === 'unknown';
  useEffect(() => { onLocked?.(locked); return () => onLocked?.(false); }, [locked, onLocked]);
  const ready = run.reportReady && run.job.state === 'succeeded';
  const uniqueKnowledge = run.knowledgePoints.filter((point, index, points) => points.findIndex((item) => item.knowledgePointId === point.knowledgePointId) === index);
  async function requestAiQuestions() {
    const modelProfileId = catalog?.defaultChatProfileId || '';
    if (aiBusy || !modelProfileId || targets.length === 0) return;
    setAiBusy(true);
    setAiNotice(null);
    try {
      const view = await createQuestionGenerationJob({
        modelProfileId,
        knowledgePointIds: targets,
        count: aiCount,
        instructions: aiNote.trim() || null,
      });
      setAiNotice(view.state === 'succeeded'
        ? `AI 已生成 ${view.candidateCount ?? 0} 道候选题（导入批 ${view.importId ?? '—'}）：请到题库校对确认入库，再回来创建练习。`
        : `AI 出题任务状态：${view.state}${view.errorCode ? `（${view.errorCode}）` : ''}；请稍后到题库查看或重试。`);
    } catch (error) {
      const e = error as { message?: string };
      setAiNotice(`AI 出题失败：${e.message ?? '未知错误'}`);
    } finally {
      setAiBusy(false);
    }
  }
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
      <div className="b4-field" aria-label="AI 出题补齐">
        <span className="b4-meta">题库不够时可用 AI 补题（按所选知识点与描述生成候选，需到题库校对确认后才会进入练习选拔）：</span>
        <span className="practice-ai-row">
          <input
            aria-label="AI 补题数量"
            type="number" min={1} max={20}
            value={aiCount}
            onChange={(event) => setAiCount(Math.max(1, Math.min(20, Number(event.target.value) || 5)))}
            disabled={aiBusy || locked || !ready}
          />
          <input
            aria-label="AI 出题要求"
            type="text"
            placeholder="给 AI 的出题要求（可空，如：基础巩固，贴近例题）"
            maxLength={500}
            value={aiNote}
            onChange={(event) => setAiNote(event.target.value)}
            disabled={aiBusy || locked || !ready}
          />
          <button
            type="button"
            className="space-button"
            disabled={aiBusy || locked || !ready || targets.length === 0 || !(catalog?.defaultChatProfileId || '')}
            onClick={() => void requestAiQuestions()}
          >
            {aiBusy ? '生成中…' : 'AI 出题补齐'}
          </button>
        </span>
        {aiNotice && <p className="b4-meta" role="status">{aiNotice}</p>}
      </div>
    </fieldset>
    <SubmissionNotice submission={submission} />
    <button className="space-button primary" disabled={submission.busy || !ready || (submission.phase !== 'unknown' && (!title.trim() || targets.length === 0))} onClick={() => void submit()}>
      {submission.phase === 'unknown' ? '重试原创建练习提交' : '创建针对练习'}
    </button>
    {submission.result && <p className="b4-chain"><Link href={`/practices?practiceSetId=${encodeURIComponent(submission.result.practiceSetId)}`}>打开新练习：{submission.result.title}</Link></p>}
  </section>;
}
