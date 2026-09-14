import { test, expect } from '@playwright/test';

/**
 * S2 深链回归：/chat/[sessionId] 定位具体会话；无效 id 显示明确状态。
 * 会话通过 IndexedDB 预置（真实库），不依赖模型凭证与后端。
 */
const SEED_CONVERSATION = {
  id: 'seed-deeplink-1',
  title: '深链核验会话',
  messages: [
    { id: 'u', role: 'user', content: '深链里的问题', status: 'done' },
    { id: 'a', role: 'assistant', content: '深链里的回答', status: 'done' },
  ],
  createdAt: '2026-09-07T00:00:00.000Z',
  updatedAt: '2026-09-07T00:00:00.000Z',
  schemaVersion: 1,
  revision: 1,
  draft: '',
  modelProfileId: null,
  mode: 'real',
};

test('深链定位到指定会话并显示历史', async ({ page }) => {
  await page.addInitScript((seed) => {
    const request = indexedDB.open('zhiqikeyuan-chat', 1);
    request.onupgradeneeded = (event) => {
      (event.target as IDBOpenDBRequest).result.createObjectStore('conversations', {
        keyPath: 'id',
      });
    };
    request.onsuccess = () => {
      const db = request.result;
      db.transaction('conversations', 'readwrite')
        .objectStore('conversations')
        .put(seed);
    };
  }, SEED_CONVERSATION);
  await page.goto('/chat/seed-deeplink-1');
  const textarea = page.getByRole('textbox', { name: '输入问题' });
  await textarea.waitFor({ state: 'visible', timeout: 15000 });
  await expect(page.getByText('深链核验会话').first()).toBeVisible({ timeout: 15000 });
  await expect(page.locator('.chat-bubble.assistant').last()).toContainText('深链里的回答');
  await expect(page.getByRole('status').filter({ hasText: '会话不存在' })).toHaveCount(0);
});

test('无效会话 id 显示明确的不可用状态，且不自动打开最近会话', async ({ page }) => {
  // 预置一个会话，确认失效深链不会把它当作“最近会话”展示
  await page.addInitScript((seed) => {
    const request = indexedDB.open('zhiqikeyuan-chat', 1);
    request.onupgradeneeded = (event) => {
      (event.target as IDBOpenDBRequest).result.createObjectStore('conversations', { keyPath: 'id' });
    };
    request.onsuccess = () => {
      const db = request.result;
      db.transaction('conversations', 'readwrite').objectStore('conversations').put(seed);
    };
  }, SEED_CONVERSATION);
  await page.goto('/chat/does-not-exist');
  const textarea = page.getByRole('textbox', { name: '输入问题' });
  await textarea.waitFor({ state: 'visible', timeout: 15000 });
  await expect(page.getByText('来源会话已不存在', { exact: false })).toBeVisible({ timeout: 15000 });
  await expect(page.getByRole('link', { name: '返回学习问答' })).toBeVisible();
  // 不自动落到最近会话到聊天区（学习记录侧栏按“保留学习记录”要求仍可列出该会话）
  await expect(page.locator('.chat-message-column')).not.toContainText('深链核验会话');
  await expect(page.locator('.chat-bubble.assistant')).toHaveCount(0);
  await expect(page.getByText('从一个问题，开始理解。')).toBeVisible();
});

/** R17 迁移：深链进入后，用户新建/切换会话不被 URL 强行回跳 */
async function seedAlphaBeta(page: import('@playwright/test').Page) {
  await page.route('**/api/v1/model-catalog', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'review only; no provider' }),
    }),
  );
  await page.goto('/chat');
  await page.getByRole('textbox', { name: '输入问题' }).waitFor();
  await page.evaluate(async () => {
    await new Promise<void>((resolve, reject) => {
      const request = indexedDB.open('zhiqikeyuan-chat', 1);
      request.onupgradeneeded = () =>
        request.result.createObjectStore('conversations', { keyPath: 'id' });
      request.onerror = () => reject(request.error);
      request.onsuccess = () => {
        const db = request.result;
        const tx = db.transaction('conversations', 'readwrite');
        for (const id of ['alpha', 'beta']) {
          tx.objectStore('conversations').put({
            id,
            title: `review-${id}`,
            schemaVersion: 1,
            revision: 1,
            draft: '',
            modelProfileId: null,
            mode: 'real',
            createdAt: '2026-09-07T00:00:00.000Z',
            updatedAt: '2026-09-07T00:00:00.000Z',
            messages: [
              { id: `${id}-u`, role: 'user', content: `question-${id}`, status: 'done' },
              { id: `${id}-a`, role: 'assistant', content: `answer-${id}`, status: 'done' },
            ],
          });
        }
        tx.oncomplete = () => {
          db.close();
          resolve();
        };
        tx.onerror = () => reject(tx.error);
      };
    });
  });
}

test('R17：深链进入后新建对话不被 URL 回跳', async ({ page }) => {
  await seedAlphaBeta(page);
  await page.goto('/chat/alpha');
  await expect(page.locator('.chat-bubble.assistant')).toContainText('answer-alpha', {
    timeout: 15000,
  });
  await page.getByRole('button', { name: '新建对话', exact: true }).click();
  await expect(page.locator('.chat-bubble.assistant')).toHaveCount(0);
  await page.getByRole('textbox', { name: '输入问题' }).fill('新会话草稿');
  await expect(page.locator('.chat-bubble.assistant')).toHaveCount(0); // 不回跳 alpha
});

test('R17：深链进入后切换其他会话不被 URL 回跳', async ({ page }) => {
  await seedAlphaBeta(page);
  await page.goto('/chat/alpha');
  await expect(page.locator('.chat-bubble.assistant')).toContainText('answer-alpha', {
    timeout: 15000,
  });
  await page.getByRole('button', { name: '打开会话 review-beta', exact: true }).click();
  await expect(page.locator('.chat-bubble.assistant')).toContainText('answer-beta', {
    timeout: 15000,
  }); // 停留在 beta
});

/** 交付复核（2026-09-07）迁移：选择会话后地址与当前会话同步，刷新不回旧会话 */
test('选择会话后地址同步，刷新后仍显示所选会话', async ({ page }) => {
  await seedAlphaBeta(page);
  await page.goto('/chat/alpha');
  await expect(page.locator('.chat-bubble.assistant')).toContainText('answer-alpha', {
    timeout: 15000,
  });
  await page.getByRole('button', { name: '打开会话 review-beta', exact: true }).click();
  await expect(page.locator('.chat-bubble.assistant')).toContainText('answer-beta', {
    timeout: 15000,
  });
  expect(new URL(page.url()).pathname).toBe('/chat/beta'); // 地址表达正在查看的会话
  await page.reload();
  await expect(page.locator('.chat-bubble.assistant')).toContainText('answer-beta', {
    timeout: 15000,
  }); // 刷新仍为 beta，不回 alpha
});

/** 深链契约：前进/后退按 URL 重新定位会话 */
test('后退返回上一个会话，前进回到切换后的会话', async ({ page }) => {
  await seedAlphaBeta(page);
  await page.goto('/chat/alpha');
  await expect(page.locator('.chat-bubble.assistant')).toContainText('answer-alpha', {
    timeout: 15000,
  });
  await page.getByRole('button', { name: '打开会话 review-beta', exact: true }).click();
  await expect(page.locator('.chat-bubble.assistant')).toContainText('answer-beta', {
    timeout: 15000,
  });
  await page.goBack();
  await expect(page.locator('.chat-bubble.assistant')).toContainText('answer-alpha', {
    timeout: 15000,
  });
  await page.goForward();
  await expect(page.locator('.chat-bubble.assistant')).toContainText('answer-beta', {
    timeout: 15000,
  });
});

/** 深链契约：新建后地址指向新会话，刷新可恢复（会话已入库） */
test('新建对话后地址指向新会话，刷新不回跳且无不存在提示', async ({ page }) => {
  await seedAlphaBeta(page);
  await page.goto('/chat/alpha');
  await expect(page.locator('.chat-bubble.assistant')).toContainText('answer-alpha', {
    timeout: 15000,
  });
  await page.getByRole('button', { name: '新建对话', exact: true }).click();
  await expect(page.locator('.chat-bubble.assistant')).toHaveCount(0);
  const pathname = new URL(page.url()).pathname;
  expect(pathname.startsWith('/chat/')).toBe(true);
  expect(pathname === '/chat/alpha' || pathname === '/chat/beta').toBe(false); // 地址已指向新会话
  await page.waitForTimeout(700); // 等待防抖保存落盘
  await page.reload();
  await expect(page.getByRole('textbox', { name: '输入问题' })).toBeVisible({ timeout: 15000 });
  await expect(page.locator('.chat-bubble.assistant')).toHaveCount(0); // 仍是空的新会话
  await expect(page.getByText('来源会话已不存在', { exact: false })).toHaveCount(0);
});
