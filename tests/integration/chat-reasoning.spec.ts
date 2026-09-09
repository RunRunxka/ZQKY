import { test, expect } from '@playwright/test';

for (const model of ['教学问答模型', 'Responses 模型', 'Anthropic 模型']) {
  test(`${model}：推理先显示，正文出现后折叠，公式与恢复正常`, async ({ page, request }, info) => {
    await page.goto('/chat');
    await page.getByRole('button', { name: '选择模型', exact: true }).click();
    await page.getByRole('dialog').getByRole('button').filter({ hasText: model }).click();
    await page.getByRole('textbox', { name: '输入问题' }).fill('推理验收');
    await page.getByRole('button', { name: '发送', exact: true }).click();
    const toggle = page.getByRole('button', { name: '推理过程' });
    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
    await expect(page.getByRole('region', { name: '推理内容' })).toContainText('先分析公式');
      await expect(page.locator('.chat-reasoning-body .katex')).toBeVisible();
      await expect(page.locator('.chat-reasoning-fold')).toHaveCSS('opacity', '1');
    expect((await (await request.get('http://127.0.0.1:8002/stats')).json()).first).toBeNull();
    await page.screenshot({ path: info.outputPath('reasoning-streaming.png') });
    await request.get('http://127.0.0.1:8002/answer');
    await expect(page.getByText('第一段中文已经到达。', { exact: true })).toBeVisible();
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
    expect((await (await request.get('http://127.0.0.1:8002/stats')).json()).last).toBeNull();
    await expect(page.locator('.chat-bubble.assistant > .answer-markdown .katex')).toHaveCount(2);
    await toggle.click();
    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
    await request.get('http://127.0.0.1:8002/release');
    await expect(page.getByRole('button', { name: '发送', exact: true })).toBeVisible();
    await expect(toggle).toHaveAttribute('aria-expanded', 'true');
    await page.reload();
    await expect(toggle).toHaveAttribute('aria-expanded', 'false');
      await toggle.click();
      await expect(page.getByRole('region', { name: '推理内容' })).toContainText('先分析公式');
      await expect(page.locator('.chat-reasoning-fold')).toHaveCSS('opacity', '1');
    await page.setViewportSize({ width: 390, height: 844 });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
    await page.screenshot({ path: info.outputPath('reasoning-restored-mobile.png') });
  });
}
