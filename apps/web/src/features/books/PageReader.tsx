'use client';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Bookmark, ChevronLeft, ChevronRight, Copy, Loader2, RefreshCcw } from 'lucide-react';
import {
  latestQuizAttempt,
  markVisited,
  quizAttemptMatches,
  recordQuizAttempt,
  setUserNote,
  toggleBookmark,
  type BlockStatus,
  type BookBlock,
  type BookPage,
  type BookQuizAttempt,
  type PageStatus,
  type ReplicaBook,
} from '@/services/books-store';
import { BookBlockFailure, bookFailureKindLabel } from './BookBlockFailure';
import {
  getRepair,
  regeneratePage as regeneratePageRun,
  retryBlock as retryBlockRun,
  startRun as startRunRun,
  type BookRunHandle,
  type RepairResult,
} from '@/services/book-generation';
import '@/features/books/books.css';
import '@/features/books/styles/book-reader-states.css';

// ===== 流水线状态视图（H1-BOOKS-PIPELINE I3） =====
// 类型与判定来自 books-store §4.1/4.2 冻结契约（I1 已落地导出）；
// 本文件只做“读取不写回”的派生渲染（缺 status 按 ready）。

type PipelinePage = BookPage;
type PipelineBlock = BookBlock;

function pageStatusOf(page: PipelinePage | undefined): PageStatus {
  return page?.status ?? 'ready';
}

/** 块状态：块自身显式 status 优先；页骨架态下未完成块跟随页；旧数据缺 status 按 ready */
function blockStatusOf(page: PipelinePage | undefined, block: PipelineBlock): BlockStatus {
  if (block.status) return block.status;
  const pageStatus = pageStatusOf(page);
  if (pageStatus === 'pending' || pageStatus === 'planning') return 'pending';
  if (pageStatus === 'generating') return 'generating';
  return 'ready';
}

function failedBlocksOf(page: PipelinePage | undefined): PipelineBlock[] {
  return (page?.blocks ?? []).filter((block) => blockStatusOf(page, block) === 'error');
}

/** 阅读器正文生成提示文案（对照参考 ActivityHeader label；参数照抄 REFERENCE-SPEC §5） */
function readerStatusLabel(
  pageStatus: PageStatus,
  hydrating: boolean,
): '正在载入本章…' | '正在规划本页的块…' | '正在编译本页…' | null {
  if (hydrating) return '正在载入本章…';
  if (pageStatus === 'planning') return '正在规划本页的块…';
  if (pageStatus === 'generating') return '正在编译本页…';
  return null;
}

// ===== I1 执行器接入（§4.4 冻结 API）：收敛为一个对象，按“能力可用”判定按钮可用性 =====
// HARDEN v1：页/块修复返回 Promise<RepairResult>（真实异步结果 + 操作身份 + 取消语义）

interface GenerationApi {
  retryBlock?: (bookId: string, pageId: string, blockId: string) => Promise<RepairResult>;
  regeneratePage?: (bookId: string, pageId: string) => Promise<RepairResult>;
  startRun?: (
    bookId: string,
    options?: { scenario?: object; source?: 'user' | 'auto-open' | 'retry' },
  ) => BookRunHandle | null;
  getRepair?: (
    bookId: string,
    pageId: string,
  ) => { operationId: string; runId: string; blockIds: string[]; writtenBlockIds: string[] } | null;
}
type QuizAttemptView = Pick<BookQuizAttempt, 'choice' | 'blockVersion'>;

const generationModule: GenerationApi = {
  retryBlock: (bookId, pageId, blockId) => retryBlockRun(bookId, pageId, blockId),
  regeneratePage: (bookId, pageId) => regeneratePageRun(bookId, pageId),
  startRun: (bookId, options) => startRunRun(bookId, { source: options?.source }),
  getRepair: (bookId, pageId) => getRepair(bookId, pageId),
};

function loadGenerationApi(): GenerationApi | null {
  return generationModule;
}

/**
 * 兼容服务替身：真实实现返回 Promise<RepairResult>；测试替身可能返回非 Promise（旧形状）。
 * 非 Promise 结果视为"无结果"，只结束忙态，不据此虚构成功/失败。
 */
async function awaitRepairResult(result: unknown): Promise<RepairResult | null> {
  if (result && typeof (result as { then?: unknown }).then === 'function') {
    return (await result) as RepairResult;
  }
  return null;
}

/**
 * 全局翻页键是否应当忽略本次按键（M22-06）。
 * 排除：输入框/文本域/下拉/可编辑元素（含 contenteditable 后代）、组合输入（IME）、
 * 带修饰键的快捷键（Ctrl/Meta/Alt/Shift）与已被其他处理器消费的事件。
 */
function shouldIgnorePageKey(event: KeyboardEvent): boolean {
  if (event.defaultPrevented) return true;
  if (event.isComposing) return true; // 组合输入进行中（中文输入法的 ←/→ 选字）
  if (event.ctrlKey || event.metaKey || event.altKey || event.shiftKey) return true;
  const target = event.target as (HTMLElement & { tagName?: string }) | null;
  if (!target || typeof target.tagName !== 'string') return false;
  const tag = target.tagName.toLowerCase();
  if (tag === 'input' || tag === 'textarea' || tag === 'select') return true;
  if (target.isContentEditable === true) return true;
  const editable =
    typeof target.closest === 'function' ? target.closest('[contenteditable]') : null;
  if (editable instanceof HTMLElement) {
    return editable.getAttribute('contenteditable') !== 'false';
  }
  return false;
}

function readPageFromBook(book: ReplicaBook, pageId: string): PipelinePage | undefined {
  // 页面内联在书籍记录（本地仓储形态）；经 chapters.pageIds 定位
  const raw = (book as unknown as { pages?: PipelinePage[] }).pages;
  return raw?.find((page) => page.id === pageId);
}

/** 从存储读取书签真实状态（toggleBookmark 落库后由上层订阅刷新重渲染；此处读取不写回） */
function readBookmarked(bookId: string, pageId: string): boolean {
  if (typeof window === 'undefined') return false;
  try {
    const raw = window.localStorage.getItem('zhiqikeyuan:books');
    if (!raw) return false;
    const list = JSON.parse(raw) as { id?: string; reading?: { bookmarkedPageIds?: string[] } }[];
    return Boolean(list.find((item) => item.id === bookId)?.reading?.bookmarkedPageIds?.includes(pageId));
  } catch {
    return false;
  }
}

// ===== 阅读器 =====

/** 阅读器：Block 分发渲染（对照参考 BlockRenderer 的 14 类本地形态）+ 翻页/键盘/书签/已读登记 */
export function PageReader({ book, pageId }: { book: ReplicaBook; pageId: string }) {
  const router = useRouter();
  const pages = useMemo(
    () => book.chapters.flatMap((chapter) => chapter.pageIds),
    [book.chapters],
  );
  const index = pages.indexOf(pageId);
  const chapter = book.chapters.find((item) => item.pageIds.includes(pageId)) ?? null;

  const [generationApi] = useState<GenerationApi | null>(() =>
    typeof window === 'undefined' ? null : loadGenerationApi(),
  );
  const [busyBlockId, setBusyBlockId] = useState<string | null>(null);
  // 挂载时若本页已有在途修复（模块级操作不随组件卸载取消），忙态如实恢复
  const [pageBusy, setPageBusy] = useState<boolean>(() =>
    typeof window === 'undefined'
      ? false
      : Boolean(loadGenerationApi()?.getRepair?.(book.id, pageId)),
  );
  /** 页/块修复的失败或"未生效"原因（M22-02：不再静默无操作） */
  const [repairError, setRepairError] = useState<string | null>(null);
  /** 排队页「生成本章」无法启动时的原因 */
  const [startError, setStartError] = useState<string | null>(null);
  /** 本组件发起的修复请求序号：只有最新一次点击能改动忙态与提示（旧请求被取代后不得清除新忙态） */
  const repairRequestRef = useRef(0);

  // 书签真实状态读取自存储（组件接收的 book 是渲染时快照；
  // toggleBookmark 落库后经订阅刷新由上层重渲染，本地以存储为准避免旧快照回显）
  const [bookmarkTick, forceBookmarkRefresh] = useState(0);
  const bookmarkedInStore = useMemo(() => {
    try {
      return readBookmarked(book.id, pageId);
    } catch {
      return false;
    }
    // bookmarkTick：点击书签后强制重读存储（快照 book 未变时也能反映真实状态）
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [book.id, pageId, book.updatedAt, bookmarkTick]);
  const bookmarked = book.reading.bookmarkedPageIds.includes(pageId) || bookmarkedInStore;

  const page = readPageFromBook(book, pageId);
  const pageStatus = pageStatusOf(page);
  const blocks = page?.blocks ?? [];
  const failedBlocks = failedBlocksOf(page);

  // 打开章节即登记已读（对照参考 markVisited）。
  // 冻结契约 §4.3：仅 ready/partial 登记 visited；currentPageId 始终更新——
  // 该规则由 books-store.markVisited 自身保证；此处仅在有内容（ready/partial）时调用，
  // 未生成页（pending/planning/generating/error）打开不登记已读。
  useEffect(() => {
    if (pageStatus === 'ready' || pageStatus === 'partial') {
      markVisited(book.id, pageId);
    }
  }, [book.id, pageId, pageStatus]);

  // 键盘翻章（对照参考 ←/→）。HARDEN v1：在笔记编辑、组合输入与修饰键场景下不得触发全局翻页。
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (shouldIgnorePageKey(event)) return;
      if (event.key === 'ArrowLeft' && index > 0) {
        router.push(`/books/${book.id}/pages/${pages[index - 1]!}`);
      } else if (event.key === 'ArrowRight' && index < pages.length - 1) {
        router.push(`/books/${book.id}/pages/${pages[index + 1]!}`);
      }
    }
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [book.id, index, pages, router]);

  const prevId = index > 0 ? pages[index - 1] : null;
  const nextId = index < pages.length - 1 ? pages[index + 1] : null;

  // 正文状态派生（对照参考 writing/queued/hydrating 判定，REFERENCE-SPEC §5）：
  // - writing：本页 planning/generating（页自身状态是诚实答案，不问是谁启动的）；
  // - queued：页 pending（欠一次运行且当前无执行者在写）——提供“现在开始”入口；
  // - hydrating：页已就绪但块尚未到达（目标侧：页有序号、blocks 空、状态非生成中）——是载入，不是空页。
  const writing = pageStatus === 'planning' || pageStatus === 'generating';
  const queued = !writing && pageStatus === 'pending';
  const hydrating = !writing && !queued && blocks.length === 0;
  const statusLine = readerStatusLabel(pageStatus, hydrating);

  /**
   * 修复结果落地：只有最新一次点击能改动忙态与提示。
   * - completed → 清除提示；
   * - failed / skipped / superseded / cancelled → 如实显示原因（不再"按钮可点但什么都没发生"）。
   */
  const settleRepair = useCallback(
    (requestId: number, result: RepairResult | null, fallbackError?: string) => {
      if (requestId !== repairRequestRef.current) return; // 已被更新的一次点击取代
      const failed = result ? result.status !== 'completed' : Boolean(fallbackError);
      setRepairError(failed ? (result?.error ?? fallbackError ?? '本次操作未生效。') : null);
      setPageBusy(false);
      setBusyBlockId(null);
    },
    [],
  );

  const runRepairAction = useCallback(
    (action: 'page' | 'block', blockId?: string) => {
      const invoke =
        action === 'page'
          ? generationApi?.regeneratePage
          : generationApi?.retryBlock && blockId !== undefined
            ? (id: string, page: string) => generationApi.retryBlock!(id, page, blockId)
            : undefined;
      if (!invoke) return;
      if (action === 'block' ? busyBlockId !== null : pageBusy) return;
      const requestId = (repairRequestRef.current += 1);
      setRepairError(null);
      if (action === 'page') setPageBusy(true);
      else setBusyBlockId(blockId ?? null);
      void (async () => {
        try {
          const result = await awaitRepairResult(invoke(book.id, pageId));
          settleRepair(requestId, result);
        } catch (cause) {
          settleRepair(requestId, null, cause instanceof Error ? cause.message : '重新生成失败。');
        }
      })();
    },
    [book.id, busyBlockId, generationApi, pageBusy, pageId, settleRepair],
  );

  /** 强制重新生成（整页）：regeneratePage 保留 user_note 与块身份（§4.3），只复位非 user_note 块 */
  const onRegeneratePage = () => runRepairAction('page');

  /** 排队页“生成本章”：startRun（source 'user'）——按执行器语义启动整轮运行（含本章） */
  const onStartChapter = () => {
    if (!generationApi?.startRun || pageBusy) return;
    setStartError(null);
    const handle = generationApi.startRun(book.id, { source: 'user' });
    // 启动失败（他标签页持租约/状态变化/存储读取失败）如实说明，不静默无操作
    if (!handle) {
      setStartError('无法开始生成：本书当前不可启动（可能已被其他标签页接管、状态已变化，或本地存储不可读）。');
      return;
    }
    setPageBusy(false);
  };

  /** 单块重试（§4.3 retryBlock：pending + 清 failure；页 partial→generating） */
  const onRetryBlock = (targetBlockId: string) => runRepairAction('block', targetBlockId);

  const regenerateAvailable = Boolean(generationApi?.regeneratePage);
  // 归档书是只读的（books-store.runWritable 拒绝 archived 写入，对照参考 can_resume 不含归档）：
  // 生成/重试/重新生成入口一律禁用并给出同一说明，避免"按钮可点但什么都没发生"的静默无操作。
  const archived = book.status === 'archived';
  const archivedNote = '已归档（只读）：生成、重试与重新生成入口已禁用以保持归档内容不被改写；如需继续编辑，请先在书籍列表取消归档。';

  return (
    <article className="books-reader">
      <div className="space-session-top" style={{ marginBottom: 10 }}>
        <span className="space-chip">{chapter ? chapter.title : '章节'}</span>
        <span className="space-chip">
          第 {index + 1}/{pages.length} 页
        </span>
        <span className="space-session-actions">
          <button
            className="space-button"
            aria-pressed={bookmarked}
            aria-label={bookmarked ? '移除书签' : '添加书签'}
            onClick={() => {
              toggleBookmark(book.id, pageId);
              forceBookmarkRefresh((value) => value + 1);
            }}
          >
            <Bookmark size={13} fill={bookmarked ? 'currentColor' : 'none'} />
            {bookmarked ? '已加书签' : '书签'}
          </button>
          <button
            className="space-button"
            aria-label="强制重新生成"
            disabled={!regenerateAvailable || pageBusy || archived}
            title={
              archived
                ? archivedNote
                : regenerateAvailable
                  ? '重新生成本页（保留笔记与块身份）'
                  : '生成服务不可用（本地模拟执行器未接入）'
            }
            onClick={onRegeneratePage}
          >
            {pageBusy ? <Loader2 size={13} className="space-spin" aria-hidden /> : <RefreshCcw size={13} aria-hidden />}
            {pageBusy ? '正在重新生成…' : '强制重新生成'}
          </button>
        </span>
      </div>
      {archived && (
        <p className="book-reader-readonly-note" role="note">
          {archivedNote}
        </p>
      )}
      {/* 修复/启动未生效的原因（M22-02：失败、被取代、不可写都如实说明，不静默无操作） */}
      {repairError && (
        <p className="book-reader-storage-error" role="alert">
          重新生成未完成：{repairError}
        </p>
      )}
      {startError && (
        <p className="book-reader-storage-error" role="alert">
          {startError}
        </p>
      )}
      <h2 style={{ marginTop: 0 }}>
        <Link href={`/books/${book.id}`}>{book.title}</Link>
      </h2>
      <div className="space-banner info" role="note" style={{ marginBottom: 14 }}>
        本页内容为本地模拟编译产物（显式标注），非模型生成；练习作答与页内笔记本地持久化，跨会话恢复（参考为服务端 attempt）。
      </div>
      {/* 正文生成提示（对照参考 ActivityHeader：role="status" aria-live="polite"） */}
      {statusLine && (
        <p className="book-reader-activity" role="status" aria-live="polite">
          <Loader2 size={13} className="space-spin" aria-hidden />
          <span className="book-reader-activity-label">{statusLine}</span>
        </p>
      )}
      {/* 排队页（对照参考 queued 分支） */}
      {queued && (
        <div className="book-reader-queued">
          <p>本章尚未生成，将按顺序生成——也可以现在开始。</p>
          <button
            type="button"
            className="space-button"
            disabled={!generationApi?.startRun || pageBusy || archived}
            title={archived ? archivedNote : undefined}
            onClick={onStartChapter}
          >
            {pageBusy ? <Loader2 size={13} className="space-spin" aria-hidden /> : <RefreshCcw size={13} aria-hidden />}
            生成本章
          </button>
        </div>
      )}
      {/* 页失败面板（对照参考 hasFailedBlocks 分支：标题计数 + 重新生成本页 + 最多列 5 条） */}
      {failedBlocks.length > 0 && (
        <div className="book-reader-page-failures" role="alert">
          <div className="book-reader-page-failures-head">
            <strong>
              {failedBlocks.length === 1 ? '1 个块失败' : `${failedBlocks.length} 个块失败`}
            </strong>
            <button
              type="button"
              className="space-button"
              disabled={!regenerateAvailable || pageBusy || archived}
              title={archived ? archivedNote : undefined}
              onClick={onRegeneratePage}
            >
              {pageBusy ? <Loader2 size={13} className="space-spin" aria-hidden /> : <RefreshCcw size={13} aria-hidden />}
              {pageBusy ? '正在重新生成…' : '重新生成本页'}
            </button>
          </div>
          <div className="book-reader-page-failures-list">
            {failedBlocks.slice(0, 5).map((block) => (
              <div className="book-reader-page-failures-item" key={block.id}>
                <code>{block.type}</code>
                <span>
                  {bookFailureKindLabel(block.failure?.kind)}：{block.failure?.message ?? '未知错误（本地模拟）'}
                </span>
                <button
                  type="button"
                  className="space-button"
                  disabled={!generationApi?.retryBlock || busyBlockId !== null || archived}
                  title={archived ? archivedNote : undefined}
                  onClick={() => onRetryBlock(block.id)}
                >
                  {busyBlockId === block.id ? (
                    <Loader2 size={11} className="space-spin" aria-hidden />
                  ) : null}
                  重试块
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
      {/* 整页失败（page.status === 'error'）：如实呈现页级错误（页面生成失败），不归因供应商 */}
      {pageStatus === 'error' && (
        <div className="book-reader-page-failures book-reader-page-error" role="alert">
          <div className="book-reader-page-failures-head">
            <strong>页面生成失败</strong>
            <button
              type="button"
              className="space-button"
              disabled={!regenerateAvailable || pageBusy || archived}
              title={archived ? archivedNote : undefined}
              onClick={onRegeneratePage}
            >
              {pageBusy ? <Loader2 size={13} className="space-spin" aria-hidden /> : <RefreshCcw size={13} aria-hidden />}
              {pageBusy ? '正在重新生成…' : '重新生成本页'}
            </button>
          </div>
          <div className="book-reader-page-failures-list">
            <div className="book-reader-page-failures-item">
              <span>{page?.error ?? '未知错误（本地模拟）'}</span>
            </div>
          </div>
        </div>
      )}
      {(chapter?.pageIds ?? []).indexOf(pageId) >= 0 &&
        blocks.map((rawBlock) => {
          const block = rawBlock as PipelineBlock;
          const status = blockStatusOf(page, block);
          if (status === 'error') {
            return (
              <BookBlockFailure
                key={block.id}
                block={block}
                busy={busyBlockId === block.id}
                retryDisabled={!generationApi?.retryBlock || busyBlockId !== null || archived}
                onRetry={() => onRetryBlock(block.id)}
              />
            );
          }
          if (status === 'pending' || status === 'generating') {
            // 块占位（对照参考 BlockRenderer 的 pending·generating 分支，口径按 §5.1"生成中/排队"两态）：
            // pending 不写"正在生成"——没有执行器在写它（整页失败后的残留 pending、已中断的书、
            // 正在排队等前序块的页），那时如实说"等待生成"。
            return (
              <div className="book-reader-block-generating" key={block.id} data-block-state={status}>
                {status === 'generating' ? (
                  <Loader2 size={13} className="space-spin" aria-hidden />
                ) : null}
                <span>
                  {status === 'generating' ? `正在生成 ${block.type} 块…` : `${block.type} 块等待生成…`}
                </span>
              </div>
            );
          }
          return (
            <BookBlockView
              key={block.id}
              block={block}
              bookId={book.id}
              pageId={pageId}
            />
          );
        })}
      <div className="books-reader-footer">
        {prevId ? (
          <Link className="space-button" href={`/books/${book.id}/pages/${prevId}`}>
            <ChevronLeft size={14} />
            上一页
          </Link>
        ) : (
          <span />
        )}
        <span className="space-footnote">← / → 键盘翻页</span>
        {nextId ? (
          <Link className="space-button primary" href={`/books/${book.id}/pages/${nextId}`}>
            下一页
            <ChevronRight size={14} />
          </Link>
        ) : (
          <span />
        )}
      </div>
    </article>
  );
}

function BookBlockView({
  block,
  bookId,
  pageId,
}: {
  block: PipelineBlock;
  bookId: string;
  pageId: string;
}) {
  const [answer, setAnswer] = useState<string | null>(null);
  const [note, setNote] = useState(block.type === 'user_note' ? block.content : '');
  const [flipped, setFlipped] = useState<Record<number, boolean>>({});
  const [copied, setCopied] = useState(false);
  const [noteError, setNoteError] = useState(false);

  // 进入页面恢复最近一次作答（练习答案本地持久化）。
  // 作答版本关系（§4.3 quizAttemptMatches）：版本不匹配时不把旧作答显示为新题答案，
  // 如实提示并允许重新作答；历史作答保留在存储中。
  const restoredAttemptRef = useMemo(
    () => (latestQuizAttempt(bookId, pageId, block.id) ?? null) as QuizAttemptView | null,
    [bookId, pageId, block.id],
  );
  const attemptMatches =
    block.type === 'quiz' && restoredAttemptRef
      ? quizAttemptMatches(block, restoredAttemptRef)
      : true;
  const staleAttemptShown = Boolean(restoredAttemptRef) && !attemptMatches;

  useEffect(() => {
    if (block.type !== 'quiz') return;
    const attempt = latestQuizAttempt(bookId, pageId, block.id);
    // 仅在版本匹配时恢复为当前题的作答；不匹配时保留为“旧版作答记录”提示
    if (attempt && quizAttemptMatches(block, attempt)) setAnswer(attempt.choice);
  }, [bookId, pageId, block]);

  if (block.type === 'placeholder') {
    return (
      <div className="books-block space-empty">
        <strong>{block.title || '待编译内容'}</strong>
        <span>{block.content}</span>
      </div>
    );
  }
  if (block.type === 'section') {
    return (
      <div className="books-block">
        {block.title && <h3 style={{ marginBottom: 4 }}>{block.title}</h3>}
        <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{block.content}</p>
      </div>
    );
  }
  if (block.type === 'callout') {
    return (
      <aside className="books-block books-block-callout">
        {block.title && <strong>{block.title}</strong>}
        <p style={{ margin: '4px 0 0', whiteSpace: 'pre-wrap' }}>{block.content}</p>
      </aside>
    );
  }
  if (block.type === 'code') {
    return (
      <div className="books-block">
        <div className="space-session-top" style={{ marginBottom: 4 }}>
          {block.title && <strong>{block.title}</strong>}
          <span className="space-chip">{block.language ?? 'text'}</span>
          <span className="space-session-actions">
            <button
              className="space-button"
              aria-label="复制代码"
              onClick={() => {
                void navigator.clipboard?.writeText(block.content).then(
                  () => setCopied(true),
                  () => setCopied(false),
                );
                window.setTimeout(() => setCopied(false), 1500);
              }}
            >
              <Copy size={12} />
              {copied ? '已复制' : '复制'}
            </button>
          </span>
        </div>
        <pre className="books-code" style={{ margin: 0, padding: '10px 12px', borderRadius: 10, overflowX: 'auto', background: 'rgba(0,0,0,0.05)', fontSize: 13 }}>
          <code>{block.content}</code>
        </pre>
      </div>
    );
  }
  if (block.type === 'timeline') {
    const items = block.content.split('\n').filter((line) => line.trim());
    return (
      <div className="books-block">
        {block.title && <strong>{block.title}</strong>}
        <ol style={{ margin: '6px 0 0', paddingLeft: 20 }}>
          {items.map((item, idx) => {
            const [head, ...rest] = item.split('::');
            return (
              <li key={idx} style={{ marginBottom: 4 }}>
                <strong>{(head ?? '').trim()}</strong>
                {rest.length > 0 && <span>：{rest.join('::').trim()}</span>}
              </li>
            );
          })}
        </ol>
      </div>
    );
  }
  if (block.type === 'flash_cards') {
    const cards = block.content.split('\n').filter((line) => line.includes('::'));
    return (
      <div className="books-block">
        {block.title && <strong>{block.title}</strong>}
        <ul style={{ listStyle: 'none', margin: '6px 0 0', padding: 0 }}>
          {cards.map((card, idx) => {
            const [question, answerText] = card.split('::');
            return (
              <li key={idx} style={{ marginBottom: 6 }}>
                <button
                  type="button"
                  className="space-button"
                  style={{ width: '100%', justifyContent: 'flex-start', textAlign: 'left' }}
                  aria-pressed={Boolean(flipped[idx])}
                  onClick={() => setFlipped((current) => ({ ...current, [idx]: !current[idx] }))}
                >
                  {flipped[idx] ? `答：${(answerText ?? '').trim()}` : `问：${(question ?? '').trim()}`}
                </button>
              </li>
            );
          })}
        </ul>
      </div>
    );
  }
  if (block.type === 'figure') {
    return (
      <figure className="books-block" style={{ margin: 0 }}>
        <div
          className="space-empty"
          role="img"
          aria-label={block.title ?? '插图占位'}
          style={{ minHeight: 90, display: 'grid', placeItems: 'center', border: '1px dashed rgba(0,0,0,0.2)', borderRadius: 10 }}
        >
          <span>图（模拟占位，真实图像未生成）</span>
        </div>
        {block.title && <figcaption className="space-footnote" style={{ marginTop: 4 }}>{block.title}</figcaption>}
      </figure>
    );
  }
  if (block.type === 'user_note') {
    return (
      <div className="books-block">
        {block.title && <strong>{block.title}</strong>}
        <textarea
          aria-label="我的笔记内容"
          value={note}
          placeholder="写下你的笔记，自动本地保存…"
          style={{ minHeight: 64, marginTop: 6, width: '100%' }}
          onChange={(event) => {
            setNote(event.target.value);
            setNoteError(false);
          }}
          onBlur={() => {
            // 本地存储写入失败：页内如实提示（不伪装已保存，不归因供应商）
            try {
              const saved = setUserNote(bookId, pageId, block.id, note);
              setNoteError(!saved);
            } catch {
              setNoteError(true);
            }
          }}
        />
        {noteError && (
          <p className="book-reader-storage-error" role="alert">
            写入失败，内容未保存。本页笔记未写入本地存储，请重试或另行保存。
          </p>
        )}
        <p className="space-footnote" style={{ margin: '4px 0 0' }}>失焦时本地保存；仅本机可见。</p>
      </div>
    );
  }
  if (block.type === 'deep_dive') {
    return (
      <details className="books-block">
        <summary style={{ cursor: 'pointer', fontWeight: 600 }}>{block.title ?? '深入探究'}</summary>
        <p style={{ margin: '6px 0 0', whiteSpace: 'pre-wrap' }}>{block.content}</p>
      </details>
    );
  }
  if (block.type === 'concept_graph') {
    const edges = block.content.split('\n').filter((line) => line.includes('-'));
    return (
      <div className="books-block">
        {block.title && <strong>{block.title}</strong>}
        <span className="space-chip" style={{ marginLeft: 6 }}>模拟静态展示</span>
        <ul style={{ margin: '6px 0 0', paddingLeft: 18 }}>
          {edges.map((edge, idx) => (
            <li key={idx}>{edge.trim().replace(/\s*-\s*/, ' → ')}</li>
          ))}
        </ul>
      </div>
    );
  }
  if (block.type === 'interactive' || block.type === 'animation') {
    return (
      <div className="books-block space-empty" role="note">
        <strong>{block.title ?? (block.type === 'interactive' ? '互动组件' : '动画演示')}</strong>
        <span>{block.content}</span>
        <span className="space-chip">显式模拟占位</span>
      </div>
    );
  }
  if (block.type === 'quiz' && block.quiz) {
    const answered = answer !== null;
    return (
      <div className="books-block">
        <p style={{ fontWeight: 600 }}>{block.content}</p>
        {/* 作答版本不匹配：如实提示旧版作答记录，不当作新题答案；允许重新作答 */}
        {staleAttemptShown && (
          <p className="book-reader-quiz-stale" role="note">
            该题内容已更新；当前显示的是旧版题目的作答记录（旧作答 {restoredAttemptRef?.choice ?? '—'} 已保留在历史中）。
          </p>
        )}
        {Object.entries(block.quiz.options).map(([key, value]) => {
          const isCorrect = key === block.quiz!.correct;
          const tone = answered && key === answer ? (isCorrect ? 'correct' : 'wrong') : '';
          return (
            <button
              key={key}
              type="button"
              className={`books-quiz-option ${tone}`}
              disabled={answered}
              onClick={() => {
                setAnswer(key);
                // 作答记录携带块内容版本（§4.3 blockVersion），重生成后旧作答不再算新题答案
                recordQuizAttempt({
                  bookId,
                  pageId,
                  blockId: block.id,
                  choice: key,
                  correct: key === block.quiz!.correct,
                  ...(block.contentVersion !== undefined ? { blockVersion: block.contentVersion } : {}),
                });
              }}
            >
              {key}. {value}
            </button>
          );
        })}
        {answered && (
          <p className={answer === block.quiz.correct ? 'space-chip green' : 'space-chip'} role="status">
            {answer === block.quiz.correct ? '回答正确。' : `回答错误，正确答案 ${block.quiz.correct}。`}
            {block.quiz.explanation ? ` ${block.quiz.explanation}` : ''}
          </p>
        )}
      </div>
    );
  }
  // text 与未知类型统一按 Markdown 文本渲染（本地形态，pre-wrap）
  return (
    <div className="books-block">
      {block.title && <h3 style={{ marginBottom: 4 }}>{block.title}</h3>}
      <p style={{ margin: 0, whiteSpace: 'pre-wrap' }}>{block.content}</p>
    </div>
  );
}
