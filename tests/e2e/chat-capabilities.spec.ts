import { test, expect } from '@playwright/test';

/**
 * S4 逐能力模拟闭环 e2e（全部在模拟模式与本地数据上执行）：
 * 1. deep_solve：planning→reasoning→writing 阶段序列 + 结构化答案正文；
 * 2. deep_question：quiz 产物作答反馈（本地判定）+ 保存到题库（space-store）；
 * 3. deep_research：大纲确认卡→检索→report 产物（引用定位）+ 保存到笔记；
 * 4. visualize 数学动画路由：六阶段 + 演示媒体如实标识（不假装执行 Manim）。
 */

async function switchToMock(page: import('@playwright/test').Page) {
  const textarea = page.getByRole('textbox', { name: '输入问题' });
  await textarea.waitFor({ state: 'visible', timeout: 15000 });
  await page.getByRole('button', { name: '模拟', exact: true }).click();
  return textarea;
}

async function chooseCapability(page: import('@playwright/test').Page, label: string) {
  await page.getByRole('button', { name: /选择业务能力，当前/ }).click();
  const dialog = page.getByRole('dialog', { name: '选择业务能力' });
  const primary = dialog.getByRole('button', { name: new RegExp('^' + label) });
  if ((await primary.count()) > 0) {
    await primary.first().click();
    return;
  }
  // 次要能力收进“更多能力”飞出层（悬停展开——点击会 toggle 关闭，同参考交互）
  await dialog.getByRole('button', { name: /更多能力/ }).hover();
  await dialog.getByRole('button', { name: new RegExp('^' + label) }).last().click();
}

async function waitTurnEnd(page: import('@playwright/test').Page) {
  await expect(page.getByRole('button', { name: '停止', exact: true })).toHaveCount(0, {
    timeout: 20000,
  });
}

test('deep_solve：planning→reasoning→writing 阶段序列与结构化答案', async ({ page }) => {
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  await chooseCapability(page, '深度求解');
  await textarea.fill('解一道二次函数题');
  await page.getByRole('button', { name: '发送', exact: true }).click();

  // 阶段序列按参考 manifest 顺序出现
  for (const stage of ['规划解题路径', '逐步推理', '组织答案']) {
    await expect(page.locator('.chat-stage', { hasText: stage }).first()).toBeVisible({
      timeout: 15000,
    });
  }
  // 推理过程独立呈现（不是正文）+ 正文结构化答案
  await expect(page.locator('.chat-bubble.assistant').last()).toContainText(
    '深度求解（本地演示）',
    { timeout: 15000 },
  );
  await expect(page.locator('.chat-bubble.assistant').last()).toContainText('解题步骤');
  await waitTurnEnd(page);
});

test('deep_question：quiz 产物作答反馈与保存到题库', async ({ page }) => {
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  await chooseCapability(page, '智能出题');
  await page.getByRole('button', { name: '先确认能力配置' }).click();
  const card = page.locator('.chat-cap-config');
  await card.getByLabel('出题主题').fill('光合作用');
  await card.getByRole('button', { name: '确认', exact: true }).click();
  await expect(card.getByText('已确认').first()).toBeVisible();

  await textarea.fill('出题验证');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  const chip = page.getByRole('button', { name: /出题结果（模拟）/ }).first();
  await expect(chip).toBeVisible({ timeout: 20000 });
  await waitTurnEnd(page);
  await chip.click();

  const workspace = page.locator('.chat-workspace');
  const quizView = workspace.locator('.chat-quiz-view');
  await expect(quizView).toBeVisible();
  await expect(quizView).toContainText('共 3 题（主题：光合作用）');

  // 选择题：点选正确项 → 本地判定为正确；错误项 → 判定为错误
  const firstItem = quizView.locator('.chat-quiz-item').first();
  await firstItem.getByRole('button', { name: /^A\./ }).click();
  await expect(firstItem.locator('.chat-quiz-verdict')).toContainText('回答正确');
  await expect(firstItem.locator('.chat-quiz-explain')).toContainText('解析');

  // 保存到题库：写入 space-store（S5 业务页同一仓储），幂等语义提示
  await quizView.getByRole('button', { name: /保存到题库/ }).click();
  await expect(quizView.getByRole('button', { name: /已保存到题库（新增 3 题）/ })).toBeVisible();
  const bank = await page.evaluate(() =>
    JSON.parse(window.localStorage.getItem('zhiqikeyuan:quiz-bank') ?? '[]'),
  );
  expect(bank).toHaveLength(3);
  expect(bank[0]).toMatchObject({ topic: '光合作用', questionType: 'choice' });
});

test('deep_research：大纲确认→检索→报告产物与保存到笔记', async ({ page }) => {
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  await chooseCapability(page, '深度研究');
  await page.getByRole('button', { name: '先确认能力配置' }).click();
  const card = page.locator('.chat-cap-config');
  await page.getByRole('combobox', { name: '产出类型' }).selectOption('report');
  await page.getByRole('combobox', { name: '研究深度' }).selectOption('standard');
  await card.getByRole('button', { name: '确认', exact: true }).click();
  await expect(card.getByText('已确认').first()).toBeVisible();

  await textarea.fill('研究光合作用');
  await page.getByRole('button', { name: '发送', exact: true }).click();

  // 两段式：先出大纲确认卡
  const outlineCard = page.locator('.chat-ask-card').first();
  await expect(outlineCard).toContainText('研究大纲', { timeout: 20000 });
  await outlineCard.getByRole('button', { name: /确认大纲，按此执行/ }).click();
  await outlineCard.getByRole('button', { name: '提交', exact: true }).click();

  // 检索与撰写阶段可见；报告产物带引用
  await expect(page.locator('.chat-stage', { hasText: '逐题检索演示资料' }).first()).toBeVisible({
    timeout: 15000,
  });
  const chip = page.getByRole('button', { name: /研究报告（模拟）/ }).first();
  await expect(chip).toBeVisible({ timeout: 20000 });
  await waitTurnEnd(page);
  await chip.click();

  const workspace = page.locator('.chat-workspace');
  const reportView = workspace.locator('.chat-report-view');
  await expect(reportView).toBeVisible();
  await expect(reportView).toContainText('CIT-');
  // 保存到笔记 → space-store
  await reportView.getByRole('button', { name: /保存到笔记/ }).click();
  await expect(reportView.getByRole('button', { name: /已保存到笔记/ })).toBeVisible();
  const entries = await page.evaluate(() =>
    JSON.parse(window.localStorage.getItem('zhiqikeyuan:notebook-entries') ?? '[]'),
  );
  expect(entries).toHaveLength(1);
  expect(entries[0]).toMatchObject({ kind: 'research_report' });
});

test('visualize 数学动画路由：六阶段与演示媒体如实标识', async ({ page }) => {
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  await chooseCapability(page, '可视化');
  await page.getByRole('button', { name: '先确认能力配置' }).click();
  const card = page.locator('.chat-cap-config');
  await page.getByRole('combobox', { name: '渲染模式' }).selectOption('manim_video');
  await card.getByRole('button', { name: '确认', exact: true }).click();
  await expect(card.getByText('已确认').first()).toBeVisible();

  await textarea.fill('动画验证');
  await page.getByRole('button', { name: '发送', exact: true }).click();

  // 六阶段（对照参考 math_animator）
  for (const stage of ['概念分析', '分镜设计', '生成 Manim 代码', '渲染重试', '总结', '渲染输出']) {
    await expect(page.locator('.chat-stage', { hasText: stage }).first()).toBeVisible({
      timeout: 15000,
    });
  }
  const chip = page.getByRole('button', { name: /数学动画（模拟）/ }).first();
  await expect(chip).toBeVisible({ timeout: 20000 });
  await waitTurnEnd(page);
  await chip.click();
  const workspace = page.locator('.chat-workspace');
  await expect(workspace).toContainText('未真实执行');
  await expect(workspace).toContainText('不生成真实视频文件');
});
