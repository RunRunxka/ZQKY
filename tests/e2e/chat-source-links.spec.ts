import { test, expect, type Page } from '@playwright/test';

/**
 * R-10 来源回链验收（笔记 / 题库 → 聊天）。
 * 隔离数据：本 spec 只写自己的 localStorage/IndexedDB 种子，不使用用户 5173。
 * 覆盖：正确会话、旧链接、会话已删除、缺失身份、重名内容、刷新、前进后退。
 */

const CHAT_DB = 'zhiqikeyuan-chat';

function conversation(id: string, title: string, updatedAt: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    title,
    messages: [
      { id: `${id}-u`, role: 'user', content: `问题-${id}`, status: 'done' },
      { id: `${id}-a`, role: 'assistant', content: `回答-${id}`, status: 'done' },
    ],
    createdAt: updatedAt,
    updatedAt,
    schemaVersion: 1,
    revision: 1,
    draft: '',
    modelProfileId: null,
    mode: 'real',
    ...extra,
  };
}

async function seedConversations(page: Page, items: Record<string, unknown>[]) {
  await page.addInitScript(
    ({ dbName, value }) => {
      const request = indexedDB.open(dbName, 1);
      request.onupgradeneeded = (event) => {
        (event.target as IDBOpenDBRequest).result.createObjectStore('conversations', { keyPath: 'id' });
      };
      request.onsuccess = () => {
        const db = request.result;
        const tx = db.transaction('conversations', 'readwrite');
        for (const item of value) tx.objectStore('conversations').put(item);
      };
    },
    { dbName: CHAT_DB, value: items },
  );
}

/** 题库条目：可指定是否带可靠 sessionId */
function quizEntry(id: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    messageId: `${id}-msg`,
    questionId: `${id}-q`,
    topic: '测试主题',
    question: `题目-${id}`,
    questionType: 'multiple_choice',
    options: { A: '甲', B: '乙' },
    correctAnswer: 'A',
    explanation: '解析',
    difficulty: 'easy',
    savedAt: '2026-09-08T01:00:00.000Z',
    source: 'deep_question',
    ...extra,
  };
}

async function seedQuiz(page: Page, entries: Record<string, unknown>[]) {
  await page.addInitScript(
    ({ value }) => window.localStorage.setItem('zhiqikeyuan:quiz-bank', JSON.stringify(value)),
    { value: entries },
  );
}

async function seedNotebookRecords(page: Page, records: Record<string, unknown>[]) {
  // 只写记录；默认笔记本（notebook-main「学习笔记」）由仓储按需创建，缺 notebookId 即归入其中
  await page.addInitScript(
    ({ value }) => {
      window.localStorage.setItem('zhiqikeyuan:notebook-entries', JSON.stringify(value));
    },
    { value: records },
  );
}

/** 进入默认笔记本，使记录列表可见（/notebooks 首屏要求先选择笔记本）。 */
async function openDefaultNotebook(page: Page) {
  await page.getByRole('button', { name: /学习笔记/ }).click();
}

test.describe('R-10 题库 → 会话回链', () => {
  test('有可靠 sessionId 且会话存在：链接指向该真实会话（不带 ?mode=mock）', async ({ page }) => {
    await seedConversations(page, [conversation('sess-a', '甲会话', '2026-09-08T01:00:00.000Z')]);
    await seedQuiz(page, [quizEntry('qa', { sessionId: 'sess-a' })]);
    await page.goto('/space/questions');

    const link = page.getByRole('link', { name: '查看出处会话' });
    await expect(link).toBeVisible();
    // R-10：链接同时带真实 sessionId 与 messageId（题库 messageId = `${id}-msg`）
    await expect(link).toHaveAttribute('href', '/chat/sess-a?message=qa-msg');
    await link.click();
    await expect(page).toHaveURL(/\/chat\/sess-a\?message=qa-msg$/);
    await expect(page.locator('.chat-bubble.user', { hasText: '问题-sess-a' })).toBeVisible();
  });

  test('旧数据无 sessionId：不显示来源链接也不报错', async ({ page }) => {
    await seedConversations(page, [conversation('sess-a', '甲会话', '2026-09-08T01:00:00.000Z')]);
    await seedQuiz(page, [quizEntry('legacy')]);
    await page.goto('/space/questions');
    await expect(page.getByText('题目-legacy')).toBeVisible();
    await expect(page.getByRole('link', { name: '查看出处会话' })).toHaveCount(0);
    await expect(page.getByText('来源会话已不存在')).toHaveCount(0);
  });

  test('来源会话已删除：提示来源不可用并保留内容，不建假会话', async ({ page }) => {
    await seedConversations(page, []);
    await seedQuiz(page, [quizEntry('qs', { sessionId: 'sess-gone' })]);
    await page.goto('/space/questions');
    await expect(page.getByText('题目-qs')).toBeVisible();
    await expect(page.getByText('来源会话已不存在')).toBeVisible();
    await expect(page.getByRole('link', { name: '查看出处会话' })).toHaveCount(0);
  });

  test('重名内容：两条指向各自会话，不串位', async ({ page }) => {
    await seedConversations(page, [
      conversation('sess-a', '同名', '2026-09-08T01:00:00.000Z'),
      conversation('sess-b', '同名', '2026-09-08T02:00:00.000Z'),
    ]);
    await seedQuiz(page, [
      { ...quizEntry('dup1'), question: '重复题目', sessionId: 'sess-a' },
      { ...quizEntry('dup2'), question: '重复题目', sessionId: 'sess-b' },
    ]);
    await page.goto('/space/questions');
    const links = page.getByRole('link', { name: '查看出处会话' });
    await expect(links).toHaveCount(2);
    const hrefs = await links.evaluateAll((nodes) => nodes.map((n) => n.getAttribute('href')));
    expect(hrefs.sort()).toEqual([
      '/chat/sess-a?message=dup1-msg',
      '/chat/sess-b?message=dup2-msg',
    ]);
  });

  test('刷新后仍按真实会话回链', async ({ page }) => {
    await seedConversations(page, [conversation('sess-a', '甲会话', '2026-09-08T01:00:00.000Z')]);
    await seedQuiz(page, [quizEntry('qa', { sessionId: 'sess-a' })]);
    await page.goto('/space/questions');
    await expect(page.getByRole('link', { name: '查看出处会话' })).toHaveAttribute(
      'href',
      '/chat/sess-a?message=qa-msg',
    );
    await page.reload();
    await expect(page.getByRole('link', { name: '查看出处会话' })).toHaveAttribute(
      'href',
      '/chat/sess-a?message=qa-msg',
    );
  });

  test('旧链接（/chat/<messageId>?mode=mock）：不静默落到最近会话，明确提示不存在', async ({ page }) => {
    await seedConversations(page, [conversation('sess-a', '甲会话', '2026-09-08T01:00:00.000Z')]);
    // 模拟历史错误链接：messageId 被当成 sessionId，并带过期 mode 参数
    await page.goto('/chat/qa-msg?mode=mock');
    await expect(page.getByText(/来源会话已不存在/)).toBeVisible();
    // 不出现模拟回答
    await expect(page.getByText('【模拟回复】')).toHaveCount(0);
  });

  test('前进/后退在会话回链与列表之间保持正确目标', async ({ page }) => {
    await seedConversations(page, [conversation('sess-a', '甲会话', '2026-09-08T01:00:00.000Z')]);
    await seedQuiz(page, [quizEntry('qa', { sessionId: 'sess-a' })]);
    await page.goto('/space/questions');
    await page.getByRole('link', { name: '查看出处会话' }).click();
    await expect(page).toHaveURL(/\/chat\/sess-a\?message=qa-msg$/);
    await page.goBack();
    await expect(page).toHaveURL(/\/space\/questions$/);
    await page.goForward();
    await expect(page).toHaveURL(/\/chat\/sess-a\?message=qa-msg$/);
  });
});

test.describe('R-10 笔记 → 会话回链', () => {
  test('有可靠 sessionId：打开原会话指向真实会话；无 sessionId 则不显示链接', async ({ page }) => {
    await seedConversations(page, [conversation('sess-n', '笔记来源', '2026-09-08T01:00:00.000Z')]);
    await seedNotebookRecords(page, [
      { id: 'n1', type: 'research_report', title: '带来源报告', content: '正文A', metadata: { sessionId: 'sess-n' }, createdAt: '2026-09-08T01:00:00.000Z', updatedAt: '2026-09-08T01:00:00.000Z' },
      { id: 'n2', type: 'chat', title: '无来源记录', content: '正文B', createdAt: '2026-09-08T02:00:00.000Z', updatedAt: '2026-09-08T02:00:00.000Z' },
    ]);
    await page.goto('/notebooks');
    await openDefaultNotebook(page);

    const withSource = page.locator('.space-session-card', { hasText: '带来源报告' });
    await withSource.getByRole('button', { name: '展开记录 带来源报告' }).click();
    await expect(withSource.getByRole('link', { name: '打开原会话' })).toHaveAttribute('href', '/chat/sess-n');

    const without = page.locator('.space-session-card', { hasText: '无来源记录' });
    await without.getByRole('button', { name: '展开记录 无来源记录' }).click();
    await expect(without).toContainText('正文B');
    await expect(without.getByRole('link', { name: '打开原会话' })).toHaveCount(0);
  });

  test('笔记来源会话已删除：提示不可用且保留记录内容', async ({ page }) => {
    await seedConversations(page, []);
    await seedNotebookRecords(page, [
      { id: 'n3', type: 'research_report', title: '孤立报告', content: '正文C', metadata: { sessionId: 'sess-gone' }, createdAt: '2026-09-08T01:00:00.000Z', updatedAt: '2026-09-08T01:00:00.000Z' },
    ]);
    await page.goto('/notebooks');
    await openDefaultNotebook(page);
    const row = page.locator('.space-session-card', { hasText: '孤立报告' });
    await row.getByRole('button', { name: '展开记录 孤立报告' }).click();
    await expect(row).toContainText('正文C');
    await expect(row).toContainText('来源会话已不存在');
    await expect(row.getByRole('link', { name: '打开原会话' })).toHaveCount(0);
  });
});
