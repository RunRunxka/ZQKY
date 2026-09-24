import { test, expect } from '@playwright/test';

/**
 * S5-C 书籍与课程浏览器回归：
 * 书籍列表（演示载入幂等/新建草稿）、状态机（确认提案→确认大纲→模拟编译→阅读器）、
 * 阅读器（翻页/键盘/书签/已读进度/无效页码/重建）、课程（列表/大纲勾选/编辑重置/
 * 资源附加跨目录联动/不可用态/归档）、导航显示（书籍可见、课程按参考隐藏）。
 * 全部使用隔离上下文与显式演示/种子数据，不读取真实用户数据。
 */

test('书籍列表：演示载入幂等、新建草稿与统计', async ({ page }) => {
  await page.goto('/books');
  await expect(page.getByRole('heading', { name: '书籍' })).toBeVisible();
  await expect(page.getByText('还没有书籍')).toBeVisible();
  // 样式回归：直达路由必须已加载 space 设计语言
  const display = await page.locator('.space-page').evaluate((el) => getComputedStyle(el).display);
  expect(display).toBe('flex');

  await page.getByRole('button', { name: '载入演示数据' }).click();
  await expect(page.getByRole('status').filter({ hasText: '已载入演示书籍' })).toBeVisible();
  await expect(page.locator('.space-persona-card', { hasText: '分数入门（演示书籍）' })).toBeVisible();
  await expect(page.locator('.space-persona-card', { hasText: '修辞手法小册（演示草稿）' })).toBeVisible();
  await expect(page.locator('.space-persona-card')).toHaveCount(2);
  await page.getByRole('button', { name: '载入演示数据' }).click();
  await expect(page.locator('.space-persona-card')).toHaveCount(2);

  // 统计与状态徽标（演示就绪书带 1 已读 → CTA 为继续阅读）
  await expect(page.getByRole('note').filter({ hasText: '共 2 本' })).toBeVisible();
  await expect(
    page.locator('.space-persona-card', { hasText: '分数入门（演示书籍）' }).locator('.space-chip', { hasText: '可阅读' }),
  ).toBeVisible();
  await expect(
    page.locator('.space-persona-card', { hasText: '分数入门（演示书籍）' }).getByRole('button', { name: '继续阅读' }),
  ).toBeVisible();

  // 新建书籍 → 草稿（模拟提案）
  await page.getByRole('button', { name: '新建书籍' }).click();
  const dialog = page.getByRole('dialog', { name: '新建书籍' });
  await dialog.getByLabel('书名').fill('测试书籍甲');
  await dialog.getByLabel('简介').fill('浏览器回归用');
  await dialog.getByRole('button', { name: '创建（生成模拟提案）' }).click();
  await expect(page).toHaveURL(/\/books\/bk-/);
  await expect(page.getByRole('heading', { name: '测试书籍甲' })).toBeVisible();
  await expect(page.getByText('提案（模拟）')).toBeVisible();
  await expect(page.getByText(/模拟提案：本地模板生成/)).toBeVisible();
});

test('书籍状态机：确认提案→确认大纲→模拟编译进入阅读器', async ({ page }) => {
  await page.goto('/books');
  await page.getByRole('button', { name: '载入演示数据' }).click();
  await page
    .locator('.space-persona-card', { hasText: '修辞手法小册（演示草稿）' })
    .getByRole('button', { name: '继续创建' })
    .click();
  await expect(page).toHaveURL(/\/books\/demo-book-draft$/);
  await expect(page.getByText('提案（模拟）')).toBeVisible();

  await page.getByRole('button', { name: '确认提案（进入大纲）' }).click();
  await expect(page.getByRole('status').filter({ hasText: '已确认提案' })).toBeVisible();
  await expect(page.getByText(/章节大纲（4 章）/)).toBeVisible();
  await expect(page.getByText('1. 比喻是什么')).toBeVisible();

  await page.getByRole('button', { name: '确认大纲并编译（模拟）' }).click();
  // 合同变更（H1-BOOKS-PIPELINE v2）：编译改由本地模拟执行器异步逐章逐块推进，不再是"确认即 ready"。
  // 旧同步断言替换为更强的异步状态断言：先出现活动条与生成中态，再等生成结束、内容可读。
  await expect(page).toHaveURL(/\/books\/demo-book-draft\/pages\//, { timeout: 15000 });
  await expect(page.getByText('第 1/8 页')).toBeVisible();
  await expect(page.locator('.book-pipeline-strip')).toContainText('正在逐章编译（本地模拟，不调用模型）…');
  await expect(page.getByRole('note').filter({ hasText: '本地模拟编译产物' })).toBeVisible();
  await expect(page.locator('.book-pipeline-strip')).toHaveCount(0, { timeout: 40000 });
  await expect(page.getByText(/这一页的主要目标是/)).toBeVisible({ timeout: 15000 });
});

test('就绪书阅读器：续读定位、书签、键盘翻页、无效页码与重建', async ({ page }) => {
  await page.goto('/books');
  await page.getByRole('button', { name: '载入演示数据' }).click();
  // 演示就绪书预置 1 已读（p0）→ 续读定位 p0
  await page.getByRole('link', { name: '打开书籍 分数入门（演示书籍）' }).click();
  await expect(page).toHaveURL(/\/books\/demo-book-fractions\/pages\/demo-book-fractions-p0$/);
  await expect(page.getByText('已读 1/4 页')).toBeVisible();

  // 书签切换与侧栏标记（演示书预置 p2 书签 + 当前页新书签 = 2 枚）
  await page.getByRole('button', { name: '添加书签' }).click();
  await expect(page.getByRole('button', { name: '移除书签' })).toBeVisible();
  await expect(page.getByLabel('章节目录').getByText('签')).toHaveCount(2);
  await page.keyboard.press('ArrowRight');
  await expect(page).toHaveURL(/\/pages\/demo-book-fractions-p1$/);

  // 无效页码深链
  await page.goto('/books/demo-book-fractions/pages/not-a-page');
  await expect(page.getByText('章节页不存在或已被重建')).toBeVisible();
  await page.getByRole('link', { name: '返回书籍首页' }).click();
  await expect(page).toHaveURL(/\/pages\/demo-book-fractions-p1$/);

  // 重建：重新模拟编译（异步流水线），旧页码立即失效
  page.once('dialog', (dialog) => void dialog.accept());
  await page.getByRole('button', { name: '重建书籍' }).click();
  await expect(page.getByText('章节页不存在或已被重建')).toBeVisible();
  await page.getByRole('link', { name: '返回书籍首页' }).click();
  await expect(page).toHaveURL(/\/pages\//);
  // 未生成页打开不登记已读（合同 §5.7）：等首章内容就绪后再断言已读登记
  await expect(page.getByText(/这一页的主要目标是/)).toBeVisible({ timeout: 40000 });
  await expect(page.getByText('已读 1/4 页')).toBeVisible();

  // 导出 Markdown：接住真实下载并保存到产物目录（避免悬挂下载对象拖垮浏览器）
  const downloadPromise = page.waitForEvent('download');
  await page.getByRole('button', { name: '导出 Markdown' }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe('分数入门（演示书籍）.md');
  await download.saveAs(await import('node:path').then((path) => path.join('_work', 'e2e-export-probe.md')));
  const exported = await import('node:fs/promises').then((f) => f.readFile('_work/e2e-export-probe.md', 'utf8'));
  expect(exported).toContain('# 分数入门（演示书籍）');
  await expect(page.getByRole('status').filter({ hasText: '已导出「分数入门（演示书籍）.md」' })).toBeVisible();
});

test('阅读器练习块：本地判定正确/错误', async ({ page }) => {
  await page.goto('/books');
  await page.getByRole('button', { name: '载入演示数据' }).click();
  await page.goto('/books/demo-book-fractions/pages/demo-book-fractions-p0');
  await expect(page.getByText(/这一页的主要目标是/)).toBeVisible();
  await page.getByRole('button', { name: 'A. 理解本页概念并能举例' }).click();
  await expect(page.getByRole('status').filter({ hasText: '回答正确。' })).toBeVisible();
  await page.goto('/books/demo-book-fractions/pages/demo-book-fractions-p1');
  await page.getByRole('button', { name: 'B. 背诵全文' }).click();
  await expect(page.getByRole('status').filter({ hasText: '回答错误，正确答案 A。' })).toBeVisible();
});

test('课程：演示载入、大纲勾选与编辑重置、资源附加与不可用态、归档', async ({ page }) => {
  await page.goto('/courses');
  await expect(page.getByRole('heading', { name: '课程' })).toBeVisible();
  await page.getByRole('button', { name: '载入演示数据' }).click();
  await expect(page.getByRole('status').filter({ hasText: '已载入演示课程' })).toBeVisible();
  await expect(page.locator('.space-persona-card', { hasText: '七年级数学（演示课程）' })).toBeVisible();
  await expect(page.getByText(/已归档课程（1）/)).toBeVisible();

  await page.getByRole('link', { name: '打开课程 七年级数学（演示课程）' }).click();
  await expect(page).toHaveURL(/\/courses\/demo-course-math$/);
  // H1-COURSE-SESSIONS v1：本页已有真实学习会话区（不再是"课程学习会话未接入"占位），本课程此时尚无会话
  await expect(page.getByRole('heading', { name: '学习会话' })).toBeVisible();
  await expect(page.getByText('本课程还没有学习会话')).toBeVisible();
  // 大纲：1/2 已完成，下一单元
  await expect(page.getByText(/大纲（1\/2 已完成，下一单元：一元一次方程）/)).toBeVisible();
  // 演示资源引用的知识库未载入 → 不可用态
  await expect(page.getByText(/课程标准库（不可用：目标已删除或未载入）/)).toBeVisible();

  // 勾选下一单元 → 全部完成
  await page.getByRole('checkbox', { name: '标记「一元一次方程」为已完成' }).check();
  await expect(page.getByText(/大纲（2\/2 已完成，全部完成）/)).toBeVisible();

  // 附加资料：候选来自本地目录（笔记本默认项恒在）
  await page.getByRole('button', { name: '附加资料' }).click();
  const addDialog = page.getByRole('dialog', { name: '附加课程资料' });
  await expect(addDialog.getByRole('heading', { name: '笔记本' })).toBeVisible();
  const notebookRow = addDialog.locator('.space-session-card', { hasText: '学习笔记' });
  await notebookRow.getByRole('button', { name: '附加' }).click();
  await expect(page.getByRole('status').filter({ hasText: '已附加资料「学习笔记」' })).toBeVisible();
  await expect(page.getByRole('link', { name: '学习笔记', exact: true })).toHaveAttribute(
    'href',
    '/notebooks/notebook-main',
  );

  // 编辑大纲：重建并重置 covered
  await page.getByRole('button', { name: '编辑大纲' }).click();
  await page.getByLabel('大纲文本').fill('新单元甲 | 主题一, 主题二');
  await page.getByRole('button', { name: '保存大纲' }).click();
  await expect(page.getByRole('status').filter({ hasText: '已保存大纲' })).toBeVisible();
  await expect(page.getByText(/大纲（0\/1 已完成，下一单元：新单元甲）/)).toBeVisible();

  // 移除资料：仅剩演示知识库条目（不可用态仍在）
  await page.getByRole('button', { name: '移除资料 学习笔记' }).click();
  await expect(page.getByRole('status').filter({ hasText: '已移除资料「学习笔记」' })).toBeVisible();
  await expect(page.getByRole('link', { name: '学习笔记', exact: true })).toHaveCount(0);
  await expect(page.getByText(/课程标准库（不可用：目标已删除或未载入）/)).toBeVisible();

  // 归档 → 列表折叠区展开后可见
  await page.getByRole('button', { name: '归档', exact: true }).click();
  await expect(page.getByRole('status').filter({ hasText: '已归档课程' })).toBeVisible();
  await page.getByRole('link', { name: '返回课程列表' }).click();
  const archivedGroup = page.getByText(/已归档课程（2）/);
  await expect(archivedGroup).toBeVisible();
  await archivedGroup.click();
  await expect(page.locator('.space-persona-card', { hasText: '七年级数学（演示课程）' })).toBeVisible();
});

test('课程新建与导航显示：书籍可见、课程按参考隐藏', async ({ page }) => {
  await page.goto('/courses');
  await page.getByRole('button', { name: '新建课程' }).click();
  const dialog = page.getByRole('dialog', { name: '新建课程' });
  await dialog.getByLabel('名称').fill('测试课程甲');
  await dialog.getByLabel('简介').fill('浏览器回归用');
  await dialog.getByRole('button', { name: '创建' }).click();
  await expect(page).toHaveURL(/\/courses\/cs-/);
  await expect(page.getByRole('heading', { name: /测试课程甲/ })).toBeVisible();
  await expect(page.getByText('还没有大纲')).toBeVisible();

  // 导航（UX-PERF-CLOSEOUT v1）：书籍已并入「教材资料库」，桌面侧栏不再有
  // 书籍顶级项；书籍与课程仍可经教材资料库页入口与手机抽屉到达，路由不变。
  // 项目导航根级默认展开（NavigationPreference）；仅在收起偏好下先展开，兼容两种状态
  await page.goto('/papers');
  await expect(page.locator('.app-shell')).toBeVisible();
  const expandNav = page.getByRole('button', { name: '展开项目导航' });
  if (await expandNav.isVisible()) await expandNav.click();
  await expect(page.getByRole('button', { name: '书籍', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '课程', exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: '教材资料库', exact: true })).toHaveCount(1);
  await page.goto('/books');
  await expect(
    page.getByRole('navigation', { name: '项目功能导航' }).getByRole('button', {
      name: '教材资料库',
      exact: true,
    }),
  ).toHaveAttribute('aria-current', 'page');
});

test('教材资料库 ↔ 书籍/课程：完整往返路径、返回入口与唯一当前项（UX-REGRESSION-FIX v1）', async ({
  page,
}) => {
  const currentNav = page.locator('.global-nav [aria-current="page"]');
  const backToKb = page.getByRole('link', { name: '返回教材资料库' });

  // ===== 教材资料库 → 书籍列表 → 书籍详情 → 书籍列表 → 教材资料库 =====
  await page.goto('/knowledge-bases');
  await page.locator('.kb-library-links a[href="/books"]').click();
  await expect(page).toHaveURL(/\/books$/);
  await expect(backToKb).toBeVisible();
  await expect(currentNav).toHaveCount(1);
  await expect(currentNav).toHaveText(/教材资料库/);

  // 空列表也能看到返回入口
  await expect(page.getByRole('heading', { name: '书籍', exact: true })).toBeVisible();
  await page.getByRole('button', { name: '载入演示数据' }).click();
  const bookCard = page.locator('a[href^="/books/"]').first();
  await expect(bookCard).toBeVisible();
  await bookCard.click();
  await expect(page).toHaveURL(/\/books\/[^/]+$/);
  await expect(currentNav).toHaveText(/教材资料库/);
  await page.getByRole('link', { name: '返回书籍列表' }).click();
  await expect(page).toHaveURL(/\/books$/);
  await expect(backToKb).toBeVisible();
  await backToKb.click();
  await expect(page).toHaveURL(/\/knowledge-bases$/);
  await expect(currentNav).toHaveText(/教材资料库/);

  // 直接深链打开列表页同样能返回（不依赖 history.back）
  await page.goto('/books');
  await expect(backToKb).toBeVisible();
  await backToKb.click();
  await expect(page).toHaveURL(/\/knowledge-bases$/);

  // ===== 教材资料库 → 课程列表 → 课程详情 → 课程列表 → 教材资料库 =====
  await page.locator('.kb-library-links a[href="/courses"]').click();
  await expect(page).toHaveURL(/\/courses$/);
  await expect(backToKb).toBeVisible();
  await expect(currentNav).toHaveCount(1);
  await expect(currentNav).toHaveText(/教材资料库/);
  await page.getByRole('button', { name: '载入演示数据' }).click();
  const courseCard = page.locator('a[href^="/courses/"]').first();
  await expect(courseCard).toBeVisible();
  await courseCard.click();
  await expect(page).toHaveURL(/\/courses\/[^/]+$/);
  await expect(currentNav).toHaveText(/教材资料库/);
  await page.getByRole('link', { name: '返回课程列表' }).click();
  await expect(page).toHaveURL(/\/courses$/);
  await backToKb.click();
  await expect(page).toHaveURL(/\/knowledge-bases$/);
  await expect(currentNav).toHaveText(/教材资料库/);

  // 手机视口：返回入口仍可见且不横向溢出
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/books');
  await expect(backToKb).toBeVisible();
  await page.goto('/courses');
  await expect(backToKb).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
});
