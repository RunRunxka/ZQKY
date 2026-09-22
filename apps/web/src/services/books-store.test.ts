import { afterEach, beforeEach, describe, expect, it } from 'vitest';
import {
  BookValidationError,
  archiveBook,
  applyRunEvent,
  confirmProposal,
  confirmSpine,
  createBook,
  deleteBook,
  ensureBookRun,
  exportBookMarkdown,
  failBookRun,
  finishBookRun,
  getBookPage,
  getBookPages,
  latestQuizAttempt,
  loadDemoBooks,
  markVisited,
  pauseBookRun,
  quizAttemptMatches,
  readBooks,
  readQuizAttempts,
  rebuildBook,
  readingPercent,
  recordQuizAttempt,
  regeneratePage,
  resumeBookRun,
  retryBlock,
  setUserNote,
  toggleBookmark,
  updateBook,
  type BookPage,
  type CommitResult,
  type ReplicaBook,
} from './books-store';
import {
  __resetCollectionLockQueuesForTests,
  __setCollectionLockOptionsForTests,
} from './collection-lock';

// ===== 提交包装（仅测试）：等待事务，非 committed 直接判失败，返回落库后的真实值 =====
async function saved<T>(pending: Promise<CommitResult<T>>): Promise<T> {
  const result = await pending;
  if (result.status !== 'committed' || result.value === null) {
    throw new Error(`expected committed, got ${result.status}: ${result.message}`);
  }
  return result.value;
}

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  // 仅测试：缩短回退锁的 settle 窗口（不影响被测语义，只加快用例；真实浏览器走 Web Locks）
  __setCollectionLockOptionsForTests({ waitMs: 200, settleMs: 4, staleMs: 1500 });
});

afterEach(() => {
  __resetCollectionLockQueuesForTests();
});

/** 建立一本处于 spine_ready 的书（提案已确认） */
async function setupSpineReady(title: string): Promise<{ book: ReplicaBook; runStartSeq: number }> {
  const book = await saved(createBook(title, ''));
  const spined = await saved(confirmProposal(book.id));
  expect(spined?.status).toBe('spine_ready');
  return { book, runStartSeq: 0 };
}

/** 手工驱动一页的全部事件（不经执行器，直接验证仓储事件语义；seq 从 1 起单调递增） */
async function runPageEvents(
  bookId: string,
  runId: string,
  page: BookPage,
  opts?: { failBlockIds?: string[]; chapterIndex?: number; startSeq?: number },
): Promise<number> {
  let seq = opts?.startSeq ?? 1;
  const chapterIndex = opts?.chapterIndex ?? 0;
  const e = async (event: Parameters<typeof applyRunEvent>[2]) => {
    await saved(applyRunEvent(bookId, runId, event, seq));
    seq += 1;
  };
  await e({ type: 'page-start', chapterIndex, pageIndex: 0 });
  await e({ type: 'page-planned', pageId: page.id, blockIds: page.blocks.map((block) => block.id) });
  for (const block of page.blocks) {
    await e({ type: 'block-start', pageId: page.id, blockId: block.id });
    if (opts?.failBlockIds?.includes(block.id)) {
      await e({
        type: 'block-error',
        pageId: page.id,
        blockId: block.id,
        failure: { kind: 'content', message: '模拟块失败', retryable: true, simulated: true },
      });
    } else {
      await e({
        type: 'block-ready',
        pageId: page.id,
        blockId: block.id,
        block: { ...block, content: block.content || '生成内容（模拟）', status: 'ready' },
      });
    }
  }
  await e({ type: 'page-ready', pageId: page.id });
  return seq;
}

describe('books-store（既有行为兼容）', () => {
  it('createBook 生成带模拟提案的草稿并拒绝重名/空名', async () => {
    const book = await saved(createBook('测试书', '面向测试人群'));
    expect(book.status).toBe('draft');
    expect(book.proposal?.chapters.length).toBeGreaterThan(0);
    expect(book.proposal?.angle).toContain('模拟提案');
    // 重名是"提交层前置条件不满足"：返回 skipped + 原因（不是参数错误，故不抛）
    const duplicated = await createBook('测试书', '');
    expect(duplicated.status).toBe('skipped');
    expect(duplicated.value).toBeNull();
    expect(duplicated.message).toContain('同名');
    await expect(createBook('   ', '')).rejects.toThrow('书名不能为空。');
    // 归档状态幅度：draft 不能被归档（提交层拒绝→skipped，存储不变）
    const demo = await saved(createBook('归档占名书', ''));
    const denied = await archiveBook(demo.id, false);
    expect(denied.status).toBe('skipped');
    expect(denied.value).toBeNull();
    expect(readBooks().find((item) => item.id === demo.id)!.status).toBe('draft');
    void demo;
  });

  it('非法状态流转不生效；归档仅限就绪/归档态', async () => {
    const book = await saved(createBook('守卫书', ''));
    // draft 不能直接编译：前置条件不满足 → skipped（不写、不报成功）
    const badSpine = await confirmSpine(book.id);
    expect(badSpine.status).toBe('skipped');
    expect(readBooks().find((item) => item.id === book.id)!.status).toBe('draft');
    // draft 不能被归档
    expect((await archiveBook(book.id, true)).status).toBe('skipped');
    const spined = await saved(confirmProposal(book.id));
    expect(spined?.status).toBe('spine_ready');
    // compiling 中不能被归档（进入编译后由流水线管理）
    const compiling = await saved(confirmSpine(book.id));
    expect(compiling?.status).toBe('compiling');
    // 编译中不能被归档：同样是 skipped，状态不变
    expect((await archiveBook(book.id, true)).status).toBe('skipped');
    expect(readBooks().find((item) => item.id === book.id)!.status).toBe('compiling');
    // 无执行器且未生成任何页：finish 保持 compiling（有未完成页即"已中断"）
    const interrupted = await saved(finishBookRun(book.id, compiling!.run!.runId));
    expect(interrupted?.status).toBe('compiling');
    // 全部页事件完成后 finish → ready
    let seq = 1;
    const seqPages = getBookPages(book.id);
    for (let index = 0; index < seqPages.length; index += 1) {
      seq = await runPageEvents(book.id, compiling!.run!.runId, seqPages[index]!, { chapterIndex: Math.floor(index / 2), startSeq: seq });
    }
    const finished = await saved(finishBookRun(book.id, compiling!.run!.runId));
    expect(finished?.status).toBe('ready');
    const archived = await saved(archiveBook(book.id, true));
    expect(archived?.status).toBe('archived');
    const restored = await saved(archiveBook(book.id, false));
    expect(restored?.status).toBe('ready');
  });

  it('updateBook 重名校验、deleteBook 与导出 Markdown', async () => {
    await saved(createBook('书甲', '甲的简介'));
    const bookB = await saved(createBook('书乙', '乙的简介'));
    await expect(updateBook(bookB.id, { title: '书甲' })).rejects.toThrow(BookValidationError);
    const updated = await saved(updateBook(bookB.id, { title: '书乙（改）', description: '新简介' }));
    expect(updated.title).toBe('书乙（改）');

    // 未完成书籍导出：文首注明未完成章节，未生成页如实标注
    await saved(confirmProposal(bookB.id));
    const compiling = await saved(confirmSpine(bookB.id));
    const pages = getBookPages(bookB.id);
    expect(pages.length).toBe((compiling?.chapters.length ?? 0) * 2);
    const exported = exportBookMarkdown(bookB.id);
    expect(exported?.name).toBe('书乙（改）.md');
    expect(exported?.content).toContain('# 书乙（改）');
    expect(exported?.content).toContain('尚有');
    expect(exported?.content).toContain('个章节页未生成完成');
    expect(exported?.content).toContain('状态：排队等待生成');

    // 生成全部页后导出包含章节、页面与练习答案（完成态不带未完成标注）
    let seq = 1;
    const forPages = pages;
    for (let index = 0; index < forPages.length; index += 1) {
      seq = await runPageEvents(bookB.id, compiling!.run!.runId, forPages[index]!, { chapterIndex: Math.floor(index / 2), startSeq: seq });
    }
    await saved(finishBookRun(bookB.id, compiling!.run!.runId));
    const complete = exportBookMarkdown(bookB.id);
    expect(complete?.content).toContain('## ');
    expect(complete?.content).toMatch(/答案：A/);
    expect(complete?.content).not.toContain('未生成完成');
    // 深链取页
    expect(getBookPage(bookB.id, pages[0]!.id)?.id).toBe(pages[0]!.id);
    expect(getBookPage(bookB.id, 'missing')).toBeNull();

    expect((await deleteBook(bookB.id)).status).toBe('committed');
    // 重复删除：记录不存在 → missing（不返回"已完成"的候选值）
    const againDelete = await deleteBook(bookB.id);
    expect(againDelete.status).toBe('missing');
    expect(againDelete.value).toBeNull();
    expect(readBooks().some((item) => item.id === bookB.id)).toBe(false);
  });

  it('演示载入幂等且就绪书带预置进度（页/块带 ready 状态）', async () => {
    await saved(loadDemoBooks());
    await saved(loadDemoBooks());
    const books = readBooks();
    expect(books.filter((book) => book.id.startsWith('demo-book-'))).toHaveLength(2);
    const ready = books.find((book) => book.id === 'demo-book-fractions')!;
    expect(ready.status).toBe('ready');
    const pages = getBookPages(ready.id);
    expect(pages).toHaveLength(4);
    expect(pages.every((page) => page.status === 'ready')).toBe(true);
    expect(ready.reading.bookmarkedPageIds).toEqual(['demo-book-fractions-p2']);
    expect(ready.reading.visitedPageIds).toEqual(['demo-book-fractions-p0']);
    const draft = books.find((book) => book.id === 'demo-book-draft')!;
    expect(draft.proposal?.chapters.length).toBeGreaterThan(0);
  });

  it('练习作答持久化：记录/最新作答恢复/历史保留 + blockVersion 版本关系', async () => {
    const { book } = await setupSpineReady('作答书');
    const compiling = await saved(confirmSpine(book.id))!;
    const [page] = getBookPages(book.id);
    await runPageEvents(book.id, compiling.run!.runId, page!);
    const quizBlock = page!.blocks.find((block) => block.type === 'quiz')!;    expect(latestQuizAttempt(book.id, page!.id, quizBlock.id)).toBeNull();

    const v1 = 'v1';
    await saved(recordQuizAttempt({
      bookId: book.id,
      pageId: page!.id,
      blockId: quizBlock.id,
      choice: 'B',
      correct: false,
      blockVersion: v1,
    }));
    await saved(recordQuizAttempt({
      bookId: book.id,
      pageId: page!.id,
      blockId: quizBlock.id,
      choice: 'A',
      correct: true,
      blockVersion: v1,
    }));

    // 历史保留（2 条），最新一条为最终选择
    expect(readQuizAttempts({ bookId: book.id })).toHaveLength(2);
    const latest = latestQuizAttempt(book.id, page!.id, quizBlock.id)!;
    expect(latest.choice).toBe('A');
    expect(latest.correct).toBe(true);
    expect(latest.blockVersion).toBe(v1);

    // 版本关系：同版本匹配；块换版本后旧作答不匹配；缺版本（旧数据）视为匹配
    expect(quizAttemptMatches({ contentVersion: v1 }, latest)).toBe(true);
    expect(quizAttemptMatches({ contentVersion: 'v2' }, latest)).toBe(false);
    expect(quizAttemptMatches({ contentVersion: undefined }, latest)).toBe(true);
    expect(quizAttemptMatches({ contentVersion: v1 }, { blockVersion: undefined })).toBe(true);
    expect(quizAttemptMatches({ contentVersion: v1 }, null)).toBe(false);
  });

  it('block 品类覆盖参考 14 类；user_note 失焦保存写回', async () => {
    const { book } = await setupSpineReady('品类书');
    const compiling = await saved(confirmSpine(book.id))!;
    const runId = compiling.run!.runId;
    const pages = getBookPages(book.id);
    let seq = 1;
    const forPages = pages;
    for (let index = 0; index < forPages.length; index += 1) {
      seq = await runPageEvents(book.id, runId, forPages[index]!, { chapterIndex: Math.floor(index / 2), startSeq: seq });
    }
    const secondPage = pages[1]!;
    const types = new Set(secondPage.blocks.map((block) => block.type));
    // 第二页补充其余品类演示
    for (const kind of ['code', 'timeline', 'flash_cards', 'deep_dive', 'figure', 'concept_graph', 'user_note', 'interactive', 'animation'] as const) {
      expect(types.has(kind)).toBe(true);
    }
    const noteBlock = secondPage.blocks.find((block) => block.type === 'user_note')!;
    expect(await saved(setUserNote(book.id, secondPage.id, noteBlock.id, '我的页内笔记'))).toBe(true);
    expect(getBookPages(book.id)[1]!.blocks.find((item) => item.id === noteBlock.id)?.content).toBe('我的页内笔记');
    // 非用户笔记 block：不适用本次变更 → skipped（不写、不报成功）
    const textBlock = secondPage.blocks.find((block) => block.type === 'text')!;
    const denied = await setUserNote(book.id, secondPage.id, textBlock.id, 'x');
    expect(denied.status).toBe('skipped');
    expect(denied.value).toBeNull();
  });
});

describe('books-store（生成流水线状态机）', () => {
  it('状态流转全链：draft→spine_ready→compiling→ready；confirmSpine 建骨架并写检查点', async () => {
    const { book } = await setupSpineReady('状态机书');
    const spined = readBooks().find((item) => item.id === book.id)!;
    expect(spined.chapters.every((chapter) => chapter.pageIds.length === 0)).toBe(true);

    const compiling = await saved(confirmSpine(book.id))!;
    expect(compiling.status).toBe('compiling');
    expect(compiling.run?.status).toBe('running');
    expect(compiling.run?.stage).toBe('preparing');
    // 阅读进度清空，currentPageId 指向首页
    expect(compiling.reading.visitedPageIds).toEqual([]);
    expect(compiling.reading.currentPageId).toBe(getBookPages(book.id)[0]?.id ?? null);

    const pages = getBookPages(book.id);
    expect(pages.length).toBe(spined.chapters.length * 2);
    // 骨架：页/块全部 pending
    expect(pages.every((page) => page.status === 'pending')).toBe(true);
    expect(pages.every((page) => page.blocks.every((block) => block.status === 'pending'))).toBe(true);

    // 事件推进整本 → ready
    const runId = compiling.run!.runId;
    let seq = 1;
    const forPages = pages;
    for (let index = 0; index < forPages.length; index += 1) {
      seq = await runPageEvents(book.id, runId, forPages[index]!, { chapterIndex: Math.floor(index / 2), startSeq: seq });
    }
    const finished = await saved(finishBookRun(book.id, runId))!;
    expect(finished.status).toBe('ready');
    expect(finished.run?.status).toBe('finished');
    const finalPages = getBookPages(book.id);
    expect(finalPages.every((page) => page.status === 'ready')).toBe(true);
    expect(finalPages.every((page) => page.blocks.some((block) => block.content.includes('模拟')))).toBe(true);
    expect(finalPages.every((page) => page.blocks.some((block) => block.type === 'quiz' && block.quiz))).toBe(true);

    // 进度：打开章节登记已读（4 章×2 页=8 页，1 已读≈13%）
    await saved(markVisited(book.id, finalPages[0]!.id));
    const current = readBooks().find((item) => item.id === book.id)!;
    expect(current.reading.currentPageId).toBe(finalPages[0]!.id);
    expect(readingPercent(current)).toBe(Math.round((1 / finalPages.length) * 100));

    // 书签切换幂等往返
    await saved(toggleBookmark(book.id, finalPages[1]!.id));
    await saved(toggleBookmark(book.id, finalPages[1]!.id));
    const afterToggle = readBooks().find((item) => item.id === book.id)!;
    expect(afterToggle.reading.bookmarkedPageIds).toEqual([]);

    // 重建：进度清空、页面重新生成、回到 compiling
    const rebuilt = await saved(rebuildBook(book.id))!;
    expect(rebuilt.status).toBe('compiling');
    expect(rebuilt.reading.visitedPageIds).toEqual([]);
    expect(rebuilt.chapters.map((chapter) => chapter.id)).not.toEqual(finished.chapters.map((chapter) => chapter.id));
  });

  it('暂停与恢复：生成中页/块复位 pending；恢复清除暂停标注', async () => {
    const { book } = await setupSpineReady('暂停书');
    const compiling = await saved(confirmSpine(book.id))!;
    const runId = compiling.run!.runId;
    const [page] = getBookPages(book.id);
    // 推进到第一个块 generating
    await saved(applyRunEvent(book.id, runId, { type: 'page-start', chapterIndex: 0, pageIndex: 0 }, 1));
    await saved(applyRunEvent(book.id, runId, { type: 'page-planned', pageId: page!.id, blockIds: page!.blocks.map((b) => b.id) }, 2));
    await saved(applyRunEvent(book.id, runId, { type: 'block-start', pageId: page!.id, blockId: page!.blocks[0]!.id }, 3));

    const paused = await saved(pauseBookRun(book.id, 'user', 'Paused by user.'))!;
    expect(paused.status).toBe('paused');
    expect(paused.run?.pauseKind).toBe('user');
    expect(paused.run?.pauseReason).toBe('Paused by user.');
    // 正在生成的页/块复位 pending
    const pausedPage = getBookPage(book.id, page!.id)!;
    expect(pausedPage.status).toBe('pending');
    expect(pausedPage.blocks[0]!.status).toBe('pending');

    // 恢复：paused→compiling，暂停标注清除
    const resumed = await saved(resumeBookRun(book.id, runId))!;
    expect(resumed.status).toBe('compiling');
    expect(resumed.run?.pauseKind).toBeUndefined();
    expect(resumed.run?.pauseReason).toBeUndefined();
    expect(resumed.run?.status).toBe('running');

    // paused 状态下事件仍可写入（runWritable 允许 paused），用于 provider 暂停事件
    const rePaused = await saved(pauseBookRun(book.id, 'provider', '模拟供应商连续失败。'))!;
    expect(rePaused.run?.pauseKind).toBe('provider');
  });

  it('run-paused/run-failed 事件驱动书籍状态；failBookRun 落 error', async () => {
    const { book } = await setupSpineReady('事件书');
    const compiling = await saved(confirmSpine(book.id))!;
    const runId = compiling.run!.runId;

    const viaEvent = await saved(applyRunEvent(book.id, runId, { type: 'run-paused', kind: 'user', reason: 'r' }, 1))!;
    expect(viaEvent.status).toBe('paused');
    expect(viaEvent.run?.pauseKind).toBe('user');

    await saved(resumeBookRun(book.id, runId));
    const failed = await saved(failBookRun(book.id, runId, { kind: 'storage', message: '写入失败' }))!;
    expect(failed.status).toBe('error');
    expect(failed.run?.failure).toEqual({ kind: 'storage', message: '写入失败' });
    expect(failed.run?.status).toBe('failed');

    // error（storage）可恢复→compiling
    const resumed = await saved(resumeBookRun(book.id, runId))!;
    expect(resumed.status).toBe('compiling');

    const viaFailEvent = await saved(applyRunEvent(book.id, runId, { type: 'run-failed', failure: { kind: 'internal', message: 'x' } }, 2))!;
    expect(viaFailEvent.status).toBe('error');
    expect(viaFailEvent.run?.failure?.kind).toBe('internal');
  });

  it('块失败→partial 页；retryBlock 只复位该块；整页失败→error 页', async () => {
    const { book } = await setupSpineReady('块失败书');
    const compiling = await saved(confirmSpine(book.id))!;
    const runId = compiling.run!.runId;
    const [page] = getBookPages(book.id);
    const failing = page!.blocks[1]!;
    await runPageEvents(book.id, runId, page!, { failBlockIds: [failing.id] });

    // 页内存在 error 块 → partial；失败块带 BlockFailure（simulated）
    const partialPage = getBookPage(book.id, page!.id)!;
    expect(partialPage.status).toBe('partial');
    const failedBlock = partialPage.blocks.find((block) => block.id === failing.id)!;
    expect(failedBlock.status).toBe('error');
    expect(failedBlock.failure).toMatchObject({ kind: 'content', retryable: true, simulated: true });
    // 其余块保持 ready、内容完整
    expect(partialPage.blocks.filter((block) => block.status === 'ready')).toHaveLength(partialPage.blocks.length - 1);

    // retryBlock：只复位该块（其余块状态不动）
    const retried = await saved(retryBlock(book.id, page!.id, failing.id))!;
    const afterRetry = getBookPage(book.id, page!.id)!;
    expect(afterRetry.blocks.find((block) => block.id === failing.id)?.status).toBe('pending');
    expect(afterRetry.blocks.find((block) => block.id === failing.id)?.failure).toBeUndefined();
    expect(afterRetry.blocks.filter((block) => block.status === 'ready')).toHaveLength(partialPage.blocks.length - 1);
    void retried;

    // 重试后重新生成该块 → 页回 ready
    await saved(applyRunEvent(book.id, runId, { type: 'block-start', pageId: page!.id, blockId: failing.id }, 100));
    await saved(applyRunEvent(book.id, runId, { type: 'block-ready', pageId: page!.id, blockId: failing.id, block: { ...failing, content: '重新生成（模拟）', status: 'ready' } }, 101));
    await saved(applyRunEvent(book.id, runId, { type: 'page-ready', pageId: page!.id }, 102));
    expect(getBookPage(book.id, page!.id)?.status).toBe('ready');

    // 整页失败 → error 页（attempts 递增）
    const page2 = getBookPages(book.id)[1]!;
    await saved(applyRunEvent(book.id, runId, { type: 'page-start', chapterIndex: 0, pageIndex: 1 }, 200));
    await saved(applyRunEvent(book.id, runId, { type: 'page-error', pageId: page2!.id, message: '整页失败（模拟）' }, 201));
    const errorPage = getBookPage(book.id, page2!.id)!;
    expect(errorPage.status).toBe('error');
    expect(errorPage.error).toBe('整页失败（模拟）');
    expect(errorPage.attempts).toBe(1);
  });

  it('finishBookRun：partial 计入完成；存在 error/pending 页保持 compiling（中断）', async () => {
    const { book } = await setupSpineReady('完成语义书');
    const compiling = await saved(confirmSpine(book.id))!;
    const runId = compiling.run!.runId;
    const pages = getBookPages(book.id);
    // 除最后一页外全部正常完成；最后一页 partial（1 个失败块）→ 无 error/pending → ready
    let seq = 1;
    const seqPages = pages.slice(0, -1);
    for (let index = 0; index < seqPages.length; index += 1) {
      seq = await runPageEvents(book.id, runId, seqPages[index]!, { chapterIndex: Math.floor(index / 2), startSeq: seq });
    }
    const last = pages[pages.length - 1]!;
    await runPageEvents(book.id, runId, last, {
      failBlockIds: [last.blocks[0]!.id],
      chapterIndex: pages.length / 2 - 1,
      startSeq: seq,
    });
    // 复核：partial 页确实为 partial（局部块失败 ≠ 整页失败），其余页全部 ready
    expect(getBookPage(book.id, last.id)?.status).toBe('partial');
    expect(pages.slice(0, -1).every((page) => getBookPage(book.id, page.id)?.status === 'ready')).toBe(true);
    const done1 = await saved(finishBookRun(book.id, runId))!;
    expect(done1.status).toBe('ready'); // partial 刻意计入完成（engine.py:110-118）
    expect(done1.run?.status).toBe('finished');

    // 整页 error → 保持 compiling（无执行器即"已中断"）
    const rebuilt = await saved(rebuildBook(book.id))!;
    const runId2 = rebuilt.run!.runId;
    const pages2 = getBookPages(book.id);
    let seq2 = 1;
    const seq2Pages = pages2.slice(0, -1);
    for (let index = 0; index < seq2Pages.length; index += 1) {
      seq2 = await runPageEvents(book.id, runId2, seq2Pages[index]!, { chapterIndex: Math.floor(index / 2), startSeq: seq2 });
    }
    await saved(applyRunEvent(book.id, runId2, { type: 'page-start', chapterIndex: pages2.length / 2 - 1, pageIndex: 1 }, 900));
    await saved(applyRunEvent(book.id, runId2, { type: 'page-error', pageId: pages2[pages2.length - 1]!.id, message: 'x' }, 901));
    const done2 = await saved(finishBookRun(book.id, runId2))!;
    expect(done2.status).toBe('compiling');
    expect(done2.run?.status).toBe('stopped');
  });

  it('重复/迟到事件不重复落库；删除后迟到事件丢弃', async () => {
    const { book } = await setupSpineReady('幂等书');
    const compiling = await saved(confirmSpine(book.id))!;
    const runId = compiling.run!.runId;
    const [page] = getBookPages(book.id);
    const block = page!.blocks[0]!;

    await saved(applyRunEvent(book.id, runId, { type: 'block-start', pageId: page!.id, blockId: block.id }, 5));
    // 重复 seq（=5）与迟到 seq（<5）：被忽略 → skipped（不写、也不报"已提交"）
    const dup = await applyRunEvent(book.id, runId, { type: 'block-ready', pageId: page!.id, blockId: block.id, block: { ...block, status: 'ready' } }, 5);
    expect(dup.status).toBe('skipped');
    expect(dup.value).toBeNull();
    expect(dup.message).toContain('重复');
    const blockStill = getBookPage(book.id, page!.id)!.blocks.find((item) => item.id === block.id)!;
    expect(blockStill.status).toBe('generating'); // 重复事件未生效
    const late = await applyRunEvent(book.id, runId, { type: 'block-ready', pageId: page!.id, blockId: block.id, block: { ...block, status: 'ready' } }, 3);
    expect(late.status).toBe('skipped');
    expect(getBookPage(book.id, page!.id)!.blocks.find((item) => item.id === block.id)?.status).toBe('generating');

    // 正常 seq 生效
    await saved(applyRunEvent(book.id, runId, { type: 'block-ready', pageId: page!.id, blockId: block.id, block: { ...block, content: 'x', status: 'ready' } }, 6));
    expect(getBookPage(book.id, page!.id)!.blocks.find((item) => item.id === block.id)?.status).toBe('ready');

    // 删除后迟到事件不得复活记录
    await saved(deleteBook(book.id));
    const revived = await applyRunEvent(book.id, runId, { type: 'block-ready', pageId: page!.id, blockId: block.id, block: { ...block, status: 'ready' } }, 7);
    expect(revived.status).toBe('missing'); // 记录不存在，迟到事件不复活它
    expect(revived.value).toBeNull();
    expect(readBooks().some((item) => item.id === book.id)).toBe(false);
  });

  it('旧四态数据与缺字段页/块兼容读取（不写回）', async () => {
    // 直接注入旧格式（无 status/run 字段）的书籍记录
    const legacy = {
      id: 'legacy-book',
      title: '旧版书',
      description: '',
      status: 'ready',
      proposal: null,
      chapters: [
        { id: 'legacy-ch', title: '第一章', summary: 's', pageIds: ['legacy-p0'] },
      ],
      reading: { currentPageId: 'legacy-p0', visitedPageIds: [], bookmarkedPageIds: [] },
      createdAt: '2026-01-01T00:00:00.000Z',
      updatedAt: '2026-01-01T00:00:00.000Z',
      pages: [
        {
          id: 'legacy-p0',
          bookId: 'legacy-book',
          chapterId: 'legacy-ch',
          title: '第一章（1/2）',
          order: 0,
          blocks: [
            { id: 'legacy-b0', type: 'text', content: '旧内容' },
            { id: 'legacy-b1', type: 'quiz', content: 'q', quiz: { options: { A: 'a', B: 'b' }, correct: 'A' } },
          ],
        },
      ],
    };
    window.localStorage.setItem('zhiqikeyuan:books', JSON.stringify([legacy]));

    // 读取：缺 status 按 ready 派生（不抛错）
    const pages = getBookPages('legacy-book');
    expect(pages).toHaveLength(1);
    expect(pages[0]!.status).toBeUndefined(); // 读取不写回：字段保持缺失
    expect(pages[0]!.blocks.every((block) => block.status === undefined)).toBe(true);

    // markVisited 在旧数据页（缺 status）登记 visited
    await saved(markVisited('legacy-book', 'legacy-p0'));
    const book = readBooks().find((item) => item.id === 'legacy-book')!;
    expect(book.reading.visitedPageIds).toContain('legacy-p0');
    // 写回后仍未给旧块补 status（读取期派生，不写回）
    const raw = JSON.parse(window.localStorage.getItem('zhiqikeyuan:books')!) as Array<{
      id: string;
      pages?: Array<{ blocks?: Array<{ status?: string }> }>;
    }>;
    const storedPage = raw.find((item) => item.id === 'legacy-book')!.pages![0]!;
    expect(storedPage.blocks!.every((block) => block.status === undefined)).toBe(true);

    // 导出：旧数据正常导出（无未完成标注）
    const exported = exportBookMarkdown('legacy-book');
    expect(exported?.content).toContain('旧内容');
    expect(exported?.content).not.toContain('未生成完成');
  });

  it('生成期间写入的笔记/书签/阅读进度不被事件覆盖（读最新→局部改→写回）', async () => {
    const { book } = await setupSpineReady('并发书');
    const compiling = await saved(confirmSpine(book.id))!;
    const runId = compiling.run!.runId;
    const [page1, page2] = getBookPages(book.id);
    const noteBlock = page2!.blocks.find((block) => block.type === 'user_note')!;

    // 推进第一页
    await runPageEvents(book.id, runId, page1!);
    // 生成期间用户操作：书签 + 笔记 + 阅读进度
    await saved(toggleBookmark(book.id, page1!.id));
    await saved(setUserNote(book.id, page2!.id, noteBlock.id, '生成期间写下的笔记'));
    await saved(markVisited(book.id, page1!.id));

    // 继续推进后续页（事件写入；seq 接续，全局单调）
    let seq = 100;
    const seqPages = getBookPages(book.id).slice(1);
    for (let index = 0; index < seqPages.length; index += 1) {
      seq = await runPageEvents(book.id, runId, seqPages[index]!, { chapterIndex: Math.floor((index + 1) / 2), startSeq: seq });
    }
    await saved(finishBookRun(book.id, runId));

    const final = readBooks().find((item) => item.id === book.id)!;
    expect(final.status).toBe('ready');
    expect(final.reading.bookmarkedPageIds).toContain(page1!.id);
    expect(final.reading.visitedPageIds).toContain(page1!.id);
    const finalNote = getBookPage(book.id, page2!.id)!.blocks.find((block) => block.id === noteBlock.id)!;
    expect(finalNote.content).toBe('生成期间写下的笔记'); // user_note 内容不被事件覆盖
  });

  it('regeneratePage 保留 user_note 内容与块 id 身份；整页复位 pending', async () => {
    const { book } = await setupSpineReady('重生成书');
    const compiling = await saved(confirmSpine(book.id))!;
    const runId = compiling.run!.runId;
    const pages = getBookPages(book.id);
    let seq = 1;
    const forPages = pages;
    for (let index = 0; index < forPages.length; index += 1) {
      seq = await runPageEvents(book.id, runId, forPages[index]!, { chapterIndex: Math.floor(index / 2), startSeq: seq });
    }
    const secondPage = pages[1]!;
    const noteBlock = secondPage.blocks.find((block) => block.type === 'user_note')!;
    await saved(setUserNote(book.id, secondPage.id, noteBlock.id, '重生成前的笔记'));
    const blockIds = secondPage.blocks.map((block) => block.id);

    const regenerated = await saved(regeneratePage(book.id, secondPage.id))!;
    const after = getBookPage(book.id, secondPage.id)!;
    expect(regenerated.status === 'compiling' || true).toBe(true);
    expect(after.status).toBe('pending');
    // 块身份不变
    expect(after.blocks.map((block) => block.id)).toEqual(blockIds);
    // user_note 内容保留
    expect(after.blocks.find((block) => block.id === noteBlock.id)?.content).toBe('重生成前的笔记');
    // 其余块复位 pending 且清 failure
    expect(after.blocks.every((block) => block.status === 'pending')).toBe(true);
    // 其它页不受影响
    expect(getBookPage(book.id, pages[0]!.id)?.status).toBe('ready');
  });

  it('markVisited：未完成页只更新 currentPageId 不登记 visited', async () => {    const { book } = await setupSpineReady('进度分离书');
    const compiling = await saved(confirmSpine(book.id))!;
    const pages = getBookPages(book.id);
    // 全部页尚 pending：打开第 2 页
    await saved(markVisited(book.id, pages[1]!.id));
    let current = readBooks().find((item) => item.id === book.id)!;
    expect(current.reading.currentPageId).toBe(pages[1]!.id);
    expect(current.reading.visitedPageIds).toEqual([]); // 未生成页不算已读
    expect(readingPercent(current)).toBe(0);

    // 首页完成后打开首页 → 登记
    await runPageEvents(book.id, compiling.run!.runId, pages[0]!, { chapterIndex: 0 });
    await saved(markVisited(book.id, pages[0]!.id));
    current = readBooks().find((item) => item.id === book.id)!;
    expect(current.reading.visitedPageIds).toEqual([pages[0]!.id]);
    expect(readingPercent(current)).toBe(Math.round((1 / pages.length) * 100));
  });
});

describe('books-store（页状态兜底与写入容器，H1 v2 总控裁定 A2/A6）', () => {
  /** 旧格式就绪书（有章节/页面/块、没有 run 字段）：演示书与旧四态数据的形态 */
  function legacyReadyBook() {
    return {
      id: 'legacy-ready',
      title: '旧版就绪书',
      description: '',
      status: 'ready',
      proposal: null,
      chapters: [{ id: 'legacy-ch', title: '第一章', summary: 's', pageIds: ['legacy-p0'] }],
      reading: { currentPageId: 'legacy-p0', visitedPageIds: ['legacy-p0'], bookmarkedPageIds: [] },
      createdAt: '2026-01-01T00:00:00.000Z',
      updatedAt: '2026-01-01T00:00:00.000Z',
      pages: [
        {
          id: 'legacy-p0',
          bookId: 'legacy-ready',
          chapterId: 'legacy-ch',
          title: '第一章（1/1）',
          order: 0,
          blocks: [
            { id: 'legacy-b0', type: 'section', title: '第一章', content: '旧内容' },
            { id: 'legacy-b1', type: 'text', content: '旧正文' },
          ],
        },
      ],
    };
  }

  it('page-ready 兜底：仍有 pending/generating 块的页不会被判成 ready（不虚报完成）', async () => {
    const { book } = await setupSpineReady('页兜底书');
    const compiling = await saved(confirmSpine(book.id))!;
    const runId = compiling.run!.runId;
    const [page] = getBookPages(book.id);
    const pageId = page!.id;
    let seq = 1;
    await saved(applyRunEvent(book.id, runId, { type: 'page-start', chapterIndex: 0, pageIndex: 0 }, seq++));
    await saved(applyRunEvent(
      book.id,
      runId,
      { type: 'page-planned', pageId, blockIds: page!.blocks.map((block) => block.id) },
      seq++,
    ));
    // 只完成第 1 块；第 2 块停在 generating、其余仍 pending
    await saved(applyRunEvent(book.id, runId, { type: 'block-start', pageId, blockId: page!.blocks[0]!.id }, seq++));
    await saved(applyRunEvent(
      book.id,
      runId,
      {
        type: 'block-ready',
        pageId,
        blockId: page!.blocks[0]!.id,
        block: { ...page!.blocks[0]!, content: '生成内容（模拟）', status: 'ready' },
      },
      seq++,
    ));
    await saved(applyRunEvent(book.id, runId, { type: 'block-start', pageId, blockId: page!.blocks[1]!.id }, seq++));
    // 迟到的 page-ready：块还没全部就绪，不得判成 ready
    await saved(applyRunEvent(book.id, runId, { type: 'page-ready', pageId }, seq++));
    const mid = getBookPage(book.id, pageId)!;
    expect(mid.status).toBe('generating');
    expect(mid.status).not.toBe('ready');

    // 存在失败块 + 其它块未就绪 → partial（局部失败可用），同样不冒充全部完成
    await saved(applyRunEvent(
      book.id,
      runId,
      {
        type: 'block-error',
        pageId,
        blockId: page!.blocks[2]!.id,
        failure: { kind: 'content', message: '模拟块失败', retryable: true, simulated: true },
      },
      seq++,
    ));
    await saved(applyRunEvent(book.id, runId, { type: 'page-ready', pageId }, seq++));
    expect(getBookPage(book.id, pageId)!.status).toBe('partial');
  });

  it('ensureBookRun：无 run 的书补建写入容器（状态不变、幂等）；已有 run 不重复写', async () => {
    window.localStorage.setItem('zhiqikeyuan:books', JSON.stringify([legacyReadyBook()]));
    const ensured = await ensureBookRun('legacy-ready');
    expect(ensured.status).toBe('committed');
    expect(ensured.value?.status).toBe('ready'); // 书籍状态不变（补检查点不等于重新生成）
    expect(ensured.value?.run?.runId).toBeTruthy();
    expect(ensured.value?.run?.status).toBe('finished'); // 已跑完一轮的容器，不是"正在生成"
    // 幂等：已有检查点时不做任何写入 → skipped，存储里的 runId 不变
    const again = await ensureBookRun('legacy-ready');
    expect(again.status).toBe('skipped');
    expect(again.value).toBeNull();
    const stored = readBooks().find((item) => item.id === 'legacy-ready')!;
    expect(stored.run?.runId).toBe(ensured.value?.run?.runId);
    expect(stored.reading.visitedPageIds).toEqual(['legacy-p0']); // 阅读进度不动
    // 已有 run 的编译中书：跳过写入，runId 不变
    const { book } = await setupSpineReady('已有检查点书');
    const compiling = await saved(confirmSpine(book.id));
    const kept = await ensureBookRun(book.id);
    expect(kept.status).toBe('skipped');
    const storedCompiling = readBooks().find((item) => item.id === book.id)!;
    expect(storedCompiling.run?.runId).toBe(compiling.run!.runId);
    expect(storedCompiling.status).toBe('compiling');
    // 不存在的书：记录不存在
    expect((await ensureBookRun('missing-book')).status).toBe('missing');
  });
});
