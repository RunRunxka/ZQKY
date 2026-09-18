// T8b: R-11 三态回归（修正种子键名与资源字段：KB_KEY=zqky.replica.knowledge.v1，资源带 position/addedAt）
import { chromium } from 'playwright';
import fs from 'node:fs';
const OUT = 'H:/备份xuexi/智启课源/docs/qa/B-R05-EXT2/A1-shots';
const base = 'http://127.0.0.1:5174';
const log = [];
const browser = await chromium.launch({ headless: true, channel: 'msedge' });
const COURSE = {
  id: 'seed-course-fault', name: '三态回归课程', description: 'A1 验收', color: 'blue', instructions: '学习约定文本',
  syllabus: [{ id: 'u1', position: 0, title: '单元一', topics: ['主题A'], covered: false }],
  resources: [{ id: 'r1', kind: 'knowledge_base', refId: 'kb-1', label: '课程标准库', position: 0, addedAt: '2026-09-08T00:00:00.000Z' }],
  status: 'active', createdAt: '2026-09-08T00:00:00.000Z', updatedAt: '2026-09-08T00:00:00.000Z',
};
async function seed(page, kbRaw) {
  await page.addInitScript(({ course, kb }) => {
    if (!window.localStorage.getItem('zhiqikeyuan:courses')) {
      window.localStorage.setItem('zhiqikeyuan:courses', JSON.stringify([course]));
    }
    if (kb === null) window.localStorage.removeItem('zqky.replica.knowledge.v1');
    else window.localStorage.setItem('zqky.replica.knowledge.v1', kb);
  }, { course: COURSE, kb: kbRaw });
}
async function runCase(name, kbRaw, checks) {
  const c = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await c.newPage();
  await seed(p, kbRaw);
  await p.goto(base + '/courses/seed-course-fault', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(700);
  const res = await checks(p);
  log.push({ case: name, ...res });
  console.log(name, JSON.stringify(res));
  await p.screenshot({ path: `${OUT}/t8-${name}.png` });
  await c.close();
}
try {
  // Case 1: 目标已删除——KB store 正常（空数组），refId 不存在
  await runCase('missing-target', '[]', async (p) => ({
    unavailableSuffix: await p.getByText('（不可用：目标已删除或未载入）').count(),
    errorBanner: await p.getByText('资源目录读取失败', { exact: false }).count(),
    syllabusVisible: await p.getByText(/大纲（0\/1 已完成/).count(),
  }));
  // Case 2: 目录读取失败——KB localStorage 损坏 JSON
  await runCase('dir-read-fail', '{corrupted!!', async (p) => ({
    unknownSuffix: await p.getByText('（目录读取失败，暂无法确认）').count(),
    errorBanner: await p.getByText('资源目录读取失败', { exact: false }).count(),
    retryBtn: await p.getByRole('button', { name: '重试' }).count(),
    syllabusVisible: await p.getByText(/大纲（0\/1 已完成/).count(),
    bannerText: await p.locator('.space-banner.error').first().innerText().catch(() => null),
  }));
  // Case 3: 可用——KB 正常且 refId 匹配
  await runCase('available-target', JSON.stringify([{ id: 'kb-1', name: '课程标准库', description: '', createdAt: '2026-09-08T00:00:00.000Z', updatedAt: '2026-09-08T00:00:00.000Z', sources: [] }]), async (p) => ({
    linkLabel: await p.locator('a.courses-resource-label').count(),
    unavailableSuffix: await p.getByText('（不可用：目标已删除或未载入）').count(),
  }));
} finally {
  await browser.close();
  fs.writeFileSync(`${OUT}/t8b-r11-faults.json`, JSON.stringify(log, null, 2));
}
