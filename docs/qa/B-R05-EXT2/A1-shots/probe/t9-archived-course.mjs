// T9: 归档课程详情态抽查 + 与 after/ 一致性抽查（books 1920）
import { chromium } from 'playwright';
const OUT = 'H:/备份xuexi/智启课源/docs/qa/B-R05-EXT2/A1-shots';
const base = 'http://127.0.0.1:5174';
const browser = await chromium.launch({ headless: true, channel: 'msedge' });
try {
  const c = await browser.newContext({ viewport: { width: 1440, height: 900 } });
  const p = await c.newPage();
  await p.goto(base + '/courses', { waitUntil: 'domcontentloaded' });
  await p.getByRole('button', { name: '载入演示数据' }).click();
  await p.waitForTimeout(400);
  await p.goto(base + '/courses/demo-course-archived', { waitUntil: 'domcontentloaded' });
  await p.waitForTimeout(600);
  const st = await p.evaluate(() => {
    const h1 = document.querySelector('h1');
    return {
      title: h1 ? h1.textContent.trim() : null,
      hasArchivedChip: !!Array.from(document.querySelectorAll('.space-chip')).find((c2) => c2.textContent.trim() === '已归档'),
      archiveBtnText: (Array.from(document.querySelectorAll('.space-card-actions .space-button')).map((b) => b.textContent.trim())).find((t) => t.includes('恢复')),
      emptySyllabus: await0,
    };
  }).catch(() => null);
  // 上面 evaluate 内不能用 await——重新用纯值
  const st2 = await p.evaluate(() => {
    const h1 = document.querySelector('h1');
    return {
      title: h1 ? h1.textContent.trim() : null,
      hasArchivedChip: !!Array.from(document.querySelectorAll('.space-chip')).find((c2) => c2.textContent.trim() === '已归档'),
      hasRestoreBtn: !!Array.from(document.querySelectorAll('button')).find((b) => b.textContent.trim() === '恢复'),
      emptySyllabus: !!Array.from(document.querySelectorAll('.space-empty strong')).find((e) => e.textContent.includes('还没有大纲')),
    };
  });
  console.log('archived course:', JSON.stringify(st2));
  await p.screenshot({ path: `${OUT}/t9-archived-course.png` });
  await c.close();
} finally {
  await browser.close();
}
