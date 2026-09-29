/**
 * 本地「可读文本投影」——**只服务旧历史展示**（RAG-QUALITY v1.1 · F0-COMPACT-CHAT）。
 *
 * 三种文本必须区分（PLAN §2.2）：封存原文不可变；清洗文本按清洗版本派生；简短回答由回答
 * 策略生成。新结果一律使用后端给出的 `evidence[].readable`（`rag-readable-v1`）；**本文件
 * 只用于旧历史消息缺 `readable` 时的展示降级**，不改库、不回传、不作为引用依据。
 *
 * 规则与 `apps/api/app/services/text_projection/**`（B0）逐条一致，唯一对照集是仓库根
 * `tests/fixtures/text-projection-samples.json`（24 组，前后端共用）。**不得另造一套规则**：
 * 改动实现必须同时让 `text-projection.test.ts` 的全部样例通过。
 *
 * 坐标口径：全部是 Unicode 码点（`Array.from` 下标），不是 UTF-16 码元，也不是后端字节。
 *
 * 边界：纯函数、无 I/O、无网络、无图片请求；返回派生文本与映射，从不回写输入。
 */

type SegmentKind = 'kept' | 'alt_kept' | 'removed';

export interface SourceSegment {
  cleanStart: number;
  cleanEnd: number;
  rawStart: number;
  rawEnd: number;
  kind: SegmentKind;
}

export interface TextProjection {
  version: typeof TEXT_PROJECTION_VERSION;
  text: string;
  sourceSegments: SourceSegment[];
  removedImageCount: number;
}

export const TEXT_PROJECTION_VERSION = 'rag-readable-v1';

/** 单行内联图片的整体长度上限（码点）；超过即认为不是真实图片节点 */
const MAX_INLINE_NODE_CHARS = 4096;
/** HTML 标签（含属性）的长度上限（码点） */
const MAX_HTML_TAG_CHARS = 4096;
/** 引用标签长度上限（对齐 CommonMark 的 999） */
const MAX_LABEL_CHARS = 999;

const TRAILING_WHITESPACE = ' \t\r';

interface ProtectedRange {
  start: number;
  end: number;
  kind: 'code_fence' | 'code_span' | 'math_display' | 'math_inline';
}

interface ReferenceDefinition {
  label: string;
  labelKey: string;
  start: number;
  end: number;
  destination: string;
}

interface ImageNode {
  kind: 'markdown_image' | 'html_img' | 'html_picture';
  start: number;
  end: number;
  altStart: number;
  altEnd: number;
  altText: string;
  definition?: ReferenceDefinition;
}

interface RemovalPlan {
  start: number;
  end: number;
  keptSpans: [number, number][];
  imageCount: number;
}

interface Replacement {
  rawStart: number;
  rawEnd: number;
  replacement: string;
  sourceStart: number | null;
  sourceEnd: number | null;
}

interface MappedText {
  text: string;
  segments: SourceSegment[];
}

/* ------------------------------------------------------------------ 基础工具 */

function isEscaped(chars: string[], index: number): boolean {
  let backslashes = 0;
  let cursor = index - 1;
  while (cursor >= 0 && chars[cursor] === '\\') {
    backslashes += 1;
    cursor -= 1;
  }
  return backslashes % 2 === 1;
}

function isSpaceChar(char: string): boolean {
  return /\s/.test(char);
}

function runLength(chars: string[], index: number, char: string): number {
  let cursor = index;
  while (cursor < chars.length && chars[cursor] === char) cursor += 1;
  return cursor - index;
}

/** `(行首, 行尾, 下一行行首)`；行尾不含换行符 */
function iterLines(chars: string[]): [number, number, number][] {
  const lines: [number, number, number][] = [];
  const total = chars.length;
  let cursor = 0;
  while (cursor <= total) {
    let newline = -1;
    for (let probe = cursor; probe < total; probe += 1)
      if (chars[probe] === '\n') {
        newline = probe;
        break;
      }
    if (newline === -1) {
      lines.push([cursor, total, total + 1]);
      break;
    }
    lines.push([cursor, newline, newline + 1]);
    cursor = newline + 1;
    if (cursor === total) {
      lines.push([cursor, total, total + 1]);
      break;
    }
  }
  return lines;
}

function inRanges(ranges: ProtectedRange[], index: number): boolean {
  for (const span of ranges) {
    if (span.start <= index && index < span.end) return true;
    if (span.start > index) return false;
  }
  return false;
}

/** `start` 之后第一个空行（连续两个换行，中间仅空白）的位置 */
function nextBlankLine(chars: string[], start: number): number | null {
  let cursor = start;
  const total = chars.length;
  while (cursor < total) {
    let newline = -1;
    for (let probe = cursor; probe < total; probe += 1)
      if (chars[probe] === '\n') {
        newline = probe;
        break;
      }
    if (newline === -1) return null;
    let probe = newline + 1;
    while (probe < total && ' \t\r'.includes(chars[probe]!)) probe += 1;
    if (probe < total && chars[probe] === '\n') return newline;
    cursor = newline + 1;
  }
  return null;
}

/* ------------------------------------------------------------------ 保护区 */

function fenceMarker(line: string): [string, number] | null {
  const stripped = line.replace(/^ +/, '');
  if (line.length - stripped.length > 3) return null;
  if (!stripped) return null;
  const char = stripped[0]!;
  if (char !== '`' && char !== '~') return null;
  let width = 0;
  while (width < stripped.length && stripped[width] === char) width += 1;
  if (width < 3) return null;
  const rest = stripped.slice(width);
  if (char === '`' && rest.includes('`')) return null;
  return [char, width];
}

function closingFence(line: string, char: string, width: number): boolean {
  const stripped = line.replace(/^ +/, '');
  if (line.length - stripped.length > 3) return false;
  let run = 0;
  while (run < stripped.length && stripped[run] === char) run += 1;
  if (run < width) return false;
  return stripped.slice(run).trim() === '';
}

function scanFences(chars: string[]): ProtectedRange[] {
  const ranges: ProtectedRange[] = [];
  const total = chars.length;
  let cursor = 0;
  while (cursor < total) {
    let newline = -1;
    for (let probe = cursor; probe < total; probe += 1)
      if (chars[probe] === '\n') {
        newline = probe;
        break;
      }
    const lineEnd = newline === -1 ? total : newline;
    const marker = fenceMarker(chars.slice(cursor, lineEnd).join(''));
    if (marker === null) {
      if (newline === -1) break;
      cursor = newline + 1;
      continue;
    }
    const [char, width] = marker;
    let probe = newline !== -1 ? lineEnd + 1 : total;
    let closeEnd: number | null = null;
    while (probe < total) {
      let innerNewline = -1;
      for (let scan = probe; scan < total; scan += 1)
        if (chars[scan] === '\n') {
          innerNewline = scan;
          break;
        }
      const innerEnd = innerNewline === -1 ? total : innerNewline;
      if (closingFence(chars.slice(probe, innerEnd).join(''), char, width)) {
        closeEnd = innerEnd;
        break;
      }
      if (innerNewline === -1) break;
      probe = innerNewline + 1;
    }
    if (closeEnd === null) {
      // 未闭合围栏按 CommonMark 处理到文末
      ranges.push({ start: cursor, end: total, kind: 'code_fence' });
      break;
    }
    ranges.push({ start: cursor, end: closeEnd, kind: 'code_fence' });
    let nextNewline = -1;
    for (let scan = closeEnd; scan < total; scan += 1)
      if (chars[scan] === '\n') {
        nextNewline = scan;
        break;
      }
    if (nextNewline === -1) break;
    cursor = nextNewline + 1;
  }
  return ranges;
}

function dollarCanOpen(chars: string[], index: number, run: number): boolean {
  if (run >= 2) return true;
  const after = index + run;
  if (after >= chars.length) return false;
  return !isSpaceChar(chars[after]!);
}

function dollarCanClose(chars: string[], index: number, run: number): boolean {
  if (run >= 2) return true;
  if (index === 0 || isSpaceChar(chars[index - 1]!)) return false;
  const after = index + run;
  if (after < chars.length && /[0-9]/.test(chars[after]!)) return false;
  return true;
}

/** 找与开始处等长的下一次 char 连续段；返回该段之后的位置 */
function findClosingRun(
  chars: string[],
  start: number,
  char: string,
  width: number,
  options: { allowNewlines: boolean; dollarRules: boolean; skip?: ProtectedRange[] },
): number | null {
  const total = chars.length;
  const blankAt = nextBlankLine(chars, start);
  const skip = options.skip ?? [];
  let skipIndex = 0;
  let cursor = start;
  while (cursor < total) {
    while (skipIndex < skip.length && cursor >= skip[skipIndex]!.end) skipIndex += 1;
    if (skipIndex < skip.length && skip[skipIndex]!.start <= cursor) {
      cursor = skip[skipIndex]!.end;
      continue;
    }
    if (blankAt !== null && cursor > blankAt) return null;
    const current = chars[cursor]!;
    if (current === '\n' && !options.allowNewlines) return null;
    if (current === '\\' && cursor + 1 < total) {
      cursor += 2;
      continue;
    }
    if (current !== char) {
      cursor += 1;
      continue;
    }
    const run = runLength(chars, cursor, char);
    if (run === width) {
      if (!options.dollarRules || dollarCanClose(chars, cursor, run)) return cursor + run;
    }
    cursor += run;
  }
  return null;
}

function scanInlineProtected(chars: string[], fences: ProtectedRange[]): ProtectedRange[] {
  const ranges: ProtectedRange[] = [];
  const total = chars.length;
  let fenceIndex = 0;
  let cursor = 0;
  while (cursor < total) {
    while (fenceIndex < fences.length && cursor >= fences[fenceIndex]!.end) fenceIndex += 1;
    if (fenceIndex < fences.length && fences[fenceIndex]!.start <= cursor) {
      cursor = fences[fenceIndex]!.end;
      continue;
    }
    const char = chars[cursor]!;
    if ((char !== '`' && char !== '$') || isEscaped(chars, cursor)) {
      cursor += 1;
      continue;
    }
    const run = runLength(chars, cursor, char);
    if (char === '`') {
      const end = findClosingRun(chars, cursor + run, '`', run, {
        allowNewlines: true,
        dollarRules: false,
        skip: fences,
      });
      if (end !== null) {
        ranges.push({ start: cursor, end, kind: 'code_span' });
        cursor = end;
        continue;
      }
      cursor += run;
      continue;
    }
    if (!dollarCanOpen(chars, cursor, run)) {
      cursor += run;
      continue;
    }
    const end = findClosingRun(chars, cursor + run, '$', run, {
      allowNewlines: run >= 2,
      dollarRules: true,
      skip: fences,
    });
    if (end !== null) {
      ranges.push({ start: cursor, end, kind: run >= 2 ? 'math_display' : 'math_inline' });
      cursor = end;
      continue;
    }
    cursor += run;
  }
  return ranges;
}

/** 代码围栏、行内代码与公式保护区：其中的 `![…]`/`<img>` 是字面示例，不得当图片节点 */
export function scanCodeAndMathRanges(chars: string[]): ProtectedRange[] {
  const fences = scanFences(chars);
  const inline = scanInlineProtected(chars, fences);
  const merged: ProtectedRange[] = [];
  const ordered = [...fences, ...inline].sort((a, b) => a.start - b.start || a.end - b.end);
  for (const span of ordered) {
    if (fences.some((fence) => fence.start < span.end && span.start < fence.end) && !fences.includes(span))
      continue;
    const last = merged[merged.length - 1];
    if (last && span.start < last.end) continue;
    merged.push(span);
  }
  return merged;
}

/* ------------------------------------------------------------------ 引用定义 */

export function normalizeLabelKey(label: string): string {
  return label.split(/\s+/).filter(Boolean).join(' ').toLowerCase();
}

function parseDestination(chars: string[], cursor: number, limit: number): [string, number] {
  if (cursor >= limit) return ['', cursor];
  if (chars[cursor] === '<') {
    let probe = cursor + 1;
    while (probe < limit) {
      if (chars[probe] === '\\') {
        probe += 2;
        continue;
      }
      if (chars[probe] === '>') return [chars.slice(cursor + 1, probe).join(''), probe + 1];
      if (chars[probe] === '<' || chars[probe] === '\n') return ['', cursor];
      probe += 1;
    }
    return ['', cursor];
  }
  let probe = cursor;
  let depth = 0;
  while (probe < limit) {
    const char = chars[probe]!;
    if (char === '\\') {
      probe += 2;
      continue;
    }
    if (char === ' ' || char === '\t') break;
    if (char === '(') depth += 1;
    else if (char === ')') {
      if (depth === 0) break;
      depth -= 1;
    }
    probe += 1;
  }
  const text = chars.slice(cursor, probe).join('');
  return text ? [text, probe] : ['', cursor];
}

function parseTitle(chars: string[], cursor: number, limit: number): number | null {
  if (cursor >= limit) return null;
  const opener = chars[cursor]!;
  if (!'"\'('.includes(opener)) return null;
  const closer = opener === '(' ? ')' : opener;
  let probe = cursor + 1;
  while (probe < limit) {
    if (chars[probe] === '\\') {
      probe += 2;
      continue;
    }
    if (chars[probe] === closer) return probe + 1;
    if (opener === '(' && chars[probe] === '(') return null;
    probe += 1;
  }
  return null;
}

function parseDefinitionLine(
  chars: string[],
  lineStart: number,
  lineEnd: number,
): ReferenceDefinition | null {
  let cursor = lineStart;
  let indent = 0;
  while (cursor < lineEnd && chars[cursor] === ' ' && indent < 4) {
    cursor += 1;
    indent += 1;
  }
  if (indent > 3 || cursor >= lineEnd || chars[cursor] !== '[') return null;
  const labelStart = cursor + 1;
  let probe = labelStart;
  while (probe < lineEnd) {
    if (chars[probe] === '\\') {
      probe += 2;
      continue;
    }
    if (chars[probe] === '[') return null;
    if (chars[probe] === ']') break;
    probe += 1;
  }
  if (probe >= lineEnd) return null;
  const label = chars.slice(labelStart, probe).join('');
  if (!label.trim() || Array.from(label).length > MAX_LABEL_CHARS) return null;
  cursor = probe + 1;
  if (cursor >= lineEnd || chars[cursor] !== ':') return null;
  cursor += 1;
  while (cursor < lineEnd && ' \t'.includes(chars[cursor]!)) cursor += 1;
  const [destination, afterDestination] = parseDestination(chars, cursor, lineEnd);
  if (!destination) return null;
  cursor = afterDestination;
  while (cursor < lineEnd && ' \t'.includes(chars[cursor]!)) cursor += 1;
  const titleEnd = parseTitle(chars, cursor, lineEnd);
  if (titleEnd !== null) cursor = titleEnd;
  if (chars.slice(cursor, lineEnd).join('').trim() !== '') return null;
  return {
    label,
    labelKey: normalizeLabelKey(label),
    start: lineStart,
    end: lineEnd,
    destination,
  };
}

function scanReferenceDefinitions(
  chars: string[],
  protectedRanges: ProtectedRange[],
): ReferenceDefinition[] {
  const found: ReferenceDefinition[] = [];
  for (const [lineStart, lineEnd] of iterLines(chars)) {
    if (inRanges(protectedRanges, lineStart)) continue;
    const parsed = parseDefinitionLine(chars, lineStart, lineEnd);
    if (parsed) found.push(parsed);
  }
  return found;
}

/* ------------------------------------------------------------------ 图片节点 */

function trimSpan(chars: string[], start: number, end: number): [number, number] {
  let from = start;
  let to = end;
  while (from < to && isSpaceChar(chars[from]!)) from += 1;
  while (to > from && isSpaceChar(chars[to - 1]!)) to -= 1;
  return [from, to];
}

function lineLimit(chars: string[], index: number): number {
  for (let probe = index; probe < chars.length; probe += 1)
    if (chars[probe] === '\n') return probe;
  return chars.length;
}

function findMatchingBracket(
  chars: string[],
  openIndex: number,
  protectedRanges: ProtectedRange[],
): number | null {
  const limit = Math.min(chars.length, openIndex + MAX_INLINE_NODE_CHARS);
  let depth = 0;
  let cursor = openIndex;
  while (cursor < limit) {
    if (inRanges(protectedRanges, cursor)) return null;
    const char = chars[cursor]!;
    if (char === '\\') {
      cursor += 2;
      continue;
    }
    if (char === '\n') return null;
    if (char === '[') depth += 1;
    else if (char === ']') {
      depth -= 1;
      if (depth === 0) return cursor;
    }
    cursor += 1;
  }
  return null;
}

/** 解析 `(dest "title")`；返回右括号之后的位置 */
function parseInlineDestination(
  chars: string[],
  openIndex: number,
  allowEmpty: boolean,
): number | null {
  const limit = lineLimit(chars, openIndex);
  let cursor = openIndex + 1;
  while (cursor < limit && ' \t'.includes(chars[cursor]!)) cursor += 1;
  const [destination, afterDestination] = parseDestination(chars, cursor, limit);
  cursor = afterDestination;
  if (!destination && !allowEmpty) return null;
  while (cursor < limit && ' \t'.includes(chars[cursor]!)) cursor += 1;
  const titleEnd = parseTitle(chars, cursor, limit);
  if (titleEnd !== null) cursor = titleEnd;
  while (cursor < limit && ' \t'.includes(chars[cursor]!)) cursor += 1;
  if (cursor >= limit || chars[cursor] !== ')') return null;
  return cursor + 1;
}

function parseMarkdownImage(
  chars: string[],
  start: number,
  definitions: Map<string, ReferenceDefinition>,
  protectedRanges: ProtectedRange[],
): ImageNode | null {
  const bracket = start + 1;
  const close = findMatchingBracket(chars, bracket, protectedRanges);
  if (close === null) return null;
  const altStart = bracket + 1;
  const altEnd = close;
  const altText = chars.slice(altStart, altEnd).join('');
  const cursor = close + 1;
  if (cursor < chars.length && chars[cursor] === '(') {
    const end = parseInlineDestination(chars, cursor, true);
    if (end === null) return null;
    return { kind: 'markdown_image', start, end, altStart, altEnd, altText };
  }
  if (cursor < chars.length && chars[cursor] === '[') {
    const refClose = findMatchingBracket(chars, cursor, protectedRanges);
    if (refClose === null) return null;
    const label = chars.slice(cursor + 1, refClose).join('');
    const key = label.trim() ? normalizeLabelKey(label) : normalizeLabelKey(altText);
    const definition = definitions.get(key);
    if (!definition) return null;
    return {
      kind: 'markdown_image',
      start,
      end: refClose + 1,
      altStart,
      altEnd,
      altText,
      definition,
    };
  }
  // 简写式 `![说明]`：只有存在同名引用定义时才算图片节点
  const definition = definitions.get(normalizeLabelKey(altText));
  if (!definition) return null;
  return { kind: 'markdown_image', start, end: close + 1, altStart, altEnd, altText, definition };
}

function parseMarkdownLink(
  chars: string[],
  start: number,
  definitions: Map<string, ReferenceDefinition>,
  protectedRanges: ProtectedRange[],
): { contentStart: number; contentEnd: number; linkEnd: number; definition?: ReferenceDefinition } | null {
  const close = findMatchingBracket(chars, start, protectedRanges);
  if (close === null) return null;
  const contentStart = start + 1;
  const contentEnd = close;
  const cursor = close + 1;
  if (cursor < chars.length && chars[cursor] === '(') {
    const end = parseInlineDestination(chars, cursor, true);
    if (end === null) return null;
    return { contentStart, contentEnd, linkEnd: end };
  }
  if (cursor < chars.length && chars[cursor] === '[') {
    const refClose = findMatchingBracket(chars, cursor, protectedRanges);
    if (refClose === null) return null;
    const label = chars.slice(cursor + 1, refClose).join('');
    const fallback = chars.slice(contentStart, contentEnd).join('');
    const key = label.trim() ? normalizeLabelKey(label) : normalizeLabelKey(fallback);
    const definition = definitions.get(key);
    if (!definition) return null;
    return { contentStart, contentEnd, linkEnd: refClose + 1, definition };
  }
  const definition = definitions.get(normalizeLabelKey(chars.slice(contentStart, contentEnd).join('')));
  if (!definition) return null;
  return { contentStart, contentEnd, linkEnd: close + 1, definition };
}

interface HtmlTag {
  name: string;
  end: number;
  attrs: Map<string, { value: string; start: number; end: number }>;
}

function parseHtmlTag(chars: string[], start: number): HtmlTag | null {
  const total = chars.length;
  if (chars[start] !== '<') return null;
  let cursor = start + 1;
  if (cursor < total && '/!?'.includes(chars[cursor]!)) return null;
  const nameStart = cursor;
  while (cursor < total && /[\p{L}\p{N}_:-]/u.test(chars[cursor]!)) cursor += 1;
  const name = chars.slice(nameStart, cursor).join('').toLowerCase();
  if (!name) return null;
  if (cursor < total && !' \t\n\r/>'.includes(chars[cursor]!)) return null;
  const limit = Math.min(total, start + MAX_HTML_TAG_CHARS);
  const attrs = new Map<string, { value: string; start: number; end: number }>();
  while (cursor < limit) {
    const char = chars[cursor]!;
    if (char === '>') return { name, end: cursor + 1, attrs };
    if (char === '/' && cursor + 1 < limit && chars[cursor + 1] === '>')
      return { name, end: cursor + 2, attrs };
    if (' \t\n\r'.includes(char)) {
      cursor += 1;
      continue;
    }
    const attrStart = cursor;
    while (cursor < limit && !'= \t\n\r/>'.includes(chars[cursor]!)) cursor += 1;
    const attrName = chars.slice(attrStart, cursor).join('').toLowerCase();
    while (cursor < limit && ' \t\n\r'.includes(chars[cursor]!)) cursor += 1;
    let value = '';
    let valueStart = cursor;
    let valueEnd = cursor;
    if (cursor < limit && chars[cursor] === '=') {
      cursor += 1;
      while (cursor < limit && ' \t\n\r'.includes(chars[cursor]!)) cursor += 1;
      if (cursor < limit && '"\'"'.includes(chars[cursor]!)) {
        const quote = chars[cursor]!;
        cursor += 1;
        valueStart = cursor;
        while (cursor < limit && chars[cursor] !== quote) cursor += 1;
        value = chars.slice(valueStart, cursor).join('');
        valueEnd = cursor;
        cursor += 1;
      } else {
        valueStart = cursor;
        while (cursor < limit && !' \t\n\r>'.includes(chars[cursor]!)) cursor += 1;
        value = chars.slice(valueStart, cursor).join('');
        valueEnd = cursor;
      }
    }
    if (attrName && !attrs.has(attrName)) attrs.set(attrName, { value, start: valueStart, end: valueEnd });
  }
  return null;
}

function findHtmlClose(chars: string[], name: string, start: number): [number, number] | null {
  const lowered = chars.join('').toLowerCase();
  const marker = `</${name}`;
  let cursor = start;
  for (;;) {
    const found = lowered.indexOf(marker, cursor);
    if (found === -1) return null;
    const after = found + marker.length;
    if (after < chars.length && ' \t\n\r>'.includes(chars[after]!)) {
      const closing = chars.join('').indexOf('>', after);
      if (closing !== -1 && closing - found <= MAX_HTML_TAG_CHARS) return [found, closing + 1];
    }
    cursor = found + 1;
  }
}

interface HtmlHit {
  start: number;
  end: number;
  nodes: ImageNode[];
}

function parseHtmlMedia(chars: string[], start: number): HtmlHit | null {
  const tag = parseHtmlTag(chars, start);
  if (!tag) return null;
  if (tag.name === 'img') {
    const alt = tag.attrs.get('alt') ?? { value: '', start: tag.end, end: tag.end };
    const node: ImageNode = {
      kind: 'html_img',
      start,
      end: tag.end,
      altStart: alt.start,
      altEnd: alt.end,
      altText: alt.value,
    };
    return { start, end: tag.end, nodes: [node] };
  }
  if (tag.name === 'picture') {
    const closed = findHtmlClose(chars, 'picture', tag.end);
    if (!closed) return null;
    const [contentEnd, elementEnd] = closed;
    const inner = scanChildImages(chars, tag.end, contentEnd, new Map(), []);
    const img = inner[0];
    const node: ImageNode = {
      kind: 'html_picture',
      start,
      end: elementEnd,
      altStart: img ? img.altStart : elementEnd,
      altEnd: img ? img.altEnd : elementEnd,
      altText: img ? img.altText : '',
    };
    return { start, end: elementEnd, nodes: [node] };
  }
  if (tag.name === 'source') {
    if (!tag.attrs.has('srcset') && !tag.attrs.has('src')) return null;
    return { start, end: tag.end, nodes: [] };
  }
  if (tag.name !== 'a') return null;
  const closed = findHtmlClose(chars, 'a', tag.end);
  if (!closed) return null;
  const [contentEnd, elementEnd] = closed;
  const children = scanChildImages(chars, tag.end, contentEnd, new Map(), []);
  if (!children.length || !childrenCover(chars, tag.end, contentEnd, children)) return null;
  return { start, end: elementEnd, nodes: children };
}

function childrenCover(chars: string[], start: number, end: number, nodes: ImageNode[]): boolean {
  let cursor = start;
  for (const node of nodes) {
    if (chars.slice(cursor, node.start).join('').trim()) return false;
    cursor = node.end;
  }
  return chars.slice(cursor, end).join('').trim() === '';
}

function keptSpanFor(chars: string[], node: ImageNode): [number, number] | null {
  const [coreStart, coreEnd] = trimSpan(chars, node.altStart, node.altEnd);
  if (coreStart >= coreEnd) return null;
  if (!meaningfulAltText(chars.slice(coreStart, coreEnd).join(''))) return null;
  return [coreStart, coreEnd];
}

function planFor(chars: string[], nodes: ImageNode[], start: number, end: number): RemovalPlan {
  const kept: [number, number][] = [];
  for (const node of nodes) {
    const span = keptSpanFor(chars, node);
    if (span) kept.push(span);
  }
  return { start, end, keptSpans: kept.sort((a, b) => a[0] - b[0] || a[1] - b[1]), imageCount: nodes.length };
}

function scanChildImages(
  chars: string[],
  start: number,
  end: number,
  definitions: Map<string, ReferenceDefinition>,
  protectedRanges: ProtectedRange[],
): ImageNode[] {
  const found: ImageNode[] = [];
  let cursor = start;
  let protectedIndex = 0;
  while (cursor < end) {
    while (protectedIndex < protectedRanges.length && cursor >= protectedRanges[protectedIndex]!.end)
      protectedIndex += 1;
    if (protectedIndex < protectedRanges.length && protectedRanges[protectedIndex]!.start <= cursor) {
      cursor = protectedRanges[protectedIndex]!.end;
      continue;
    }
    const char = chars[cursor]!;
    if (char === '!' && !isEscaped(chars, cursor) && chars[cursor + 1] === '[') {
      const node = parseMarkdownImage(chars, cursor, definitions, protectedRanges);
      if (node && node.end <= end) {
        found.push(node);
        cursor = node.end;
        continue;
      }
    } else if (char === '<') {
      const hit = parseHtmlMedia(chars, cursor);
      if (hit && hit.end <= end) {
        found.push(...hit.nodes);
        cursor = hit.end;
        continue;
      }
    }
    cursor += 1;
  }
  return found;
}

function finalizePlans(plans: RemovalPlan[]): RemovalPlan[] {
  const ordered = [...plans].sort((a, b) => a.start - b.start || a.end - b.end);
  const result: RemovalPlan[] = [];
  let previousEnd = -1;
  for (const plan of ordered) {
    if (plan.start < previousEnd) continue;
    result.push(plan);
    previousEnd = plan.end;
  }
  return result;
}

function definitionPlan(chars: string[], definition: ReferenceDefinition): RemovalPlan {
  let end = definition.end;
  if (end < chars.length && chars[end] === '\n') end += 1;
  return { start: definition.start, end, keptSpans: [], imageCount: 0 };
}

interface ScanResult {
  protectedRanges: ProtectedRange[];
  definitions: ReferenceDefinition[];
  plans: RemovalPlan[];
}

function scanDocument(chars: string[]): ScanResult {
  const protectedRanges = scanCodeAndMathRanges(chars);
  const definitions = scanReferenceDefinitions(chars, protectedRanges);
  const definitionMap = new Map(definitions.map((item) => [item.labelKey, item]));
  const plans: RemovalPlan[] = [];
  const imageLabels = new Set<string>();
  const textLabels = new Set<string>();
  const total = chars.length;
  const definitionLines = new Map(definitions.map((item) => [item.start, item]));
  let cursor = 0;
  let protectedIndex = 0;
  while (cursor < total) {
    while (protectedIndex < protectedRanges.length && cursor >= protectedRanges[protectedIndex]!.end)
      protectedIndex += 1;
    if (protectedIndex < protectedRanges.length && protectedRanges[protectedIndex]!.start <= cursor) {
      cursor = protectedRanges[protectedIndex]!.end;
      continue;
    }
    const definition = definitionLines.get(cursor);
    if (definition) {
      cursor = definition.end < total ? definition.end + 1 : total;
      continue;
    }
    const char = chars[cursor]!;
    if (char === '!' && !isEscaped(chars, cursor) && chars[cursor + 1] === '[') {
      const node = parseMarkdownImage(chars, cursor, definitionMap, protectedRanges);
      if (node) {
        plans.push(planFor(chars, [node], node.start, node.end));
        if (node.definition) imageLabels.add(node.definition.labelKey);
        cursor = node.end;
        continue;
      }
    } else if (char === '[' && !isEscaped(chars, cursor)) {
      const parsed = parseMarkdownLink(chars, cursor, definitionMap, protectedRanges);
      if (parsed) {
        const children = scanChildImages(
          chars,
          parsed.contentStart,
          parsed.contentEnd,
          definitionMap,
          protectedRanges,
        );
        if (children.length && childrenCover(chars, parsed.contentStart, parsed.contentEnd, children)) {
          plans.push(planFor(chars, children, cursor, parsed.linkEnd));
          if (parsed.definition) imageLabels.add(parsed.definition.labelKey);
          cursor = parsed.linkEnd;
          continue;
        }
        if (parsed.definition) textLabels.add(parsed.definition.labelKey);
      }
    } else if (char === '<') {
      const hit = parseHtmlMedia(chars, cursor);
      if (hit) {
        plans.push(planFor(chars, hit.nodes, hit.start, hit.end));
        cursor = hit.end;
        continue;
      }
    }
    cursor += 1;
  }
  for (const item of definitions) {
    if (textLabels.has(item.labelKey)) continue;
    if (imageLabels.has(item.labelKey)) plans.push(definitionPlan(chars, item));
  }
  return { protectedRanges, definitions, plans: finalizePlans(plans) };
}

/* --------------------------------------------------------------- alt 判定 */

const IMAGE_EXTENSIONS = new Set([
  'avif',
  'bmp',
  'gif',
  'heic',
  'heif',
  'ico',
  'jpeg',
  'jpg',
  'png',
  'svg',
  'tif',
  'tiff',
  'webp',
]);

const GENERIC_ALT_PATTERN =
  /^(?:image|images|img|imgs|pic|pics|photo|photos|picture|pictures|figure|figures|fig|figs|illustration|diagram|chart|graph|screenshot|图片|图像|图|插图|附图|示意图|图表|照片|配图)[\s\-_.:：#]*\d*$/i;
const LONG_OPAQUE_PATTERN = /^[0-9A-Za-z]{32,}$/;
const HEX_PATTERN = /^(?=[0-9A-Fa-f])[0-9A-Fa-f\s\-_.]+$/;
const UUID_PATTERN = /^\{?[0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12}\}?$/;
const FILENAME_PATTERN = /^[\w\-.()（）[\] ]+\.[A-Za-z0-9]{2,5}$/;
const HEX_MIN_DIGITS = 16;

export function looksLikePath(text: string): boolean {
  if (['/', '\\', '://'].some((marker) => text.includes(marker))) return true;
  if (!FILENAME_PATTERN.test(text)) return false;
  const suffix = text.slice(text.lastIndexOf('.') + 1).toLowerCase();
  return IMAGE_EXTENSIONS.has(suffix);
}

export function looksLikeHash(text: string): boolean {
  if (UUID_PATTERN.test(text)) return true;
  if (LONG_OPAQUE_PATTERN.test(text)) return true;
  if (HEX_PATTERN.test(text)) return text.replace(/[\s\-_.]/g, '').length >= HEX_MIN_DIGITS;
  return false;
}

export function looksLikeGenericPlaceholder(text: string): boolean {
  return GENERIC_ALT_PATTERN.test(text);
}

/** 返回可作为说明文字保留的 alt；不具说明价值时返回空串（与后端 `meaningful_alt_text` 一致） */
export function meaningfulAltText(text: string): string {
  const core = text.trim();
  if (!core) return '';
  if (looksLikePath(core) || looksLikeHash(core) || looksLikeGenericPlaceholder(core)) return '';
  return core;
}

/* ------------------------------------------------------------------ 替换与映射 */

function replacementsFromPlans(chars: string[], plans: RemovalPlan[]): Replacement[] {
  const replacements: Replacement[] = [];
  for (const plan of plans) {
    let cursor = plan.start;
    for (const [keptStart, keptEnd] of plan.keptSpans) {
      if (keptStart > cursor)
        replacements.push({
          rawStart: cursor,
          rawEnd: keptStart,
          replacement: '',
          sourceStart: null,
          sourceEnd: null,
        });
      replacements.push({
        rawStart: keptStart,
        rawEnd: keptEnd,
        replacement: chars.slice(keptStart, keptEnd).join(''),
        sourceStart: keptStart,
        sourceEnd: keptEnd,
      });
      cursor = keptEnd;
    }
    if (cursor < plan.end)
      replacements.push({
        rawStart: cursor,
        rawEnd: plan.end,
        replacement: '',
        sourceStart: null,
        sourceEnd: null,
      });
  }
  return replacements;
}

type Piece = [number, number, string | null, SegmentKind];

function buildPieces(chars: string[], replacements: Replacement[]): Piece[] {
  const ordered = [...replacements].sort((a, b) => a.rawStart - b.rawStart || a.rawEnd - b.rawEnd);
  const pieces: Piece[] = [];
  let previousEnd = 0;
  for (const replacement of ordered) {
    if (replacement.rawStart > previousEnd)
      pieces.push([previousEnd, replacement.rawStart, null, 'kept']);
    if (replacement.replacement) {
      const sourceStart = replacement.sourceStart!;
      const sourceEnd = replacement.sourceEnd!;
      pieces.push([replacement.rawStart, sourceStart, '', 'removed']);
      pieces.push([sourceStart, sourceEnd, replacement.replacement, 'alt_kept']);
      pieces.push([sourceEnd, replacement.rawEnd, '', 'removed']);
    } else {
      pieces.push([replacement.rawStart, replacement.rawEnd, '', 'removed']);
    }
    previousEnd = replacement.rawEnd;
  }
  if (previousEnd < chars.length) pieces.push([previousEnd, chars.length, null, 'kept']);
  if (!pieces.length) pieces.push([0, 0, '', 'kept']);
  return pieces;
}

function mergeRemovedSegments(segments: SourceSegment[]): SourceSegment[] {
  const merged: SourceSegment[] = [];
  for (const segment of segments) {
    if (segment.kind === 'removed' && segment.rawStart === segment.rawEnd) continue;
    const previous = merged[merged.length - 1];
    if (previous && previous.kind === 'removed' && segment.kind === 'removed') {
      if (previous.cleanStart === segment.cleanStart && previous.rawEnd === segment.rawStart) {
        merged[merged.length - 1] = {
          cleanStart: previous.cleanStart,
          cleanEnd: previous.cleanEnd,
          rawStart: previous.rawStart,
          rawEnd: segment.rawEnd,
          kind: 'removed',
        };
        continue;
      }
    }
    merged.push(segment);
  }
  return merged;
}

function applyReplacementsWithSourceMapping(chars: string[], replacements: Replacement[]): MappedText {
  const pieces = buildPieces(chars, replacements);
  const textParts: string[] = [];
  const segments: SourceSegment[] = [];
  let cleanCursor = 0;
  for (const [rawStart, rawEnd, cleanText, kind] of pieces) {
    if (kind === 'removed') {
      if (rawEnd > rawStart)
        segments.push({
          cleanStart: cleanCursor,
          cleanEnd: cleanCursor,
          rawStart,
          rawEnd,
          kind: 'removed',
        });
      continue;
    }
    const pieceText = cleanText === null ? chars.slice(rawStart, rawEnd).join('') : cleanText;
    const pieceLength = Array.from(pieceText).length;
    textParts.push(pieceText);
    segments.push({
      cleanStart: cleanCursor,
      cleanEnd: cleanCursor + pieceLength,
      rawStart,
      rawEnd,
      kind,
    });
    cleanCursor += pieceLength;
  }
  return { text: textParts.join(''), segments: mergeRemovedSegments(segments) };
}

/* ------------------------------------------------------------------ 有限归一 */

function blankLineKeepMask(text: string): boolean[] {
  const chars = Array.from(text);
  const keep = chars.map(() => true);
  const lines = iterLines(chars);
  for (const [start, end] of lines) {
    let cursor = end;
    while (cursor > start && TRAILING_WHITESPACE.includes(chars[cursor - 1]!)) cursor -= 1;
    for (let index = cursor; index < end; index += 1) keep[index] = false;
  }
  const blank = lines.map(([start, end]) => chars.slice(start, end).join('').trim() === '');
  const contentLines = blank.map((isBlank, index) => (isBlank ? -1 : index)).filter((index) => index >= 0);
  if (!contentLines.length) return keep.map(() => false);
  const firstContent = contentLines[0]!;
  const lastContent = contentLines[contentLines.length - 1]!;
  for (let index = 0; index < lines[firstContent]![0]; index += 1) keep[index] = false;
  for (let index = lines[lastContent]![1]; index < chars.length; index += 1) keep[index] = false;
  let runStarted = false;
  for (let index = firstContent; index <= lastContent; index += 1) {
    if (!blank[index]) {
      runStarted = false;
      continue;
    }
    if (!runStarted) {
      runStarted = true;
      continue;
    }
    const [, , nextStart] = lines[index]!;
    for (let probe = lines[index]![0]; probe < Math.min(nextStart, chars.length); probe += 1)
      keep[probe] = false;
  }
  return keep;
}

function normalizeBlankLinesOnly(mapped: MappedText): MappedText {
  const keep = blankLineKeepMask(mapped.text);
  if (keep.every(Boolean)) return mapped;
  const prefix = new Array<number>(keep.length + 1).fill(0);
  for (let index = 0; index < keep.length; index += 1)
    prefix[index + 1] = prefix[index]! + (keep[index] ? 1 : 0);
  const chars = Array.from(mapped.text);
  const text = chars.filter((_, index) => keep[index]).join('');
  const segments: SourceSegment[] = [];
  const shifted = (
    segment: SourceSegment,
    cleanStart: number,
    cleanEnd: number,
    kind: SegmentKind,
  ): SourceSegment => {
    const offset = cleanStart - segment.cleanStart;
    const rawStart = segment.rawStart + offset;
    const rawEnd = rawStart + (cleanEnd - cleanStart);
    if (kind === 'removed')
      return {
        cleanStart: prefix[cleanStart]!,
        cleanEnd: prefix[cleanStart]!,
        rawStart,
        rawEnd,
        kind,
      };
    const length = cleanEnd - cleanStart;
    return {
      cleanStart: prefix[cleanStart]!,
      cleanEnd: prefix[cleanStart]! + length,
      rawStart,
      rawEnd,
      kind,
    };
  };
  for (const segment of mapped.segments) {
    if (segment.cleanStart === segment.cleanEnd) {
      segments.push({
        cleanStart: prefix[segment.cleanStart]!,
        cleanEnd: prefix[segment.cleanStart]!,
        rawStart: segment.rawStart,
        rawEnd: segment.rawEnd,
        kind: segment.kind,
      });
      continue;
    }
    let cursor = segment.cleanStart;
    const runs: [number, number][] = [];
    let probe = segment.cleanStart;
    while (probe < segment.cleanEnd) {
      if (!keep[probe]) {
        probe += 1;
        continue;
      }
      let runEnd = probe;
      while (runEnd < segment.cleanEnd && keep[runEnd]) runEnd += 1;
      runs.push([probe, runEnd]);
      probe = runEnd;
    }
    for (const [runStart, runEnd] of runs) {
      if (runStart > cursor) segments.push(shifted(segment, cursor, runStart, 'removed'));
      segments.push(shifted(segment, runStart, runEnd, segment.kind));
      cursor = runEnd;
    }
    if (cursor < segment.cleanEnd) segments.push(shifted(segment, cursor, segment.cleanEnd, 'removed'));
  }
  return { text, segments: mergeRemovedSegments(segments) };
}

/* ------------------------------------------------------------------ 公开入口 */

/**
 * 旧历史展示用清洗：清除图片 Markdown/HTML，保留公式、表格、正文与图注。
 * **只按 Unicode 码点计算**；不修改输入，不产生任何网络请求。
 */
export function projectReadableText(raw: string): TextProjection {
  const chars = Array.from(raw);
  const scan = scanDocument(chars);
  const mapped = applyReplacementsWithSourceMapping(chars, replacementsFromPlans(chars, scan.plans));
  const normalized = normalizeBlankLinesOnly(mapped);
  return {
    version: TEXT_PROJECTION_VERSION,
    text: normalized.text,
    sourceSegments: normalized.segments,
    removedImageCount: scan.plans.reduce((total, plan) => total + plan.imageCount, 0),
  };
}
