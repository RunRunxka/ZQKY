'use client';

/**
 * 导出预览与产物下载（R8-FE 2026-10-12）。
 *
 * 用户口径：**确认（审核）后才可导出**；导出区是 A4 分页预览的两个页签——
 * 学生卷（卷头 + 题号 + 题干 + 作答区留白）与教师卷（追加答案与解析、答案页）——
 * 下载按钮按归档 exports 端点：学生卷 / 教师卷 docx、成绩模板 xlsx。
 *
 * 纪律（取自归档 `features/practices/PracticeExports.tsx`）：
 * - `202` 只代表任务接受；产物元数据与固定修订身份不符时不提供下载；
 * - 下载字节数与产物 `byteSize` 不一致时不保存文件；
 * - 成绩模板需在练习转换为施测后生成（`convertedAssessmentId` 存在才可点）；
 * - 预览由审核修订的固定内容按内容流分页，题不劈页；与真实 docx 由后端组装，预览是估算。
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import type {
  ExportArtifact,
  ExportReceipt,
  ExportRequest,
  PracticeRevisionView,
  PracticeSetView,
} from '@/contracts/b4';
import type { ContentBlock, RichContentV2 } from '@/contracts/question-bank';
import { b4Api } from '@/services/teaching-loop-b4-api';
import { asApiError, useAsyncResource, useFrozenSubmission } from '@/features/assessments/hooks';
import { useTeachingJob } from '@/features/assessments/jobs';
import { ApiError } from '@/services/api-client';
import { RichBlocks } from '@/features/question-bank/rich-content';
import { getQuestionAsset } from '@/services/question-bank-api';
import { layoutPaper, pageEndLabel, PAPER_PADDING_PX, type PaperLayout, type PaperSegment } from './paper';
import { ErrorNotice, JobStatusNotice, RichReview, SubmissionNotice, scoreText, shortId } from './ui';
import { SlidingGroup } from '@/components/ui/SlidingGroup';

const VARIANT_LABEL: Record<ExportRequest['variant'], string> = {
  student: '学生卷 DOCX',
  teacher: '教师卷 DOCX',
  score_template: '成绩模板 XLSX',
};

type ExportVariant = ExportRequest['variant'];
type FrozenExport = { setId: string; revisionId: string; body: ExportRequest };

function triggerBlobDownload(blob: Blob, fileName: string): boolean {
  if (typeof document === 'undefined' || typeof URL.createObjectURL !== 'function') return false;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  return true;
}

/** 答案页的答案块（无答案时明确「答案缺失」，不猜造）。 */
function AnswerBlocks({ content, questionId, revisionId }: { content: RichContentV2; questionId: string; revisionId: string }) {
  const loadAsset = (assetId: string, signal: AbortSignal) => getQuestionAsset('question', questionId, assetId, signal);
  const blocks: ContentBlock[] = content.answerBlocks;
  if (blocks.length === 0) return <span className="practices-warn">答案缺失</span>;
  return <RichBlocks blocks={blocks} loadAsset={loadAsset} assetScope={`${questionId}|${revisionId}`} />;
}

function PaperSheet({ pageNumber, children }: { pageNumber: number; children: React.ReactNode }) {
  return (
    <div className="practices-sheet" data-testid={`practices-paper-${pageNumber}`}>
      <div className="practices-sheet-body" style={{ padding: `${PAPER_PADDING_PX}px` }}>
        {children}
      </div>
      <div className="practices-page-end" data-testid={`practices-page-end-${pageNumber}`}>
        {pageEndLabel(pageNumber)}
      </div>
    </div>
  );
}

export interface PracticeExportPanelProps {
  view: PracticeSetView;
  services?: typeof b4Api;
}

export function PracticeExportPanel({ view, services = b4Api }: PracticeExportPanelProps) {
  const reviewedRevisions = useMemo(
    () => view.revisions.filter((revision) => revision.state === 'reviewed'),
    [view.revisions],
  );
  const defaultRevision = view.currentRevision.state === 'reviewed' ? view.currentRevision : reviewedRevisions[0] ?? null;
  const [revisionId, setRevisionId] = useState(defaultRevision?.practiceRevisionId ?? '');
  useEffect(() => {
    setRevisionId(defaultRevision?.practiceRevisionId ?? '');
  }, [defaultRevision?.practiceRevisionId, view.practiceSetId]);
  const revision: PracticeRevisionView | null =
    reviewedRevisions.find((item) => item.practiceRevisionId === revisionId) ?? defaultRevision;
  const [tab, setTab] = useState<'student' | 'teacher'>('student');
  const [offset, setOffset] = useState(0);
  const [error, setError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState('');
  const [downloading, setDownloading] = useState<string | null>(null);
  const alive = useRef(true);
  const downloadAbort = useRef<AbortController | null>(null);
  const receiptIdentity = useRef<{ jobId: string; exportId: string; variant: ExportVariant; assessmentId: string | null } | null>(null);
  const submission = useFrozenSubmission<FrozenExport, ExportReceipt>();
  const artifacts = useAsyncResource(
    (signal) =>
      revision
        ? services.listPracticeExports(view.practiceSetId, revision.practiceRevisionId, { offset, limit: 50 }, signal)
        : Promise.resolve(null),
    `practice-artifacts|${view.practiceSetId}|${revision?.practiceRevisionId ?? 'none'}|${offset}`,
  );
  const job = useTeachingJob({
    onTerminal: (jobView) => {
      const identity = receiptIdentity.current;
      if (jobView.state !== 'succeeded' || !identity || jobView.jobId !== identity.jobId || !revision) return;
      const result = jobView.result;
      if (
        !result ||
        typeof result.artifactId !== 'string' ||
        result.exportId !== identity.exportId ||
        result.practiceRevisionId !== revision.practiceRevisionId ||
        result.variant !== identity.variant ||
        (result.assessmentId ?? null) !== identity.assessmentId
      ) {
        setError(new ApiError('EXPORT_IDENTITY_MISMATCH', '任务产物与固定练习版本不一致，未提供下载。请核对此任务。', 500, false));
        return;
      }
      void services.getExportArtifact(result.artifactId).then(
        (artifact) => {
          if (!alive.current || receiptIdentity.current?.jobId !== jobView.jobId) return;
          if (
            artifact.artifactId !== result.artifactId ||
            artifact.exportId !== identity.exportId ||
            artifact.practiceRevisionId !== revision.practiceRevisionId ||
            artifact.variant !== identity.variant ||
            artifact.assessmentId !== identity.assessmentId
          ) {
            setError(new ApiError('EXPORT_IDENTITY_MISMATCH', '产物元数据不属于此固定版本，未提供下载。', 500, false));
            return;
          }
          setNotice(`已生成：${artifact.filename}`);
          artifacts.reload();
        },
        (cause) => {
          if (alive.current && receiptIdentity.current?.jobId === jobView.jobId) setError(asApiError(cause));
        },
      );
    },
  });
  const activeJob = job.view?.state === 'queued' || job.view?.state === 'running';
  const busy = submission.busy || submission.phase === 'unknown' || downloading !== null || activeJob;

  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
      downloadAbort.current?.abort();
    };
  }, []);

  const layout: PaperLayout | null = useMemo(
    () => (revision ? layoutPaper(revision.items, tab) : null),
    [revision, tab],
  );

  if (!revision || !layout) {
    return (
      <section className="practices-card" aria-label="导出预览" data-testid="practices-export-gate">
        <header className="practices-card-head">
          <h2>导出预览</h2>
        </header>
        <p className="space-banner" role="status">
          未审核（review）的草稿不能进入导出区：请先在「编辑与微调」提交审核并确认冻结；导出只从已审核修订生成。
        </p>
      </section>
    );
  }

  const convertedAssessmentId = revision.convertedAssessmentId ?? null;
  // 守卫后的非空别名：闭包（renderSegment）里不再需要可选链，也不会丢类型收窄。
  const paper = layout;
  const currentRevision = revision;

  async function start(variant: ExportVariant) {
    if (!revision) return;
    setError(null);
    setNotice('');
    const packet: FrozenExport =
      submission.phase === 'unknown' && submission.frozen
        ? submission.frozen.payload
        : {
            setId: view.practiceSetId,
            revisionId: revision.practiceRevisionId,
            body: { submissionId: '', variant, assessmentId: variant === 'score_template' ? convertedAssessmentId : null },
          };
    const receipt = await submission.submit(packet, (frozen) =>
      services.createPracticeExport(frozen.payload.setId, frozen.payload.revisionId, {
        ...frozen.payload.body,
        submissionId: frozen.submissionId,
      }),
    );
    if (!receipt || !alive.current) return;
    const boundVariant = packet.body.variant;
    const boundAssessment = packet.body.assessmentId ?? null;
    if (receipt.practiceRevisionId !== revision.practiceRevisionId || receipt.job.domain !== 'teaching' || receipt.job.kind !== 'export') {
      setError(new ApiError('EXPORT_IDENTITY_MISMATCH', '导出收据不属于此固定版本。', 500, false));
      return;
    }
    receiptIdentity.current = { jobId: receipt.job.jobId, exportId: receipt.exportId, variant: boundVariant, assessmentId: boundAssessment };
    job.adopt(receipt.job);
  }

  async function download(artifact: ExportArtifact) {
    if (!revision || artifact.practiceRevisionId !== revision.practiceRevisionId || downloading) return;
    const controller = new AbortController();
    downloadAbort.current?.abort();
    downloadAbort.current = controller;
    setDownloading(artifact.artifactId);
    setError(null);
    try {
      const file = await services.downloadExportArtifact(artifact.artifactId, controller.signal);
      if (!alive.current || controller.signal.aborted) return;
      if (file.blob.size !== artifact.byteSize) {
        throw new ApiError('EXPORT_DOWNLOAD_INCOMPLETE', '下载字节数与固定产物不一致，未保存文件，请重试。', 500, true);
      }
      if (!triggerBlobDownload(file.blob, file.fileName ?? artifact.filename)) {
        setError(new ApiError('DOWNLOAD_UNAVAILABLE', '当前环境不支持浏览器下载，请稍后在桌面浏览器重试。', 500, true));
      }
    } catch (cause) {
      if (alive.current && !controller.signal.aborted) setError(asApiError(cause));
    } finally {
      if (alive.current) setDownloading(null);
    }
  }

  function renderSegment(segment: PaperSegment) {
    if (segment.kind === 'header') {
      return (
        <header className="practices-paper-head" key={segment.id}>
          <h3>{currentRevision.title}</h3>
          <p className="practices-meta">
            <span>学科 {currentRevision.subjectId}</span>
            <span>· 题量 {currentRevision.items.length}</span>
            <span>· 总分 {scoreText(currentRevision.totalScoreUnits)}</span>
            <span>· {tab === 'student' ? '学生卷' : '教师卷'}</span>
          </p>
          <div className="practices-paper-lines">
            <span>班级：__________</span>
            <span>姓名：__________</span>
            <span>学号：__________</span>
          </div>
        </header>
      );
    }
    if (segment.kind === 'answer-sheet') {
      return (
        <section className="practices-answer-sheet" key={segment.id} data-testid="practices-answer-sheet">
          <h3>答案页</h3>
          <ol>
            {paper.items.map((item) => (
              <li key={item.itemId}>
                <strong>第 {item.questionNo} 题</strong>
                <span>
                  <AnswerBlocks content={item.content} questionId={item.questionId} revisionId={currentRevision.practiceRevisionId} />
                </span>
              </li>
            ))}
          </ol>
        </section>
      );
    }
    const item = paper.items.find((entry) => entry.itemId === segment.itemIds[0]);
    if (!item) return null;
    const loadAsset = (assetId: string, signal: AbortSignal) => getQuestionAsset('question', item.questionId, assetId, signal);
    const hasOptions = Object.keys(item.content.optionBlocks).length > 0;
    return (
      <article className="practices-paper-question" key={segment.id} data-testid={`practices-paper-item-${item.itemId}`}>
        <div className="practices-paper-question-head">
          <strong>第 {item.questionNo} 题</strong>
          {item.isScored && item.maxScoreUnits !== null && <span className="practices-meta">（{scoreText(item.maxScoreUnits)} 分）</span>}
        </div>
        <RichReview
          content={item.content}
          loadAsset={loadAsset}
          assetScope={`${item.itemId}|${currentRevision.practiceRevisionId}`}
          teacher={tab === 'teacher'}
        />
        {tab === 'student' && (
          <div className={hasOptions ? 'practices-answer-line' : 'practices-answer-area'} aria-label={`第 ${item.questionNo} 题作答区`} data-testid={`practices-answer-space-${item.itemId}`}>
            {hasOptions ? <span className="practices-meta">作答：__________</span> : <span className="practices-meta">作答区</span>}
          </div>
        )}
      </article>
    );
  }

  return (
    <section className="practices-card" aria-label="导出预览" data-testid="practices-export">
      <header className="practices-card-head">
        <h2>导出预览</h2>
        <p className="practices-hint">
          已审核修订 v{revision.version} · {shortId(revision.practiceRevisionId)}
          {revision.reviewedAt ? ` · 审核于 ${revision.reviewedAt.slice(0, 16).replace('T', ' ')}` : ''}
          。预览按内容流分页、题不劈页，是版面估算；真实分页由后端导出服务生成。
        </p>
      </header>

      {reviewedRevisions.length > 1 && (
        <label className="practices-field">
          已审核修订
          <select
            className="space-select"
            data-testid="practices-revision-select"
            value={revision.practiceRevisionId}
            onChange={(event) => {
              setRevisionId(event.target.value);
              setOffset(0);
            }}
          >
            {reviewedRevisions.map((item) => (
              <option key={item.practiceRevisionId} value={item.practiceRevisionId}>
                v{item.version} · {shortId(item.practiceRevisionId)}
                {item.practiceRevisionId === view.currentRevision.practiceRevisionId ? '（当前）' : ''}
              </option>
            ))}
          </select>
        </label>
      )}

      <SlidingGroup activeKey={tab} variant="underline" className="practices-tabs" role="tablist" aria-label="卷面页签">
        {(['student', 'teacher'] as const).map((variant) => (
          <button
            key={variant}
            role="tab"
            id={`practices-tab-${variant}`}
            aria-selected={tab === variant}
            aria-controls={`practices-panel-${variant}`}
            tabIndex={tab === variant ? 0 : -1}
            className={tab === variant ? 'current' : ''}
            data-testid={`practices-tab-${variant}`}
            onClick={() => setTab(variant)}
            onKeyDown={(event) => {
              if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
                event.preventDefault();
                setTab(variant === 'student' ? 'teacher' : 'student');
              }
            }}
          >
            {variant === 'student' ? '学生卷' : '教师卷'}
          </button>
        ))}
      </SlidingGroup>

      <div className="practices-preview" id={`practices-panel-${tab}`} role="tabpanel" aria-labelledby={`practices-tab-${tab}`} data-testid="practices-preview">
        {layout.pages.map((page) => (
          <PaperSheet key={page.number} pageNumber={page.number}>
            {page.segments.map((segment) => renderSegment(segment))}
          </PaperSheet>
        ))}
      </div>

      <section className="practices-exports-actions" aria-label="生成导出">
        <div className="practices-actions">
          {(['student', 'teacher'] as const).map((variant) => (
            <button
              key={variant}
              className="space-button"
              data-testid={`practices-export-${variant}`}
              disabled={busy}
              onClick={() => void start(variant)}
            >
              生成{VARIANT_LABEL[variant]}
            </button>
          ))}
          <button
            className="space-button"
            data-testid="practices-export-score_template"
            disabled={busy || !convertedAssessmentId}
            title={convertedAssessmentId ? `施测 ${convertedAssessmentId}` : '需先转换为施测'}
            onClick={() => void start('score_template')}
          >
            生成{VARIANT_LABEL.score_template}
          </button>
          {submission.phase === 'unknown' && (
            <button
              className="space-button primary"
              disabled={submission.busy}
              onClick={() => void start(submission.frozen?.payload.body.variant ?? 'student')}
            >
              重试原导出提交
            </button>
          )}
        </div>
        {!convertedAssessmentId && (
          <p className="practices-hint" data-testid="practices-score-template-hint">
            成绩模板须先由该审核修订「转换为施测」后生成（本页不包含转换流程，转换入口在回流批次）。
          </p>
        )}
        <SubmissionNotice submission={submission} />
        <JobStatusNotice job={job.view} pending={job.pending !== null} onRetry={job.retry} onCancel={job.cancel}>
          {job.observing && <p role="status">正在观察导出任务…</p>}
        </JobStatusNotice>
        <ErrorNotice error={error} />
        {notice && (
          <p className="practices-hint" role="status" data-testid="practices-export-notice">
            {notice}
          </p>
        )}
      </section>

      <section className="practices-artifacts" aria-label="导出产物">
        <ReadArtifacts resource={artifacts} onDownload={download} downloading={downloading} busy={busy} />
        <div className="practices-actions">
          <button className="space-button" disabled={busy} onClick={artifacts.reload}>
            刷新产物历史
          </button>
        </div>
      </section>
    </section>
  );
}

function ReadArtifacts({ resource, onDownload, downloading, busy }: {
  resource: ReturnType<typeof useAsyncResource<Awaited<ReturnType<typeof b4Api.listPracticeExports>> | null>>;
  onDownload: (artifact: ExportArtifact) => void;
  downloading: string | null;
  busy: boolean;
}) {
  if (resource.state.phase === 'loading' && !resource.lastData) return <p role="status">正在读取导出产物…</p>;
  if (resource.state.phase === 'failed') {
    return (
      <>
        <ErrorNotice error={resource.state.error} />
        {resource.lastData && <p className="practices-hint">读取失败，以下保留上一次成功结果。</p>}
      </>
    );
  }
  const items = (resource.lastData?.items ?? []).filter((artifact) => artifact.variant in VARIANT_LABEL);
  if (items.length === 0) return <p className="practices-hint">此审核修订还没有成功的导出产物。</p>;
  return (
    <div className="practices-artifact-list">
      {items.map((artifact) => (
        <article key={artifact.artifactId} className="practices-artifact" data-testid={`practices-artifact-${artifact.variant}`}>
          <strong>{VARIANT_LABEL[artifact.variant]}</strong>
          <span className="practices-meta">
            {artifact.filename} · {artifact.byteSize} 字节 · {artifact.createdAt.slice(0, 16).replace('T', ' ')}
          </span>
          <button className="space-button" disabled={busy || downloading !== null} onClick={() => onDownload(artifact)}>
            {downloading === artifact.artifactId ? '下载中…' : `下载${VARIANT_LABEL[artifact.variant]}`}
          </button>
        </article>
      ))}
    </div>
  );
}
