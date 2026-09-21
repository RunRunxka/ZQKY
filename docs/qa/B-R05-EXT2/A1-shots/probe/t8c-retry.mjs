// T8c: R-11 重试链路——目录失败 → 重试仍失败 → 数据修复后重试恢复
import { chromium } from 'playwright';
import fs from 'node:fs';
const OUT = 'H:/备份xuexi/智启课源/docs/qa/B-R05-EXT2/A1-shots';
const base = 'http://127.0.0.1:5174';
const log = [];
const browser = await chromium.launch({ headless: true, channel: 'msedge' });
const COURSE = {
  id: 'seed-course-fault', name: '三态回归课程', description: 'A1 验收', color: 'blue', instructions: '',
  syllabus: [{ id: 'u1', position: 0, title: '单元一', topics: [], covered: false }],
  resources: [{ id: 'r1', kind: 'knowledge_base', refId: 'kb-1', label: '课程标准库', position: 0, addedAt: '2026-09-08T00:00:00.000Z' }],
  status: 'active', createdAt: '2026-09-08T00:00:00.000Z', updatedAt: '2026-09-08T00:00:00.000Z',
};
try {
  const c = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await c.newPage();
  await p.addInitScript((course) => {
    if (!window.localStorage.getItem('zhiqikeyuan:courses')) {
      window.localStorage.setItem('zhiqikeyuan:courses', JSON.stringify([course]));
    }
    window.localStorage.setItem('zqky.replica.knowledge.v1', '{corrupted!!');
  }, COURSE);
  await p.goto(base + '/courses/seed-course-fault', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(700);
  const fail1 = await p.getByText('资源目录读取失败', { exact: false }).count();
  // 原始损坏数据逐字节未变（store 不清数据）
  const rawAfterFail = await p.evaluate(() => window.localStorage.getItem('zqky.replica.knowledge.v1'));
  // 重试（数据仍损坏）→ 仍失败
  await p.getByRole('button', { name: '重试' }).click();
  await p.waitForTimeout(400);
  const fail2 = await p.getByText('资源目录读取失败', { exact: false }).count();
  log.push({ step: 'fail + retry-fail', fail1, fail2, rawPreserved: rawAfterFail === '{corrupted!!' });
  console.log('fail->retry-fail:', fail1, fail2, 'raw preserved:', rawAfterFail === '{corrupted!!');
  // 修复数据（模拟用户到别处修复后回来）→ 重试恢复
  await p.evaluate(() => {
    window.localStorage.setItem('zqky.replica.knowledge.v1', JSON.stringify([{ id: 'kb-1', name: '课程标准库', description: '', createdAt: '2026-09-08T00:00:00.000Z', updatedAt: '2026-09-08T00:00:00.000Z', sources: [] }]));
  });
  await p.getByRole('button', { name: '重试' }).click();
  await p.waitForTimeout(500);
  const okAfterFix = await p.locator('a.courses-resource-label').count();
  const errAfterFix = await p.getByText('资源目录读取失败', { exact: false }).count();
  log.push({ step: 'fix + retry-recover', okAfterFix, errAfterFix });
  console.log('fix->recover:', okAfterFix, 'errors:', errAfterFix);
  await p.screenshot({ path: `${OUT}/t8c-retry-recovered.png` });
  await c.close();
} finally {
  await browser.close();
  fs.writeFileSync(`${OUT}/t8c-retry.json`, JSON.stringify(log, null, 2));
}
