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
/**
 * R-15：本用例原用 contract-v1 之前的设置页定位（`.connection-group` + 卡片上的
 * 「从服务获取模型」/`.managed-model`/「设为默认」/「编辑模型 X」）。当前设置页是
 * 连接卡片 → 详情弹窗 → 嵌套发现弹窗 → 独立「默认模型」分区，这里按新结构重写定位，
 * 每个断言的意图不变；发现弹窗与详情弹窗会同时存在，定位一律按标题/名称收窄。
 */
test('模型发现追加、默认模型同步、表单冲突保留', async ({ page, request }, info) => {
  await page.goto('/settings');
  await page.getByRole('button', { name: '打开 教学模型服务 的详情' }).click();
  const detail = page.getByRole('dialog', { name: '教学模型服务' });
  await expect(detail).toBeVisible();

  // 意图 1：发现列表只追加——已添加的不可重复勾选，未添加的仍可选
  await detail.getByRole('button', { name: '从服务获取' }).click();
  const discovery = page.getByRole('dialog', { name: '从服务获取模型' });
  await expect(discovery).toBeVisible();
  await expect(discovery.getByRole('checkbox', { name: 'teaching-alpha 已添加' })).toBeDisabled();
  await expect(discovery.getByRole('checkbox', { name: 'teaching-beta' })).toBeEnabled();

  // 意图 2：勾选一个 → 添加 → 添加成功（列表把该项标为已添加且不可重复选）
  await discovery.getByRole('checkbox', { name: 'teaching-beta' }).check();
  await discovery.getByRole('button', { name: '添加所选 1 个' }).click();
  await expect(discovery.getByRole('checkbox', { name: 'teaching-beta 已添加' })).toBeChecked();
  await expect(discovery.getByRole('checkbox', { name: 'teaching-beta 已添加' })).toBeDisabled();
  // 新 UI 的发现弹窗在添加成功后保持打开（便于继续追加），显式「完成」后关闭；详情仍在
  await discovery.getByRole('button', { name: '完成' }).click();
  await expect(page.getByRole('dialog', { name: '从服务获取模型' })).toBeHidden();
  await expect(detail).toBeVisible();
  await detail.getByRole('button', { name: '关闭对话框' }).click();
  await expect(detail).toBeHidden();

  // 意图 3：把该模型设为默认 → 独立「默认模型」分区显示它被选中
  await page.getByRole('button', { name: '默认模型', exact: true }).click();
  await expect(page.getByRole('heading', { name: '全局默认问答模型' })).toBeVisible();
  const defaultTrigger = page.getByRole('button', { name: '选择模型' });
  await expect(defaultTrigger).toContainText('教学问答模型');
  await defaultTrigger.click();
  await page
    .getByRole('dialog', { name: '选择问答模型' })
    .getByRole('button', { name: /teaching-beta/ })
    .click();
  await expect(defaultTrigger).toContainText('teaching-beta');
  // 默认状态的第二处可见表达：详情模型行从「用于问答」按钮变为已选标记
  await page.getByRole('button', { name: '问答模型', exact: true }).click();
  await page.getByRole('button', { name: '打开 教学模型服务 的详情' }).click();
  const detailAgain = page.getByRole('dialog', { name: '教学模型服务' });
  const betaRow = detailAgain.locator('.detail-model').filter({ hasText: 'teaching-beta' });
  await expect(betaRow.getByText('用于问答', { exact: true })).toBeVisible();
  await expect(
    detailAgain
      .locator('.detail-model')
      .filter({ hasText: '教学问答模型' })
      .getByRole('button', { name: '用于问答' }),
  ).toBeVisible();

  // 意图 4：编辑该模型 → 改显示名称期间外部写入制造 revision 冲突 → 报错但保留输入
  await betaRow.getByRole('button', { name: '编辑 teaching-beta' }).click();
  const editor = page.getByRole('dialog', { name: '编辑模型' });
  await editor.getByLabel('显示名称').fill('未保存的新名称');
  const catalog = await (await request.get('/api/v1/model-catalog')).json();
  const conflicting = await request.put('/api/v1/model-defaults', {
    data: { modelProfileId: 'p0', expectedRevision: catalog.revision },
  });
  expect(conflicting.ok()).toBe(true);
  await editor.getByRole('button', { name: '保存修改', exact: true }).click();
  await expect(editor.getByRole('alert')).toContainText('配置已被其他操作更新');
  await expect(editor.getByLabel('显示名称')).toHaveValue('未保存的新名称');

  // 意图 5：逐层关闭并刷新后，服务端状态与这次失败保存无关
  await editor.getByRole('button', { name: '关闭对话框' }).click();
  await expect(editor).toBeHidden();
  await expect(detailAgain).toBeVisible();
  await detailAgain.getByRole('button', { name: '关闭对话框' }).click();
  await expect(detailAgain).toBeHidden();
  await page.reload();
  await expect(page.getByText('当前使用 · 教学问答模型')).toBeVisible();
  await page.getByRole('button', { name: '打开 教学模型服务 的详情' }).click();
  const reloaded = page.getByRole('dialog', { name: '教学模型服务' });
  await expect(reloaded.getByText('教学问答模型', { exact: true })).toBeVisible();
  await expect(reloaded.getByText('teaching-beta', { exact: true }).first()).toBeVisible();
  await expect(reloaded.getByText('未保存的新名称')).toHaveCount(0);
  await reloaded.getByRole('button', { name: '关闭对话框' }).click();
  await expect(reloaded).toBeHidden();
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
