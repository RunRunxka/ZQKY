'use client';
import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { useParams, useRouter } from 'next/navigation';
import { ArrowLeft, BookMarked, Sparkles } from 'lucide-react';
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
import '@/features/space/styles/space.css';
import '@/features/books/books.css';
import { PageReader } from './PageReader';

const STATUS_LABEL: Record<ReplicaBook['status'], string> = {
  draft: '草稿 · 待确认提案',
  spine_ready: '大纲待确认',
  ready: '可阅读',
  archived: '已归档',
};

const STATUS_TONE: Record<ReplicaBook['status'], string> = {
  draft: 'amber',
  spine_ready: 'blue',
  ready: 'green',
  archived: '',
};

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
  const chapterTotal = books.reduce((sum, book) => sum + book.chapters.length, 0);

  return (
    <div className="space-page">
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
          生成流水线未接入：提案、大纲与编译为本地确定性模拟（显式标注），阅读进度与导出在本地保存。
        </p>
      </header>
      <main className="space-content">
        <div className="space-meta-row" role="note">
          <span className="space-chip">共 {books.length} 本</span>
          <span className="space-chip">进行中 {active.filter((book) => book.status !== 'ready').length}</span>
          <span className="space-chip">可阅读 {active.filter((book) => book.status === 'ready').length}</span>
          <span className="space-chip">章节 {chapterTotal}</span>
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
            {books.length > 6 && (
              <div className="space-toolbar">
                <input
                  className="space-search"
                  type="search"
                  placeholder="按书名搜索…"
                  aria-label="搜索书籍"
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                />
              </div>
            )}
            <div className="space-card-grid">
              {filtered.map((book) => {
                const pages = book.status === 'ready' ? book.chapters.reduce((sum, chapter) => sum + chapter.pageIds.length, 0) : 0;
                const percent = readingPercent(book);
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
                      </div>
                      <p className="space-card-body">{book.description || '（无简介）'}</p>
                      <div className="space-meta-row">
                        <span className={`space-chip ${STATUS_TONE[book.status]}`}>{STATUS_LABEL[book.status]}</span>
                        <span className="space-chip">{book.chapters.length} 章</span>
                        {book.status === 'ready' && <span className="space-chip">{pages} 页</span>}
                      </div>
                      {book.status === 'ready' && (
                        <div className="space-reading-bar" aria-label={`阅读进度 ${percent}%`}>
                          <div className="space-reading-bar-fill" style={{ width: `${percent}%` }} />
                        </div>
                      )}
                      <span className="space-footnote">更新于 {new Date(book.updatedAt).toLocaleString('zh-CN')}</span>
                    </Link>
                    <div className="space-card-actions" style={{ marginTop: 8 }}>
                      <button
                        className="space-button"
                        onClick={() => router.push(`/books/${book.id}`)}
                      >
                        {cta}
                      </button>
                      <button
                        className="space-button danger"
                        onClick={() => {
                          if (window.confirm(`删除书籍「${book.title}」？本地阅读进度将一并移除。`)) {
                            deleteBook(book.id);
                          }
                        }}
                      >
                        删除
                      </button>
                    </div>
                  </article>
                );
              })}
            </div>
            {books.length > 6 && filtered.length === 0 && (
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
  return (
    <Modal title="新建书籍" onClose={onClose}>
      <form
        className="space-form"
        onSubmit={(event) => {
          event.preventDefault();
          try {
            const book = createBook(title, description);
            onCreated(book.id);
          } catch (cause) {
            setError(
              cause instanceof BookValidationError ? cause.message : '创建失败，请检查输入后重试。',
            );
          }
        }}
      >
        <p className="space-footnote" style={{ marginTop: 0 }}>
          创建后立即生成本地模拟提案；确认提案→确认大纲后同步模拟编译为可读书籍（不调用模型）。
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
          <button type="submit" className="space-button primary">
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

  const refresh = useCallback(() => {
    try {
      setBooks(readBooks());
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '书籍目录无法读取，原数据未修改。');
    }
  }, []);

  useEffect(() => {
    refresh();
    return subscribeBooks(refresh);
  }, [refresh]);

  const book = useMemo(() => books?.find((item) => item.id === bookId) ?? null, [books, bookId]);

  // 就绪书未带页码时自动续读（当前页 → 首页）
  useEffect(() => {
    if (!book || book.status !== 'ready' || pageId) return;
    const firstPageId =
      book.reading.currentPageId ?? book.chapters.flatMap((chapter) => chapter.pageIds)[0] ?? null;
    if (firstPageId) router.replace(`/books/${bookId}/pages/${firstPageId}`);
  }, [book, bookId, pageId, router]);

  if (books !== null && !book) {
    return (
      <div className="space-page">
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
      <div className="space-page">
        <div className="space-banner" style={{ marginTop: 80 }}>
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
  return (
    <>
      {error && (
        <div className="space-content">
          <div className="space-banner error" role="alert">
            {error}
          </div>
        </div>
      )}
      <ReaderLayout book={book} pageId={pageId} onNotice={setNotice} notice={notice} />
    </>
  );
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
  const proposal = book.proposal;
  return (
    <div className="space-page">
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
            onClick={() => {
              const updated = confirmProposal(book.id);
              onNotice(updated ? '已确认提案，进入大纲确认。' : '确认失败：书籍状态已变化。');
            }}
          >
            确认提案（进入大纲）
          </button>
        </div>
      </main>
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
  return (
    <div className="space-page">
      <header className="space-header">
        <div className="space-header-row">
          <Link className="space-back" href="/books">
            <ArrowLeft size={16} />
            返回书籍列表
          </Link>
        </div>
        <h1>{book.title}</h1>
        <p className="space-description">大纲已登记（模拟）；确认后同步编译为可读书籍。</p>
      </header>
      <main className="space-content">
        <div className="space-banner info" role="note">
          编译未接入模型：确认大纲将按本地模板每章生成 2 页模拟内容，并清空阅读进度重新开始。
        </div>
        {notice && (
          <div className="space-banner info" role="status">
            {notice}
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
            onClick={() => {
              const updated = confirmSpine(book.id);
              onNotice(updated ? '模拟编译完成，书籍已可阅读。' : '编译失败：书籍状态已变化。');
            }}
          >
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
}: {
  book: ReplicaBook;
  pageId?: string;
  onNotice: (value: string | null) => void;
  notice: string | null;
}) {
  const pages = book.chapters.flatMap((chapter) => chapter.pageIds);
  const index = pageId ? pages.indexOf(pageId) : -1;
  const page = pageId ? pages[index] ?? null : null;

  if (!pageId || !page) {
    // 深链页码无效：提示并回有效页
    return (
      <div className="space-page">
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

  return (
    <div className="space-page">
      <header className="space-header">
        <div className="space-header-row">
          <Link className="space-back" href="/books">
            <ArrowLeft size={16} />
            返回书籍列表
          </Link>
          <div className="space-card-actions">
            <button
              className="space-button"
              onClick={() => {
                const result = exportBookMarkdown(book.id);
                if (!result) return;
                const blob = new Blob([result.content], { type: 'text/markdown;charset=utf-8' });
                const url = URL.createObjectURL(blob);
                const anchor = document.createElement('a');
                anchor.href = url;
                anchor.download = result.name;
                anchor.click();
                URL.revokeObjectURL(url);
                onNotice(`已导出「${result.name}」。`);
              }}
            >
              导出 Markdown
            </button>
            <button
              className="space-button danger"
              onClick={() => {
                if (window.confirm(`重建书籍「${book.title}」？将重新模拟编译并清空阅读进度。`)) {
                  rebuildBook(book.id);
                  onNotice('已重建（模拟重新编译），阅读进度已清空。');
                }
              }}
            >
              重建书籍
            </button>
          </div>
        </div>
        <h1>{book.title}</h1>
        <p className="space-description">
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
      <main className="space-content books-layout">
        <BookSidebar book={book} currentPageId={pageId} />
        {/* key 按 pageId 重置页内状态（练习作答等） */}
        <PageReader key={pageId} book={book} pageId={pageId} />
      </main>
    </div>
  );
}

function BookSidebar({ book, currentPageId }: { book: ReplicaBook; currentPageId: string }) {
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
            return (
              <Link
                key={pageId}
                className={`space-scope-item ${pageId === currentPageId ? 'current' : ''}`}
                aria-current={pageId === currentPageId ? 'page' : undefined}
                href={`/books/${book.id}/pages/${pageId}`}
                style={visited ? undefined : { opacity: 0.75 }}
              >
                <span
                  aria-hidden
                  style={{
                    width: 8,
                    height: 8,
                    borderRadius: 999,
                    flexShrink: 0,
                    background: visited ? 'var(--ink, #222)' : 'transparent',
                    border: '1px solid var(--ink, #222)',
                  }}
                />
                <span style={{ flex: 1, textAlign: 'left' }}>
                  {chapter.title}（{offset + 1}/2）
                </span>
                {bookmarked && (
                  <span className="space-chip amber" aria-label="已加书签">
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
