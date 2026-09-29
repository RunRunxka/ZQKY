/**
 * 单一消息投影（RAG-QUALITY v1.1 · PLAN §4.1）——**显示、默认复制、后续历史上下文都用它**。
 *
 * 背景（Q1）：旧路径把 `message.content`（后端已拼接知识点 + 全部教材原文）直接渲染，
 * 同时证据面板再展示一遍原文，造成同一份内容两次出现。现在：
 *
 * - 结构化首答（有 `ragResult` 且**无** `ragExplain`）→ 紧凑视图：只展示知识点 + `[n]`
 *   引用编号，教材原文只在「教材依据」面板按需展开；
 * - 普通回答、详解回答、旧 v1 → 原正文，不做任何截断；
 * - 判定只看**结构化字段**（`ragResult` 是否存在 + `presentation?.version`），
 *   **绝不**用「查找『教材原文摘录』再截掉一段」这类字符串猜测处理历史消息。
 *
 * 历史兼容（PLAN §4.3）：
 * - 有完整 `ragResult` 的旧 v2 首答 → 即时用本投影，**不改 IndexedDB 原记录**；
 *   旧知识点本身很长时，优先展示能完整装入预算的点，其余放进「展开旧答」（不截断、不伪造摘要）；
 * - `readable` 缺失（旧消息）→ 展示降级为 `evidence.text`，明确标注「未清洗历史原文」，
 *   并对**旧历史**做一次本地图片语法隐藏（`text-projection.ts`，只影响展示，不改库）；
 * - 只有孤立 `ragEvidence` → 附加折叠来源，不推断正文结构。
 */

import type { ChatMessage } from '@/contracts/chat';
import {
  isRagResultV2,
  locatorLabel,
  type RagPointStatus,
  type RagResultV2,
  type TextbookEvidence,
} from './rag-v2';
import { projectReadableText, scanCodeAndMathRanges } from './text-projection';

/* ------------------------------------------------------------ 预算常数（仅旧结果用） */

/** 来源短预览上限（码点，PLAN §4.2「最多 160 字」） */
export const SOURCE_PREVIEW_MAX_CHARS = 160;
/**
 * 旧 v2 结果的紧凑展示预算（与后端 `app/core/rag_budget.py` 同一口径）。
 * 新结果（`presentation.version === 'compact-v1'`）由后端保证预算，前端**不**再裁剪。
 */
export const COMPACT_MAX_POINTS = 3;
export const COMPACT_POINT_MAX_CHARS = 90;
export const COMPACT_TOTAL_MAX_CHARS = 250;

/* ------------------------------------------------------------ 视图类型 */

export interface CompactSource {
  /** `[n]` 编号 = 该证据在 `result.evidence` 数组中的序号（1 基） */
  index: number;
  evidenceId: string;
  title: string;
  editionLabel: string;
  subjectLabel: string;
  chapterPath: string[];
  locator: string;
  isSuperseded: boolean;
  /** 展示/预览/复制用的清洗文本（新结果 = `readable.text`；旧消息 = 本地清洗结果） */
  readableText: string;
  /** 旧消息缺 `readable`：展示降级，需明确标注「未清洗历史原文」 */
  legacyRaw: boolean;
  /** 被清洗掉的图片节点数（新结果来自 `readable.removedImageCount`） */
  removedImageCount: number;
  /** 最多 160 字、在完整句或结构边界结束的预览；找不到合适短预览时为 null */
  preview: string | null;
}

export interface CompactPoint {
  pointId: string;
  title: string;
  /** 展示用说明：能完整装入预算时给出；装不下时为空串（不伪造摘要） */
  summary: string;
  /** `[n]` 引用编号（未在来源列表中的编号不在此列，避免造出不存在的来源） */
  citations: number[];
  /** 旧答中未装入紧凑预算的完整说明（放「展开旧答」）；无则为 null */
  overflowSummary: string | null;
}

export interface RagMessageView {
  kind: 'rag';
  status: RagPointStatus;
  reasonCode: string | null;
  /** 后端给的可读原因（原样展示，不改写） */
  officialReason: string | null;
  /** 状态与原因码映射出的用户可读说明；成功且无异常时为 null */
  userNotice: string | null;
  points: CompactPoint[];
  sources: CompactSource[];
  /** 是否为新格式结果（后端 `presentation.version === 'compact-v1'`） */
  compactPresentation: boolean;
  copyText: string;
  historyText: string;
  sourcePanelInitiallyExpanded: false;
}

export interface MarkdownMessageView {
  kind: 'markdown';
  markdown: string;
  copyText: string;
  historyText: string;
}

export type MessageView = MarkdownMessageView | RagMessageView;

/* ------------------------------------------------------------ 文案映射 */

export const REASON_CODE_NOTICE: Record<string, string> = {
  NO_MATCH: '当前范围内没有找到足够依据，回答未包含教材外推内容。',
  EVIDENCE_TEXT_EMPTY:
    '命中的教材片段在清洗后没有可引用的正文（可能只有图片），不能据此作答；可在「教材依据」中查看定位。',
  EVIDENCE_UNIT_TOO_LARGE: '有教材命中，但其内容过长无法完整引用（不会从公式或句子中间截断）。',
  SUMMARY_INVALID: '已找到教材证据，但本地概括未完成，只保留可逐条核对的教材来源。',
  SUMMARY_PARTIAL: '本地概括只保留了能完整装入预算的部分知识点，不是完整回答。',
};

const STATUS_NOTICE: Record<RagPointStatus, string | null> = {
  ok: null,
  partial: '本次定位未完整完成：请以「教材依据」中的原文为准，不要当作完整结论。',
  uncertain: '证据不确定：命中的教材片段不足以支撑稳定结论，请补充条件后重新定位。',
  no_evidence:
    '当前范围内没有找到足够依据，回答未包含教材外推内容。可补充题干条件、教材章节或具体步骤后重新定位。',
};

/** 结果 → 用户可读说明（partial 绝不说成成功；有命中却无法使用时不说「没有找到教材依据」）。 */
export function mapResultNotice(result: RagResultV2): string | null {
  const code = typeof result.reasonCode === 'string' ? result.reasonCode : null;
  if (code && REASON_CODE_NOTICE[code]) return REASON_CODE_NOTICE[code];
  return STATUS_NOTICE[result.status] ?? null;
}

/* ------------------------------------------------------------ 预览（完整句/结构边界） */

const PREVIEW_BOUNDARY = new Set(['。', '！', '？', '；', '．', '…', '!', '?', ';', '\n']);

/**
 * 生成来源短预览：在**完整句或结构边界**结束，不截半个公式。
 * 找不到合适短预览（例如首句就超过上限、或截断点落在公式/代码里）时返回 null，
 * 由 UI 只显示标题 + 「展开摘录」。
 */
export function buildSourcePreview(text: string, maxChars = SOURCE_PREVIEW_MAX_CHARS): string | null {
  const trimmed = text.trim();
  if (!trimmed) return null;
  const chars = Array.from(trimmed);
  if (chars.length <= maxChars) return trimmed;
  const protectedRanges = scanCodeAndMathRanges(chars.slice(0, maxChars + 1));
  const inProtected = (index: number) =>
    protectedRanges.some((range) => range.start <= index && index < range.end);
  for (let cut = maxChars; cut > 0; cut -= 1) {
    if (!PREVIEW_BOUNDARY.has(chars[cut - 1]!)) continue;
    if (inProtected(cut - 1) || inProtected(cut)) continue;
    const candidate = chars.slice(0, cut).join('').trim();
    if (!candidate) continue;
    // 不在半个公式处结束：保留文本里 `$` 必须成对
    if ((candidate.match(/\$/g)?.length ?? 0) % 2 === 1) continue;
    return candidate;
  }
  return null;
}

/* ------------------------------------------------------------ 来源与知识点 */

/** 证据 → 展示来源（新旧字段严格区分用途：展示用 readable，回传/校验只用坐标字段）。 */
export function buildCompactSources(evidence: TextbookEvidence[]): CompactSource[] {
  return evidence.map((item, position) => {
    const readable = item.readable;
    const legacyRaw = !readable || typeof readable.text !== 'string';
    const projection = legacyRaw ? projectReadableText(item.text) : null;
    const readableText = legacyRaw ? (projection?.text ?? item.text) : readable.text;
    return {
      index: position + 1,
      evidenceId: item.evidenceId,
      title: item.title,
      editionLabel: item.editionLabel,
      subjectLabel: item.subjectLabel,
      chapterPath: item.chapterPath,
      locator: locatorLabel(item.locator),
      isSuperseded: item.isSuperseded,
      readableText,
      legacyRaw,
      removedImageCount: legacyRaw ? (projection?.removedImageCount ?? 0) : readable.removedImageCount,
      preview: buildSourcePreview(readableText),
    };
  });
}

function codepointLength(text: string): number {
  return Array.from(text).length;
}

/**
 * 知识点 → 紧凑展示点。
 *
 * - 新结果（`compact-v1`）：后端已按 3 点 / 90 / 250 预算产出，原样展示；
 * - 旧 v2 结果：优先展示能**完整**装入预算的点，其余放进「展开旧答」；
 *   单个点都装不下时只保留标题与展开入口，**不伪造新摘要**。
 */
export function selectCompactDisplayPoints(
  points: RagResultV2['points'],
  compactPresentation: boolean,
  citationIndexes: Map<string, number>,
): CompactPoint[] {
  const selected: CompactPoint[] = [];
  let used = 0;
  for (const point of points) {
    const citations = point.evidenceIds
      .map((id) => citationIndexes.get(id))
      .filter((value): value is number => typeof value === 'number');
    if (compactPresentation) {
      selected.push({
        pointId: point.pointId,
        title: point.title,
        summary: point.summary,
        citations,
        overflowSummary: null,
      });
      continue;
    }
    const bodyLength = codepointLength(point.title) + codepointLength(point.summary);
    const fits =
      selected.length < COMPACT_MAX_POINTS &&
      bodyLength <= COMPACT_POINT_MAX_CHARS &&
      used + bodyLength <= COMPACT_TOTAL_MAX_CHARS;
    if (fits) {
      used += bodyLength;
      selected.push({
        pointId: point.pointId,
        title: point.title,
        summary: point.summary,
        citations,
        overflowSummary: null,
      });
      continue;
    }
    selected.push({
      pointId: point.pointId,
      title: point.title,
      summary: '',
      citations,
      overflowSummary: point.summary,
    });
  }
  return selected;
}

/** `[n]` 编号表：编号 = 证据在 `result.evidence` 数组中的序号（1 基，与来源面板顺序一致）。 */
export function citationIndexMap(result: RagResultV2): Map<string, number> {
  const labels = new Map<string, number>();
  result.evidence.forEach((item, position) => {
    if (!labels.has(item.evidenceId)) labels.set(item.evidenceId, position + 1);
  });
  let next = result.evidence.length + 1;
  for (const point of result.points) {
    for (const evidenceId of point.evidenceIds) {
      if (labels.has(evidenceId)) continue;
      labels.set(evidenceId, next);
      next += 1;
    }
  }
  return labels;
}

/** 默认复制 / 后续历史：简短知识点 + 紧凑出处（**不含整段教材原文**）。 */
export function renderCompactText(
  points: CompactPoint[],
  sources: CompactSource[],
  notice: string | null,
): string {
  const lines: string[] = [];
  points.forEach((point, position) => {
    const markers = point.citations.map((index) => `[${index}]`).join('');
    const body = point.summary ? `\n${point.summary}${markers}` : markers ? ` ${markers}` : '';
    lines.push(`${position + 1}. ${point.title}${body}`);
  });
  const cited = [...new Set(points.flatMap((point) => point.citations))].sort((a, b) => a - b);
  const sourceLines = cited
    .map((index) => {
      const source = sources.find((item) => item.index === index);
      if (!source) return null;
      return `[${index}] ${[source.title, source.editionLabel, source.locator].filter(Boolean).join(' · ')}`;
    })
    .filter((line): line is string => !!line);
  if (sourceLines.length) lines.push(`出处：${sourceLines.join('；')}`);
  // 状态说明（partial / no_evidence / uncertain 等）随复制与历史一起保留，避免把部分结果当完整回答
  if (notice) lines.push(notice);
  return lines.join('\n\n');
}

/** 结构化紧凑视图（显示 / 复制 / 历史共用同一份结果）。 */
export function projectCompactRag(result: RagResultV2): RagMessageView {
  const compactPresentation = result.presentation?.version === 'compact-v1';
  const citationIndexes = citationIndexMap(result);
  const sources = buildCompactSources(result.evidence);
  const userNotice = mapResultNotice(result);
  const points = selectCompactDisplayPoints(result.points, compactPresentation, citationIndexes);
  const text = renderCompactText(points, sources, userNotice ?? result.reason ?? null);
  return {
    kind: 'rag',
    status: result.status,
    reasonCode: typeof result.reasonCode === 'string' ? result.reasonCode : null,
    officialReason: result.reason ?? null,
    userNotice,
    points,
    sources,
    compactPresentation,
    copyText: text,
    historyText: text,
    sourcePanelInitiallyExpanded: false,
  };
}

/** 单一投影入口：结构化 RAG 首答走紧凑视图，其余一律保持原正文。 */
export function projectMessage(message: ChatMessage): MessageView {
  if (isRagResultV2(message.ragResult) && !message.ragExplain) return projectCompactRag(message.ragResult);
  return {
    kind: 'markdown',
    markdown: message.content,
    copyText: message.content,
    historyText: message.content,
  };
}

/* ------------------------------------------------------------ 引用标记切分 */

export interface CitationTextPart {
  kind: 'text' | 'citation';
  text: string;
  index?: number;
}

/**
 * 把知识点文本按 `[n]` 切成文本段与引用标记；**公式/代码保护区内不切**（不误伤 `$…$` 里的字面量）。
 * 仅 `allowed` 中存在的编号才作为引用；其余按原文保留为普通文本。
 */
export function splitCitationMarkers(text: string, allowed: Set<number>): CitationTextPart[] {
  const chars = Array.from(text);
  const protectedRanges = scanCodeAndMathRanges(chars);
  const inProtected = (index: number) =>
    protectedRanges.some((range) => range.start <= index && index < range.end);
  const parts: CitationTextPart[] = [];
  let cursor = 0;
  let index = 0;
  while (index < chars.length) {
    if (chars[index] !== '[' || inProtected(index)) {
      index += 1;
      continue;
    }
    const match = /^\[(\d{1,2})\]/.exec(chars.slice(index, index + 4).join(''));
    const number = match ? Number(match[1]) : Number.NaN;
    if (!match || !allowed.has(number)) {
      index += 1;
      continue;
    }
    if (index > cursor) parts.push({ kind: 'text', text: chars.slice(cursor, index).join('') });
    parts.push({ kind: 'citation', text: match[0], index: number });
    index += match[0].length;
    cursor = index;
  }
  if (cursor < chars.length) parts.push({ kind: 'text', text: chars.slice(cursor).join('') });
  return parts.length ? parts : [{ kind: 'text', text }];
}
