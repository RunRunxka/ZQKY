/**
 * 生成流文本 → 表格字段的逐格解析（R7-FE）。
 *
 * 红线：解析结果只形成**候选**（模块 → 字段值 + 教学过程行），由教师「采用」后才写进草稿；
 * 未识别的行不丢弃，留在 `unparsed` 里由界面照实提示（候选原文始终可见）。
 *
 * 字段路径与预览表格行 id 一一对应（如 `analysis.learning`、`objectives.knowledge`），
 * 因此「正在填充哪一格」在预览里有确定的高亮位置。
 */
import type {
  LessonBasicInfo,
  LessonEvaluationFeedback,
  LessonPlanData,
  LessonTeachingAnalysis,
  LessonTeachingStrategy,
  ProcessItemV2,
} from '@/contracts/lesson-plans';
import {
  emptyProcessV2Row,
  newId,
  normalizeAnalysis,
  normalizeBasicInfo,
  normalizeEvaluation,
  normalizeStrategy,
} from '../model/lesson-data';
import { readKeyPoints, readObjectives, writeKeyPoints, writeObjectives } from '../model/objectives';

/** 字段路径的键判定：`analysis.learning` 这类路径必须落在契约的键集合内才写回。 */
const isBasicField = (key: string): key is keyof LessonBasicInfo => key in normalizeBasicInfo(null);
const isAnalysisField = (key: string): key is keyof LessonTeachingAnalysis => key in normalizeAnalysis(null);
const isStrategyField = (key: string): key is keyof LessonTeachingStrategy => key in normalizeStrategy(null);
const isEvaluationField = (key: string): key is keyof LessonEvaluationFeedback =>
  key in normalizeEvaluation(null);

export interface LessonFieldFill {
  /** 与预览行 id 一致（如 `analysis.learning`）。 */
  field: string;
  label: string;
  value: string;
}

export interface ModuleFillResult {
  /** 生成流模块键（analysis/objectives/…）。 */
  module: string;
  fields: LessonFieldFill[];
  processRows: ProcessItemV2[];
  unparsed: string[];
}

interface SectionLabel {
  pattern: RegExp;
  field: string;
  label: string;
}

function sectionParser(labels: SectionLabel[], fallbackField?: string, fallbackLabel?: string) {
  return (text: string): { fields: LessonFieldFill[]; unparsed: string[] } => {
    const values = new Map<string, { label: string; value: string }>();
    const unparsed: string[] = [];
    let current: SectionLabel | null = null;
    for (const rawLine of text.split(/\r?\n/)) {
      const line = rawLine.trim();
      if (!line) continue;
      const matched = labels.find((label) => label.pattern.test(line));
      if (matched) {
        current = matched;
        const value = line.replace(matched.pattern, '').trim();
        const existing = values.get(matched.field);
        const merged = value ? (existing?.value ? `${existing.value}\n${value}` : value) : (existing?.value ?? '');
        values.set(matched.field, { label: matched.label, value: merged });
        continue;
      }
      if (current) {
        const existing = values.get(current.field)!;
        existing.value = existing.value ? `${existing.value}\n${line}` : line;
        continue;
      }
      if (fallbackField) {
        const existing = values.get(fallbackField);
        values.set(fallbackField, {
          label: fallbackLabel ?? fallbackField,
          value: existing?.value ? `${existing.value}\n${line}` : line,
        });
        continue;
      }
      unparsed.push(line);
    }
    return {
      fields: [...values.entries()]
        .filter(([, entry]) => entry.value.trim().length > 0)
        .map(([field, entry]) => ({ field, label: entry.label, value: entry.value.trim() })),
      unparsed,
    };
  };
}

const ANALYSIS_LABELS: SectionLabel[] = [
  { pattern: /^\s*(?:[#>*\-•·]+\s*)?【?\s*学情分析\s*】?\s*[：:]?\s*/, field: 'analysis.learning', label: '学情分析' },
  { pattern: /^\s*(?:[#>*\-•·]+\s*)?【?\s*教材分析\s*】?\s*[：:]?\s*/, field: 'analysis.textbook', label: '教材分析' },
  { pattern: /^\s*(?:[#>*\-•·]+\s*)?【?\s*教学内容\s*】?\s*[：:]?\s*/, field: 'analysis.content', label: '教学内容' },
  { pattern: /^\s*(?:[#>*\-•·]+\s*)?【?\s*思政(?:资源|元素)\s*】?\s*[：:]?\s*/, field: 'analysis.ideological', label: '思政资源' },
];

const STRATEGY_LABELS: SectionLabel[] = [
  { pattern: /^\s*(?:[#>*\-•·]+\s*)?【?\s*设计思路\s*】?\s*[：:]?\s*/, field: 'strategy.designThinking', label: '设计思路' },
  { pattern: /^\s*(?:[#>*\-•·]+\s*)?【?\s*教学流程\s*】?\s*[：:]?\s*/, field: 'strategy.teachingFlow', label: '教学流程' },
  { pattern: /^\s*(?:[#>*\-•·]+\s*)?【?\s*教学手段\s*】?\s*[：:]?\s*/, field: 'strategy.methods', label: '教学手段' },
  { pattern: /^\s*(?:[#>*\-•·]+\s*)?【?\s*教学设计(?:（[^）]*）)?\s*】?\s*[：:]?\s*/, field: 'strategy.teachingDesign', label: '教学设计' },
];

const EVALUATION_LABELS: SectionLabel[] = [
  { pattern: /^\s*(?:[#>*\-•·]+\s*)?【?\s*课后测试情况\s*】?\s*[：:]?\s*/, field: 'evaluation.afterClassTest', label: '课后测试情况' },
  { pattern: /^\s*(?:[#>*\-•·]+\s*)?【?\s*课后作业(?:情况)?\s*】?\s*[：:]?\s*/, field: 'evaluation.homework', label: '作业情况' },
  { pattern: /^\s*(?:[#>*\-•·]+\s*)?【?\s*作业情况\s*】?\s*[：:]?\s*/, field: 'evaluation.homework', label: '作业情况' },
];

/** 阶段小标题行（教学过程）：`【课前热身】`「课程引入」或「阶段：练习巩固」。 */
const PHASE_LINE = /^\s*(?:【(.+?)】|\[(.+?)\]|（(.+?)）|阶段\s*[：:]\s*(.+?))\s*$/;

const PHASE_KEYWORDS: Array<{ keyword: RegExp; phase: ProcessItemV2['phase'] }> = [
  { keyword: /(热身|导入|引入)/, phase: 'introduction' },
  { keyword: /(研讨|探究|探索|新授)/, phase: 'exploration' },
  { keyword: /(练习|巩固|实践)/, phase: 'practice' },
  { keyword: /(总结|提升|小结|拓展)/, phase: 'conclusion' },
];

function phaseOfLabel(label: string): ProcessItemV2['phase'] {
  return PHASE_KEYWORDS.find((entry) => entry.keyword.test(label))?.phase ?? 'exploration';
}

/** 教学过程行解析：`环节名 | 教师活动 | 学生活动 | 设计意图`（分隔符 `|` 或 `｜`）。 */
export function parseProcessLines(text: string): { rows: ProcessItemV2[]; unparsed: string[] } {
  const rows: ProcessItemV2[] = [];
  const unparsed: string[] = [];
  let phaseLabel = '';
  let phase: ProcessItemV2['phase'] = 'exploration';
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line) continue;
    const phaseMatch = PHASE_LINE.exec(line);
    if (phaseMatch) {
      const label = (phaseMatch[1] ?? phaseMatch[2] ?? phaseMatch[3] ?? phaseMatch[4] ?? '').trim();
      if (label) {
        phaseLabel = label;
        phase = phaseOfLabel(label);
        continue;
      }
    }
    const parts = line
      .replace(/^\s*(?:[#>*\-•·]+\s*)?/, '')
      .split(/[|｜]/)
      .map((part) => part.trim());
    if (parts.length >= 2) {
      // 没有显式阶段行时按环节名推断阶段（不编造阶段小标题：phaseLabel 仍留空）。
      const rowPhase = phaseLabel ? phase : phaseOfLabel(parts[0]);
      rows.push({
        id: newId(),
        phase: rowPhase,
        phaseLabel,
        title: parts[0],
        teacherActivity: parts[1] ?? '',
        studentActivity: parts[2] ?? '',
        intent: parts.slice(3).join(' ').trim(),
      });
      continue;
    }
    if (line.length <= 24 && !/[，。；,.、]/.test(line) && rows.length === 0) {
      // 极短且无标点的孤行更可能是阶段名而不是环节正文。
      phaseLabel = line;
      phase = phaseOfLabel(line);
      continue;
    }
    rows.push({
      ...emptyProcessV2Row(),
      phase,
      phaseLabel,
      title: line,
    });
  }
  return { rows, unparsed };
}

/** 目标模块：知识/能力/思政 + 教学重点/难点（复用 objectives codec）。 */
function parseObjectives(text: string): { fields: LessonFieldFill[]; unparsed: string[] } {
  const objectives = readObjectives(text);
  const keyPoints = readKeyPoints(objectives.other.join('\n'));
  const fields: LessonFieldFill[] = [];
  if (objectives.rows.knowledge) fields.push({ field: 'objectives.knowledge', label: '知识目标', value: objectives.rows.knowledge });
  if (objectives.rows.ability) fields.push({ field: 'objectives.ability', label: '能力目标', value: objectives.rows.ability });
  if (objectives.rows.ideological)
    fields.push({ field: 'objectives.ideological', label: '思政目标', value: objectives.rows.ideological });
  const composed = keyPoints.key || keyPoints.difficulty ? writeKeyPoints(keyPoints) : '';
  if (composed) fields.push({ field: 'objectives.keyPoints', label: '教学重点与难点', value: composed });
  return {
    fields,
    unparsed: objectives.structured
      ? []
      : text.split(/\r?\n/).filter((line) => line.trim().length > 0),
  };
}

const parsers: Record<string, (text: string) => { fields: LessonFieldFill[]; unparsed: string[] }> = {
  analysis: sectionParser(ANALYSIS_LABELS, 'analysis.learning', '学情分析'),
  objectives: parseObjectives,
  strategy: sectionParser(STRATEGY_LABELS, 'strategy.designThinking', '设计思路'),
  evaluation: sectionParser(EVALUATION_LABELS, 'evaluation.afterClassTest', '课后测试情况'),
  exercises: (text) => {
    const { fields } = sectionParser([], 'evaluation.exercises', '练习与作业')(text);
    return { fields, unparsed: [] };
  },
  reflection: (text) => {
    const value = text.trim();
    return {
      fields: value ? [{ field: 'reflection', label: '教学反思', value }] : [],
      unparsed: [],
    };
  },
};

/** 解析某模块的流式文本（可增量调用，文本永远从头累积）。 */
export function parseModuleText(moduleKey: string, text: string): ModuleFillResult {
  if (moduleKey === 'process') {
    const { rows, unparsed } = parseProcessLines(text);
    return { module: moduleKey, fields: [], processRows: rows, unparsed };
  }
  const parser = parsers[moduleKey];
  if (!parser) {
    return { module: moduleKey, fields: [], processRows: [], unparsed: text.trim() ? [text.trim()] : [] };
  }
  const { fields, unparsed } = parser(text);
  return { module: moduleKey, fields, processRows: [], unparsed };
}

/** 把多条模块结果合并为一份正文补丁（只覆盖有值的字段，不动其它内容）。 */
export function applyFillToData(data: LessonPlanData, results: ModuleFillResult[]): LessonPlanData {
  const next: LessonPlanData = {
    ...data,
    lessonTypes: [...data.lessonTypes],
    process: data.process.map((item) => ({ ...item })),
    basic: normalizeBasicInfo(data.basic),
    analysis: normalizeAnalysis(data.analysis),
    strategy: normalizeStrategy(data.strategy),
    evaluation: normalizeEvaluation(data.evaluation),
    processV2: (data.processV2 ?? []).map((row) => ({ ...row })),
  };
  for (const result of results) {
    for (const field of result.fields) {
      const [head, tail] = field.field.split('.');
      if (head === 'basic' && tail && isBasicField(tail)) {
        next.basic![tail] = field.value;
      } else if (head === 'analysis' && tail && isAnalysisField(tail)) {
        next.analysis![tail] = field.value;
      } else if (head === 'strategy' && tail && isStrategyField(tail)) {
        next.strategy![tail] = field.value;
      } else if (head === 'evaluation' && tail && isEvaluationField(tail)) {
        next.evaluation![tail] = field.value;
      } else if (head === 'objectives') {
        if (tail === 'knowledge' || tail === 'ability' || tail === 'ideological') {
          const view = readObjectives(next.coreCompetencies);
          view.rows[tail] = field.value;
          view.structured = true;
          next.coreCompetencies = writeObjectives(view);
        } else if (tail === 'keyPoints') {
          next.keyPoints = field.value;
        }
      } else if (field.field === 'reflection') {
        next.reflection = field.value;
      }
    }
    if (result.processRows.length > 0) {
      next.processV2 = result.processRows.map((row) => ({ ...row }));
    }
  }
  return next;
}

/** 候选覆盖后的展示正文（草稿 + 未采用候选）。 */
export function mergeCandidateData(
  data: LessonPlanData,
  results: ModuleFillResult[],
): { data: LessonPlanData; filledFields: Set<string> } {
  const filledFields = new Set<string>();
  for (const result of results) {
    for (const field of result.fields) filledFields.add(field.field);
    if (result.processRows.length > 0) filledFields.add('process');
  }
  return { data: applyFillToData(data, results), filledFields };
}
