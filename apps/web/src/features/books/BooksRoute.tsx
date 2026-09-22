'use client';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import {
  ArrowLeft,
  ArrowRight,
  BookMarked,
  Bookmark,
  Clock,
  FileText,
  Layers,
  Loader2,
  RefreshCcw,
  RotateCcw,
  Search,
  Sparkles,
} from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import {
  BookValidationError,
  confirmProposal,
  confirmSpine,
  createBook,
  deleteBook,
  exportBookMarkdown,
  loadDemoBooks,
  readingPercent,
  rebuildBook,
  readBooks,
  subscribeBooks,
  type ReplicaBook,
} from '@/services/books-store';
import {
  getLease,
  getRun,
  getRunExit,
  resumeRun,
  startRun,
  stopRun,
  type BookRunScenario,
} from '@/services/book-generation';
import '@/features/space/styles/space.css';
import '@/features/books/books.css';
import '@/features/books/styles/book-pipeline.css';
import { PageReader } from './PageReader';
import { BookGenerationStrip, deriveStripChapters } from './BookGenerationStrip';
import { BookPausedBanner } from './BookPausedBanner';

const STATUS_LABEL: Record<ReplicaBook['status'], string> = {
  draft: '草稿 · 待确认提案',
  spine_ready: '大纲待确认',
  compiling: '正在生成',
  paused: '已暂停',
  ready: '可阅读',
  error: '生成失败',
  archived: '已归档',
};

const STATUS_TONE: Record<ReplicaBook['status'], string> = {
  draft: 'amber',
  spine_ready: 'blue',
  compiling: 'blue',
  paused: 'amber',
  ready: 'green',
  error: '',
  archived: '',
};

/** 侧栏页状态词（对照参考 BookSidebar STATUS_LABEL：排队/规划/编译中/就绪/部分失败/失败） */
const PAGE_STATUS_LABEL: Record<string, string> = {
  pending: '排队',
  planning: '规划',
  generating: '编译中',
  ready: '就绪',
  partial: '部分失败',
  error: '失败',
};

/** 页面状态 → 圆点形态（对照参考 PAGE_MARK：pending→done/muted、planning·generating→running、ready→accent、partial·error→error） */
const PAGE_STATUS_DOT: Record<string, string> = {
  pending: 'queued',
  planning: 'running',
  generating: 'running',
  ready: 'done',
  partial: 'error',
  error: 'error',
};

/** 缺 status 的旧页面/块按 ready 处理（读取期派生，不写回；任务卡 §4.2 兼容规则） */
type PageRuntimeStatus = 'pending' | 'planning' | 'generating' | 'ready' | 'partial' | 'error';

interface PageRuntime {
  status: PageRuntimeStatus;
  generatingBlockTitle: string | null;
}

function readPages(book: ReplicaBook): { id: string; blocks: { status?: string; title?: string; failure?: unknown }[] }[] {
  return (book as unknown as { pages?: { id: string; blocks: { status?: string; title?: string; failure?: unknown }[] }[] }).pages ?? [];
}

function pageRuntimeOf(book: ReplicaBook): (pageId: string) => PageRuntime {
  const pages = readPages(book);
  return (pageId: string) => {
    const page = pages.find((item) => item.id === pageId);
    if (!page) return { status: 'pending', generatingBlockTitle: null };
    const blocks = page.blocks ?? [];
    if (blocks.length === 0) return { status: 'pending', generatingBlockTitle: null };
    let hasError = false;
    let generating: string | null = null;
    let readyCount = 0;
    for (const block of blocks) {
      const status = block.status ?? 'ready';
      if (status === 'ready') readyCount += 1;
      else if (status === 'error') hasError = true;
      else if (status === 'generating' && !generating) generating = block.title ?? '本页内容';
    }
    if (generating) return { status: 'generating', generatingBlockTitle: generating };
    if (hasError) return { status: readyCount > 0 ? 'partial' : 'error', generatingBlockTitle: null };
    if (readyCount === blocks.length) return { status: 'ready', generatingBlockTitle: null };
    return { status: 'pending', generatingBlockTitle: null };
  };
}

/** 完成章数 = 该章所有页 ready（partial 计入完成语义由卡片显示另行说明，章完成只数全 ready） */
function chapterProgress(book: ReplicaBook): { doneChapters: number; totalChapters: number; donePages: number; totalPages: number } {
  const runtimeOf = pageRuntimeOf(book);
  let doneChapters = 0;
  let donePages = 0;
  let totalPages = 0;
  for (const chapter of book.chapters) {
    let chapterDone = chapter.pageIds.length > 0;
    for (const pageId of chapter.pageIds) {
      totalPages += 1;
      const status = runtimeOf(pageId).status;
      if (status === 'ready' || status === 'partial') donePages += 1;
      if (status !== 'ready') chapterDone = false;
    }
    if (chapterDone) doneChapters += 1;
  }
  return { doneChapters, totalChapters: book.chapters.length, donePages, totalPages };
}

/** 组件内的执行器会话状态：不随组件卸载取消执行器（模块级），只记录交互忙态 */
interface RunUiState {
  pausing: boolean;
  resuming: boolean;
  /** 整轮失败后「重试生成」的忙态 */
  retrying: boolean;
}

export function BooksRoute() {
  const params = useParams<{ bookId?: string; pageId?: string }>();
  const bookId = params?.bookId;
  if (!bookId) return <BookLibrary />;
  return <BookWorkspace bookId={bookId} pageId={params?.pageId} />;
}

function BookLibrary() {
  const router = useRouter();
  const [books, setBooks] = useState<ReplicaBook[]>([]);
  const [query, setQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [pendingDeleteId, setPendingDeleteId] = useState<string | null>(null);

  const refresh = useCallback(() => {
    try {
      setBooks(readBooks());
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '书籍目录无法读取，原数据未修改。');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    return subscribeBooks(refresh);
  }, [refresh]);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    const list = [...books].sort((a, b) => (a.updatedAt < b.updatedAt ? 1 : -1));
    return q ? list.filter((book) => book.title.toLowerCase().includes(q)) : list;
  }, [books, query]);

  const active = books.filter((book) => book.status !== 'archived');

  return (
    <div className="space-page books-page">
      <header className="space-header">
        <div className="space-header-row">
          <h1>书籍</h1>
          <div className="space-card-actions">
            <button
              className="space-button"
              onClick={() => {
                loadDemoBooks();
                setNotice('已载入演示书籍（重复载入不产生重复条目）。编译内容为本地模拟，不含模型产出。');
              }}
            >
              <Sparkles size={14} />
              载入演示数据
            </button>
            <button className="space-button primary" onClick={() => setCreating(true)}>
              <BookMarked size={14} />
              新建书籍
            </button>
          </div>
        </div>
        <p className="space-description">
          生成流水线未接入模型：提案、大纲为本地确定性模拟，编译由本地模拟执行器逐章逐块异步推进（显式标注），可暂停、可恢复；阅读进度与导出在本地保存。
        </p>
      </header>
      <main className="space-content">
        <div className="space-meta-row" role="note">
          <span className="space-chip">共 {books.length} 本</span>
          <span className="space-chip">进行中 {active.filter((book) => book.status !== 'ready').length}</span>
          <span className="space-chip">可阅读 {active.filter((book) => book.status === 'ready').length}</span>
          <span className="space-chip">章节 {books.reduce((sum, book) => sum + book.chapters.length, 0)}</span>
        </div>
        {notice && (
          <div className="space-banner info" role="status">
            {notice}
          </div>
        )}
        {error && (
          <div className="space-banner error" role="alert">
            {error}
          </div>
        )}

        {loading ? (
          <div aria-hidden>
            {[0, 1].map((index) => (
              <div className="space-skeleton" key={index} style={{ height: 76, marginBottom: 10 }} />
            ))}
          </div>
        ) : books.length === 0 ? (
          <div className="space-empty">
            <strong>还没有书籍</strong>
            <span>载入演示书籍快速体验，或新建一本书开始（提案与编译为本地模拟）。</span>
          </div>
        ) : (
          <>
            <div className="space-toolbar">
              <div className="books-search-wrap">
                <span className="books-search-icon" aria-hidden>
                  <Search size={13} />
                </span>
                <input
                  className="space-search"
                  type="search"
                  placeholder="按书名搜索…"
                  aria-label="搜索书籍"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </div>
              <span className="books-search-count" aria-live="polite">
                {query.trim() ? (
                  <>
                    {filtered.length}/{books.length} · 匹配「{query.trim()}」
                  </>
                ) : (
                  <span className="space-chip">我的书架 · 共 {books.length} 本</span>
                )}
              </span>
            </div>
            <div className="space-card-grid">
              {filtered.map((book) => {
                const generating = book.status === 'compiling' || book.status === 'paused' || book.status === 'error';
                const progress = generating ? chapterProgress(book) : null;
                const pages =
                  book.status === 'ready'
                    ? book.chapters.reduce((sum, chapter) => sum + chapter.pageIds.length, 0)
                    : 0;
                const percent = readingPercent(book);
                const pendingDelete = pendingDeleteId === book.id;
                const cta =
                  book.status === 'draft'
                    ? '继续创建'
                    : book.status === 'spine_ready'
                      ? '确认大纲'
                      : book.status === 'ready'
                        ? percent > 0
                          ? '继续阅读'
                          : '开始阅读'
                        : '查看';
                return (
                  <article className="space-persona-card" key={book.id}>
                    <Link className="space-card-link" href={`/books/${book.id}`} aria-label={`打开书籍 ${book.title}`}>
                      <div className="space-card-title">
                        <BookMarked size={15} aria-hidden />
                        {book.title}
                        <ArrowRight size={14} className="books-card-arrow" aria-hidden />
                      </div>
                      <p className="space-card-body">{book.description || '（无简介）'}</p>
                      <div className="space-meta-row">
                        {/* 状态徽标对所有状态都渲染：既有 e2e（books-courses）以卡片上的「可阅读」锁定就绪态，
                            隐藏就绪徽标会让"这本书已完成"失去最直接的界面信号。 */}
                        <span className={`space-chip ${STATUS_TONE[book.status]}`}>
                          {book.status === 'compiling' && (
                            <span className="book-pipeline-status-chip-dot pulsing" aria-hidden />
                          )}
                          {STATUS_LABEL[book.status]}
                        </span>
                        <span className="books-meta-item">
                          <Layers size={11} aria-hidden />
                          {book.chapters.length} 章
                        </span>
                        {book.status === 'ready' && (
                          <span className="books-meta-item">
                            <FileText size={11} aria-hidden />
                            {pages} 页
                          </span>
                        )}
                        {progress && progress.totalChapters > 0 && (
                          <span className="book-pipeline-progress">
                            {progress.doneChapters}/{progress.totalChapters} 章
                          </span>
                        )}
                      </div>
                      {book.status === 'ready' && (
                        <div className="space-reading-bar" aria-label={`阅读进度 ${percent}%`}>
                          <div className="space-reading-bar-fill" style={{ width: `${percent}%` }} />
                        </div>
                      )}
                      <span className="space-footnote">
                        <Clock size={11} aria-hidden style={{ marginRight: 4, verticalAlign: -1 }} />
                        更新于 {new Date(book.updatedAt).toLocaleString('zh-CN')}
                      </span>
                    </Link>
                    <div className="space-card-actions" style={{ marginTop: 8 }}>
                      <button
                        className="space-button"
                        onClick={() => router.push(`/books/${book.id}`)}
                      >
                        {cta}
                      </button>
                      {pendingDelete ? (
                        <>
                          <button
                            className="space-button danger"
                            onClick={() => {
                              // 删除入口先停执行器与在途修复，再删记录（M22-01：不留心跳/监听/租约与幽灵任务）
                              stopRun(book.id, 'delete');
                              deleteBook(book.id);
                              setPendingDeleteId(null);
                            }}
                          >
                            确认删除
                          </button>
                          <button className="space-button" onClick={() => setPendingDeleteId(null)}>
                            取消
                          </button>
                        </>
                      ) : (
                        <button className="space-button danger" onClick={() => setPendingDeleteId(book.id)}>
                          删除
                        </button>
                      )}
                    </div>
                  </article>
                );
              })}
            </div>
            {filtered.length === 0 && (
              <div className="space-empty">
                <strong>没有匹配的书籍</strong>
                <span>换个搜索词再试。</span>
              </div>
            )}
          </>
        )}

        {creating && (
          <CreateBookForm
            onClose={() => setCreating(false)}
            onCreated={(id) => {
              setCreating(false);
              router.push(`/books/${id}`);
            }}
          />
        )}
      </main>
    </div>
  );
}

function CreateBookForm({ onClose, onCreated }: { onClose: () => void; onCreated: (id: string) => void }) {
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  return (
    <Modal title="新建书籍" onClose={onClose}>
      <form
        className="space-form"
        onSubmit={(event) => {
          event.preventDefault();
          setSubmitting(true);
          // 本地同步模拟创建：短促 busy 呈现（Loader2 旋转）后落库，操作语义不变
          window.setTimeout(() => {
            try {
              const book = createBook(title, description);
              onCreated(book.id);
            } catch (cause) {
              setError(
                cause instanceof BookValidationError ? cause.message : '创建失败，请检查输入后重试。',
              );
              setSubmitting(false);
            }
          }, 350);
        }}
      >
        <p className="space-footnote" style={{ marginTop: 0 }}>
          创建后立即生成本地模拟提案；确认提案→确认大纲后由本地模拟执行器逐章逐块异步编译（不调用模型）。
        </p>
        <label>
          书名
          <input
            value={title}
            required
            maxLength={80}
            onChange={(event) => setTitle(event.target.value)}
            placeholder="例如：分数入门"
          />
        </label>
        <label>
          简介
          <input
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="这本书写给谁、讲什么？"
          />
        </label>
        {error && (
          <p className="space-form-error" role="alert">
            {error}
          </p>
        )}
        <div className="space-form-footer">
          <button type="button" className="space-button" onClick={onClose}>
            取消
          </button>
          <button type="submit" className="space-button primary" disabled={submitting}>
            {submitting && <Loader2 size={13} className="space-spin" aria-hidden />}
            创建（生成模拟提案）
          </button>
        </div>
      </form>
    </Modal>
  );
}

function BookWorkspace({ bookId, pageId }: { bookId: string; pageId?: string }) {
  const router = useRouter();
  const [books, setBooks] = useState<ReplicaBook[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [runUi, setRunUi] = useState<RunUiState>({ pausing: false, resuming: false, retrying: false });
  const [tick, setTick] = useState(0);
  const scenarioRef = useRef<BookRunScenario>({});
  const scenarioBookRef = useRef<string | null>(null);
  /** 本挂载内已经出现过执行器（或已自动续跑过）的书：同一挂载内不再自动重启（见下方自动续跑） */
  const autoRunRef = useRef<Set<string>>(new Set());

  const refresh = useCallback(() => {
    try {
      setBooks(readBooks());
      // 读取成功即清除旧错误：上一次失败的原因不再残留在界面上（M22-04）
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '书籍目录无法读取，原数据未修改。');
    }
  }, []);

  useEffect(() => {
    refresh();
    return subscribeBooks(refresh);
  }, [refresh]);

  const book = useMemo(() => books?.find((item) => item.id === bookId) ?? null, [books, bookId]);

  // 执行器状态（模块级执行器，不随组件卸载取消）：500ms 轮询重读，
  // 覆盖 store 事件之外的句柄状态与租约心跳变化；计时由活动条自己驱动。
  const activeBookId = book?.id ?? null;
  const run = useMemo(() => {
    void tick; // 轮询触发重读模块级执行器句柄
    return activeBookId ? getRun(activeBookId) : null;
  }, [activeBookId, tick]);

  useEffect(() => {
    if (!activeBookId) return;
    const timer = window.setInterval(() => setTick((value) => value + 1), 500);
    return () => window.clearInterval(timer);
  }, [activeBookId]);

  // 自动续跑（对照参考 maybe_resume_on_open）：仅 compiling 且无活跃执行器且租约可续。
  // paused 绝不自动续跑；他标签页持活租约时不启动（lease.live && !lease.mine 时只读显示生成中）。
  // 触发时机限定为"打开书籍/刷新打开 +（他标签页）租约失效"这一类一次性的接管：
  // 同一挂载内一旦跑过执行器就不再自动重启，否则一次页失败后的"已中断"会被下一次轮询
  // 立刻自动接管——用户既看不到中断态，也看不到失败原因与恢复入口。
  useEffect(() => {
    if (!book || book.status !== 'compiling') return;
    if (getRun(book.id)) {
      autoRunRef.current.add(book.id);
      return;
    }
    const lease = getLease(book.id);
    if (lease && lease.live && !lease.mine) return; // 他标签页持活租约：只读显示，等其失效后再接管
    if (autoRunRef.current.has(book.id)) return;
    const handle = startRun(book.id, {
      scenario: scenarioBookRef.current === book.id ? scenarioRef.current : undefined,
      source: 'auto-open',
    });
    if (handle) {
      autoRunRef.current.add(book.id);
      // 同步失败（首个写入即被存储拒绝）的句柄 status 已是 failed：此时不得提示"已从断点继续"
      if (handle.status !== 'failed') setNotice('已从断点继续（本地模拟执行器）。');
    }
  }, [book, tick]);

  // 组件卸载不清除执行器（模块级）；同书翻页由 key 稳定性保证不重启
  // （这里不用 cleanup 取消 run —— 任务卡 §4.4：执行器不随组件卸载取消）

  // 自动续读：就绪书未带页码时跳转当前页；扩展到 compiling/paused/error（生成中直接进入阅读器）
  useEffect(() => {
    if (!book || pageId) return;
    if (book.status !== 'ready' && book.status !== 'compiling' && book.status !== 'paused' && book.status !== 'error') return;
    const firstPageId =
      book.reading.currentPageId ?? book.chapters.flatMap((chapter) => chapter.pageIds)[0] ?? null;
    if (firstPageId) router.replace(`/books/${bookId}/pages/${firstPageId}`);
  }, [book, bookId, pageId, router]);

  // 执行器异常收尾的如实提示：读失败/失权不是"静默停止"（M22-01/M22-03）。
  // 只在退出原因变化时提示一次，不因 500ms 轮询反复弹出。
  const exitNoticeRef = useRef<string | null>(null);
  useEffect(() => {
    if (!activeBookId) return;
    const exit = getRunExit(activeBookId);
    if (!exit || exit.reason === 'finished') return;
    const stamp = `${exit.reason}@${exit.at}`;
    if (exitNoticeRef.current === stamp) return;
    exitNoticeRef.current = stamp;
    if (exit.reason === 'read-denied' || exit.reason === 'lease-lost') {
      setNotice(exit.message ?? '本次生成已停止。');
    }
  }, [activeBookId, tick]);

  // 首次读取失败：显示错误与重试入口，而不是被"正在读取书籍…"的加载分支永久掩盖（M22-04）。
  // 读取失败时书籍数据保持 null（不做任何写入），因此这里必须与"尚未读到数据"区分开。
  if (books === null && error) {
    return (
      <div className="space-page books-page">
        <div className="space-content" style={{ marginTop: 80 }}>
          <div className="space-banner error" role="alert">
            <div className="space-banner-row">
              <span>书籍目录读取失败：{error}</span>
              <button className="space-button" onClick={refresh}>
                <RefreshCcw size={14} />
                重试读取
              </button>
            </div>
          </div>
          <p className="space-footnote" style={{ marginTop: 0 }}>
            读取失败时不会写入或清空任何本地数据；修复存储或稍后可重试读取。
          </p>
          <div className="space-card-actions">
            <Link className="space-button" href="/books">
              <ArrowLeft size={14} />
              返回书籍列表
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (books !== null && !book) {
    return (
      <div className="space-page books-page">
        <div className="space-empty" style={{ marginTop: 80 }}>
          <strong>书籍「{bookId}」不存在</strong>
          <span>它可能已被删除，或链接有误。</span>
          <Link className="space-button" href="/books">
            <ArrowLeft size={14} />
            返回书籍列表
          </Link>
        </div>
      </div>
    );
  }

  if (!book) {
    return (
      <div className="space-page books-page">
        <div className="books-loading" style={{ marginTop: 80 }} role="status">
          <Loader2 size={14} className="space-spin" aria-hidden />
          正在读取书籍…
        </div>
      </div>
    );
  }

  if (book.status === 'draft') {
    return (
      <>
        {error && (
          <div className="space-content">
            <div className="space-banner error" role="alert">
              {error}
            </div>
          </div>
        )}
        <ProposalView book={book} onNotice={setNotice} notice={notice} />
      </>
    );
  }
  if (book.status === 'spine_ready') {
    return (
      <>
        {error && (
          <div className="space-content">
            <div className="space-banner error" role="alert">
              {error}
            </div>
          </div>
        )}
        <SpineView book={book} onNotice={setNotice} notice={notice} />
      </>
    );
  }

  const runtimeOf = pageRuntimeOf(book);
  const progress = chapterProgress(book);
  const runMeta = readRunMeta(book);
  const working = Boolean(run) && run!.status === 'running';
  const remoteLease = (() => {
    const lease = getLease(book.id);
    return lease && lease.live && !lease.mine ? lease : null;
  })();

  const handlePause = () => {
    const handle = getRun(book.id);
    if (!handle) return;
    setRunUi((current) => ({ ...current, pausing: true }));
    handle.pause();
    window.setTimeout(() => setRunUi((current) => ({ ...current, pausing: false })), 600);
  };
  const handleResume = () => {
    setRunUi((current) => ({ ...current, resuming: true }));
    // paused 与"已中断（compiling 无执行器）"统一走 resumeRun：
    // 它先把 paused/error 转成 compiling 再启动执行器；直接调 startRun 对 paused 书无效
    // （startRun 只接受 compiling）——刷新/换标签页后点「恢复生成」会静默无操作。
    const handle = resumeRun(book.id);
    if (!handle) {
      setNotice('无法继续生成：本书当前不是可恢复状态，或已有其他标签页在执行（本地模拟执行器）。');
    }
    window.setTimeout(() => setRunUi((current) => ({ ...current, resuming: false })), 600);
  };
  /** 整轮失败（error）的「重试生成」：resumeRun 走 resumeBookRun→startRun，从断点续跑 */
  const handleRetryRun = () => {
    setRunUi((current) => ({ ...current, retrying: true }));
    const handle = resumeRun(book.id);
    if (!handle) {
      // 无 run 记录或他标签页持活租约：明确说明，不留静默无操作
      setNotice('无法重试生成：本书缺少可恢复的运行记录，或已有其他标签页在执行（本地模拟执行器）。');
    }
    window.setTimeout(() => setRunUi((current) => ({ ...current, retrying: false })), 600);
  };

  return (
    <>
      {error && (
        <div className="space-content">
          <div className="space-banner error" role="alert">
            {error}
          </div>
        </div>
      )}
      <ReaderLayout
        book={book}
        pageId={pageId}
        onNotice={setNotice}
        notice={notice}
        runtimeOf={runtimeOf}
        progress={progress}
        working={working}
        remoteLease={Boolean(remoteLease)}
        runStartedAt={runMeta?.startedAt ?? null}
        runUi={runUi}
        onPause={handlePause}
        onResume={handleResume}
        onRetryRun={handleRetryRun}
      />
    </>
  );
}

/** 从书籍记录读取 run 检查点元数据（读取期派生，不写回；字段名按任务卡 §4.2） */
function readRunMeta(book: ReplicaBook): {
  startedAt: number;
  pauseKind?: 'user' | 'provider';
  pauseReason?: string;
  failure?: { kind: string; message: string };
} | null {
  const raw = (
    book as unknown as {
      run?:
        | {
            startedAt?: number;
            pauseKind?: 'user' | 'provider';
            pauseReason?: string;
            failure?: { kind: string; message: string };
          }
        | null;
    }
  ).run;
  if (!raw || typeof raw.startedAt !== 'number') return null;
  return {
    startedAt: raw.startedAt,
    pauseKind: raw.pauseKind,
    pauseReason: raw.pauseReason,
    failure: raw.failure,
  };
}

function ProposalView({
  book,
  onNotice,
  notice,
}: {
  book: ReplicaBook;
  onNotice: (value: string | null) => void;
  notice: string | null;
}) {
  const [confirming, setConfirming] = useState(false);
  const proposal = book.proposal;
  return (
    <div className="space-page books-page">
      <header className="space-header">
        <div className="space-header-row">
          <Link className="space-back" href="/books">
            <ArrowLeft size={16} />
            返回书籍列表
          </Link>
        </div>
        <h1>{book.title}</h1>
        <p className="space-description">{book.description || '（无简介）'}</p>
      </header>
      <main className="space-content">
        <div className="space-banner info" role="note">
          生成流水线未接入：以下提案为本地模板模拟生成，不调用模型；确认后进入大纲确认。
        </div>
        {notice && (
          <div className="space-banner info" role="status">
            {notice}
          </div>
        )}
        <div className="space-empty" style={{ textAlign: 'left' }}>
          <strong>提案（模拟）</strong>
          <span>{proposal?.angle ?? '（无提案）'}</span>
          <span>目标读者：{proposal?.audience ?? '—'}</span>
        </div>
        <section className="space-group">
          <h2 className="space-group-label">拟定章节</h2>
          <ul className="space-session-list">
            {(proposal?.chapters ?? []).map((title, index) => (
              <li className="space-session-card" key={title}>
                <div className="space-session-top">
                  <span className="space-session-title">
                    {index + 1}. {title}
                  </span>
                  <span className="space-chip amber">模拟提案</span>
                </div>
              </li>
            ))}
          </ul>
        </section>
        <div className="space-card-actions">
          <button
            className="space-button primary"
            disabled={confirming}
            onClick={() => {
              setConfirming(true);
              // 本地同步模拟确认：短促 busy 呈现（Loader2 旋转）后落库，操作语义不变
              window.setTimeout(() => {
                const updated = confirmProposal(book.id);
                onNotice(updated ? '已确认提案，进入大纲确认。' : '确认失败：书籍状态已变化。');
                setConfirming(false);
              }, 350);
            }}
          >
            {confirming && <Loader2 size={13} className="space-spin" aria-hidden />}
            确认提案（进入大纲）
          </button>
        </div>
      </main>
    </div>
  );
}

/** 模拟执行器场景设置（队长裁定新增；默认全关，仅本地模拟） */
function ScenarioSettings({
  bookId,
  scenarioRef,
  scenarioBookRef,
}: {
  bookId: string;
  scenarioRef: React.RefObject<BookRunScenario>;
  scenarioBookRef: React.RefObject<string | null>;
}) {
  const [open, setOpen] = useState(false);
  const [failBlocks, setFailBlocks] = useState(false);
  const [failPages, setFailPages] = useState(false);
  const [providerPause, setProviderPause] = useState(false);
  const [storageFailure, setStorageFailure] = useState(false);
  const [storageFailureOnFinish, setStorageFailureOnFinish] = useState(false);
  const [failPagesCount, setFailPagesCount] = useState(1);
  const [providerPauseCount, setProviderPauseCount] = useState(2);
  const [storagePageIndex, setStoragePageIndex] = useState(0);

  // 选择结果写入 ref（BooksRoute 在 startRun 时通过 scenario 传入）
  useEffect(() => {
    scenarioBookRef.current = bookId;
    scenarioRef.current = {
      ...(failBlocks ? { failBlockIds: ['*first'] } : {}),
      ...(failPages ? { failPages: failPagesCount } : {}),
      ...(providerPause ? { providerPauseAfterPages: providerPauseCount } : {}),
      ...(storageFailure ? { storageFailureAt: { pageIndex: storagePageIndex } } : {}),
      ...(storageFailureOnFinish ? { storageFailureOnFinish: true } : {}),
    };
  }, [bookId, scenarioRef, scenarioBookRef, failBlocks, failPages, failPagesCount, providerPause, providerPauseCount, storageFailure, storagePageIndex, storageFailureOnFinish]);

  return (
    <div className="book-pipeline-scenario">
      <button
        type="button"
        className="book-pipeline-scenario-toggle"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
      >
        模拟执行器设置（仅本地模拟）
      </button>
      {open && (
        <div className="book-pipeline-scenario-body">
          <label className="space-toggle">
            <input
              type="checkbox"
              checked={failBlocks}
              onChange={(event) => setFailBlocks(event.target.checked)}
            />
            注入块失败（首个块首次尝试失败，重试即成功）
          </label>
          <label className="space-toggle">
            <input
              type="checkbox"
              checked={failPages}
              onChange={(event) => setFailPages(event.target.checked)}
            />
            注入整页失败（前
            <input
              type="number"
              min={1}
              max={20}
              value={failPagesCount}
              onChange={(event) => setFailPagesCount(Math.max(1, Number(event.target.value) || 1))}
              aria-label="整页失败页数"
            />
            页）
          </label>
          <label className="space-toggle">
            <input
              type="checkbox"
              checked={providerPause}
              onChange={(event) => setProviderPause(event.target.checked)}
            />
            模拟供应商连续失败暂停（连续
            <input
              type="number"
              min={2}
              max={10}
              value={providerPauseCount}
              onChange={(event) => setProviderPauseCount(Math.max(2, Number(event.target.value) || 2))}
              aria-label="供应商暂停阈值"
            />
            页失败）
          </label>
          <label className="space-toggle">
            <input
              type="checkbox"
              checked={storageFailure}
              onChange={(event) => setStorageFailure(event.target.checked)}
            />
            模拟存储写入失败（第
            <input
              type="number"
              min={0}
              max={50}
              value={storagePageIndex}
              onChange={(event) => setStoragePageIndex(Math.max(0, Number(event.target.value) || 0))}
              aria-label="存储失败页序"
            />
            页写入失败）
          </label>
          <label className="space-toggle">
            <input
              type="checkbox"
              checked={storageFailureOnFinish}
              onChange={(event) => setStorageFailureOnFinish(event.target.checked)}
            />
            模拟最终完成写入失败（全部页生成完后，完成状态落库失败；一次性）
          </label>
          <p className="book-pipeline-scenario-note">
            以上均为本地模拟场景注入，用于验证失败与恢复链路；不调用模型，不代表真实供应商或存储故障。设置在确认大纲开始生成时生效。
          </p>
        </div>
      )}
    </div>
  );
}

function SpineView({
  book,
  onNotice,
  notice,
}: {
  book: ReplicaBook;
  onNotice: (value: string | null) => void;
  notice: string | null;
}) {
  const [confirming, setConfirming] = useState(false);
  const scenarioRef = useRef<BookRunScenario>({});
  const scenarioBookRef = useRef<string | null>(null);

  return (
    <div className="space-page books-page">
      <header className="space-header">
        <div className="space-header-row">
          <Link className="space-back" href="/books">
            <ArrowLeft size={16} />
            返回书籍列表
          </Link>
        </div>
        <h1>{book.title}</h1>
        <p className="space-description">大纲已登记（模拟）；确认后由本地模拟执行器逐章逐块异步编译。</p>
      </header>
      <main className="space-content">
        <div className="space-banner info" role="note">
          编译未接入模型：确认大纲后由本地模拟执行器逐章逐块生成（每章 2 页模拟内容），期间可暂停、可恢复，并清空阅读进度重新开始。
        </div>
        {notice && (
          <div className="space-banner info" role="status">
            {notice}
          </div>
        )}
        <ScenarioSettings bookId={book.id} scenarioRef={scenarioRef} scenarioBookRef={scenarioBookRef} />
        {confirming && (
          <div className="books-loading" role="status">
            <Loader2 size={14} className="space-spin" aria-hidden />
            正在生成章节页面（模拟编译）…
          </div>
        )}
        <section className="space-group">
          <h2 className="space-group-label">章节大纲（{book.chapters.length} 章）</h2>
          <ul className="space-session-list">
            {book.chapters.map((chapter, index) => (
              <li className="space-session-card" key={chapter.id}>
                <div className="space-session-top">
                  <span className="space-session-title">
                    {index + 1}. {chapter.title}
                  </span>
                  <span className="space-chip">每章 2 页（模拟）</span>
                </div>
                <div className="space-meta-row">
                  <span>{chapter.summary}</span>
                </div>
              </li>
            ))}
          </ul>
        </section>
        <div className="space-card-actions">
          <button
            className="space-button primary"
            disabled={confirming}
            onClick={() => {
              setConfirming(true);
              // 确认大纲 → 进入 compiling 并启动本地模拟执行器（异步流水线，替代旧同步编译）
              window.setTimeout(() => {
                const updated = confirmSpine(book.id);
                if (!updated) {
                  onNotice('编译失败：书籍状态已变化。');
                  setConfirming(false);
                  return;
                }
                const scenario = scenarioBookRef.current === book.id ? scenarioRef.current : undefined;
                const handle = startRun(book.id, { scenario, source: 'user' });
                onNotice(
                  handle
                    ? '已开始本地模拟编译（异步逐章生成，可在生成中阅读已完成内容）。'
                    : '编译已登记，但本地模拟执行器未能启动（可能已在其他标签页生成）。',
                );
                setConfirming(false);
              }, 350);
            }}
          >
            {confirming && <Loader2 size={13} className="space-spin" aria-hidden />}
            确认大纲并编译（模拟）
          </button>
        </div>
      </main>
    </div>
  );
}

function ReaderLayout({
  book,
  pageId,
  onNotice,
  notice,
  runtimeOf,
  progress,
  working,
  remoteLease,
  runStartedAt,
  runUi,
  onPause,
  onResume,
  onRetryRun,
}: {
  book: ReplicaBook;
  pageId?: string;
  onNotice: (value: string | null) => void;
  notice: string | null;
  runtimeOf: (pageId: string) => PageRuntime;
  progress: { doneChapters: number; totalChapters: number; donePages: number; totalPages: number };
  working: boolean;
  remoteLease: boolean;
  runStartedAt: number | null;
  runUi: RunUiState;
  onPause: () => void;
  onResume: () => void;
  onRetryRun: () => void;
}) {
  const [exporting, setExporting] = useState(false);
  const pages = book.chapters.flatMap((chapter) => chapter.pageIds);
  const index = pageId ? pages.indexOf(pageId) : -1;
  const page = pageId ? pages[index] ?? null : null;

  if (!pageId || !page) {
    // 深链页码无效：提示并回有效页
    return (
      <div className="space-page books-page">
        <div className="space-empty" style={{ marginTop: 80 }}>
          <strong>章节页不存在或已被重建</strong>
          <span>书籍可能已重新编译，旧页码失效。</span>
          <Link className="space-button" href={`/books/${book.id}`}>
            返回书籍首页
          </Link>
        </div>
      </div>
    );
  }

  const runMeta = readRunMeta(book);
  const stripPhase =
    book.status === 'paused'
      ? ('paused' as const)
      : book.status === 'compiling' && !working && !remoteLease
        ? ('interrupted' as const)
        : book.status === 'compiling'
          ? runMeta && progress.doneChapters === 0 && progress.donePages === 0
            ? ('preparing' as const)
            : ('compilation' as const)
          : null;
  const showStrip =
    (stripPhase !== null && (working || remoteLease)) ||
    (stripPhase === 'interrupted') ||
    book.status === 'paused';
  const stripChapters = deriveStripChapters(book, book.chapters, runtimeOf);

  return (
    <div className="space-page books-page">
      <header className="space-header">
        <div className="space-header-row">
          <Link className="space-back" href="/books">
            <ArrowLeft size={16} />
            返回书籍列表
          </Link>
          <div className="space-card-actions">
            <button
              className="space-button"
              disabled={exporting}
              onClick={() => {
                setExporting(true);
                const result = exportBookMarkdown(book.id);
                if (!result) {
                  setExporting(false);
                  return;
                }
                const blob = new Blob([result.content], { type: 'text/markdown;charset=utf-8' });
                const url = URL.createObjectURL(blob);
                const anchor = document.createElement('a');
                anchor.href = url;
                anchor.download = result.name;
                anchor.click();
                URL.revokeObjectURL(url);
                onNotice(`已导出「${result.name}」。`);
                setExporting(false);
              }}
            >
              {exporting && <Loader2 size={13} className="space-spin" aria-hidden />}
              导出 Markdown
            </button>
            <button
              className="space-button danger"
              disabled={exporting}
              onClick={() => {
                if (window.confirm(`重建书籍「${book.title}」？将重新模拟编译并清空阅读进度。`)) {
                  rebuildBook(book.id);
                  onNotice('已重建（模拟重新编译），阅读进度已清空。');
                }
              }}
            >
              <RotateCcw size={13} aria-hidden />
              重建书籍
            </button>
          </div>
        </div>
        <h1>{book.title}</h1>
        <p className="space-description">
          {/* 整轮失败的原因只在下方横幅里呈现一次（那里带「重试生成」入口），此处不重复长文案 */}
          阅读进度 {readingPercent(book)}% · 已读 {book.reading.visitedPageIds.length}/{pages.length} 页
          {book.status === 'archived' && (
            <span className="space-chip" style={{ marginLeft: 8 }}>
              已归档（可读）
            </span>
          )}
        </p>
      </header>
      {notice && (
        <div className="space-content">
          <div className="space-banner info" role="status">
            {notice}
          </div>
        </div>
      )}
      <main className="space-content">
        {book.status === 'error' && (
          <div className="space-banner error" role="alert">
            <span className="book-pipeline-error-text">
              生成失败（本地模拟）：{runMeta?.failure?.message ?? '生成中断，未完成章节未半写。'}
            </span>
            <span className="book-pipeline-error-actions">
              <button className="space-button" onClick={onRetryRun} disabled={runUi.retrying}>
                {runUi.retrying ? (
                  <Loader2 size={13} className="space-spin" aria-hidden />
                ) : (
                  <RefreshCcw size={13} aria-hidden />
                )}
                {runUi.retrying ? '正在重试…' : '重试生成'}
              </button>
              <span className="space-footnote">从断点续跑（已完成页不重复生成）；也可用「重建书籍」整本重新模拟编译。</span>
            </span>
          </div>
        )}
        {book.status === 'paused' && runMeta?.pauseKind && (
          <BookPausedBanner
            pauseKind={runMeta.pauseKind}
            pauseReason={runMeta.pauseReason ?? null}
            resuming={runUi.resuming}
            onResume={onResume}
          />
        )}
        {showStrip && stripPhase !== null && (
          <BookGenerationStrip
            phase={stripPhase}
            working={working}
            doneChapters={progress.doneChapters}
            totalChapters={progress.totalChapters}
            startedAt={runStartedAt}
            chapters={stripChapters}
            pausing={runUi.pausing}
            resuming={runUi.resuming}
            remote={remoteLease}
            onPause={onPause}
            onResume={onResume}
          />
        )}
        <div className="books-layout">
          <BookSidebar book={book} currentPageId={pageId} runtimeOf={runtimeOf} />
          {/* key 按 pageId 重置页内状态（练习作答等） */}
          <PageReader key={pageId} book={book} pageId={pageId} />
        </div>
      </main>
    </div>
  );
}

function BookSidebar({
  book,
  currentPageId,
  runtimeOf,
}: {
  book: ReplicaBook;
  currentPageId: string;
  runtimeOf: (pageId: string) => PageRuntime;
}) {
  return (
    <nav className="space-scope-rail books-rail" aria-label="章节目录">
      {book.chapters.map((chapter, chapterIndex) => (
        <div key={chapter.id}>
          <p className="space-group-label" style={{ margin: '10px 0 4px' }}>
            第 {chapterIndex + 1} 章 · {chapter.title}
          </p>
          {chapter.pageIds.map((pageId, offset) => {
            const visited = book.reading.visitedPageIds.includes(pageId);
            const bookmarked = book.reading.bookmarkedPageIds.includes(pageId);
            const runtime = runtimeOf(pageId);
            const isLegacy = book.status === 'ready' || book.status === 'archived';
            const statusLabel = PAGE_STATUS_LABEL[runtime.status] ?? '';
            return (
              <Link
                key={pageId}
                className={`space-scope-item ${pageId === currentPageId ? 'current' : ''}`}
                aria-current={pageId === currentPageId ? 'page' : undefined}
                href={`/books/${book.id}/pages/${pageId}`}
                style={visited ? undefined : { opacity: 0.75 }}
                title={`${chapter.title}（${offset + 1}/2）${
                  isLegacy
                    ? visited
                      ? ' · 已读'
                      : ' · 未读'
                    : ` · ${statusLabel}${visited ? ' · 已读' : ''}`
                }`}
              >
                <span
                  aria-hidden
                  className={`book-pipeline-page-dot ${
                    isLegacy
                      ? visited
                        ? 'accent'
                        : 'queued'
                      : (PAGE_STATUS_DOT[runtime.status] ?? 'queued')
                  }`}
                />
                <span className="books-rail-title">
                  {chapter.title}（{offset + 1}/2）
                </span>
                {!isLegacy && (
                  <span className="book-pipeline-page-mark" aria-hidden>
                    {statusLabel}
                  </span>
                )}
                {bookmarked && (
                  <span className="books-bookmark-mark" aria-label="已加书签" title="已加书签">
                    <Bookmark size={10} aria-hidden />
                    签
                  </span>
                )}
              </Link>
            );
          })}
        </div>
      ))}
    </nav>
  );
}
