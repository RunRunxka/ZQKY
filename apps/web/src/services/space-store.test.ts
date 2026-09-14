import { beforeEach, describe, expect, it } from 'vitest';
import {
  addQuizCategory,
  listNotebookEntries,
  listQuizBank,
  listQuizCategories,
  loadDemoQuizEntries,
  recordQuizAnswer,
  removeQuizCategory,
  removeQuizEntries,
  renameQuizCategory,
  saveNotebookEntry,
  saveQuizEntries,
  updateQuizEntry,
} from './space-store';

/**
 * S4/S5 本地模拟仓储（space-store）：题库与笔记的幂等保存、作答记录、
 * 书签/已掌握/分类标记与演示题库显式载入。
 * 聊天产物保存与 S5 业务页读取共用这份仓储（同复合身份）。
 */

describe('S4 本地模拟仓储 space-store', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('题库保存：同 id 幂等不重复，作答记录可写回', () => {
    const entry = {
      id: 'm1:q-1',
      messageId: 'm1',
      questionId: 'q-1',
      topic: '光合作用',
      question: '【演示】题干',
      questionType: 'choice',
      options: { A: '一', B: '二' },
      correctAnswer: 'A',
      explanation: '解析',
      difficulty: '自动',
    };
    const first = saveQuizEntries([entry]);
    expect(first).toEqual({ added: 1, skipped: 0 });
    const second = saveQuizEntries([{ ...entry }]);
    expect(second).toEqual({ added: 0, skipped: 1 });
    expect(listQuizBank()).toHaveLength(1);

    recordQuizAnswer('m1:q-1', { answer: 'B', correct: false });
    expect(listQuizBank()[0]!.lastAnswer).toMatchObject({ answer: 'B', correct: false });
    // 未保存的题目不能写作答记录（只作用于本仓储）
    recordQuizAnswer('missing', { answer: 'x', correct: true });
    expect(listQuizBank()).toHaveLength(1);
  });

  it('笔记保存：同 id 返回 exists 不重复入库', () => {
    const entry = {
      id: 'm1:report-1',
      messageId: 'm1',
      artifactId: 'report-1',
      title: '研究报告（模拟）',
      kind: 'research_report',
      content: '# 报告',
    };
    expect(saveNotebookEntry(entry)).toBe('added');
    expect(saveNotebookEntry({ ...entry })).toBe('exists');
    expect(listNotebookEntries()).toHaveLength(1);
    expect(listNotebookEntries()[0]!.content).toBe('# 报告');
  });
});

describe('S5-A 题库标记、分类与演示数据', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  function seed() {
    saveQuizEntries([
      {
        id: 'm1:q-1',
        messageId: 'm1',
        questionId: 'q-1',
        topic: '分数',
        question: '题一',
        questionType: '选择题',
        correctAnswer: 'A',
        explanation: '',
        difficulty: '基础',
      },
      {
        id: 'm1:q-2',
        messageId: 'm1',
        questionId: 'q-2',
        topic: '修辞',
        question: '题二',
        questionType: '填空题',
        correctAnswer: '拟人',
        explanation: '',
        difficulty: '基础',
      },
    ]);
  }

  it('书签与已掌握标记可切换，旧数据缺省视为未标记', () => {
    seed();
    expect(listQuizBank().every((e) => !e.bookmarked && !e.resolved)).toBe(true);
    updateQuizEntry('m1:q-1', { bookmarked: true, resolved: true });
    const entry = listQuizBank().find((e) => e.id === 'm1:q-1')!;
    expect(entry.bookmarked).toBe(true);
    expect(entry.resolved).toBe(true);
    // 不存在条目静默返回 null，不抛错
    expect(updateQuizEntry('missing', { bookmarked: true })).toBeNull();
  });

  it('删除条目按 id 批量生效，返回删除数量', () => {
    seed();
    expect(removeQuizEntries(['m1:q-1', 'missing'])).toBe(1);
    expect(listQuizBank().map((e) => e.id)).toEqual(['m1:q-2']);
  });

  it('分类增删改：重名拒绝、删除分类后题目回到未分类', () => {
    seed();
    const cat = addQuizCategory('代数巩固');
    expect(cat).not.toBeNull();
    expect(addQuizCategory('代数巩固')).toBeNull(); // 重名
    expect(addQuizCategory('  ')).toBeNull(); // 空名

    expect(renameQuizCategory(cat!.id, '几何巩固')).toBe(true);
    const other = addQuizCategory('古诗文积累');
    expect(other).not.toBeNull();
    expect(renameQuizCategory(cat!.id, '古诗文积累')).toBe(false); // 与其他分类重名
    expect(renameQuizCategory('missing', 'x')).toBe(false);

    updateQuizEntry('m1:q-1', { categoryId: cat!.id });
    expect(listQuizBank().find((e) => e.id === 'm1:q-1')!.categoryId).toBe(cat!.id);
    removeQuizCategory(cat!.id);
    // 删除单个分类：另一分类保留，题目回到未分类
    expect(listQuizCategories().map((c) => c.name)).toEqual(['古诗文积累']);
    expect(listQuizBank().find((e) => e.id === 'm1:q-1')!.categoryId).toBeNull();
  });

  it('演示题库显式载入：幂等且带演示来源与既有标记', () => {
    const first = loadDemoQuizEntries();
    expect(first.added).toBeGreaterThan(0);
    const second = loadDemoQuizEntries();
    expect(second).toEqual({ added: 0, skipped: first.added });
    const bank = listQuizBank();
    expect(bank.every((e) => e.source === 'demo')).toBe(true);
    // 演示数据自带至少一道"上次答错"与一枚书签，供范围筛选验收
    expect(bank.some((e) => e.lastAnswer?.correct === false)).toBe(true);
    expect(bank.some((e) => e.bookmarked)).toBe(true);
  });
});

describe('R-10 题库来源会话身份', () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it('保存带 sessionId 的题目可读回', () => {
    saveQuizEntries([
      {
        id: 'm1:q1',
        messageId: 'm1',
        sessionId: 'sess-1',
        questionId: 'q1',
        topic: 't',
        question: 'q',
        questionType: 'choice',
        correctAnswer: 'A',
        explanation: 'e',
        difficulty: 'easy',
      },
    ]);
    expect(listQuizBank().find((e) => e.id === 'm1:q1')?.sessionId).toBe('sess-1');
  });

  it('旧数据无 sessionId：保持 undefined，不猜测绑定', () => {
    window.localStorage.setItem(
      'zhiqikeyuan:quiz-bank',
      JSON.stringify([
        { id: 'old:q', messageId: 'old', questionId: 'q', topic: 't', question: 'q', questionType: 'choice', correctAnswer: 'A', explanation: 'e', difficulty: 'easy', savedAt: '2026-01-01T00:00:00Z' },
      ]),
    );
    expect(listQuizBank().find((e) => e.id === 'old:q')?.sessionId).toBeUndefined();
  });

  it('脏 sessionId（空串）不作为可靠身份', () => {
    window.localStorage.setItem(
      'zhiqikeyuan:quiz-bank',
      JSON.stringify([
        { id: 'bad:q', messageId: 'bad', sessionId: '  ', questionId: 'q', topic: 't', question: 'q', questionType: 'choice', correctAnswer: 'A', explanation: 'e', difficulty: 'easy', savedAt: '2026-01-01T00:00:00Z' },
      ]),
    );
    expect(listQuizBank().find((e) => e.id === 'bad:q')?.sessionId).toBeUndefined();
  });
});
