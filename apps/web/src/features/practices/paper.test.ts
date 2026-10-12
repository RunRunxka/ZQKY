/**
 * 练习卷分页模型（R8-FE）：题不劈页、页码从 1 起、教师卷追加答案页、
 * 高度随内容增长。全部为纯函数，SSR/测试可复现。
 */

import { describe, expect, it } from 'vitest';
import type { PracticeItemView } from '@/contracts/b4';
import type { RichContentV2 } from '@/contracts/question-bank';
import { A4_HEIGHT_PX, PAPER_PADDING_PX, PAGE_FOOTER_RESERVE_PX, countLines, layoutPaper, pageEndLabel, questionHeight } from './paper';

function rich(stem: string, options: Record<string, string> = {}, answer = '答案'): RichContentV2 {
  return {
    version: 2,
    sharedMaterials: [],
    stemBlocks: [{ id: 'stem-1', kind: 'paragraph', text: stem }],
    optionBlocks: Object.fromEntries(Object.entries(options).map(([key, text]) => [key, [{ id: `o-${key}`, kind: 'paragraph', text }]])),
    answerBlocks: [{ id: 'a-1', kind: 'paragraph', text: answer }],
    explanationBlocks: [{ id: 'e-1', kind: 'paragraph', text: '解析文字' }],
    assets: [],
    origin: { originalAssetId: 'q-1', originalSha256: 'sha', sourceLocator: {} },
  };
}

function item(index: number, content: RichContentV2): PracticeItemView {
  return {
    practiceItemId: `item-${index}`,
    selectionId: `sel-${index}`,
    itemKey: `key-${index}`,
    nodeKey: `node-${index}`,
    parentItemId: null,
    questionNo: String(index),
    ordinal: index,
    isScored: true,
    maxScoreUnits: 100,
    questionId: `question-${index}`,
    questionRevisionId: `rev-${index}`,
    content,
    knowledgePoints: [{ knowledgePointId: 'kp-1', knowledgeRevisionId: 'kr-1', name: '知识点', role: 'primary' }],
    sourceLocator: {},
    reason: '符合约束',
    answerState: 'provided',
  };
}

describe('countLines', () => {
  it('CJK 全宽、拉丁半宽，保留显式换行', () => {
    expect(countLines('', 100, 14)).toBe(0);
    expect(countLines('一行', 100, 14)).toBe(1);
    expect(countLines('a\nb', 100, 14)).toBe(2);
    expect(countLines('字'.repeat(20), 140, 14)).toBe(2);
  });
});

describe('layoutPaper', () => {
  it('页码从 1 起，卷头在第一页', () => {
    const layout = layoutPaper([item(1, rich('题干一'))], 'student');
    expect(layout.pages[0].number).toBe(1);
    expect(layout.pages[0].segments[0].kind).toBe('header');
    expect(pageEndLabel(1)).toBe('第 1 页结束');
  });

  it('纸张容量内的题不分页', () => {
    const capacity = A4_HEIGHT_PX - PAPER_PADDING_PX * 2 - PAGE_FOOTER_RESERVE_PX;
    const small = rich('短题干');
    expect(questionHeight(small, 'student')).toBeLessThan(capacity);
    const layout = layoutPaper([item(1, small), item(2, small)], 'student');
    expect(layout.pages).toHaveLength(1);
    expect(layout.pages[0].segments.filter((segment) => segment.kind === 'question')).toHaveLength(2);
  });

  it('题不劈页：放不下的题整块移到下一页而不是拆开', () => {
    const long = rich('长'.repeat(1500));
    const layout = layoutPaper([item(1, rich('短题干')), item(2, long)], 'student');
    const pagesWithQuestions = layout.pages.filter((page) => page.segments.some((segment) => segment.kind === 'question'));
    expect(pagesWithQuestions.length).toBeGreaterThan(1);
    // 每题恰好完整出现在一个页面里（不重复、不拆块）。
    const seen = layout.pages.flatMap((page) => page.segments.filter((segment) => segment.kind === 'question').map((segment) => segment.itemIds[0]));
    expect(seen).toEqual(['item-1', 'item-2']);
  });

  it('教师卷追加答案页；学生卷没有答案页', () => {
    const student = layoutPaper([item(1, rich('题干'))], 'student');
    const teacher = layoutPaper([item(1, rich('题干'))], 'teacher');
    expect(student.pages.flatMap((page) => page.segments).some((segment) => segment.kind === 'answer-sheet')).toBe(false);
    expect(teacher.pages.flatMap((page) => page.segments).some((segment) => segment.kind === 'answer-sheet')).toBe(true);
  });

  it('教师卷题干高度包含答案与解析（学生卷不含）', () => {
    const content = rich('题干', { A: '选项甲' });
    expect(questionHeight(content, 'teacher')).toBeGreaterThan(questionHeight(content, 'student'));
  });

  it('空题目列表仍给出一页空纸（不返回 0 页）', () => {
    const layout = layoutPaper([], 'student');
    expect(layout.pages).toHaveLength(1);
    expect(layout.pages[0].segments.map((segment) => segment.kind)).toEqual(['header']);
  });
});
