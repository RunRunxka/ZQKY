import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  archiveBook,
  confirmProposal,
  confirmSpine,
  createBook,
  deleteBook,
  getBookPage,
  getBookPages,
  readBooks,
  type ReplicaBook,
} from './books-store';import {
  CONSECUTIVE_PAGE_FAILURE_LIMIT,
  DEFAULT_RUN_SCENARIO,
  RUN_LEASE_STALE_MS,
  cancelRepairs,
  expandRunScenario,
  getLease,
  getRepair,
  getRun,
  getRunExit,
  regeneratePage as regeneratePageExec,
  resumeRun,
  retryBlock as retryBlockExec,
  startRun,
  stopRun,
} from './book-generation';
import { quizAttemptMatches } from './books-store';

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
});

afterEach(() => {
  // 清理执行器与定时器，避免用例间串扰
  for (const book of readBooks()) {
    stopRun(book.id, 'test-cleanup');
  }
  vi.restoreAllMocks();
  vi.useRealTimers();
});

/** 建立一本 compiling 书并返回其记录 */
function setupCompiling(title: string): ReplicaBook {
  const book = createBook(title, '');
  confirmProposal(book.id);
  const compiling = confirmSpine(book.id);
  if (!compiling) throw new Error('confirmSpine failed');
  return compiling;
}

/** 等待条件满足（轮询真实定时器推进；上限保护） */
async function waitFor(condition: () => boolean, timeoutMs = 8000): Promise<void> {
  const start = Date.now();
  while (!condition()) {
    if (Date.now() - start > timeoutMs) {
      throw new Error(`waitFor timeout after ${timeoutMs}ms`);
    }
    await new Promise((resolve) => setTimeout(resolve, 25));
  }
}

/** 快速场景：缩短延时加速用例 */
const FAST = { stageDelayMs: 5, blockDelayMs: 5 };

describe('book-generation 执行器', () => {
  it('正常路径：逐页逐块事件推进到 ready；进度非同步一次性完成', async () => {
    const compiling = setupCompiling('执行器正常书');
    expect(readBooks().find((item) => item.id === compiling.id)!.status).toBe('compiling');

    const handle = startRun(compiling.id, { scenario: FAST });
    expect(handle).not.toBeNull();
    expect(handle!.status).toBe('running');
    expect(handle!.runId).toBe(compiling.run!.runId); // 沿用检查点 runId

    // 期间观察到"部分完成"中间态（事件增量可见，非同步整本）
    let sawIntermediate = false;
    await waitFor(() => {
      const book = readBooks().find((item) => item.id === compiling.id)!;
      const statuses = getBookPages(compiling.id).map((page) => page.status ?? 'ready');
      const done = statuses.filter((status) => status === 'ready' || status === 'partial').length;
      if (done > 0 && done < statuses.length) sawIntermediate = true;
      return book.status === 'ready';
    });
    expect(sawIntermediate).toBe(true);

    const final = readBooks().find((item) => item.id === compiling.id)!;
    expect(final.status).toBe('ready');
    expect(final.run?.status).toBe('finished');
    for (const page of getBookPages(compiling.id)) {
      expect(page.status).toBe('ready');
      expect(page.blocks.every((block) => block.status === 'ready')).toBe(true);
      expect(page.blocks.some((block) => block.content.includes('模拟生成'))).toBe(true);
      expect(page.generatedAt).toBeDefined();
    }
    // 结束后执行器清出注册表、租约释放
    expect(getRun(compiling.id)).toBeNull();
    expect(getLease(compiling.id)).toBeNull();
  }, 15000);

  it('常量与默认场景对照参考（阈值 2、租约 3s、默认 300/220ms）', () => {
    expect(CONSECUTIVE_PAGE_FAILURE_LIMIT).toBe(2);
    expect(RUN_LEASE_STALE_MS).toBe(3000);
    expect(DEFAULT_RUN_SCENARIO).toEqual({ stageDelayMs: 300, blockDelayMs: 220 });
  });

  it('getRun 同书返回同一执行器（不重复启动）；非 compiling 返回 null', async () => {
    const compiling = setupCompiling('单执行器书');
    const h1 = startRun(compiling.id, { scenario: FAST });
    const h2 = startRun(compiling.id, { scenario: FAST });
    expect(h2).not.toBeNull();
    expect(h2!.runId).toBe(h1!.runId);
    await waitFor(() => readBooks().find((item) => item.id === compiling.id)!.status === 'ready');

    // 已完成书再启动 → null
    expect(startRun(compiling.id)).toBeNull();
    // draft 书 → null
    const draft = createBook('草稿不启动', '');
    expect(startRun(draft.id)).toBeNull();
  }, 15000);

  it('用户暂停：页/块复位 pending，执行器停止；恢复后从断点续跑', async () => {
    const compiling = setupCompiling('暂停书');
    const runId = compiling.run!.runId;
    const handle = startRun(compiling.id, { scenario: { ...FAST, blockDelayMs: 30 } })!;

    // 等第一页完成
    await waitFor(() => (getBookPages(compiling.id)[0]?.status ?? 'pending') === 'ready');
    handle.pause();
    const paused = readBooks().find((item) => item.id === compiling.id)!;
    expect(paused.status).toBe('paused');
    expect(paused.run?.pauseKind).toBe('user');
    expect(paused.run?.runId).toBe(runId);
    // 执行器已停止（getRun null），租约释放
    expect(getRun(compiling.id)).toBeNull();

    // paused 不自动续跑：startRun(paused 书) 不接管（仅 resumeRun 显式恢复）
    expect(startRun(compiling.id)).toBeNull();

    const resumedHandle = resumeRun(compiling.id);
    expect(resumedHandle).not.toBeNull();
    await waitFor(() => readBooks().find((item) => item.id === compiling.id)!.status === 'ready');
    // 断点续跑：第一页内容保留（不重新生成、块 id 不变）
    const pages = getBookPages(compiling.id);
    expect(pages[0]!.blocks.every((block) => block.status === 'ready')).toBe(true);
    expect(pages.every((page) => page.status === 'ready')).toBe(true);
  }, 15000);

  it('刷新中断续跑：stopRun 保留断点；模块重建后从检查点续跑（已完成页不重复生成）', async () => {
    const compiling = setupCompiling('刷新书');
    const firstPageId = getBookPages(compiling.id)[0]!.id;
    startRun(compiling.id, { scenario: FAST });
    // 第一页完成后模拟刷新：模块状态丢失（stopRun 保留断点）
    await waitFor(() => getBookPage(compiling.id, firstPageId)?.status === 'ready');
    const firstPageBefore = getBookPage(compiling.id, firstPageId)!;
    stopRun(compiling.id, 'reload');
    expect(getRun(compiling.id)).toBeNull();

    // 书籍仍 compiling（无执行器 = "已中断"）
    const interrupted = readBooks().find((item) => item.id === compiling.id)!;
    expect(interrupted.status).toBe('compiling');

    // "重载后"：新执行器从检查点续跑（auto-open 语义）
    const resumed = resumeRun(compiling.id);
    expect(resumed).not.toBeNull();
    await waitFor(() => readBooks().find((item) => item.id === compiling.id)!.status === 'ready');

    // 已完成页块 id 与内容保持（未重复生成：块 id 不变）
    const firstPageAfter = getBookPage(compiling.id, firstPageId)!;
    expect(firstPageAfter.blocks.map((block) => block.id)).toEqual(
      firstPageBefore.blocks.map((block) => block.id),
    );
    expect(firstPageAfter.status).toBe('ready');
  }, 15000);

  it('块失败一次后重试即成功（failBlockIds）', async () => {
    const compiling = setupCompiling('块失败书');
    // 预先指定第一页第一个块为注入失败块
    const firstPage = getBookPages(compiling.id)[0]!;
    const target = firstPage.blocks[0]!;
    const scenario = { ...FAST, failBlockIds: [target.id] };
    startRun(compiling.id, { scenario });

    await waitFor(() => {
      const page = getBookPage(compiling.id, firstPage.id);
      return page?.status === 'partial';
    });
    const partialPage = getBookPage(compiling.id, firstPage.id)!;
    const failed = partialPage.blocks.find((block) => block.id === target.id)!;
    expect(failed.status).toBe('error');
    expect(failed.failure).toMatchObject({ kind: 'content', retryable: true, simulated: true });
    // 其余块可用
    expect(partialPage.blocks.filter((block) => block.status === 'ready').length).toBe(
      partialPage.blocks.length - 1,
    );

    // 整书完成（partial 计入完成）
    await waitFor(() => readBooks().find((item) => item.id === compiling.id)!.status === 'ready');

    // 重试该块：重试即成功（不再注入失败）
    retryBlockExec(compiling.id, firstPage.id, target.id);
    await waitFor(() => {
      const page = getBookPage(compiling.id, firstPage.id);
      return page?.blocks.find((block) => block.id === target.id)?.status === 'ready';
    });
    const recovered = getBookPage(compiling.id, firstPage.id)!;
    expect(recovered.status).toBe('ready');
    expect(recovered.blocks.every((block) => block.status === 'ready')).toBe(true);
  }, 20000);

  it('连续 2 页失败触发 provider 暂停（显式模拟标注，不宣称真实上游）', async () => {
    const compiling = setupCompiling('供应商暂停书');
    startRun(compiling.id, { scenario: { ...FAST, failPages: 2, providerPauseAfterPages: 2 } });

    await waitFor(() => {
      const book = readBooks().find((item) => item.id === compiling.id)!;
      return book.status === 'paused';
    });
    const paused = readBooks().find((item) => item.id === compiling.id)!;
    expect(paused.run?.pauseKind).toBe('provider');
    expect(paused.run?.pauseReason).toContain('模拟供应商连续失败');
    expect(paused.run?.pauseReason).toContain('本地注入');
    // 两页 error
    const statuses = getBookPages(compiling.id).map((page) => page.status);
    expect(statuses.filter((status) => status === 'error').length).toBe(2);
    // 执行器停止
    expect(getRun(compiling.id)).toBeNull();
    // paused 不自动续跑
    expect(startRun(compiling.id)).toBeNull();
  }, 15000);

  it('storageFailureAt：写入失败走真实抛错路径并落 error（kind storage），不谎报已保存', async () => {
    const compiling = setupCompiling('存储失败书');
    // 第 1 页完成后（done=1）触发写失败
    startRun(compiling.id, { scenario: { ...FAST, storageFailureAt: { pageIndex: 1 } } });

    await waitFor(() => {
      const book = readBooks().find((item) => item.id === compiling.id)!;
      return book.status === 'error';
    });
    const failed = readBooks().find((item) => item.id === compiling.id)!;
    expect(failed.run?.failure?.kind).toBe('storage');
    expect(failed.run?.failure?.message).toContain('本地保存失败');
    expect(failed.run?.status).toBe('failed');
    // 执行器清理
    expect(getRun(compiling.id)).toBeNull();

    // storage error 可恢复 → 续跑
    const resumed = resumeRun(compiling.id);
    expect(resumed).not.toBeNull();
    await waitFor(() => readBooks().find((item) => item.id === compiling.id)!.status === 'ready');
    // localStorage.setItem 已复原（未残留 mock）
    window.localStorage.setItem('zhiqikeyuan:probe', 'ok');
    expect(window.localStorage.getItem('zhiqikeyuan:probe')).toBe('ok');
  }, 20000);

  it('stop 后迟到回调被丢弃（删除书籍后不复活记录）', async () => {
    const compiling = setupCompiling('删除书');
    startRun(compiling.id, { scenario: { ...FAST, blockDelayMs: 60 } });
    const firstPageId = getBookPages(compiling.id)[0]!.id;
    await waitFor(() => (getBookPage(compiling.id, firstPageId)?.blocks[0]?.status ?? 'pending') === 'ready');

    stopRun(compiling.id, 'delete');
    deleteBook(compiling.id);
    // 等待潜在迟到回调窗口过去
    await new Promise((resolve) => setTimeout(resolve, 150));

    expect(readBooks().some((item) => item.id === compiling.id)).toBe(false);
    // 再等一个周期，确认无复活
    await new Promise((resolve) => setTimeout(resolve, 150));
    expect(readBooks().some((item) => item.id === compiling.id)).toBe(false);
  }, 15000);

  it('租约：运行中 live 且 mine；心跳推进；结束后释放；不同书可并行各自执行', async () => {
    const compiling = setupCompiling('租约书');
    startRun(compiling.id, { scenario: { ...FAST, blockDelayMs: 40 } });

    const lease = getLease(compiling.id);
    expect(lease).not.toBeNull();
    expect(lease!.mine).toBe(true);
    expect(lease!.runId).toBe(compiling.run!.runId);

    // 心跳推进（两次观测间隔内 updatedAt 不老化到失效）
    await new Promise((resolve) => setTimeout(resolve, 120));
    const lease2 = getLease(compiling.id);
    expect(lease2!.live).toBe(true);

    const book2 = setupCompiling('第二本书'); // 不同书不受影响
    expect(startRun(book2.id, { scenario: FAST })).not.toBeNull();
    // 同书：已运行中不重复启动（返回现有句柄，不产生第二个执行器）
    const again = startRun(compiling.id, { scenario: FAST });
    expect(again!.runId).toBe(compiling.run!.runId);

    await waitFor(() => readBooks().find((item) => item.id === compiling.id)!.status === 'ready');
    await waitFor(() => readBooks().find((item) => item.id === book2.id)!.status === 'ready');
    expect(getLease(compiling.id)).toBeNull(); // 结束释放
    expect(getLease(book2.id)).toBeNull();
  }, 15000);

  it('他标签页持活租约：本标签不启动第二个执行器（真实租约记录，不改本标签身份）', () => {
    const compiling = setupCompiling('占用租约书');
    // 直接写入"另一个标签页"的活租约（owner 不同、心跳新鲜）
    window.localStorage.setItem(
      `zhiqikeyuan:book-lease:${compiling.id}`,
      JSON.stringify({
        owner: 'other-tab-owner',
        runId: compiling.run!.runId,
        heartbeatAt: Date.now(),
        nonce: 'other-tab-lease',
      }),
    );
    expect(getLease(compiling.id)!.mine).toBe(false);
    expect(startRun(compiling.id, { scenario: FAST })).toBeNull();
    expect(getRun(compiling.id)).toBeNull();
    // 别人的租约不被本标签页清掉
    expect(getLease(compiling.id)!.owner).toBe('other-tab-owner');
  });

  it('失去所有权：执行器立即收尾、停止续租，且不动别人的租约记录，之后可恢复', async () => {
    const compiling = setupCompiling('失权书');
    startRun(compiling.id, { scenario: { stageDelayMs: 10, blockDelayMs: 120 } });
    expect(getRun(compiling.id)).not.toBeNull();

    // 另一个标签页接管租约（写入自己的 owner+nonce，心跳新鲜）
    const foreign = {
      owner: 'other-tab-owner',
      runId: compiling.run!.runId,
      heartbeatAt: Date.now(),
      nonce: 'other-tab-lease',
    };
    window.localStorage.setItem(`zhiqikeyuan:book-lease:${compiling.id}`, JSON.stringify(foreign));

    // 下一次驱动步/心跳的归属校验发现失权 → 立即收尾
    await waitFor(() => getRun(compiling.id) === null);
    expect(getRunExit(compiling.id)?.reason).toBe('lease-lost');
    // 不再续租：跨过一个心跳周期后租约仍是接管方的记录
    await new Promise((resolve) => setTimeout(resolve, 1200));
    const lease = getLease(compiling.id);
    expect(lease?.owner).toBe('other-tab-owner');
    // 书籍保持可恢复的 compiling（失权不是"已完成"，也不是"已失败"）
    const interrupted = readBooks().find((item) => item.id === compiling.id)!;
    expect(interrupted.status).toBe('compiling');
    expect(interrupted.run?.status).not.toBe('finished');

    // 接管方释放后，本标签页可显式恢复并完成
    window.localStorage.removeItem(`zhiqikeyuan:book-lease:${compiling.id}`);
    expect(resumeRun(compiling.id)).not.toBeNull();
    await waitFor(() => readBooks().find((item) => item.id === compiling.id)!.status === 'ready', 12000);
    expect(getBookPages(compiling.id).every((page) => page.status === 'ready')).toBe(true);
  }, 20000);

  it('regeneratePage 执行器路径：重建整页并保留 user_note 内容与块身份', async () => {
    const compiling = setupCompiling('整页重生成书');
    startRun(compiling.id, { scenario: FAST });
    await waitFor(() => readBooks().find((item) => item.id === compiling.id)!.status === 'ready');

    const pages = getBookPages(compiling.id);
    const secondPage = pages[1]!;
    const noteBlock = secondPage.blocks.find((block) => block.type === 'user_note')!;
    // 写入用户笔记
    const raw = JSON.parse(window.localStorage.getItem('zhiqikeyuan:books')!) as Array<{
      id: string;
      pages?: Array<{ id: string; blocks: Array<{ id: string; content: string }> }>;
    }>;
    const stored = raw.find((item) => item.id === compiling.id)!;
    const storedNote = stored.pages!.find((page) => page.id === secondPage.id)!.blocks.find((b) => b.id === noteBlock.id)!;
    storedNote.content = '重生成前用户笔记';
    window.localStorage.setItem('zhiqikeyuan:books', JSON.stringify(raw));

    const idsBefore = secondPage.blocks.map((block) => block.id);
    regeneratePageExec(compiling.id, secondPage.id);
    await waitFor(() => {
      const page = getBookPage(compiling.id, secondPage.id);
      return page?.status === 'ready' && page.blocks.every((block) => block.status === 'ready');
    });
    const after = getBookPage(compiling.id, secondPage.id)!;
    expect(after.blocks.map((block) => block.id)).toEqual(idsBefore);
    expect(after.blocks.find((block) => block.id === noteBlock.id)?.content).toBe('重生成前用户笔记');
  }, 15000);

  it('演示数据与执行器互不干扰：demo ready 书不经执行器', async () => {
    window.localStorage.setItem(
      'zhiqikeyuan:books',
      JSON.stringify([
        {
          id: 'demo-book-fractions',
          title: '分数入门（演示书籍）',
          description: '',
          status: 'ready',
          proposal: null,
          chapters: [],
          reading: { currentPageId: null, visitedPageIds: [], bookmarkedPageIds: [] },
          createdAt: '2026-09-08T01:00:00.000Z',
          updatedAt: '2026-09-08T01:00:00.000Z',
          pages: [],
        },
      ]),
    );
    // ready 书不启动执行器
    expect(startRun('demo-book-fractions')).toBeNull();
    expect(getRun('demo-book-fractions')).toBeNull();
  });
});

describe('book-generation 注入语义修复（H1 v2 总控裁定 A1/A2/A4）', () => {
  it("通配注入展开：'*first' 真的命中全书第一个块（UI 开关不是静默无操作）", async () => {
    const compiling = setupCompiling('通配注入书');
    const firstPage = getBookPages(compiling.id)[0]!;
    const firstBlockId = firstPage.blocks[0]!.id;

    // 解析期展开：通配 → 实际块 id
    const expanded = expandRunScenario(
      readBooks().find((item) => item.id === compiling.id)!,
      { failBlockIds: ['*first'] },
    );
    expect(expanded.failBlockIds).toEqual([firstBlockId]);

    startRun(compiling.id, { scenario: { ...FAST, failBlockIds: ['*first'] } });
    await waitFor(() => getBookPage(compiling.id, firstPage.id)?.status === 'partial');
    const page = getBookPage(compiling.id, firstPage.id)!;
    const failed = page.blocks.filter((block) => block.status === 'error');
    expect(failed).toHaveLength(1);
    expect(failed[0]!.id).toBe(firstBlockId); // 命中的是"全书第一个块"
    expect(failed[0]!.failure?.simulated).toBe(true);

    // 持久化的是展开后的真实块 id：续跑/重试沿用同一目标，不再依赖通配
    const stored = readBooks().find((item) => item.id === compiling.id)!;
    expect(stored.runScenario?.failBlockIds).toEqual([firstBlockId]);
    expect(stored.runScenario?.failBlockIds).not.toContain('*first');
  }, 15000);

  it('只开启"模拟供应商连续失败暂停"（未开整页失败）也会真的暂停（开关不是静默无操作）', async () => {
    const compiling = setupCompiling('供应商开关书');
    startRun(compiling.id, { scenario: { ...FAST, providerPauseAfterPages: 2 } });

    await waitFor(() => readBooks().find((item) => item.id === compiling.id)!.status === 'paused');
    const paused = readBooks().find((item) => item.id === compiling.id)!;
    expect(paused.run?.pauseKind).toBe('provider');
    expect(paused.run?.pauseReason).toContain('模拟供应商连续失败');
    // 供应商场景自身产生连续页失败（阈值 2）
    expect(getBookPages(compiling.id).filter((page) => page.status === 'error')).toHaveLength(2);

    // 恢复后同一批页不再注入失败（一次性），续跑到 ready
    expect(resumeRun(compiling.id)).not.toBeNull();
    await waitFor(() => readBooks().find((item) => item.id === compiling.id)!.status === 'ready', 12000);
    expect(getBookPages(compiling.id).every((page) => page.status === 'ready')).toBe(true);
  }, 25000);

  it('整页失败注入是一次性：首轮失败后保持中断（compiling），恢复即成功且不重复注入', async () => {
    const compiling = setupCompiling('页失败一次性书');
    const pages = getBookPages(compiling.id);
    startRun(compiling.id, { scenario: { ...FAST, failPages: 1 } });

    // 首轮：第 1 页失败，其余页完成；无执行器后保持 compiling（已中断），不谎报 ready
    await waitFor(
      () =>
        getRun(compiling.id) === null &&
        getBookPages(compiling.id).slice(1).every((page) => page.status === 'ready'),
    );
    const interrupted = readBooks().find((item) => item.id === compiling.id)!;
    expect(interrupted.status).toBe('compiling');
    expect(interrupted.run?.status).toBe('stopped');
    const failedPage = getBookPage(compiling.id, pages[0]!.id)!;
    expect(failedPage.status).toBe('error');
    expect(failedPage.attempts).toBe(1);
    expect(failedPage.error).toContain('模拟页面失败');

    // 恢复：不再注入（attempts>0），续跑到 ready
    expect(resumeRun(compiling.id)).not.toBeNull();
    await waitFor(() => readBooks().find((item) => item.id === compiling.id)!.status === 'ready', 12000);
    const recovered = getBookPage(compiling.id, pages[0]!.id)!;
    expect(recovered.status).toBe('ready');
    expect(recovered.attempts).toBe(1); // 未再次失败
    expect(recovered.error).toBeUndefined();
  }, 25000);

  it('无 run 记录的已就绪书（演示书/旧四态数据）可重试与整页重生成：补检查点且不改书籍状态', async () => {    // 旧格式就绪书：有章节/页面/块，没有 run 字段（与演示书同形态）
    window.localStorage.setItem(
      'zhiqikeyuan:books',
      JSON.stringify([
        {
          id: 'legacy-ready',
          title: '旧版就绪书',
          description: '',
          status: 'ready',
          proposal: null,
          chapters: [{ id: 'legacy-ch', title: '第一章', summary: 's', pageIds: ['legacy-p0'] }],
          reading: { currentPageId: 'legacy-p0', visitedPageIds: [], bookmarkedPageIds: [] },
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
                { id: 'legacy-b0', type: 'section', title: '第一章', content: '旧内容', status: 'error' },
                { id: 'legacy-b1', type: 'text', content: '旧正文' },
                { id: 'legacy-b2', type: 'callout', content: '旧提示' },
                { id: 'legacy-b3', type: 'quiz', content: '旧练习', quiz: { options: { A: 'a', B: 'b' }, correct: 'A' } },
              ],
            },
          ],
        },
      ]),
    );
    expect(readBooks().find((item) => item.id === 'legacy-ready')!.run).toBeUndefined();

    // 单块重试：不再静默无操作（此前因缺 runId 直接 return）
    retryBlockExec('legacy-ready', 'legacy-p0', 'legacy-b0');
    await waitFor(
      () => getBookPage('legacy-ready', 'legacy-p0')?.blocks.find((b) => b.id === 'legacy-b0')?.status === 'ready',
    );
    const afterRetry = readBooks().find((item) => item.id === 'legacy-ready')!;
    expect(afterRetry.run?.runId).toBeTruthy(); // 补建了写入容器
    expect(afterRetry.status).toBe('ready'); // 书籍状态不变（页级修复不把整本变回生成中）
    expect(afterRetry.reading.visitedPageIds).toEqual([]);

    // 整页重生成：同样可用，结束时页回到 ready
    regeneratePageExec('legacy-ready', 'legacy-p0');
    await waitFor(() => {
      const page = getBookPage('legacy-ready', 'legacy-p0');
      return page?.status === 'ready' && page.blocks.every((block) => block.status === 'ready');
    });
    const finalBook = readBooks().find((item) => item.id === 'legacy-ready')!;
    expect(finalBook.status).toBe('ready');
    expect(getBookPage('legacy-ready', 'legacy-p0')!.blocks.map((block) => block.id)).toEqual([
      'legacy-b0',
      'legacy-b1',
      'legacy-b2',
      'legacy-b3',
    ]);
  }, 20000);

  it('块内容版本真实写入：作答版本关系不是死代码（同内容同版本，异版本不匹配）', async () => {
    const compiling = setupCompiling('内容版本书');
    startRun(compiling.id, { scenario: FAST });
    await waitFor(() => readBooks().find((item) => item.id === compiling.id)!.status === 'ready');

    const [page] = getBookPages(compiling.id);
    const quiz = page!.blocks.find((block) => block.type === 'quiz')!;
    // 生产路径（执行器 block-ready 载荷）必须产出真实版本号，而不是只在类型里存在
    expect(typeof quiz.contentVersion).toBe('string');
    expect(quiz.contentVersion).toMatch(/^v1-[0-9a-f]{8}$/);

    // 同一页里不同内容的块版本不同（版本来自内容，不是常量）
    const text = page!.blocks.find((block) => block.type === 'text')!;
    expect(text.contentVersion).not.toBe(quiz.contentVersion);

    // 作答版本关系：与当前块版本一致 → 匹配；其他版本 → 不匹配
    expect(quizAttemptMatches(quiz, { blockVersion: quiz.contentVersion })).toBe(true);
    expect(quizAttemptMatches(quiz, { blockVersion: 'v1-deadbeef' })).toBe(false);
    // 旧数据（任一侧缺版本）仍视为匹配，保留历史可用性
    expect(quizAttemptMatches(quiz, { blockVersion: undefined })).toBe(true);

    // 重生成同样内容 → 版本不变（同一道题，旧作答仍然有效，不误判成过期）
    regeneratePageExec(compiling.id, page!.id);
    await waitFor(() => {
      const current = getBookPage(compiling.id, page!.id);
      return current?.status === 'ready' && current.blocks.every((block) => block.status === 'ready');
    });
    const afterRegenerate = getBookPage(compiling.id, page!.id)!.blocks.find((block) => block.id === quiz.id)!;
    expect(afterRegenerate.contentVersion).toBe(quiz.contentVersion);
    expect(quizAttemptMatches(afterRegenerate, { blockVersion: quiz.contentVersion })).toBe(true);
  }, 20000);
});

/**
 * H1-BOOKS-HARDEN v1（M22-01～03/05）回归。
 * 前三条由 main 审查的隔离探针改造而来：**原探针断言缺陷存在，这里断言修复后的正确行为**。
 * 原探针保留在 docs/qa/main-review-20260922/book-probe.test.ts，修复后已不再复现缺陷。
 */
describe('H1-BOOKS-HARDEN v1 缺陷回归（原探针断言反转）', () => {
  const BOOKS_KEY = 'zhiqikeyuan:books';

  it('M22-01 删除运行中的书：执行器、心跳、监听与租约统一收尾（不残留 running/续租）', async () => {
    const book = setupCompiling('删除收尾书');
    startRun(book.id, { scenario: { stageDelayMs: 5, blockDelayMs: 300 } });
    expect(getRun(book.id)).not.toBeNull();
    expect(getLease(book.id)?.live).toBe(true);

    deleteBook(book.id);

    // 下一次驱动步发现书籍已删除 → 立即收尾（而不是继续 running 并续租）
    await waitFor(() => getRun(book.id) === null);
    expect(getRunExit(book.id)?.reason).toBe('deleted');
    expect(getLease(book.id)).toBeNull();
    // 跨过一个心跳周期：租约不被续期（无心跳残留）
    await new Promise((resolve) => setTimeout(resolve, 1200));
    expect(getLease(book.id)).toBeNull();
    expect(readBooks()).toEqual([]);
  }, 20000);

  it('M22-01 存储读取被拒：执行器收尾（不残留 running/心跳/租约），恢复后可从断点继续生成', async () => {
    const book = setupCompiling('读失败收尾书');
    startRun(book.id, { scenario: { stageDelayMs: 5, blockDelayMs: 20 } });
    await waitFor(() => getRun(book.id) !== null);

    const original = Storage.prototype.getItem;
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(function (
      this: Storage,
      name: string,
    ) {
      if (name === BOOKS_KEY) throw new Error('harden: read denied');
      return original.call(this, name);
    });
    await waitFor(() => getRun(book.id) === null);
    spy.mockRestore();

    // 收尾原因区分"读取失败"与"删除"；不残留租约与心跳
    expect(getRunExit(book.id)?.reason).toBe('read-denied');
    expect(getLease(book.id)).toBeNull();
    await new Promise((resolve) => setTimeout(resolve, 1200));
    expect(getLease(book.id)).toBeNull();

    // 读取被拒期间没有写入任何生成结果，也没有假报完成
    const stored = readBooks().find((item) => item.id === book.id)!;
    expect(stored.status).toBe('compiling');
    expect(stored.run?.status).not.toBe('finished');
    expect(getBookPages(book.id).every((page) => page.status === 'pending')).toBe(true);

    // 存储恢复后可恢复：从断点续跑到 ready
    expect(resumeRun(book.id)).not.toBeNull();
    await waitFor(
      () => readBooks().find((item) => item.id === book.id)!.status === 'ready',
      15000,
    );
    expect(getBookPages(book.id).every((page) => page.status === 'ready')).toBe(true);
  }, 25000);

  it('M22-02 修复返回真实异步结果，且旧任务不得借用新 runId 写入（冻结身份）', async () => {
    const book = setupCompiling('迟到写入书');
    const pageId = getBookPages(book.id)[0]!.id;
    const frozenRunId = book.run!.runId;

    const promise = regeneratePageExec(book.id, pageId);
    expect(typeof promise.then).toBe('function'); // 不再是 fire-and-forget 的 void

    // 启动后换 run（模拟重建/换轮次）：旧操作的写入必须全部被拒
    const raw = JSON.parse(window.localStorage.getItem(BOOKS_KEY)!) as Array<{
      id: string;
      run?: { runId: string };
      pages?: Array<{ id: string; blocks: Array<{ id: string; status?: string }> }>;
    }>;
    raw.find((item) => item.id === book.id)!.run!.runId = 'replacement-run';
    window.localStorage.setItem(BOOKS_KEY, JSON.stringify(raw));

    const result = await promise;
    expect(result.status).toBe('superseded');
    expect(result.droppedWrites).toBeGreaterThan(0);
    // 冻结的是启动时的运行身份，不是"最新的 runId"
    expect(result.runId).toBe(frozenRunId);
    expect(result.runId).not.toBe('replacement-run');

    const current = readBooks().find((item) => item.id === book.id)!;
    expect(current.run!.runId).toBe('replacement-run');
    // 迟到写入被拒：旧任务没有把任何块写成 ready
    const storedPage = getBookPage(book.id, pageId)!;
    expect(storedPage.blocks.some((block) => block.status === 'ready')).toBe(false);
  }, 20000);

  it('M22-02 单块重试：结果为 completed 且列出真实写入的块；同页重复请求复用同一 Promise', async () => {
    const book = setupCompiling('修复结果书');
    const page = getBookPages(book.id)[0]!;
    const target = page.blocks[0]!;
    startRun(book.id, { scenario: { ...FAST, failBlockIds: [target.id] } });
    await waitFor(() => getBookPage(book.id, page.id)?.status === 'partial');
    await waitFor(() => readBooks().find((item) => item.id === book.id)!.status === 'ready');

    const runId = readBooks().find((item) => item.id === book.id)!.run!.runId;
    const first = retryBlockExec(book.id, page.id, target.id);
    const second = retryBlockExec(book.id, page.id, target.id);
    expect(second).toBe(first); // 互斥：重复请求不产生第二遍生成

    const [r1, r2] = await Promise.all([first, second]);
    expect(r1.status).toBe('completed');
    expect(r2).toBe(r1);
    expect(r1.runId).toBe(runId);
    expect(r1.writtenBlockIds).toEqual([target.id]);
    expect(r1.droppedWrites).toBe(0);
    expect(getRepair(book.id, page.id)).toBeNull(); // 结束后不再占用互斥位
    expect(getBookPage(book.id, page.id)!.blocks.find((b) => b.id === target.id)!.status).toBe('ready');
  }, 25000);

  it('M22-02 整页重生成中重试单块：在途整页操作覆盖该块，复用同一 Promise（不留半生成页）', async () => {
    const book = setupCompiling('覆盖复用书');
    startRun(book.id, { scenario: FAST });
    await waitFor(() => readBooks().find((item) => item.id === book.id)!.status === 'ready');
    const page = getBookPages(book.id)[1]!;

    const pageOp = regeneratePageExec(book.id, page.id);
    const blockOp = retryBlockExec(book.id, page.id, page.blocks[0]!.id);
    expect(blockOp).toBe(pageOp); // 整页目标覆盖单块目标

    const [pageResult, blockResult] = await Promise.all([pageOp, blockOp]);
    expect(pageResult.status).toBe('completed');
    expect(blockResult).toBe(pageResult);
    expect(getBookPage(book.id, page.id)!.blocks.every((b) => b.status === 'ready')).toBe(true);
  }, 25000);

  it('M22-02 整页请求取代单块在途操作：旧操作终态 superseded，页最终完整 ready', async () => {
    const book = setupCompiling('取代操作书');
    startRun(book.id, { scenario: FAST });
    await waitFor(() => readBooks().find((item) => item.id === book.id)!.status === 'ready');
    const page = getBookPages(book.id)[1]!;

    const blockOp = retryBlockExec(book.id, page.id, page.blocks[0]!.id);
    const pageOp = regeneratePageExec(book.id, page.id);
    expect(pageOp).not.toBe(blockOp); // 整页请求未被单块在途操作覆盖 → 取代

    const [blockResult, pageResult] = await Promise.all([blockOp, pageOp]);
    expect(blockResult.status).toBe('superseded');
    expect(pageResult.status).toBe('completed');
    expect(getBookPage(book.id, page.id)!.blocks.every((b) => b.status === 'ready')).toBe(true);
  }, 25000);

  it('M22-02 取消：cancelRepairs 让在途修复以 cancelled 收尾，剩余写入丢弃', async () => {
    const book = setupCompiling('取消修复书');
    const pageId = getBookPages(book.id)[0]!.id;
    const promise = regeneratePageExec(book.id, pageId);
    expect(cancelRepairs(book.id, 'test-cancel')).toBe(1);

    const result = await promise;
    expect(result.status).toBe('cancelled');
    expect(result.writtenBlockIds).toEqual([]);
    expect(getRepair(book.id, pageId)).toBeNull();
  }, 20000);

  it('M22-02 存储写失败：修复以 failed 如实解析（不 reject、不谎报成功）', async () => {
    const book = setupCompiling('修复写失败书');
    const pageId = getBookPages(book.id)[0]!.id;
    // 复位通过仓储写入：注入一次真实写失败 → 修复在开始前就如实失败
    const original = Storage.prototype.setItem;
    const spy = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(function (
      this: Storage,
      name: string,
      value: string,
    ) {
      if (name === BOOKS_KEY) throw new DOMException('quota', 'QuotaExceededError');
      return original.call(this, name, value);
    });
    const result = await regeneratePageExec(book.id, pageId);
    spy.mockRestore();

    expect(result.status).toBe('failed');
    expect(result.error).toBeTruthy();
    expect(result.writtenBlockIds).toEqual([]);
    // 复位失败后不残留互斥占用
    expect(getRepair(book.id, pageId)).toBeNull();
  }, 20000);

  it('M22-05 最终完成写入失败：不假报完成，落 kind storage 失败并可重试完成（一次性注入）', async () => {
    const book = setupCompiling('完成写失败书');
    startRun(book.id, { scenario: { ...FAST, storageFailureOnFinish: true } });

    await waitFor(
      () => readBooks().find((item) => item.id === book.id)!.status === 'error',
      20000,
    );
    const failed = readBooks().find((item) => item.id === book.id)!;
    expect(failed.status).toBe('error'); // 绝不因"内存里跑完了"而写成 ready
    expect(failed.run?.failure?.kind).toBe('storage');
    expect(failed.run?.failure?.message).toContain('最终完成状态写入失败');
    expect(failed.run?.status).toBe('failed');
    expect(getRunExit(book.id)?.reason).toBe('failed');
    // 资源释放：句柄与租约都不残留
    expect(getRun(book.id)).toBeNull();
    expect(getLease(book.id)).toBeNull();

    // 恢复入口：重试生成（一次性注入不再触发）→ 真正完成
    expect(resumeRun(book.id)).not.toBeNull();
    await waitFor(
      () => readBooks().find((item) => item.id === book.id)!.status === 'ready',
      20000,
    );
    expect(getBookPages(book.id).every((page) => page.status === 'ready')).toBe(true);
    // 注入未污染真实存储
    window.localStorage.setItem('zhiqikeyuan:harden-probe', 'ok');
    expect(window.localStorage.getItem('zhiqikeyuan:harden-probe')).toBe('ok');
  }, 30000);

  it('stopRun 也取消在途修复（删除/停止入口不留幽灵任务）', async () => {
    const book = setupCompiling('停止取消修复书');
    const pageId = getBookPages(book.id)[0]!.id;
    const promise = regeneratePageExec(book.id, pageId);
    expect(getRepair(book.id, pageId)).not.toBeNull();
    stopRun(book.id, 'delete');
    const result = await promise;
    expect(result.status).toBe('cancelled');
    expect(getRepair(book.id, pageId)).toBeNull();
  }, 20000);

  it('A1 挑刺：修复期间书籍变为不可写（归档）→ 不得报 completed，块不计入写入结果', async () => {
    const book = setupCompiling('修复期间归档书');
    startRun(book.id, { scenario: FAST });
    await waitFor(() => readBooks().find((item) => item.id === book.id)!.status === 'ready');
    const page = getBookPages(book.id)[1]!;

    const promise = regeneratePageExec(book.id, page.id);
    // 复位已写入（页回 pending），趁块延时窗口把书归档：此后 runWritable 一律拒绝生成事件
    expect(archiveBook(book.id, true)?.status).toBe('archived');

    const result = await promise;
    expect(result.status).toBe('failed'); // 写入被仓储静默拒绝：绝不谎报 completed
    expect(result.writtenBlockIds).toEqual([]);
    expect(result.droppedWrites).toBeGreaterThan(0);
    expect(result.error).toMatch(/不接受生成|未生效/);
    expect(getRepair(book.id, page.id)).toBeNull();
    // 归档内容不被生成事件改写（块仍是复位后的 pending，不是 ready）
    const stored = getBookPage(book.id, page.id)!;
    expect(stored.blocks.some((block) => block.status === 'ready')).toBe(false);
  }, 25000);
});
