'use client';
import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import { Bookmark, ChevronLeft, ChevronRight } from 'lucide-react';
import {
  markVisited,
  toggleBookmark,
  type BookBlock,
  type ReplicaBook,
} from '@/services/books-store';
import '@/features/books/books.css';

/** 阅读器：Block 分发渲染（对照参考 BlockRenderer 的本地子集）+ 翻页/键盘/书签/已读登记 */
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
        本页内容为本地模拟编译产物（显式标注），非模型生成；作答仅在当前页判定，不作答记录持久化（参考为服务端 attempt）。
      </div>
      {(chapter?.pageIds ?? []).indexOf(pageId) >= 0 &&
        findBlocks(book, pageId).map((block) => <BookBlockView key={block.id} block={block} />)}
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

function BookBlockView({ block }: { block: BookBlock }) {
  const [answer, setAnswer] = useState<string | null>(null);
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
              onClick={() => setAnswer(key)}
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
