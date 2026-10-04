import fs from 'node:fs';
import { test, expect, type Locator, type Page, type TestInfo } from '@playwright/test';

const origin = 'http://127.0.0.1:8001';
const qa = 'docs/qa/TEACHING-LOOP-G1-RESUME-B4-20261002/v00-browser';
// Collection is allowed before CTRL prepares the fresh, isolated seed. Execution requires it.
function readSeed() {
  return JSON.parse(fs.readFileSync(`${qa}/browser-seed.json`, 'utf8').replace(/^\ufeff/, '')) as {
    dataDir: string; paperId: string; paperRevisionId: string; title: string; richPaperFile: string;
    richPaperSha256: string; delimiters: { name: string; expectedText: string; expectedOperators: string[] }[];
  };
}
const today = () => { const n = new Date(); return `${n.getFullYear()}-${String(n.getMonth()+1).padStart(2,'0')}-${String(n.getDate()).padStart(2,'0')}`; };

test('G1 independent real roster changes and mapping/edit protection → newly confirmed score matrix', async ({ page, request }, testInfo) => {
  const seed = readSeed();
  const receipts: unknown[] = [], responses: unknown[] = [], confirms: unknown[] = [];
  const tag = `V00-G1-${Date.now()}`;
  async function api(path: string, method = 'GET', body?: unknown) {
    const result = await request.fetch(`${origin}/api/v1${path}`, { method, data: body });
    const value = await result.json(); receipts.push({ path, method, status: result.status(), body: value });
    expect(result.ok(), JSON.stringify(value)).toBeTruthy(); return value;
  }
  page.on('response', async result => {
    if (!result.url().includes('/api/v1/')) return;
    const req = result.request();
    responses.push({ url: new URL(result.url()).pathname, method: req.method(), status: result.status() });
  });
  page.on('request', req => {
    if (req.url().includes('/score-imports/') && req.url().endsWith('/confirm')) confirms.push(req.postDataJSON());
  });
  try {
    // Preparation uses the actual HTTP services, never a synthetic successful business response.
    const cls = await api('/classes', 'POST', { code: tag, name: `${tag}班`, schoolYear: '2026', gradeId: 'grade-1' });
    const target = await api('/classes', 'POST', { code: `${tag}-target`, name: `${tag}转入班`, schoolYear: '2026', gradeId: 'grade-1' });
    const kept = await api('/students', 'POST', { name: `${tag}甲`, studentNo: `${tag}-001`, classId: cls.id });
    const removed = await api('/students', 'POST', { name: `${tag}乙`, studentNo: `${tag}-002`, classId: cls.id });
    await page.goto('/assessments');
    await page.getByTestId(`assessments-class-${cls.id}`).click();
    await page.getByTestId('assessments-tab-paper').click();
    await page.getByTestId(`assessments-select-paper-${seed.paperId}`).click();
    await expect(page.getByTestId('assessments-paper-selected')).toContainText(seed.paperRevisionId);
    await page.getByTestId('assessments-tab-assessment').click();
    await page.getByLabel(`${kept.name} 出勤`, { exact: true }).selectOption('exempt');
    await page.getByLabel(`${kept.name} 人次序号`, { exact: true }).fill('3');
    await page.getByLabel(`参测 ${kept.name}`, { exact: true }).uncheck();
    await page.getByTestId('assessments-tab-roster').click();
    await page.getByLabel('学生姓名', { exact: true }).fill(`${tag}丙`);
    await page.getByLabel('学生学号', { exact: true }).fill(`${tag}-003`);
    await page.getByRole('button', { name: '添加学生', exact: true }).click();
    await expect(page.getByLabel('学生姓名', { exact: true })).toHaveValue('');
    await page.getByTestId('assessments-tab-assessment').click();
    await expect(page.getByLabel(`参测 ${tag}丙`, { exact: true })).toBeChecked();
    await expect(page.getByLabel(`参测 ${kept.name}`, { exact: true })).not.toBeChecked();
    await expect(page.getByLabel(`${kept.name} 出勤`, { exact: true })).toHaveValue('exempt');
    await expect(page.getByLabel(`${kept.name} 人次序号`, { exact: true })).toHaveValue('3');
    await page.getByTestId('assessments-tab-roster').click();
    await page.getByLabel('名单文件', { exact: true }).setInputFiles({ name: 'G1-独立名单.csv', mimeType: 'text/csv',
      buffer: Buffer.from(`\ufeff学号,姓名\n${tag}-004,${tag}丁\n`, 'utf8') });
    await page.getByRole('button', { name: '上传名单', exact: true }).click();
    await page.getByLabel('第 1 行处理', { exact: true }).selectOption('create');
    await page.getByRole('button', { name: '保存映射与行决策', exact: true }).click();
    await page.getByRole('button', { name: '确认名单', exact: true }).click();
    await expect(page.getByTestId('roster-import-result')).toContainText('名单已确认');
    await page.getByTestId('assessments-tab-assessment').click();
    await expect(page.getByLabel(`参测 ${tag}丁`, { exact: true })).toBeChecked();
    await expect(page.getByLabel(`参测 ${kept.name}`, { exact: true })).not.toBeChecked();
    await expect(page.getByLabel(`${kept.name} 出勤`, { exact: true })).toHaveValue('exempt');
    await expect(page.getByLabel(`${kept.name} 人次序号`, { exact: true })).toHaveValue('3');
    await page.getByTestId('assessments-tab-roster').click();
    await page.getByLabel('转班学生', { exact: true }).selectOption(removed.id);
    await page.getByLabel('转入班级', { exact: true }).selectOption(target.id);
    await page.getByLabel('转班日期', { exact: true }).fill(today());
    await page.getByRole('button', { name: '确认转班', exact: true }).click();
    await expect(page.getByTestId('roster-transfer-result')).toContainText('已转班');
    await page.getByTestId('assessments-tab-assessment').click();
    await expect(page.getByLabel(`参测 ${removed.name}`, { exact: true })).toHaveCount(0);
    await expect(page.getByTestId('assessments-assessments-panel')).toContainText('已撤销其参测选择及人次草稿');
    await expect(page.getByLabel(`参测 ${kept.name}`, { exact: true })).not.toBeChecked();
    await expect(page.getByLabel(`${kept.name} 出勤`, { exact: true })).toHaveValue('exempt');
    await expect(page.getByLabel(`${kept.name} 人次序号`, { exact: true })).toHaveValue('3');
    const currentRoster = await api(`/classes/${cls.id}/students`);
    expect(currentRoster.items.map((x: {name: string}) => x.name).sort()).toEqual([`${tag}甲`,`${tag}丙`,`${tag}丁`].sort());

    await page.getByLabel(`参测 ${kept.name}`, { exact: true }).check();
    await page.getByLabel(`${kept.name} 出勤`, { exact: true }).selectOption('present');
    await page.getByLabel(`${kept.name} 人次序号`, { exact: true }).fill('1');
    await page.getByLabel('施测标题', { exact: true }).fill(`${tag}施测`);
    await page.getByLabel('施测日期', { exact: true }).fill(today());
    await page.getByRole('button', { name: '创建施测', exact: true }).click();
    await expect(page.getByTestId('assessments-create-result')).toContainText('3 人次');
    const assessments = await api(`/assessments?classId=${encodeURIComponent(cls.id)}`);
    const assessment = assessments.items.find((x: {title: string}) => x.title === `${tag}施测`);
    expect(assessment).toBeTruthy();
    await page.getByTestId('assessments-tab-score').click();
    await page.getByLabel('成绩表格文件', { exact: true }).setInputFiles({ name: 'G1-独立成绩.csv', mimeType: 'text/csv',
      buffer: Buffer.from(`\ufeff学号,姓名,Q1,Q2,Q3,合计F,合计G\n${tag}-001,${tag}甲,2,2,5,9,9\n${tag}-003,${tag}丙,2,3,5,10,10\n${tag}-004,${tag}丁,0,3,5,8,8\n`, 'utf8') });
    await page.getByRole('button', { name: '上传并创建待校对批次', exact: true }).click();
    await expect(page.getByLabel('映射工作表名', { exact: true })).toHaveValue('CSV');
    await page.getByLabel('学号列', { exact: true }).fill('A');
    await page.getByLabel('姓名列', { exact: true }).fill('B');
    await page.getByLabel('Q1 列字母', { exact: true }).fill('C');
    await page.getByLabel('Q2 列字母', { exact: true }).fill('D');
    await page.getByLabel('Q3 列字母', { exact: true }).fill('E');
    await page.getByLabel('总分列', { exact: true }).fill('F');
    let release!: () => void, delivered!: () => void;
    const delayed = new Promise<void>(resolve => { release = resolve; });
    const reached = new Promise<void>(resolve => { delivered = resolve; });
    await page.route('**/api/v1/score-imports/*', async route => {
      const req = route.request();
      if (req.method() !== 'PATCH' || req.postDataJSON()?.mapping?.totalColumn !== 'F') { await route.continue(); return; }
      const actual = await route.fetch();
      expect(actual.status()).toBe(200); receipts.push({ case: 'R02-actual-F-response', body: await actual.json() });
      delivered(); await delayed; await route.fulfill({ response: actual });
    });
    await page.getByRole('button', { name: '保存映射并重算', exact: true }).click(); await reached;
    await page.getByLabel('总分列', { exact: true }).fill('G'); release();
    await expect(page.getByTestId('assessments-mapping-notice')).toContainText('新映射编辑已保留');
    await expect(page.getByLabel('总分列', { exact: true })).toHaveValue('G');
    await expect(page.getByTestId('assessments-mapping-dirty')).toBeVisible();
    await expect(page.getByTestId('score-goto-acknowledge')).toBeDisabled();
    await page.unroute('**/api/v1/score-imports/*');
    // Explicitly remove total mapping before changing a leaf; no original-total mismatch is concealed.
    await page.getByLabel('总分列', { exact: true }).fill('');
    await page.getByRole('button', { name: '保存映射并重算', exact: true }).click();
    await expect(page.getByTestId('assessments-mapping-dirty')).toHaveCount(0);
    await expect(page.getByTestId('score-goto-acknowledge')).toBeEnabled();
    await page.getByTestId('score-goto-acknowledge').click();
    await page.getByLabel('第 2 行 列 C 校正', { exact: true }).fill('1');
    await expect(page.getByText('有未保存的校对', { exact: true })).toBeVisible();
    await expect(page.getByTestId('score-open-confirm')).toHaveCount(0);
    await expect(page.getByTestId('score-goto-acknowledge')).toBeDisabled();
    expect(confirms).toHaveLength(0);
    await page.getByTestId('score-save-drafts').click();
    await expect(page.getByTestId('score-draft-notice')).toContainText('已保存校对');
    await expect(page.getByTestId('score-goto-acknowledge')).toBeEnabled();
    await page.getByTestId('score-goto-acknowledge').click();
    let lost = false;
    await page.route('**/api/v1/score-imports/*/confirm', async route => {
      const actual = await route.fetch();
      expect(actual.status()).toBe(200); receipts.push({ case: 'R01-actual-confirm', body: await actual.json() });
      if (!lost) { lost = true; await route.abort('failed'); } else await route.fulfill({ response: actual });
    });
    await page.getByTestId('score-open-confirm').click(); await page.getByTestId('score-confirm-submit').click();
    await expect(page.getByTestId('score-confirm-unknown')).toBeVisible();
    await expect(page.getByLabel('第 2 行 列 C 校正', { exact: true })).toBeDisabled();
    await page.getByTestId('score-confirm-submit').click();
    await expect(page.getByTestId('score-confirm-result')).toContainText('已确认（重放）');
    expect(confirms).toHaveLength(2); expect(confirms[1]).toEqual(confirms[0]);
    const revisions = await api(`/assessments/${assessment.assessmentId}/score-revisions`);
    expect(revisions.items).toHaveLength(1);
    const matrix = await api(`/score-revisions/${revisions.items[0].revisionId}/matrix?offset=0&limit=50`);
    expect(matrix.total).toBe(3);
    const row = matrix.rows.find((x: { participant: {name: string} }) => x.participant.name === kept.name);
    expect(row.cells.map((x: {scoreUnits: number}) => x.scoreUnits)).toEqual([100, 200, 500]);
    expect(row.participant.totalUnits).toBe(800);
    await page.getByTestId('assessments-tab-history').click();
    await expect(page.getByTestId('assessments-matrix')).toBeVisible();
    await expect(page.locator('[data-testid^="assessments-matrix-row-"]').filter({ hasText: kept.name })).toContainText('8 / 10 分');
    for (const viewport of [{width:1440,height:900},{width:1920,height:1080},{width:390,height:844}]) {
      await page.setViewportSize(viewport);
      expect(await page.evaluate(() => document.documentElement.scrollWidth - innerWidth)).toBeLessThanOrEqual(1);
      await page.screenshot({path:testInfo.outputPath(`g1-history-${viewport.width}.png`),fullPage:true});
    }
    await page.getByTestId('assessments-tab-score').focus();
    await expect(page.getByTestId('assessments-tab-score')).toBeFocused();
    await page.getByTestId('assessments-tab-score').press('Enter');
    await expect(page.getByTestId('assessments-tab-score')).toHaveAttribute('aria-selected','true');
    await page.emulateMedia({reducedMotion:'reduce'});
    expect(await page.evaluate(() => matchMedia('(prefers-reduced-motion: reduce)').matches)).toBeTruthy();
  } finally {
    fs.writeFileSync(testInfo.outputPath('business-receipts.json'),JSON.stringify({tag,receipts,responses,confirms},null,2));
  }
});

async function collectFormulaGeometry(formula: Locator) {
  return formula.evaluate(element => ({
    text: element.textContent,
    rect: element.getBoundingClientRect().toJSON(),
    parts: Array.from(element.querySelectorAll('mtext, mo')).map(part => ({
      tag: part.localName, text: part.textContent, rect: part.getBoundingClientRect().toJSON(),
      color: getComputedStyle(part).color, visibility: getComputedStyle(part).visibility,
    })),
  }));
}

async function screenshotLayout(page: Page, testInfo: TestInfo, title: string, width: number, height: number) {
  await page.setViewportSize({ width, height });
  const layout = await page.evaluate(() => ({
    width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
    activeElement: document.activeElement?.getAttribute('data-testid'),
    offenders: Array.from(document.querySelectorAll<HTMLElement>('.assessments-page *'))
      .filter(element => element.getBoundingClientRect().right > innerWidth + 1)
      .map(element => ({ tag: element.tagName, className: element.className,
        width: element.getBoundingClientRect().width, right: element.getBoundingClientRect().right,
        text: element.textContent?.slice(0, 80) })).slice(0, 30),
  }));
  fs.writeFileSync(testInfo.outputPath(`${title}-${width}-layout.json`), JSON.stringify(layout, null, 2));
  expect(layout.scrollWidth - layout.width, JSON.stringify(layout)).toBeLessThanOrEqual(1);
  await page.screenshot({ path: testInfo.outputPath(`${title}-${width}.png`), fullPage: true });
  return layout;
}

test('R08 actual DOCX → paper review/confirmation renders every OMML argument and separator; three viewports, keyboard, actual reduced motion', async ({ page, request }, testInfo) => {
  const seed = readSeed();
  const receipts: unknown[] = [], renderings: unknown[] = [], layouts: unknown[] = [];
  const tag = `V00-G1R-R08-${Date.now()}`;
  async function api(path: string, method = 'GET', body?: unknown) {
    const response = await request.fetch(`${origin}/api/v1${path}`, { method, data: body });
    const value = await response.json();
    receipts.push({ path, method, status: response.status(), body: value });
    expect(response.ok(), JSON.stringify(value)).toBeTruthy();
    return value;
  }
  let motion: unknown;
  try {
    const point = await api('/knowledge-points', 'POST', { subjectId: 'math', code: tag, name: 'R08 真实原卷公式校对' });
    const cls = await api('/classes', 'POST', { code: `${tag}-motion`, name: 'R08 动画校验班', schoolYear: '2026', gradeId: 'grade-1' });
    await page.goto('/assessments');
    // Existing UI class hover: observe actual browser transitions, without changing DOM or CSS.
    const target = page.getByTestId(`assessments-class-${cls.id}`);
    await expect(target).toBeVisible();
    await expect(target).toHaveAttribute('aria-pressed', 'false');
    await page.emulateMedia({ reducedMotion: 'no-preference' });
    await page.mouse.move(0, 0);
    const normalBefore = await target.evaluate(element => getComputedStyle(element).backgroundColor);
    const normalPromise = target.evaluate(element => new Promise(resolve => {
      element.addEventListener('pointerenter', () => requestAnimationFrame(() => {
        const style = getComputedStyle(element);
        resolve({ background: style.backgroundColor, transitionDuration: style.transitionDuration,
          animations: element.getAnimations().map(animation => ({ playState: animation.playState,
            duration: animation.effect?.getComputedTiming().duration })) });
      }), { once: true });
    }));
    await target.hover();
    const normal = await normalPromise as { background: string; transitionDuration: string; animations: {playState: string; duration: number}[] };
    expect(normal.transitionDuration.split(',').some(value => parseFloat(value) > 0)).toBe(true);
    expect(normal.animations.some(animation => animation.playState === 'running' && Number(animation.duration) > 0)).toBe(true);
    await page.mouse.move(0, 0);
    await page.emulateMedia({ reducedMotion: 'reduce' });
    const reducedBefore = await target.evaluate(element => getComputedStyle(element).backgroundColor);
    const reducedPromise = target.evaluate(element => new Promise(resolve => {
      element.addEventListener('pointerenter', () => requestAnimationFrame(() => {
        const first = getComputedStyle(element);
        const background = first.backgroundColor;
        const durations = first.transitionDuration;
        const animations = element.getAnimations().map(animation => ({ playState: animation.playState,
          duration: animation.effect?.getComputedTiming().duration }));
        requestAnimationFrame(() => resolve({ background, afterNextFrame: getComputedStyle(element).backgroundColor,
          transitionDuration: durations, animations }));
      }), { once: true });
    }));
    await target.hover();
    const reduced = await reducedPromise as {background: string; afterNextFrame: string; transitionDuration: string; animations: {playState: string; duration: number}[]};
    expect(reduced.transitionDuration.split(',').every(value => parseFloat(value) <= 0.00002)).toBe(true);
    expect(reduced.animations.filter(animation => animation.playState === 'running')).toHaveLength(0);
    expect(reduced.background).not.toBe(reducedBefore);
    expect(reduced.background).toBe(reduced.afterNextFrame);
    motion = { normalBefore, normal, reducedBefore, reduced };
    fs.writeFileSync(testInfo.outputPath('actual-reduced-motion.json'), JSON.stringify(motion, null, 2));

    // Actual keyboard Tab navigation with the repository's visible focus ring.
    await page.getByTestId('assessments-tab-roster').focus();
    await page.keyboard.press('Tab');
    const paperTab = page.getByTestId('assessments-tab-paper');
    await expect(paperTab).toBeFocused();
    const focus = await paperTab.evaluate(element => ({ outlineStyle: getComputedStyle(element).outlineStyle,
      outlineWidth: getComputedStyle(element).outlineWidth, outlineColor: getComputedStyle(element).outlineColor,
      matchesFocusVisible: element.matches(':focus-visible') }));
    expect(focus.matchesFocusVisible).toBe(true);
    expect(focus.outlineStyle).not.toBe('none');
    expect(parseFloat(focus.outlineWidth)).toBeGreaterThanOrEqual(2);
    fs.writeFileSync(testInfo.outputPath('keyboard-focus.json'), JSON.stringify(focus, null, 2));
    await page.screenshot({ path: testInfo.outputPath('keyboard-visible-focus.png'), fullPage: true });
    await page.keyboard.press('Enter');
    await expect(paperTab).toHaveAttribute('aria-selected', 'true');

    await page.getByLabel('原卷学科', { exact: true }).selectOption('math');
    await page.getByLabel('导入原卷标题', { exact: true }).fill(`${tag} 富内容卷`);
    await page.getByLabel('原卷DOCX文件', { exact: true }).setInputFiles({ name: 'G1R-真实OMML原卷.docx',
      mimeType: 'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
      buffer: fs.readFileSync(seed.richPaperFile) });
    const importedResponse = page.waitForResponse(response => response.url().endsWith('/api/v1/paper-imports') && response.request().method() === 'POST');
    await page.getByRole('button', { name: '上传原卷并校对', exact: true }).click();
    const imported = await importedResponse;
    expect(imported.status()).toBe(201);
    const actualImport = await imported.json();
    receipts.push({ path: '/paper-imports', method: 'POST', status: imported.status(), body: actualImport,
      sourceFileSha256: seed.richPaperSha256 });
    await expect(page.getByTestId('paper-import-review')).toBeVisible();
    const source = page.getByRole('region', { name: '完整原文块', exact: true });
    await expect(source).toContainText('原文合并表头');
    await expect(source.getByRole('img').first()).toBeVisible();
    expect(await source.getByRole('img').first().evaluate(element => (element as HTMLImageElement).naturalWidth)).toBeGreaterThan(0);
    for (const viewport of [{width:1440,height:900},{width:1920,height:1080},{width:390,height:844}]) {
      await page.setViewportSize(viewport);
      for (const delimiter of seed.delimiters) {
        const formula = source.locator('math[aria-label="原始公式"]').filter({ hasText: delimiter.expectedText });
        await expect(formula).toHaveCount(1);
        await expect(formula).toBeVisible();
        await expect(formula.locator('mtext')).toHaveText(['x', 'y']);
        await expect(formula.locator('mo')).toHaveText(delimiter.expectedOperators);
        const geometry = await collectFormulaGeometry(formula);
        const parts = geometry.parts;
        expect(parts.map(part => part.text)).toEqual([delimiter.expectedOperators[0], 'x', delimiter.expectedOperators[1], 'y', delimiter.expectedOperators[2]]);
        for (const part of parts) {
          expect(part.rect.width, `${delimiter.name}/${part.text}`).toBeGreaterThan(0);
          expect(part.rect.height).toBeGreaterThan(0);
          expect(part.visibility).toBe('visible');
        }
        expect(parts[1].rect.x).toBeLessThan(parts[2].rect.x);
        expect(parts[2].rect.x).toBeLessThan(parts[3].rect.x);
        renderings.push({ viewport, case: delimiter.name, expectedText: delimiter.expectedText, geometry });
        await formula.screenshot({ path: testInfo.outputPath(`r08-${delimiter.name}-${viewport.width}.png`) });
      }
      layouts.push(await screenshotLayout(page, testInfo, 'r08-paper-review', viewport.width, viewport.height));
    }
    await page.setViewportSize({width:1440,height:900});
    for (const no of ['1', '2', '3']) await page.getByLabel(`题 ${no} 知识点`, { exact: true }).selectOption([point.id]);
    await page.getByTestId('paper-save-draft').click();
    await expect(page.getByTestId('paper-confirm')).toBeEnabled();
    await page.getByTestId('paper-confirm').click();
    await expect(page.getByTestId('paper-confirm-result')).toContainText('已确认原卷');
    const fixed = await api(`/papers/${actualImport.paper.paperId}/revisions/${actualImport.revision.paperRevisionId}/content`);
    expect(fixed.state).toBe('confirmed');
    expect(fixed.totalScoreUnits).toBe(1000);
    expect(fixed.items.filter((item: {isScored:boolean}) => item.isScored).map((item: {maxScoreUnits:number}) => item.maxScoreUnits)).toEqual([200, 300, 500]);
    const fixedSource = page.getByRole('region', { name: '完整原文块', exact: true });
    for (const delimiter of seed.delimiters) {
      await expect(fixedSource.locator('math[aria-label="原始公式"]').filter({ hasText: delimiter.expectedText })).toBeVisible();
    }
    await page.screenshot({ path: testInfo.outputPath('r08-fixed-confirmed-1440.png'), fullPage: true });
    await testInfo.attach('rich-paper-and-renderings.json', { contentType: 'application/json',
      body: Buffer.from(JSON.stringify({ seed, receipts, renderings, layouts, motion }, null, 2)) });
  } finally {
    fs.writeFileSync(testInfo.outputPath('r08-real-paper-receipts.json'), JSON.stringify({ tag, seed, receipts, renderings, layouts, motion }, null, 2));
  }
});
