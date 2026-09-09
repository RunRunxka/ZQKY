import { test, expect } from '@playwright/test';

/**
 * S5-D 沉浸阅读回归：
 * 集合列表（演示载入/进入工作区三栏）、选区操作（高亮/笔记/书签/问 AI 预填）、
 * 伴生会话（演示会话/发送模拟回复/新会话 URL 改写/切换/深链）、
 * 材料库（新建/分配/删除）、工作区管理（添加/切换/移除材料、重命名、
 * 整理笔记与发到笔记本跨页联动）、不存在集合深链报错。
 * 伴生回复为本地模拟并标注【模拟回复】；全部使用隔离上下文与演示数据。
 */

async function gotoDemoWorkspace(page: import('@playwright/test').Page) {
  await page.goto('/reading');
  await page.getByRole('button', { name: '载入演示数据' }).click();
  await expect(page.getByRole('status').filter({ hasText: '已载入演示阅读数据' })).toBeVisible();
  await page.getByRole('link', { name: '打开阅读集合 分数阅读（演示集合）' }).click();
  await expect(page).toHaveURL(/\/reading\/demo-reading-ws$/);
  await expect(page.getByRole('heading', { name: '分数阅读（演示集合）' })).toBeVisible();
}

test('集合列表：空态、演示载入幂等、进入工作区三栏与演示批注/书签', async ({ page }) => {
  await page.goto('/reading');
  await expect(page.getByRole('heading', { name: '沉浸阅读' })).toBeVisible();
  await expect(page.getByText('还没有阅读集合')).toBeVisible();
  const display = await page.locator('.space-page').evaluate((el) => getComputedStyle(el).display);
  expect(display).toBe('flex');

  await page.getByRole('button', { name: '载入演示数据' }).click();
  await expect(page.getByRole('status').filter({ hasText: '已载入演示阅读数据' })).toBeVisible();
  await expect(page.locator('.space-persona-card', { hasText: '分数阅读（演示集合）' })).toBeVisible();
  await expect(page.locator('.space-persona-card')).toHaveCount(1);
  await page.getByRole('button', { name: '载入演示数据' }).click();
  await expect(page.locator('.space-persona-card')).toHaveCount(1);

  await page.getByRole('link', { name: '打开阅读集合 分数阅读（演示集合）' }).click();
  await expect(page).toHaveURL(/\/reading\/demo-reading-ws$/);
  // 三栏：导航 + 阅读器 + 伴生助手
  await expect(page.getByRole('complementary', { name: '阅读导航' })).toBeVisible();
  await expect(page.getByRole('complementary', { name: '伴生助手（模拟）' })).toBeVisible();
  await expect(page.getByRole('heading', { name: '分数是什么', level: 1 })).toBeVisible();
  // 演示批注在正文中高亮
  await expect(page.locator('mark[data-annotation-id="demo-reading-ann-1"]')).toBeVisible();
  // 导航：大纲 3 项、书签 1、批注 1
  const nav = page.getByRole('complementary', { name: '阅读导航' });
  await expect(nav.getByRole('button', { name: '分数是什么' })).toBeVisible();
  await expect(nav.getByRole('button', { name: '生活中的分数' })).toBeVisible();
  await nav.getByRole('tab', { name: '书签（1）' }).click();
  await expect(nav.getByRole('button', { name: '生活中的分数', exact: true })).toBeVisible();
  await nav.getByRole('tab', { name: '批注（1）' }).click();
  await expect(nav.getByText('约分通分的依据，考试常考。')).toBeVisible();
});

test('选区操作：高亮、批注笔记、书签与问 AI 预填', async ({ page }) => {
  await gotoDemoWorkspace(page);
  const selectPara = async (needle: string) => {
    await page.evaluate((text) => {
      const para = [...document.querySelectorAll('[data-loc]')].find((el) => el.textContent?.includes(text));
      if (!para) throw new Error(`找不到段落：${text}`);
      const range = document.createRange();
      range.selectNodeContents(para);
      const sel = window.getSelection();
      if (!sel) throw new Error('无选区对象');
      sel.removeAllRanges();
      sel.addRange(range);
    }, needle);
    await page.locator('p', { hasText: needle }).dispatchEvent('mouseup');
  };

  // 高亮（黄色）
  await selectPara('半块蛋糕是');
  const bar = page.getByRole('menu', { name: '选区操作' });
  await expect(bar).toBeVisible();
  await bar.getByRole('button', { name: '高亮（yellow）' }).click();
  await expect(page.getByRole('status').filter({ hasText: '已添加高亮' })).toBeVisible();
  const nav = page.getByRole('complementary', { name: '阅读导航' });
  await expect(nav.getByRole('tab', { name: '批注（2）' })).toBeVisible();

  // 批注笔记
  await selectPara('分数表示把一个整体');
  await bar.getByRole('button', { name: '笔记' }).click();
  await bar.getByLabel('批注笔记内容').fill('课上强调过平均分。');
  await bar.getByRole('button', { name: '保存笔记' }).click();
  await expect(page.getByRole('status').filter({ hasText: '已保存批注笔记' })).toBeVisible();
  await nav.getByRole('tab', { name: '批注（3）' }).click();
  await expect(nav.getByText('课上强调过平均分。')).toBeVisible();

  // 书签
  await selectPara('半块蛋糕是');
  await bar.getByRole('button', { name: '书签' }).click();
  await expect(page.getByRole('status').filter({ hasText: '已添加书签' })).toBeVisible();
  await nav.getByRole('tab', { name: '书签（2）' }).click();
  await expect(nav.getByRole('button', { name: /半块蛋糕是/ }).first()).toBeVisible();

  // 问 AI：quote 预填到伴生输入框
  await selectPara('半块蛋糕是');
  await bar.getByRole('button', { name: '问 AI' }).click();
  await expect(page.getByLabel('向伴生助手提问')).toHaveValue(/半块蛋糕是/);
});

test('伴生会话：演示会话、发送模拟回复、新会话 URL、切换与深链', async ({ page }) => {
  await gotoDemoWorkspace(page);
  const companion = page.getByRole('complementary', { name: '伴生助手（模拟）' });
  const messages = companion.locator('.reading-msg');
  // 演示会话直接呈现
  await expect(companion.getByRole('combobox', { name: '阅读会话选择' })).toHaveValue('demo-reading-ss-1');
  await expect(messages.filter({ hasText: '什么是约分？' })).toHaveCount(1);
  await expect(messages.filter({ hasText: /【模拟回复】约分是把分子分母的公因数约去/ })).toHaveCount(1);

  // 发送 → 用户消息 + 本地模拟回复
  await companion.getByLabel('向伴生助手提问').fill('通分和约分有什么区别？');
  await companion.getByLabel('发送提问').click();
  await expect(messages.filter({ hasText: '通分和约分有什么区别？' })).toHaveCount(1);
  await expect(messages.filter({ hasText: /【模拟回复】关于《分数是什么（演示材料）》.*本地模板生成/ })).toHaveCount(1);

  // 新会话：URL 改写为 sessions/<id>，空会话提示
  await companion.getByRole('button', { name: '新建阅读会话' }).click();
  await expect(page).toHaveURL(/\/reading\/demo-reading-ws\/sessions\/rss-/);
  await expect(companion.getByText(/伴生助手为本地模拟/)).toBeVisible();
  await companion.getByLabel('向伴生助手提问').fill('新会话第一条');
  await companion.getByLabel('发送提问').click();
  await expect(messages.filter({ hasText: '新会话第一条' })).toHaveCount(1);

  // 切换回演示会话：消息恢复且 URL 跟随
  await companion.getByRole('combobox', { name: '阅读会话选择' }).selectOption('demo-reading-ss-1');
  await expect(page).toHaveURL(/\/reading\/demo-reading-ws\/sessions\/demo-reading-ss-1$/);
  await expect(messages.filter({ hasText: '什么是约分？' })).toHaveCount(1);

  // 深链直达会话
  await page.goto('/reading/demo-reading-ws/sessions/demo-reading-ss-1');
  await expect(messages.filter({ hasText: /【模拟回复】约分是把分子分母的公因数约去/ })).toHaveCount(1);
});

test('材料库：新建文本材料、分配到集合与删除', async ({ page }) => {
  await page.goto('/reading/materials');
  await expect(page.getByRole('heading', { name: '阅读材料库' })).toBeVisible();
  await expect(page.getByText('还没有材料')).toBeVisible();

  await page.getByRole('button', { name: '载入演示数据' }).click();
  await expect(page.getByRole('status').filter({ hasText: '已载入演示阅读数据' })).toBeVisible();
  await expect(page.locator('.space-session-card', { hasText: '修辞手法摘录（未分配演示材料）' })).toBeVisible();

  await page.getByRole('button', { name: '新建文本材料' }).click();
  const dialog = page.getByRole('dialog', { name: '新建文本材料' });
  await dialog.getByLabel('标题').fill('阅读理解步骤');
  await dialog.getByLabel('正文').fill('# 三步读文章\n\n先看题目，再读正文，最后回题作答。');
  await dialog.getByRole('button', { name: '创建' }).click();
  await expect(page).toHaveURL(/\/reading\/materials\?focus=mat-/);
  await expect(page.locator('.space-session-card', { hasText: '阅读理解步骤' })).toBeVisible();

  // 分配到演示集合
  await page
    .locator('.space-session-card', { hasText: '阅读理解步骤' })
    .getByRole('button', { name: '分配材料 阅读理解步骤' })
    .click();
  await page
    .getByRole('dialog', { name: '分配「阅读理解步骤」' })
    .locator('.space-session-card', { hasText: '分数阅读（演示集合）' })
    .getByRole('button', { name: '加入' })
    .click();
  await expect(page.getByRole('status').filter({ hasText: '已把「阅读理解步骤」加入' })).toBeVisible();
  await expect(page.locator('.space-session-card', { hasText: '阅读理解步骤' }).getByText('已入 1 个集合')).toBeVisible();

  // 删除（confirm）
  page.once('dialog', (d) => void d.accept());
  await page
    .locator('.space-session-card', { hasText: '阅读理解步骤' })
    .getByRole('button', { name: '删除材料 阅读理解步骤' })
    .click();
  await expect(page.locator('.space-session-card', { hasText: '阅读理解步骤' })).toHaveCount(0);
});

test('工作区管理：添加/切换/移除材料、重命名、整理笔记发到笔记本、深链报错', async ({ page }) => {
  await gotoDemoWorkspace(page);

  // 添加演示材料 B 并切换
  await page.getByRole('button', { name: '添加材料' }).click();
  await page
    .getByRole('dialog', { name: '添加材料到集合' })
    .locator('.space-session-card', { hasText: '修辞手法摘录（未分配演示材料）' })
    .getByRole('button', { name: '添加' })
    .click();
  await expect(page.getByRole('status').filter({ hasText: '已添加材料「修辞手法摘录（未分配演示材料）」' })).toBeVisible();
  await expect(page.getByRole('tab', { name: /修辞手法摘录/ })).toHaveAttribute('aria-selected', 'true');
  await expect(page.getByRole('heading', { name: '比喻', level: 1 })).toBeVisible();

  await page.getByRole('tab', { name: /分数是什么（演示材料）/ }).click();
  await expect(page.getByRole('heading', { name: '分数是什么', level: 1 })).toBeVisible();

  // 重命名集合
  await page.getByRole('button', { name: '重命名集合' }).click();
  const rename = page.getByRole('dialog', { name: '重命名阅读集合' });
  await rename.getByLabel('名称').fill('分数精读（改名）');
  await rename.getByRole('button', { name: '保存' }).click();
  await expect(page.getByRole('heading', { name: '分数精读（改名）' })).toBeVisible();

  // 整理笔记（模拟整理）
  await page.getByRole('button', { name: '整理笔记' }).click();
  const organized = page.getByRole('dialog', { name: '整理笔记（模拟整理）' });
  await expect(organized.getByText('分子和分母同时乘或除以同一个不为零的数，分数的大小不变。')).toBeVisible();
  await organized.getByRole('button', { name: '关闭', exact: true }).click();

  // 发到笔记本 → 学习笔记
  await page.getByRole('button', { name: '发到笔记本' }).click();
  await page
    .getByRole('dialog', { name: '整理笔记发到笔记本' })
    .locator('.space-session-card', { hasText: '学习笔记' })
    .getByRole('button', { name: '写入' })
    .click();
  await expect(page.getByRole('status').filter({ hasText: '已把整理笔记写入笔记本「学习笔记」' })).toBeVisible();

  // 跨页联动：笔记本出现该记录
  await page.goto('/notebooks/notebook-main');
  await expect(page.getByText('分数精读（改名） · 阅读笔记')).toBeVisible();

  // 移除材料（confirm；X 图标以 aria-label 定位）
  await page.goto('/reading/demo-reading-ws');
  page.once('dialog', (d) => void d.accept());
  await page.getByLabel('移除材料 分数是什么（演示材料）').click();
  await expect(page.getByRole('tab', { name: /分数是什么（演示材料）/ })).toHaveCount(0);

  // 不存在集合深链
  await page.goto('/reading/no-such-workspace');
  await expect(page.getByText('阅读集合不存在或已被删除')).toBeVisible();
  await page.getByRole('link', { name: '返回沉浸阅读' }).click();
  await expect(page).toHaveURL(/\/reading$/);
});

// ===== R28–R31 审查修复回归（阅读审查 2026-09-08）=====

/** 复现审查场景的自定义种子：两个材料（可选长文），重复段落用于 R29 */
async function seedReviewMaterials(page: import('@playwright/test').Page, long = false) {
  await page.addInitScript(({ longText }) => {
    const now = '2026-09-08T00:00:00.000Z';
    const text = longText
      ? Array.from({ length: 100 }, (_, i) => `第 ${i} 段正文。这是用于验证阅读位置的足够长的测试材料。`).join('\n\n')
      : '# 标题\n\n相同的句子。\n\n相同的句子。';
    const materials = ['a', 'b'].map((id) => ({
      id, title: `材料${id.toUpperCase()}`, text, filename: null, sourceKind: 'text', sourceUrl: null,
      charCount: text.length, sizeBytes: text.length * 3, positionPct: 0,
      workspaceIds: ['review-ws'], createdAt: now, updatedAt: now,
    }));
    localStorage.setItem('zhiqikeyuan:reading-materials', JSON.stringify(materials));
    localStorage.setItem('zhiqikeyuan:reading-workspaces', JSON.stringify([{
      id: 'review-ws', title: '审查集合', description: '', activeMaterialId: 'a',
      tabs: materials.map((m) => ({ materialId: m.id, addedAt: now })), createdAt: now, updatedAt: now,
    }]));
  }, { longText: long });
  await page.goto('/reading/review-ws');
  await expect(page.getByRole('heading', { name: '审查集合' })).toBeVisible();
}

const reviewReader = (page: import('@playwright/test').Page) => page.locator('.reading-layout > .reading-pane:not(aside)');

test('R28 材料库入口：真实路由跳转、前进后退一致', async ({ page }) => {
  await gotoDemoWorkspace(page);
  // 入口一：Tab 条「材料库…」
  await page.getByRole('button', { name: '材料库…', exact: true }).click();
  await expect(page).toHaveURL(/\/reading\/materials$/);
  await expect(page.getByRole('heading', { name: '阅读材料库', exact: true })).toBeVisible();
  await page.goBack();
  await expect(page.getByRole('heading', { name: '分数阅读（演示集合）' })).toBeVisible();
  await page.goForward();
  await expect(page.getByRole('heading', { name: '阅读材料库', exact: true })).toBeVisible();

  // 入口二：添加材料弹窗无候选时的「打开材料库」
  await page.goto('/reading/demo-reading-ws');
  await page.getByRole('button', { name: '添加材料' }).click();
  await page
    .getByRole('dialog', { name: '添加材料到集合' })
    .locator('.space-session-card', { hasText: '修辞手法摘录（未分配演示材料）' })
    .getByRole('button', { name: '添加' })
    .click();
  await expect(page.getByRole('status').filter({ hasText: '已添加材料' })).toBeVisible();
  await page.getByRole('button', { name: '添加材料' }).click();
  await page.getByRole('dialog', { name: '添加材料到集合' }).getByRole('button', { name: '打开材料库' }).click();
  await expect(page).toHaveURL(/\/reading\/materials$/);
  await expect(page.getByRole('heading', { name: '阅读材料库', exact: true })).toBeVisible();
});

test('R29 批注定位：高亮第二处重复段落只标记该处', async ({ page }, testInfo) => {
  await seedReviewMaterials(page);
  await reviewReader(page).locator('p[data-loc]').nth(1).evaluate((paragraph) => {
    const range = document.createRange();
    range.selectNodeContents(paragraph);
    const selection = window.getSelection()!;
    selection.removeAllRanges();
    selection.addRange(range);
    paragraph.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }));
  });
  await page.getByRole('button', { name: '高亮（yellow）', exact: true }).click();
  await page.screenshot({ path: testInfo.outputPath('duplicate-highlight.png') });
  await expect(reviewReader(page).locator('mark')).toHaveCount(1);
  await expect(reviewReader(page).locator('p[data-loc]').nth(0).locator('mark')).toHaveCount(0);
  // 刷新后仍只恢复所标注的一处（segments 持久化）
  await page.reload();
  await expect(reviewReader(page).locator('mark')).toHaveCount(1);
  await expect(reviewReader(page).locator('p[data-loc]').nth(0).locator('mark')).toHaveCount(0);
});

test('R30 阅读位置：切换到零位置材料回到顶部，旧材料位置保留', async ({ page }, testInfo) => {
  await seedReviewMaterials(page, true);
  await reviewReader(page).evaluate((el) => { el.scrollTop = (el.scrollHeight - el.clientHeight) * 0.6; });
  await expect.poll(() => reviewReader(page).evaluate((el) => el.scrollTop)).toBeGreaterThan(100);
  await expect.poll(() => page.evaluate(() => JSON.parse(localStorage.getItem('zhiqikeyuan:reading-materials')!)[0].positionPct)).toBeGreaterThan(0);
  await page.getByRole('tab', { name: /^材料B/ }).click();
  await expect(reviewReader(page).locator('header strong')).toHaveText('材料B');
  await page.screenshot({ path: testInfo.outputPath('unread-position.png') });
  await expect.poll(() => reviewReader(page).evaluate((el) => el.scrollTop)).toBe(0);
  // 切回材料 A：已保存的位置恢复
  await page.getByRole('tab', { name: /^材料A/ }).click();
  await expect.poll(() => reviewReader(page).evaluate((el) => el.scrollTop)).toBeGreaterThan(100);
});

test('R31 布局：收起导航正文变宽；伴生栏拖拽与键盘可达', async ({ page }, testInfo) => {
  await gotoDemoWorkspace(page);
  const before = (await reviewReader(page).boundingBox())!.width;
  await page.getByRole('button', { name: '收起导航', exact: true }).click();
  await expect(page.getByRole('complementary', { name: '阅读导航' })).toHaveCount(0);
  await page.screenshot({ path: testInfo.outputPath('collapsed-navigation.png') });
  await expect.poll(async () => (await reviewReader(page).boundingBox())!.width).toBeGreaterThan(before);
  // 展开恢复
  await page.getByRole('button', { name: '展开导航', exact: true }).click();
  await expect(page.getByRole('complementary', { name: '阅读导航' })).toBeVisible();

  // 伴生栏拖拽（1440×900 ≥ 1280 分界）：向左拖 40px → 加宽 40 并持久化
  const handle = page.getByRole('separator', { name: '调整伴生栏宽度' });
  await expect(handle).toBeVisible();
  const box = (await handle.boundingBox())!;
  await page.mouse.move(box.x + box.width / 2, box.y + 100);
  await page.mouse.down();
  await page.mouse.move(box.x + box.width / 2 - 40, box.y + 100, { steps: 4 });
  await page.mouse.up();
  await expect.poll(() => page.evaluate(() => localStorage.getItem('zhiqikeyuan:reader:companionWidth'))).toBe('420');

  // 键盘：ArrowLeft 加宽 16
  await handle.focus();
  await handle.press('ArrowLeft');
  await expect.poll(() => page.evaluate(() => localStorage.getItem('zhiqikeyuan:reader:companionWidth'))).toBe('436');
});
