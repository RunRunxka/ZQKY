import { cleanup, render } from '@testing-library/react';
import { afterEach, describe, expect, it } from 'vitest';
import { StreamingMarkdown } from './StreamingMarkdown';

afterEach(cleanup);

/** 渲染给定文本，返回 DOM 统计（流式呈现的核心可观测项） */
function renderText(text: string) {
  const ui = render(<StreamingMarkdown text={text} />);
  const q = (sel: string) => ui.container.querySelectorAll(sel).length;
  const stat = {
    katex: q('.katex'),
    katexDisplay: q('.katex-display'),
    errors: q('.katex-error'),
    raw: q('.chat-reasoning-raw'),
  };
  return { ui, stat };
}

describe('流式推理正文的公式呈现（UX-REGRESSION-FIX v1）', () => {
  it('流式过程中：已闭合的块与已闭合的尾段都渲染公式（四种定界符）', () => {
    // 块 1（空行结束）+ 尾段（定界符闭合）——流式中间态就是这样
    const text =
      '先分析公式 \\(a^2+b^2=c^2\\)，再给出结论。\n\n行内 $y = x^2$ 与反斜杠 \\(z\\)。';
    const { stat } = renderText(text);
    expect(stat.katex).toBe(3);
    expect(stat.errors).toBe(0);
    expect(stat.raw).toBe(0); // 尾段闭合 → 不是原文呈现
  });

  it('块级公式（$$ 与 \\[...\\]）在流式过程中即渲染为 katex-display', () => {
    const text = '推导：\n\n$$\nE = mc^2\n$$\n\n\\[\\sum_{i=1}^{n} i\\]\n\n结束段。';
    const { stat } = renderText(text);
    expect(stat.katexDisplay).toBe(2);
    expect(stat.errors).toBe(0);
  });

  it('未闭合的尾段按原文呈现，补齐定界符后转为公式（未闭合 → 闭合）', () => {
    const open = '前一段 $a^2$ 已渲染。\n\n尾段 $x + y';
    const first = renderText(open);
    expect(first.stat.katex).toBe(1); // 已闭合的块照常渲染
    expect(first.stat.raw).toBe(1); // 未闭合尾段以原文呈现
    expect(first.stat.errors).toBe(0);
    expect(first.ui.container.textContent).toContain('$x + y');

    first.ui.rerender(<StreamingMarkdown text={'前一段 $a^2$ 已渲染。\n\n尾段 $x + y = z$ 补齐。'} />);
    expect(first.ui.container.querySelectorAll('.katex').length).toBe(2);
    expect(first.ui.container.querySelectorAll('.chat-reasoning-raw').length).toBe(0);
    expect(first.ui.container.querySelectorAll('.katex-error').length).toBe(0);
  });

  it('代码里的美元符号保持原文，不解析成公式、不产生 katex-error', () => {
    const text = '代码里的美元符号：\n\n```sh\necho "$HOME 与 $((1+2))"\n```\n\n行内代码 `$x$` 也保持原文。';
    const { stat, ui } = renderText(text);
    expect(stat.katex).toBe(0);
    expect(stat.errors).toBe(0);
    expect(ui.container.textContent).toContain('$HOME 与 $((1+2))');
    expect(ui.container.textContent).toContain('$x$');
  });

  it('逐字保留原文：仅做展示切分，不丢字符（拼接后文本与原文一致）', () => {
    const text = '第一段。\n\n未闭合尾段 $p + q';
    const { ui } = renderText(text);
    const plain = (ui.container.textContent ?? '').replace(/\s+/g, ' ').trim();
    expect(plain).toContain('第一段。');
    expect(plain).toContain('$p + q');
  });

  it('长尾段超过上限时以原文呈现（避免每帧解析增长中的长文本）', () => {
    const text = `${'字'.repeat(4500)} $a$`;
    const { stat } = renderText(text);
    expect(stat.raw).toBe(1);
    expect(stat.katex).toBe(0);
  });
});
