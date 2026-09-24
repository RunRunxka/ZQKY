import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { AnswerMarkdown } from './AnswerMarkdown';
import { normalizeMathDelimiters } from './model/markdown-math';

afterEach(cleanup);
describe('AI 数学内容展示', () => {
  it('渲染美元及反斜杠行内、块级公式，保留上下文', () => {
    const text = String.raw`行内 \(x^2\)，常规 $y^2$。
\[\frac{1}{2}+\sqrt{x}\]
$$
E=mc^2
$$`;
    const ui = render(<AnswerMarkdown text={text} />);
    expect(ui.container.querySelectorAll('.katex')).toHaveLength(4);
    expect(ui.container.querySelectorAll('.katex-display')).toHaveLength(2);
    expect(ui.container.querySelector('.katex-error')).toBeNull();
    expect(ui.container.textContent).toContain('行内');
  });
  it('双重转义的公式分隔符仅在展示层折叠一层，并保护代码内容', () => {
    const source = String.raw`\\(r^2\\) and \\[\\frac{1}{2}\\]`;
    expect(normalizeMathDelimiters(source)).toContain('$r^2$');
    const ui = render(<AnswerMarkdown text={source} />);
    expect(ui.container.querySelectorAll('.katex')).toHaveLength(2);
    expect(ui.container.querySelectorAll('.katex-error')).toHaveLength(0);
    const code = String.raw`\\(literal\\)`;
    const codeUi = render(<AnswerMarkdown text={`\`\`\`text\n${code}\n\`\`\``} />);
    expect(codeUi.container.querySelector('.katex')).toBeNull();
    expect(codeUi.container.textContent).toContain(code);
  });

  it('代码中的公式保持原文，未闭合流式片段可以继续完成', () => {
    const code = '```latex\n\\[x^2\\]\n```\n`\\(y\\)`\n    \\(z\\)';
    expect(normalizeMathDelimiters(code)).toBe(code);
    const unclosed = '```latex\n\\[x^2\\]';
    expect(normalizeMathDelimiters(unclosed)).toBe(unclosed);
    const ui = render(<AnswerMarkdown text={String.raw`\[\frac{1}`} />);
    expect(ui.container.querySelector('.katex')).toBeNull();
    ui.rerender(<AnswerMarkdown text={String.raw`\[\frac{1}{2}\]`} />);
    expect(ui.container.querySelector('.katex-display')).not.toBeNull();
    expect(ui.container.querySelector('.katex-error')).toBeNull();
  });
});
