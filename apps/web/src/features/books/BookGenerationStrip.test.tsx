import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import {
  BookGenerationStrip,
  deriveStripChapters,
  formatRunElapsed,
  type BookStripChapterState,
} from './BookGenerationStrip';
import type { BookChapter, ReplicaBook } from '@/services/books-store';

// jsdom 无 matchMedia：strip 不依赖它，但维持与既有测试一致的环境补丁习惯
beforeAll(() => {
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
    }));
  }
});

afterEach(() => {
  cleanup();
});

const idleChapters: BookStripChapterState[] = [
  { key: 'ch-1', label: '01 · 比喻是什么', doneBlocks: 4, totalBlocks: 4, generatingBlock: null, hasFailure: false, active: false },
  { key: 'ch-2', label: '02 · 拟人与夸张', doneBlocks: 2, totalBlocks: 8, generatingBlock: '正文段落', hasFailure: false, active: true },
  { key: 'ch-3', label: '03 · 修辞的常见误区', doneBlocks: 0, totalBlocks: 8, generatingBlock: null, hasFailure: false, active: true },
];

function stripProps(overrides: Partial<Parameters<typeof BookGenerationStrip>[0]> = {}) {
  return {
    phase: 'compilation' as const,
    working: true,
    doneChapters: 1,
    totalChapters: 3,
    startedAt: Date.now() - 65_000,
    chapters: idleChapters,
    pausing: false,
    resuming: false,
    onPause: vi.fn(),
    onResume: vi.fn(),
    ...overrides,
  };
}

describe('BookGenerationStrip（本地模拟流水线活动条）', () => {
  it('运行中呈现阶段文案、n/m 章与 mm:ss 计时，role=status 且 polite', () => {
    render(<BookGenerationStrip {...stripProps()} />);
    const status = screen.getByRole('status');
    expect(status).toHaveAttribute('aria-live', 'polite');
    expect(status).toHaveTextContent('正在逐章编译（本地模拟，不调用模型）');
    expect(status).toHaveTextContent('1/3 章');
    expect(status).toHaveTextContent('01:05');
  });

  it('运行中显示「暂停生成」，点击触发 onPause；pausing 时切换为「正在暂停…」并禁用', () => {
    const onPause = vi.fn();
    const { rerender } = render(<BookGenerationStrip {...stripProps({ onPause })} />);
    const pauseButton = screen.getByRole('button', { name: '暂停生成' });
    fireEvent.click(pauseButton);
    expect(onPause).toHaveBeenCalledTimes(1);
    rerender(<BookGenerationStrip {...stripProps({ onPause, pausing: true })} />);
    const busy = screen.getByRole('button', { name: '正在暂停…' });
    expect(busy).toBeDisabled();
  });

  it('无执行器的 compiling 显示「继续生成」（RefreshCcw 图标文案）；点击触发 onResume', () => {
    const onResume = vi.fn();
    render(<BookGenerationStrip {...stripProps({ working: false, onResume })} />);
    const continueButton = screen.getByRole('button', { name: '继续生成' });
    fireEvent.click(continueButton);
    expect(onResume).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('button', { name: '暂停生成' })).not.toBeInTheDocument();
  });

  it('paused 显示「恢复生成」与已暂停阶段文案，不再显示暂停按钮', () => {
    render(<BookGenerationStrip {...stripProps({ phase: 'paused', working: false })} />);
    expect(screen.getByRole('button', { name: '恢复生成' })).toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('生成已暂停');
    expect(screen.queryByRole('button', { name: '暂停生成' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '继续生成' })).not.toBeInTheDocument();
  });

  it('已中断（compiling 无执行器）显示中断文案与「继续生成」，点击触发 onResume', () => {
    const onResume = vi.fn();
    render(
      <BookGenerationStrip {...stripProps({ phase: 'interrupted', working: false, onResume })} />,
    );
    // 中断态必须有恢复入口（否则页失败后的书只能靠"重建书籍"清空进度重新来）
    expect(screen.getByRole('status')).toHaveTextContent('生成已中断（无执行器在跑）');
    const continueButton = screen.getByRole('button', { name: '继续生成' });
    fireEvent.click(continueButton);
    expect(onResume).toHaveBeenCalledTimes(1);
    expect(screen.queryByRole('button', { name: '暂停生成' })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '恢复生成' })).not.toBeInTheDocument();
  });

  it('点击「已生成内容」展开 role=dialog 浮层，按章分组列出块级进度与状态', () => {
    render(<BookGenerationStrip {...stripProps()} />);
    const toggle = screen.getByRole('button', { name: '已生成内容' });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(toggle);
    expect(toggle).toHaveAttribute('aria-expanded', 'true');
    const dialog = screen.getByRole('dialog', { name: '已生成内容' });
    expect(dialog).toHaveTextContent('章节');
    expect(dialog).toHaveTextContent('01 · 比喻是什么');
    expect(dialog).toHaveTextContent('已完成 4/4 块');
    expect(dialog).toHaveTextContent('正在生成 正文段落');
    expect(dialog).toHaveTextContent('排队');
    // 浮层不得是 46px 活动条（role=status）的子节点：那条是 overflow:hidden 的 flex 行，
    // 子节点会被裁成一条线（曾在浏览器里真的发生过，见 DEFECT-LEDGER N10）
    expect(screen.getByRole('status').contains(dialog)).toBe(false);
    expect(dialog.closest('.book-pipeline-strip')).toBeNull();
    expect(dialog.closest('.book-pipeline-strip-shell')).not.toBeNull();
    fireEvent.click(toggle);
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  it('部分块失败的章显示「部分块失败」', () => {
    const chapters: BookStripChapterState[] = [
      { key: 'ch-1', label: '01 · 失败章', doneBlocks: 2, totalBlocks: 4, generatingBlock: null, hasFailure: true, active: true },
    ];
    render(<BookGenerationStrip {...stripProps({ chapters, totalChapters: 1, doneChapters: 0 })} />);
    fireEvent.click(screen.getByRole('button', { name: '已生成内容' }));
    expect(screen.getByRole('dialog', { name: '已生成内容' })).toHaveTextContent('部分块失败');
  });

  it('他标签页执行时显示「本书正在另一个标签页生成」且本标签不提供暂停控制', () => {
    render(<BookGenerationStrip {...stripProps({ remote: true, working: false })} />);
    expect(screen.getByText('本书正在另一个标签页生成')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '暂停生成' })).not.toBeInTheDocument();
  });
});

describe('formatRunElapsed（计时格式对照参考 mm:ss / h:mm:ss）', () => {
  it('不足 1 小时为 mm:ss，超 1 小时为 h:mm:ss', () => {
    expect(formatRunElapsed(0)).toBe('00:00');
    expect(formatRunElapsed(5_000)).toBe('00:05');
    expect(formatRunElapsed(65_000)).toBe('01:05');
    expect(formatRunElapsed(3_723_000)).toBe('1:02:03');
    expect(formatRunElapsed(-100)).toBe('00:00');
  });
});

describe('deriveStripChapters（从书籍记录派生章级状态）', () => {
  const book = {
    id: 'bk-x',
    chapters: [
      { id: 'ch-1', title: '第一章', summary: '', pageIds: ['pg-1', 'pg-2'] },
    ],
    pages: [
      {
        id: 'pg-1',
        blocks: [
          { id: 'b1', status: 'ready', title: '导语' },
          { id: 'b2', status: 'ready' },
        ],
      },
      {
        id: 'pg-2',
        blocks: [
          { id: 'b3', status: 'generating', title: '练习' },
          { id: 'b4', status: 'error', title: '插图' },
        ],
      },
    ],
  } as unknown as ReplicaBook;
  const chapters: BookChapter[] = book.chapters;
  const pageStateOf = (pageId: string) =>
    pageId === 'pg-1'
      ? { status: 'ready' as const, generatingBlockTitle: null }
      : pageId === 'pg-2'
        ? { status: 'partial' as const, generatingBlockTitle: '练习' }
        : { status: 'pending' as const, generatingBlockTitle: null };

  it('统计完成块、生成中块名与失败标记；缺 status 的旧块按 ready 读取', () => {
    const derived = deriveStripChapters(book, chapters, pageStateOf);
    expect(derived).toHaveLength(1);
    const chapter = derived[0]!;
    expect(chapter.label).toBe('01 · 第一章');
    expect(chapter.doneBlocks).toBe(2);
    expect(chapter.totalBlocks).toBe(4);
    expect(chapter.generatingBlock).toBe('练习');
    expect(chapter.hasFailure).toBe(true);
    expect(chapter.active).toBe(true);
  });

  it('全部 ready 的章视为不活跃（完成）', () => {
    const readyBook = {
      ...book,
      pages: [
        {
          id: 'pg-1',
          blocks: [
            { id: 'b1', status: 'ready', title: '导语' },
            { id: 'b2', status: 'ready' },
          ],
        },
        {
          id: 'pg-2',
          blocks: [
            { id: 'b3', status: 'ready', title: '练习' },
            { id: 'b4' },
          ],
        },
      ],
    } as unknown as ReplicaBook;
    const allReady = deriveStripChapters(
      readyBook,
      chapters,
      () => ({ status: 'ready' as const, generatingBlockTitle: null }),
    );
    expect(allReady[0]!.active).toBe(false);
    expect(allReady[0]!.hasFailure).toBe(false);
  });
});
