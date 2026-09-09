import { test, expect } from '@playwright/test';

/**
 * S2 完整输入区 e2e：能力选择与配置门控、附件选取/移除/校验、
 * 语音未接入说明与演示转写、欢迎区→首次发送 650ms 宽度过渡、三视口布局证据。
 * 全部在模拟模式与本地目录上执行，不访问真实模型或外部服务。
 */

async function switchToMock(page: import('@playwright/test').Page) {
  const textarea = page.getByRole('textbox', { name: '输入问题' });
  await textarea.waitFor({ state: 'visible', timeout: 15000 });
  await page.getByRole('button', { name: '模拟', exact: true }).click();
  return textarea;
}

test('能力选择→配置门控→确认→发送：模拟回复复述冻结配置', async ({ page }) => {
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  // 选择“智能出题”
  await page.getByRole('button', { name: '选择业务能力，当前：对话' }).click();
  await page
    .getByRole('dialog', { name: '选择业务能力' })
    .getByRole('button', { name: /^智能出题/ })
    .click();
  // 配置未确认：发送按钮为 blocked 态，点击后打开右侧配置卡而非静默失败
  await textarea.fill('帮我出题复习');
  const send = page.getByRole('button', { name: '先确认能力配置' });
  await expect(send).toBeVisible();
  await send.click();
  const configCard = page.locator('.chat-cap-config');
  await expect(configCard).toBeVisible();
  await expect(configCard.getByText('必填')).toBeVisible();
  await expect(configCard.getByText(/出题主题不能为空/)).toBeVisible();
  // 修正配置 → 错误消失 → 确认
  await configCard.getByLabel('出题主题').fill('光合作用');
  await expect(configCard.getByText(/出题主题不能为空/)).toHaveCount(0);
  await configCard.getByRole('button', { name: '确认' }).click();
  await expect(configCard.getByText('已确认').first()).toBeVisible();
  // 发送 → 模拟回复复述冻结的能力配置
  await page.getByRole('button', { name: '发送' }).click();
  await expect(page.locator('.chat-bubble.assistant').last()).toContainText('【模拟回复】', {
    timeout: 15000,
  });
  await expect(page.locator('.chat-bubble.assistant').last()).toContainText('本轮能力：智能出题');
  await expect(page.locator('.chat-bubble.assistant').last()).toContainText('主题=光合作用');
  // S4：能力轮产物入口出现（QUIZ 标识）；过程增量仅在流式时显示（processNote 不持久）
  await expect(page.locator('.chat-bubble.assistant').last()).toContainText('出题结果（模拟）');
});

test('附件：选取显示卡片、可预览可移除，类型校验给出明确错误', async ({ page }) => {
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  // 选择附件：一个文本文件 + 一个 PNG（生成 1x1 像素）
  const png = Buffer.from(
    'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg==',
    'base64',
  );
  await page.setInputFiles('input[type="file"]', [
    { name: '教案.txt', mimeType: 'text/plain', buffer: Buffer.from('教案内容') },
    { name: '示意图.png', mimeType: 'image/png', buffer: png },
  ]);
  await expect(page.locator('.chat-attach-doc')).toContainText('教案.txt');
  await expect(page.locator('.chat-attach-thumb img')).toBeAttached();
  // 文本卡片点击 → 明确说明无解析服务，不伪装预览
  await page.locator('.chat-attach-doc').click();
  const previewDialog = page.locator('dialog.workspace-modal');
  await expect(previewDialog).toContainText('无文件解析服务', { timeout: 5000 });
  await previewDialog.getByRole('button', { name: '关闭对话框' }).click();
  // 类型不支持 → 明确错误（4s 自动清除，此处只验证出现）
  await page.setInputFiles('input[type="file"]', [
    { name: '恶意.xyz', mimeType: '', buffer: Buffer.from('x') },
  ]);
  await expect(page.locator('.chat-attach-error')).toContainText('不支持的文件类型：恶意.xyz');
  // 移除附件
  await page.locator('.chat-attach-card', { hasText: '教案.txt' }).hover();
  await page.locator('.chat-attach-card button[aria-label="移除附件 教案.txt"]').click();
  await expect(page.locator('.chat-attach-card')).toHaveCount(1);
  await textarea.fill('附件演示发送');
  await page.getByRole('button', { name: '发送' }).click();
  await expect(page.locator('.chat-bubble.assistant').last()).toContainText('附件 1 个', {
    timeout: 15000,
  });
  await expect(page.locator('.chat-bubble.assistant').last()).toContainText('示意图.png');
  await expect(page.locator('.chat-bubble.assistant').last()).toContainText('未读取文件内容');
});

test('语音入口：明确未接入状态与演示转写，不采集音频', async ({ page }) => {
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  await page.getByRole('button', { name: '语音输入（未接入，查看说明）' }).click();
  await expect(page.locator('.chat-voice-panel')).toContainText('语音输入 · 未接入');
  await page.getByRole('button', { name: '插入演示转写' }).click();
  await expect(textarea).toHaveValue(/演示转写/);
});

test('真实模式：能力菜单列出目录但非对话能力禁用并标注未接入', async ({ page }, testInfo) => {
  await page.route('**/api/v1/model-catalog', (route) =>
    route.fulfill({
      status: 503,
      contentType: 'application/json',
      body: JSON.stringify({ detail: 'review only; no provider' }),
    }),
  );
  await page.goto('/chat');
  const textarea = page.getByRole('textbox', { name: '输入问题' });
  await textarea.waitFor({ state: 'visible', timeout: 15000 });
  await page.getByRole('button', { name: '选择业务能力，当前：对话' }).click();
  const dialog = page.getByRole('dialog', { name: '选择业务能力' });
  await expect(dialog.getByRole('button', { name: /^对话/ })).toBeEnabled();
  const quiz = dialog.getByRole('button', { name: /^智能出题/ });
  await expect(quiz).toBeDisabled();
  await expect(dialog.getByText('真实服务未接入').first()).toBeVisible();
  await testInfo.attach('s2-real-mode-capability-menu.txt', {
    body: 'real mode capability menu: chat enabled, others disabled',
    contentType: 'text/plain',
  });
});

test('指定主页参考：首次发送保持 912px 输入区和按钮位置稳定', async ({ page }, testInfo) => {
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  const widthProbe = () =>
    page.evaluate(() => {
      const el = document.querySelector('.chat-composer-wrap')!;
      const style = getComputedStyle(el);
      return {
        maxWidth: style.maxWidth,
        transition: style.transitionDuration,
        easing: style.transitionTimingFunction,
        width: el.getBoundingClientRect().width,
      };
    });
  const before = await widthProbe();
  // 2026-09-09 用户改为指定 deeptutor-page 主页；其 composer 固定 912px，外层含 48px 留白。
  expect(before.maxWidth).toBe('960px');
  // 保留连续采样，验证发送期间不会发生旧的 768→960 横向跳位。
  await textarea.fill('过渡验证');
  await page.getByRole('button', { name: '发送' }).click();
  const seen: number[] = [];
  for (let i = 0; i < 20; i += 1) {
    seen.push((await widthProbe()).width);
    await page.waitForTimeout(40);
  }
  const after = await widthProbe();
  expect(after.maxWidth).toBe('960px');
  expect(
    seen.every((width) => Math.abs(width - before.width) < 1),
    `输入区应稳定，实际采样=${seen.join(',')}`,
  ).toBe(true);
  await expect(page.locator('.chat-composer')).toHaveCSS('border-radius', '27px');
  await expect(textarea).toHaveCSS('transition-duration', '0.15s');
  await testInfo.attach('s2-width-samples.txt', {
    body: seen.map((w, i) => `${i * 40}ms: ${Math.round(w)}`).join('\n'),
    contentType: 'text/plain',
  });
});

test('S3 结果工作区：出题轮产物 chip → 打开预览 → 下载真实内容 → 刷新恢复不重放', async ({
  page,
}, testInfo) => {
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  await page.getByRole('button', { name: '选择业务能力，当前：对话' }).click();
  await page
    .getByRole('dialog', { name: '选择业务能力' })
    .getByRole('button', { name: /^智能出题/ })
    .click();
  await textarea.fill('帮我出题');
  await page.getByRole('button', { name: '先确认能力配置' }).click();
  await page.locator('.chat-cap-config').getByLabel('出题主题').fill('光合作用');
  await page.locator('.chat-cap-config').getByRole('button', { name: '确认' }).click();
  await page.getByRole('button', { name: '发送' }).click();
  // 产物入口 chip 出现在消息内
  const chip = page.getByRole('button', { name: /出题结果（模拟）/ }).first();
  await expect(chip).toBeVisible({ timeout: 15000 });
  // 打开右侧结果工作区
  await chip.click();
  const panel = page.locator('.chat-artifact-panel');
  await expect(panel).toBeVisible();
  await expect(panel).toContainText('出题结果（模拟）');
  await expect(panel).toContainText('参考答案');
  // 下载使用真实已生成的本地内容
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    panel.getByRole('button', { name: /下载 出题结果（模拟）\.md/ }).click(),
  ]);
  expect(download.suggestedFilename()).toBe('出题结果（模拟）.md');
  await testInfo.attach('s3-artifact-download.txt', {
    body: `download filename: ${download.suggestedFilename()}`,
    contentType: 'text/plain',
  });
  await page.getByRole('button', { name: '关闭结果工作区' }).click();
  await expect(panel).toHaveCount(0);
  // 等轮次结束（run finally 已强制落盘）再刷新；流式中途刷新的取消语义由其他用例覆盖
  await expect(page.getByRole('button', { name: '发送' })).toBeVisible({ timeout: 15000 });
  // 刷新恢复：产物随会话持久化，不重放执行（刷新后模式回到真实，需重新切到模拟查看）
  await page.reload();
  await switchToMock(page);
  const restoredChip = page.getByRole('button', { name: /出题结果（模拟）/ }).first();
  await expect(restoredChip).toBeVisible({ timeout: 15000 });
  await restoredChip.click();
  await expect(page.locator('.chat-artifact-panel')).toContainText('参考答案');
  await expect(page.getByRole('button', { name: '停止' })).toHaveCount(0); // 无重放
});

const VIEWPORTS = [
  { name: '1440x900', width: 1440, height: 900 },
  { name: '1920x1080', width: 1920, height: 1080 },
  { name: '390x844', width: 390, height: 844 },
];

for (const viewport of VIEWPORTS) {
  test(`S2 输入区布局证据：${viewport.name}`, async ({ page }, testInfo) => {
    await page.setViewportSize({ width: viewport.width, height: viewport.height });
    await page.goto('/chat');
    const textarea = await switchToMock(page);
    await textarea.fill('布局证据');
    // 横向溢出检查（除 390 允许滚动容器内部滚动外，页面不得横向溢出）
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
    );
    expect(overflow, '页面不应横向溢出').toBeLessThanOrEqual(0);
    await page.screenshot({
      path: testInfo.outputDir + `/composer-s2-${viewport.name}.png`,
      fullPage: false,
    });
    await testInfo.attach(`composer-s2-${viewport.name}.png`, {
      path: testInfo.outputDir + `/composer-s2-${viewport.name}.png`,
    });
  });
}
