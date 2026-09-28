import { describe, expect, it } from 'vitest';
import type { QuestionContent } from '@/contracts/question-bank';
import {
  answerHasContent,
  changeContentType,
  confirmBlockers,
  contentErrors,
  metadataErrors,
  nextOptionKey,
  normalizeAnswer,
  tagsFromText,
  tagsToText,
} from './draft-form';

function content(overrides: Partial<QuestionContent> = {}): QuestionContent {
  return {
    type: 'single_choice',
    stemMarkdown: '下列说法正确的是？',
    options: [
      { key: 'A', textMarkdown: '甲' },
      { key: 'B', textMarkdown: '乙' },
    ],
    answer: { choiceKeys: ['A'], accepted: null, textMarkdown: null },
    explanationMarkdown: null,
    assetIds: [],
    ...overrides,
  };
}

describe('答案归一与判定', () => {
  it('全空答案归一为 null（等价「原文未提供答案」）', () => {
    expect(normalizeAnswer({ choiceKeys: [], accepted: null, textMarkdown: '   ' })).toBeNull();
    expect(normalizeAnswer(null)).toBeNull();
    expect(answerHasContent(null)).toBe(false);
  });

  it('保留有内容的答案并去重 key、去文本空白', () => {
    expect(
      normalizeAnswer({ choiceKeys: ['A', 'A', 'B'], accepted: null, textMarkdown: '  ' }),
    ).toEqual({ choiceKeys: ['A', 'B'], accepted: null, textMarkdown: null });
    expect(answerHasContent({ choiceKeys: [], accepted: false, textMarkdown: null })).toBe(true);
    expect(answerHasContent({ choiceKeys: [], accepted: null, textMarkdown: '解析' })).toBe(true);
  });
});

describe('题型切换', () => {
  it('切到单选只保留 1 个仍存在的 key，切到文本题清空选项答案', () => {
    const multiple = changeContentType(
      content({
        type: 'multiple_choice',
        answer: { choiceKeys: ['A', 'B', 'C'], accepted: null, textMarkdown: null },
      }),
      'single_choice',
    );
    expect(multiple.answer).toEqual({ choiceKeys: ['A'], accepted: null, textMarkdown: null });

    const short = changeContentType(content(), 'short_answer');
    expect(short.answer).toBeNull();
    expect(short.type).toBe('short_answer');
  });

  it('切到判断题保留 accepted，切回选择题不丢选项', () => {
    const tf = changeContentType(
      content({ answer: { choiceKeys: [], accepted: true, textMarkdown: null } }),
      'true_false',
    );
    expect(tf.answer).toEqual({ choiceKeys: [], accepted: true, textMarkdown: null });
    expect(tf.options).toHaveLength(2);

    const back = changeContentType(tf, 'multiple_choice');
    expect(back.answer).toBeNull();
    expect(back.options).toHaveLength(2);
  });
});

describe('结构预检', () => {
  it('拦截空题干、重复 key、空选项内容与单选题多答案', () => {
    expect(contentErrors(content({ stemMarkdown: '  ' }))).toContain('题干不能为空。');
    expect(
      contentErrors(
        content({
          options: [
            { key: 'A', textMarkdown: '甲' },
            { key: 'A', textMarkdown: '乙' },
          ],
        }),
      ).join(' '),
    ).toContain('选项 key 不能重复。');
    expect(
      contentErrors(content({ options: [{ key: 'A', textMarkdown: ' ' }] })).join(' '),
    ).toContain('选项内容不能为空。');
    expect(
      contentErrors(
        content({
          type: 'multiple_choice',
          answer: { choiceKeys: ['A', 'Z'], accepted: null, textMarkdown: null },
        }),
      ).join(' '),
    ).toContain('答案 key 不在选项中：Z。');
    expect(
      contentErrors(
        content({
          type: 'single_choice',
          answer: { choiceKeys: ['A', 'B'], accepted: null, textMarkdown: null },
        }),
      ).join(' '),
    ).toContain('单选题的答案只能有 1 个选项。');
    expect(contentErrors(content())).toEqual([]);
  });

  it('入库前预检提示缺失答案需显式确认', () => {
    const missing = content({ answer: null });
    expect(confirmBlockers(missing, false)).toEqual([
      '答案缺失：需先「标记原文未提供答案」，或补齐答案后才能入库。',
    ]);
    expect(confirmBlockers(missing, true)).toEqual([]);
    expect(
      confirmBlockers(content({ type: 'single_choice', options: [], answer: null }), true),
    ).toEqual(['选择题必须至少有一个选项。']);
  });

  it('分类预检只拦标签数量与空标签', () => {
    const metadata = {
      stageId: '',
      gradeId: '',
      subjectId: '',
      editionId: '',
      knowledgeTags: Array.from({ length: 33 }, (_, index) => `t${index}`),
      difficulty: 'easy' as const,
    };
    expect(metadataErrors(metadata).join(' ')).toContain('知识点标签最多 32 个。');
    expect(metadataErrors({ ...metadata, knowledgeTags: [''], difficulty: 'unspecified' })).toEqual(
      ['知识点标签不能为空。'],
    );
  });
});

describe('选项 key 与标签输入', () => {
  it('生成未被占用的 key，量到 Z 后用 O27 兜底', () => {
    expect(nextOptionKey([{ key: 'A', textMarkdown: '甲' }])).toBe('B');
    const all = Array.from({ length: 26 }, (_, index) => ({
      key: String.fromCharCode(65 + index),
      textMarkdown: 'x',
    }));
    expect(nextOptionKey(all)).toBe('O27');
  });

  it('标签输入按中英文逗号、顿号、分号与空格切分并去重', () => {
    expect(tagsFromText('有理数、数轴, 相反数 绝对值;有关')).toEqual([
      '有理数',
      '数轴',
      '相反数',
      '绝对值',
      '有关',
    ]);
    expect(tagsToText(['有理数', '数轴'])).toBe('有理数、数轴');
  });
});
