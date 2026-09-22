import { expect, test, type Page, type Route } from '@playwright/test';

/**
 * H1-COURSE-SESSIONS v1 浏览器回归：课程 → 创建学习会话 → 真实问答 → 返回课程 → 恢复原会话。
 *
 * 上游替身（与 `chat.spec.ts` 同法）：路由级 stub `model-catalog` / `model-profiles` / `chat/stream`，
 * 并**捕获发往 `/api/v1/chat/stream` 的真实请求体**——课程上下文（system 消息）是否真的进入请求，
 * 这里按报文断言；"FastAPI → 供应商适配器"由 `apps/api/tests/test_chat_stream_api.py` 的
 * system 转发测试覆盖。真实供应商调用无可用凭证，本批记 not_run。
 *
 * 隔离：每个 test 独立 context（IndexedDB / localStorage 为空）；不触碰用户 5173 数据。
 */

const PROFILES = [
  {
    id: 'profile-1',
    connectionId: 'conn-1',
    displayName: '模拟模型',
    modelId: 'sim-chat-1',
    purpose: 'chat',
    contextTokens: 8000,
    maxOutputTokens: 512,
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
async function stubUpstream(page: Page, calls: StreamCall[], script: ('ok' | 'error')[] = []): Promise<void> {
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
    const body = route.request().postDataJSON() as { messages: { role: string; content: string }[] };
    calls.push({ messages: body.messages });
    const outcome = script[calls.length - 1] ?? 'ok';
    return route.fulfill({
      status: 200,
      headers: { 'content-type': 'text/event-stream' },
      body: outcome === 'ok' ? SSE_OK : SSE_ERROR,
    });
  });
}

/** 读取真实会话库（IndexedDB `zhiqikeyuan-chat`）中的会话 */
async function readConversations(page: Page): Promise<
  { id: string; title: string; courseId?: string }[]
> {
  return page.evaluate(
    () =>
      new Promise<{ id: string; title: string; courseId?: string }[]>((resolve, reject) => {
        const request = indexedDB.open('zhiqikeyuan-chat', 1);
        request.onupgradeneeded = () =>
          request.result.createObjectStore('conversations', { keyPath: 'id' });
        request.onerror = () => reject(request.error);
        request.onsuccess = () => {
          const db = request.result;
          const tx = db.transaction('conversations', 'readonly');
          const all = tx.objectStore('conversations').getAll();
          all.onsuccess = () => {
            const rows = (all.result as { id: string; title: string; courseId?: string }[]).map(
              (row) => ({ id: row.id, title: row.title, ...(row.courseId ? { courseId: row.courseId } : {}) }),
            );
            resolve(rows);
          };
          all.onerror = () => reject(all.error);
        };
      }),
  );
}

/** 载入演示课程并打开某课程详情页 */
async function openCourse(page: Page, name: string, path?: string): Promise<void> {
  await page.goto('/courses');
  if (path) {
    await page.getByRole('button', { name: '载入演示数据' }).click();
    await page.goto(path);
  } else {
    await page.getByRole('button', { name: '载入演示数据' }).click();
    await page.locator('.space-persona-card', { hasText: name }).getByRole('link').first().click();
  }
  await expect(page.getByRole('heading', { name })).toBeVisible({ timeout: 15000 });
}

/** 在聊天页发送一条消息并等待回答 */
async function sendMessage(page: Page, text: string): Promise<void> {
  const input = page.getByRole('textbox', { name: '输入问题' });
  await input.waitFor({ state: 'visible', timeout: 15000 });
  await input.fill(text);
  await page.getByRole('button', { name: '发送' }).click();
  await expect(page.locator('.chat-bubble.user').last()).toContainText(text, { timeout: 15000 });
}

test.describe('课程学习会话闭环', () => {
  test('两个课程各自创建与恢复会话，互不串位；课程上下文随请求发送', async ({ page }) => {
    const calls: StreamCall[] = [];
    await stubUpstream(page, calls);

    // 课程 A：演示课程
    await openCourse(page, '七年级数学（演示课程）', '/courses/demo-course-math');
    await page.getByRole('button', { name: '新建学习会话' }).click();
    await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}$/, { timeout: 20000 });
    const sessionA = page.url().split('/chat/')[1]!;
    await sendMessage(page, '课程A的问题');
    await expect(page.locator('.chat-bubble.assistant').last()).toContainText('这是模拟回答。');
    // 课程上下文真实进入请求（system 在 messages 最前）
    expect(calls[0]!.messages[0]!.role).toBe('system');
    expect(calls[0]!.messages[0]!.content).toContain('课程名称：七年级数学（演示课程）');
    expect(calls[0]!.messages[0]!.content).toContain('每次课前先复习上一单元错题');
    // 聊天页显示归属与返回入口
    await expect(page.locator('.chat-banner.course')).toContainText('所属课程：七年级数学（演示课程）');
    await page.getByRole('link', { name: '返回课程' }).click();
    await expect(page).toHaveURL(/\/courses\/demo-course-math$/);
    // 会话出现在本课程列表
    await expect(page.locator('.courses-sessions')).toContainText('学习会话（1）');
    await expect(page.locator('.courses-sessions').getByText('课程A的问题')).toBeVisible();

    // 课程 B：新建课程并创建会话
    await page.goto('/courses');
    await page.getByRole('button', { name: '新建课程' }).click();
    await page.getByLabel('名称').fill('第二门课程');
    await page.getByRole('button', { name: '创建', exact: true }).click();
    await expect(page).toHaveURL(/\/courses\/cs-/, { timeout: 15000 });
    const courseBUrl = page.url();
    await page.getByRole('button', { name: '新建学习会话' }).click();
    await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}$/, { timeout: 20000 });
    const sessionB = page.url().split('/chat/')[1]!;
    expect(sessionB).not.toBe(sessionA);
    await sendMessage(page, '课程B的问题');
    expect(calls[1]!.messages[0]!.content).toContain('课程名称：第二门课程');

    // 归属隔离：B 的会话不出现在 A 的列表里，反之亦然
    await page.goto(courseBUrl);
    await expect(page.locator('.courses-sessions')).toContainText('学习会话（1）');
    await expect(page.locator('.courses-sessions').getByText('课程B的问题')).toBeVisible();
    await page.goto('/courses/demo-course-math');
    await expect(page.locator('.courses-sessions')).toContainText('学习会话（1）');
    await expect(page.locator('.courses-sessions').getByText('课程B的问题')).toHaveCount(0);

    // 恢复原会话：从课程页打开，历史仍在且归属仍在
    await page.locator('.courses-sessions').getByRole('link', { name: /打开会话/ }).click();
    await expect(page).toHaveURL(new RegExp(`/chat/${sessionA}$`));
    await expect(page.locator('.chat-bubble.user').first()).toContainText('课程A的问题');
    const rows = await readConversations(page);
    expect(rows.find((row) => row.id === sessionA)?.courseId).toBe('demo-course-math');
    expect(rows.find((row) => row.id === sessionB)?.courseId).not.toBe('demo-course-math');
  });

  test('普通旧会话兼容：未归属不出现在课程列表，聊天页正常且不被改写', async ({ page }) => {
    const calls: StreamCall[] = [];
    await stubUpstream(page, calls);
    // 预置一条旧会话（无 courseId，历史内容齐全）
    await page.addInitScript(() => {
      const request = indexedDB.open('zhiqikeyuan-chat', 1);
      request.onupgradeneeded = () =>
        request.result.createObjectStore('conversations', { keyPath: 'id' });
      request.onsuccess = () => {
        request.result.transaction('conversations', 'readwrite').objectStore('conversations').put({
          id: 'legacy-plain',
          title: '普通旧会话',
          messages: [
            { id: 'u', role: 'user', content: '旧问题', status: 'done' },
            { id: 'a', role: 'assistant', content: '旧回答', status: 'done' },
          ],
          createdAt: '2026-09-01T00:00:00.000Z',
          updatedAt: '2026-09-01T00:00:00.000Z',
          schemaVersion: 1,
          revision: 1,
          draft: '',
          modelProfileId: null,
          mode: 'real',
        });
      };
    });

    await openCourse(page, '七年级数学（演示课程）', '/courses/demo-course-math');
    // 空态：旧会话不因"最近访问/标题"被算进本课程
    await expect(page.locator('.courses-sessions')).toContainText('本课程还没有学习会话');

    await page.goto('/chat/legacy-plain');
    await expect(page.locator('.chat-bubble.assistant').last()).toContainText('旧回答');
    // 无课程归属 chip
    await expect(page.locator('.chat-banner.course')).toHaveCount(0);
    // 发送仍走普通问答（无 system 课程块）
    await sendMessage(page, '继续问');
    expect(calls[0]!.messages.some((message) => message.role === 'system')).toBe(false);
    // 旧记录保持未归属（不被改写）
    const rows = await readConversations(page);
    expect(rows.find((row) => row.id === 'legacy-plain')?.courseId).toBeUndefined();
  });

  test('同一 tick 连点「新建学习会话」只产生一条会话；写入失败保留页面状态并可重试', async ({ page }) => {
    await stubUpstream(page, []);
    await openCourse(page, '七年级数学（演示课程）', '/courses/demo-course-math');

    // 同一 tick 连点两次（React 忙态尚未提交）：必须只创建一条
    const clicks = await page.evaluate(() => {
      const button = Array.from(document.querySelectorAll('button')).find((item) =>
        item.textContent?.includes('新建学习会话'),
      ) as HTMLButtonElement | undefined;
      if (!button) return 0;
      button.click();
      button.click();
      return 2;
    });
    expect(clicks).toBe(2);
    await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}$/, { timeout: 20000 });
    const created = page.url().split('/chat/')[1]!;
    const rowsAfterDoubleClick = await readConversations(page);
    expect(rowsAfterDoubleClick.filter((row) => row.courseId === 'demo-course-math')).toHaveLength(1);

    // 写入失败：注入一次 put 失败 → 错误提示、留在课程页、可重试
    await page.goto('/courses/demo-course-math');
    await page.evaluate((existingId) => {
      const prototype = IDBObjectStore.prototype as IDBObjectStore & {
        __zqkyPatched?: boolean;
      };
      if (prototype.__zqkyPatched) return;
      prototype.__zqkyPatched = true;
      const original = IDBObjectStore.prototype.put;
      let failures = 1;
      IDBObjectStore.prototype.put = function (this: IDBObjectStore, ...args: unknown[]) {
        const value = args[0] as { id?: string } | undefined;
        if (failures > 0 && value && typeof value.id === 'string' && value.id !== existingId) {
          failures -= 1;
          throw new DOMException('注入的写入失败（测试）', 'AbortError');
        }
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        return (original as any).apply(this, args);
      } as typeof IDBObjectStore.prototype.put;
    }, created);

    await page.getByRole('button', { name: '新建学习会话' }).click();
    await expect(page.getByRole('alert').filter({ hasText: '新建学习会话失败' })).toBeVisible({
      timeout: 15000,
    });
    await expect(page).toHaveURL(/\/courses\/demo-course-math$/); // 未跳转
    expect((await readConversations(page)).filter((row) => row.courseId === 'demo-course-math')).toHaveLength(1);

    // 重试成功 → 才跳转
    await page.getByRole('button', { name: '重试新建' }).click();
    await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}$/, { timeout: 20000 });
    expect((await readConversations(page)).filter((row) => row.courseId === 'demo-course-math')).toHaveLength(2);
  });

  test('刷新、前进后退与课程↔聊天往返：归属与历史保持', async ({ page }) => {
    const calls: StreamCall[] = [];
    await stubUpstream(page, calls);
    await openCourse(page, '七年级数学（演示课程）', '/courses/demo-course-math');
    await page.getByRole('button', { name: '新建学习会话' }).click();
    await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}$/, { timeout: 20000 });
    const sessionId = page.url().split('/chat/')[1]!;
    await sendMessage(page, '往返前的提问');

    await page.reload();
    await expect(page.locator('.chat-banner.course')).toContainText('所属课程：七年级数学（演示课程）');
    await expect(page.locator('.chat-bubble.user').first()).toContainText('往返前的提问');

    await page.goBack();
    await expect(page).toHaveURL(/\/courses\/demo-course-math$/);
    await page.goForward();
    await expect(page).toHaveURL(new RegExp(`/chat/${sessionId}$`));
    await expect(page.locator('.chat-banner.course')).toContainText('返回课程');
  });

  test('课程修改后新轮用新快照，旧轮重试保持旧快照', async ({ page }) => {
    const calls: StreamCall[] = [];
    await stubUpstream(page, calls, ['error', 'ok', 'ok']); // 第 1 轮失败以便重试
    await openCourse(page, '七年级数学（演示课程）', '/courses/demo-course-math');
    await page.getByRole('button', { name: '新建学习会话' }).click();
    await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}$/, { timeout: 20000 });
    await sendMessage(page, '第一轮（会失败）');
    await expect(page.locator('.chat-bubble.assistant .chat-error, .chat-bubble.assistant').last()).toBeVisible();

    // 课程改名 + 改约定
    await page.goto('/courses/demo-course-math');
    await page.getByRole('button', { name: '编辑', exact: true }).click();
    await page.getByLabel('名称').fill('七年级数学（改名后）');
    await page
      .getByLabel('学习约定（每次对话注入的课程 instructions）')
      .fill('新约定：先做五分钟小测。');
    await page.getByRole('button', { name: '保存', exact: true }).click();
    await expect(page.getByRole('heading', { name: '七年级数学（改名后）' })).toBeVisible({ timeout: 15000 });

    // 旧轮重试：仍用冻结时的旧快照
    await page.getByRole('link', { name: '返回课程' }).count(); // 页面已是课程页；用会话列表回到会话
    await page.locator('.courses-sessions').getByRole('link', { name: /打开会话/ }).click();
    await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}$/);
    await page.getByRole('button', { name: '重试' }).first().click();
    await expect(page.locator('.chat-bubble.assistant').last()).toContainText('这是模拟回答。', {
      timeout: 15000,
    });
    expect(calls[1]!.messages[0]!.content).toContain('七年级数学（演示课程）');
    expect(calls[1]!.messages[0]!.content).not.toContain('改名后');

    // 新轮：新快照
    await sendMessage(page, '第二轮');
    expect(calls[2]!.messages[0]!.content).toContain('七年级数学（改名后）');
    expect(calls[2]!.messages[0]!.content).toContain('新约定：先做五分钟小测。');
  });

  test('课程删除后：历史会话与消息保留、归属不改写、如实提示且按普通问答发送', async ({ page }) => {
    const calls: StreamCall[] = [];
    await stubUpstream(page, calls);
    await openCourse(page, '七年级数学（演示课程）', '/courses/demo-course-math');
    await page.getByRole('button', { name: '新建学习会话' }).click();
    await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}$/, { timeout: 20000 });
    const sessionId = page.url().split('/chat/')[1]!;
    await sendMessage(page, '删除前的提问');

    // 删除课程（非破坏：会话与消息保留）
    page.once('dialog', (dialog) => void dialog.accept());
    await page.goto('/courses/demo-course-math');
    await page.getByRole('button', { name: '删除', exact: true }).click();
    await expect(page).toHaveURL(/\/courses$/, { timeout: 15000 });

    await page.goto(`/chat/${sessionId}`);
    await expect(page.locator('.chat-bubble.user').first()).toContainText('删除前的提问');
    await expect(page.locator('.chat-banner.course')).toContainText('所属课程已删除或不可用');
    await sendMessage(page, '删除后的问题');
    await expect(page.getByRole('alert').filter({ hasText: '所属课程已删除或不可用' })).toBeVisible();
    // 不注入课程上下文（不沿用其他课程），历史与归属保留
    expect(calls[1]!.messages.some((message) => message.role === 'system')).toBe(false);
    const rows = await readConversations(page);
    expect(rows.find((row) => row.id === sessionId)?.courseId).toBe('demo-course-math');
  });

  test('归档课程：会话区只读（新建禁用），既有会话仍可打开且历史保留', async ({ page }) => {
    await stubUpstream(page, []);
    // 演示归档课程：新建入口禁用并给出说明
    await page.goto('/courses');
    await page.getByRole('button', { name: '载入演示数据' }).click();
    await page.goto('/courses/demo-course-archived');
    await expect(page.getByRole('button', { name: '新建学习会话' })).toBeDisabled();
    await expect(page.locator('.courses-sessions')).toContainText('已归档课程：学习会话为只读');
  });

  test('流式中切换会话：目标会话不被污染，迟到回答被丢弃', async ({ page }) => {
    const calls: StreamCall[] = [];
    await stubUpstream(page, calls);
    // 让第一次请求延迟返回，制造"流式中"窗口
    let delayed = true;
    await page.route('**/api/v1/chat/stream', async (route: Route) => {
      if (delayed) {
        delayed = false;
        await new Promise((resolve) => setTimeout(resolve, 4000));
        return route.fulfill({
          status: 200,
          headers: { 'content-type': 'text/event-stream' },
          body: SSE_OK,
        });
      }
      return route.fulfill({
        status: 200,
        headers: { 'content-type': 'text/event-stream' },
        body: SSE_OK,
      });
    });

    await openCourse(page, '七年级数学（演示课程）', '/courses/demo-course-math');
    await page.getByRole('button', { name: '新建学习会话' }).click();
    await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}$/, { timeout: 20000 });
    const courseSession = page.url().split('/chat/')[1]!;
    const input = page.getByRole('textbox', { name: '输入问题' });
    await input.waitFor({ state: 'visible', timeout: 15000 });
    await input.fill('课程会话的问题');
    await page.getByRole('button', { name: '发送' }).click();

    // 流式（请求已发出、回答未到）期间切到普通新会话
    await page.getByRole('button', { name: '新对话' }).click();
    const plainSession = page.url().includes('/chat/') ? page.url().split('/chat/')[1]! : '';
    expect(plainSession).not.toBe(courseSession);
    // 目标会话不应出现来源会话的消息或课程归属
    await expect(page.locator('.chat-bubble.user')).toHaveCount(0);
    await expect(page.locator('.chat-banner.course')).toHaveCount(0);

    // 迟到回答到达后仍不得写入目标会话
    await page.waitForTimeout(5000);
    await expect(page.locator('.chat-bubble.assistant')).toHaveCount(0);
    await expect(page.locator('.chat-banner.course')).toHaveCount(0);
    const rows = await readConversations(page);
    const courseRow = rows.find((row) => row.id === courseSession);
    expect(courseRow?.courseId).toBe('demo-course-math');
  });

  test('三视口无横向溢出、键盘可创建会话、减少动画下仍可用', async ({ page }) => {
    await stubUpstream(page, []);
    await openCourse(page, '七年级数学（演示课程）', '/courses/demo-course-math');
    const heading = page.getByRole('heading', { name: '学习会话' });

    for (const viewport of [
      { width: 1440, height: 900 },
      { width: 1920, height: 1080 },
      { width: 390, height: 844 },
    ]) {
      await page.setViewportSize(viewport);
      await expect(heading).toBeVisible();
      const overflow = await page.evaluate(
        () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
      );
      expect(overflow, `${viewport.width}×${viewport.height} 课程页不应横向溢出`).toBeLessThanOrEqual(1);
    }

    // 键盘可达：聚焦「新建学习会话」后回车即创建并跳转（不依赖鼠标）
    const newButton = page.getByRole('button', { name: '新建学习会话' });
    await newButton.focus();
    await expect(newButton).toBeFocused();
    await page.keyboard.press('Enter');
    await expect(page).toHaveURL(/\/chat\/[0-9a-f-]{36}$/, { timeout: 20000 });

    // 减少动画：课程页与会话区仍然完整可用，不依赖过渡/动画完成
    await page.emulateMedia({ reducedMotion: 'reduce' });
    await page.goto('/courses/demo-course-math');
    await expect(heading).toBeVisible();
    await expect(page.getByRole('button', { name: '新建学习会话' })).toBeEnabled();
    await expect(page.getByRole('link', { name: /打开会话/ })).toHaveCount(1);
  });
});
