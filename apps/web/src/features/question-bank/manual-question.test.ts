import { describe, expect, it } from 'vitest';
import { composeManualQuestion, MANUAL_QUESTION_FILE_NAME } from './manual-question';

describe('手动录入题目的 Markdown 组装', () => {
  it('题号、选项编号、答案与解析按后端规则拆题格式输出', () => {
    const text = composeManualQuestion({
      stem: '计算 $2^3$ 的值。',
      optionsText: '6\n8\n9',
      answer: 'B',
      explanation: '因为 $2^3=8$。',
    });
    expect(text).toBe(
      '1. 计算 $2^3$ 的值。\n\nA. 6\nB. 8\nC. 9\n\n答案：B\n解析：因为 $2^3=8$。\n',
    );
  });

  it('题干已带题号时不重复加号', () => {
    const text = composeManualQuestion({
      stem: '3. 已知 $x=1$，求 $x+1$。',
      optionsText: '',
      answer: '',
      explanation: '',
    });
    expect(text).toBe('3. 已知 $x=1$，求 $x+1$。\n');
  });

  it('中文序号与括号题号同样识别', () => {
    expect(
      composeManualQuestion({ stem: '（2）判断对错。', optionsText: '', answer: '对', explanation: '' }),
    ).toBe('（2）判断对错。\n\n答案：对\n');
    expect(
      composeManualQuestion({ stem: '二、填空题。', optionsText: '', answer: '', explanation: '' }),
    ).toBe('二、填空题。\n');
  });

  it('选项留空时不产生空选项块；题干为空返回 null', () => {
    const text = composeManualQuestion({
      stem: '  简答题题干。 ',
      optionsText: '\n\n',
      answer: '略',
      explanation: '',
    });
    expect(text).toBe('1. 简答题题干。\n\n答案：略\n');
    expect(composeManualQuestion({ stem: '   ', optionsText: 'A', answer: '', explanation: '' })).toBeNull();
  });

  it('文件名固定为 Markdown（后端按后缀解析）', () => {
    expect(MANUAL_QUESTION_FILE_NAME.endsWith('.md')).toBe(true);
  });
});
