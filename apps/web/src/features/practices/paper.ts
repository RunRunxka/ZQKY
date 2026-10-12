/**
 * 练习卷 A4 分页预览模型（R8-FE 2026-10-12）。
 *
 * 与教案工作台预览同一风格与同一估算口径（`features/lesson-plan/services/pagination`）：
 * A4 = 210×297mm ≈ 794×1123px（96dpi），按内容流分页，**题不劈页**（一道题整块放进下
 * 一页而不是拆开）；每张纸下缘是红色虚线分页标记「第 N 页结束」。
 *
 * 卷面差异（用户口径）：
 * - 学生卷：卷头 + 题号 + 题干（富内容）+ 作答区留白（不显示答案与解析）；
 * - 教师卷：在其上追加每题「答案 / 解析」与末尾「答案页」。
 *
 * 估算只用于预览分页（与真实 docx 导出由后端组装），不用真实测量，保证 SSR 与测试可复现。
 * 作答区高度是启发式：选项块存在按客观题给一条作答线，否则按主观题给留白——
 * 练习视图不携带题型字段，这里不猜造题型文案，只决定留白大小。
 */

import type { FixedKnowledge, PracticeItemView } from '@/contracts/b4';
import type { ContentBlock, RichContentV2 } from '@/contracts/question-bank';

export const A4_WIDTH_PX = 794;
export const A4_HEIGHT_PX = 1123;
export const PAGE_FOOTER_RESERVE_PX = 40;
/** 纸张内边距（预览与打印共用同一份值）。 */
export const PAPER_PADDING_PX = 56;
/** 卷头（标题 + 姓名/班级作答线 + 说明）高度。 */
export const HEADER_HEIGHT_PX = 132;

export type PaperVariant = 'student' | 'teacher';

export interface PaperItem {
  itemId: string;
  /** 固定题身份：受管图片资源只按它读取（不拼 URL）。 */
  questionId: string;
  questionNo: string;
  ordinal: number;
  isScored: boolean;
  maxScoreUnits: number | null;
  content: RichContentV2;
  answerState: string;
  knowledgePoints: FixedKnowledge[];
}

export interface PaperSegment {
  id: string;
  kind: 'header' | 'question' | 'answer-sheet';
  /** question / answer-sheet 的题目引用。 */
  itemIds: string[];
  /** 预留高度（估算）。 */
  height: number;
  gapBefore: number;
}

export interface PaperPage {
  number: number;
  segments: PaperSegment[];
}

export interface PaperLayout {
  variant: PaperVariant;
  items: PaperItem[];
  pages: PaperPage[];
}

function charWidth(char: string, fontSize: number): number {
  return /[\u0000-\u00ff]/.test(char) ? fontSize * 0.55 : fontSize;
}

/** 文本在给定宽度内的行数（CJK 全宽、拉丁半宽；保留显式换行）。 */
export function countLines(text: string, widthPx: number, fontSize: number): number {
  if (!text) return 0;
  let lines = 0;
  for (const paragraph of text.split(/\r?\n/)) {
    if (paragraph === '') {
      lines += 1;
      continue;
    }
    let width = 0;
    let count = 1;
    for (const char of paragraph) {
      const w = charWidth(char, fontSize);
      if (width + w > widthPx && width > 0) {
        count += 1;
        width = 0;
      }
      width += w;
    }
    lines += count;
  }
  return lines;
}

const BASE_FONT_PX = 15;
const LINE_HEIGHT = 1.7;
const BLOCK_GAP_PX = 10;
const QUESTION_GAP_PX = 22;
const OPTION_ROW_PX = 26;
/** 客观题作答线 / 主观题作答留白（启发式，见文件头说明）。 */
const ANSWER_LINE_PX = 34;
const ANSWER_AREA_PX = 150;

function blockLines(block: ContentBlock, width: number): number {
  switch (block.kind) {
    case 'paragraph':
      return Math.max(1, countLines(block.text, width, BASE_FONT_PX));
    case 'formula':
      return block.latex ? 1 + Math.ceil(block.latex.length / 60) : 1;
    case 'image':
      return 4;
    case 'table': {
      const columns = Math.max(1, block.columnCount ?? 2);
      const rows = Math.ceil(block.cells.length / columns);
      return Math.max(1, rows) * 1.4;
    }
  }
}

function blocksHeight(blocks: ContentBlock[], width: number): number {
  return blocks.reduce((sum, block) => sum + blockLines(block, width) * BASE_FONT_PX * LINE_HEIGHT + BLOCK_GAP_PX, 0);
}

function answerSpaceHeight(content: RichContentV2): number {
  const hasOptions = Object.keys(content.optionBlocks).length > 0;
  return hasOptions ? ANSWER_LINE_PX : ANSWER_AREA_PX;
}

/** 单题的预留高度（含题号行、题干、选项、作答区；教师卷再含答案与解析）。 */
export function questionHeight(content: RichContentV2, variant: PaperVariant): number {
  const width = A4_WIDTH_PX - PAPER_PADDING_PX * 2;
  let height = 24; // 题号 + 分值行
  height += blocksHeight(content.sharedMaterials.flatMap((material) => material.blocks), width);
  height += blocksHeight(content.stemBlocks, width);
  const optionCount = Object.keys(content.optionBlocks).length;
  if (optionCount > 0) height += optionCount * OPTION_ROW_PX + BLOCK_GAP_PX;
  height += variant === 'student' ? answerSpaceHeight(content) : 0;
  if (variant === 'teacher') {
    height += blocksHeight(content.answerBlocks.length ? content.answerBlocks : [], width);
    height += blocksHeight(content.explanationBlocks, width);
    if (content.answerBlocks.length === 0) height += BASE_FONT_PX * LINE_HEIGHT + BLOCK_GAP_PX;
    if (content.explanationBlocks.length === 0) height += BASE_FONT_PX * LINE_HEIGHT + BLOCK_GAP_PX;
  }
  return Math.round(height + QUESTION_GAP_PX);
}

/** 答案页高度（题号 + 一行答案摘要）。 */
function answerSheetHeight(items: PaperItem[]): number {
  return 40 + items.length * (BASE_FONT_PX * LINE_HEIGHT + 8) + 30;
}

export function toPaperItems(items: PracticeItemView[]): PaperItem[] {
  return [...items]
    .sort((a, b) => a.ordinal - b.ordinal)
    .map((item) => ({
      itemId: item.practiceItemId,
      questionId: item.questionId,
      questionNo: item.questionNo,
      ordinal: item.ordinal,
      isScored: item.isScored,
      maxScoreUnits: item.maxScoreUnits,
      content: item.content,
      answerState: item.answerState,
      knowledgePoints: item.knowledgePoints,
    }));
}

/**
 * 按内容流分页：题目不劈页（放不下且当前页已有内容时整题移到下一页）；
 * 教师卷的答案页从新的一页开始。
 */
export function paginatePaper(items: PaperItem[], variant: PaperVariant): PaperSegment[] {
  const capacity = A4_HEIGHT_PX - PAPER_PADDING_PX * 2 - PAGE_FOOTER_RESERVE_PX;
  const pages: PaperSegment[][] = [];
  let current: PaperSegment[] = [];
  let remaining = capacity;
  const flush = () => {
    if (current.length > 0) pages.push(current);
    current = [];
    remaining = capacity;
  };
  const push = (segment: PaperSegment) => {
    if (segment.height + segment.gapBefore > remaining && current.length > 0) flush();
    current.push(segment);
    remaining -= segment.height + segment.gapBefore;
  };
  push({ id: 'paper-header', kind: 'header', itemIds: [], height: HEADER_HEIGHT_PX, gapBefore: 0 });
  items.forEach((item) => {
    push({
      id: `question-${item.itemId}`,
      kind: 'question',
      itemIds: [item.itemId],
      height: questionHeight(item.content, variant),
      gapBefore: 0,
    });
  });
  if (variant === 'teacher') {
    push({
      id: 'answer-sheet',
      kind: 'answer-sheet',
      itemIds: items.map((item) => item.itemId),
      height: answerSheetHeight(items),
      gapBefore: 0,
    });
  }
  flush();
  const pagesOut: PaperPage[] = (pages.length > 0 ? pages : [[]]).map((segments, index) => ({
    number: index + 1,
    segments,
  }));
  return pagesOut.flatMap((page) => page.segments.map((segment) => ({ ...segment, id: `p${page.number}-${segment.id}` })));
}

/** 生成整份卷面布局（页码从 1 起）。 */
export function layoutPaper(items: PracticeItemView[], variant: PaperVariant): PaperLayout {
  const paperItems = toPaperItems(items);
  const segments = paginatePaper(paperItems, variant);
  const capacity = A4_HEIGHT_PX - PAPER_PADDING_PX * 2 - PAGE_FOOTER_RESERVE_PX;
  const pages: PaperPage[] = [];
  let current: PaperSegment[] = [];
  let used = 0;
  const flush = () => {
    if (current.length > 0) pages.push({ number: pages.length + 1, segments: current });
    current = [];
    used = 0;
  };
  segments.forEach((segment) => {
    const needed = segment.height + segment.gapBefore;
    if (needed > capacity - used && current.length > 0) flush();
    current.push(segment);
    used += needed;
  });
  flush();
  if (pages.length === 0) pages.push({ number: 1, segments: [] });
  return { variant, items: paperItems, pages };
}

/** 页尾红色虚线标记文案（与教案工作台同款）。 */
export function pageEndLabel(pageNumber: number): string {
  return `第 ${pageNumber} 页结束`;
}
