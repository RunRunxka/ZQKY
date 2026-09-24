import { expect, test, type Page, type Route } from '@playwright/test';

/**
 * CHAT-CONTEXT-BUDGET v1 浏览器回归：按**真实报文**断言请求预算。
 *
 * 上游替身（与 `course-sessions.spec.ts` 同法）：路由级 stub `model-catalog` / `model-profiles` /
 * `chat/stream`，并捕获发往 `POST /api/v1/chat/stream` 的请求体——课程块、历史与当前问题
 * 是否在同一预算内、每条是否不超后端单条上限、放不下时是否**根本不发请求**，这里按报文断言。
 * 真实供应商调用无可用凭证，本批记 not_run；后端硬限制的实现由 `apps/api/app/schemas/chat.py` 负责（本批零后端改动）。
 *
 * 隔离：每个 test 独立 context（IndexedDB / localStorage 为空）；不触碰用户 5173 数据。
 */

const CONTEXT_TOKENS = 8000;
const MAX_OUTPUT_TOKENS = 512;
/** 与 contracts/chat.ts 的 contextBudgetChars 同一公式（字符估算，不是精确 token 计数） */
const INPUT_BUDGET = Math.max(2000, CONTEXT_TOKENS * 2 - MAX_OUTPUT_TOKENS * 3); // 14464
const BACKEND_LIMITS = { maxMessages: 200, maxMessageChars: 32000, maxTotalChars: 120000 };
const COURSE_DISCLAIMER = '内容未解析、未检索、未随本请求发送';
const COURSE_LIMIT = 2400;

const PROFILES = [
  {
    id: 'profile-1',
    connectionId: 'conn-1',
    displayName: '模拟模型',
    modelId: 'sim-chat-1',
    purpose: 'chat',
    contextTokens: CONTEXT_TOKENS,
    maxOutputTokens: MAX_OUTPUT_TOKENS,
    supportedParams: ['temperature'],
    capabilities: { chat: 'verified' },
    connection: { displayName: '模拟连接', protocol: 'openai-chat', hasCredential: true },
    createdAt: '2026-09-06T00:00:00Z',
    updatedAt: '2026-09-06T00:00:00Z',
  },
];

const SSE_OK = [
  'event: message.start',
  'data: {"requestId":"req-1","messageId":"m1","modelProfileId":"profile-1"}',
  '',
  'event: text.delta',
  'data: {"messageId":"m1","text":"这是模拟回答。"}',
  '',
  'event: message.end',
  'data: {"messageId":"m1","finishReason":"stop"}',
  '',
  '',
].join('\n');

const SSE_ERROR = [
  'event: message.start',
  'data: {"requestId":"req-1","messageId":"m1","modelProfileId":"profile-1"}',
  '',
  'event: error',
  'data: {"code":"UPSTREAM_ERROR","message":"上游失败（测试替身）"}',
  '',
  '',
].join('\n');

interface StreamCall {
  messages: { role: string; content: string }[];
}

/** 路由级上游替身：记录每次 chat/stream 的请求体；可按序返回成功/失败 */
async function stubUpstream(
  page: Page,
  calls: StreamCall[],
  script: ('ok' | 'error')[] = [],
): Promise<void> {
  await page.route('**/api/v1/model-catalog', (route: Route) =>
    route.fulfill({
      json: {
        revision: 1,
        defaultChatProfileId: 'profile-1',
        profiles: PROFILES,
        connections: [
          { id: 'conn-1', displayName: '模拟连接', protocol: 'openai-chat', hasCredential: true },
        ],
      },
    }),
  );
  await page.route('**/api/v1/model-profiles', (route: Route) => route.fulfill({ json: PROFILES }));
  await page.route('**/api/v1/chat/stream', (route: Route) => {
    const body = route.request().postDataJSON() as {
      messages: { role: string; content: string }[];
    };
    calls.push({ messages: body.messages });
    const outcome = script[calls.length - 1] ?? 'ok';
    return route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: outcome === 'ok' ? SSE_OK : SSE_ERROR,
    });
  });
}

/** 报文级预算断言：条数、总字符、单条字符都在限制内，返回实际总字符 */
function expectBudgetCompliant(messages: { role: string; content: string }[]): number {
  const total = messages.reduce((sum, message) => sum + message.content.length, 0);
  expect(messages.length).toBeLessThanOrEqual(BACKEND_LIMITS.maxMessages);
  expect(total).toBeLessThanOrEqual(Math.min(INPUT_BUDGET, BACKEND_LIMITS.maxTotalChars));
  for (const message of messages) {
    expect(message.content.length).toBeLessThanOrEqual(BACKEND_LIMITS.maxMessageChars);
  }
  return total;
}

/** 载入演示课程并打开某课程详情页 */
async function openCourse(page: Page, path = '/courses/demo-course-math'): Promise<void> {
  await page.goto('/courses');
  await page.getByRole('button', { name: '载入演示数据' }).click();
  await page.goto(path);
  await expect(page.getByRole('heading', { name: '七年级数学（演示课程）' })).toBeVisible({
    timeout: 15000,
  });
}

/** 在课程页新建学习会话，返回会话 id */
async function openCourseSession(page: Page): Promise<string> {
  await page.getByRole('button', { name: '新建学习会话' }).click();
  await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}$/, { timeout: 20000 });
  const input = page.getByRole('textbox', { name: '输入问题' });
  await input.waitFor({ state: 'visible', timeout: 15000 });
  return page.url().split('/chat/')[1]!;
}

/** 发送一条消息并等待回答 */
async function sendMessage(page: Page, text: string): Promise<void> {
  const input = page.getByRole('textbox', { name: '输入问题' });
  await input.fill(text);
  await page.getByRole('button', { name: '发送' }).click();
  await expect(page.locator('.chat-bubble.user').last()).toContainText(text.slice(0, 24), {
    timeout: 15000,
  });
}

test.describe('请求预算（课程块 + 历史 + 当前问题）', () => {
  test('课程轮：system 课程块在最前、总字符不超预算、每条不超后端单条上限', async ({ page }) => {
    const calls: StreamCall[] = [];
    await stubUpstream(page, calls);
    await openCourse(page);
    await openCourseSession(page);
    await sendMessage(page, '这个单元怎么讲？');
    await expect(page.locator('.chat-bubble.assistant').last()).toContainText('这是模拟回答。');

    expect(calls).toHaveLength(1);
    const messages = calls[0]!.messages;
    expect(messages[0]!.role).toBe('system');
    expect(messages[0]!.content).toContain('课程名称：七年级数学（演示课程）');
    expect(messages[0]!.content).toContain('每次课前先复习上一单元错题');
    expect(messages[0]!.content).toContain(COURSE_DISCLAIMER);
    expect(messages[0]!.content.length).toBeLessThanOrEqual(COURSE_LIMIT);
    expectBudgetCompliant(messages);
    expect(messages.at(-1)).toMatchObject({ role: 'user', content: '这个单元怎么讲？' });
  });

  test('UI 粘贴超长大纲标题：报文仍合规、免责句仍在，课程原始数据未被改写', async ({ page }) => {
    const calls: StreamCall[] = [];
    await stubUpstream(page, calls);
    await openCourse(page);
    const hugeTitle = '单'.repeat(32001);
    await page.getByRole('button', { name: '编辑大纲' }).click();
    await page.getByLabel('大纲文本').fill(hugeTitle);
    await page.getByRole('button', { name: '保存大纲' }).click();
    await expect(page.getByText('已保存大纲（covered 已重置，由学员重新勾选）。')).toBeVisible({
      timeout: 15000,
    });

    await openCourseSession(page);
    await sendMessage(page, '这个单元怎么讲？');
    await expect(page.locator('.chat-bubble.assistant').last()).toContainText('这是模拟回答。');

    expect(calls).toHaveLength(1);
    const messages = calls[0]!.messages;
    expect(messages[0]!.role).toBe('system');
    expect(messages[0]!.content).toContain(COURSE_DISCLAIMER);
    // 课程块整体受 2400 与后端单条上限约束：超长标题不得整段进入报文（截到 120 字符）
    expect(messages[0]!.content.length).toBeLessThanOrEqual(COURSE_LIMIT);
    expect(messages[0]!.content).not.toContain('单'.repeat(200));
    expectBudgetCompliant(messages);

    // 课程原始数据未被改写（渲染期防御裁剪不落库）
    const stored = await page.evaluate(
      () =>
        JSON.parse(window.localStorage.getItem('zhiqikeyuan:courses') ?? '[]') as {
          id: string;
          syllabus: { title: string }[];
        }[],
    );
    expect(stored.find((course) => course.id === 'demo-course-math')?.syllabus[0]?.title).toBe(
      hugeTitle,
    );
  });

  test('当前问题放不下：不发任何请求、输入框内容仍在、提示可读；课程块放不下时如实提示；改短后成功', async ({
    page,
  }) => {
    const calls: StreamCall[] = [];
    await stubUpstream(page, calls);
    await openCourse(page);
    await openCourseSession(page);

    const input = page.getByRole('textbox', { name: '输入问题' });
    const tooLong = '问'.repeat(INPUT_BUDGET + 100);
    await input.fill(tooLong);
    await page.getByRole('button', { name: '发送' }).click();
    // 可读提示（字符估算口径，不是精确 token）
    const notice = page.getByRole('alert').filter({ hasText: '超出本轮可用预算' });
    await expect(notice).toBeVisible();
    await expect(notice).toContainText('字符估算');
    expect(calls).toHaveLength(0); // 没有发往 chat/stream 的请求
    await expect(input).toHaveValue(tooLong); // 输入框内容仍在，可改后重发
    await expect(page.locator('.chat-bubble.user')).toHaveCount(0);

    // 问题几乎占满预算：课程块整体放不下 → 本轮不带课程上下文，并如实提示
    await input.fill('问'.repeat(INPUT_BUDGET - 20));
    await page.getByRole('button', { name: '发送' }).click();
    await expect(page.locator('.chat-bubble.assistant').last()).toContainText('这是模拟回答。');
    expect(calls).toHaveLength(1);
    expect(calls[0]!.messages.some((message) => message.role === 'system')).toBe(false);
    expectBudgetCompliant(calls[0]!.messages);
    await expect(page.locator('[data-budget-record]')).toContainText('课程上下文');

    // 改短后：正常带上课程块；超长历史整条丢弃并如实提示
    await sendMessage(page, '简短问题');
    expect(calls).toHaveLength(2);
    expect(calls[1]!.messages[0]!.role).toBe('system');
    expect(calls[1]!.messages.at(-1)).toMatchObject({ role: 'user', content: '简短问题' });
    expectBudgetCompliant(calls[1]!.messages);
    await expect(page.locator('[data-budget-record]')).toContainText('丢弃最旧的 1 条历史消息');
  });

  test('上游错误后忙态回到可重试、无残留空占位；重试报文同样合规', async ({ page }) => {
    const calls: StreamCall[] = [];
    await stubUpstream(page, calls, ['error', 'ok']);
    await openCourse(page);
    await openCourseSession(page);
    await sendMessage(page, '会失败的问题');
    const errorCard = page.locator('.chat-bubble.assistant .chat-error');
    await expect(errorCard).toBeVisible({ timeout: 15000 });
    // 忙态已收尾：按钮回到「发送」，没有卡在「停止」
    await expect(page.getByRole('button', { name: '停止' })).toHaveCount(0);
    expect(calls).toHaveLength(1);

    await errorCard.getByRole('button', { name: '重试' }).click();
    await expect(page.locator('.chat-bubble.assistant').last()).toContainText('这是模拟回答。', {
      timeout: 15000,
    });
    expect(calls).toHaveLength(2);
    expect(calls[1]!.messages[0]!.role).toBe('system');
    expectBudgetCompliant(calls[1]!.messages);
    // 重试不追加重复用户消息，也不残留空助手占位
    expect(calls[1]!.messages.filter((message) => message.role === 'user')).toEqual([
      { role: 'user', content: '会失败的问题' },
    ]);
    await expect(page.locator('.chat-bubble.assistant')).toHaveCount(1);
    await expect(page.locator('.chat-bubble.user')).toHaveCount(1);
  });
});
