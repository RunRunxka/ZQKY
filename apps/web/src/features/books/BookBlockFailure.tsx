'use client';
import { AlertTriangle } from 'lucide-react';
import type { BlockFailure, BookBlock, BookBlockType, BookFailureKind } from '@/services/books-store';

/**
 * 块失败卡（H1-BOOKS-PIPELINE I3；对照参考 BlockRenderer error 分支）：
 * AlertTriangle + 「<类型> 块生成失败」+ 分类（含不可重试标记）+ 原因 + 「重试」。
 * 分类文案本地化并标注本地模拟；不把局部失败归因为“供应商错误”。
 */

/** 失败分类标签（本地化；对照参考 failure.kind 的可用子集，句子用中文并标注本地模拟） */
export function bookFailureKindLabel(kind: BookFailureKind | undefined): string {
  switch (kind) {
    case 'content':
      return '内容生成失败（本地模拟）';
    case 'storage':
      return '本地存储写入失败';
    case 'internal':
      return '内部错误（本地模拟）';
    default:
      return '未知错误（本地模拟）';
  }
}

export function BookBlockFailure({
  block,
  busy,
  retryDisabled,
  onRetry,
}: {
  block: BookBlock;
  busy: boolean;
  retryDisabled: boolean;
  onRetry: () => void;
}) {
  const failure: BlockFailure | undefined = block.failure;
  const kindText = bookFailureKindLabel(failure?.kind);
  const metaLine = failure && failure.retryable === false ? `${kindText} · 不可重试` : kindText;
  // 不可重试标记同时进入禁用态与 title（屏幕阅读器与悬停均可见）
  const notRetryable = failure?.retryable === false;
  return (
    <div className="book-reader-block-failure" role="alert">
      <div className="book-reader-block-failure-title">
        <AlertTriangle size={14} aria-hidden />
        <strong>{blockTypeName(block.type)} 块生成失败</strong>
      </div>
      <div className="book-reader-block-failure-meta">{metaLine}</div>
      <div className="book-reader-block-failure-message">
        {failure?.message ?? '未知错误（本地模拟）'}
      </div>
      <button
        type="button"
        className="space-button"
        disabled={retryDisabled || busy || notRetryable}
        aria-disabled={retryDisabled || busy || notRetryable ? 'true' : undefined}
        title={notRetryable ? '该失败不可重试（本地模拟）' : undefined}
        onClick={onRetry}
      >
        {busy ? '正在重试…' : '重试'}
      </button>
    </div>
  );
}

/** 块类型中文标签（对照参考 t(block.type)） */
function blockTypeName(type: BookBlockType): string {
  const names: Record<BookBlockType, string> = {
    text: '文本',
    section: '小节',
    callout: '提示',
    quiz: '练习',
    placeholder: '占位',
    code: '代码',
    timeline: '时间线',
    flash_cards: '记忆卡',
    figure: '插图',
    user_note: '笔记',
    deep_dive: '深入探究',
    concept_graph: '概念图',
    interactive: '互动组件',
    animation: '动画',
  };
  return names[type] ?? '未知';
}
