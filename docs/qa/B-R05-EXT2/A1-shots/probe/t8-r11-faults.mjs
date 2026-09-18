// T8: R-11 三态回归——目录读取失败 vs 目标已删除 vs 可用，重试可用，不阻断正文
import { chromium } from 'playwright';
import fs from 'node:fs';
const OUT = 'H:/备份xuexi/智启课源/docs/qa/B-R05-EXT2/A1-shots';
const base = 'http://127.0.0.1:5174';
const log = [];
const browser = await chromium.launch({ headless: true, channel: 'msedge' });
// courses-store 的资源目录读取依赖 windowlocalStorage/zhiqikeyuan 命名空间与知识库 store。
// 目录读取失败的触发方式：seed 课程引用 refId 不存在 → 「不可用」；目录读取失败需要 KB store 本身损坏。
// 参照 course-resource-faults.spec.ts 思路：损坏知识库 localStorage 使 readResourceDirectories 抛错。
async function runCase(name, seedSetup, checks) {
  const c = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await c.newPage();
  await seedSetup(c, p);
  await p.goto(base + '/courses/seed-course-fault', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(700);
  const res = await checks(p);
  log.push({ case: name, ...res });
  console.log(name, JSON.stringify(res));
  await p.screenshot({ path: `${OUT}/t8-${name}.png` });
  await c.close();
}
const courseBase = (resources) => [{
  id: 'seed-course-fault', name: '三态回归课程', description: 'A1 验收', color: 'blue', instructions: '', status: 'active',
  createdAt: '2026-09-08T01:00:00.000Z', updatedAt: '2026-09-08T02:00:00.000Z',
  syllabus: [{ id: 'u1', position: 0, title: '单元甲', topics: [], covered: false }],
  resources,
}];
try {
  // Case 1: 目标已删除（知识库 store 正常但 refId 不存在）
  await runCase('missing-target',
    async (c) => {
      await c.addInitScript(() => {
        window.localStorage.setItem('zhiqikeyuan:knowledge-bases', JSON.stringify([]));
      });
      await c.addInitScript((courses) => {
        window.localStorage.setItem('zhiqikeyuan:courses', JSON.stringify(courses));
      }, courseBase([{ id: 'r1', kind: 'knowledge_base', refId: 'kb-not-exist', label: '课程标准库' }]));
    },
    async (p) => ({
      unavailableSuffix: await p.getByText('（不可用：目标已删除或未载入）').count(),
      errorBanner: await p.getByText('资源目录读取失败', { exact: false }).count(),
      syllabusVisible: await p.getByText(/大纲（0\/1 已完成/).count(),
    }));

  // Case 2: 目录读取失败（知识库 localStorage 损坏 JSON）
  await runCase('dir-read-fail',
    async (c) => {
      await c.addInitScript(() => {
        window.localStorage.setItem('zhiqikeyuan:knowledge-bases', '{corrupted!!');
      });
      await c.addInitScript((courses) => {
        window.localStorage.setItem('zhiqikeyuan:courses', JSON.stringify(courses));
      }, courseBase([{ id: 'r1', kind: 'knowledge_base', refId: 'kb-x', label: '课程标准库' }]));
    },
    async (p) => ({
      unknownSuffix: await p.getByText('（目录读取失败，暂无法确认）').count(),
      errorBanner: await p.getByText('资源目录读取失败', { exact: false }).count(),
      retryBtn: await p.getByRole('button', { name: '重试' }).count(),
      syllabusVisible: await p.getByText(/大纲（0\/1 已完成/).count(),
    }));

  // Case 3: 可用（KB 正常且 refId 匹配）——检查 label 是链接
  await runCase('available-target',
    async (c) => {
      await c.addInitScript(() => {
        window.localStorage.setItem('zhiqikeyuan:knowledge-bases', JSON.stringify([{ id: 'kb-ok', name: '可用知识库', description: '', createdAt: '2026-09-08T00:00:00.000Z', updatedAt: '2026-09-08T00:00:00.000Z', sources: [] }]));
      });
      await c.addInitScript((courses) => {
        window.localStorage.setItem('zhiqikeyuan:courses', JSON.stringify(courses));
      }, courseBase([{ id: 'r1', kind: 'knowledge_base', refId: 'kb-ok', label: '可用知识库' }]));
    },
    async (p) => ({
      linkLabel: await p.locator('a.courses-resource-label').count(),
      unavailableSuffix: await p.getByText('（不可用：目标已删除或未载入）').count(),
    }));
} finally {
  await browser.close();
  fs.writeFileSync(`${OUT}/t8-r11-faults.json`, JSON.stringify(log, null, 2));
}
