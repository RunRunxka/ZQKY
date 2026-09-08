import { test, expect, type Page } from '@playwright/test';

/**
 * R19–R25 输入区与结果工作区边界回归
 * （自 _work/review-s2-s3-20260908/composer-boundaries.spec.ts 迁入正式回归，验收语义不变）：
 * - R19 配置确认：任意字段变更撤销确认，非法配置无法绕过提交；
 * - R20 提交契约：模拟只附件发送必须形成轮次；真实模式粘贴附件不静默转纯文字请求；
 * - R21 会话归属：会话级人设选择不串入新建会话；
 * - R22 面板选择：产物打开时请求配置，配置卡必须显式激活可见；
 * - R23 文件并发：串行接纳 + 读取占位预留配额，超配额明确报错；
 * - R24 产物身份：不同轮同 id 产物以复合身份打开，各自正确。
 * 全部在隔离上下文与本地/夹具数据上执行：模拟模式不访问真实模型，
 * 真实模式用本地 SSE 拦截夹具（不调用真实供应商）。
 */

test.beforeEach(async ({ page }) => {
  await page.route('**/api/v1/model-catalog', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: '{"detail":"isolated review; no supplier"}',
    }),
  );
});

async function mock(page: Page) {
  await page.goto('/chat');
  await expect(page.getByRole('textbox', { name: '输入问题' })).toBeEnabled();
  await page.getByRole('button', { name: '模拟', exact: true }).click();
  await expect(page.getByRole('textbox', { name: '输入问题' })).toBeEnabled();
}

async function choose(page: Page, label: string) {
  await page.getByRole('button', { name: /选择业务能力，当前/ }).click();
  await page
    .getByRole('dialog', { name: '选择业务能力' })
    .getByRole('button', { name: new RegExp('^' + label) })
    .click();
}

async function seedArtifacts(page: Page) {
  await page.goto('/chat');
  await expect(page.getByRole('textbox', { name: '输入问题' })).toBeEnabled();
  await page.evaluate(
    async () =>
      new Promise<void>((resolve, reject) => {
        const req = indexedDB.open('zhiqikeyuan-chat-mock', 1);
        req.onupgradeneeded = () => req.result.createObjectStore('conversations', { keyPath: 'id' });
        req.onerror = () => reject(req.error);
        req.onsuccess = () => {
          const db = req.result,
            tx = db.transaction('conversations', 'readwrite');
          tx.objectStore('conversations').put({
            id: 'artifact-review',
            title: 'artifact-review',
            schemaVersion: 1,
            revision: 1,
            draft: '',
            modelProfileId: null,
            mode: 'mock',
            createdAt: '2026-09-08T00:00:00.000Z',
            updatedAt: '2026-09-08T00:00:00.000Z',
            messages: ['A', 'B'].flatMap((label) => [
              { id: `u-${label}`, role: 'user', content: `question ${label}`, status: 'done' },
              {
                id: `a-${label}`,
                turnId: `turn-${label}`,
                role: 'assistant',
                content: `answer ${label}`,
                status: 'done',
                artifacts: [
                  {
                    id: 'report',
                    kind: 'markdown',
                    title: `产物 ${label}`,
                    content: `payload-${label}`,
                    createdAt: '2026-09-08T00:00:00.000Z',
                  },
                ],
              },
            ]),
          });
          tx.oncomplete = () => {
            db.close();
            resolve();
          };
          tx.onerror = () => reject(tx.error);
        };
      }),
  );
  await page.reload();
  await page.getByRole('button', { name: '模拟', exact: true }).click();
  await expect(page.locator('.chat-artifact-chips')).toHaveCount(2);
}

test('R19 编辑已确认的配置撤销确认并阻断发送', async ({ page }) => {
  await mock(page);
  await choose(page, '智能出题');
  await page.getByRole('textbox', { name: '输入问题' }).fill('配置更改验证');
  await page.getByRole('button', { name: '先确认能力配置' }).click();
  const card = page.locator('.chat-cap-config');
  await card.getByLabel('出题主题').fill('原主题');
  await card.getByRole('button', { name: '确认', exact: true }).click();
  await card.getByLabel('出题主题').fill('');
  await expect(card).toContainText('出题主题不能为空');
  await expect(page.getByRole('button', { name: '先确认能力配置' })).toBeVisible();
});

test('R20 只附件发送必须先形成轮次再清理待发送附件', async ({ page }) => {
  await mock(page);
  await page.setInputFiles('input[type=file]', {
    name: 'only.txt',
    mimeType: 'text/plain',
    buffer: Buffer.from('keep me'),
  });
  await expect(page.locator('.chat-attach-card')).toHaveCount(1);
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(page.locator('.chat-row.user')).toHaveCount(1);
});

test('R20 真实模式粘贴附件必须先说明不支持，不得静默发出纯文字请求', async ({ page }) => {
  const profile = {
    id: 'fixture-profile',
    connectionId: 'fixture-connection',
    displayName: '审查夹具',
    modelId: 'fixture',
    purpose: 'chat',
    contextTokens: 8000,
    maxOutputTokens: 512,
    connection: { hasCredential: true, displayName: '审查夹具', protocol: 'openai-chat' },
  };
  await page.route('**/api/v1/model-catalog', (route) =>
    route.fulfill({ json: { revision: 1, defaultChatProfileId: profile.id, profiles: [profile], connections: [] } }),
  );
  let calls = 0;
  await page.route('**/api/v1/chat/stream', (route) => {
    calls++;
    return route.fulfill({
      status: 200,
      contentType: 'text/event-stream',
      body: 'event: text.delta\ndata: {"text":"fixture response"}\n\nevent: message.end\ndata: {"finishReason":"stop"}\n\n',
    });
  });
  await page.goto('/chat');
  const input = page.getByRole('textbox', { name: '输入问题' });
  await expect(input).toBeEnabled();
  await page.evaluate(() => {
    const data = new DataTransfer();
    data.items.add(new File(['attachment content'], 'review.txt', { type: 'text/plain' }));
    document.querySelector('textarea')!.dispatchEvent(
      new ClipboardEvent('paste', { clipboardData: data, bubbles: true, cancelable: true }),
    );
  });
  await input.fill('请分析附件');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(page.getByRole('alert').filter({ hasText: /附件|解析/ })).toBeVisible();
  expect(calls).toBe(0);
});

test('R21 声明为会话级的人设选择不得串入新建会话', async ({ page }) => {
  await mock(page);
  await page.getByRole('button', { name: '新建对话', exact: true }).click();
  await expect(page).toHaveURL(/\/chat\/.+/);
  const originalSessionUrl = page.url();
  await page.getByRole('button', { name: '添加文件与上下文' }).click();
  const menu = page.getByRole('dialog', { name: '添加文件与上下文' });
  await menu.getByRole('button', { name: '载入演示数据', exact: true }).first().click();
  await menu.getByRole('button', { name: /耐心的小学老师/ }).click();
  await menu.press('Escape');
  await expect(page.locator('.chat-ref-tree')).toContainText('耐心的小学老师');
  await page.getByRole('button', { name: '新建对话', exact: true }).click();
  await expect(page).not.toHaveURL(originalSessionUrl);
  await expect(page.locator('.chat-ref-tree')).toHaveCount(0);
});

test('R22 打开产物时请求能力配置必须显示配置卡', async ({ page }) => {
  await seedArtifacts(page);
  await page.locator('.chat-artifact-chips').first().getByRole('button').click();
  await expect(page.locator('.chat-artifact-panel')).toBeVisible();
  await choose(page, '智能出题');
  await page.getByRole('textbox', { name: '输入问题' }).fill('下一次出题');
  await page.getByRole('button', { name: '先确认能力配置' }).click();
  await expect(page.locator('.chat-cap-config')).toBeVisible();
});

test('R23 并发文件读取以读取占位预留配额', async ({ page }) => {
  await page.addInitScript(() => {
    const read = FileReader.prototype.readAsDataURL;
    FileReader.prototype.readAsDataURL = function (file) {
      setTimeout(() => read.call(this, file), 350);
    };
  });
  await mock(page);
  await page.evaluate(() => {
    const input = document.querySelector<HTMLInputElement>('input[type=file]')!;
    for (const name of ['one.txt', 'two.txt']) {
      const data = new DataTransfer();
      data.items.add(new File([new Uint8Array(16 * 1024 * 1024)], name, { type: 'text/plain' }));
      input.files = data.files;
      input.dispatchEvent(new Event('change', { bubbles: true }));
    }
  });
  await expect(page.locator('.chat-attach-card').first()).toBeVisible();
  await expect(page.locator('.chat-attach-error')).toContainText('25MB');
  await expect(page.locator('.chat-attach-card')).toHaveCount(1);
});

test('R24 不同轮次同 id 产物必须打开被点击的轮次', async ({ page }) => {
  await seedArtifacts(page);
  await page.locator('.chat-artifact-chips').nth(1).getByRole('button').click();
  await expect(page.locator('.chat-artifact-preview-body')).toContainText('payload-B');
});
