import { test, expect } from '@playwright/test';
import fs from 'node:fs/promises';
import fixture from '../fixtures/lesson-plan.json' with { type: 'json' };
import { verifyDocx, verifySource } from '../../scripts/verify-template.mjs';
const key = 'zhiqikeyuan:lesson-plan:v1';
test.beforeEach(async ({ context }) => {
  await context.addInitScript(
    ({ key, draft }) => {
      if (!localStorage.getItem(key)) localStorage.setItem(key, JSON.stringify(draft));
    },
    { key, draft: fixture },
  );
});
test('根路由跳转学习问答，教案直达与草稿刷新恢复，无客户端初始化错误', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(e.message));
  page.on('console', (m) => {
    if (m.type() === 'error' && /hydration|hydrating/i.test(m.text())) errors.push(m.text());
  });
  await page.goto('/');
  await expect(page).toHaveURL(/\/chat$/);
  await expect(page.locator('.chat-page')).toBeVisible();
  await page.goto('/lesson-plans');
  const title = page.getByRole('textbox', { name: '课题', exact: true });
  await expect(title).toHaveValue('荷塘月色');
  await title.fill('课题 · 持久化验证');
  await expect(page.locator('.subject-cell')).toHaveText('课题 · 持久化验证');
  await expect(page.locator('.save-status')).toHaveText('已保存到本机');
  await page.reload();
  await expect(title).toHaveValue('课题 · 持久化验证');
  expect(errors).toEqual([]);
});
test('路由切换立即保存，返回恢复；其他页面不继承教案打印样式', async ({ page }) => {
  await page.goto('/lesson-plans');
  const title = page.getByRole('textbox', { name: '课题', exact: true });
  await title.fill('最后一笔编辑');
  await page.getByRole('button', { name: '学习问答', exact: true }).click();
  await expect(page).toHaveURL(/\/chat$/);
  await expect(page.locator('.chat-page')).toBeVisible();
  await page.emulateMedia({ media: 'print' });
  // 学习问答主页使用自己的工具栏；全局顶栏自主页复刻后在桌面隐藏。
  await expect(page.locator('.chat-toolbar')).toBeVisible();
  await expect(page.locator('.chat-page')).toBeVisible();
  expect(await page.locator('body').evaluate((e) => getComputedStyle(e).page)).toBe('auto');
  await page.emulateMedia({ media: 'screen' });
  // R-02：品牌按钮现在统一回唯一主页 /chat；回到教案工作台改走侧栏菜单，
  // 并顺带断言品牌入口不再指向教案页。
  await expect(page.locator('.sidebar-brand')).toHaveAttribute('aria-label', '返回学习问答');
  await page.getByRole('button', { name: '教案工作台', exact: true }).click();
  await expect(page).toHaveURL(/\/lesson-plans$/);
  await expect(title).toHaveValue('最后一笔编辑');
});
test('规则确认、撤销重做、环节排序及增删', async ({ page }) => {
  await page.goto('/lesson-plans');
  await page.getByRole('button', { name: '要求填充' }).click();
  await page
    .getByRole('textbox', { name: '备课要求' })
    .fill('课题：规则新课题\n核心素养：批量修改目标\n未知项：请检查');
  await page.getByRole('button', { name: '识别填充内容' }).click();
  await expect(page.locator('.fill-warnings')).toContainText('未知项');
  await expect(page.locator('.subject-cell')).toHaveText('荷塘月色');
  await page.getByRole('button', { name: '确认填入教案' }).click();
  await expect(page.locator('.subject-cell')).toHaveText('规则新课题');
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(page.locator('.subject-cell')).toHaveText('荷塘月色');
  await page.getByRole('button', { name: '重做', exact: true }).click();
  await expect(page.locator('.subject-cell')).toHaveText('规则新课题');
  await page.getByRole('button', { name: '教学过程', exact: true }).click();
  await page.getByRole('button', { name: '下移环节1' }).click();
  await expect(page.locator('.process-editor').first().getByLabel('环节名称')).toHaveValue(
    fixture.data.process[1].stage,
  );
  await page.getByRole('button', { name: '添加教学环节' }).click();
  await expect(page.locator('.process-editor')).toHaveCount(5);
  await page.getByRole('button', { name: '删除环节5' }).click();
  await expect(page.locator('.process-editor')).toHaveCount(4);
  await page.getByRole('button', { name: '撤销', exact: true }).click();
  await expect(page.locator('.process-editor')).toHaveCount(5);
});
test('JSON备份导入、Word结构和PDF打印导出', async ({ page }, testInfo) => {
  await page.goto('/lesson-plans');
  await page.getByRole('textbox', { name: '课题', exact: true }).fill('导出测试');
  await page.getByRole('button', { name: '导出教案', exact: true }).click();
  const backupEvent = page.waitForEvent('download');
  await page.getByRole('button', { name: /备份草稿/ }).click();
  const backup = await backupEvent;
  const backupPath = testInfo.outputPath('backup.json');
  await backup.saveAs(backupPath);
  expect(JSON.parse(await fs.readFile(backupPath, 'utf8')).data.title).toBe('导出测试');
  await page.locator('input[type=file]').setInputFiles({
    name: 'restore.json',
    mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify(fixture)),
  });
  await expect(page.locator('.subject-cell')).toHaveText('荷塘月色');
  await page.getByRole('button', { name: '导出教案', exact: true }).click();
  const docxEvent = page.waitForEvent('download');
  await page.getByRole('button', { name: '导出 Word' }).click();
  const docx = await docxEvent;
  await docx.saveAs(testInfo.outputPath('sample.docx'));
  expect(
    Object.values(verifyDocx(await fs.readFile(testInfo.outputPath('sample.docx')))),
  ).not.toContain(false);
  expect(Object.values(verifySource())).not.toContain(false);
  await page.getByRole('button', { name: '导出教案', exact: true }).click();
  await page.getByRole('button', { name: '导出 PDF' }).click();
  await expect(page.getByRole('dialog')).toContainText('另存为 PDF');
  await page.evaluate(() => {
    window.print = () => {
      document.body.dataset.printCalled = 'yes';
      window.dispatchEvent(new Event('afterprint'));
    };
  });
  await page.getByRole('button', { name: '打开打印窗口' }).click();
  await expect(page.locator('body')).toHaveAttribute('data-print-called', 'yes');
  const pdf = await page.pdf({
    path: testInfo.outputPath('sample.pdf'),
    preferCSSPageSize: true,
    printBackground: true,
  });
  expect(pdf.subarray(0, 4).toString()).toBe('%PDF');
});
test('长文和长二次备课在大字号下无溢出，文本不丢失', async ({ page }, testInfo) => {
  const draft = structuredClone(fixture);
  draft.data.coreCompetencies = '语言建构与运用，思维发展与提升。'.repeat(75);
  draft.data.process = [
    {
      ...draft.data.process[0],
      design: '围绕课文展开讨论，品味景物描写，关注学生的学习体验。'.repeat(32),
      secondary: '教学观察与记录。'.repeat(40),
    },
  ];
  await page.goto('/lesson-plans');
  await page.locator('input[type=file]').setInputFiles({
    name: 'long.json',
    mimeType: 'application/json',
    buffer: Buffer.from(JSON.stringify(draft)),
  });
  await page.getByRole('button', { name: '版式', exact: true }).click();
  await page.getByRole('slider', { name: '预览字号' }).fill('16');
  await expect(page.locator('.paper').nth(3)).toBeVisible();
  const rows = await page.locator('.paper').evaluateAll((papers) =>
    papers.map((p) => {
      const rect = p.getBoundingClientRect(),
        scale = rect.height / 1123;
      const content = p.querySelector('.approval-line') ?? p.querySelector('table:last-of-type')!;
      return {
        height: p.scrollHeight,
        bottom: (content.getBoundingClientRect().bottom - rect.top) / scale,
        footer: (p.querySelector('.paper-footer')!.getBoundingClientRect().top - rect.top) / scale,
      };
    }),
  );
  expect(rows.every((r) => r.height <= 1123 && r.bottom < r.footer - 8)).toBe(true);
  const text = (await page.locator('.print-text').allTextContents()).join('').replace(/\s/g, '');
  expect(text).toContain(draft.data.coreCompetencies);
  const secondary = (await page.locator('.secondary-cell .print-text').allTextContents())
    .join('')
    .replace(/\s/g, '');
  expect(secondary).toBe(draft.data.process[0].secondary);
  await page.pdf({
    path: testInfo.outputPath('long-content.pdf'),
    preferCSSPageSize: true,
    printBackground: true,
  });
  await fs.writeFile(testInfo.outputPath('pagination.json'), JSON.stringify(rows, null, 2));
});
test('桌面、平板和手机布局及未知路由', async ({ page }, testInfo) => {
  await page.goto('/lesson-plans');
  await expect(page.getByRole('textbox', { name: '课题', exact: true })).toBeVisible();
  for (const size of [
    { width: 1440, height: 900 },
    { width: 1024, height: 768 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(size);
    await page.screenshot({ path: testInfo.outputPath(`viewport-${size.width}.png`) });
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth)).toBe(
      true,
    );
  }
  await page.getByRole('button', { name: '预览教案', exact: true }).click();
  await expect(page.locator('.preview-pane')).toBeVisible();
  await page.screenshot({ path: testInfo.outputPath('mobile-preview.png') });
  await page.goto('/missing-route');
  await expect(page.getByRole('heading', { name: '页面不存在' })).toBeVisible();
});
test('损坏草稿不会被自动覆盖', async ({ page, context }) => {
  await context.addInitScript((key) => localStorage.setItem(key, 'invalid-json'), key);
  await page.goto('/lesson-plans');
  await expect(page.locator('.storage-alert')).toContainText('自动保存已暂停');
  await page.getByRole('textbox', { name: '课题', exact: true }).fill('临时编辑');
  await page.waitForTimeout(800);
  expect(await page.evaluate((key) => localStorage.getItem(key), key)).toBe('invalid-json');
});
test('无面包屑直接标题、编辑→配置→预览顺序与唯一折叠按钮', async ({ page }) => {
  await page.goto('/lesson-plans');
  await expect(page.getByRole('textbox', { name: '课题', exact: true })).toBeVisible();

  // 1) 教案页不再显示壳内「备课空间 > 教案工作台」面包屑，改由页面自渲染同级直接标题
  await expect(page.locator('.app-header .breadcrumb')).toBeHidden();
  const heading = page.getByRole('heading', { level: 1, name: '教案工作台', exact: true });
  await expect(heading).toBeVisible();
  const displayFont = await page.evaluate(() =>
    getComputedStyle(document.documentElement)
      .getPropertyValue('--font-display')
      .split(',')[0]
      .replace(/["']/g, '')
      .trim(),
  );
  const titleStyle = await heading.evaluate((el) => {
    const style = getComputedStyle(el);
    return {
      fontFamily: style.fontFamily,
      fontSize: style.fontSize,
      fontWeight: style.fontWeight,
      lineHeight: style.lineHeight,
      textAlign: style.textAlign,
    };
  });
  // 与 /co-writer、/reading 的 .space-header h1 同级：同一 --font-display 变量与同一套排版值
  expect(titleStyle.fontFamily).toContain(displayFont);
  expect(titleStyle.fontSize).toBe('24px');
  expect(titleStyle.fontWeight).toBe('600');
  expect(titleStyle.lineHeight).toBe('30px');
  expect(titleStyle.textAlign).toBe('left');

  // 2) DOM 阅读顺序与视觉顺序一致：编辑区 → 教案配置 → 教案预览
  const domOrder = await page
    .locator('.editor-panel, .outline-panel, .preview-pane')
    .evaluateAll((nodes) =>
      nodes.map((node) =>
        node.classList.contains('editor-panel')
          ? 'editor'
          : node.classList.contains('outline-panel')
            ? 'config'
            : 'preview',
      ),
    );
  expect(domOrder).toEqual(['editor', 'config', 'preview']);
  const editorBox = await page.locator('.editor-panel').boundingBox();
  const configBox = await page.locator('.outline-panel').boundingBox();
  const previewBox = await page.locator('.preview-pane').boundingBox();
  expect(editorBox && configBox && previewBox).toBeTruthy();
  expect(editorBox!.x).toBeLessThan(configBox!.x);
  expect(configBox!.x).toBeLessThan(previewBox!.x);
  expect(configBox!.width).toBeGreaterThan(0);

  // 3) 折叠控件唯一存在于编辑区顶部，aria 与状态一致
  await expect(page.locator('.outline-panel .icon-button')).toHaveCount(0);
  const toggle = page.locator('.editor-heading .config-toggle');
  await expect(toggle).toHaveCount(1);
  await expect(toggle).toHaveAttribute('aria-controls', 'lesson-config-panel');
  await expect(page.locator('#lesson-config-panel')).toBeVisible();
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await expect(toggle).toHaveAccessibleName('收起教案配置');

  // 4) 收起后配置面板只隐藏不卸载，展开回来表单值仍在，按钮自身焦点不丢
  await page.getByRole('button', { name: '版式', exact: true }).click();
  const slider = page.getByRole('slider', { name: '预览字号' });
  await slider.fill('16');
  await page.locator('#lesson-config-panel').evaluate((el) => el.setAttribute('data-probe', 'kept'));
  await toggle.press('Enter');
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await expect(toggle).toHaveAccessibleName('展开教案配置');
  await expect(page.locator('#lesson-config-panel')).toBeAttached();
  await expect(page.locator('#lesson-config-panel[data-probe="kept"]')).toBeHidden();
  await expect(page.locator('.editor-panel')).toBeVisible();
  await expect(toggle).toBeFocused();
  await toggle.press('Enter');
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await expect(page.locator('#lesson-config-panel[data-probe="kept"]')).toBeVisible();
  await expect(slider).toHaveValue('16');

  // 5) 连续快速点击只按奇偶切换，按钮始终存在且保持焦点
  for (let i = 0; i < 3; i += 1) await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await expect(page.locator('.editor-panel')).toBeVisible();
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'true');
  await expect(page.locator('#lesson-config-panel')).toBeVisible();
  await expect(toggle).toBeFocused();

  // 6) 减少动画时过渡被压制，切换仍然可用（观测：常规 0.2s → 减少动画后 0.01ms）
  const motionDuration = await page
    .locator('.app-shell')
    .evaluate((el) => getComputedStyle(el).transitionDuration);
  expect(Number.parseFloat(motionDuration)).toBeGreaterThan(0);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const reducedDuration = await page
    .locator('.app-shell')
    .evaluate((el) => getComputedStyle(el).transitionDuration);
  expect(Number.parseFloat(reducedDuration)).toBeLessThan(0.001);
  await toggle.click();
  await expect(toggle).toHaveAttribute('aria-expanded', 'false');
  await page.emulateMedia({ reducedMotion: 'no-preference' });

  // 7) 平板（1024×800）折叠按钮双向可用；手机（390×844）不出现点了没反馈的控制
  await page.setViewportSize({ width: 1024, height: 800 });
  await page.reload();
  const tabletToggle = page.locator('.editor-heading .config-toggle');
  await expect(tabletToggle).toBeVisible();
  if ((await tabletToggle.getAttribute('aria-expanded')) === 'false') await tabletToggle.click();
  await expect(page.locator('#lesson-config-panel')).toBeVisible();
  await expect((await page.locator('.outline-panel').boundingBox())!.width).toBeGreaterThan(0);
  await tabletToggle.click();
  await expect(tabletToggle).toHaveAttribute('aria-expanded', 'false');
  await expect(page.locator('#lesson-config-panel')).toBeHidden();
  await page.setViewportSize({ width: 390, height: 844 });
  await expect(page.locator('.editor-heading .config-toggle')).toBeHidden();
  await expect(page.getByRole('heading', { level: 1, name: '教案工作台', exact: true })).toBeVisible();
});

test('教案标题与导出菜单同一顶栏，四视口不重叠不溢出（UX-REGRESSION-FIX v1）', async ({
  page,
}) => {
  for (const viewport of [
    { width: 1920, height: 1080 },
    { width: 1440, height: 900 },
    { width: 1024, height: 800 },
    { width: 390, height: 844 },
  ]) {
    await page.setViewportSize(viewport);
    await page.goto('/lesson-plans');
    await expect(page.getByRole('textbox', { name: '课题', exact: true })).toBeVisible();

    // 1) 标题就在公共顶栏内，且与导出菜单同一行（不再有顶栏下方多出的一栏）
    const heading = page.getByRole('heading', { level: 1, name: '教案工作台', exact: true });
    await expect(heading).toBeVisible();
    expect(await page.locator('.lesson-page-head').count()).toBe(0);
    const geometry = await page.evaluate(() => {
      const header = document.querySelector('.app-header') as HTMLElement;
      const title = document.querySelector('.lesson-page-title') as HTMLElement;
      const exportBtn = [...document.querySelectorAll('button')].find((b) =>
        (b.textContent ?? '').includes('导出教案'),
      ) as HTMLElement | undefined;
      const editor = document.querySelector('.editor-panel') as HTMLElement;
      const brand = document.querySelector('.app-header .brand') as HTMLElement | null;
      const r = (el?: HTMLElement | null) => (el ? el.getBoundingClientRect() : null);
      const hb = r(header);
      const tb = r(title);
      const eb = r(exportBtn);
      const bb = r(brand);
      return {
        titleInsideHeader: !!header && !!title && header.contains(title),
        exportInsideHeader: !!header && !!exportBtn && header.contains(exportBtn),
        sameRow: !!(hb && tb && eb) && Math.abs(tb!.top + tb!.height / 2 - (eb!.top + eb!.height / 2)) < 2,
        verticallyInsideHeader: !!(hb && tb) && tb!.top >= hb!.top - 1 && tb!.bottom <= hb!.bottom + 1,
        noOverlap: !!(tb && eb) && tb!.right <= eb!.left,
        // 相邻控件必须有可见间隔（UX-REGRESSION-FIX v1 自查修复：390 下品牌与标题原本间隔 0px）
        brandToTitleGap: bb ? tb!.left - bb.right : null,
        titleToExportGap: eb ? eb.left - tb!.right : null,
        editorTop: editor ? Math.round(editor.getBoundingClientRect().top) : null,
        headerBottom: hb ? Math.round(hb.bottom) : null,
        pageOverflowX: document.documentElement.scrollWidth - document.documentElement.clientWidth,
      };
    });
    expect(geometry.titleInsideHeader, `标题应在顶栏内 @${viewport.width}`).toBe(true);
    expect(geometry.exportInsideHeader, `导出菜单应在顶栏内 @${viewport.width}`).toBe(true);
    expect(geometry.sameRow, `标题与导出应同一行 @${viewport.width}`).toBe(true);
    expect(geometry.verticallyInsideHeader).toBe(true);
    expect(geometry.noOverlap, `标题不得与导出重叠 @${viewport.width}`).toBe(true);
    expect(
      geometry.titleToExportGap,
      `标题与导出需有可见间隔 @${viewport.width}`,
    ).toBeGreaterThanOrEqual(2);
    if (geometry.brandToTitleGap !== null)
      expect(
        geometry.brandToTitleGap,
        `顶栏品牌与标题需有可见间隔 @${viewport.width}`,
      ).toBeGreaterThanOrEqual(2);
    expect(geometry.pageOverflowX, `不得横向溢出 @${viewport.width}`).toBeLessThanOrEqual(1);
    // 2) 内容区紧接顶栏，没有多出的一行标题空间
    expect(geometry.editorTop).toBe(geometry.headerBottom);

    // 3) 顶栏内不出现标题换行/截断导致的按钮挤压：导出菜单仍可打开
    await page.getByRole('button', { name: /导出教案/ }).click();
    await expect(page.getByRole('button', { name: /Word|导出 Word/ }).first()).toBeVisible();
    await page.keyboard.press('Escape');
  }
});
