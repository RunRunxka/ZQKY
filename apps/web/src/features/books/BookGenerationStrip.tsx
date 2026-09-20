'use client';
import { useEffect, useState } from 'react';
import { ChevronDown, Loader2, Pause, Play, RefreshCcw } from 'lucide-react';
import type { BookChapter, ReplicaBook } from '@/services/books-store';
import '@/features/books/styles/book-pipeline.css';

/**
 * 生成活动条（对照参考 BookGenerationActivity；H1-BOOKS-PIPELINE I2）。
 * 单行 46px、role=status aria-live=polite：阶段文案 + n/m 章 + mm:ss 计时 + 右侧控制。
 * 阶段按队长裁定只呈现两段：准备（大纲已就绪·模拟）与逐章编译，不伪造参考 6 阶段进度。
 * 计时为本地 1s 定时器，仅在有活跃执行器时推进（对照参考 backendWorking 才计时）。
 * 所有生成行为均为本地模拟执行器驱动，不调用模型。
 */

export type BookStripPhase = 'preparing' | 'compilation' | 'paused' | 'interrupted';

export interface BookStripChapterState {
  key: string;
  /** 章标题（含序号呈现） */
  label: string;
  /** 完成块数 / 总块数 */
  doneBlocks: number;
  totalBlocks: number;
  /** 正在生成的块名（当前块） */
  generatingBlock: string | null;
  /** 本章是否有失败块（含整页失败） */
  hasFailure: boolean;
  /** 本章是否仍处于未完成（等待/生成中/失败待处理） */
  active: boolean;
}

export interface BookGenerationStripProps {
  phase: BookStripPhase;
  /** 有活跃执行器（本标签页在跑） */
  working: boolean;
  /** 完成章数 / 总章数（章视为完成=该章所有页 ready） */
  doneChapters: number;
  totalChapters: number;
  /** 运行起点（run.startedAt，毫秒）；未知传 null（不显示计时，避免用渲染期时间冒充运行起点） */
  startedAt: number | null;
  chapters: BookStripChapterState[];
  /** 用户暂停（运行中按下后的忙态） */
  pausing: boolean;
  /** 恢复按钮忙态（恢复中…） */
  resuming: boolean;
  /** 是否由其他标签页执行（本标签只读） */
  remote?: boolean;
  onPause: () => void;
  onResume: () => void;
}

/** 计时格式（对照参考 book-progress.ts :138-146：mm:ss，超 1 小时 h:mm:ss） */
export function formatRunElapsed(ms: number): string {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  const mm = String(minutes).padStart(2, '0');
  const ss = String(seconds).padStart(2, '0');
  return hours > 0 ? `${hours}:${mm}:${ss}` : `${mm}:${ss}`;
}

export function BookGenerationStrip(props: BookGenerationStripProps) {
  const { phase, working, doneChapters, totalChapters, startedAt, chapters } = props;
  const [now, setNow] = useState(() => Date.now());
  const [open, setOpen] = useState(false);

  // 计时器只在有活跃执行器时推进（本地 1s tick）
  useEffect(() => {
    if (!working) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(timer);
  }, [working]);

  if (phase === 'paused' || phase === 'interrupted') {
    if (doneChapters >= totalChapters && totalChapters > 0) return null;
  }

  const settled = phase === 'paused' || phase === 'interrupted';
  const stageText =
    phase === 'preparing'
      ? '准备（大纲已就绪·模拟）…'
      : phase === 'paused'
        ? '生成已暂停'
        : phase === 'interrupted'
          ? '生成已中断（无执行器在跑）'
          : '正在逐章编译（本地模拟，不调用模型）…';
  const elapsed = startedAt === null ? null : formatRunElapsed(Math.max(0, now - startedAt));

  const showPause = working && !settled;
  // 「继续生成」用于"没有执行器在跑但本可继续"的两态：编译中无执行器、已中断
  // （对照参考 :203-223：interrupted 用 RefreshCcw + Continue generating）。
  // 「恢复生成」只属于 paused（用户/模拟供应商暂停后必须显式恢复）。
  const showContinue = !working && (phase === 'compilation' || phase === 'interrupted');
  const showResume = phase === 'paused';

  return (
    // 外壳负责锚定浮层（对照参考 BookGenerationActivity 的 `relative` 包裹层）：
    // 46px 单行条本身是 overflow:hidden 的 flex 行，浮层若作为它的子节点会被裁成一条线。
    <div className="book-pipeline-strip-shell">
      <div className="book-pipeline-strip" role="status" aria-live="polite">
        <span className={`book-pipeline-strip-status${settled ? '' : ' breathing'}`}>
          <span className="book-pipeline-strip-stage">{stageText}</span>
          <span className="book-pipeline-strip-chapters">
            {doneChapters}/{totalChapters} 章
          </span>
          {elapsed !== null && (
            <span className="book-pipeline-strip-timer" aria-label={`已运行 ${elapsed}`}>
              {elapsed}
            </span>
          )}
        </span>
        <span className="book-pipeline-strip-controls">
          {props.remote && <span className="book-pipeline-progress">本书正在另一个标签页生成</span>}
          {showPause && (
            <button className="space-button" onClick={props.onPause} disabled={props.pausing}>
              {props.pausing ? (
                <Loader2 size={13} className="space-spin" aria-hidden />
              ) : (
                <Pause size={13} aria-hidden />
              )}
              {props.pausing ? '正在暂停…' : '暂停生成'}
            </button>
          )}
          {showContinue && (
            <button className="space-button" onClick={props.onResume} disabled={props.resuming}>
              {props.resuming ? (
                <Loader2 size={13} className="space-spin" aria-hidden />
              ) : (
                <RefreshCcw size={13} aria-hidden />
              )}
              {props.resuming ? '正在继续…' : '继续生成'}
            </button>
          )}
          {showResume && (
            <button className="space-button" onClick={props.onResume} disabled={props.resuming}>
              {props.resuming ? (
                <Loader2 size={13} className="space-spin" aria-hidden />
              ) : (
                <Play size={13} aria-hidden />
              )}
              {props.resuming ? '正在恢复…' : '恢复生成'}
            </button>
          )}
          <button
            type="button"
            className="book-pipeline-strip-toggle"
            data-open={open}
            aria-expanded={open}
            aria-controls="book-pipeline-detail"
            onClick={() => setOpen((value) => !value)}
          >
            已生成内容
            <ChevronDown size={13} className="book-pipeline-strip-toggle-chevron" aria-hidden />
          </button>
        </span>
      </div>
      {open && (
        // 定位层（对照参考：`absolute inset-x-0 top-full z-40 flex justify-center`）覆盖在正文之上，
        // 不参与活动条的高度协商，也不受 46px 行的 overflow 裁切。
        <div className="book-pipeline-detail-layer">
          <div
            id="book-pipeline-detail"
            className="book-pipeline-detail"
            role="dialog"
            aria-label="已生成内容"
          >
            <div className="book-pipeline-detail-body">
              <p className="book-pipeline-detail-title">章节</p>
              {chapters.map((chapter) => (
                <div className="book-pipeline-detail-chapter" key={chapter.key}>
                  <span
                    className={`book-pipeline-dot${
                      chapter.hasFailure
                        ? ' error'
                        : chapter.generatingBlock
                          ? ' running'
                          : chapter.active
                            ? ''
                            : ' done'
                    }`}
                    aria-hidden
                  />
                  <span className="book-pipeline-detail-chapter-title">{chapter.label}</span>
                  <span
                    className={`book-pipeline-detail-chapter-state${
                      chapter.hasFailure ? ' error' : ''
                    }`}
                  >
                    {chapter.hasFailure
                      ? '部分块失败'
                      : chapter.generatingBlock
                        ? `正在生成 ${chapter.generatingBlock}`
                        : chapter.active
                          ? '排队'
                          : `已完成 ${chapter.doneBlocks}/${chapter.totalBlocks} 块`}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

/** 从书籍记录派生活动条所需的章级状态（读取期派生，不写回） */
export function deriveStripChapters(
  book: ReplicaBook,
  chapters: BookChapter[],
  pageStateOf: (pageId: string) => {
    status: 'pending' | 'planning' | 'generating' | 'ready' | 'partial' | 'error';
    generatingBlockTitle: string | null;
  },
): BookStripChapterState[] {
  return chapters.map((chapter, index) => {
    let doneBlocks = 0;
    let totalBlocks = 0;
    let generatingBlock: string | null = null;
    let hasFailure = false;
    let allReady = true;
    for (const pageId of chapter.pageIds) {
      const page = (book as unknown as { pages?: { id: string; blocks: { status?: string; title?: string; failure?: unknown }[] }[] }).pages?.find(
        (item) => item.id === pageId,
      );
      const state = pageStateOf(pageId);
      if (state.status === 'error') {
        hasFailure = true;
        allReady = false;
      }
      if (state.status === 'partial') hasFailure = true;
      if (state.status !== 'ready') allReady = false;
      for (const block of page?.blocks ?? []) {
        totalBlocks += 1;
        const status = block.status ?? 'ready';
        if (status === 'ready') doneBlocks += 1;
        if (status === 'error') hasFailure = true;
        if (status === 'generating' && !generatingBlock) {
          generatingBlock = block.title ?? '本页内容';
        }
      }
      if (!generatingBlock && state.status === 'generating' && page?.blocks.length) {
        const active = page.blocks.find((block) => (block.status ?? 'ready') !== 'ready');
        generatingBlock = active?.title ?? '本页内容';
      }
    }
    return {
      key: chapter.id,
      label: `${String(index + 1).padStart(2, '0')} · ${chapter.title}`,
      doneBlocks,
      totalBlocks,
      generatingBlock,
      hasFailure,
      active: !allReady,
    };
  });
}
