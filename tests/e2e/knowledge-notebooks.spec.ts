import { test, expect, type Page } from '@playwright/test';

/**
 * S5-B 教材资料库与笔记本浏览器回归：
 * 资料库列表（演示载入幂等/新建与重名拒绝/检索引擎页签）、
 * 资料库详情（登记文档仅元信息/外部来源登记与移除/索引显式空态/改名同步 URL/删除）、
 * 知识库解析与索引显式模拟（登记后自动模拟解析/取消/失败重试/刷新恢复/旧数据兼容）、
 * 笔记本（默认笔记本归集/记录展开与编辑/移动与复制/新建/导出/删除笔记本记录回退/深链报错）。
 * 全部使用隔离上下文与显式种子数据，不读取真实用户数据。
 */

type KbSeed = {
  id: string;
  name: string;
  description: string;
  isDefault?: boolean;
  docs?: Record<string, unknown>[];
  sources?: Record<string, unknown>[];
  indexVersions?: Record<string, unknown>[];
};

const KB_DETAIL_SEED: KbSeed[] = [
  {
    id: 'seed-kb-1',
    name: '课程标准库',
    description: '详情页回归种子库',
    isDefault: true,
    docs: [
      {
        id: 'seed-doc-1',
        name: '课程标准摘录一.md',
        size: 1024,
        registeredAt: '2026-09-08T01:00:00.000Z',
      },
      {
        id: 'seed-doc-2',
        name: '课程标准摘录二.md',
        size: 2048,
        registeredAt: '2026-09-08T01:05:00.000Z',
      },
    ],
    sources: [],
  },
];

/** 空库种子：登记后自动模拟解析会生成首个索引版本 */
const KB_EMPTY_SEED: KbSeed[] = [
  { id: 'seed-kb-empty', name: '空种子库', description: '空库种子', docs: [], sources: [] },
];

/** 缺 status/indexVersions 的旧数据种子：读取后应归一化为 registered */
const KB_LEGACY_SEED: KbSeed[] = [
  {
    id: 'seed-kb-legacy',
    name: '旧数据种子库',
    description: '缺 status/indexVersions 的旧数据',
    docs: [
      {
        id: 'legacy-doc-1',
        name: '旧文档一.md',
        size: 1000,
        registeredAt: '2026-09-08T01:00:00.000Z',
      },
    ],
    sources: [],
  },
];

/** 进行中种子：进入页面时 resumeKbIngests 会重新推进 parsing 文档 */
const KB_PARSING_SEED: KbSeed[] = [
  {
    id: 'seed-kb-parsing',
    name: '进行中种子库',
    description: '进行中解析的种子',
    docs: [
      {
        id: 'parsing-doc-1',
        name: '解析中文档.md',
        size: 2048,
        registeredAt: '2026-09-08T01:00:00.000Z',
        status: 'parsing',
        progress: { stage: '解析中', percent: 35 },
      },
    ],
    sources: [],
  },
];

const NOTEBOOKS_SEED = [
  {
    id: 'nb-monthly',
    name: '月度整理',
    description: '月度回顾用',
    color: 'green',
    createdAt: '2026-09-08T01:00:00.000Z',
    updatedAt: '2026-09-08T01:00:00.000Z',
  },
];

const RECORDS_SEED = [
  {
    id: 'rec-1',
    type: 'research_report',
    title: '演示研究报告',
    summary: '演示摘要',
    userQuery: '什么是分数？',
    content: '# 报告正文',
    createdAt: '2026-09-08T01:00:00.000Z',
    updatedAt: '2026-09-08T01:10:00.000Z',
    metadata: { sessionId: 'seed-session-1' },
  },
  {
    id: 'rec-2',
    notebookId: 'nb-monthly',
    type: 'chat',
    title: '月度对话记录',
    content: '对话内容',
    createdAt: '2026-09-08T02:00:00.000Z',
    updatedAt: '2026-09-08T02:10:00.000Z',
  },
];

/** 仅首次写入种子：保证 reload 后不把进行中的模拟推进状态重置回初始种子 */
async function seedKnowledge(page: Page, entries: KbSeed[]) {
  await page.addInitScript((value) => {
    if (!window.localStorage.getItem('zqky.replica.knowledge.v1')) {
      window.localStorage.setItem('zqky.replica.knowledge.v1', JSON.stringify(value));
    }
  }, entries);
}

async function seedNotebookData(page: Page, notebooks: typeof NOTEBOOKS_SEED, records: typeof RECORDS_SEED) {
  await page.addInitScript(({ notebooks, records }) => {
    window.localStorage.setItem('zhiqikeyuan:notebooks', JSON.stringify(notebooks));
    window.localStorage.setItem('zhiqikeyuan:notebook-entries', JSON.stringify(records));
  }, { notebooks, records });
}

/**
 * 分区导航按钮：限定在分区 nav 内并 exact 匹配。
 * 避免与详情页工具条按钮（如「全部解析并索引」包含子串「索引」）产生 strict mode 歧义。
 */
function gotoSection(page: Page, name: string) {
  return page.locator('nav[aria-label="知识库分区"]').getByRole('button', { name, exact: true });
}

test('教材资料库列表：演示载入幂等、新建与重名拒绝、检索引擎页签', async ({ page }) => {
  await page.goto('/knowledge-bases');
  await expect(page.getByRole('heading', { name: '教材资料库' })).toBeVisible();
  await expect(page.getByText('还没有知识库')).toBeVisible();
  // 样式回归：直达路由必须已加载 space 设计语言（防止 CSS 断链）
  const display = await page
    .locator('.space-page')
    .evaluate((el) => getComputedStyle(el).display);
  expect(display).toBe('flex');

  // 演示载入（幂等）
  await page.getByRole('button', { name: '载入演示数据' }).click();
  await expect(page.getByRole('status').filter({ hasText: '已载入演示知识库' })).toBeVisible();
  await expect(page.locator('.space-persona-card', { hasText: '课程标准库' })).toBeVisible();
  await expect(page.locator('.space-persona-card', { hasText: '教学设计案例库' })).toBeVisible();
  await expect(page.locator('.space-persona-card')).toHaveCount(2);
  await page.getByRole('button', { name: '载入演示数据' }).click();
  await expect(page.locator('.space-persona-card')).toHaveCount(2);

  // 新建
  await page.getByRole('button', { name: '新建知识库' }).click();
  const dialog = page.getByRole('dialog', { name: '新建知识库' });
  await dialog.getByLabel('名称').fill('测试资料库甲');
  await dialog.getByLabel('简介').fill('浏览器回归用');
  await dialog.getByRole('button', { name: '创建' }).click();
  await expect(
    page.getByRole('status').filter({ hasText: '已创建知识库「测试资料库甲」' }),
  ).toBeVisible();
  await expect(page.locator('.space-persona-card')).toHaveCount(3);

  // 重名拒绝
  await page.getByRole('button', { name: '新建知识库' }).click();
  const dialog2 = page.getByRole('dialog', { name: '新建知识库' });
  await dialog2.getByLabel('名称').fill('测试资料库甲');
  await dialog2.getByRole('button', { name: '创建' }).click();
  await expect(dialog2.getByRole('alert')).toContainText('已存在同名知识库');
  await dialog2.getByRole('button', { name: '取消' }).click();

  // 检索引擎页签：分组展示且显式标注未接入/演示
  await page.getByRole('tab', { name: /检索引擎/ }).click();
  await expect(page.getByText('内置检索（未接入）')).toBeVisible();
  await expect(page.getByText('LightRAG（演示）')).toBeVisible();
  await expect(page.getByText('WeKnora（演示）')).toBeVisible();
  await expect(page.getByText('IMA 云检索（演示）')).toBeVisible();
  await expect(page.getByText('Obsidian')).toBeVisible();
  await expect(page.getByText('MarginNote 4')).toBeVisible();
});

test('知识库详情：登记文档、来源登记/移除、索引空态、改名同步 URL 与删除', async ({ page }) => {
  await seedKnowledge(page, KB_DETAIL_SEED);
  await page.goto(`/knowledge-bases/${encodeURIComponent('课程标准库')}`);
  await expect(page.getByRole('heading', { name: /课程标准库/ })).toBeVisible();
  await expect(page.getByText('默认库', { exact: true })).toBeVisible();

  // 文档分区：种子文档无 status → 归一化为 registered，带"未解析 · 未索引"标记
  await expect(page.locator('.space-session-card')).toHaveCount(2);
  await expect(page.locator('.space-chip', { hasText: '未解析 · 未索引' })).toHaveCount(2);

  // 索引分区：显式模拟说明 + 未产生版本时空态（在登记触发模拟前验证）
  await gotoSection(page, '索引').click();
  await expect(page.getByText('还没有索引版本')).toBeVisible();
  await expect(page.locator('.space-empty', { hasText: '还没有索引版本' })).toContainText(
    '真实向量检索服务未接入',
  );

  // 登记文档（仅元信息，登记后启动显式模拟解析）
  await gotoSection(page, '登记文档').click();
  await page.getByLabel('选择要登记的文件').setInputFiles({
    name: '课堂练习-分数.md',
    mimeType: 'text/markdown',
    buffer: Buffer.from('# 练习'),
  });
  await expect(page.getByRole('status').filter({ hasText: '已登记 1 个文档' })).toBeVisible();
  await gotoSection(page, '文档').click();
  await expect(page.locator('.space-session-card', { hasText: '课堂练习-分数.md' })).toBeVisible();
  await expect(page.locator('.space-session-card')).toHaveCount(3);

  // 外部来源：登记与移除（不同步抓取）
  await gotoSection(page, '外部来源').click();
  await expect(page.getByText('还没有登记来源。')).toBeVisible();
  await page.getByLabel('来源类型').selectOption({ label: 'GitHub 仓库' });
  await page.getByLabel('来源地址').fill('https://github.com/owner/repo');
  await page.getByRole('button', { name: '登记来源' }).click();
  await expect(page.getByRole('status').filter({ hasText: '已登记来源' })).toBeVisible();
  const sourceCard = page.locator('.space-session-card', {
    hasText: 'https://github.com/owner/repo',
  });
  await expect(sourceCard).toBeVisible();
  await page.getByRole('button', { name: '登记来源' }).click();
  await expect(page.getByRole('alert').filter({ hasText: '来源地址不能为空' })).toBeVisible();
  await sourceCard.getByRole('button', { name: '移除来源 https://github.com/owner/repo' }).click();
  await expect(page.getByRole('status').filter({ hasText: '已移除来源登记' })).toBeVisible();
  await expect(page.locator('.space-session-card')).toHaveCount(0);

  // 设置分区：改名后 URL 同步替换，不落"不存在"页
  await gotoSection(page, '设置').click();
  await page.getByLabel('知识库名称').fill('课程标准库（改）');
  await page.getByRole('button', { name: '保存修改' }).click();
  await expect(page).toHaveURL(
    new RegExp(`/knowledge-bases/${encodeURIComponent('课程标准库（改）')}$`),
  );
  await expect(page.getByRole('heading', { name: /课程标准库（改）/ })).toBeVisible();
  await expect(page.getByText('知识库「课程标准库」不存在')).toHaveCount(0);

  // 改名导航后页面重挂载回默认分区；重新进入设置删除
  await gotoSection(page, '设置').click();
  page.once('dialog', (dialog) => void dialog.accept());
  await page.getByRole('button', { name: '删除知识库' }).click();
  await expect(page).toHaveURL(/\/knowledge-bases$/);
  await expect(page.getByText('还没有知识库')).toBeVisible();
});

test('知识库详情：登记后自动模拟解析到就绪并生成索引版本', async ({ page }) => {
  await seedKnowledge(page, KB_EMPTY_SEED);
  await page.goto(`/knowledge-bases/${encodeURIComponent('空种子库')}`);
  await expect(page.getByRole('heading', { name: /空种子库/ })).toBeVisible();

  // 空库：无版本
  await gotoSection(page, '索引').click();
  await expect(page.getByText('还没有索引版本')).toBeVisible();

  // 登记一个文档 → 自动模拟解析
  await gotoSection(page, '登记文档').click();
  await page.getByLabel('选择要登记的文件').setInputFiles({
    name: '自动解析样例.md',
    mimeType: 'text/markdown',
    buffer: Buffer.from('# 自动解析'),
  });
  // 立即回到文档分区，捕捉进行中的进度条（parsing/indexing 窗口）
  await gotoSection(page, '文档').click();
  await expect(page.locator('[role="progressbar"]').first()).toBeVisible({ timeout: 5000 });
  await expect(page.getByRole('status').filter({ hasText: '已登记 1 个文档' })).toBeVisible();

  // 进行中（解析中/索引中）→ 已解析 · 已索引
  await expect(page.locator('.space-chip', { hasText: '已解析 · 已索引' })).toBeVisible({
    timeout: 8000,
  });

  // 索引分区出现 1 个版本
  await gotoSection(page, '索引').click();
  await expect(page.locator('.space-session-card', { hasText: /版本 1/ })).toBeVisible();
  await expect(page.getByText('还没有索引版本')).toHaveCount(0);
});

test('知识库详情：进行中取消解析进入处理失败并可重试', async ({ page }) => {
  await seedKnowledge(page, KB_PARSING_SEED);
  await page.goto(`/knowledge-bases/${encodeURIComponent('进行中种子库')}`);
  const card = page.locator('.space-session-card', { hasText: '解析中文档.md' });
  await expect(card.locator('.space-chip', { hasText: /解析中|索引中/ }).first()).toBeVisible();

  // 进行中取消 → 处理失败 + 取消说明
  await card.getByRole('button', { name: '取消解析 解析中文档.md', exact: true }).click();
  await expect(card.locator('.space-chip', { hasText: '处理失败' })).toBeVisible();
  await expect(card.getByText(/已取消解析/)).toBeVisible();

  // 重试解析 → 成功
  await card.getByRole('button', { name: '重试解析 解析中文档.md', exact: true }).click();
  await expect(page.locator('.space-chip', { hasText: '已解析 · 已索引' })).toBeVisible({
    timeout: 8000,
  });
});

test('知识库详情：模拟失败后重试成功并生成索引版本', async ({ page }) => {
  await seedKnowledge(page, KB_EMPTY_SEED);
  await page.goto(`/knowledge-bases/${encodeURIComponent('空种子库')}`);

  await gotoSection(page, '登记文档').click();
  await page.getByLabel('模拟一次解析失败（演示失败与重试路径）').check();
  await page.getByLabel('选择要登记的文件').setInputFiles({
    name: '失败重试样例.md',
    mimeType: 'text/markdown',
    buffer: Buffer.from('# 失败重试'),
  });
  await expect(page.getByRole('status').filter({ hasText: '已登记 1 个文档' })).toBeVisible();
  await gotoSection(page, '文档').click();

  const card = page.locator('.space-session-card', { hasText: '失败重试样例.md' });
  await expect(card.locator('.space-chip', { hasText: '处理失败' })).toBeVisible({ timeout: 8000 });
  await expect(card.getByText(/解析失败/)).toBeVisible();

  await card.getByRole('button', { name: '重试解析 失败重试样例.md', exact: true }).click();
  await expect(card.locator('.space-chip', { hasText: '已解析 · 已索引' })).toBeVisible({
    timeout: 8000,
  });

  await gotoSection(page, '索引').click();
  await expect(page.locator('.space-session-card', { hasText: /版本 1/ })).toBeVisible();
});

test('知识库详情：登记后刷新可恢复进行中的模拟解析', async ({ page }) => {
  await seedKnowledge(page, KB_EMPTY_SEED);
  await page.goto(`/knowledge-bases/${encodeURIComponent('空种子库')}`);

  await gotoSection(page, '登记文档').click();
  await page.getByLabel('选择要登记的文件').setInputFiles({
    name: '刷新恢复样例.md',
    mimeType: 'text/markdown',
    buffer: Buffer.from('# 刷新恢复'),
  });
  await expect(page.getByRole('status').filter({ hasText: '已登记 1 个文档' })).toBeVisible();
  await gotoSection(page, '文档').click();

  // 等到进入进行中再刷新，确保写入的进度快照为 parsing/indexing
  await expect(page.locator('[role="progressbar"]').first()).toBeVisible({ timeout: 6000 });
  await page.reload();

  // resumeKbIngests 挂载恢复，不永久卡在进行中
  await expect(page.locator('.space-chip', { hasText: '已解析 · 已索引' })).toBeVisible({
    timeout: 8000,
  });
});

test('知识库详情：缺 status/indexVersions 的旧种子正常渲染', async ({ page }) => {
  await seedKnowledge(page, KB_LEGACY_SEED);
  await page.goto(`/knowledge-bases/${encodeURIComponent('旧数据种子库')}`);
  await expect(page.getByRole('heading', { name: /旧数据种子库/ })).toBeVisible();
  await expect(page.locator('.space-chip', { hasText: '未解析 · 未索引' })).toHaveCount(1);
  await expect(page.locator('.space-banner.error')).toHaveCount(0);

  await gotoSection(page, '索引').click();
  await expect(page.getByText('还没有索引版本')).toBeVisible();
});

test('知识库详情：目录数据损坏时如实报错且不覆盖原数据', async ({ page }) => {
  const corrupted = '{ this is not valid json';
  await page.addInitScript((value) => {
    window.localStorage.setItem('zqky.replica.knowledge.v1', value);
  }, corrupted);
  await page.goto(`/knowledge-bases/${encodeURIComponent('任意库')}`);

  // 读取失败必须显示错误，而不是停在“正在读取知识库…”
  await expect(page.locator('.space-banner.error')).toContainText('原数据已保留');
  await expect(page.getByText('正在读取知识库…')).toHaveCount(0);

  // 原数据未被覆盖
  const stored = await page.evaluate(() =>
    window.localStorage.getItem('zqky.replica.knowledge.v1'),
  );
  expect(stored).toBe(corrupted);
});

test('笔记本：默认笔记本、记录展开/编辑/移动复制、新建/导出/删除回退', async ({ page }) => {
  await seedNotebookData(page, NOTEBOOKS_SEED, RECORDS_SEED);
  await page.goto('/notebooks');
  await expect(page.getByRole('heading', { name: '笔记本', exact: true })).toBeVisible();
  await expect(page.getByText('选择一个笔记本')).toBeVisible();
  const rail = page.locator('.space-scope-rail');
  await expect(rail.locator('.space-scope-item', { hasText: '学习笔记' })).toContainText('1');
  await expect(rail.locator('.space-scope-item', { hasText: '月度整理' })).toContainText('1');

  // 无 notebookId 的记录归默认笔记本
  await rail.locator('.space-scope-item', { hasText: '学习笔记' }).click();
  await expect(page).toHaveURL(/\/notebooks\/notebook-main$/);
  const row = page.locator('.space-session-card', { hasText: '演示研究报告' });
  await expect(row).toBeVisible();
  await expect(row.locator('.space-chip', { hasText: '研究报告' })).toBeVisible();

  // 展开记录：摘要/正文/原会话深链
  await row.getByRole('button', { name: '展开记录 演示研究报告' }).click();
  await expect(row).toContainText('# 报告正文');
  await expect(row).toContainText('演示摘要');
  await expect(row.getByRole('link', { name: '打开原会话' })).toHaveAttribute(
    'href',
    '/chat/seed-session-1?mode=mock',
  );

  // 编辑记录
  await row.getByRole('button', { name: '编辑记录 演示研究报告' }).click();
  const editDialog = page.getByRole('dialog', { name: '编辑记录 · 演示研究报告' });
  await editDialog.getByLabel('标题').fill('演示研究报告（改）');
  await editDialog.getByRole('button', { name: '保存' }).click();
  await expect(
    page.getByRole('status').filter({ hasText: '已保存记录「演示研究报告（改）」' }),
  ).toBeVisible();
  const editedRow = page.locator('.space-session-card', { hasText: '演示研究报告（改）' });
  await expect(editedRow).toBeVisible();

  // 复制到月度整理（副本）
  await editedRow
    .getByRole('button', { name: '移动或复制记录 演示研究报告（改）' })
    .click();
  const copyDialog = page.getByRole('dialog', { name: '移动或复制 · 演示研究报告（改）' });
  await copyDialog.getByLabel('目标笔记本').selectOption({ label: '月度整理' });
  await copyDialog.getByRole('radio', { name: /复制/ }).check();
  await copyDialog.getByRole('button', { name: '执行' }).click();
  await expect(
    page.getByRole('status').filter({ hasText: '已把「演示研究报告（改）」复制到目标笔记本' }),
  ).toBeVisible();
  await expect(rail.locator('.space-scope-item', { hasText: '月度整理' })).toContainText('2');

  // 月度整理内可见副本；把月度对话记录移回学习笔记
  await rail.locator('.space-scope-item', { hasText: '月度整理' }).click();
  await expect(page).toHaveURL(/\/notebooks\/nb-monthly$/);
  await expect(
    page.locator('.space-session-card', { hasText: '演示研究报告（改）（副本）' }),
  ).toBeVisible();
  await expect(page.locator('.space-session-card')).toHaveCount(2);
  await page
    .locator('.space-session-card', { hasText: '月度对话记录' })
    .getByRole('button', { name: '移动或复制记录 月度对话记录' })
    .click();
  const moveDialog = page.getByRole('dialog', { name: '移动或复制 · 月度对话记录' });
  await moveDialog.getByLabel('目标笔记本').selectOption({ label: '学习笔记' });
  await moveDialog.getByRole('button', { name: '执行' }).click();
  await expect(
    page.getByRole('status').filter({ hasText: '已把「月度对话记录」移动到目标笔记本' }),
  ).toBeVisible();
  await expect(page.locator('.space-session-card')).toHaveCount(1);
  await expect(rail.locator('.space-scope-item', { hasText: '学习笔记' })).toContainText('2');

  // 新建笔记本并自动选中
  await rail.locator('.space-scope-item', { hasText: '新建笔记本' }).click();
  const createDialog = page.getByRole('dialog', { name: '新建笔记本' });
  await createDialog.getByLabel('名称').fill('测试笔记本丙');
  await createDialog.getByRole('button', { name: '创建' }).click();
  await expect(
    page.getByRole('status').filter({ hasText: '已创建笔记本「测试笔记本丙」' }),
  ).toBeVisible();
  await expect(page.locator('.space-session-title', { hasText: '测试笔记本丙' })).toBeVisible();
  await expect(page.getByText('这个笔记本还是空的')).toBeVisible();

  // 导出 Markdown（空笔记本也可导出，只含标题）
  await page.getByRole('button', { name: '导出 Markdown' }).click();
  await expect(
    page.getByRole('status').filter({ hasText: '已导出「测试笔记本丙.md」' }),
  ).toBeVisible();

  // 删除笔记本：记录回默认笔记本，不丢失
  page.once('dialog', (dialog) => void dialog.accept());
  await page.getByRole('button', { name: '删除', exact: true }).click();
  await expect(
    page.getByRole('status').filter({ hasText: '已删除「测试笔记本丙」' }),
  ).toBeVisible();
  await expect(page.getByText('选择一个笔记本')).toBeVisible();

  // 删除记录（确认弹窗接受）
  await rail.locator('.space-scope-item', { hasText: '学习笔记' }).click();
  page.once('dialog', (dialog) => void dialog.accept());
  await page
    .locator('.space-session-card', { hasText: '月度对话记录' })
    .getByRole('button', { name: '删除记录 月度对话记录' })
    .click();
  await expect(
    page.getByRole('status').filter({ hasText: '已删除记录「月度对话记录」' }),
  ).toBeVisible();
  await expect(page.locator('.space-session-card', { hasText: '月度对话记录' })).toHaveCount(0);
});

test('笔记本深链指向不存在的笔记本时明确报错', async ({ page }) => {
  await page.goto('/notebooks/does-not-exist');
  await expect(
    page.getByRole('alert').filter({ hasText: '链接指向的笔记本不存在' }),
  ).toBeVisible();
});
