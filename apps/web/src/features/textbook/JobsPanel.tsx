'use client';

/**
 * 入库任务面板：服务端任务列表（阶段、进度、错误、取消/重试）。
 * 仅在面板打开（组件挂载）时轮询，关闭即停；失败保留上一次列表并以 `role="alert"` 报错。
 */

import { useCallback, useEffect, useState } from 'react';
import { Modal } from '@/components/ui/Modal';
import type { JobList, JobView } from '@/contracts/textbook';
import { cancelJob, listJobs, retryJob } from '@/services/textbook-api';
import { asApiError, usePolling, type AsyncState } from './hooks';
import { isJobActive, jobKindLabel, jobStateLabel, progressPercent } from './labels';

export function JobsPanel({
  onClose,
  pollIntervalMs = 2000,
}: {
  onClose: () => void;
  /** 轮询间隔（生产默认 2s；测试可缩小）。 */
  pollIntervalMs?: number;
}) {
  const [state, setState] = useState<AsyncState<JobList>>({ phase: 'loading' });
  const [pollError, setPollError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [busyJobId, setBusyJobId] = useState<string | null>(null);

  const load = useCallback(async (background: boolean) => {
    if (!background) setState({ phase: 'loading' });
    try {
      const data = await listJobs();
      setState({ phase: 'ready', data });
      setPollError(null);
    } catch (error) {
      const apiError = asApiError(error);
      if (background) setPollError(apiError.message);
      else setState({ phase: 'failed', error: apiError });
    }
  }, []);

  useEffect(() => {
    void load(false);
  }, [load]);
  usePolling(() => load(true), true, pollIntervalMs);

  async function runAction(job: JobView, action: 'cancel' | 'retry') {
    setBusyJobId(job.jobId);
    setActionError(null);
    try {
      if (action === 'cancel') await cancelJob(job.jobId);
      else await retryJob(job.jobId);
      await load(true);
    } catch (error) {
      setActionError(
        `${action === 'cancel' ? '取消' : '重试'}任务 ${job.jobId} 失败：${asApiError(error).message}`,
      );
    } finally {
      setBusyJobId(null);
    }
  }

  return (
    <Modal title="入库任务" onClose={onClose}>
      <div className="textbook-panel textbook-jobs">
        <p className="textbook-hint">
          任务状态与进度来自服务端（`/textbook-jobs`）；本面板打开时轮询，关闭即停止。
        </p>

        {state.phase === 'loading' && (
          <div aria-hidden>
            {[0, 1].map((index) => (
              <div className="space-skeleton" key={index} style={{ height: 72 }} />
            ))}
          </div>
        )}

        {state.phase === 'failed' && (
          <div className="space-banner error" role="alert">
            入库任务读取失败：{state.error.message}
            <div className="textbook-panel-actions">
              <button className="space-button" onClick={() => void load(false)}>
                重试
              </button>
            </div>
          </div>
        )}

        {pollError && state.phase === 'ready' && (
          <div className="space-banner error" role="alert">
            轮询失败（显示的是上一次成功读取的结果）：{pollError}
            <div className="textbook-panel-actions">
              <button className="space-button" onClick={() => void load(true)}>
                立即刷新
              </button>
            </div>
          </div>
        )}

        {actionError && (
          <div className="space-banner error" role="alert">
            {actionError}
          </div>
        )}

        {state.phase === 'ready' && state.data.jobs.length === 0 && (
          <div className="space-empty">
            <strong>还没有入库任务</strong>
            <span>从「导入教材」上传并提交后，任务会出现在这里。</span>
          </div>
        )}

        {state.phase === 'ready' && state.data.jobs.length > 0 && (
          <ul className="textbook-job-list">
            {state.data.jobs.map((job) => {
              const documentPercent = progressPercent(
                job.progress.documentsDone,
                job.progress.documentsTotal,
              );
              const chunkPercent = progressPercent(
                job.progress.chunksDone,
                job.progress.chunksTotal,
              );
              return (
                <li className="textbook-job-item" key={job.jobId}>
                  <div className="textbook-job-head">
                    <strong>
                      {jobKindLabel(job.kind)} · {job.jobId}
                    </strong>
                    <span
                      className={`space-chip ${
                        job.state === 'succeeded'
                          ? 'green'
                          : job.state === 'failed'
                            ? 'amber'
                            : 'blue'
                      }`}
                    >
                      {jobStateLabel(job.state)}
                    </span>
                  </div>
                  <div className="space-meta-row">
                    <span className="space-chip">
                      已完成教材 {job.progress.documentsDone}/{job.progress.documentsTotal}
                    </span>
                    <span className="space-chip">
                      已完成块 {job.progress.chunksDone}/{job.progress.chunksTotal}
                    </span>
                    {job.progress.currentTitle && (
                      <span className="space-chip">当前：{job.progress.currentTitle}</span>
                    )}
                    <span className="space-chip">第 {job.attempt} 次尝试</span>
                  </div>
                  <div
                    className="textbook-progress"
                    role="progressbar"
                    aria-label={`教材进度 ${job.jobId}`}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={documentPercent}
                  >
                    <div style={{ width: `${documentPercent}%` }} />
                  </div>
                  <div
                    className="textbook-progress"
                    role="progressbar"
                    aria-label={`分块进度 ${job.jobId}`}
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={chunkPercent}
                  >
                    <div style={{ width: `${chunkPercent}%` }} />
                  </div>
                  {job.errorCode || job.errorMessage ? (
                    <p className="textbook-job-error">
                      错误：{job.errorCode ? `${job.errorCode} · ` : ''}
                      {job.errorMessage ?? '（服务端未提供原因说明）'}
                    </p>
                  ) : null}
                  <div className="textbook-panel-actions">
                    {isJobActive(job.state) && (
                      <button
                        className="space-button"
                        onClick={() => void runAction(job, 'cancel')}
                        disabled={busyJobId === job.jobId}
                      >
                        取消任务
                      </button>
                    )}
                    {job.state === 'failed' && job.retryable && (
                      <button
                        className="space-button"
                        onClick={() => void runAction(job, 'retry')}
                        disabled={busyJobId === job.jobId}
                      >
                        重试任务
                      </button>
                    )}
                    {job.state === 'failed' && !job.retryable && (
                      <span className="textbook-hint">该任务不可自动重试（原因见上方错误）。</span>
                    )}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </div>
    </Modal>
  );
}
