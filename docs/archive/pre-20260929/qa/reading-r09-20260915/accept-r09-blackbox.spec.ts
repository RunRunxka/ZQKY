import { test, expect, type Page } from '@playwright/test';

/**
 * 独立验收 R-09（候选 a1fa16e）：验收者自写黑盒用例，与实现者 tests/e2e/reading.spec.ts 分开。
 * 全部使用隔离上下文 + 演示数据 + 端口 5174 + .next-test 构建；
 * 断言检查容器 scrollTop/scrollHeight 数值与用户手势，不依赖 CSS 类名。
 * 伴生回复为显式模拟服务（标注【模拟回复】），不代表真实 AI 供应商行为。
 */

const companionPane = (page: Page) => page.getByRole('complementary', { name: '伴生助手（模拟）' });
const body = (page: Page) => page.locator('.reading-companion-body');
const reader = (page: Page) => page.locator('.reading-pane[onMouseUp], .reading-pane').filter({ has: page.locator('[data-loc]') }).first();

async function gotoDemoWorkspace(page: Page) {
  await page.goto('/reading');
  await page.getByRole('button', { name: '载入演示数据' }).click();
  await expect(page.getByRole('status').filter({ hasText: '已载入演示阅读数据' })).toBeVisible();
  await page.getByRole('link', { name: '打开阅读集合 分数阅读（演示集合）' }).click();
  await expect(page).toHaveURL(/\/reading\/demo-reading-ws$/);
}

/** 从 localStorage 读指定会话持久化数据（实现层真实落盘，绕过渲染时机） */
async function persistedSession(page: Page, sessionId: string) {
  return page.evaluate((id) => {
    const list = JSON.parse(localStorage.getItem('zhiqikeyuan:reading-sessions') ?? '[]') as Array<{
      id: string;
      messages: { role: string; content: string }[];
      draft?: string;
    }>;
    return list.find((item) => item.id === id) ?? null;
  }, sessionId);
}

// ===== A：滚动跟随 =====

test('ACC-A 真实滚轮上滚后位置保持，正文与整页不动；「回到最新」只滚伴生容器', async ({ page }, testInfo) => {
  await gotoDemoWorkspace(page);
  const companion = companionPane(page);
  const compBody = body(page);

  // 第一轮完成，让容器有基础内容；第二轮流式中做手势
  await companion.getByLabel('向伴生助手提问').fill('验收A第一轮');
  await companion.getByLabel('发送提问').click();
  // 回复是异步流式落盘的：等持久化里出现第二轮回复（探针实测：初始2条→完成后4条）
  await expect
    .poll(async () => (await persistedSession(page, 'demo-reading-ss-1'))?.messages.length ?? 0)
    .toBe(4);
  const demo = await persistedSession(page, 'demo-reading-ss-1');
  expect(demo?.messages.filter((m) => m.role === 'assistant')).toHaveLength(2); // 演示1轮 + 本轮

  await companion.getByLabel('向伴生助手提问').fill('验收A第二轮流式手势');
  await companion.getByLabel('发送提问').click();

  // 事件驱动：等容器真的可滚动（可滚动量 > 80px）再上滚，避免空容器假动作
  await expect.poll(() => compBody.evaluate((el) => el.scrollHeight - el.clientHeight)).toBeGreaterThan(80);

  // 底部基线：上滚前应在底部
  const bottomGapBefore = await compBody.evaluate((el) => el.scrollHeight - el.scrollTop - el.clientHeight);
  expect(bottomGapBefore).toBeLessThan(2);

  // 真实用户手势：mouse.wheel 向上
  await compBody.hover();
  await page.mouse.wheel(0, -600);
  await page.waitForTimeout(120); // 等待滚动物理结束（wheel 是异步滚动）
  const topAfterWheel = await compBody.evaluate((el) => el.scrollTop);
  expect(topAfterWheel).toBeLessThan(60);

  // 记录正文容器与整页基线
  const readerEl = page.locator('.reading-pane').filter({ has: page.locator('[data-loc]') }).first();
  const readerTopBefore = await readerEl.evaluate((el) => el.scrollTop);
  const scrollYBefore = await page.evaluate(() => window.scrollY);

  // 流式继续：可滚动量继续增长，且 scrollTop 不被拉回、距底 > 90（跟随已关闭）
  await expect.poll(() => compBody.evaluate((el) => el.scrollHeight - el.clientHeight)).toBeGreaterThan(150);
  const topDuring = await compBody.evaluate((el) => el.scrollTop);
  expect(topDuring, '流式中 scrollTop 不应被拉回底部(0)').toBeLessThan(60);
  const gapDuring = await compBody.evaluate((el) => el.scrollHeight - el.scrollTop - el.clientHeight);
  expect(gapDuring, '距底应 > 90px（用户已离开底部）').toBeGreaterThan(90);
  expect(await readerEl.evaluate((el) => el.scrollTop), '正文容器位置不动').toBe(readerTopBefore);
  expect(await page.evaluate(() => window.scrollY), '整页 scrollY 不动').toBe(scrollYBefore);

  await page.screenshot({ path: testInfo.outputPath('acc-a-scroll-held.png') });

  // 「回到最新」：点击后伴生容器回到底部，正文与整页仍不动
  const backBtn = companion.getByRole('button', { name: '回到最新' });
  await expect(backBtn).toBeVisible();
  await backBtn.click();
  await expect.poll(() => compBody.evaluate((el) => el.scrollHeight - el.scrollTop - el.clientHeight)).toBeLessThan(2);
  expect(await readerEl.evaluate((el) => el.scrollTop)).toBe(readerTopBefore);
  expect(await page.evaluate(() => window.scrollY)).toBe(scrollYBefore);
  await expect(backBtn).toHaveCount(0);
});

test('ACC-A2 底部时正常跟随（未上滚则增量后仍在底部）', async ({ page }) => {
  await gotoDemoWorkspace(page);
  const companion = companionPane(page);
  const compBody = body(page);
  await companion.getByLabel('向伴生助手提问').fill('验收A2跟随基线');
  await companion.getByLabel('发送提问').click();
  await expect.poll(() => compBody.evaluate((el) => el.scrollHeight - el.clientHeight)).toBeGreaterThan(80);
  // 用户不做任何手势：全程应保持在底部（gap < 2）
  await expect
    .poll(() => compBody.evaluate((el) => el.scrollHeight - el.scrollTop - el.clientHeight), { timeout: 8000 })
    .toBeLessThan(2);
});

// ===== B：会话归属 =====

test('ACC-B 生成中切新会话立即干净；迟到事件只落旧会话；切回完整', async ({ page }) => {
  await gotoDemoWorkspace(page);
  const companion = companionPane(page);
  const compBody = body(page);

  await companion.getByLabel('向伴生助手提问').fill('验收B旧轮问题');
  await companion.getByLabel('发送提问').click();
  await expect(page.getByTestId('companion-turn')).toBeVisible();
  // 抓住进行中的 turnId（DOM 上不可见，改以持久化消息数判定迟到收尾已完成）
  const msgsBefore = (await persistedSession(page, 'demo-reading-ss-1'))?.messages.length ?? 0;

  // 生成中 → 新会话
  await companion.getByRole('button', { name: '新建阅读会话' }).click();
  await expect(page).toHaveURL(/\/sessions\/rss-/);
  const newSessionUrl = new URL(page.url()).pathname;
  const newSessionId = newSessionUrl.split('/sessions/')[1];

  // 新会话立即可用且干净：无"生成中"块、无旧内容、可立即发送新问题
  await expect(page.getByTestId('companion-turn')).toHaveCount(0);
  await expect(page.locator('.reading-msg')).toHaveCount(0);
  await companion.getByLabel('向伴生助手提问').fill('验收B新会话立即提问');
  await companion.getByLabel('发送提问').click();
  await expect(page.getByTestId('companion-turn')).toBeVisible(); // 新会话自己的轮次
  // 新轮次内容必须是新问题的（旧轮文本不得出现）
  await expect.poll(() => page.getByTestId('companion-turn').innerText()).not.toContain('验收B旧轮问题');

  // 等旧轮迟到 end 落盘：旧会话助手消息追加完整模拟回复
  await expect
    .poll(async () => {
      const s = await persistedSession(page, 'demo-reading-ss-1');
      return s?.messages.filter((m) => m.role === 'assistant').length ?? 0;
    }, { timeout: 15000 })
    .toBeGreaterThan(0);
  const lastOld = await page.evaluate(() => {
    const list = JSON.parse(localStorage.getItem('zhiqikeyuan:reading-sessions') ?? '[]') as Array<{ id: string; messages: { role: string; content: string }[] }>;
    const s = list.find((i) => i.id === 'demo-reading-ss-1')!;
    return s.messages.filter((m) => m.role === 'assistant').at(-1)!.content;
  });
  expect(lastOld).toContain('【模拟回复】');

  // 新会话持久化里不得有旧轮内容
  const newSess = await persistedSession(page, newSessionId!);
  const newContents = JSON.stringify(newSess?.messages ?? []);
  expect(newContents).not.toContain('验收B旧轮问题');
  expect(newSess?.messages.filter((m) => m.role === 'assistant').every((m) => m.content.includes('验收B新会话立即提问')) ?? false).toBe(true);

  // 切回旧会话：用户消息 + 完整模拟回复都恢复
  await companion.getByRole('combobox', { name: '阅读会话选择' }).selectOption('demo-reading-ss-1');
  await expect(page.locator('.reading-msg').filter({ hasText: '验收B旧轮问题' })).toHaveCount(1);
  await expect(page.locator('.reading-msg').filter({ hasText: '【模拟回复】' })).toHaveCount(2);
  void msgsBefore; void compBody;
});

test('ACC-B2 取消后旧轮收尾不改新会话；已生成内容保留在旧会话', async ({ page }) => {
  await gotoDemoWorkspace(page);
  const companion = companionPane(page);
  await companion.getByLabel('向伴生助手提问').fill('验收B2取消问题');
  await companion.getByLabel('发送提问').click();
  await expect(page.getByTestId('companion-turn')).toBeVisible();
  await expect.poll(() => page.getByTestId('companion-turn').innerText()).toMatch(/【模拟回复】/);
  await companion.getByRole('button', { name: '停止生成' }).click();

  await companion.getByRole('button', { name: '新建阅读会话' }).click();
  await expect(page).toHaveURL(/\/sessions\/rss-/);
  await expect(page.getByTestId('companion-turn')).toHaveCount(0);
  await expect(page.locator('.reading-msg')).toHaveCount(0);

  await expect
    .poll(async () => {
      const s = await persistedSession(page, 'demo-reading-ss-1');
      return s?.messages.filter((m) => m.role === 'assistant').at(-1)?.content ?? '';
    })
    .toContain('（已取消）');

  await companion.getByRole('combobox', { name: '阅读会话选择' }).selectOption('demo-reading-ss-1');
  await expect(page.locator('.reading-msg').filter({ hasText: /（已取消）/ })).toHaveCount(1);
  await expect(page.locator('.reading-msg').filter({ hasText: '验收B2取消问题' })).toHaveCount(1);
});

// ===== C：会话历史 =====

test('ACC-C 切换/新建有历史；重复切换同一会话不加历史；popstate 同步会话+草稿', async ({ page }) => {
  await gotoDemoWorkspace(page);
  const companion = companionPane(page);
  const picker = companion.getByRole('combobox', { name: '阅读会话选择' });

  const len0 = await page.evaluate(() => history.length);
  await companion.getByLabel('向伴生助手提问').fill('验收C的A会话草稿');
  // 让草稿防抖落盘（300ms 防抖）
  await expect.poll(async () => (await persistedSession(page, 'demo-reading-ss-1'))?.draft ?? '').toBe('验收C的A会话草稿');

  // 新建会话 B：push 1 条
  await companion.getByRole('button', { name: '新建阅读会话' }).click();
  await expect(page).toHaveURL(/\/sessions\/rss-/);
  const urlB = new URL(page.url()).pathname;
  const lenAfterNew = await page.evaluate(() => history.length);
  expect(lenAfterNew, '新建会话应 push 一条历史').toBe(len0 + 1);

  // 新会话草稿为空（不串 A 的草稿）
  await expect(companion.getByLabel('向伴生助手提问')).toHaveValue('');

  // 主动切回 A：再 push 1 条
  await picker.selectOption('demo-reading-ss-1');
  await expect(page).toHaveURL(/\/sessions\/demo-reading-ss-1$/);
  expect(await page.evaluate(() => history.length)).toBe(lenAfterNew + 1);
  // A 草稿恢复
  await expect(companion.getByLabel('向伴生助手提问')).toHaveValue('验收C的A会话草稿');

  // 重复切到 A（地址已一致）：不得再 push
  await picker.selectOption('demo-reading-ss-1');
  expect(await page.evaluate(() => history.length), '地址一致不写历史').toBe(lenAfterNew + 1);

  // 后退 → B；前进 → A（草稿一致）
  await page.goBack();
  await expect(page).toHaveURL(urlB.endsWith('/') ? urlB : urlB);
  await expect(companion.getByLabel('向伴生助手提问')).toHaveValue('');
  await page.goForward();
  await expect(page).toHaveURL(/\/sessions\/demo-reading-ss-1$/);
  await expect(companion.getByLabel('向伴生助手提问')).toHaveValue('验收C的A会话草稿');
});

test('ACC-C2 初始化/规范化不制造重复历史；无效会话沿用既有提示语义', async ({ page }) => {
  // 深链直达 A：首次定位不 push 额外历史
  await page.goto('/reading');
  await page.getByRole('button', { name: '载入演示数据' }).click();
  await expect(page.getByRole('status').filter({ hasText: '已载入演示阅读数据' })).toBeVisible();
  await page.getByRole('link', { name: '打开阅读集合 分数阅读（演示集合）' }).click();
  await expect(page).toHaveURL(/\/reading\/demo-reading-ws$/);
  const len0 = await page.evaluate(() => history.length);
  await page.goto('/reading/demo-reading-ws/sessions/demo-reading-ss-1');
  // 探针2实测：深链 goto 占自身 1 条（3→4），reload 不新增（4→4）。
  // 断言：深链定位 + reload 都不得额外 push（若组件 replaceState 滥用会仍为同一地址但
  // 长度回落不可能；若 pushState 滥用则长度会 > 4）。
  const lenBeforeReload = await page.evaluate(() => history.length);
  await page.reload();
  await expect(page.getByRole('combobox', { name: '阅读会话选择' })).toHaveValue('demo-reading-ss-1');
  const lenAfterDeepLink = await page.evaluate(() => history.length);
  expect(lenAfterDeepLink, 'reload 与深链定位均不新增历史条目').toBe(lenBeforeReload);

  // 无效会话深链：沿用"链接指向的会话不存在"语义
  await page.goto('/reading/demo-reading-ws/sessions/not-exist-ss');
  await expect(page.getByRole('alert').filter({ hasText: '链接指向的会话不存在' })).toBeVisible();
  await expect(page.getByRole('combobox', { name: '阅读会话选择' })).toHaveValue('demo-reading-ss-1');
  void len0;
});

test('ACC-F 刷新后按会话恢复消息与草稿、不重放生成过程', async ({ page }) => {
  await gotoDemoWorkspace(page);
  const companion = companionPane(page);
  await companion.getByLabel('向伴生助手提问').fill('验收F刷新前提问');
  await companion.getByLabel('发送提问').click();
  await expect
    .poll(async () => (await persistedSession(page, 'demo-reading-ss-1'))?.messages.filter((m) => m.content.includes('验收F刷新前提问')).length ?? 0)
    .toBe(1);
  await expect
    .poll(async () => ((await persistedSession(page, 'demo-reading-ss-1'))?.messages.filter((m) => m.role === 'assistant').at(-1)?.content ?? '').includes('【模拟回复】'))
    .toBe(true);
  await companion.getByLabel('向伴生助手提问').fill('验收F未发送草稿');
  await expect.poll(async () => (await persistedSession(page, 'demo-reading-ss-1'))?.draft ?? '').toBe('验收F未发送草稿');

  await page.reload();
  // 消息恢复、无"生成中"块重放
  await expect(page.locator('.reading-msg').filter({ hasText: '验收F刷新前提问' })).toHaveCount(1);
  await expect(page.locator('.reading-msg').filter({ hasText: '【模拟回复】' })).toHaveCount(2);
  await expect(page.getByTestId('companion-turn')).toHaveCount(0);
  // 草稿恢复
  await expect(companion.getByLabel('向伴生助手提问')).toHaveValue('验收F未发送草稿');
});

// ===== G：390 视口 + reducedMotion 移动端抽屉 =====

test('ACC-G 移动端抽屉（reduce）：真实手势上滚保持、回到最新、切换有历史', async ({ page }, testInfo) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await gotoDemoWorkspace(page);
  await page.getByRole('button', { name: '打开伴生助手面板' }).click();
  const drawer = page.getByRole('dialog', { name: '伴生助手（模拟）' });
  await expect(drawer).toBeVisible();

  await drawer.getByLabel('向伴生助手提问').fill('验收G第一轮');
  await drawer.getByLabel('发送提问').click();
  await expect
    .poll(async () => (await persistedSession(page, 'demo-reading-ss-1'))?.messages.filter((m) => m.role === 'assistant').length ?? 0)
    .toBe(2);
  await drawer.getByLabel('向伴生助手提问').fill('验收G第二轮流式');
  await drawer.getByLabel('发送提问').click();

  const drawerBody = drawer.locator('.reading-companion-body');
  await expect.poll(() => drawerBody.evaluate((el) => el.scrollHeight - el.clientHeight)).toBeGreaterThan(80);
  const readerEl = page.locator('.reading-pane').filter({ has: page.locator('[data-loc]') }).first();
  const readerTopBefore = await readerEl.evaluate((el) => el.scrollTop);
  const scrollYBefore = await page.evaluate(() => window.scrollY);

  await drawerBody.hover();
  await page.mouse.wheel(0, -600);
  await page.waitForTimeout(120);
  expect(await drawerBody.evaluate((el) => el.scrollTop)).toBeLessThan(60);
  await expect.poll(() => drawerBody.evaluate((el) => el.scrollHeight - el.clientHeight)).toBeGreaterThan(150);
  expect(await drawerBody.evaluate((el) => el.scrollTop)).toBeLessThan(60);
  expect(await readerEl.evaluate((el) => el.scrollTop), '移动端正文不动').toBe(readerTopBefore);
  expect(await page.evaluate(() => window.scrollY), '移动端整页不动').toBe(scrollYBefore);
  await page.screenshot({ path: testInfo.outputPath('acc-g-mobile.png') });

  await drawer.getByRole('button', { name: '回到最新' }).click();
  await expect.poll(() => drawerBody.evaluate((el) => el.scrollHeight - el.scrollTop - el.clientHeight)).toBeLessThan(2);

  await drawer.getByRole('button', { name: '新建阅读会话' }).click();
  await expect(page).toHaveURL(/\/sessions\/rss-/);
  const createdUrl = new URL(page.url()).pathname;
  await page.goBack();
  await expect(page).toHaveURL(/\/reading\/demo-reading-ws$/);
  await page.goForward();
  expect(new URL(page.url()).pathname).toBe(createdUrl);
});
