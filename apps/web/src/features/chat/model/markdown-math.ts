/** 仅转换展示内容；原消息、复制和导出保留供应商原文。代码区不参与公式归一化。 */
function collapseDoubleEscapedDelimiters(text: string, open: string, close: string) {
  let result = '';
  let cursor = 0;
  while (cursor < text.length) {
    const start = text.indexOf(open, cursor);
    if (start < 0) return result + text.slice(cursor);
    if (start > 0 && text[start - 1] === '\\') {
      result += text.slice(cursor, start + 1);
      cursor = start + 1;
      continue;
    }
    const end = text.indexOf(close, start + open.length);
    if (end < 0 || (end > 0 && text[end - 1] === '\\')) {
      result += text.slice(cursor, start + open.length);
      cursor = start + open.length;
      continue;
    }
    result += `${text.slice(cursor, start)}${open.slice(1)}${text.slice(start + open.length, end)}${close.slice(1)}`;
    cursor = end + close.length;
  }
  return result;
}

export function normalizeMathDelimiters(source: string): string {
  const protectedSpans: string[] = [];
  const marker = `\u0000MATH${source.length}\u0000`;
  const protect = (value: string) => `${marker}${protectedSpans.push(value) - 1}\u0000`;
  // 完整或仍在流式接收的 fenced code，以及 inline code / 缩进代码。
  let text = source.replace(
    /(^ {0,3}(`{3,}|~{3,})[^\n]*\n)[\s\S]*?(?:^ {0,3}\2[ \t]*(?=\n|$)|$(?![\s\S]))/gm,
    protect,
  );
  text = text.replace(/(`+)[^`\n]*?\1/g, protect).replace(/^(?: {4}|\t).*$/gm, protect);
  // 一些供应商会把公式定界符本身再转义一层（\\(...\\) / \\[...\\]）。
  // 仅对完整成对的定界符折叠这一层，不改消息原文。
  text = collapseDoubleEscapedDelimiters(text, '\\\\(', '\\\\)');
  text = collapseDoubleEscapedDelimiters(text, '\\\\[', '\\\\]');
  // 支持模型常用的 \(...\)、\[...\]，以及 $$ 内多包一层 \(...\) 的输出。
  text = text.replace(
    /\$\$\s*\\\(([\s\S]*?)\\\)\s*\$\$/g,
    (_, body: string) => `\n$$\n${body}\n$$\n`,
  );
  text = text.replace(/(?<!\\)\\\[([\s\S]*?)\\\]/g, (_, body: string) => `\n$$\n${body}\n$$\n`);
  text = text.replace(/(?<!\\)\\\(([\s\S]*?)\\\)/g, (_, body: string) => `$${body.trim()}$`);
  return text.replace(
    new RegExp(`${marker}(\\d+)\u0000`, 'g'),
    (_, index: string) => protectedSpans[Number(index)],
  );
}
