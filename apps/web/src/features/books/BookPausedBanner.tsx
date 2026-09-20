'use client';
import { Loader2, Play } from 'lucide-react';
import '@/features/books/styles/book-pipeline.css';

/**
 * 生成暂停横幅（对照参考 BookPausedBanner；H1-BOOKS-PIPELINE I2）。
 * 按 pauseKind 分叉说明；provider 类必须写明是本地模拟的供应商连续失败，
 * 不得宣称真实上游故障。恢复按钮：恢复生成 / 正在恢复…（描边按钮）。
 */

export interface BookPausedBannerProps {
  pauseKind: 'user' | 'provider';
  pauseReason?: string | null;
  resuming: boolean;
  onResume: () => void;
}

const PAUSE_TEXT: Record<'user' | 'provider', string> = {
  user: '生成已暂停。已生成的内容全部保留，未完成的章节只在你恢复后才会继续（本地模拟执行器，不调用模型）。',
  provider:
    '本地模拟的供应商连续失败，生成已暂停：剩余章节未被半写，已生成的内容全部保留。这是显式模拟的暂停场景，不代表真实上游服务故障。',
};

export function BookPausedBanner({ pauseKind, pauseReason, resuming, onResume }: BookPausedBannerProps) {
  return (
    <div className="book-pipeline-paused">
      <span className="book-pipeline-paused-title">
        <Play size={14} aria-hidden />
        生成已暂停
      </span>
      <p className="book-pipeline-paused-text">{PAUSE_TEXT[pauseKind]}</p>
      {pauseReason ? <code className="book-pipeline-paused-reason">{pauseReason}</code> : null}
      <div className="book-pipeline-paused-actions">
        <button className="space-button" onClick={onResume} disabled={resuming}>
          {resuming ? (
            <Loader2 size={13} className="space-spin" aria-hidden />
          ) : (
            <Play size={13} aria-hidden />
          )}
          {resuming ? '正在恢复…' : '恢复生成'}
        </button>
      </div>
    </div>
  );
}
