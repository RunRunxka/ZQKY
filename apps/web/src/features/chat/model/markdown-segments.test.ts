import { describe, expect, it } from 'vitest';
import { splitMarkdownSegments } from './markdown-segments';

/** 不变式：blocks.join('') + tail 与输入逐字一致 */
function expectExact(text: string) {
  const { blocks, tail } = splitMarkdownSegments(text);
  expect(blocks.join('') + tail).toBe(text);
}

describe('流式 Markdown 安全切分（UX-REGRESSION-FIX v1）', () => {
  it('空行切块，且拼接后与原文逐字一致', () => {
    const text = '第一段。\n\n第二段。\n\n第三段';
    const { blocks, tail } = splitMarkdownSegments(text);
    expect(blocks).toEqual(['第一段。\n\n', '第二段。\n\n']);
    expect(tail).toBe('第三段');
    expectExact(text);
  });

  it('未闭合代码围栏内不切块（围栏内的空行不当作块边界）', () => {
    const text = '说明：\n\n```python\nprint("a")\n\nprint("b")\n```\n\n结束';
    const { blocks, tail } = splitMarkdownSegments(text);
    // 围栏块整体作为一个块，围栏内的空行没把块切开
    expect(blocks.join('')).toContain('print("a")\n\nprint("b")');
    expect(tail).toBe('结束');
    expectExact(text);
  });

  it('围栏未闭合时整段留在尾段（不把代码中间切开）', () => {
    const text = '开头\n\n```python\nprint("a")\n\nprint("b")';
    const { blocks, tail, tailSafe } = splitMarkdownSegments(text);
    expect(blocks).toEqual(['开头\n\n']);
    expect(tail).toContain('print("a")');
    expect(tailSafe).toBe(false);
    expectExact(text);
  });

  it('块级公式 $$ 内的空行不切块', () => {
    const text = '前文\n\n$$\na = b\n\nc = d\n$$\n\n后文';
    const { blocks, tail } = splitMarkdownSegments(text);
    expect(blocks.join('')).toContain('c = d');
    expect(tail).toBe('后文');
    expectExact(text);
  });

  it('松散列表的空行不切块（避免一个列表被拆成多个）', () => {
    const text = '- 第一项\n\n- 第二项\n\n正文';
    const { blocks, tail } = splitMarkdownSegments(text);
    expect(blocks.join('')).toContain('- 第二项');
    expect(tail).toBe('正文');
    expectExact(text);
  });

  it('尾段定界符闭合判定：行内 $、\\(、\\[、行内代码、围栏', () => {
    expect(splitMarkdownSegments('正文 $x^2$ 结束').tailSafe).toBe(true);
    expect(splitMarkdownSegments('正文 $x^2').tailSafe).toBe(false);
    expect(splitMarkdownSegments('正文 \\(x^2\\) 结束').tailSafe).toBe(true);
    expect(splitMarkdownSegments('正文 \\(x^2').tailSafe).toBe(false);
    expect(splitMarkdownSegments('正文 \\[x^2\\] 结束').tailSafe).toBe(true);
    expect(splitMarkdownSegments('正文 `code 结束').tailSafe).toBe(false);
    // 代码跨度里的美元符号不参与计数（`$HOME` 不构成未闭合公式）
    expect(splitMarkdownSegments('代码 `echo "$HOME"` 结束').tailSafe).toBe(true);
    expect(splitMarkdownSegments('```sh\necho "$HOME"\n```\n结束').tailSafe).toBe(true);
  });

  it('尾段超过上限时不再用 Markdown 渲染（长增长文本的每帧解析上界）', () => {
    const long = `${'字'.repeat(5000)}`;
    expect(splitMarkdownSegments(long, { tailLimit: 4000 }).tailSafe).toBe(false);
    expect(splitMarkdownSegments(long, { tailLimit: 6000 }).tailSafe).toBe(true);
  });

  it('四种常见定界符与代码里的美元符号混合时的逐字性与安全性', () => {
    const text = [
      '行内 $a^2$ 与 \\(b^2\\)。',
      '',
      '$$',
      '\\int_0^1 x\\,dx',
      '$$',
      '',
      '\\[\\sum_i i\\]',
      '',
      '```sh',
      'echo "$HOME 与 $((1+2))"',
      '```',
      '',
      '尾段 $x + y',
    ].join('\n');
    const { blocks, tail, tailSafe } = splitMarkdownSegments(text);
    expect(blocks.join('')).toContain('echo "$HOME 与 $((1+2))"');
    expect(tail).toBe('尾段 $x + y');
    expect(tailSafe).toBe(false); // 尾段有未闭合的 $
    expectExact(text);
  });
});

describe('超限尾段安全上提为块（每次提交只解析受长度约束的尾段）', () => {
  it('多行长尾段按行边界上提，尾段长度回到上限内且原文逐字保留', () => {
    const line = `第 N 行含公式 $a_1^2$ 与文字。`;
    const text = Array.from({ length: 200 }, (_, i) => `${line}（${i}）`).join('\n');
    const { blocks, tail, tailSafe } = splitMarkdownSegments(text);
    expect(blocks.length).toBeGreaterThan(0);
    expect(tail.length).toBeLessThanOrEqual(4000);
    expect(tailSafe).toBe(true);
    expect(blocks.join('') + tail).toBe(text);
  });

  it('不把表格拆开（表格行前不作为切点）', () => {
    const rows = ['| a | b |', '| --- | --- |', ...Array.from({ length: 200 }, (_, i) => `| ${i} | ${i * 2} |`)];
    const text = `表头说明。\n\n${rows.join('\n')}`;
    const { blocks, tail } = splitMarkdownSegments(text, { tailLimit: 200 });
    // 切点只可能落在表格之前的空行，表格整体留在同一个块里
    const tableChunk = [...blocks, tail].find((chunk) => chunk.includes('| --- |'));
    expect(tableChunk).toBeTruthy();
    expect(tableChunk).toContain('| 199 | 398 |');
    expect(blocks.join('') + tail).toBe(text);
  });

  it('未闭合定界符之后不再上提（尾段保持原文呈现，不把公式切成两半）', () => {
    // 尾段内含一个未闭合的 $，其后仍有大量行：扫描不到平衡切点 → 不上提 → 原文呈现
    const text = `开头段落。\n\n$尚未闭合 = \\frac{1}{2}\n${'内容行\n'.repeat(1500)}结束`;
    const { blocks, tail, tailSafe } = splitMarkdownSegments(text);
    expect(blocks.join('') + tail).toBe(text);
    expect(tail.length).toBeGreaterThan(4000);
    expect(tailSafe).toBe(false);
  });
});
