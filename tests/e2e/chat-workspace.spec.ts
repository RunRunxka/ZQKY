import { test, expect } from '@playwright/test';

/**
 * S3 结果工作区与消息操作 e2e（全部在模拟模式与本地目录上执行）：
 * 1. S3 出口组合回归：工具(MCP)→追问→同轮续写→产物→下载→刷新恢复不重放；
 * 2. 多标签工作区：活动主页常驻、产物标签打开/切换/关闭回退（对照参考 SessionViewerPanel）；
 * 3. 工作区宽度拖动（400–960 钳制）+ localStorage 持久化 + 220ms 展开动画（M-artifact）；
 * 4. 来源与上下文（引用/来源定位落点）与用户消息操作（复制/复用）。
 */

const SEED_EXTENSIONS = [
  {
    id: 'm1',
    kind: 'mcp',
    name: '演示检索',
    description: '本地演示 MCP',
    content: '',
    enabled: true,
  },
  {
    id: 's1',
    kind: 'skill',
    name: '提问技能',
    description: '本地演示技能',
    content: '',
    enabled: true,
  },
];

function seedExtensions(page: import('@playwright/test').Page) {
  return page.addInitScript(
    ({ seed }) => {
      window.localStorage.setItem('zqky.replica.extensions.v1', JSON.stringify(seed));
    },
    { seed: SEED_EXTENSIONS },
  );
}

async function switchToMock(page: import('@playwright/test').Page) {
  const textarea = page.getByRole('textbox', { name: '输入问题' });
  await textarea.waitFor({ state: 'visible', timeout: 15000 });
  await page.getByRole('button', { name: '模拟', exact: true }).click();
  return textarea;
}

async function chooseCapability(page: import('@playwright/test').Page, label: string) {
  await page.getByRole('button', { name: /选择业务能力，当前/ }).click();
  await page
    .getByRole('dialog', { name: '选择业务能力' })
    .getByRole('button', { name: new RegExp('^' + label) })
    .click();
}

async function confirmQuizTopic(page: import('@playwright/test').Page, topic: string) {
  await page.getByRole('button', { name: '先确认能力配置' }).click();
  const card = page.locator('.chat-cap-config');
  await card.getByLabel('出题主题').fill(topic);
  await card.getByRole('button', { name: '确认', exact: true }).click();
  await expect(card.getByText('已确认').first()).toBeVisible();
}

test('S3 出口组合：工具→追问→同轮续写→产物→下载→刷新恢复', async ({ page }, testInfo) => {
  await seedExtensions(page);
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  await chooseCapability(page, '智能出题');
  await confirmQuizTopic(page, '光合作用');
  // 布防追问 + 选择一个 MCP：本轮应为 工具→追问→续写→产物 的组合
  await page.getByRole('button', { name: '模拟追问' }).click();
  await page.getByRole('button', { name: '选择本轮扩展（MCP 与技能）' }).click();
  const extPanel = page.getByRole('dialog', { name: '选择本轮扩展' });
  await extPanel.getByRole('button', { name: /选择MCP 演示检索|选择 MCP 演示检索/ }).click();
  await page.keyboard.press('Escape');

  await textarea.fill('组合流程验证');
  await page.getByRole('button', { name: '发送', exact: true }).click();

  // 工具卡完成（MCP 模拟调用）
  const toolCard = page.locator('.chat-tool-card').first();
  await expect(toolCard).toContainText('演示检索', { timeout: 15000 });
  await expect(toolCard).toContainText('完成');

  // 同轮追问卡：回答后同 sessionId/turnId 续写
  const askCard = page.locator('.chat-ask-card').first();
  await expect(askCard).toContainText('希望结果侧重哪个方向', { timeout: 15000 });
  await askCard.getByRole('button', { name: /侧重解析/ }).click();
  await askCard.getByRole('button', { name: '提交', exact: true }).click();
  const bubble = page.locator('.chat-bubble.assistant').last();
  await expect(bubble).toContainText('已记录产出侧重', { timeout: 15000 });

  // 产物 chip → 打开工作区标签 → 下载真实内容
  const chip = page.getByRole('button', { name: /出题结果（模拟）/ }).first();
  await expect(chip).toBeVisible({ timeout: 15000 });
  await chip.click();
  const workspace = page.locator('.chat-workspace');
  await expect(workspace).toBeVisible();
  await expect(workspace).toContainText('参考答案');
  const [download] = await Promise.all([
    page.waitForEvent('download'),
    workspace.getByRole('button', { name: /下载 出题结果（模拟）\.md/ }).click(),
  ]);
  expect(download.suggestedFilename()).toBe('出题结果（模拟）.md');
  await testInfo.attach('s3-combo-download.txt', {
    body: `download filename: ${download.suggestedFilename()}`,
    contentType: 'text/plain',
  });

  // 等轮次结束后刷新：会话与产物持久化，恢复不重放
  await expect(page.getByRole('button', { name: '发送', exact: true })).toBeVisible({
    timeout: 15000,
  });
  await page.reload();
  await switchToMock(page);
  const restoredChip = page.getByRole('button', { name: /出题结果（模拟）/ }).first();
  await expect(restoredChip).toBeVisible({ timeout: 15000 });
  await restoredChip.click();
  await expect(page.locator('.chat-workspace')).toContainText('参考答案');
  await expect(page.getByRole('button', { name: '停止', exact: true })).toHaveCount(0);
});

test('多标签工作区：活动主页常驻，产物标签打开/切换/关闭回退', async ({ page }) => {
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  await chooseCapability(page, '智能出题');
  await confirmQuizTopic(page, '主题一');
  await textarea.fill('第一轮出题');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(page.getByRole('button', { name: /出题结果（模拟）/ }).first()).toBeVisible({
    timeout: 15000,
  });

  // 第二轮换能力（可视化），确认后发送
  // 轮次结束信号：停止按钮消失（输入已清空时发送按钮保持禁用是正常状态，不能作信号）
  await expect(page.getByRole('button', { name: '停止', exact: true })).toHaveCount(0, {
    timeout: 15000,
  });
  await chooseCapability(page, '可视化');
  await page.getByRole('button', { name: '先确认能力配置' }).click();
  const visCard = page.locator('.chat-cap-config');
  await visCard.getByRole('button', { name: '确认', exact: true }).click();
  await textarea.fill('第二轮可视化');
  await page.getByRole('button', { name: '发送', exact: true }).click();

  const tabs = page.locator('.chat-workspace-tabs .chat-workspace-tab');
  // 打开第一个产物（出题）
  await page
    .getByRole('button', { name: /出题结果（模拟）/ })
    .first()
    .click();
  const workspace = page.locator('.chat-workspace');
  await expect(workspace.getByRole('tab', { selected: true })).toContainText('出题结果（模拟）');
  // 打开第二个产物（可视化）→ 两个标签 + SVG 预览
  // （SVG 走 data-URL <img> 安全渲染，"模拟图表"在图片内，不作为 DOM 文本断言）
  await page
    .getByRole('button', { name: /可视化结果（模拟）/ })
    .first()
    .click();
  await expect(tabs).toHaveCount(2);
  const visImg = workspace.locator('.chat-artifact-preview-body img[alt="可视化结果（模拟）"]');
  await expect(visImg).toBeVisible();
  // 活动主页标签切换回去（预览与 img 一并消失，主页显示会话信息）
  await workspace.getByRole('tab', { name: '活动' }).click();
  await expect(visImg).toHaveCount(0);
  await expect(workspace.locator('.chat-workspace-body')).toContainText('本会话');
  // 再切到出题标签
  await tabs.filter({ hasText: '出题结果（模拟）' }).first().click();
  await expect(workspace.locator('.chat-artifact-preview-body')).toContainText('参考答案');
  // 关闭当前标签：回退到相邻标签（可视化）
  await page.getByRole('button', { name: '关闭标签 出题结果（模拟）' }).first().click();
  await expect(tabs).toHaveCount(1);
  await expect(visImg).toBeVisible();
  // 关闭最后一个标签：回到活动主页
  await page.getByRole('button', { name: '关闭标签 可视化结果（模拟）' }).first().click();
  await expect(tabs).toHaveCount(0);
  // 会话信息在活动主页可见（InfoPanel）
  await expect(page.locator('.chat-info')).toContainText('本会话');
});

test('工作区宽度拖动、持久化与 220ms 展开动画', async ({ page }, testInfo) => {
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  await textarea.fill('宽度验证');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await page.getByRole('button', { name: '会话详情' }).click();
  const workspace = page.locator('.chat-workspace');
  await expect(workspace).toBeVisible();

  // M-artifact：220ms 展开动画（进出场，同参考 ANIM_MS）
  const anim = await workspace.evaluate((node) => {
    const cs = getComputedStyle(node);
    return { name: cs.animationName, duration: cs.animationDuration };
  });
  expect(anim.name).toBe('chat-home-viewer');
  expect(anim.duration).toBe('0.22s');

  // 拖动左缘把手：宽度写入 CSS var 并钳制在 400–960
  const handle = page.locator('.chat-workspace-resize');
  // 指定主页为整幅滑入；拖拽从动画结束后的真实边缘开始。
  await expect(workspace).toHaveCSS('transform', 'none');
  const box = await handle.boundingBox();
  expect(box).not.toBeNull();
  const startX = box!.x + box!.width / 2;
  const startY = box!.y + box!.height / 2;
  await page.mouse.move(startX, startY);
  await page.mouse.down();
  // 目标宽度 700px → 把手 x = 1440 - 700 = 740
  await page.mouse.move(1440 - 700, startY, { steps: 8 });
  await page.mouse.up();
  // getPropertyValue 返回 "700px"——用 parseFloat 提取数值（Number() 会得到 NaN）
  const widthAfterDrag = await page.evaluate(() =>
    parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--viewer-width')),
  );
  expect(widthAfterDrag).toBe(700);
  await testInfo.attach('s3-width-drag.txt', {
    body: `--viewer-width after drag: ${widthAfterDrag}`,
    contentType: 'text/plain',
  });

  // 持久化：刷新后恢复拖动宽度（目标自己的键 zhiqikeyuan:viewer-width）
  await page.reload();
  await switchToMock(page);
  await page.getByRole('button', { name: '会话详情' }).click();
  const widthAfterReload = await page.evaluate(() =>
    parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--viewer-width')),
  );
  expect(widthAfterReload).toBe(700);
  await expect(page.locator('.chat-workspace')).toHaveCSS('transform', 'none');

  // 越界钳制：拖到极左 → 上限 960（1440*0.7=1008 软上限不触发，硬上限 960 生效）
  const box2 = await page.locator('.chat-workspace-resize').boundingBox();
  await page.mouse.move(box2!.x + box2!.width / 2, box2!.y + box2!.height / 2);
  await page.mouse.down();
  await page.mouse.move(10, box2!.y + box2!.height / 2, { steps: 6 });
  await page.mouse.up();
  const widthClamped = await page.evaluate(() =>
    parseFloat(getComputedStyle(document.documentElement).getPropertyValue('--viewer-width')),
  );
  expect(widthClamped).toBe(960);
});

test('来源与上下文块 + 用户消息操作（复制/复用）', async ({ page }) => {
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  // 载入演示人设并选择（会话级）
  await page.getByRole('button', { name: '添加文件与上下文' }).click();
  const menu = page.getByRole('dialog', { name: '添加文件与上下文' });
  await menu.getByRole('button', { name: '载入演示数据', exact: true }).first().click();
  await menu.getByRole('button', { name: /耐心的小学老师/ }).click();
  await menu.press('Escape');
  await expect(page.locator('.chat-ref-tree')).toContainText('耐心的小学老师');

  await textarea.fill('来源块验证');
  await page.getByRole('button', { name: '发送', exact: true }).click();
  await expect(page.locator('.chat-bubble.assistant').last()).toContainText('【模拟回复】', {
    timeout: 15000,
  });

  // 来源与上下文（引用/来源定位落点）：展开可见角色条目与如实说明
  const sources = page.locator('.chat-sources').first();
  await expect(sources).toContainText('来源与上下文（1）');
  await sources.locator('summary').click();
  await expect(sources).toContainText('角色 · 耐心的小学老师');
  await expect(sources).toContainText('演示目录');

  // 用户消息操作：复用此提问到输入框
  const userRow = page.locator('.chat-row.user').first();
  await userRow.getByRole('button', { name: '复用此提问到输入框' }).click();
  await expect(page.getByRole('textbox', { name: '输入问题' })).toHaveValue('来源块验证');
});
