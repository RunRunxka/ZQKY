/**
 * 教案工作台模块登记与排版设置（R7-FE 三栏复刻）。
 *
 * 模板两页不预览：第 1 页封面、第 2 页目录（七模块 + 附件三条）；**第 3 页起为内容**
 * （4 张表：一、基本信息；二、教学分析；三、教学目标；四、教学策略；五、教学过程；
 * 六、评价反馈；七、教学反思）。模块顺序、显隐、自定义模块与排版设置共同决定预览与导出。
 */
import type {
  LessonFontId,
  LessonPlanData,
  LessonWorkbenchModuleWire,
  LessonWorkbenchStyleWire,
} from '@/contracts/lesson-plans';
import { processToV2 } from './lesson-data';

export type BuiltinModuleId =
  | 'basic'
  | 'analysis'
  | 'objectives'
  | 'strategy'
  | 'process'
  | 'evaluation'
  | 'reflection';

export interface BuiltinModuleDef {
  id: BuiltinModuleId;
  /** 模板目录固定序号（一~七）；实际显示序号按可见顺序重排。 */
  no: string;
  label: string;
  /** 目录/表头副标题（说明这一节写什么）。 */
  hint: string;
  /** 固定模块：不可隐藏、不可删除（基本信息表是模板第一张内容表）。 */
  fixed?: boolean;
}

export const BUILTIN_MODULES: readonly BuiltinModuleDef[] = [
  {
    id: 'basic',
    no: '一',
    label: '基本信息',
    hint: '课程名称 / 授课对象 / 授课时间 / 授课地点 / 教学章节',
    fixed: true,
  },
  {
    id: 'analysis',
    no: '二',
    label: '教学分析',
    hint: '学情分析 / 教材分析 / 教学内容 / 思政资源',
  },
  {
    id: 'objectives',
    no: '三',
    label: '教学目标',
    hint: '知识 / 能力 / 思政 三行（vMerge）+ 教学重点、难点',
  },
  {
    id: 'strategy',
    no: '四',
    label: '教学策略',
    hint: '设计思路 / 教学流程 / 教学手段',
  },
  {
    id: 'process',
    no: '五',
    label: '教学过程',
    hint: '教学环节 × 教师活动 / 学生活动 / 设计意图（含阶段小标题行）',
  },
  {
    id: 'evaluation',
    no: '六',
    label: '评价反馈',
    hint: '模板四项：课后测试 / 课后作业 / 课后调查反馈 / 督导专家反馈',
  },
  {
    id: 'reflection',
    no: '七',
    label: '教学反思',
    hint: '目标达成度 / 教学特色 / 教学后记',
  },
] as const;

const CHINESE_NUMBERS = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十'] as const;

export function chineseNumber(index: number): string {
  if (index < CHINESE_NUMBERS.length) return CHINESE_NUMBERS[index];
  return String(index);
}

/* ------------------------------------------------------------------ 排版设置 */

export interface LessonFontOption {
  id: LessonFontId;
  label: string;
  /** CSS font-family；字体文件缺失时按族回退（见 public/fonts/README.md）。 */
  family: string;
}

export const LESSON_FONTS: readonly LessonFontOption[] = [
  {
    id: 'puhuiti',
    label: '阿里巴巴普惠体',
    family: "'Alibaba PuHuiTi', 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif",
  },
  {
    id: 'misans',
    label: 'MiSans',
    family: "'MiSans', 'MiSans Regular', 'PingFang SC', 'Microsoft YaHei', 'Noto Sans SC', sans-serif",
  },
  {
    id: 'noto-sans-sc',
    label: '思源黑体',
    family: "'Noto Sans SC', 'Source Han Sans SC', 'PingFang SC', 'Microsoft YaHei', sans-serif",
  },
  {
    id: 'source-han-serif',
    label: '思源宋体',
    family: "'Source Han Serif SC', 'Noto Serif SC', 'Songti SC', STSong, SimSun, serif",
  },
] as const;

export const DEFAULT_LESSON_STYLE: LessonWorkbenchStyleWire = {
  fontId: 'puhuiti',
  baseSize: 14,
  headingSize: 16,
  labelSize: 12,
  lineHeight: 1.7,
  pageMargin: 48,
  moduleGap: 16,
  paragraphGap: 6,
};

export const STYLE_LIMITS = {
  baseSize: { min: 12, max: 20, step: 1 },
  headingSize: { min: 13, max: 26, step: 1 },
  labelSize: { min: 10, max: 18, step: 1 },
  lineHeight: { min: 1, max: 2, step: 0.05 },
  pageMargin: { min: 24, max: 96, step: 4 },
  moduleGap: { min: 0, max: 40, step: 2 },
  paragraphGap: { min: 0, max: 24, step: 2 },
} as const;

export function fontFamilyOf(fontId: string): string {
  return (LESSON_FONTS.find((font) => font.id === fontId) ?? LESSON_FONTS[0]).family;
}

function clamp(value: unknown, min: number, max: number, fallback: number): number {
  const numeric = typeof value === 'number' && Number.isFinite(value) ? value : fallback;
  return Math.min(max, Math.max(min, Math.round(numeric * 100) / 100));
}

/** 容错补全排版设置（旧草稿缺 style 时取默认值，不抛错）。 */
export function normalizeStyle(value: unknown): LessonWorkbenchStyleWire {
  const source = (typeof value === 'object' && value !== null ? value : {}) as Record<string, unknown>;
  const fontId =
    typeof source.fontId === 'string' && LESSON_FONTS.some((font) => font.id === source.fontId)
      ? (source.fontId as LessonFontId)
      : DEFAULT_LESSON_STYLE.fontId;
  return {
    fontId,
    baseSize: clamp(source.baseSize, STYLE_LIMITS.baseSize.min, STYLE_LIMITS.baseSize.max, DEFAULT_LESSON_STYLE.baseSize),
    headingSize: clamp(
      source.headingSize,
      STYLE_LIMITS.headingSize.min,
      STYLE_LIMITS.headingSize.max,
      DEFAULT_LESSON_STYLE.headingSize,
    ),
    labelSize: clamp(source.labelSize, STYLE_LIMITS.labelSize.min, STYLE_LIMITS.labelSize.max, DEFAULT_LESSON_STYLE.labelSize),
    lineHeight: clamp(
      source.lineHeight,
      STYLE_LIMITS.lineHeight.min,
      STYLE_LIMITS.lineHeight.max,
      DEFAULT_LESSON_STYLE.lineHeight,
    ),
    pageMargin: clamp(
      source.pageMargin,
      STYLE_LIMITS.pageMargin.min,
      STYLE_LIMITS.pageMargin.max,
      DEFAULT_LESSON_STYLE.pageMargin,
    ),
    moduleGap: clamp(source.moduleGap, STYLE_LIMITS.moduleGap.min, STYLE_LIMITS.moduleGap.max, DEFAULT_LESSON_STYLE.moduleGap),
    paragraphGap: clamp(
      source.paragraphGap,
      STYLE_LIMITS.paragraphGap.min,
      STYLE_LIMITS.paragraphGap.max,
      DEFAULT_LESSON_STYLE.paragraphGap,
    ),
  };
}

/* ------------------------------------------------------------------ 模块布局 */

export interface LessonModuleEntry {
  id: string;
  kind: 'builtin' | 'custom';
  builtinId?: BuiltinModuleId;
  label: string;
  hidden: boolean;
  /** 自定义模块正文。 */
  body?: string;
}

export const CUSTOM_MODULE_PREFIX = 'custom-';

export function defaultModuleLayout(): LessonModuleEntry[] {
  return BUILTIN_MODULES.map((entry) => ({
    id: entry.id,
    kind: 'builtin' as const,
    builtinId: entry.id,
    label: entry.label,
    hidden: false,
  }));
}

export function builtinDef(id: string): BuiltinModuleDef | undefined {
  return BUILTIN_MODULES.find((entry) => entry.id === id);
}

function isBuiltinId(value: unknown): value is BuiltinModuleId {
  return typeof value === 'string' && BUILTIN_MODULES.some((entry) => entry.id === value);
}

/** 容错补全模块布局：未知内置键丢弃；缺省补全七个内置模块（旧草稿兼容）。 */
export function normalizeModules(value: unknown): LessonModuleEntry[] {
  if (!Array.isArray(value)) return defaultModuleLayout();
  const entries: LessonModuleEntry[] = [];
  const seen = new Set<string>();
  for (const item of value) {
    if (typeof item !== 'object' || item === null) continue;
    const source = item as Record<string, unknown>;
    const kind = source.kind === 'custom' ? 'custom' : 'builtin';
    if (kind === 'builtin') {
      const id = isBuiltinId(source.builtinId) ? source.builtinId : isBuiltinId(source.id) ? source.id : null;
      if (!id || seen.has(id)) continue;
      seen.add(id);
      const def = builtinDef(id)!;
      entries.push({
        id,
        kind: 'builtin',
        builtinId: id,
        label: def.label,
        hidden: source.hidden === true,
      });
      continue;
    }
    const id = typeof source.id === 'string' && source.id ? source.id : `${CUSTOM_MODULE_PREFIX}${entries.length}`;
    if (seen.has(id)) continue;
    seen.add(id);
    entries.push({
      id,
      kind: 'custom',
      label: typeof source.label === 'string' && source.label.trim() ? source.label : '自定义模块',
      hidden: source.hidden === true,
      body: typeof source.body === 'string' ? source.body : '',
    });
  }
  // 内置模块必须齐全（少的补回原位），但保持用户既有顺序。
  for (const def of BUILTIN_MODULES) {
    if (!seen.has(def.id)) {
      entries.push({ id: def.id, kind: 'builtin', builtinId: def.id, label: def.label, hidden: false });
    }
  }
  return entries;
}

export function modulesToWire(modules: LessonModuleEntry[]): LessonWorkbenchModuleWire[] {
  return modules.map((entry) => ({
    id: entry.id,
    kind: entry.kind,
    ...(entry.builtinId ? { builtinId: entry.builtinId } : {}),
    label: entry.label,
    ...(entry.hidden ? { hidden: true } : {}),
    ...(entry.kind === 'custom' ? { body: entry.body ?? '' } : {}),
  }));
}

/* ------------------------------------------------------------------ 完成度 */

function hasText(value: string | undefined): boolean {
  return typeof value === 'string' && value.trim().length > 0;
}

/** 模块完成度：核心字段有值即算完成（左栏状态点）。 */
export function moduleFilled(entry: LessonModuleEntry, data: LessonPlanData): boolean {
  if (entry.kind === 'custom') return hasText(entry.body);
  switch (entry.builtinId) {
    case 'basic': {
      const basic = data.basic;
      return (
        hasText(basic?.courseName) ||
        hasText(basic?.audience) ||
        hasText(basic?.teachingTime) ||
        hasText(basic?.location) ||
        hasText(basic?.chapter)
      );
    }
    case 'analysis': {
      const analysis = data.analysis;
      return (
        hasText(analysis?.learning) ||
        hasText(analysis?.textbook) ||
        hasText(analysis?.content) ||
        hasText(analysis?.ideological)
      );
    }
    case 'objectives':
      return hasText(data.coreCompetencies) || hasText(data.keyPoints);
    case 'strategy': {
      const strategy = data.strategy;
      return (
        hasText(strategy?.designThinking) ||
        hasText(strategy?.teachingFlow) ||
        hasText(strategy?.methods) ||
        hasText(data.teachingDesign)
      );
    }
    case 'process':
      return processToV2(data).some(
        (row) => hasText(row.title) || hasText(row.teacherActivity) || hasText(row.studentActivity) || hasText(row.intent),
      );
    case 'evaluation':
      return hasText(data.exercises) || hasText(data.evaluation?.afterClassTest) || hasText(data.evaluation?.homework);
    case 'reflection':
      return hasText(data.reflection);
    default:
      return false;
  }
}

/** 生成流模块键 → 工作台模块键（六、评价反馈同时承接 exercises 与 evaluation 两个流模块）。 */
export const STREAM_TO_MODULE: Record<string, BuiltinModuleId> = {
  analysis: 'analysis',
  objectives: 'objectives',
  strategy: 'strategy',
  process: 'process',
  exercises: 'evaluation',
  evaluation: 'evaluation',
  reflection: 'reflection',
};
