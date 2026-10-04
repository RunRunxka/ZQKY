'use client';

import { useEffect, useRef, useState } from 'react';
import type { ExportRequest, ExportReceipt, ExportArtifact, PracticeRevisionView } from '@/contracts/b4';
import { b4Api } from '@/services/teaching-loop-b4-api';
import { asApiError, useAsyncResource, useFrozenSubmission } from '@/features/assessments/hooks';
import { useObservedJob } from '@/services/use-workflow-job';
import { ApiError } from '@/services/api-client';
import { ErrorNotice, ReadNotice, SubmissionNotice, Pagination, JobStatus } from '@/features/learning-analysis/ui';

const variantLabel = { student: '学生 DOCX', teacher: '教师 DOCX', score_template: '成绩模板 XLSX' };
type FrozenExport = { setId: string; revisionId: string; body: ExportRequest };

export function PracticeExports({ revision, services, convertedAssessmentId, onLocked }: {
  revision: PracticeRevisionView; services: typeof b4Api; convertedAssessmentId: string | null; onLocked: (locked: boolean) => void;
}) {
  const [assessmentId, setAssessmentId] = useState(convertedAssessmentId ?? '');
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<ApiError | null>(null);
  const [downloading, setDownloading] = useState<string | null>(null);
  const submission = useFrozenSubmission<FrozenExport, ExportReceipt>();
  const artifacts = useAsyncResource((signal) => services.listPracticeExports(revision.practiceSetId, revision.practiceRevisionId, { offset, limit: 50 }, signal), `practice-artifacts|${revision.practiceSetId}|${revision.practiceRevisionId}|${offset}`);
  const alive = useRef(true);
  const receiptIdentity = useRef<{ jobId: string; exportId: string; variant: ExportRequest['variant']; assessmentId: string | null } | null>(null);
  const downloadGeneration = useRef(0);
  const downloadAbort = useRef<AbortController | null>(null);
  const job = useObservedJob('teaching', { onTerminal: (view) => {
    const identity = receiptIdentity.current;
    if (view.state !== 'succeeded' || !identity || view.jobId !== identity.jobId) return;
    const result = view.result;
    if (!result || typeof result.artifactId !== 'string' || result.exportId !== identity.exportId || result.practiceRevisionId !== revision.practiceRevisionId || result.variant !== identity.variant || result.assessmentId !== identity.assessmentId) {
      setError(new ApiError('EXPORT_IDENTITY_MISMATCH', '任务产物与固定练习版本不一致，未提供下载。请核对此任务。', 500, false)); return;
    }
    void services.getExportArtifact(result.artifactId).then((artifact) => {
      if (!alive.current || receiptIdentity.current?.jobId !== view.jobId) return;
      if (artifact.artifactId !== result.artifactId || artifact.exportId !== identity.exportId || artifact.practiceRevisionId !== revision.practiceRevisionId || artifact.variant !== identity.variant || artifact.assessmentId !== identity.assessmentId) {
        setError(new ApiError('EXPORT_IDENTITY_MISMATCH', '产物元数据不属于此固定版本，未提供下载。', 500, false)); return;
      }
      artifacts.reload();
    }, (cause) => { if (alive.current && receiptIdentity.current?.jobId === view.jobId) setError(asApiError(cause)); });
  } });
  const activeJob = job.view?.state === 'queued' || job.view?.state === 'running';
  const locked = submission.busy || submission.phase === 'unknown' || downloading !== null;
  useEffect(() => { alive.current = true; return () => { alive.current = false; downloadGeneration.current += 1; downloadAbort.current?.abort(); }; }, []);
  useEffect(() => { if (convertedAssessmentId && !submission.busy && submission.phase !== 'unknown') setAssessmentId(convertedAssessmentId); }, [convertedAssessmentId, submission.busy, submission.phase]);
  useEffect(() => { onLocked(locked); return () => onLocked(false); }, [locked, onLocked]);

  async function start(variant: ExportRequest['variant']) {
    setError(null);
    const packet: FrozenExport = submission.phase === 'unknown' && submission.frozen ? submission.frozen.payload : { setId: revision.practiceSetId, revisionId: revision.practiceRevisionId, body: { submissionId: '', variant, assessmentId: variant === 'score_template' ? assessmentId.trim() : null } };
    const result = await submission.submit(packet,
      (frozen) => services.createPracticeExport(frozen.payload.setId, frozen.payload.revisionId, { ...frozen.payload.body, submissionId: frozen.submissionId }));
    if (!result || !alive.current) return;
    // 原包重试采用原 variant/assessmentId；未知时其他按钮已锁定，不能切换请求。
    const boundVariant = packet.body.variant;
    const boundAssessment = packet.body.assessmentId ?? null;
    if (result.practiceRevisionId !== revision.practiceRevisionId || result.job.domain !== 'teaching' || result.job.kind !== 'export') {
      setError(new ApiError('EXPORT_IDENTITY_MISMATCH', '导出收据不属于此固定版本。', 500, false)); return;
    }
    receiptIdentity.current = { jobId: result.job.jobId, exportId: result.exportId, variant: boundVariant, assessmentId: boundAssessment };
    job.adopt(result.job);
  }
  async function download(artifact: ExportArtifact) {
    if (artifact.practiceRevisionId !== revision.practiceRevisionId || downloading) return;
    const controller = new AbortController(); downloadAbort.current?.abort(); downloadAbort.current = controller;
    const token = ++downloadGeneration.current;
    setDownloading(artifact.artifactId); setError(null);
    try {
      const file = await services.downloadExportArtifact(artifact.artifactId, controller.signal);
      if (!alive.current || token !== downloadGeneration.current || controller.signal.aborted) return;
      if (file.blob.size !== artifact.byteSize) throw new ApiError('EXPORT_DOWNLOAD_INCOMPLETE', '下载字节数与固定产物不一致，未保存文件，请重试。', 500, true);
      const url = URL.createObjectURL(file.blob);
      const link = document.createElement('a'); link.href = url; link.download = file.fileName ?? artifact.filename;
      document.body.appendChild(link); link.click(); link.remove(); URL.revokeObjectURL(url);
    } catch (cause) { if (alive.current && token === downloadGeneration.current && !controller.signal.aborted) setError(asApiError(cause)); }
    finally { if (alive.current && token === downloadGeneration.current) setDownloading(null); }
  }
  return <section className="b4-section" aria-label="固定练习导出"><h2>固定审核版本导出</h2>
    <p className="b4-hint">练习 v{revision.version} · {revision.practiceRevisionId}。学生版不含答案解析，教师版标明缺失答案。202表示任务接受；成功产物才可下载。</p>
    <label className="b4-field">此审核版本已转换的施测ID<input aria-label="模板施测ID" value={assessmentId} disabled={locked} onChange={(event) => setAssessmentId(event.target.value)} /></label>
    <p className="b4-hint">成绩模板须在本练习转换施测后生成；后端冻结接受导出时的真实参测名单、固定原卷和叶映射，空白成绩不补0。</p>
    <div className="b4-actions">{(['student', 'teacher', 'score_template'] as const).map((variant) => <button key={variant} className="space-button" disabled={locked || activeJob || (variant === 'score_template' && !assessmentId.trim())} onClick={() => void start(variant)}>生成{variantLabel[variant]}</button>)}
      {submission.phase === 'unknown' && <button className="space-button primary" disabled={submission.busy} onClick={() => void start(submission.frozen?.payload.body.variant ?? 'student')}>重试原导出提交</button>}
    </div>
    <SubmissionNotice submission={submission} /><JobStatus job={job} /><ErrorNotice error={error} />
    <ReadNotice resource={artifacts} label="固定导出产物" /><button className="space-button" onClick={artifacts.reload}>刷新产物历史</button>
    {artifacts.state.phase === 'ready' && artifacts.lastData?.items.length === 0 && <p>此审核版本还没有成功的导出产物。</p>}
    <div className="b4-artifacts">{artifacts.lastData?.items.filter((artifact) => artifact.practiceRevisionId === revision.practiceRevisionId).map((artifact) => <article className="b4-job" key={artifact.artifactId}><strong>{variantLabel[artifact.variant]}</strong><span className="b4-meta">{artifact.filename} · {artifact.byteSize}字节 · {artifact.createdAt}</span>{artifact.assessmentId && <span className="b4-meta">名单来源施测 {artifact.assessmentId}</span>}<button className="space-button" disabled={downloading !== null} onClick={() => void download(artifact)}>{downloading === artifact.artifactId ? '下载中…' : `下载${variantLabel[artifact.variant]}`}</button></article>)}</div>
    <Pagination page={artifacts.lastData} offset={offset} onOffset={setOffset} disabled={locked} />
  </section>;
}
