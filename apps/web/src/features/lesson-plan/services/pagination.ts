/**
 * 教案预览分页（R7-FE）：A4 纸、第 3 页起编号。
 *
 * 模板第 1 页 = 封面、第 2 页 = 目录，**预览只渲染内容**，所以第一张内容纸就是「第 3 页」，
 * 每张纸下缘给出红色虚线分页标记 `第 N 页结束`（与左侧栏换行设置同源的估算，不用真实测量，
 * 保证服务端渲染与测试可复现）。
 *
 * 估算口径：A4 = 210×297mm ≈ 794×1123px（96dpi）；单元格按 CJK 宽度 1em、拉丁 0.55em
 * 换行计数，乘以 `fontSize × lineHeight`，再加内边距与段落间距。
 */
import type { LessonPlanData, LessonWorkbenchModuleWire } from '@/contracts/lesson-plans';
import { processToV2 } from '../model/lesson-data';
import { fontFamilyOf, normalizeStyle, type LessonModuleEntry } from '../model/modules';
import { readKeyPoints, readObjectives } from '../model/objectives';

export const A4_WIDTH_PX = 794;
export const A4_HEIGHT_PX = 1123;
/** 内容第一页的页码（封面 1 / 目录 2 不预览）。 */
export const FIRST_CONTENT_PAGE = 3;
/** 页脚页码与页面留白预留。 */
export const PAGE_FOOTER_RESERVE_PX = 34;

export type PreviewBlockKind = 'band' | 'row' | 'process-head' | 'process-phase' | 'custom-band' | 'custom-row';

export interface PreviewBlock {
  /** 行 id：与填充字段路径一致（如 `analysis.learning`），预览据此标出「正在填充」。 */
  id: string;
  moduleId: string;
  kind: PreviewBlockKind;
  /** 字段标签或模块标题。 */
  label: string;
  /** 单元格文本：band 为 [标题]，row 为 [正文]，process 行为 [环节, 教师, 学生, 意图]。 */
  cells: string[];
  minHeight: number;
  /** 模块间距：新模块第一行之前。 */
  gapBefore: number;
  /**
   * 纵向合并单元格分组（模板「三、教学目标」的 知识/能力/思政 三行 vMerge）：
   * 连续同组行在预览里合并左侧标签列，`groupLabel` 只取组内第一行。
   */
  mergeGroup?: string;
  groupLabel?: string;
  /** 行内前缀（知识 / 能力 / 思政），显示在正文单元格里。 */
  subLabel?: string;
}

export interface PreviewPage {
  /** 真实页码：从 3 开始。 */
  number: number;
  blocks: PreviewBlock[];
}

export interface PreviewLayout {
  pages: PreviewPage[];
  blocks: PreviewBlock[];
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

const ROW_PADDING_PX = 14;
const LABEL_COLUMN_PX = 96;
const CELL_PADDING_PX = 16;

interface ModuleRows {
  id: string;
  label: string;
  rows: Array<Omit<PreviewBlock, 'moduleId' | 'gapBefore'>>;
}

function rowHeight(lines: number, fontSize: number, lineHeight: number, minHeight: number, paragraphs: number, paragraphGap: number): number {
  const textHeight = lines * fontSize * lineHeight + Math.max(0, paragraphs - 1) * paragraphGap;
  return Math.max(minHeight, textHeight + ROW_PADDING_PX);
}

function textRow(
  id: string,
  label: string,
  text: string,
  style: ReturnType<typeof normalizeStyle>,
  options: { minHeight?: number; contentWidth: number },
): Omit<PreviewBlock, 'moduleId' | 'gapBefore'> {
  const lines = countLines(text, options.contentWidth - CELL_PADDING_PX, style.baseSize);
  const paragraphs = text ? text.split(/\r?\n/).length : 1;
  return {
    id,
    kind: 'row',
    label,
    cells: [text],
    minHeight: rowHeight(
      Math.max(lines, 1),
      style.baseSize,
      style.lineHeight,
      options.minHeight ?? 34,
      paragraphs,
      style.paragraphGap,
    ),
  };
}

function bandRow(
  id: string,
  label: string,
  style: ReturnType<typeof normalizeStyle>,
): Omit<PreviewBlock, 'moduleId' | 'gapBefore'> {
  return {
    id,
    kind: 'band',
    label,
    cells: [label],
    minHeight: Math.round(style.headingSize * style.lineHeight + 22),
  };
}

/** 依据模块布局与正文生成预览行（隐藏模块与固定模块的规则都在这里）。 */
export function buildModuleRows(
  data: LessonPlanData,
  modules: Array<LessonModuleEntry | LessonWorkbenchModuleWire>,
  rawStyle: unknown,
): ModuleRows[] {
  const style = normalizeStyle(rawStyle);
  const contentWidth = A4_WIDTH_PX - style.pageMargin * 2 - LABEL_COLUMN_PX;
  const result: ModuleRows[] = [];
  const basic = data.basic ?? null;
  const analysis = data.analysis ?? null;
  const strategy = data.strategy ?? null;
  const evaluation = data.evaluation ?? null;

  let visibleBuiltinIndex = 0;
  for (const entry of modules) {
    if (entry.hidden) continue;
    const id = String(entry.id);
    if (entry.kind === 'custom') {
      const body = entry.body ?? '';
      result.push({
        id,
        label: entry.label,
        rows: [
          { ...bandRow(`${id}.band`, entry.label, style), kind: 'custom-band' },
          textRow(`${id}.body`, entry.label, body, style, { contentWidth, minHeight: 60 }),
        ],
      });
      continue;
    }
    const builtinId = entry.builtinId || id;
    const no = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十'][visibleBuiltinIndex] ?? '一';
    visibleBuiltinIndex += 1;
    switch (builtinId) {
      case 'basic':
        result.push({
          id,
          label: `${no}、基本信息`,
          rows: [
            textRow('basic.courseName', '课程名称', basic?.courseName ?? data.title, style, { contentWidth }),
            textRow('basic.audience', '授课对象', basic?.audience ?? '', style, { contentWidth }),
            textRow('basic.teachingTime', '授课时间', basic?.teachingTime ?? '', style, { contentWidth }),
            textRow('basic.location', '授课地点', basic?.location ?? '', style, { contentWidth }),
            textRow('basic.chapter', '教学章节', basic?.chapter ?? '', style, { contentWidth }),
          ],
        });
        break;
      case 'analysis':
        result.push({
          id,
          label: `${no}、教学分析`,
          rows: [
            textRow('analysis.learning', '学情分析', analysis?.learning ?? '', style, { contentWidth }),
            textRow('analysis.textbook', '教材分析', analysis?.textbook ?? '', style, { contentWidth }),
            textRow('analysis.content', '教学内容', analysis?.content ?? '', style, { contentWidth }),
            textRow('analysis.ideological', '思政资源', analysis?.ideological ?? '', style, { contentWidth }),
          ],
        });
        break;
      case 'objectives': {
        const objectives = readObjectives(data.coreCompetencies);
        const keyPoints = readKeyPoints(data.keyPoints);
        const merged: { mergeGroup: string; groupLabel: string } = { mergeGroup: 'objectives', groupLabel: '教学目标' };
        const rows: Array<Omit<PreviewBlock, 'moduleId' | 'gapBefore'>> = [
          { ...textRow('objectives.knowledge', '知识', objectives.rows.knowledge, style, { contentWidth }), ...merged, subLabel: '知识' },
          { ...textRow('objectives.ability', '能力', objectives.rows.ability, style, { contentWidth }), ...merged, subLabel: '能力' },
          { ...textRow('objectives.ideological', '思政', objectives.rows.ideological, style, { contentWidth }), ...merged, subLabel: '思政' },
        ];
        // 教学重点/难点只在已有内容时出现（新教案的表结构与用户模板逐行一致）。
        if (keyPoints.key || keyPoints.difficulty || keyPoints.other.length > 0) {
          rows.push({
            ...textRow('objectives.keyPoints', '教学重点、难点', data.keyPoints, style, { contentWidth }),
            mergeGroup: 'objectives-key',
            groupLabel: '教学重点、难点',
          });
        }
        result.push({ id, label: `${no}、教学目标`, rows });
        break;
      }
      case 'strategy': {
        const rows = [
          textRow('strategy.designThinking', '设计思路', strategy?.designThinking ?? '', style, { contentWidth }),
          textRow('strategy.teachingFlow', '教学流程', strategy?.teachingFlow ?? '', style, { contentWidth }),
          textRow('strategy.methods', '教学手段', strategy?.methods ?? '', style, { contentWidth }),
        ];
        // 教学设计（板书/思路）仅在已有内容时出现：新教案的表格与用户模板逐行一致。
        if (data.teachingDesign.trim()) {
          rows.push(textRow('strategy.teachingDesign', '教学设计', data.teachingDesign, style, { contentWidth }));
        }
        result.push({ id, label: `${no}、教学策略`, rows });
        break;
      }
      case 'process': {
        const rows = processToV2(data);
        const blocks: Array<Omit<PreviewBlock, 'moduleId' | 'gapBefore'>> = [
          { id: 'process.head', kind: 'process-head', label: '教学环节', cells: ['教学环节', '教师活动', '学生活动', '设计意图'], minHeight: 36 },
        ];
        let lastPhase = '';
        const cellWidth = Math.max(60, (contentWidth - CELL_PADDING_PX) / 3);
        if (rows.length === 0) {
          blocks.push({
            id: 'process.empty',
            kind: 'row',
            label: '—',
            cells: ['（暂无教学环节：可在中栏「教学过程」添加）'],
            minHeight: 40,
          });
        }
        for (const row of rows) {
          const phaseLabel = row.phaseLabel || '';
          const phaseKey = `${row.phase}:${phaseLabel}`;
          if (phaseLabel && phaseKey !== lastPhase) {
            blocks.push({
              id: `process.phase.${phaseKey}`,
              kind: 'process-phase',
              label: phaseLabel,
              cells: [phaseLabel],
              minHeight: Math.round(style.headingSize * style.lineHeight + 16),
            });
            lastPhase = phaseKey;
          }
          const lines = Math.max(
            countLines(row.title, cellWidth, style.baseSize),
            countLines(row.teacherActivity, cellWidth, style.baseSize),
            countLines(row.studentActivity, cellWidth, style.baseSize),
            countLines(row.intent, cellWidth, style.baseSize),
            1,
          );
          blocks.push({
            id: `process.${row.id}`,
            kind: 'row',
            label: row.title || '环节',
            cells: [row.title, row.teacherActivity, row.studentActivity, row.intent],
            minHeight: Math.max(
              52,
              lines * style.baseSize * style.lineHeight + ROW_PADDING_PX,
            ),
          });
        }
        result.push({ id, label: `${no}、教学过程`, rows: blocks });
        break;
      }
      case 'evaluation': {
        const rows = [];
        if (data.exercises.trim()) {
          rows.push(textRow('evaluation.exercises', '练习与作业', data.exercises, style, { contentWidth }));
        }
        rows.push(textRow('evaluation.afterClassTest', '课后测试情况', evaluation?.afterClassTest ?? '', style, { contentWidth }));
        rows.push(textRow('evaluation.homework', '作业情况', evaluation?.homework ?? '', style, { contentWidth }));
        result.push({ id, label: `${no}、评价反馈`, rows });
        break;
      }
      case 'reflection':
        result.push({
          id,
          label: `${no}、教学反思`,
          rows: [textRow('reflection', '教学反思', data.reflection, style, { contentWidth })],
        });
        break;
      default:
        break;
    }
  }
  return result;
}

/** 展平为分页用的行块（模块标题作为 band 行参与流式分页）。 */
export function buildPreviewBlocks(
  data: LessonPlanData,
  modules: Array<LessonModuleEntry | LessonWorkbenchModuleWire>,
  rawStyle: unknown,
): PreviewBlock[] {
  const style = normalizeStyle(rawStyle);
  const blocks: PreviewBlock[] = [];
  const grouped = buildModuleRows(data, modules, style);
  grouped.forEach((moduleRows, index) => {
    const gapBefore = index === 0 ? 0 : style.moduleGap;
    const hasOwnBand = moduleRows.rows[0]?.kind === 'custom-band';
    if (!hasOwnBand) {
      blocks.push({
        id: `${moduleRows.id}.band`,
        moduleId: moduleRows.id,
        kind: 'band',
        label: moduleRows.label,
        cells: [moduleRows.label],
        minHeight: Math.round(style.headingSize * style.lineHeight + 22),
        gapBefore,
      });
    }
    moduleRows.rows.forEach((row, rowIndex) => {
      blocks.push({
        ...row,
        moduleId: moduleRows.id,
        gapBefore: rowIndex === 0 && hasOwnBand ? gapBefore : 0,
      });
    });
  });
  return blocks;
}

/** 按内容流分页；页码从 3 开始。 */
export function paginateBlocks(blocks: PreviewBlock[], rawStyle: unknown): PreviewPage[] {
  const style = normalizeStyle(rawStyle);
  const capacity = A4_HEIGHT_PX - style.pageMargin * 2 - PAGE_FOOTER_RESERVE_PX;
  const pages: PreviewPage[] = [];
  let current: PreviewBlock[] = [];
  let remaining = capacity;
  const flush = () => {
    if (current.length > 0) {
      pages.push({ number: FIRST_CONTENT_PAGE + pages.length, blocks: current });
      current = [];
      remaining = capacity;
    }
  };
  blocks.forEach((block, index) => {
    const needed = block.minHeight + block.gapBefore;
    if (needed > remaining && current.length > 0) flush();
    current.push(block);
    remaining -= needed;
    // 孤行控制：模块标题（band）不能落在页尾——标题之后若放不下下一行，标题整块移到下一页。
    const isBand = block.kind === 'band' || block.kind === 'custom-band';
    const next = blocks[index + 1];
    if (isBand && next && next.minHeight + next.gapBefore > remaining && current.length > 1) {
      current.pop();
      flush();
      current.push(block);
      remaining = capacity - needed;
    }
  });
  flush();
  if (pages.length === 0) pages.push({ number: FIRST_CONTENT_PAGE, blocks: [] });
  return pages;
}

export function layoutPreview(
  data: LessonPlanData,
  modules: Array<LessonModuleEntry | LessonWorkbenchModuleWire>,
  style: unknown,
): PreviewLayout {
  const blocks = buildPreviewBlocks(data, modules, style);
  return { blocks, pages: paginateBlocks(blocks, style) };
}

/** 页尾红色虚线标记文案。 */
export function pageEndLabel(pageNumber: number): string {
  return `第 ${pageNumber} 页结束`;
}

/** 纸张样式（预览与打印共用同一份字号/行高/字体）。 */
export function paperStyleVars(rawStyle: unknown): Record<string, string> {
  const style = normalizeStyle(rawStyle);
  return {
    '--lp-font': fontFamilyOf(style.fontId),
    '--lp-base': `${style.baseSize}px`,
    '--lp-heading': `${style.headingSize}px`,
    '--lp-label': `${style.labelSize}px`,
    '--lp-line': String(style.lineHeight),
    '--lp-page-margin': `${style.pageMargin}px`,
    '--lp-module-gap': `${style.moduleGap}px`,
    '--lp-paragraph-gap': `${style.paragraphGap}px`,
  };
}
