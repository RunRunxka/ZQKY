import { test, expect } from '@playwright/test';

// 模拟对话闭环 e2e：不需要模型凭证与后端；模拟服务为本地脚本，数据与真实问答隔离。
const REPLY_FRAGMENT = '【模拟回复】';

// 本地模拟扩展目录种子：两个 MCP、一个技能（全部启用）
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
    id: 'm2',
    kind: 'mcp',
    name: '课程数据',
    description: '本地演示 MCP 2',
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

function seedExtensions(page: import('@playwright/test').Page, reducedMotion = false) {
  return page.addInitScript(
    ({ seed, motion }) => {
      window.localStorage.setItem('zqky.replica.extensions.v1', JSON.stringify(seed));
      if (motion) window.localStorage.setItem('zqky.motion', 'reduced');
    },
    { seed: SEED_EXTENSIONS, motion: reducedMotion },
  );
}

async function switchToMock(page: import('@playwright/test').Page) {
  const textarea = page.getByRole('textbox', { name: '输入问题' });
  await textarea.waitFor({ state: 'visible', timeout: 15000 });
  await page.getByRole('button', { name: '模拟', exact: true }).click();
  return textarea;
}

/** R6 布局边界证据：输入区、发送按钮与模式说明的几何信息 */
async function bounds(page: import('@playwright/test').Page) {
  return page.evaluate(() => {
    const rect = (selector: string) => {
      const node = document.querySelector(selector);
      if (!node) return null;
      const r = node.getBoundingClientRect();
      return { left: r.left, right: r.right, width: r.width, height: r.height };
    };
    return {
      composer: rect('.chat-composer'),
      send: rect('.chat-send-button'),
      modeLabel: rect('.chat-mode-chip'),
      viewport: innerWidth,
    };
  });
}

/** R7 焦点证据：当前焦点是否落在收起/展开的工具详情内 */
async function focusEvidence(page: import('@playwright/test').Page) {
  return page.evaluate(() => ({
    hiddenDetailHasFocus: Boolean(document.activeElement?.closest('.chat-tool-detail:not(.open)')),
    openDetailHasFocus: Boolean(document.activeElement?.closest('.chat-tool-detail.open')),
    focused: document.activeElement?.className ?? '',
  }));
}

test('模拟模式发送→流式→完成，会话与真实问答隔离且刷新后恢复', async ({ page }, testInfo) => {
  await page.goto('/chat');
  const textarea = page.getByRole('textbox', { name: '输入问题' });
  await textarea.waitFor({ state: 'visible', timeout: 15000 });

  // 切到模拟模式：横幅出现且模型选择器被替换为模拟标识
  await page.getByRole('button', { name: '模拟', exact: true }).click();
  await expect(page.getByText(/模拟模式：回复由本地脚本生成/)).toBeVisible();
  await expect(page.getByText('模拟模式 · 不访问真实模型')).toBeVisible();

  // Shift+Enter 换行不发送，Enter 发送
  await textarea.fill('第一行');
  await textarea.press('Shift+Enter');
  await textarea.type('第二行');
  const draftAfterShiftEnter = await textarea.inputValue();
  expect(draftAfterShiftEnter).toContain('\n');
  await textarea.press('Enter');

  const reply = page.locator('.chat-bubble.assistant').last();
  await expect(reply).toContainText(REPLY_FRAGMENT, { timeout: 15000 });
  await expect(page.getByText('模拟模型 · 本地脚本').last()).toBeVisible();
  await expect(textarea).toHaveValue('');

  // 真实模式列表隔离：切回真实无会话，再切回模拟历史恢复
  await page.getByRole('button', { name: '真实', exact: true }).click();
  await expect(page.getByText('还没有历史会话。')).toBeVisible();
  await page.getByRole('button', { name: '模拟', exact: true }).click();
  await expect(page.locator('.chat-session-list li')).toHaveCount(1);

  // 刷新后模式回到真实（默认行为），再进模拟历史仍恢复
  await page.reload();
  await textarea.waitFor({ state: 'visible', timeout: 15000 });
  await expect(page.getByText('还没有历史会话。')).toBeVisible();
  await page.getByRole('button', { name: '模拟', exact: true }).click();
  await expect(page.locator('.chat-bubble.assistant').last()).toContainText(REPLY_FRAGMENT);
  await page.screenshot({ path: testInfo.outputPath('chat-mock-1440.png') });
});

test('连续发送不重复，停止后不再追加文本', async ({ page }) => {
  await page.goto('/chat');
  const textarea = page.getByRole('textbox', { name: '输入问题' });
  await textarea.waitFor({ state: 'visible', timeout: 15000 });
  await page.getByRole('button', { name: '模拟', exact: true }).click();

  await textarea.fill('问题一');
  await textarea.press('Enter');
  const stopButton = page.getByRole('button', { name: '停止' });
  await expect(stopButton).toBeVisible();
  // 生成中再次 Enter 不产生第二轮
  await textarea.fill('问题二');
  await textarea.press('Enter');
  await expect(page.locator('.chat-row.user')).toHaveCount(1);

  // force：S2 的 650ms 宽度过渡（对照参考）使按钮位置在过渡期间持续变化，
  // Playwright 的稳定性重试会让点击落到流结束之后——force 立即点击保持原验收语义
  // （生成中点击停止→内容冻结不再追加）。
  await stopButton.click({ force: true });
  const bubble = page.locator('.chat-bubble.assistant').last();
  await expect(bubble.getByText('已停止')).toBeVisible();
  const contentAfterStop = await bubble.textContent();
  await page.waitForTimeout(400);
  expect(await bubble.textContent()).toBe(contentAfterStop);
});

test('模拟失败给出明确错误并可重试成功', async ({ page }) => {
  await page.goto('/chat');
  const textarea = page.getByRole('textbox', { name: '输入问题' });
  await textarea.waitFor({ state: 'visible', timeout: 15000 });
  await page.getByRole('button', { name: '模拟', exact: true }).click();
  await page.getByRole('button', { name: '模拟一次失败' }).click();

  await textarea.fill('会失败的问题');
  await textarea.press('Enter');
  const errorBox = page.locator('.chat-error');
  await expect(errorBox).toContainText('MOCK_ERROR', { timeout: 15000 });
  await expect(errorBox).toContainText('可直接重试');

  // 重试（未再布防）→ 成功
  await errorBox.getByRole('button', { name: '重试' }).click();
  await expect(page.locator('.chat-bubble.assistant').last()).toContainText(REPLY_FRAGMENT, {
    timeout: 15000,
  });
  // 失败的尝试保留为“之前的尝试”
  await expect(page.getByText('之前的尝试 · 已保留')).toBeVisible();
});

test('生成中浏览器返回离开页面，回来后生成已取消且内容冻结', async ({ page }) => {
  // R1 浏览器回归：浏览器返回（popstate）既不触发 pagehide，也不经过侧栏 beforeNavigate，
  // 卸载清理必须取消生成并把会话冲正保存。
  await page.goto('/lesson-plans');
  await page.getByRole('button', { name: '学习问答', exact: true }).click();
  const textarea = page.getByRole('textbox', { name: '输入问题' });
  await textarea.waitFor({ state: 'visible', timeout: 15000 });
  await page.getByRole('button', { name: '模拟', exact: true }).click();
  await textarea.fill('返回测试的问题');
  await textarea.press('Enter');
  await expect(page.getByRole('button', { name: '停止' })).toBeVisible();
  await page.waitForTimeout(400); // 让模拟流输出若干分块

  await page.goBack();
  await expect(page).toHaveURL(/\/lesson-plans$/);
  await page.waitForTimeout(400); // 留给卸载清理的取消与保存

  // 返回聊天：会话已保存，消息已停止且不再继续追加
  await page.getByRole('button', { name: '学习问答', exact: true }).click();
  await textarea.waitFor({ state: 'visible', timeout: 15000 });
  await page.getByRole('button', { name: '模拟', exact: true }).click();
  const bubble = page.locator('.chat-bubble.assistant').last();
  await expect(bubble).toBeVisible({ timeout: 15000 });
  await expect(bubble.getByText('已停止')).toBeVisible();
  const frozen = await bubble.textContent();
  await page.waitForTimeout(600);
  expect(await bubble.textContent()).toBe(frozen);
  await expect(page.locator('.chat-session-list li')).toHaveCount(1);
});

test('扩展选择→发送→工具过程卡片→展开稳定→刷新恢复不重放', async ({ page }) => {
  await seedExtensions(page);
  // 真实模式默认：明确显示扩展尚未接入
  await page.goto('/chat');
  await expect(page.getByText('扩展 · 真实模式尚未接入')).toBeVisible();

  const textarea = await switchToMock(page);
  const trigger = page.getByRole('button', { name: '选择本轮扩展（MCP 与技能）' });
  await trigger.click();
  const panel = page.getByRole('dialog', { name: '选择本轮扩展' });
  await expect(panel).toBeVisible();
  await expect(page.getByText('MCP（模拟工具调用）')).toBeVisible();
  await expect(page.getByText('Skills（技能上下文）')).toBeVisible();
  await page.getByRole('button', { name: '选择MCP 演示检索' }).click();
  await page.getByRole('button', { name: '选择MCP 课程数据' }).click();
  await page.getByRole('button', { name: '选择技能 提问技能' }).click();
  await expect(page.locator('.chat-ext-chip')).toHaveCount(3);
  await page.keyboard.press('Escape'); // 键盘关闭并恢复焦点
  await expect(panel).toBeHidden();
  await expect(trigger).toBeFocused();

  await textarea.fill('带扩展的问题');
  await textarea.press('Enter');
  const bubble = page.locator('.chat-bubble.assistant').last();
  await expect(bubble.locator('.chat-tool-card')).toHaveCount(3, { timeout: 15000 });
  await expect(bubble.locator('.chat-tool-card.done')).toHaveCount(3);
  await expect(bubble.getByText('技能上下文已加载（模拟）')).toBeVisible();
  await expect(bubble.getByText('模拟工具调用 · 未连接真实服务').first()).toBeVisible();
  await expect(bubble).toContainText(REPLY_FRAGMENT);

  // 手动展开：正文流式增量不重置手动展开/收起状态
  await bubble.locator('.chat-tool-head').first().click();
  await expect(bubble.locator('.chat-tool-detail.open')).toHaveCount(1);
  await page.waitForTimeout(400);
  await expect(bubble.locator('.chat-tool-detail.open')).toHaveCount(1);
  await bubble.locator('.chat-tool-head').first().click();
  await expect(bubble.locator('.chat-tool-detail.open')).toHaveCount(0);

  // 刷新恢复：卡片与状态还原，不重新执行
  await page.reload();
  const textarea2 = await switchToMock(page);
  await expect(textarea2).toBeEnabled();
  const restored = page.locator('.chat-bubble.assistant').last();
  await expect(restored.locator('.chat-tool-card')).toHaveCount(3, { timeout: 15000 });
  await expect(restored.locator('.chat-tool-card.running')).toHaveCount(0);
  await expect(restored.locator('.chat-tool-card.done')).toHaveCount(3);
});

test('模拟工具失败给出明确错误，可按原快照重试成功', async ({ page }) => {
  await seedExtensions(page);
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  const trigger = page.getByRole('button', { name: '选择本轮扩展（MCP 与技能）' });
  await trigger.click();
  await page.getByRole('button', { name: '选择MCP 演示检索' }).click();
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: '模拟一次失败' }).click();

  await textarea.fill('会失败的问题');
  await textarea.press('Enter');
  const bubble = page.locator('.chat-bubble.assistant').last();
  await expect(bubble.locator('.chat-tool-card.error')).toBeVisible({ timeout: 15000 });
  await expect(bubble.locator('.chat-tool-card.error')).toContainText('【模拟失败】');
  const errorBox = page.locator('.chat-error');
  await expect(errorBox).toContainText('MOCK_TOOL_ERROR');

  // 重试未再布防 → 成功；失败尝试的过程保留
  await errorBox.getByRole('button', { name: '重试' }).click();
  await expect(page.locator('.chat-bubble.assistant').last()).toContainText(REPLY_FRAGMENT, {
    timeout: 15000,
  });
  await expect(page.locator('.chat-tool-card.error').first()).toBeVisible();
  await expect(page.locator('.chat-tool-card.done').last()).toBeVisible();
});

test('工具执行中取消：运行中卡片全部收尾，不留“运行中”', async ({ page }) => {
  await seedExtensions(page);
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  const trigger = page.getByRole('button', { name: '选择本轮扩展（MCP 与技能）' });
  await trigger.click();
  await page.getByRole('button', { name: '选择MCP 演示检索' }).click();
  await page.getByRole('button', { name: '选择MCP 课程数据' }).click();
  await page.keyboard.press('Escape');

  await textarea.fill('执行中取消的问题');
  await textarea.press('Enter');
  await expect(page.locator('.chat-tool-card.running').first()).toBeVisible({
    timeout: 15000,
  });
  // 同上：650ms 宽度过渡期间按钮移动，force 立即点击，验收语义不变
  await page.getByRole('button', { name: '停止' }).click({ force: true });

  const bubble = page.locator('.chat-bubble.assistant').last();
  await expect(bubble.getByText('已停止')).toBeVisible();
  await expect(page.locator('.chat-tool-card.running')).toHaveCount(0);
  await expect(page.locator('.chat-tool-card.cancelled').first()).toBeVisible();

  // 刷新后仍保持收尾状态
  await page.reload();
  await switchToMock(page);
  await expect(page.locator('.chat-tool-card.running')).toHaveCount(0);
  await expect(page.locator('.chat-tool-card.cancelled').first()).toBeVisible();
});

test('减少动画 + 手机布局下的扩展闭环可用', async ({ page }, testInfo) => {
  await seedExtensions(page, true);
  await page.goto('/chat');
  await page.setViewportSize({ width: 390, height: 844 });
  const textarea = await switchToMock(page);
  const trigger = page.getByRole('button', { name: '选择本轮扩展（MCP 与技能）' });
  await trigger.click();
  const panel = page.getByRole('dialog', { name: '选择本轮扩展' });
  await expect(panel).toBeVisible();
  const box = await panel.boundingBox();
  expect(box?.width ?? 0).toBeLessThanOrEqual(390 * 0.9);
  await page.getByRole('button', { name: '选择MCP 演示检索' }).click();
  await page.getByRole('button', { name: '选择技能 提问技能' }).click();
  await page.keyboard.press('Escape');

  await textarea.fill('手机上带扩展的问题');
  await textarea.press('Enter');
  const bubble = page.locator('.chat-bubble.assistant').last();
  await expect(bubble.locator('.chat-tool-card')).toHaveCount(2, { timeout: 15000 });
  await expect(bubble.locator('.chat-tool-card.done')).toHaveCount(2);
  await expect(bubble).toContainText(REPLY_FRAGMENT);
  await page.screenshot({ path: testInfo.outputPath('chat-extensions-390.png') });
});

test('R6：390px 多扩展与长名称，输入区不溢出、控件可达', async ({ page }, testInfo) => {
  await page.addInitScript(() => {
    window.localStorage.setItem(
      'zqky.replica.extensions.v1',
      JSON.stringify([
        {
          id: 'm1',
          kind: 'mcp',
          name: '演示检索',
          description: '本地演示 MCP',
          content: '',
          enabled: true,
        },
        {
          id: 's2',
          kind: 'skill',
          name: '这是一个非常长的技能名称用于验证窄屏下已选扩展的换行与省略行为不会把发送按钮挤出输入区',
          description: '长名称技能',
          content: '',
          enabled: true,
        },
      ]),
    );
  });
  await page.goto('/chat');
  await page.setViewportSize({ width: 390, height: 844 });
  const textarea = await switchToMock(page);
  // 零扩展基线：输入区不出视口
  const zero = await bounds(page);
  expect(zero.composer.left).toBeGreaterThanOrEqual(0);
  expect(zero.send.right).toBeLessThanOrEqual(zero.composer.right + 1);

  await page.getByRole('button', { name: '选择本轮扩展（MCP 与技能）' }).click();
  await page.getByRole('button', { name: '选择MCP 演示检索' }).click();
  await page.getByRole('button', { name: /选择技能 这是一个非常长的技能名称/ }).click();
  await page.keyboard.press('Escape');
  await expect(page.locator('.chat-ext-chip')).toHaveCount(2);

  await textarea.fill('多扩展与长名称布局核验');
  await textarea.press('Enter');
  await expect(page.locator('.chat-tool-card.done')).toHaveCount(2, { timeout: 15000 });
  await expect(page.getByRole('button', { name: '停止', exact: true })).toHaveCount(0);

  const one = await bounds(page);
  expect.soft(one.composer.left).toBeGreaterThanOrEqual(0);
  expect.soft(one.send.right).toBeLessThanOrEqual(one.composer.right + 1);
  expect.soft(one.modeLabel.height).toBeLessThan(30); // 说明文字不竖排
  // 长名称 chip 的移除按钮可见可达（不因溢出被裁掉）
  await expect(page.locator('.chat-ext-chip').last().getByRole('button')).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('mobile-extensions-390.png') });
});

test('R7：收起详情 Tab 不进入隐藏内容，展开后可进入、收起焦点回头部', async ({ page }) => {
  await seedExtensions(page);
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  const trigger = page.getByRole('button', { name: '选择本轮扩展（MCP 与技能）' });
  await trigger.click();
  await page.getByRole('button', { name: '选择MCP 演示检索' }).click();
  await page.keyboard.press('Escape');
  await textarea.fill('请分析[示例文档](https://example.com/review)');
  await textarea.press('Enter');
  const card = page.locator('.chat-tool-card').first();
  await expect(card).toHaveClass(/done/, { timeout: 15000 });
  const head = card.locator('.chat-tool-head');
  await expect(head).toHaveAttribute('aria-expanded', 'false');
  await head.focus();
  await page.keyboard.press('Tab'); // 真实键盘：折叠态 Tab 不得进入不可见详情
  const collapsed = await focusEvidence(page);
  expect(collapsed.hiddenDetailHasFocus).toBe(false);

  // 展开后详情可进入（inert 移除）；再次收起后焦点回头部且详情移出可访问树
  await head.click();
  await expect(card.locator('.chat-tool-detail.open')).toBeVisible();
  await head.focus();
  await page.keyboard.press('Tab');
  const expanded = await focusEvidence(page);
  expect(expanded.hiddenDetailHasFocus).toBe(false);
  expect(expanded.openDetailHasFocus).toBe(true);
  await head.click();
  await expect(head).toBeFocused();
  await expect(card.locator('.chat-tool-detail.open')).toHaveCount(0);
  expect(await card.locator('.chat-tool-detail').getAttribute('inert')).not.toBeNull();
});

test('R8：菜单进出场动画与缓动参数，快速开关最终状态正确', async ({ page }, testInfo) => {
  await seedExtensions(page);
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  const trigger = page.getByRole('button', { name: '选择本轮扩展（MCP 与技能）' });
  await trigger.click();
  const panel = page.locator('.chat-ext-panel');
  await expect(panel).toBeVisible();
  await page.getByRole('button', { name: '选择MCP 演示检索' }).click(); // 后半段需要工具卡
  const enter = await panel.evaluate((node) => {
    const cs = getComputedStyle(node);
    return {
      name: cs.animationName,
      duration: cs.animationDuration,
      timing: cs.animationTimingFunction,
    };
  });
  expect(enter.name).toBe('chat-ext-pop');
  // 2026-09-09 指定主页参考：菜单入场 180ms，原有退场仍为 160ms。
  expect(enter.duration).toBe('0.18s');
  expect(enter.timing).toContain('0.16, 1, 0.3, 1'); // 弹出层缓动对齐原版 ChatComposer

  // 退场：第一帧仍挂载且播放 chat-ext-pop-out；用 Web Animations API 定格中间帧取证
  await page.waitForTimeout(250);
  await page.evaluate(() => {
    (document.querySelector('[aria-label="关闭扩展选择"]') as HTMLButtonElement).click();
  });
  await expect(panel).toHaveClass(/closing/);
  await page.evaluate(() => {
    const anim = document
      .getAnimations()
      .find((a) => (a as Animation).animationName === 'chat-ext-pop-out');
    if (anim) {
      anim.pause();
      anim.currentTime = 80;
    }
  });
  await page.screenshot({ path: testInfo.outputPath('ext-exit-mid.png') });
  const midExit = await panel.evaluate((node) => ({
    connected: node.isConnected,
    opacity: Number(getComputedStyle(node).opacity),
    inert: node.hasAttribute('inert'),
  }));
  expect(midExit.connected).toBe(true);
  expect(midExit.opacity).toBeGreaterThan(0);
  expect(midExit.opacity).toBeLessThan(1);
  expect(midExit.inert).toBe(true); // 退场期间不可聚焦

  // 中断：退场途中重新打开，最终状态正确
  await trigger.click();
  await expect(panel).toBeVisible();
  await expect(panel).not.toHaveClass(/closing/);
  await expect(page.getByRole('textbox', { name: '搜索扩展' })).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.locator('.chat-ext-panel')).toHaveCount(0, { timeout: 3000 });

  // 过程展开缓动与弹出层区分：Tailwind ease-out cubic-bezier(0,0,0.2,1)
  await textarea.fill('缓动核验');
  await textarea.press('Enter');
  const card = page.locator('.chat-tool-card').first();
  await expect(card).toHaveClass(/done/, { timeout: 15000 });
  const detailTiming = await card
    .locator('.chat-tool-detail')
    .evaluate((node) => getComputedStyle(node).transitionTimingFunction);
  expect(detailTiming).toContain('0, 0, 0.2, 1');
});

test('R9：键盘从打开的菜单返回输入框发送，菜单关闭且选项禁用', async ({ page }) => {
  await seedExtensions(page);
  await page.goto('/chat');
  const input = await switchToMock(page);
  await input.fill('键盘操作核验');
  await page.getByRole('button', { name: '选择本轮扩展（MCP 与技能）' }).click();
  await expect(page.getByRole('textbox', { name: '搜索扩展' })).toBeFocused();
  await page.keyboard.press('Shift+Tab');
  await page.keyboard.press('Shift+Tab');
  await expect(input).toBeFocused();
  await input.press('Enter');
  await expect(page.getByRole('button', { name: '停止', exact: true })).toBeVisible();
  // 生成开始：菜单自动关闭；退场期间也 inert，选项不可操作
  await expect(page.locator('.chat-ext-panel')).toHaveCount(0, { timeout: 3000 });
  await expect(page.getByRole('button', { name: '选择本轮扩展（MCP 与技能）' })).toBeDisabled();
  const bubble = page.locator('.chat-bubble.assistant').last();
  await expect(bubble).toContainText(REPLY_FRAGMENT, { timeout: 15000 });
});

test('R6：1920×1080 扩展闭环与边界截图', async ({ page }, testInfo) => {
  await seedExtensions(page);
  await page.setViewportSize({ width: 1920, height: 1080 });
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  await page.getByRole('button', { name: '选择本轮扩展（MCP 与技能）' }).click();
  await page.getByRole('button', { name: '选择MCP 演示检索' }).click();
  await page.getByRole('button', { name: '选择MCP 课程数据' }).click();
  await page.keyboard.press('Escape');
  await textarea.fill('1920 布局核验');
  await textarea.press('Enter');
  const bubble = page.locator('.chat-bubble.assistant').last();
  await expect(bubble.locator('.chat-tool-card.done')).toHaveCount(2, { timeout: 15000 });
  const evidence = await bounds(page);
  expect.soft(evidence.composer.left).toBeGreaterThanOrEqual(0);
  expect.soft(evidence.send.right).toBeLessThanOrEqual(evidence.composer.right + 1);
  await page.screenshot({ path: testInfo.outputPath('extensions-1920.png') });
});

test('R10：扩展菜单打开时点击外部，应关闭且焦点留在输入框', async ({ page }) => {
  await seedExtensions(page);
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  await page.getByRole('button', { name: '选择本轮扩展（MCP 与技能）' }).click();
  await expect(page.getByRole('textbox', { name: '搜索扩展' })).toBeFocused();
  // 内部点击不关闭
  await page.getByRole('button', { name: '选择MCP 演示检索' }).click();
  await expect(page.locator('.chat-ext-panel')).toBeVisible();
  // 点击外部输入框：菜单退场关闭，焦点留在输入框（不抢回触发器）
  await textarea.click();
  await expect(page.locator('.chat-ext-panel')).toHaveCount(0, { timeout: 3000 });
  await expect(page.getByRole('button', { name: '选择本轮扩展（MCP 与技能）' })).toHaveAttribute(
    'aria-expanded',
    'false',
  );
  await expect(textarea).toBeFocused();
});

test('追问：单选→多选/自由文本→提交→同轮续答→第二卡→完成', async ({ page }) => {
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  await page.getByRole('button', { name: '模拟追问' }).click();
  await textarea.fill('请帮我设计一个课堂提问');
  await textarea.press('Enter');

  const card1 = page.locator('.chat-ask-card').nth(0);
  await expect(card1).toBeVisible({ timeout: 15000 });
  await expect(card1).toContainText('1/2');
  // R16：原版追问卡没有进场装饰动画——不套用弹出层的 160ms pop
  const anim = await card1.evaluate((node) => {
    const cs = getComputedStyle(node);
    return { name: cs.animationName, duration: cs.animationDuration };
  });
  expect(anim.name).toBe('none');
  // 等待中可取消（主输入为空时显示停止）
  await expect(page.getByRole('button', { name: '停止', exact: true })).toBeVisible();

  // 单选：选中后自动跳到第二题
  await card1.getByRole('button', { name: /按知识点讲解/ }).click();
  await expect(card1).toContainText('2/2');
  // 多选：切换不自动前进
  await card1.getByRole('button', { name: /结合课标/ }).click();
  await card1.getByRole('button', { name: /给出示例/ }).click();
  await expect(card1.getByRole('button', { name: /结合课标/ })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await card1.getByRole('textbox').fill('多给例子');
  await card1.getByRole('button', { name: '提交回答' }).click();
  await expect(card1).toContainText('已回答');
  await expect(card1.locator('.chat-ask-summary')).toContainText('按知识点讲解');
  await expect(card1.locator('.chat-ask-summary')).toContainText('多给例子');

  // 同轮续写反映实际选择；第二张卡出现
  const bubble = page.locator('.chat-bubble.assistant').last();
  await expect(bubble).toContainText('按知识点讲解', { timeout: 15000 });
  await expect(bubble).toContainText('结合课标、给出示例');
  await expect(page.locator('.chat-ask-card')).toHaveCount(2);
  const card2 = page.locator('.chat-ask-card').nth(1);
  await expect(card2).toContainText('需要在本轮结束时附一段小结吗');

  // 第二卡：单题直接提交（未选按跳过）
  await card2.getByRole('button', { name: '提交', exact: true }).click();
  await expect(card2.locator('.chat-ask-summary')).toContainText('已跳过');
  await expect(bubble).toContainText('【模拟回复】本轮续答完成', { timeout: 15000 });
  // 全程一次会话、一次轮次
  await expect(page.locator('.chat-session-list li')).toHaveCount(1);
  await expect(page.getByRole('button', { name: '停止', exact: true })).toHaveCount(0);
});

test('追问：主输入框回答当前追问，走同一提交接口', async ({ page }) => {
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  await page.getByRole('button', { name: '模拟追问' }).click();
  await textarea.fill('设计一个提问');
  await textarea.press('Enter');
  const card1 = page.locator('.chat-ask-card').nth(0);
  await expect(card1).toBeVisible({ timeout: 15000 });

  // 主输入框回答：占位与按钮切换为追问语义；空输入时显示停止（取消等待）
  await expect(textarea).toHaveAttribute('placeholder', /回答当前追问/);
  await expect(page.getByRole('button', { name: '停止', exact: true })).toBeVisible();
  await textarea.fill('我想要按题目场景讲解，多给例子');
  const sendButton = page.getByRole('button', { name: '提交回答' });
  await expect(sendButton).toBeEnabled();
  await sendButton.click();
  await expect(card1).toContainText('已回答', { timeout: 15000 });
  await expect(card1.locator('.chat-ask-summary')).toContainText('我想要按题目场景讲解');
  // 第二卡跳过完成
  await expect(page.locator('.chat-ask-card')).toHaveCount(2);
  await page
    .locator('.chat-ask-card')
    .nth(1)
    .getByRole('button', { name: '提交', exact: true })
    .click();
  await expect(page.locator('.chat-bubble.assistant').last()).toContainText(
    '【模拟回复】本轮续答完成',
    { timeout: 15000 },
  );
});

test('追问：提交失败保留草稿与选择，可重试成功', async ({ page }) => {
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  await page.getByRole('button', { name: '模拟追问' }).click();
  await page.getByRole('button', { name: '模拟提交失败' }).click();
  await textarea.fill('会失败的问题');
  await textarea.press('Enter');
  const card1 = page.locator('.chat-ask-card').nth(0);
  await expect(card1).toBeVisible({ timeout: 15000 });

  await card1.getByRole('button', { name: /按知识点讲解/ }).click();
  await card1.getByRole('button', { name: /结合课标/ }).click();
  await card1.getByRole('button', { name: '提交回答' }).click();
  const error = card1.locator('.chat-ask-error');
  await expect(error).toContainText('MOCK_REPLY_ERROR', { timeout: 15000 });
  // 草稿与选择保留：单选在第 1 题（上一题导航可见选中态）
  await card1.getByRole('button', { name: '上一题' }).click();
  await expect(card1.getByRole('button', { name: /按知识点讲解/ })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  await card1.getByRole('button', { name: '下一题' }).click();
  await expect(card1.getByRole('button', { name: /结合课标/ })).toHaveAttribute(
    'aria-pressed',
    'true',
  );
  // 重试成功
  await error.getByRole('button', { name: '重试提交' }).click();
  await expect(card1).toContainText('已回答', { timeout: 15000 });
  await expect(page.locator('.chat-ask-card')).toHaveCount(2);
  await page
    .locator('.chat-ask-card')
    .nth(1)
    .getByRole('button', { name: '提交', exact: true })
    .click();
  await expect(page.locator('.chat-bubble.assistant').last()).toContainText(
    '【模拟回复】本轮续答完成',
    { timeout: 15000 },
  );
});

test('追问：等待中取消与刷新恢复中断', async ({ page }) => {
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  await page.getByRole('button', { name: '模拟追问' }).click();
  await textarea.fill('取消核验');
  await textarea.press('Enter');
  const card1 = page.locator('.chat-ask-card').nth(0);
  await expect(card1).toBeVisible({ timeout: 15000 });
  await expect(card1).toContainText('按什么方式讲解');

  // 等待中取消：卡片中断、消息已停止
  await page.getByRole('button', { name: '停止', exact: true }).click();
  await expect(card1).toContainText('已中断');
  await expect(card1).toContainText('本轮等待已失效');
  await expect(page.locator('.chat-bubble.assistant').last()).toContainText('已停止');
  // 中断后不可提交
  await expect(card1.getByRole('button', { name: '提交回答' })).toHaveCount(0);

  // 刷新后：恢复记录，等待明确中断，不重放、不可提交
  await page.reload();
  const textarea2 = await switchToMock(page);
  await expect(textarea2).toBeEnabled();
  const restored = page.locator('.chat-ask-card').first();
  await expect(restored).toBeVisible({ timeout: 15000 });
  await expect(restored).toContainText('已中断');
  await expect(restored).toContainText('本轮等待已失效');
  await expect(restored.getByRole('button', { name: '提交回答' })).toHaveCount(0);
  // 可显式重试原问题（新尝试）
  await expect(restored).toContainText('可重试原问题');
});

test('追问：全部跳过按原版语义提交为跳过', async ({ page }) => {
  await page.goto('/chat');
  const textarea = await switchToMock(page);
  await page.getByRole('button', { name: '模拟追问' }).click();
  await textarea.fill('跳过核验');
  await textarea.press('Enter');
  const card1 = page.locator('.chat-ask-card').nth(0);
  await expect(card1).toBeVisible({ timeout: 15000 });
  await card1.getByRole('button', { name: '跳过此题' }).click(); // 第 1 题跳过并前进
  await expect(card1).toContainText('2/2');
  await card1.getByRole('button', { name: '跳过此题' }).click(); // 第 2 题清空
  await card1.getByRole('button', { name: '提交回答' }).click();
  await expect(card1.locator('.chat-ask-summary')).toContainText('已跳过');
  const bubble = page.locator('.chat-bubble.assistant').last();
  await expect(bubble).toContainText('已按跳过处理', { timeout: 15000 });
  // 第二卡跳过完成整轮
  await expect(page.locator('.chat-ask-card')).toHaveCount(2);
  await page
    .locator('.chat-ask-card')
    .nth(1)
    .getByRole('button', { name: '提交', exact: true })
    .click();
  await expect(bubble).toContainText('【模拟回复】本轮续答完成', { timeout: 15000 });
});
