/** 仅转换展示内容；原消息、复制和导出保留供应商原文。代码区不参与公式归一化。 */
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
