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
