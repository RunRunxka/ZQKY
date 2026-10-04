'use client';

import type { ReactNode } from 'react';
import type { ApiError } from '@/services/api-client';
import type { AsyncResource, SubmissionController } from '@/features/assessments/hooks';
import type { Page } from '@/contracts/b4';
import type { JobView, Observation, RichContentV2, ContentBlock } from '@/contracts/teaching-loop';
import { RichContentRenderer, RichBlocks, type RichAssetLoader } from '@/components/ui/RichContentRenderer';

export const observationLabel: Record<Observation, string> = {
  needs_consolidation: '本次需巩固', full_credit: '本次有效证据均为满分',
  incomplete: '信息不全', no_evidence: '暂无有效依据',
};
export const statusLabel = { recorded: '有效记录', missing: '空白', absent: '缺考', exempt: '免考' };
export const attendanceLabel = { present: '参加', absent: '缺考', exempt: '免考' };
export function scoreText(units: number | null) { return units === null ? '—' : (units / 100).toFixed(2).replace(/\.00$/, ''); }

export function ErrorNotice({ error }: { error: ApiError | null }) {
  if (!error) return null;
  return <div className="space-banner error" role="alert">
    <strong>{error.code}</strong>：{error.message}
    {error.requestId && <span className="b4-meta">请求 {error.requestId}</span>}
    {error.details?.currentRevision !== undefined && <p>服务器当前编辑版本：{String(error.details.currentRevision)}。输入已保留，请核对新版本。</p>}
    {error.details?.issues?.map((issue, index) => <p key={index}>{issue.field ?? ''}{issue.row !== undefined ? ` 第${issue.row + 1}项` : ''}：{issue.message}</p>)}
  </div>;
}

export function ReadNotice<T>({ resource, label }: { resource: AsyncResource<T>; label: string }) {
  return <>
    {resource.state.phase === 'loading' && <p role="status">正在读取{label}…</p>}
    {resource.state.phase === 'failed' && <><ErrorNotice error={resource.state.error} />
      {resource.lastData !== null && <p className="b4-hint">读取失败，以下保留上一次成功结果。</p>}
      <button className="space-button" onClick={resource.reload}>重试读取{label}</button></>}
  </>;
}

export function SubmissionNotice<T, R>({ submission }: { submission: SubmissionController<T, R> }) {
  return <><ErrorNotice error={submission.error} />
    {submission.unknownNotice && <p className="space-banner" role="alert">{submission.unknownNotice} 原提交的对象、版本和内容已锁定。</p>}
    {submission.busy && <p role="status">正在提交，请稍候…</p>}</>;
}

export function Pagination<T>({ page, offset, onOffset, disabled = false }: {
  page: Page<T> | null; offset: number; onOffset: (offset: number) => void; disabled?: boolean;
}) {
  if (!page) return null;
  return <div className="b4-actions" aria-label="分页">
    <span className="b4-meta">共 {page.total} 条 · 第 {Math.floor(offset / page.limit) + 1} 页 · 每页 {page.limit}</span>
    <button className="space-button" disabled={disabled || offset === 0} onClick={() => onOffset(Math.max(0, offset - page.limit))}>上一页</button>
    <button className="space-button" disabled={disabled || offset + page.limit >= page.total} onClick={() => onOffset(offset + page.limit)}>下一页</button>
  </div>;
}

type JobController = {
  view: JobView | null; observing: boolean; pending: 'retry' | 'cancel' | null;
  actionError: ApiError | null; observationNotice: string | null;
  retry: () => void; cancel: () => void;
};
const jobLabel = { queued: '已接受，排队中', running: '正在执行', succeeded: '任务成功', failed: '任务失败', cancelled: '任务已取消', interrupted: '任务已中断' };
export function JobStatus({ job, children }: { job: JobController; children?: ReactNode }) {
  const view = job.view;
  if (!view) return null;
  return <section className="b4-job" aria-label="任务状态" aria-live="polite">
    <strong>{jobLabel[view.state]}</strong><span className="b4-meta">任务 {view.jobId} · 尝试 {view.attempt}</span>
    {(view.state === 'queued' || view.state === 'running') && <p className="b4-hint">接受任务不等于报告或文件已经准备好。</p>}
    <div className="b4-actions">
      {['failed', 'cancelled', 'interrupted'].includes(view.state) && <button className="space-button" disabled={job.pending !== null} onClick={job.retry}>重试此任务</button>}
      {['queued', 'running'].includes(view.state) && <button className="space-button" disabled={job.pending !== null} onClick={job.cancel}>取消此任务</button>}
      {job.pending && <span role="status">正在{job.pending === 'retry' ? '重试' : '请求取消'}…</span>}
    </div>
    {view.error && <div className="space-banner error" role="alert">{view.error.code}：{view.error.message}</div>}
    <ErrorNotice error={job.actionError} />
    {job.observationNotice && <p role="status">{job.observationNotice}</p>}{children}
  </section>;
}

export function isRichContent(value: unknown): value is RichContentV2 {
  if (!value || typeof value !== 'object') return false;
  const content = value as Partial<RichContentV2>;
  return content.version === 2 && Array.isArray(content.stemBlocks) && Array.isArray(content.sharedMaterials)
    && !!content.optionBlocks && Array.isArray(content.answerBlocks) && Array.isArray(content.explanationBlocks)
    && Array.isArray(content.assets) && !!content.origin;
}

/** 仅组合既有 renderer；答案区按显式教师视图显示，学生视图不挂载答案块。 */
export function RichReview({ content, loadAsset, assetScope, teacher = true }: {
  content: RichContentV2; loadAsset?: RichAssetLoader; assetScope: string; teacher?: boolean;
}) {
  return <div className="b4-rich">
    <RichContentRenderer content={content} loadAsset={loadAsset} assetScope={assetScope} />
    {Object.entries(content.optionBlocks).map(([key, blocks]) => <div key={key} className="b4-option"><strong>{key}</strong><RichBlocks blocks={blocks} loadAsset={loadAsset} assetScope={assetScope} /></div>)}
    {teacher && <><h4>教师答案</h4>{content.answerBlocks.length ? <RichBlocks blocks={content.answerBlocks} loadAsset={loadAsset} assetScope={assetScope} /> : <p>未提供答案</p>}
      <h4>解析</h4>{content.explanationBlocks.length ? <RichBlocks blocks={content.explanationBlocks} loadAsset={loadAsset} assetScope={assetScope} /> : <p>未提供解析</p>}</>}
  </div>;
}

export function surfaceBlocks(content: RichContentV2): ContentBlock[] {
  return [...content.stemBlocks, ...Object.values(content.optionBlocks).flat()];
}
