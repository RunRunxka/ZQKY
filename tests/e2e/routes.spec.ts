import { test, expect } from '@playwright/test';

/**
 * R9 路由与壳套件：十个页面在真实构建下渲染公共壳，导航当前项正确，无横向溢出。
 * 后端不在场时页面数据区显示错误态（本套件只断言壳与页面骨架，不依赖业务数据）。
 */

const ROUTES: { path: string; nav: string; root: string }[] = [
  { path: '/chat', nav: '对话', root: '.chat-page' },
  { path: '/lesson-plans', nav: '教案工作台', root: '.lesson-workbench' },
  { path: '/textbooks', nav: '教材资料库', root: '.textbook-page' },
  { path: '/knowledge-points', nav: '知识点', root: '.knowledge-points-page' },
  { path: '/question-bank', nav: '题库', root: '.question-bank-page' },
  { path: '/practices', nav: '练习', root: '.practices-page' },
  { path: '/learning-analysis', nav: '学情分析', root: '.learning-analysis-page' },
  { path: '/assessments/roster', nav: '班级管理', root: '.assessments-page' },
  { path: '/assessments/papers', nav: '试卷管理', root: '.assessments-page' },
  { path: '/settings', nav: '设置', root: '.settings-document' },
];

for (const route of ROUTES) {
  test(`${route.path}：公共壳 + 导航当前项（${route.nav}）+ 无横向溢出`, async ({ page }) => {
    await page.goto(route.path);
    const nav = page.locator('nav.global-nav');
    await expect(nav).toBeVisible();
    const current = nav.locator('[aria-current="page"]');
    await expect(current.first()).toBeVisible();
    await expect(current.filter({ hasText: route.nav }).first()).toBeVisible();
    await expect(page.locator(route.root).first()).toBeVisible();
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    expect(overflow).toBeLessThanOrEqual(1);
  });
}

test('/assessments 重定向到班级管理', async ({ page }) => {
  await page.goto('/assessments');
  await expect(page).toHaveURL(/\/assessments\/roster$/);
  await expect(page.locator('nav.global-nav [aria-current="page"]').first()).toContainText('班级管理');
});

test('390 视口：三个业务页无横向溢出且主内容可达', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  for (const path of ['/chat', '/lesson-plans', '/practices']) {
    await page.goto(path);
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - window.innerWidth,
    );
    expect(overflow, `${path} 横向溢出`).toBeLessThanOrEqual(1);
  }
});

test('教案工作台：折叠预览/编辑后剩余栏占满，无右侧空洞与隐式换行', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/lesson-plans');
  await expect(page.locator('[data-testid="lw-columns"]')).toBeVisible();
  await page.waitForTimeout(450);

  const measure = () =>
    page.locator('[data-testid="lw-columns"]').evaluate((element) => {
      const rect = (selector: string) => {
        const target = element.querySelector(selector) as HTMLElement;
        const box = target.getBoundingClientRect();
        return {
          x: box.x,
          y: box.y,
          width: box.width,
          height: box.height,
          display: getComputedStyle(target).display,
        };
      };
      const container = element.getBoundingClientRect();
      const tracks = getComputedStyle(element)
        .gridTemplateColumns.split(' ')
        .map((value) => Number.parseFloat(value))
        .filter((value) => Number.isFinite(value));
      return {
        container: { x: container.x, y: container.y, width: container.width },
        trackSum: tracks.reduce((sum, value) => sum + value, 0),
        left: rect('[data-testid="lw-col-left"]'),
        mid: rect('[data-testid="lw-col-mid"]'),
        right: rect('[data-testid="lw-col-right"]'),
        splitterLeft: rect('.lw-splitter-left'),
        splitterMid: rect('.lw-splitter-mid'),
      };
    });

  const initial = await measure();
  expect(initial.right.display).not.toBe('none');

  await page.getByTestId('lw-dock-preview').click();
  await page.waitForTimeout(450);
  const noPreview = await measure();
  expect(noPreview.right.display).toBe('none');
  expect(noPreview.splitterMid.display).toBe('none');
  expect(noPreview.mid.width).toBeGreaterThan(noPreview.container.width * 0.6);
  expect(Math.abs(noPreview.trackSum - noPreview.container.width)).toBeLessThan(6);
  expect(noPreview.mid.y).toBeCloseTo(noPreview.left.y, 0);

  await page.getByTestId('lw-dock-editor').click();
  await page.waitForTimeout(450);
  const onlyLayout = await measure();
  expect(onlyLayout.mid.display).toBe('none');
  expect(onlyLayout.splitterLeft.display).toBe('none');
  expect(onlyLayout.left.width).toBeGreaterThan(onlyLayout.container.width * 0.9);
  expect(Math.abs(onlyLayout.trackSum - onlyLayout.container.width)).toBeLessThan(6);

  await page.getByTestId('lw-dock-editor').click();
  await page.getByTestId('lw-dock-preview').click();
  await page.waitForTimeout(450);
  const restored = await measure();
  expect(restored.right.display).not.toBe('none');
  expect(restored.mid.display).not.toBe('none');
  expect(restored.splitterMid.display).not.toBe('none');
  expect(restored.right.y).toBeCloseTo(restored.left.y, 0);
  expect(Math.abs(restored.trackSum - restored.container.width)).toBeLessThan(6);
});

test('教案预览：跨页续表页首有上边框，内部子项不重复横线', async ({ page }) => {
  const lines = (prefix: string, count: number) =>
    Array.from({ length: count }, (_, index) =>
      `${prefix}${index + 1}：这是用于验证跨页页首表格线的较长文本，包含足够多的汉字以产生多行折行。`,
    ).join('\n');
  const draft = {
    schemaVersion: 1,
    styleVersion: 2,
    revision: 1,
    updatedAt: '2026-10-24T00:00:00.000Z',
    data: {
      title: '页首边框验收',
      coreCompetencies: '知识：理解页首边框\n能力：检查跨页续行\n思政：保持表格完整',
      keyPoints: '教学重点：页首有上边框\n教学难点：内部子项不重复横线',
      teachingDesign: '用于验证评价/反思跨页时的页首表格线。',
      exercises: '完成页首边框检查。',
      basic: {
        courseName: '页首边框验收',
        teacher: '王老师',
        audience: '高一（1）班',
        hours: '1',
        teachingTime: '周一',
        location: '教室 301',
        chapter: '第一单元',
      },
      analysis: {
        learning: lines('学情分析', 3),
        textbook: lines('教材分析', 2),
        content: lines('教学内容', 2),
        ideological: lines('思政资源', 1),
      },
      strategy: { designThinking: '验证跨页表格线。', teachingFlow: '检查—修正—复核', methods: '目测' },
      evaluation: { afterClassTest: lines('课后测试', 24), homework: lines('课后作业', 24) },
      reflection: `（一）目标达成度分析\n${lines('目标达成', 14)}\n（二）教学特色与可供借鉴之处\n${lines('教学特色', 14)}\n（三）教学后记\n${lines('教学后记', 14)}`,
      processV2: [],
    },
  };

  await page.addInitScript((value) => {
    window.localStorage.setItem('zhiqikeyuan:lesson-plan:v1', JSON.stringify(value));
  }, draft);
  await page.goto('/lesson-plans');
  await page.waitForSelector('[data-testid="lw-paper-3"]', { timeout: 20000 });
  await page.waitForTimeout(800);

  const result = await page.evaluate(() => {
    const pages = Array.from(document.querySelectorAll('.lw-page'));
    let continuedTables = 0;
    let badTopBorders = 0;
    let internalNoTop = 0;
    let internalNoTopWithBorder = 0;
    for (const pageElement of pages) {
      for (const table of Array.from(pageElement.querySelectorAll('table.lw-sheet-table.continued'))) {
        continuedTables += 1;
        const firstCell = table.querySelector('tbody tr td') as HTMLElement | null;
        if (!firstCell || Number.parseFloat(getComputedStyle(firstCell).borderTopWidth) <= 0) {
          badTopBorders += 1;
        }
      }
      for (const row of Array.from(pageElement.querySelectorAll('tr.lw-sheet-subrow.no-top'))) {
        if (row === row.parentElement?.querySelector('tr')) continue;
        internalNoTop += 1;
        const cell = row.querySelector('td.subcell') as HTMLElement | null;
        if (cell && Number.parseFloat(getComputedStyle(cell).borderTopWidth) > 0) {
          internalNoTopWithBorder += 1;
        }
      }
    }
    return { pages: pages.length, continuedTables, badTopBorders, internalNoTop, internalNoTopWithBorder };
  });

  expect(result.pages).toBeGreaterThan(3);
  expect(result.continuedTables).toBeGreaterThan(0);
  expect(result.badTopBorders).toBe(0);
  expect(result.internalNoTop).toBeGreaterThan(0);
  expect(result.internalNoTopWithBorder).toBe(0);
});
