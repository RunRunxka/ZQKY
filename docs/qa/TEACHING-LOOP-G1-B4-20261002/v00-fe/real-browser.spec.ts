import fs from 'node:fs';
import { test, expect } from '@playwright/test';

const origin = 'http://127.0.0.1:8001';
const qa = 'docs/qa/TEACHING-LOOP-G1-B4-20261002/v00-fe';
const seed = JSON.parse(fs.readFileSync('docs/qa/TEACHING-LOOP-G1-B4-20261002/root/browser-seed.json', 'utf8').replace(/^\ufeff/, ''));
const today = () => { const n = new Date(); return `${n.getFullYear()}-${String(n.getMonth()+1).padStart(2,'0')}-${String(n.getDate()).padStart(2,'0')}`; };

test('G1 independent real roster changes and mapping/edit protection → newly confirmed score matrix', async ({ page, request }, testInfo) => {
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
    await page.getByLabel(`参测 ${kept.name}`, { exact: true }).uncheck();
    await page.getByLabel(`${kept.name} 出勤`, { exact: true }).selectOption('exempt');
    await page.getByLabel(`${kept.name} 人次序号`, { exact: true }).fill('3');
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
    fs.writeFileSync(`${qa}/browser-receipts.json`,JSON.stringify({tag,receipts,responses,confirms},null,2));
  }
});
