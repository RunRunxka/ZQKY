import { test, expect, type Page } from '@playwright/test';

/**
 * R-11 故障回归：知识目录损坏或读取失败时，课程页保持可用。
 *
 * 隔离数据：只写本 spec 的 localStorage 种子，不读取用户真实数据。
 * 覆盖：JSON 损坏 / 结构非法 / 存储读取失败 / 目标已删除，以及
 * 故障 → 重试仍失败 → 数据修复 → 重试恢复，并比较原始存储逐字节未变。
 */

const KB_KEY = 'zqky.replica.knowledge.v1';
const COURSES_KEY = 'zhiqikeyuan:courses';

const COURSE = {
  id: 'c-r11',
  name: '容错课程',
  description: 'R-11 故障回归',
  color: 'blue',
  instructions: '学习约定文本',
  syllabus: [{ id: 'u1', position: 0, title: '单元一', topics: ['主题A'], covered: false }],
  resources: [
    {
      id: 'r1',
      kind: 'knowledge_base',
      refId: 'kb-1',
      label: '课程标准库',
      position: 0,
      addedAt: '2026-09-08T00:00:00.000Z',
    },
  ],
  status: 'active',
  createdAt: '2026-09-08T00:00:00.000Z',
  updatedAt: '2026-09-08T00:00:00.000Z',
};

async function seed(page: Page, knowledge: string | null) {
  // 只在首次写入种子：reload 不重置课程，保证"添加/解除"结果可被刷新验证
  await page.addInitScript(
    ({ coursesKey, kbKey, course, kb }) => {
      if (!window.localStorage.getItem(coursesKey)) {
        window.localStorage.setItem(coursesKey, JSON.stringify([course]));
      }
      if (kb === null) window.localStorage.removeItem(kbKey);
      else window.localStorage.setItem(kbKey, kb);
    },
    { coursesKey: COURSES_KEY, kbKey: KB_KEY, course: COURSE, kb: knowledge },
  );
}

/** 断言课程正文与大纲仍在（R-11 核心：知识目录失败不阻断课程主体）。 */
async function expectCourseBodyIntact(page: Page) {
  await expect(page.getByRole('heading', { name: '容错课程' })).toBeVisible();
  await expect(page.getByText('学习约定文本')).toBeVisible();
  // 大纲条目（精确到列表项，避免命中"下一单元：单元一"标题）
  await expect(page.getByRole('checkbox', { name: '标记「单元一」为已完成' })).toBeVisible();
  await expect(page.getByRole('heading', { name: /^大纲（/ })).toBeVisible();
}

test.describe('R-11 课程资源目录故障', () => {
  for (const [label, raw] of [
    ['JSON 损坏', '{not json'],
    ['结构非法（合法 JSON 非数组）', JSON.stringify({ not: 'array' })],
  ] as const) {
    test(`${label}：课程正文与大纲保留，资源区显示错误与重试`, async ({ page }) => {
      const errors: string[] = [];
      page.on('pageerror', (e) => errors.push(e.message));
      await seed(page, raw);
      await page.goto('/courses/c-r11');

      await expectCourseBodyIntact(page);
      // 错误横幅 + 重试入口（不是空列表）
      await expect(page.getByText('资源目录读取失败', { exact: false })).toBeVisible();
      await expect(page.getByRole('button', { name: '重试' })).toBeVisible();
      // 引用仍在，且标注为“目录读取失败，暂无法确认”而非“目标已删除”
      await expect(page.getByText('课程标准库（目录读取失败，暂无法确认）')).toBeVisible();
      await expect(page.getByText(/目标已删除/)).toHaveCount(0);
      expect(errors, '不应有未捕获页面异常').toEqual([]);

      // 存储未被覆盖
      const stored = await page.evaluate((k) => window.localStorage.getItem(k), COURSES_KEY);
      expect(stored).toBe(JSON.stringify([COURSE]));
    });
  }

  test('存储读取被拒：同样显示错误且不覆盖数据', async ({ page }) => {
    await page.addInitScript(
      ({ coursesKey, course }) => {
        window.localStorage.setItem(coursesKey, JSON.stringify([course]));
        const real = Storage.prototype.getItem;
        Storage.prototype.getItem = function (key: string) {
          if (String(key).includes('knowledge')) throw new Error('injected read failure');
          return real.call(this, key);
        };
      },
      { coursesKey: COURSES_KEY, course: COURSE },
    );
    await page.goto('/courses/c-r11');
    await expectCourseBodyIntact(page);
    await expect(page.getByText('资源目录读取失败', { exact: false })).toBeVisible();
    const stored = await page.evaluate((k) => window.localStorage.getItem(k), COURSES_KEY);
    expect(stored).toBe(JSON.stringify([COURSE]));
  });

  test('目标已删除：仍显示“不可用：目标已删除或未载入”，不作为错误', async ({ page }) => {
    await seed(page, JSON.stringify([]));
    await page.goto('/courses/c-r11');
    await expectCourseBodyIntact(page);
    await expect(page.getByText('课程标准库（不可用：目标已删除或未载入）')).toBeVisible();
    await expect(page.getByText('资源目录读取失败', { exact: false })).toHaveCount(0);
  });

  test('故障 → 重试仍失败 → 数据修复 → 重试恢复可用（不清数据）', async ({ page }) => {
    await seed(page, '{broken');
    await page.goto('/courses/c-r11');
    await expect(page.getByText('资源目录读取失败', { exact: false })).toBeVisible();
    // 重试仍失败：错误仍在，课程不变
    await page.getByRole('button', { name: '重试' }).click();
    await expect(page.getByText('资源目录读取失败', { exact: false })).toBeVisible();
    await expectCourseBodyIntact(page);

    // 修复数据后再重试：恢复为可用链接
    await page.evaluate(
      ({ kbKey, id }) =>
        window.localStorage.setItem(
          kbKey,
          JSON.stringify([{ id, name: '课程标准库', description: 'd' }]),
        ),
      { kbKey: KB_KEY, id: 'kb-1' },
    );
    await page.getByRole('button', { name: '重试' }).click();
    await expect(page.getByText('资源目录读取失败', { exact: false })).toHaveCount(0);
    await expect(page.getByRole('link', { name: '课程标准库' })).toBeVisible();

    // 全程未修改课程存储
    const stored = await page.evaluate((k) => window.localStorage.getItem(k), COURSES_KEY);
    expect(stored).toBe(JSON.stringify([COURSE]));
  });

  test('添加资源面板在故障时显示错误与重试，不崩溃', async ({ page }) => {
    const errors: string[] = [];
    page.on('pageerror', (e) => errors.push(e.message));
    await seed(page, '{broken');
    await page.goto('/courses/c-r11');
    await page.getByRole('button', { name: '附加资料' }).click();
    const dialog = page.getByRole('dialog', { name: '附加课程资料' });
    await expect(dialog).toBeVisible();
    await expect(dialog.getByText('资源目录读取失败')).toBeVisible();
    await expect(dialog.getByRole('button', { name: '重试' })).toBeVisible();
    expect(errors).toEqual([]);
  });

  test('正常资源仍可添加、打开与解除关联，刷新后正确', async ({ page }) => {
    await seed(page, JSON.stringify([{ id: 'kb-new', name: '新知识库', description: 'd' }]));
    await page.goto('/courses/c-r11');
    await page.getByRole('button', { name: '附加资料' }).click();
    const dialog = page.getByRole('dialog', { name: '附加课程资料' });
    const row = dialog.locator('li.space-session-card', { hasText: '新知识库' });
    await row.getByRole('button', { name: '附加' }).click();
    await expect(page.getByText('已附加资料')).toBeVisible({ timeout: 10000 });
    // 打开：资源行内出现指向知识库详情的链接
    const expectedHref = '/knowledge-bases/' + encodeURIComponent('新知识库');
    await expect(page.locator(`a[href="${expectedHref}"]`)).toBeVisible();
    // 刷新后仍在
    await page.reload();
    await expect(page.locator(`a[href="${expectedHref}"]`)).toBeVisible();
    // 解除关联后链接消失（记录保留在课程内直到主动移除）
    await page.getByRole('button', { name: '移除资料 新知识库' }).click();
    await expect(page.getByText('已移除资料「新知识库」')).toBeVisible();
    await expect(page.locator(`a[href="${expectedHref}"]`)).toHaveCount(0);
  });

  test('知识目录失败不阻断其他目录候选（书籍/笔记本仍可选）', async ({ page }) => {
    await page.addInitScript(
      ({ coursesKey, kbKey, course, books }) => {
        window.localStorage.setItem(coursesKey, JSON.stringify([course]));
        window.localStorage.setItem(kbKey, '{broken');
        window.localStorage.setItem('zhiqikeyuan:books', JSON.stringify(books));
      },
      {
        coursesKey: COURSES_KEY,
        kbKey: KB_KEY,
        course: COURSE,
        books: [
          {
            id: 'b1',
            title: '容错书籍',
            status: 'ready',
            createdAt: '2026-09-08T00:00:00.000Z',
            updatedAt: '2026-09-08T00:00:00.000Z',
          },
        ],
      },
    );
    await page.goto('/courses/c-r11');
    await page.getByRole('button', { name: '附加资料' }).click();
    const dialog = page.getByRole('dialog', { name: '附加课程资料' });
    // 书籍候选仍出现（失败目录未冒充空，也未阻断其他目录）
    await expect(dialog.locator('li.space-session-card', { hasText: '容错书籍' })).toBeVisible();
    // 失败目录不冒充空：不出现"知识库"分组（该书候选仍在，证明未被失败目录阻断）
    await expect(dialog.locator('section.space-group').filter({ hasText: '知识库' })).toHaveCount(0);
  });

  test('手机视口：故障态仍可读、公共壳与返回入口保留', async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });
    await seed(page, '{broken');
    await page.goto('/courses/c-r11');
    await expectCourseBodyIntact(page);
    await expect(page.getByText('资源目录读取失败', { exact: false })).toBeVisible();
    await expect(page.getByRole('button', { name: '重试' })).toBeVisible();
    // 公共壳与返回入口
    // 手机下桌面侧栏按设计收起，公共壳以顶部导航 + 抽屉呈现
    await expect(page.locator('.app-shell')).toBeVisible();
    await expect(page.getByRole('button', { name: '打开功能导航' })).toBeVisible();
    await expect(page.getByRole('link', { name: '返回课程列表' })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(true);
  });
});
