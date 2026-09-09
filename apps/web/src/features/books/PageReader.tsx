'use client';
import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Bookmark, ChevronLeft, ChevronRight, Copy } from 'lucide-react';
import {
  latestQuizAttempt,
  markVisited,
  recordQuizAttempt,
  setUserNote,
  toggleBookmark,
  type BookBlock,
  type ReplicaBook,
} from '@/services/books-store';
import '@/features/books/books.css';

/** 阅读器：Block 分发渲染（对照参考 BlockRenderer 的 14 类本地形态）+ 翻页/键盘/书签/已读登记 */
export function PageReader({ book, pageId }: { book: ReplicaBook; pageId: string }) {
  const router = useRouter();
  const pages = useMemo(
    () => book.chapters.flatMap((chapter) => chapter.pageIds),
    [book.chapters],
  );
  const index = pages.indexOf(pageId);
  const chapter = book.chapters.find((item) => item.pageIds.includes(pageId)) ?? null;
  const bookmarked = book.reading.bookmarkedPageIds.includes(pageId);

  // 打开章节即登记已读（对照参考 markVisited）
  useEffect(() => {
    markVisited(book.id, pageId);
  }, [book.id, pageId]);

  // 键盘翻章（对照参考 ←/→）
  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
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
            onClick={() => toggleBookmark(book.id, pageId)}
          >
            <Bookmark size={13} fill={bookmarked ? 'currentColor' : 'none'} />
            {bookmarked ? '已加书签' : '书签'}
          </button>
        </span>
      </div>
      <h2 style={{ marginTop: 0 }}>
        <Link href={`/books/${book.id}`}>{book.title}</Link>
      </h2>
      <div className="space-banner info" role="note" style={{ marginBottom: 14 }}>
        本页内容为本地模拟编译产物（显式标注），非模型生成；练习作答与页内笔记本地持久化，跨会话恢复（参考为服务端 attempt）。
      </div>
      {(chapter?.pageIds ?? []).indexOf(pageId) >= 0 &&
        findBlocks(book, pageId).map((block) => (
          <BookBlockView key={block.id} block={block} bookId={book.id} pageId={pageId} />
        ))}
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

function findBlocks(book: ReplicaBook, pageId: string): BookBlock[] {
  // 页面内联在书籍记录（本地仓储形态）；经 chapters.pageIds 定位
  const raw = (book as unknown as { pages?: { id: string; blocks: BookBlock[] }[] }).pages;
  return raw?.find((page) => page.id === pageId)?.blocks ?? [];
}

function BookBlockView({ block, bookId, pageId }: { block: BookBlock; bookId: string; pageId: string }) {
  const [answer, setAnswer] = useState<string | null>(null);
  const [note, setNote] = useState(block.type === 'user_note' ? block.content : '');
  const [flipped, setFlipped] = useState<Record<number, boolean>>({});
  const [copied, setCopied] = useState(false);

  // 进入页面恢复最近一次作答（练习答案本地持久化）
  useEffect(() => {
    if (block.type !== 'quiz') return;
    const attempt = latestQuizAttempt(bookId, pageId, block.id);
    if (attempt) setAnswer(attempt.choice);
  }, [bookId, pageId, block.id, block.type]);

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
          onChange={(event) => setNote(event.target.value)}
          onBlur={() => {
            setUserNote(bookId, pageId, block.id, note);
          }}
        />
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
                recordQuizAttempt({ bookId, pageId, blockId: block.id, choice: key, correct: key === block.quiz!.correct });
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
