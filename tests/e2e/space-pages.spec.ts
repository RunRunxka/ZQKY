import { test, expect, type Page } from '@playwright/test';

/**
 * S5-A 学习空间浏览器回归：
 * 仪表盘磁贴与实时计数、会话历史（搜索/重命名/归档/删除/重开）、
 * 题库（范围/标记/分类/演示载入/删除）、角色目录（新建/编辑/删除/演示幂等）、
 * CLI 应用（安装/启停/卸载）、/space/mcp·skills 重定向设置。
 * 全部使用隔离上下文与显式种子数据，不读取真实用户数据。
 */

const QUIZ_SEED = [
  {
    id: 'm-seed:q-1',
    messageId: 'm-seed',
    questionId: 'q-1',
    topic: '分数的大小比较',
    question: '比较 1/3 与 1/4 的大小。',
    questionType: '选择题',
    options: { A: '1/3 更大', B: '1/4 更大' },
    correctAnswer: 'A',
    explanation: '分母越大分数越小。',
    difficulty: '基础',
    savedAt: '2026-09-08T01:00:00.000Z',
    source: 'deep_question',
    lastAnswer: { answer: 'B', correct: false, at: '2026-09-08T01:01:00.000Z' },
  },
  {
    id: 'm-seed:q-2',
    messageId: 'm-seed',
    questionId: 'q-2',
    topic: '修辞',
    question: '"小草钻出泥土"用了什么修辞？',
    questionType: '填空题',
    correctAnswer: '拟人',
    explanation: '赋予物人的动作。',
    difficulty: '基础',
    savedAt: '2026-09-08T02:00:00.000Z',
    source: 'deep_question',
  },
];

const PERSONA_SEED = [
  {
    id: 'demo-persona-patient',
    name: '耐心的小学老师',
    description: '生活化举例（演示数据）。',
    source: 'demo',
  },
  {
    id: 'demo-persona-rigorous',
    name: '严谨的高中老师',
    description: '强调推理步骤（演示数据）。',
    source: 'demo',
  },
  {
    id: 'demo-persona-socratic',
    name: '启发式助教',
    description: '先反问再引导（演示数据）。',
    source: 'demo',
  },
];

const NOTEBOOK_SEED = [
  {
    id: 'm-seed:report-1',
    messageId: 'm-seed',
    artifactId: 'report-1',
    title: '演示研究报告',
    kind: 'research_report',
    content: '# 报告',
    savedAt: '2026-09-08T01:00:00.000Z',
  },
];

async function seedLocalStorage(page: Page) {
  await page.addInitScript(
    ({ quiz, personas, notebook }) => {
      window.localStorage.setItem('zhiqikeyuan:quiz-bank', JSON.stringify(quiz));
      window.localStorage.setItem('zqky.replica.personas.v1', JSON.stringify(personas));
      window.localStorage.setItem('zhiqikeyuan:notebook-entries', JSON.stringify(notebook));
    },
    { quiz: QUIZ_SEED, personas: PERSONA_SEED, notebook: NOTEBOOK_SEED },
  );
}

async function seedConversation(
  page: Page,
  dbName: string,
  conversation: Record<string, unknown>,
) {
  await page.addInitScript(
    ({ dbName, conversation }) => {
      const request = indexedDB.open(dbName, 1);
      request.onupgradeneeded = (event) => {
        (event.target as IDBOpenDBRequest).result.createObjectStore('conversations', {
          keyPath: 'id',
        });
      };
      request.onsuccess = () => {
        const db = request.result;
        db
          .transaction('conversations', 'readwrite')
          .objectStore('conversations')
          .put(conversation);
      };
    },
    { dbName, conversation },
  );
}

function conversation(id: string, title: string, updatedAt: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    title,
    messages: [
      { id: `${id}-u`, role: 'user', content: `问题-${id}`, status: 'done' },
      { id: `${id}-a`, role: 'assistant', content: `回答-${id}`, status: 'done' },
    ],
    createdAt: updatedAt,
    updatedAt,
    schemaVersion: 1,
    revision: 1,
    draft: '',
    modelProfileId: null,
    mode: 'real',
    ...extra,
  };
}

test('仪表盘磁贴展示实时计数并可进入各页', async ({ page }) => {
  await seedLocalStorage(page);
  await seedConversation(page, 'zhiqikeyuan-chat', conversation('seed-real-1', '真实会话一', '2026-09-08T03:00:00.000Z'));
  await page.goto('/space');
  await expect(page.getByRole('heading', { name: '学习空间' })).toBeVisible();
  // 实时计数：会话 1、题库 2、笔记本 1、角色 3
  await expect(page.locator('.space-tile', { hasText: '会话历史' })).toContainText('1');
  await expect(page.locator('.space-tile', { hasText: '题库' })).toContainText('2');
  await expect(page.locator('.space-tile', { hasText: '笔记本' })).toContainText('1');
  await expect(page.locator('.space-tile', { hasText: '角色目录' })).toContainText('3');
  // 技能与 MCP 磁贴指向设置（未载入扩展目录时计数为 0）
  await expect(page.locator('.space-tile', { hasText: '技能' })).toHaveAttribute('href', '/settings#skills');
  await expect(page.locator('.space-tile', { hasText: 'MCP 服务' })).toHaveAttribute('href', '/settings#mcp');
  // 进入题库
  await page.locator('.space-tile', { hasText: '题库' }).click();
  await expect(page).toHaveURL(/\/space\/questions$/);
  await expect(page.getByRole('heading', { name: '题库' })).toBeVisible();
});

test('笔记本磁贴进入笔记本页（S5-B 起为真实页面）', async ({ page }) => {
  await page.goto('/space');
  await page.locator('.space-tile', { hasText: '笔记本' }).click();
  await expect(page).toHaveURL(/\/notebooks$/);
  await expect(page.getByRole('heading', { name: '笔记本', exact: true })).toBeVisible();
  await expect(page.getByText('选择一个笔记本')).toBeVisible();
});

test('会话历史：筛选、重命名、归档、删除与重开', async ({ page }) => {
  await seedLocalStorage(page);
  await seedConversation(page, 'zhiqikeyuan-chat', conversation('seed-real-1', '会话甲', '2026-09-08T03:00:00.000Z'));
  await seedConversation(page, 'zhiqikeyuan-chat', conversation('seed-real-2', '会话乙', '2026-09-08T04:00:00.000Z'));
  await page.goto('/space/chat-history');
  await expect(page.locator('.space-session-card')).toHaveCount(2, { timeout: 15000 });

  // 搜索
  await page.getByRole('searchbox', { name: '搜索会话历史' }).fill('甲');
  await expect(page.locator('.space-session-card')).toHaveCount(1);
  await expect(page.locator('.space-session-title')).toHaveText('会话甲');
  await page.getByRole('searchbox', { name: '搜索会话历史' }).fill('');

  // 重命名（内联输入，Enter 提交）
  await page.getByRole('button', { name: '重命名会话 会话甲' }).click();
  await page.getByRole('textbox', { name: '会话名称' }).fill('会话甲（改）');
  await page.getByRole('textbox', { name: '会话名称' }).press('Enter');
  await expect(page.locator('.space-session-title', { hasText: '会话甲（改）' })).toBeVisible({
    timeout: 15000,
  });

  // 归档：从"进行中"消失，"已归档"筛选可见
  await page.getByRole('button', { name: '归档会话 会话甲（改）' }).click();
  await expect(page.locator('.space-session-card')).toHaveCount(1);
  await page.getByRole('button', { name: /^已归档/ }).click();
  await expect(page.locator('.space-session-card', { hasText: '会话甲（改）' })).toHaveCount(1);
  // 恢复
  await page.getByRole('button', { name: '恢复会话 会话甲（改）' }).click();
  await page.getByRole('button', { name: /^进行中/ }).click();
  await expect(page.locator('.space-session-card')).toHaveCount(2);

  // 删除（确认弹窗接受）
  page.once('dialog', (dialog) => void dialog.accept());
  await page.getByRole('button', { name: '删除会话 会话乙' }).click();
  await expect(page.locator('.space-session-card')).toHaveCount(1, { timeout: 15000 });
});

test('会话历史重开模拟会话：深链携带 mode=mock 并正确定位', async ({ page }) => {
  await seedConversation(
    page,
    'zhiqikeyuan-chat-mock',
    conversation('seed-mock-1', '模拟会话一', '2026-09-08T05:00:00.000Z', { mode: 'mock' }),
  );
  await page.goto('/space/chat-history');
  const card = page.locator('.space-session-card', { hasText: '模拟会话一' });
  await expect(card).toBeVisible({ timeout: 15000 });
  await expect(card.locator('.space-chip', { hasText: '模拟' })).toBeVisible();
  await card.getByRole('link', { name: '重新打开' }).click();
  await expect(page).toHaveURL(/\/chat\/seed-mock-1\?mode=mock$/);
  await expect(page.locator('.chat-bubble.assistant').last()).toContainText('回答-seed-mock-1', {
    timeout: 15000,
  });
  await expect(page.getByRole('status').filter({ hasText: '会话不存在' })).toHaveCount(0);
});

test('题库：范围计数、收藏切换、演示载入、分类与删除', async ({ page }) => {
  await seedLocalStorage(page);
  await page.goto('/space/questions');

  // 范围计数：全部 2、答错 1、书签 0
  await expect(page.locator('.space-scope-item', { hasText: '全部' })).toContainText('2');
  await expect(page.locator('.space-scope-item', { hasText: '答错' })).toContainText('1');
  await expect(page.locator('.space-scope-item', { hasText: '书签' })).toContainText('0');
  // 答错视图
  await page.locator('.space-scope-item', { hasText: '答错' }).click();
  await expect(page.locator('.space-question-card')).toHaveCount(1);
  await expect(page.locator('.space-question-text')).toContainText('1/3 与 1/4');
  // 错误选项标红、正确选项标绿
  await expect(page.locator('.space-option.user-wrong')).toContainText('1/4 更大');
  await expect(page.locator('.space-option.correct')).toContainText('1/3 更大');
  await page.locator('.space-scope-item', { hasText: '全部' }).click();

  // 演示载入（幂等）
  await page.getByRole('button', { name: '载入演示题目' }).click();
  await expect(page.getByRole('status').filter({ hasText: '已载入 5 道演示题目' })).toBeVisible();
  await page.getByRole('status').getByRole('button', { name: '关闭提示' }).click();
  await page.getByRole('button', { name: '载入演示题目' }).click();
  await expect(page.getByRole('status').filter({ hasText: '演示题目已全部在库中' })).toBeVisible();

  // 收藏切换并持久化（演示题自带 1 枚书签，切换后为 2）
  const card = page.locator('.space-question-card', { hasText: '小草钻出泥土' });
  await card.getByRole('button', { name: '收藏' }).click();
  await expect(page.locator('.space-scope-item', { hasText: '书签' })).toContainText('2');

  // 分类管理：新建 → 归类
  await page.getByRole('button', { name: '管理分类' }).click();
  await page.getByRole('textbox', { name: '新分类名称' }).fill('月度复习');
  await page.getByRole('button', { name: '添加', exact: true }).click();
  await expect(page.locator('.space-scope-item', { hasText: '月度复习' })).toBeVisible();
  await card.getByRole('combobox', { name: '移动到分类' }).selectOption({ label: '月度复习' });
  await expect(page.locator('.space-chip.green', { hasText: '月度复习' })).toBeVisible();
  await expect(page.locator('.space-scope-item', { hasText: '未分类' })).toContainText('6');

  // 删除一题（确认弹窗接受）
  page.once('dialog', (dialog) => void dialog.accept());
  await page
    .locator('.space-question-card', { hasText: '1/4 + 2/4' })
    .getByRole('button', { name: '删除' })
    .click();
  await expect(page.locator('.space-question-card')).toHaveCount(6, { timeout: 15000 });
});

test('角色目录：新建、编辑、删除与演示载入幂等', async ({ page }) => {
  await seedLocalStorage(page);
  await page.goto('/space/personas');
  await expect(page.locator('.space-persona-card')).toHaveCount(3, { timeout: 15000 });

  // 新建
  await page.getByRole('button', { name: '新建角色' }).click();
  const dialog = page.getByRole('dialog', { name: '新建角色' });
  await dialog.getByRole('textbox', { name: '名称' }).fill('测试角色甲');
  await dialog.getByRole('textbox', { name: /简介/ }).fill('用于浏览器回归的角色');
  await dialog.getByRole('button', { name: '保存' }).click();
  await expect(page.locator('.space-persona-card', { hasText: '测试角色甲' })).toBeVisible();
  await expect(page.locator('.space-persona-card')).toHaveCount(4);

  // 重名拒绝
  await page.getByRole('button', { name: '新建角色' }).click();
  const dialog2 = page.getByRole('dialog', { name: '新建角色' });
  await dialog2.getByRole('textbox', { name: '名称' }).fill('测试角色甲');
  await dialog2.getByRole('button', { name: '保存' }).click();
  await expect(dialog2.getByRole('alert')).toContainText('已存在同名角色');
  await dialog2.getByRole('button', { name: '取消' }).click();

  // 编辑
  const card = page.locator('.space-persona-card', { hasText: '测试角色甲' });
  await card.getByRole('button', { name: '编辑' }).click();
  const editDialog = page.getByRole('dialog', { name: '编辑角色 · 测试角色甲' });
  await editDialog.getByRole('textbox', { name: /简介/ }).fill('更新后的简介');
  await editDialog.getByRole('button', { name: '保存' }).click();
  await expect(page.locator('.space-persona-card', { hasText: '更新后的简介' })).toBeVisible();

  // 删除（确认弹窗接受）
  page.once('dialog', (dialog) => void dialog.accept());
  await page
    .locator('.space-persona-card', { hasText: '测试角色甲' })
    .getByRole('button', { name: '删除' })
    .click();
  await expect(page.locator('.space-persona-card')).toHaveCount(3, { timeout: 15000 });

  // 演示载入幂等
  await page.getByRole('button', { name: '载入演示角色' }).click();
  await expect(page.locator('.space-persona-card')).toHaveCount(3);
});

test('CLI 应用：目录安装、启停切换、卸载', async ({ page }) => {
  await page.goto('/space/cli-apps');
  await expect(page.getByText('还没有安装任何 CLI 应用')).toBeVisible({ timeout: 15000 });

  // 目录页签：安装
  await page.getByRole('tab', { name: /应用目录/ }).click();
  const entry = page.locator('.space-cli-card', { hasText: '口算题生成器' });
  await entry.getByRole('button', { name: '安装（本地登记）' }).click();
  await expect(page.getByRole('status').filter({ hasText: '模拟安装' })).toBeVisible();
  // 目录中该条目变为已安装
  await expect(entry.getByRole('button', { name: '已安装' })).toBeDisabled();

  // 已安装页签：启停 + 卸载
  await page.getByRole('tab', { name: /已安装/ }).click();
  const installed = page.locator('.space-cli-card', { hasText: '口算题生成器' });
  await expect(installed).toBeVisible();
  await installed.getByRole('button', { name: '已启用' }).click();
  await expect(installed.getByRole('button', { name: '已停用' })).toBeVisible();
  page.once('dialog', (dialog) => void dialog.accept());
  await installed.getByRole('button', { name: '卸载' }).click();
  await expect(page.getByText('还没有安装任何 CLI 应用')).toBeVisible({ timeout: 15000 });
});

test('/space/mcp 与 /space/skills 重定向到设置对应锚点', async ({ page }) => {
  await page.goto('/space/mcp');
  await expect(page).toHaveURL(/\/settings#mcp$/);
  await page.goto('/space/skills');
  await expect(page).toHaveURL(/\/settings#skills$/);
});
