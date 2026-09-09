import { test, expect } from '@playwright/test';

for (const model of ['教学问答模型', 'Responses 模型', 'Anthropic 模型']) {
  test(`${model} 经真实代理在最后分块释放前显示中文`, async ({ page, request }, testInfo) => {
    await page.goto('/chat');
    await page.getByRole('button', { name: '选择模型', exact: true }).click();
    await page.getByRole('dialog').getByRole('button').filter({ hasText: model }).click();
    await page.getByRole('textbox', { name: '输入问题' }).fill('请解释一个概念');
    await page.getByRole('button', { name: '发送', exact: true }).click();
    await expect(page.getByText('第一段中文已经到达。', { exact: true })).toBeVisible();
    expect((await (await request.get('http://127.0.0.1:8002/stats')).json()).last).toBeNull();
    await expect(page.getByRole('button', { name: '停止', exact: true })).toBeVisible();
    await page.screenshot({ path: testInfo.outputPath('stream-in-progress.png') });
    await request.get('http://127.0.0.1:8002/release');
    await expect(page.getByText('最后一段已释放。', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '发送', exact: true })).toBeVisible();
    await page.reload();
    await expect(page.getByText('第一段中文已经到达。', { exact: true })).toBeVisible();
  });
}
test('停止关闭实际上游，新会话无晚到文本', async ({ page, request }) => {
  await page.goto('/chat');
  await page.getByRole('textbox', { name: '输入问题' }).fill('暂停测试');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(page.getByText('第一段中文已经到达。', { exact: true })).toBeVisible();
  await page.getByRole('button', { name: '停止', exact: true }).click();
  await expect
    .poll(async () => (await (await request.get('http://127.0.0.1:8002/stats')).json()).cancelled)
    .toBe(true);
  await page.getByRole('button', { name: '新建对话', exact: true }).click();
  await expect(page.getByText('从一个问题，开始理解。')).toBeVisible();
  await expect(page.locator('.answer-markdown')).toHaveCount(0);
});
test('长回答 Markdown 公式与响应式布局', async ({ page, request }, info) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/chat');
  await page.screenshot({ path: info.outputPath('chat-empty-1440.png') });
  await page.getByRole('textbox', { name: '输入问题' }).fill('长回答');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(page.getByText('第一段中文已经到达。', { exact: true })).toBeVisible();
  await request.get('http://127.0.0.1:8002/release');
  await expect(page.getByText('最后一段已释放。', { exact: true })).toBeVisible();
  await expect(page.locator('.katex').first()).toBeAttached();
  await expect(page.locator('.answer-table')).toHaveCount(6);
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.locator('.chat-messages').evaluate((el) => {
      el.scrollTop = 150;
    });
    await page.screenshot({ path: info.outputPath(`chat-answer-${width}.png`) });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    if (width === 390)
      expect((await page.locator('.chat-main').boundingBox())!.width).toBeGreaterThan(350);
    await expect(page.getByRole('textbox', { name: '输入问题' })).toBeVisible();
  }
});
test('模型发现追加、默认模型同步、表单冲突保留', async ({ page, request }, info) => {
  await page.goto('/settings');
  const connection = page.locator('.connection-group').filter({ hasText: '教学模型服务' });
  await connection.getByRole('button', { name: '从服务获取模型' }).click();
  const modal = page.getByRole('dialog');
  await expect(modal.getByRole('checkbox', { name: 'teaching-alpha' })).toBeDisabled();
  await modal.getByRole('checkbox', { name: 'teaching-beta' }).check();
  await modal.getByRole('button', { name: '添加所选 1 个模型' }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  const card = page.locator('.managed-model').filter({ hasText: 'teaching-beta' });
  await card.getByRole('button', { name: '设为默认' }).click();
  await expect(card.getByText('默认', { exact: true })).toBeVisible();
  await card.getByRole('button', { name: '编辑模型 teaching-beta' }).click();
  await page.getByRole('dialog').getByLabel('显示名称').fill('未保存的新名称');
  const catalog = await (await request.get('/api/v1/model-catalog')).json();
  await request.put('/api/v1/model-defaults', {
    data: { modelProfileId: 'p0', expectedRevision: catalog.revision },
  });
  await page.getByRole('button', { name: '保存修改', exact: true }).click();
  await expect(page.getByRole('dialog').getByRole('alert')).toContainText('配置已被其他操作更新');
  await expect(page.getByLabel('显示名称')).toHaveValue('未保存的新名称');
  await page.getByRole('button', { name: '关闭对话框' }).click();
  await page.reload();
  await expect(page.getByText('教学问答模型', { exact: true })).toBeVisible();
  for (const width of [1440, 1024, 390]) {
    await page.setViewportSize({ width, height: 900 });
    await page.screenshot({ path: info.outputPath(`models-${width}.png`) });
    expect((await page.locator('.app-header').boundingBox())!.y).toBeGreaterThanOrEqual(0);
    if (width === 390) expect((await page.locator('.brand').boundingBox())!.y).toBeGreaterThanOrEqual(0);
    else await expect(page.locator('.sidebar-brand')).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  }
});
