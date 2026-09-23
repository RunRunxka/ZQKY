/**
 * 流式 Markdown 的安全切分（UX-REGRESSION-FIX v1）。
 *
 * 目的：推理流在**流式过程中**也要显示公式，但不能对每个 delta 重跑整段增长文本的
 * Markdown/KaTeX 解析（上一批的长推理卡顿就是这么来的）。做法是把文本切成
 * 「已完整结束的块」+「未完成的尾段」：
 * - 块只在**空行边界**切开，且不切进未闭合的围栏代码块、不切进 `$$` 块级公式；
 *   列表/引用项的松散空行不切（避免一个列表被拆成多个列表）；
 * - 块的内容字符串一旦确定就不再变化 → 交给 memo 化的 Markdown 组件时解析结果可复用，
 *   整轮解析总量回到 O(n)（每个字符最多被完整解析一次）；
 * - 尾段可能含未闭合定界符：`tailSafe` 为真时可以用 Markdown 渲染（公式即时可见），
 *   为假或尾段过长时按原文显示，补齐后自动转为公式。
 *
 * 返回值满足 `blocks.join('') + tail === text`（逐字保留，含原换行）。
 * 本模块是纯函数，不依赖 DOM，可单测。
 */

export interface MarkdownSegments {
  /** 已完整结束、可安全按 Markdown 渲染的块（顺序稳定，只追加） */
  blocks: string[];
  /** 未完成的尾段（可能含未闭合定界符） */
  tail: string;
  /** 尾段的定界符是否闭合且长度受控（是则可用 Markdown 渲染，公式即时可见） */
  tailSafe: boolean;
}

/** 尾段超过该长度时不再用 Markdown 渲染（避免每帧解析很长的增长中文本） */
export const DEFAULT_TAIL_LIMIT = 4000;

const FENCE_RE = /^ {0,3}(`{3,}|~{3,})/;
const LIST_OR_QUOTE_RE = /^ {0,3}(?:[-*+]|\d+[.)]|>)/;

/** 行内定界符是否闭合（行内代码、行内公式、反斜杠行内/块级公式） */
function inlineIsBalanced(text: string): boolean {
  // 先去掉完整的围栏代码块：里面的 $ 与反引号都不参与判定
  const withoutFences = text.replace(
    /^ {0,3}(`{3,}|~{3,})[^\n]*\n[\s\S]*?(?:^ {0,3}\1[ \t]*(?=\n|$)|$)/gm,
    '',
  );
  if ((withoutFences.match(/`/g) ?? []).length % 2 !== 0) return false;
  // 再去掉行内代码后数数学定界符，避免把代码里的美元符号算进去
  const withoutCode = withoutFences.replace(/`+[^`\n]*?`+/g, '');
  if ((withoutCode.match(/(?<!\\)\$/g) ?? []).length % 2 !== 0) return false;
  if (/\\\(/.test(withoutCode) && !/\\\)/.test(withoutCode)) return false;
  if (/\\\[/.test(withoutCode) && !/\\\]/.test(withoutCode)) return false;
  return true;
}

/**
 * 在尾段内寻找可安全「上提为块」的行边界（行尾且定界符全部闭合）。
 *
 * 用途：尾段超过上限时，把前面已闭合的部分上提为块（解析一次后缓存），
 * 使**每次提交只解析一个受长度约束的尾段**，而不是整段增长文本。
 * 只在行边界切分，且不切在表格行前（避免把表头与表体拆开）。
 */
export function findPromotableLineBoundary(tail: string, maxLength: number): number {
  let fence: string | null = null;
  let inMathBlock = false;
  let frameLine = false; // 当前行是围栏/块级公式标记行：不计其中的定界符
  let ticks = 0;
  let dollarOpen = false;
  let parenOpen = false;
  let bracketOpen = false;
  let lastCandidate = -1;

  for (let i = 0; i < tail.length; i += 1) {
    const ch = tail[i]!;
    if (i === 0 || tail[i - 1] === '\n') {
      const lineEnd = tail.indexOf('\n', i);
      const line = tail.slice(i, lineEnd === -1 ? tail.length : lineEnd);
      frameLine = false;
      const fenceMatch = FENCE_RE.exec(line);
      if (fenceMatch) {
        const marker = fenceMatch[1]![0]!;
        if (fence === null) fence = marker;
        else if (fence === marker) fence = null;
        frameLine = true;
      } else if (fence === null && /^ {0,3}\$\$\s*$/.test(line)) {
        inMathBlock = !inMathBlock;
        frameLine = true;
      }
      // 行首且所有定界符平衡 → 候选切点（不切在表格行前，避免表头与表体分离）
      if (
        i > 0 &&
        i <= maxLength &&
        fence === null &&
        !inMathBlock &&
        ticks % 2 === 0 &&
        !dollarOpen &&
        !parenOpen &&
        !bracketOpen &&
        !line.startsWith('|')
      ) {
        lastCandidate = i;
      }
    }
    // 标记行的字符不参与计数；未闭合围栏内同理（其内部不切分）
    if (frameLine || fence !== null) continue;
    if (ch === '`') ticks += 1;
    else if (ch === '$' && tail[i - 1] !== '\\') dollarOpen = !dollarOpen;
    else if (ch === '\\' && tail[i + 1] === '(') parenOpen = true;
    else if (ch === '\\' && tail[i + 1] === ')') parenOpen = false;
    else if (ch === '\\' && tail[i + 1] === '[') bracketOpen = true;
    else if (ch === '\\' && tail[i + 1] === ']') bracketOpen = false;
  }
  return lastCandidate;
}

/**
 * 把流式文本切成安全块 + 尾段。返回的 `blocks.join('') + tail` 与输入逐字一致。
 */
export function splitMarkdownSegments(
  text: string,
  options: { tailLimit?: number } = {},
): MarkdownSegments {
  const tailLimit = options.tailLimit ?? DEFAULT_TAIL_LIMIT;
  if (!text) return { blocks: [], tail: '', tailSafe: true };

  const lines = text.split('\n');
  const offsets: number[] = [];
  let offset = 0;
  for (const line of lines) {
    offsets.push(offset);
    offset += line.length + 1; // + '\n'
  }
  offsets.push(offset); // 末尾哨兵

  const blocks: string[] = [];
  let blockStart = 0;
  let fence: string | null = null;
  let inMathBlock = false;

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i]!;
    const fenceMatch = FENCE_RE.exec(line);
    if (fenceMatch) {
      const marker = fenceMatch[1]![0]!;
      if (fence === null) fence = marker;
      else if (fence === marker) fence = null;
    } else if (fence === null && /^ {0,3}\$\$\s*$/.test(line)) {
      inMathBlock = !inMathBlock;
    }

    if (line.trim() !== '' || fence !== null || inMathBlock) continue;

    // 空行：不在围栏/块级公式内，且不是列表/引用的松散分隔时才切块
    let next = i + 1;
    while (next < lines.length && lines[next]!.trim() === '') next += 1;
    const continuesList =
      lines[next] !== undefined && LIST_OR_QUOTE_RE.test(lines[next]!) &&
      LIST_OR_QUOTE_RE.test(lines[Math.max(0, i - 1)] ?? '');
    if (continuesList) continue;
    // 空行本身（含其换行）归属前一个块
    blocks.push(text.slice(offsets[blockStart]!, offsets[i + 1]!));
    blockStart = i + 1;
  }

  let tail = text.slice(offsets[blockStart]!);
  // 尾段过长时把前面已闭合的部分上提为块（解析一次并缓存）：
  // 每次提交只解析一个受长度约束的尾段，同时保持"已闭合的公式即时显示"。
  while (tail.length > tailLimit) {
    const boundary = findPromotableLineBoundary(tail, tailLimit);
    if (boundary <= 0) break;
    blocks.push(tail.slice(0, boundary));
    tail = tail.slice(boundary);
  }
  const tailSafe =
    fence === null && !inMathBlock && tail.length <= tailLimit && inlineIsBalanced(tail);
  return { blocks, tail, tailSafe };
}
