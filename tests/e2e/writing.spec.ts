import { test, expect } from '@playwright/test';

/**
 * S5-E 协同写作 + Whisper 密室回归：
 * 写作列表（新建空白/模板、删除）、编辑器（自动保存、选区 AI 修改流式预览/应用/撤销、
 * 版本快照与恢复）、whisper（房间创建、双席位、模拟流式回复、结束房间、危机引导卡）。
 * AI 修改与回复均为显式模拟并标注【模拟生成】/【模拟回复】。
 */

test('协同写作：新建、自动保存、AI 选区改写、应用/撤销与版本恢复', async ({ page }) => {
  await page.goto('/co-writer');
  await expect(page.getByRole('heading', { name: '协同写作' })).toBeVisible();
  await expect(page.getByText('还没有文稿')).toBeVisible();

  // 新建（带模板）
  await page.getByRole('button', { name: '新建文稿' }).click();
  const dialog = page.getByRole('dialog', { name: '新建文稿' });
  await dialog.getByLabel('标题').fill('分数教学文稿');
  await dialog.getByLabel(/教学设计示例模板/).check();
  await dialog.getByRole('button', { name: '创建' }).click();
  await expect(page).toHaveURL(/\/co-writer\/doc-/);
  await expect(page.getByRole('heading', { name: '分数教学文稿' })).toBeVisible();

  // 编辑 → 自动保存状态回到“已保存”
  const editor = page.getByLabel('文稿正文编辑区');
  await editor.fill('# 教学设计示例（模板）\n\n追加内容。');
  await expect(page.getByText('已保存', { exact: true })).toBeVisible({ timeout: 10000 });

  // 选区 AI 改写：全选正文 → 流式预览 → 应用 → 内容含模拟标注
  await page.getByLabel('文稿正文编辑区').press('ControlOrMeta+a');
  await page.getByRole('button', { name: '选区改写' }).click();
  const aiDialog = page.getByRole('dialog', { name: 'AI 改写' });
  await aiDialog.getByLabel(/指令/).fill('面向初中生');
  await aiDialog.getByRole('button', { name: '开始生成' }).click();
  const preview = page.getByRole('dialog', { name: 'AI 改写预览' }).getByLabel('AI 修改预览');
  await expect(preview).toContainText('【模拟生成】', { timeout: 15000 });
  await page.getByRole('dialog', { name: 'AI 改写预览' }).getByRole('button', { name: '应用' }).click();
  await expect(page.getByLabel('文稿正文编辑区')).toHaveValue(/【模拟生成】/);

  // 撤销恢复改写前内容
  await page.getByRole('button', { name: '撤销修改' }).click();
  await expect(page.getByLabel('文稿正文编辑区')).not.toHaveValue(/【模拟生成】/);

  // 版本：AI 应用前自动快照已在历史中；恢复最新手动状态
  await page.getByRole('button', { name: '版本历史' }).click();
  const versions = page.getByRole('dialog', { name: '版本历史' });
  await expect(versions.getByText(/改写前自动快照/)).toBeVisible();
  await versions.getByRole('button', { name: /恢复版本/ }).first().click();
  await expect(page.getByText('已保存', { exact: true })).toBeVisible({ timeout: 10000 });
});

test('协同写作：列表展示、删除确认与空态', async ({ page }) => {
  await page.goto('/co-writer');
  await page.getByRole('button', { name: '新建文稿' }).click();
  await page.getByRole('dialog', { name: '新建文稿' }).getByRole('button', { name: '创建' }).click();
  await expect(page).toHaveURL(/\/co-writer\/doc-/);
  await page.goto('/co-writer');
  await expect(page.locator('.space-session-card', { hasText: '未命名文稿' })).toBeVisible();
  page.once('dialog', (d) => void d.accept());
  await page.getByLabel('删除文稿 未命名文稿').click();
  await expect(page.getByText('还没有文稿')).toBeVisible();
});

test('whisper：创建房间、双席位模拟回复、结束房间与危机引导', async ({ page }) => {
  await page.goto('/whisper');
  await expect(page.getByRole('heading', { name: 'Whisper 密室' })).toBeVisible();
  await expect(page.getByText('还没有开启密室')).toBeVisible();

  await page.getByRole('button', { name: '开始密室' }).click();
  await expect(page.getByLabel('房间号')).toContainText('房间 room-');

  // 访客席发送 → 流式模拟回复落盘
  await page.getByLabel('密室消息输入').fill('你好，这一段我没看懂');
  await page.getByLabel('发送密室消息').click();
  await expect(page.getByLabel('密室消息').getByText(/【模拟回复】已收到访客席/)).toBeVisible({ timeout: 15000 });

  // 学员席分席独立
  await page.getByRole('tab', { name: '学员席' }).click();
  await expect(page.getByText('学员席暂无消息。发送第一条消息开始对话。')).toBeVisible();
  await page.getByLabel('密室消息输入').fill('学员侧提问');
  await page.getByLabel('发送密室消息').click();
  await expect(page.getByLabel('密室消息').getByText(/【模拟回复】已收到学员席/)).toBeVisible({ timeout: 15000 });

  // 结束房间：发送停用
  await page.getByRole('button', { name: '结束房间' }).click();
  await expect(page.getByText('本房间已结束，发送已停用')).toBeVisible();
  await expect(page.getByLabel('密室消息输入')).toBeDisabled();

  // 危机表述触发系统引导卡（新房间）
  await page.getByRole('button', { name: '新建房间' }).click();
  await page.getByLabel('密室消息输入').fill('我不想活了');
  await page.getByLabel('发送密室消息').click();
  await expect(page.getByLabel('密室消息').getByText(/【系统引导】/)).toBeVisible();
  await expect(page.getByLabel('密室消息').getByText(/12356/)).toBeVisible();
});
