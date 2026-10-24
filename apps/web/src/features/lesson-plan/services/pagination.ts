/**
 * 教案预览分页（R12）：A4 纸、正文从第 3 页起、逐表还原 Word 模板。
 *
 * 模板（app/resources/lesson_templates/lesson-plan-blank.docx）正文四张表：
 *
 * - 表 1 一、基本信息：4 列（课程名称/授课对象、授课时间/授课地点、教学章节跨 3 列）；
 * - 表 2 二、教学分析：2 列 4 行；
 * - 表 3 三、教学目标 + 四、教学策略同表：知识/能力/思政三行 vMerge、重点/难点两行、
 *   策略三行跨 2 列；
 * - 表 4 五、教学过程 + 六、评价反馈 + 七、教学反思同表：两行表头（教学环节 vMerge、
 *   教学活动跨 2 列、设计意图 vMerge；教师/学生活动）、阶段跨列行、内容行；
 *   评价反馈与教学反思各是一格跨 4 列的子项段落。
 *
 * 封面（第 1 页）与目录（第 2 页）仍由导出时生成，预览只从第 3 页起排正文；每张纸下缘
 * 给出红色虚线分页标记「第 N 页结束」。行高按 CJK 全宽 / 拉丁半宽估算，保证服务端渲染与
 * 测试可复现；不依赖真实 DOM 测量。
 */
import type { LessonPlanData, LessonWorkbenchModuleWire } from '@/contracts/lesson-plans';
import { PHASE_LABELS, processToV2 } from '../model/lesson-data';
import { fontFamilyOf, normalizeStyle, type LessonModuleEntry } from '../model/modules';
import { readKeyPoints, readObjectives } from '../model/objectives';

export const A4_WIDTH_PX = 794;
export const A4_HEIGHT_PX = 1123;
/** 内容第一页的页码（封面 1 / 目录 2 不预览）。 */
export const FIRST_CONTENT_PAGE = 3;
/** 页脚页码与页面留白预留。 */
export const PAGE_FOOTER_RESERVE_PX = 34;

/** 模板表列宽（twips，来自 lesson-plan-blank.docx 的 tblGrid）。 */
const TABLE_COLUMNS: Record<string, readonly number[]> = {
  basic: [1360, 4195, 1474, 2721],
  analysis: [1247, 8505],
  objectives: [1474, 1701, 6577],
  process: [1360, 3402, 2948, 2041],
  evaluation: [1360, 3402, 2948, 2041],
};
/** 自定义模块克隆「二、教学分析」表：2 列。 */
const CUSTOM_COLUMNS: readonly number[] = [1247, 8505];

export function tableColumns(tableId: string): number[] {
  return [...(TABLE_COLUMNS[tableId] ?? CUSTOM_COLUMNS)];
}

/** 列宽百分比（渲染 `<colgroup>` 用）。 */
export function tableColumnPercentages(tableId: string): number[] {
  const columns = tableColumns(tableId);
  const total = columns.reduce((sum, value) => sum + value, 0) || 1;
  return columns.map((value) => (value / total) * 100);
}

export type PreviewBlockKind = 'band' | 'row' | 'process-head' | 'process-phase' | 'custom-band';

export interface PreviewCell {
  text: string;
  role?: 'label' | 'value' | 'header' | 'phase';
  colspan?: number;
  rowspan?: number;
  subLabel?: string;
  /** 候选标记命中的字段 id（一个单元格可承接多个字段）。 */
  candidateIds?: string[];
}

/** 跨列表格里的子项段（评价反馈四项 / 教学反思三项）：视觉上是一格，语义上可逐项标记。 */
export interface PreviewBlock {
  /** 行 id：与填充字段路径一致（如 `analysis.learning`），预览据此标出「AI 候选」。 */
  id: string;
  moduleId: string;
  /** 所属模板表：basic/analysis/objectives/process/evaluation 或自定义模块 id。 */
  tableId: string;
  columns: number;
  kind: PreviewBlockKind;
  /** 字段标签或模块标题。 */
  label: string;
  /** 普通行的单元格；band 为 [标题]。 */
  cells: PreviewCell[];
  minHeight: number;
  /** 估算高度（分页用）。 */
  height: number;
  /** 模块间距：新模块第一行之前。 */
  gapBefore: number;
  /**
   * 纵向合并单元格分组（模板「三、教学目标」的知识/能力/思政三行 vMerge）：
   * 连续同组行在预览里合并左侧标签列，分页时整组不拆页。
   */
  mergeGroup?: string;
  groupLabel?: string;
  /** 行内前缀（知识 / 能力 / 思政）。 */
  subLabel?: string;
  /** 表格标题 / 表头：与下一块同页。 */
  keepWithNext?: boolean;
  /** 可跨页拆分的长行（普通表格行；band/表头/阶段/vMerge 组不可拆）。 */
  splittable?: boolean;
  /** 评价/反思的跨列子项行（视觉上无行间边框）。 */
  subRow?: boolean;
  /** 子项行的非首行：不画上边框，保持「一格多段」的外观。 */
  noTopBorder?: boolean;
  /** 由上一页拆分出来的续行：标签列留空，空单元格不显示「待填写」。 */
  continuation?: boolean;
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

/**
 * 把文本按视觉行宽切成行（CJK 全宽、拉丁半宽；保留显式换行）。
 * 供跨页拆分使用：head/tail 用 `\n` 连接后仍是同一段文字，渲染层按行显示。
 */
export function wrapTextLines(text: string, widthPx: number, fontSize: number): string[] {
  const source = text ?? '';
  if (!source) return [''];
  const lines: string[] = [];
  for (const paragraph of source.split(/\r?\n/)) {
    if (paragraph === '') {
      lines.push('');
      continue;
    }
    let current = '';
    let used = 0;
    for (const char of paragraph) {
      const width = charWidth(char, fontSize);
      if (used + width > widthPx && used > 0) {
        lines.push(current);
        current = '';
        used = 0;
      }
      current += char;
      used += width;
    }
    lines.push(current);
  }
  return lines;
}

/** 单元格内边距（上下 / 左右）与表格最小行高。 */
const CELL_PAD_Y = 12;
const CELL_PAD_X = 14;
const BAND_EXTRA = 12;
const PHASE_EXTRA = 8;
/** 跨页拆分时至少留在本页的行数（也用于判断标题能否与下一行同页）。 */
export const MIN_SPLIT_LINES = 3;

function paragraphCount(text: string): number {
  return text ? text.split(/\r?\n/).length : 1;
}

function cellContentHeight(
  text: string,
  widthPx: number,
  fontSize: number,
  lineHeight: number,
  paragraphGap: number,
): number {
  const lines = Math.max(1, countLines(text, Math.max(24, widthPx), fontSize));
  return lines * fontSize * lineHeight + (paragraphCount(text) - 1) * paragraphGap + CELL_PAD_Y;
}

function cellWidth(columns: readonly number[], start: number, span: number, contentWidth: number): number {
  const total = columns.reduce((sum, value) => sum + value, 0) || 1;
  const weight = columns.slice(start, start + span).reduce((sum, value) => sum + value, 0);
  return (weight / total) * contentWidth - CELL_PAD_X;
}

/** 一行的高度：按每个单元格的换行数取最大值。 */
function measureCells(
  cells: PreviewCell[],
  columns: readonly number[],
  contentWidth: number,
  style: ReturnType<typeof normalizeStyle>,
  minHeight: number,
): number {
  let cursor = 0;
  let height = minHeight;
  for (const cell of cells) {
    const span = cell.colspan ?? 1;
    const fontSize = cell.role === 'label' || cell.role === 'header' || cell.role === 'phase' ? style.labelSize : style.baseSize;
    height = Math.max(
      height,
      cellContentHeight(
        cell.text,
        cellWidth(columns, cursor, span, contentWidth),
        fontSize,
        style.lineHeight,
        style.paragraphGap,
      ),
    );
    cursor += span;
  }
  return Math.round(height);
}

/* ------------------------------------------------------------------ 行构造 */

type PreviewRowSeed = Omit<PreviewBlock, 'moduleId' | 'gapBefore'>;

interface ModuleRows {
  id: string;
  label: string;
  rows: PreviewRowSeed[];
}

function tableRow(
  id: string,
  tableId: string,
  cells: PreviewCell[],
  style: ReturnType<typeof normalizeStyle>,
  options: { minHeight?: number; splittable?: boolean; subRow?: boolean; noTopBorder?: boolean } = {},
): PreviewRowSeed {
  const columns = tableColumns(tableId);
  const contentWidth = A4_WIDTH_PX - style.pageMargin * 2;
  const minHeight = options.minHeight ?? 0;
  return {
    id,
    tableId,
    columns: columns.length,
    kind: 'row',
    label: cells.find((cell) => cell.role === 'label')?.text ?? '',
    cells,
    minHeight,
    height: measureCells(cells, columns, contentWidth, style, minHeight),
    splittable: options.splittable ?? true,
    ...(options.subRow ? { subRow: true } : {}),
    ...(options.noTopBorder ? { noTopBorder: true } : {}),
  };
}

function bandRow(
  id: string,
  tableId: string,
  label: string,
  style: ReturnType<typeof normalizeStyle>,
  kind: 'band' | 'custom-band' = 'band',
): PreviewRowSeed {
  const columns = tableColumns(tableId);
  const height = Math.round(style.headingSize * style.lineHeight + BAND_EXTRA);
  return {
    id,
    tableId,
    columns: columns.length,
    kind,
    label,
    cells: [{ text: label, role: 'header', colspan: columns.length }],
    minHeight: height,
    height,
    keepWithNext: true,
  };
}

function textCell(
  text: string,
  candidateIds?: string[],
  options: { colspan?: number; role?: PreviewCell['role'] } = {},
): PreviewCell {
  return {
    text,
    role: options.role ?? 'value',
    ...(options.colspan ? { colspan: options.colspan } : {}),
    ...(candidateIds ? { candidateIds } : {}),
  };
}

function labelCell(text: string, options: { colspan?: number; rowspan?: number } = {}): PreviewCell {
  return {
    text,
    role: 'label',
    ...(options.colspan ? { colspan: options.colspan } : {}),
    ...(options.rowspan ? { rowspan: options.rowspan } : {}),
  };
}

/** 教学目标三行的 vMerge 组：首行带跨行标签，其余行只有「子标签 + 正文」。 */
function objectivesGroup(data: LessonPlanData, style: ReturnType<typeof normalizeStyle>): PreviewRowSeed[] {
  const objectives = readObjectives(data.coreCompetencies);
  const tableId = 'objectives';
  const rows: PreviewRowSeed[] = [
    tableRow(
      'objectives.knowledge',
      tableId,
      [
        labelCell('教学目标', { rowspan: 3 }),
        labelCell('知识目标'),
        textCell(objectives.rows.knowledge, ['objectives.knowledge']),
      ],
      style,
    ),
    tableRow(
      'objectives.ability',
      tableId,
      [labelCell('能力目标'), textCell(objectives.rows.ability, ['objectives.ability'])],
      style,
    ),
    tableRow(
      'objectives.ideological',
      tableId,
      [labelCell('思政目标'), textCell(objectives.rows.ideological, ['objectives.ideological'])],
      style,
    ),
  ];
  for (const row of rows) {
    row.mergeGroup = 'objectives';
    row.groupLabel = '教学目标';
    row.subLabel = row.cells[row.cells.length - 2]?.text;
    row.splittable = false;
  }
  return rows;
}

/** 教学反思：按模板三个小标题拆分；无标题文本整体进（一）。 */
export function splitReflection(text: string): { achievement: string; features: string; postscript: string } {
  const value = text ?? '';
  const markers = [
    { key: 'achievement' as const, pattern: /^\s*(?:[（(]\s*[一二三]\s*[）)]|[一二三]\s*[、.．])\s*目标达成度/ },
    { key: 'features' as const, pattern: /^\s*(?:[（(]\s*[一二三]\s*[）)]|[一二三]\s*[、.．])\s*教学特色/ },
    { key: 'postscript' as const, pattern: /^\s*(?:[（(]\s*[一二三]\s*[）)]|[一二三]\s*[、.．])\s*教学后记/ },
  ];
  const buckets: Record<'achievement' | 'features' | 'postscript', string[]> = {
    achievement: [],
    features: [],
    postscript: [],
  };
  let current: keyof typeof buckets = 'achievement';
  for (const line of value.split(/\r?\n/)) {
    const hit = markers.find((marker) => marker.pattern.test(line));
    if (hit) {
      current = hit.key;
      continue;
    }
    buckets[current].push(line);
  }
  const join = (lines: string[]) => lines.join('\n').trim();
  return {
    achievement: join(buckets.achievement),
    features: join(buckets.features),
    postscript: join(buckets.postscript),
  };
}

/** 六、评价反馈：模板四项小标题（（三）（四）没有数据，保留标题与空行）。 */
function evaluationRows(data: LessonPlanData, style: ReturnType<typeof normalizeStyle>): PreviewRowSeed[] {
  const evaluation = data.evaluation ?? null;
  const homework = (evaluation?.homework ?? '').trim();
  const exercises = (data.exercises ?? '').trim();
  const homeworkText =
    homework && exercises && homework !== exercises ? `${homework}\n${exercises}` : homework || exercises;

  const parts: Array<{ id: string; heading: string; text: string; candidateIds?: string[] }> = [
    {
      id: 'evaluation.afterClassTest',
      heading: '（一）学生课后测试情况',
      text: (evaluation?.afterClassTest ?? '').trim(),
      candidateIds: ['evaluation.afterClassTest'],
    },
    {
      id: 'evaluation.homework',
      heading: '（二）学生课后作业情况',
      text: homeworkText,
      candidateIds: ['evaluation.homework', 'evaluation.exercises', 'exercises'],
    },
    { id: 'evaluation.afterClassSurvey', heading: '（三）学生课后调查反馈', text: '' },
    { id: 'evaluation.supervisorFeedback', heading: '（四）督导专家课后反馈', text: '' },
  ];
  return parts.map((part, index) =>
    tableRow(
      part.id,
      'evaluation',
      [
        {
          text: part.text ? `${part.heading}\n${part.text}` : part.heading,
          role: 'value',
          colspan: 4,
          ...(part.candidateIds ? { candidateIds: part.candidateIds } : {}),
        },
      ],
      style,
      { subRow: true, noTopBorder: index > 0 },
    ),
  );
}

/** 七、教学反思：模板三项小标题；文本带标题按标题拆，否则整体进（一）。 */
function reflectionRows(data: LessonPlanData, style: ReturnType<typeof normalizeStyle>): PreviewRowSeed[] {
  const parts = splitReflection(data.reflection);
  const rows: Array<{ id: string; heading: string; text: string; candidateIds?: string[] }> = [
    { id: 'reflection', heading: '（一）目标达成度分析', text: parts.achievement, candidateIds: ['reflection'] },
    { id: 'reflection.features', heading: '（二）教学特色与可供借鉴之处', text: parts.features },
    { id: 'reflection.postscript', heading: '（三）教学后记', text: parts.postscript },
  ];
  return rows.map((part, index) =>
    tableRow(
      part.id,
      'evaluation',
      [
        {
          text: part.text ? `${part.heading}\n${part.text}` : part.heading,
          role: 'value',
          colspan: 4,
          ...(part.candidateIds ? { candidateIds: part.candidateIds } : {}),
        },
      ],
      style,
      { subRow: true, noTopBorder: index > 0 },
    ),
  );
}

/** 依据模块布局与正文生成预览行（隐藏模块与固定模块的规则都在这里）。 */
export function buildModuleRows(
  data: LessonPlanData,
  modules: Array<LessonModuleEntry | LessonWorkbenchModuleWire>,
  rawStyle: unknown,
): ModuleRows[] {
  const style = normalizeStyle(rawStyle);
  const result: ModuleRows[] = [];
  const basic = data.basic ?? null;
  const analysis = data.analysis ?? null;
  const strategy = data.strategy ?? null;

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
          bandRow(`${id}.band`, id, entry.label, style, 'custom-band'),
          tableRow(`${id}.body`, id, [{ text: body, role: 'value', colspan: 2 }], style),
        ],
      });
      continue;
    }
    const builtinId = entry.builtinId || id;
    const no = ['一', '二', '三', '四', '五', '六', '七', '八', '九', '十'][visibleBuiltinIndex] ?? '一';
    visibleBuiltinIndex += 1;
    switch (builtinId) {
      case 'basic': {
        result.push({
          id,
          label: `${no}、基本信息`,
          rows: [
            bandRow(`${id}.band`, 'basic', `${no}、基本信息`, style),
            tableRow(
              'basic.courseName',
              'basic',
              [
                labelCell('课程名称'),
                textCell(basic?.courseName || data.title, ['basic.courseName']),
                labelCell('授课对象'),
                textCell(basic?.audience ?? '', ['basic.audience']),
              ],
              style,
            ),
            tableRow(
              'basic.teachingTime',
              'basic',
              [
                labelCell('授课时间'),
                textCell(basic?.teachingTime ?? '', ['basic.teachingTime']),
                labelCell('授课地点'),
                textCell(basic?.location ?? '', ['basic.location']),
              ],
              style,
            ),
            tableRow(
              'basic.chapter',
              'basic',
              [labelCell('教学章节'), textCell(basic?.chapter ?? '', ['basic.chapter'], { colspan: 3 })],
              style,
            ),
          ],
        });
        break;
      }
      case 'analysis': {
        result.push({
          id,
          label: `${no}、教学分析`,
          rows: [
            bandRow(`${id}.band`, 'analysis', `${no}、教学分析`, style),
            tableRow('analysis.learning', 'analysis', [labelCell('学情分析'), textCell(analysis?.learning ?? '', ['analysis.learning'])], style),
            tableRow('analysis.textbook', 'analysis', [labelCell('教材分析'), textCell(analysis?.textbook ?? '', ['analysis.textbook'])], style),
            tableRow('analysis.content', 'analysis', [labelCell('教学内容'), textCell(analysis?.content ?? '', ['analysis.content'])], style),
            tableRow('analysis.ideological', 'analysis', [labelCell('思政资源'), textCell(analysis?.ideological ?? '', ['analysis.ideological'])], style),
          ],
        });
        break;
      }
      case 'objectives': {
        const keyPoints = readKeyPoints(data.keyPoints);
        const keyText = keyPoints.other.length > 0 ? [keyPoints.key, keyPoints.other.join('\n')].filter(Boolean).join('\n') : keyPoints.key;
        result.push({
          id,
          label: `${no}、教学目标`,
          rows: [
            bandRow(`${id}.band`, 'objectives', `${no}、教学目标`, style),
            ...objectivesGroup(data, style),
            tableRow(
              'objectives.key',
              'objectives',
              [labelCell('教学重点'), textCell(keyText, ['objectives.key', 'objectives.keyPoints'], { colspan: 2 })],
              style,
            ),
            tableRow(
              'objectives.difficulty',
              'objectives',
              [labelCell('教学难点'), textCell(keyPoints.difficulty, ['objectives.difficulty', 'objectives.keyPoints'], { colspan: 2 })],
              style,
            ),
          ],
        });
        break;
      }
      case 'strategy': {
        const designThinking = strategy?.designThinking || data.teachingDesign;
        result.push({
          id,
          label: `${no}、教学策略`,
          rows: [
            bandRow(`${id}.band`, 'objectives', `${no}、教学策略`, style),
            tableRow(
              'strategy.designThinking',
              'objectives',
              [
                labelCell('设计思路'),
                textCell(designThinking, ['strategy.designThinking', 'strategy.teachingDesign'], { colspan: 2 }),
              ],
              style,
            ),
            tableRow(
              'strategy.teachingFlow',
              'objectives',
              [labelCell('教学流程'), textCell(strategy?.teachingFlow ?? '', ['strategy.teachingFlow'], { colspan: 2 })],
              style,
            ),
            tableRow(
              'strategy.methods',
              'objectives',
              [labelCell('教学手段'), textCell(strategy?.methods ?? '', ['strategy.methods'], { colspan: 2 })],
              style,
            ),
          ],
        });
        break;
      }
      case 'process': {
        const rows = processToV2(data);
        const blocks: PreviewRowSeed[] = [
          bandRow(`${id}.band`, 'process', `${no}、教学过程`, style),
          {
            id: 'process.head',
            tableId: 'process',
            columns: 4,
            kind: 'process-head',
            label: '教学环节',
            cells: [
              { text: '教学环节', role: 'header', rowspan: 2 },
              { text: '教学活动', role: 'header', colspan: 2 },
              { text: '设计意图', role: 'header', rowspan: 2 },
            ],
            minHeight: 32,
            height: 32,
            mergeGroup: 'process-header',
            keepWithNext: true,
          },
          {
            id: 'process.head.sub',
            tableId: 'process',
            columns: 4,
            kind: 'process-head',
            label: '教师活动',
            cells: [
              { text: '教师活动', role: 'header' },
              { text: '学生活动', role: 'header' },
            ],
            minHeight: 32,
            height: 32,
            mergeGroup: 'process-header',
          },
        ];
        const contentWidth = A4_WIDTH_PX - style.pageMargin * 2;
        const columns = tableColumns('process');
        let lastPhase = '';
        if (rows.length === 0) {
          const emptyCells: PreviewCell[] = [
            { text: '（暂无教学环节：可在中栏「教学过程」添加）', role: 'value', colspan: 4 },
          ];
          blocks.push({
            id: 'process.empty',
            tableId: 'process',
            columns: 4,
            kind: 'row',
            label: '—',
            cells: emptyCells,
            minHeight: 0,
            height: measureCells(emptyCells, columns, contentWidth, style, 0),
            splittable: true,
          });
        }
        for (const row of rows) {
          const phaseLabel = row.phaseLabel || PHASE_LABELS[row.phase] || '';
          const phaseKey = `${row.phase}:${phaseLabel}`;
          if (phaseLabel && phaseKey !== lastPhase) {
            const phaseHeight = Math.round(style.labelSize * style.lineHeight + PHASE_EXTRA);
            blocks.push({
              id: `process.phase.${phaseKey}`,
              tableId: 'process',
              columns: 4,
              kind: 'process-phase',
              label: phaseLabel,
              cells: [{ text: phaseLabel, role: 'phase', colspan: 4 }],
              minHeight: phaseHeight,
              height: phaseHeight,
              keepWithNext: true,
            });
            lastPhase = phaseKey;
          }
          const cells: PreviewCell[] = [
            { text: row.title, role: 'label' },
            { text: row.teacherActivity, role: 'value' },
            { text: row.studentActivity, role: 'value' },
            { text: row.intent, role: 'value' },
          ];
          blocks.push({
            id: `process.${row.id}`,
            tableId: 'process',
            columns: 4,
            kind: 'row',
            label: row.title || '环节',
            cells,
            minHeight: 0,
            height: measureCells(cells, columns, contentWidth, style, 0),
            splittable: true,
          });
        }
        result.push({ id, label: `${no}、教学过程`, rows: blocks });
        break;
      }
      case 'evaluation': {
        result.push({
          id,
          label: `${no}、评价反馈`,
          rows: [bandRow(`${id}.band`, 'evaluation', `${no}、评价反馈`, style), ...evaluationRows(data, style)],
        });
        break;
      }
      case 'reflection': {
        result.push({
          id,
          label: `${no}、教学反思`,
          rows: [bandRow(`${id}.band`, 'evaluation', `${no}、教学反思`, style), ...reflectionRows(data, style)],
        });
        break;
      }
      default:
        break;
    }
  }
  return result;
}

/** 展平为分页用的行块（模块标题已包含在各模块行内）。 */
export function buildPreviewBlocks(
  data: LessonPlanData,
  modules: Array<LessonModuleEntry | LessonWorkbenchModuleWire>,
  rawStyle: unknown,
): PreviewBlock[] {
  const style = normalizeStyle(rawStyle);
  const blocks: PreviewBlock[] = [];
  buildModuleRows(data, modules, style).forEach((moduleRows, index) => {
    const gapBefore = index === 0 ? 0 : style.moduleGap;
    moduleRows.rows.forEach((row, rowIndex) => {
      blocks.push({
        ...row,
        moduleId: moduleRows.id,
        gapBefore: rowIndex === 0 ? gapBefore : 0,
      });
    });
  });
  return blocks;
}

/** 连续同组行（vMerge / 两行表头）视为一个不可拆单元。 */
function groupBlocks(blocks: PreviewBlock[]): PreviewBlock[][] {
  const units: PreviewBlock[][] = [];
  for (let index = 0; index < blocks.length; index += 1) {
    const block = blocks[index];
    if (!block.mergeGroup) {
      units.push([block]);
      continue;
    }
    const unit = [block];
    let next = index + 1;
    while (next < blocks.length && blocks[next].mergeGroup === block.mergeGroup) {
      unit.push(blocks[next]);
      next += 1;
    }
    units.push(unit);
    index = next - 1;
  }
  return units;
}

function unitHeight(unit: PreviewBlock[]): number {
  return unit.reduce((sum, block) => sum + block.height, 0);
}

/** 至少能放下 MIN_SPLIT_LINES 行的高度（含内边距与段距），用于判断是否值得拆分。 */
export function minSplitHeight(rawStyle: unknown): number {
  const style = normalizeStyle(rawStyle);
  return Math.round(
    MIN_SPLIT_LINES * style.baseSize * style.lineHeight +
      (MIN_SPLIT_LINES - 1) * style.paragraphGap +
      CELL_PAD_Y,
  );
}

function nextContinuationId(id: string): string {
  const match = /~cont(\d+)$/.exec(id);
  if (!match) return `${id}~cont1`;
  return `${id.slice(0, -match[0].length)}~cont${Number(match[1]) + 1}`;
}

/**
 * 把一个长行按可用高度拆成「本页部分 + 下一页续行」。
 *
 * 行内所有单元格按同一行数切分（标签格通常只有一行，续行自然为空）；返回 null 表示
 * 不值得拆（只剩一行、已没有续文、或可用高度不足 MIN_SPLIT_LINES）。
 */
export function splitRow(
  block: PreviewBlock,
  available: number,
  rawStyle: unknown,
): { head: PreviewBlock; tail: PreviewBlock | null } | null {
  const style = normalizeStyle(rawStyle);
  if (!block.splittable || block.kind !== 'row' || block.mergeGroup) return null;
  if (available < minSplitHeight(style)) return null;
  const columns = tableColumns(block.tableId);
  const contentWidth = A4_WIDTH_PX - style.pageMargin * 2;
  let cursor = 0;
  const cellLines = block.cells.map((cell) => {
    const span = cell.colspan ?? 1;
    const width = cellWidth(columns, cursor, span, contentWidth);
    cursor += span;
    const fontSize =
      cell.role === 'label' || cell.role === 'header' || cell.role === 'phase'
        ? style.labelSize
        : style.baseSize;
    return { cell, fontSize, lines: wrapTextLines(cell.text, Math.max(24, width), fontSize) };
  });
  const maxLines = Math.max(...cellLines.map((entry) => entry.lines.length), 0);
  if (maxLines <= 1) return null;
  const maxFont = Math.max(...cellLines.map((entry) => entry.fontSize));
  const heightFor = (count: number) =>
    count * maxFont * style.lineHeight + Math.max(0, count - 1) * style.paragraphGap + CELL_PAD_Y;
  let take = 0;
  for (let count = maxLines - 1; count >= 1; count -= 1) {
    if (heightFor(count) <= available) {
      take = count;
      break;
    }
  }
  if (take < 1) return null;

  const headCells: PreviewCell[] = [];
  const tailCells: PreviewCell[] = [];
  let tailHasText = false;
  for (const entry of cellLines) {
    const headText = entry.lines.slice(0, take).join('\n');
    const tailText = entry.lines.slice(take).join('\n');
    headCells.push({ ...entry.cell, text: headText });
    tailCells.push({ ...entry.cell, text: tailText });
    if (tailText) tailHasText = true;
  }
  if (!tailHasText) return null;

  return {
    head: {
      ...block,
      cells: headCells,
      height: measureCells(headCells, columns, contentWidth, style, 0),
      minHeight: 0,
      gapBefore: block.gapBefore,
      keepWithNext: false,
    },
    tail: {
      ...block,
      id: nextContinuationId(block.id),
      cells: tailCells,
      height: measureCells(tailCells, columns, contentWidth, style, 0),
      minHeight: 0,
      gapBefore: 0,
      keepWithNext: false,
      continuation: true,
    },
  };
}

/** 按内容流分页；页码从 3 开始。长行按可用高度跨页拆分，避免整行跳页留下空白。 */
export function paginateBlocks(blocks: PreviewBlock[], rawStyle: unknown): PreviewPage[] {
  const style = normalizeStyle(rawStyle);
  const capacity = A4_HEIGHT_PX - style.pageMargin * 2 - PAGE_FOOTER_RESERVE_PX;
  /** 第一张正文纸顶部有「{课程名称}　教学设计」标题，占一行加下边距。 */
  const titleReserve = Math.round(style.headingSize * 1.4 + 12);
  const minSplit = minSplitHeight(style);
  const queue = groupBlocks(blocks);
  const pages: PreviewBlock[][] = [];
  let current: PreviewBlock[] = [];
  let remaining = capacity - titleReserve;
  const flush = () => {
    if (current.length > 0) {
      pages.push(current);
      current = [];
      remaining = capacity;
    }
  };

  while (queue.length > 0) {
    const unit = queue[0];
    const gap = current.length === 0 ? 0 : unit[0].gapBefore;
    const needed = unitHeight(unit) + gap;

    if (needed <= remaining) {
      queue.shift();
      unit.forEach((block, index) => {
        current.push(index === 0 && gap > 0 ? { ...block, gapBefore: gap } : block);
      });
      remaining -= needed;

      // 孤行控制：标题/阶段行/表头后面至少还要留得下一小段（可拆行按 3 行算）。
      const next = queue[0];
      const last = unit[unit.length - 1];
      if (last.keepWithNext && next && current.length > unit.length) {
        const nextNeed = next.length === 1 && next[0].splittable ? minSplit : unitHeight(next);
        if (nextNeed + next[0].gapBefore > remaining) {
          current.splice(current.length - unit.length, unit.length);
          flush();
          queue.unshift(unit);
        }
      }
      continue;
    }

    // 放不下：单行可拆时先拆，把本页填满。
    if (unit.length === 1 && unit[0].splittable) {
      const split = splitRow(unit[0], remaining - gap, style);
      if (split) {
        queue.shift();
        current.push(gap > 0 ? { ...split.head, gapBefore: gap } : split.head);
        flush();
        if (split.tail) queue.unshift([split.tail]);
        continue;
      }
    }

    if (current.length > 0) {
      flush();
      continue;
    }

    // 空页仍放不下（单行高于整页）：按整页高度连续拆分。
    if (unit.length === 1 && unit[0].splittable) {
      const split = splitRow(unit[0], capacity - 2, style);
      if (split) {
        queue.shift();
        current.push(split.head);
        flush();
        if (split.tail) queue.unshift([split.tail]);
        continue;
      }
    }

    // 不可拆且高于整页：独立放一页（宁可溢出也不死循环）。
    queue.shift();
    current.push(...unit);
    flush();
  }

  flush();
  const result = pages.map((page, index) => ({ number: FIRST_CONTENT_PAGE + index, blocks: page }));
  if (result.length === 0) result.push({ number: FIRST_CONTENT_PAGE, blocks: [] });
  return result;
}

export function layoutPreview(
  data: LessonPlanData,
  modules: Array<LessonModuleEntry | LessonWorkbenchModuleWire>,
  style: unknown,
): PreviewLayout {
  const blocks = buildPreviewBlocks(data, modules, style);
  return { blocks, pages: paginateBlocks(blocks, style) };
}

/**
 * 各模块在**正文**中的起始页码（正文从 1 起，与 docx 的 pgNumType start=1 一致）。
 * 导出目录使用这份映射，避免前后端两套估算各说各话。
 */
export function sectionPageMap(pages: PreviewPage[]): Record<string, number> {
  const map: Record<string, number> = {};
  for (const page of pages) {
    for (const block of page.blocks) {
      if (block.kind !== 'band' && block.kind !== 'custom-band') continue;
      if (map[block.moduleId] == null) {
        map[block.moduleId] = page.number - (FIRST_CONTENT_PAGE - 1);
      }
    }
  }
  return map;
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
