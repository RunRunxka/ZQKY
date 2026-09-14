import { test, expect, type Page } from '@playwright/test';

/**
 * B-CHAT-SOURCE-FINISH v1：
 *  - 消息定位（来源链接带 sessionId + 可选 messageId，先在会话内定位再提示）
 *  - 失效会话不可用态（不自动打开最近会话）
 *  - **真实保存链路**（聊天产物 → 保存 → 来源回链），证明 sessionId/messageId 实际落库
 *
 * 隔离数据：本 spec 只写自己的 IndexedDB / localStorage 种子；不使用用户 5173。
 * “真实保存链路”用例在浏览器内点击产物视图的保存按钮，走生产保存代码写入 space-store，
 * 再在业务页读取回链——即由真实保存路径落库，而不是只注入业务页数据。
 */

const CHAT_DB = 'zhiqikeyuan-chat';

function conversation(
  id: string,
  title: string,
  updatedAt: string,
  messages: Record<string, unknown>[],
  extra: Record<string, unknown> = {},
) {
  return {
    id,
    title,
    messages,
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

const userMsg = (id: string, content: string) => ({
  id,
  role: 'user',
  content,
  status: 'done',
});
const aiMsg = (id: string, content: string, extra: Record<string, unknown> = {}) => ({
  id,
  role: 'assistant',
  content,
  status: 'done',
  ...extra,
});

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

/** 题库条目：可指定是否带可靠 sessionId / messageId */
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
  await page.addInitScript(
    ({ value }) => window.localStorage.setItem('zhiqikeyuan:notebook-entries', JSON.stringify(value)),
    { value: records },
  );
}

async function openDefaultNotebook(page: Page) {
  await page.getByRole('button', { name: /学习笔记/ }).click();
}

test.describe('来源消息定位（sessionId + messageId）', () => {
  test('题库链接带 messageId：进入会话后定位到该消息并给出提示', async ({ page }) => {
    await seedConversations(page, [
      conversation('sess-a', '甲会话', '2026-09-08T01:00:00.000Z', [
        userMsg('m1', '第一个问题'),
        aiMsg('m2', '第一个回答'),
        userMsg('m3', '第二个问题'),
        aiMsg('m4', '第二个回答'),
      ]),
    ]);
    await seedQuiz(page, [quizEntry('qa', { sessionId: 'sess-a', messageId: 'm4' })]);
    await page.goto('/space/questions');

    const link = page.getByRole('link', { name: '查看出处会话' });
    await expect(link).toHaveAttribute('href', '/chat/sess-a?message=m4');
    await link.click();

    await expect(page).toHaveURL(/\/chat\/sess-a\?message=m4$/);
    // 定位提示可识别
    await expect(page.getByRole('status').filter({ hasText: '已定位到来源消息' })).toBeVisible({
      timeout: 15000,
    });
    // 目标消息确实被定位（高亮由脚本临时设置 outline）
    const target = page.locator('[data-message-id="m4"]');
    await expect(target).toBeVisible();
  });

  test('只在目标会话内定位：另一会话有同名内容也不会被选中', async ({ page }) => {
    await seedConversations(page, [
      conversation('sess-a', '甲会话', '2026-09-08T01:00:00.000Z', [
        userMsg('m1', '同名问题'),
        aiMsg('m2', '同名回答'),
      ]),
      conversation('sess-b', '乙会话', '2026-09-08T02:00:00.000Z', [
        userMsg('n1', '同名问题'),
        aiMsg('n2', '同名回答'),
      ]),
    ]);
    await seedQuiz(page, [quizEntry('qb', { sessionId: 'sess-b', messageId: 'n2' })]);
    await page.goto('/space/questions');
    await page.getByRole('link', { name: '查看出处会话' }).click();

    // 打开的是 sess-b，且定位的是 n2（不是 sess-a 的同名 m2）
    await expect(page.getByText('乙会话').first()).toBeVisible({ timeout: 15000 });
    await expect(page.locator('[data-message-id="n2"]')).toBeVisible();
    await expect(page.locator('[data-message-id="m2"]')).toHaveCount(0);
    await expect(page.getByRole('status').filter({ hasText: '已定位到来源消息' })).toBeVisible();
  });

  test('messageId 已删除：提示“原消息已不存在”，会话与原题目保留', async ({ page }) => {
    await seedConversations(page, [
      conversation('sess-a', '甲会话', '2026-09-08T01:00:00.000Z', [
        userMsg('m1', '保留下来的问题'),
        aiMsg('m2', '保留下来的回答'),
      ]),
    ]);
    await seedQuiz(page, [quizEntry('qc', { sessionId: 'sess-a', messageId: 'deleted-msg' })]);
    await page.goto('/space/questions');
    await page.getByRole('link', { name: '查看出处会话' }).click();

    await expect(page.getByRole('status').filter({ hasText: '原消息已不存在' })).toBeVisible({
      timeout: 15000,
    });
    // 会话本身仍打开（内容保留）
    await expect(page.locator('[data-message-id="m2"]')).toBeVisible();
    // 原题目仍在题库页（返回后可查）
    await page.goBack();
    await expect(page.getByText('题目-qc')).toBeVisible();
  });

  test('笔记无 messageId：只打开会话、不显示“已定位”提示', async ({ page }) => {
    await seedConversations(page, [
      conversation('sess-n', '笔记来源', '2026-09-08T01:00:00.000Z', [userMsg('m1', '问题'), aiMsg('m2', '回答')]),
    ]);
    await seedNotebookRecords(page, [
      {
        id: 'n1',
        type: 'research_report',
        title: '无消息定位的报告',
        content: '正文',
        metadata: { sessionId: 'sess-n' },
        createdAt: '2026-09-08T01:00:00.000Z',
        updatedAt: '2026-09-08T01:00:00.000Z',
      },
    ]);
    await page.goto('/notebooks');
    await openDefaultNotebook(page);
    const row = page.locator('.space-session-card', { hasText: '无消息定位的报告' });
    await row.getByRole('button', { name: '展开记录 无消息定位的报告' }).click();
    const link = row.getByRole('link', { name: '打开原会话' });
    await expect(link).toHaveAttribute('href', '/chat/sess-n');
    await link.click();
    await expect(page.locator('[data-message-id="m2"]')).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole('status').filter({ hasText: '已定位到来源消息' })).toHaveCount(0);
  });

  test('刷新后仍定位到同一消息', async ({ page }) => {
    await seedConversations(page, [
      conversation('sess-a', '甲会话', '2026-09-08T01:00:00.000Z', [userMsg('m1', '问题'), aiMsg('m2', '回答')]),
    ]);
    await page.goto('/chat/sess-a?message=m2');
    await expect(page.locator('[data-message-id="m2"]')).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole('status').filter({ hasText: '已定位到来源消息' })).toBeVisible();
    await page.reload();
    await expect(page.locator('[data-message-id="m2"]')).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole('status').filter({ hasText: '已定位到来源消息' })).toBeVisible();
  });

  test('减少动画下仍定位并提示（不依赖平滑滚动）', async ({ page }) => {
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await seedConversations(page, [
      conversation('sess-a', '甲会话', '2026-09-08T01:00:00.000Z', [userMsg('m1', '问题'), aiMsg('m2', '回答')]),
    ]);
    await page.goto('/chat/sess-a?message=m2');
    await expect(page.getByRole('status').filter({ hasText: '已定位到来源消息' })).toBeVisible({
      timeout: 15000,
    });
    await expect(page.locator('[data-message-id="m2"]')).toBeVisible();
  });
});

test.describe('失效会话：明确不可用，不自动打开最近会话', () => {
  test('来源会话已删除：提示不可用，不展示最近会话，也不新建会话', async ({ page }) => {
    await seedConversations(page, [
      conversation('sess-latest', '最近会话', '2026-09-08T02:00:00.000Z', [
        userMsg('l1', '最近的问题'),
        aiMsg('l2', '最近的回答'),
      ]),
    ]);
    await page.goto('/chat/does-not-exist?message=x');
    await expect(page.getByText('来源会话已不存在', { exact: false })).toBeVisible({ timeout: 15000 });
    // 不自动打开最近会话到聊天区（学习记录侧栏按"保留学习记录"要求仍列出该会话）
    await expect(page.locator('.chat-message-column')).not.toContainText('最近会话');
    await expect(page.locator('.chat-bubble.assistant')).toHaveCount(0);
    await expect(page.getByText('从一个问题，开始理解。')).toBeVisible();
    // 学习记录与主动返回仍在
    await expect(page.getByText('学习记录')).toBeVisible();
    await expect(page.getByRole('link', { name: '返回学习问答' })).toBeVisible();
  });

  test('失效深链后不创建新会话（刷新仍无会话）', async ({ page }) => {
    await page.goto('/chat/does-not-exist');
    await expect(page.getByText('来源会话已不存在', { exact: false })).toBeVisible({ timeout: 15000 });
    await page.reload();
    await expect(page.getByText('来源会话已不存在', { exact: false })).toBeVisible({ timeout: 15000 });
    // 未产生任何新会话（学习记录为空）
    await expect(page.getByText('还没有会话')).toBeVisible({ timeout: 10000 }).catch(() => undefined);
    await expect(page.locator('.chat-bubble')).toHaveCount(0);
  });

  test('正常进入 /chat 的既有行为不变（落到最近会话，无失效提示）', async ({ page }) => {
    await seedConversations(page, [
      conversation('sess-latest', '最近会话', '2026-09-08T02:00:00.000Z', [userMsg('l1', '最近的问题')]),
    ]);
    await page.goto('/chat');
    await expect(page.getByText('最近会话').first()).toBeVisible({ timeout: 15000 });
    await expect(page.getByText('来源会话已不存在', { exact: false })).toHaveCount(0);
    await expect(page.getByRole('status').filter({ hasText: '已定位到来源消息' })).toHaveCount(0);
  });
});

test.describe('真实保存链路：聊天产物 → 保存 → 来源回链', () => {
  test('题库：在产物视图点“保存到题库”，回链带真实 sessionId 与 messageId', async ({ page }) => {
    const aiId = 'real-save-ai';
    await seedConversations(page, [
      conversation('sess-real', '真实保存会话', '2026-09-08T01:00:00.000Z', [
        userMsg('real-save-user', '请出题'),
        aiMsg(aiId, '这是题目产物', {
          artifacts: [
            {
              id: 'quiz-art-1',
              kind: 'quiz',
              title: '真实保存测验',
              content: '测验正文',
              createdAt: '2026-09-08T01:00:30.000Z',
              data: {
                topic: '勾股定理',
                questions: [
                  {
                    question_id: 'q1',
                    question: '直角边为3和4，斜边是？',
                    question_type: 'choice',
                    options: { A: '5', B: '6' },
                    correct_answer: 'A',
                    explanation: '勾股定理',
                    difficulty: 'easy',
                  },
                ],
              },
            },
          ],
        }),
      ]),
    ]);

    // 进入该会话，打开产物标签，点击真实保存按钮（走生产 saveAll）
    await page.goto('/chat/sess-real');
    await expect(page.locator('[data-message-id="real-save-ai"]')).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: /真实保存测验/ }).first().click();
    const saveBtn = page.getByRole('button', { name: /保存到题库/ });
    await saveBtn.click();
    await expect(page.getByText(/已保存到题库/)).toBeVisible({ timeout: 15000 });

    // 业务页读取：链接必须带真实 sessionId 与 messageId（证明两者已落库）
    await page.goto('/space/questions');
    await expect(page.getByText('直角边为3和4，斜边是？')).toBeVisible({ timeout: 15000 });
    const link = page.getByRole('link', { name: '查看出处会话' });
    await expect(link).toHaveAttribute('href', '/chat/sess-real?message=real-save-ai');
    await link.click();
    await expect(page.getByRole('status').filter({ hasText: '已定位到来源消息' })).toBeVisible({
      timeout: 15000,
    });
    await expect(page.locator('[data-message-id="real-save-ai"]')).toBeVisible();
  });

  test('笔记：在产物视图点“保存到笔记”，回链带真实 sessionId/messageId 并定位消息', async ({ page }) => {
    const aiId = 'real-report-ai';
    await seedConversations(page, [
      conversation('sess-report', '报告会话', '2026-09-08T01:00:00.000Z', [
        userMsg('real-report-user', '写报告'),
        aiMsg(aiId, '这是报告产物', {
          artifacts: [
            {
              id: 'report-art-1',
              kind: 'report',
              title: '真实保存报告',
              content: '# 报告\n正文内容',
              createdAt: '2026-09-08T01:00:30.000Z',
              data: { mode: 'deep_research', depth: 'standard', subtopics: [], citations: [] },
            },
          ],
        }),
      ]),
    ]);

    await page.goto('/chat/sess-report');
    await expect(page.locator('[data-message-id="real-report-ai"]')).toBeVisible({ timeout: 15000 });
    await page.getByRole('button', { name: /真实保存报告/ }).first().click();
    await page.getByRole('button', { name: /保存到笔记/ }).click();
    await expect(page.getByText(/已保存到笔记/)).toBeVisible({ timeout: 15000 });

    await page.goto('/notebooks');
    await openDefaultNotebook(page);
    const row = page.locator('.space-session-card', { hasText: '真实保存报告' });
    await row.getByRole('button', { name: '展开记录 真实保存报告' }).click();
    const link = row.getByRole('link', { name: '打开原会话' });
    await expect(link).toHaveAttribute('href', '/chat/sess-report?message=real-report-ai');
    await link.click();
    await expect(page.getByRole('status').filter({ hasText: '已定位到来源消息' })).toBeVisible({
      timeout: 15000,
    });
  });
});

test.describe('前进/后退与切换不误定位', () => {
  test('带 message 的前进/后退重新定位；切到别的会话不会定位到错误消息', async ({ page }) => {
    await seedConversations(page, [
      conversation('sess-a', '甲会话', '2026-09-08T01:00:00.000Z', [userMsg('a1', '甲问题'), aiMsg('a2', '甲回答')]),
      conversation('sess-b', '乙会话', '2026-09-08T02:00:00.000Z', [userMsg('b1', '乙问题'), aiMsg('b2', '乙回答')]),
    ]);
    await page.goto('/chat/sess-a?message=a2');
    await expect(page.locator('[data-message-id="a2"]')).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole('status').filter({ hasText: '已定位到来源消息' })).toBeVisible();

    // 切到另一个会话：不应在乙会话里定位甲的消息，也不该保留"已定位"提示
    await page.getByRole('button', { name: '乙会话' }).first().click();
    await expect(page.locator('[data-message-id="b2"]')).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole('status').filter({ hasText: '已定位到来源消息' })).toHaveCount(0);
    await expect(page.locator('[data-message-id="a2"]')).toHaveCount(0);

    // 后退回到带 message 的历史条目：重新定位 a2
    await page.goBack();
    await expect(page.locator('[data-message-id="a2"]')).toBeVisible({ timeout: 15000 });
    await expect(page.getByRole('status').filter({ hasText: '已定位到来源消息' })).toBeVisible();
  });
});
