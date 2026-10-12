'use client';

/**
 * 练习模块的展示原语（R8-FE 2026-10-12）。
 *
 * 重建期最小解耦：归档里这些组件来自共享 `@/features/learning-analysis/ui`（该文件随推倒重做
 * 删除，R6-FE 取回学情页时也未整体恢复共享件）。本模块只用到其中一小部分，按归档实现
 * **逐段同构**复刻所需子集（短号/名称回落、错误与提交提示、分页、富内容只读复核），
 * 富内容渲染改经 R4-FE 的题库公共件 `@/features/question-bank/rich-content`（类型来源
 * `@/contracts/question-bank` 的 `RichContentV2`），**不新增主题、不发明字段**。
 *
 * 纪律：所有回落都是「名称优先，缺失给短号/明确文案」，不伪造名称、不把失败当空数据。
 */

import type { ReactNode } from 'react';
import type { ApiError } from '@/services/api-client';
import type { AsyncResource, SubmissionController } from '@/features/assessments/hooks';
import type { RichContentV2 } from '@/contracts/question-bank';
import type { ContentBlock } from '@/contracts/question-bank';
import {
  RichBlocks,
  RichContentRenderer,
  type RichAssetLoader,
} from '@/features/question-bank/rich-content';

/** 分值单位（后端以 1/100 分存储）：整数分不带小数，非整数保留两位；缺失给「—」。 */
export function scoreText(units: number | null): string {
  return units === null ? '—' : (units / 100).toFixed(2).replace(/\.00$/, '');
}

/** 短号：长 ID 只留前 8 位并加省略号；缺失给「—」，不伪造身份。 */
export function shortId(id: string | null | undefined, length = 8): string {
  if (!id) return '—';
  return id.length <= length ? id : `${id.slice(0, length)}…`;
}

/** 名称优先：名称非空用名称，否则回落短号（名称缺失不猜造、不用占位名）。 */
export function nameOrShortId(name: string | null | undefined, id: string | null | undefined): string {
  const trimmed = typeof name === 'string' ? name.trim() : '';
  return trimmed !== '' ? trimmed : shortId(id);
}

/**
 * 时间显示：后端 ISO 串原样截取（`2026-10-02T09:30:00Z` → `2026-10-02 09:30`），
 * 不做时区换算，避免把 UTC 值伪装成本地时间；缺失回落「时间未记录」而不猜造。
 */
export function stampText(value: string | null | undefined): string {
  if (!value) return '时间未记录';
  const match = /^(\d{4}-\d{2}-\d{2})(?:[T ](\d{2}:\d{2}))?/.exec(value);
  if (!match) return value;
  return match[2] ? `${match[1]} ${match[2]}` : match[1];
}

export function ErrorNotice({ error }: { error: ApiError | null }) {
  if (!error) return null;
  return (
    <div className="space-banner error" role="alert">
      <strong>{error.code}</strong>：{error.message}
      {error.requestId && <span className="practices-meta">请求 {error.requestId}</span>}
      {error.details?.currentRevision !== undefined && (
        <p>服务器当前编辑版本：{String(error.details.currentRevision)}。输入已保留，请核对新版本。</p>
      )}
      {error.details?.issues?.map((issue, index) => (
        <p key={index}>
          {issue.field ?? ''}
          {issue.row !== undefined ? ` 第${issue.row + 1}项` : ''}：{issue.message}
        </p>
      ))}
    </div>
  );
}

export function ReadNotice<T>({ resource, label }: { resource: AsyncResource<T>; label: string }) {
  return (
    <>
      {resource.state.phase === 'loading' && <p role="status">正在读取{label}…</p>}
      {resource.state.phase === 'failed' && (
        <>
          <ErrorNotice error={resource.state.error} />
          {resource.lastData !== null && <p className="practices-hint">读取失败，以下保留上一次成功结果。</p>}
          <button className="space-button" onClick={resource.reload}>
            重试读取{label}
          </button>
        </>
      )}
    </>
  );
}

export function SubmissionNotice<T, R>({ submission }: { submission: SubmissionController<T, R> }) {
  return (
    <>
      <ErrorNotice error={submission.error} />
      {submission.unknownNotice && (
        <p className="space-banner" role="alert">
          {submission.unknownNotice} 原提交的对象、版本和内容已锁定。
        </p>
      )}
      {submission.busy && <p role="status">正在提交，请稍候…</p>}
    </>
  );
}

export function Pagination({ total, limit, offset, onOffset, disabled = false }: {
  total: number;
  limit: number;
  offset: number;
  onOffset: (offset: number) => void;
  disabled?: boolean;
}) {
  return (
    <div className="practices-actions" aria-label="分页">
      <span className="practices-meta">
        共 {total} 条 · 第 {Math.floor(offset / limit) + 1} 页 · 每页 {limit}
      </span>
      <button className="space-button" disabled={disabled || offset === 0} onClick={() => onOffset(Math.max(0, offset - limit))}>
        上一页
      </button>
      <button className="space-button" disabled={disabled || offset + limit >= total} onClick={() => onOffset(offset + limit)}>
        下一页
      </button>
    </div>
  );
}

export interface JobViewLike {
  jobId: string;
  state: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled' | 'interrupted';
  /** 尝试号；缺省 = 服务端未给出（缺省不按 0 展示，界面给「尝试号未记录」）。 */
  attempt?: number;
  /** 任务错误信封（缺省 = 服务端未给出；缺省与 null 都按「无错误」展示）。 */
  error?: { code: string; message: string } | null;
}

const JOB_LABEL: Record<JobViewLike['state'], string> = {
  queued: '已接受，排队中',
  running: '正在执行',
  succeeded: '任务成功',
  failed: '任务失败',
  cancelled: '任务已取消',
  interrupted: '任务已中断',
};

/** 任务状态提示：`202` 只代表接受任务，绝不等于产物已就绪。 */
export function JobStatusNotice({ job, onRetry, onCancel, pending, children }: {
  job: JobViewLike | null;
  onRetry?: () => void;
  onCancel?: () => void;
  pending?: boolean;
  children?: ReactNode;
}) {
  if (!job) return null;
  const terminalFailure = ['failed', 'cancelled', 'interrupted'].includes(job.state);
  const active = job.state === 'queued' || job.state === 'running';
  return (
    <section className="practices-job" aria-label="任务状态" aria-live="polite">
      <strong>{JOB_LABEL[job.state]}</strong>
      <span className="practices-meta">
        任务 {job.jobId} · {typeof job.attempt === 'number' ? `尝试 ${job.attempt}` : '尝试号未记录'}
      </span>
      {active && <p className="practices-hint">接受任务不等于文件已经准备好；失败不会自动重试。</p>}
      {(onRetry || onCancel) && (
        <div className="practices-actions">
          {terminalFailure && onRetry && (
            <button className="space-button" disabled={pending} onClick={onRetry}>
              重试此任务
            </button>
          )}
          {active && onCancel && (
            <button className="space-button" disabled={pending} onClick={onCancel}>
              取消此任务
            </button>
          )}
        </div>
      )}
      {job.error && (
        <div className="space-banner error" role="alert">
          {job.error.code}：{job.error.message}
        </div>
      )}
      {children}
    </section>
  );
}

export function isRichContent(value: unknown): value is RichContentV2 {
  if (!value || typeof value !== 'object') return false;
  const content = value as Partial<RichContentV2>;
  return (
    content.version === 2 &&
    Array.isArray(content.stemBlocks) &&
    Array.isArray(content.sharedMaterials) &&
    !!content.optionBlocks &&
    Array.isArray(content.answerBlocks) &&
    Array.isArray(content.explanationBlocks) &&
    Array.isArray(content.assets) &&
    !!content.origin
  );
}

/** 仅组合既有 renderer；答案区按显式教师视图显示，学生视图不挂载答案块。 */
export function RichReview({ content, loadAsset, assetScope, teacher = true }: {
  content: RichContentV2;
  loadAsset?: RichAssetLoader;
  assetScope: string;
  teacher?: boolean;
}) {
  return (
    <div className="practices-rich">
      <RichContentRenderer content={content} loadAsset={loadAsset} assetScope={assetScope} />
      {Object.entries(content.optionBlocks).map(([key, blocks]) => (
        <div key={key} className="practices-option">
          <strong>{key}</strong>
          <RichBlocks blocks={blocks} loadAsset={loadAsset} assetScope={assetScope} />
        </div>
      ))}
      {teacher && (
        <>
          <h4>教师答案</h4>
          {content.answerBlocks.length ? (
            <RichBlocks blocks={content.answerBlocks} loadAsset={loadAsset} assetScope={assetScope} />
          ) : (
            <p>未提供答案</p>
          )}
          <h4>解析</h4>
          {content.explanationBlocks.length ? (
            <RichBlocks blocks={content.explanationBlocks} loadAsset={loadAsset} assetScope={assetScope} />
          ) : (
            <p>未提供解析</p>
          )}
        </>
      )}
    </div>
  );
}

/** 题面块（题干 + 全部选项），用于计分节点的显式块分配。 */
export function surfaceBlocks(content: RichContentV2): ContentBlock[] {
  return [...content.stemBlocks, ...Object.values(content.optionBlocks).flat()];
}
