/**
 * 教案正文的默认值与容错补全（R7-FE）。
 *
 * 契约冻结：`LessonPlanData` 的 v1 字段（title/totalLessons/…/process）必须保留，
 * v2 字段（basic/analysis/strategy/evaluation/processV2）全 optional。本模块是**唯一**
 * 的补全入口：旧草稿、旧服务端修订、AI 候选都从这里得到完整形状，任何字段缺失都不抛错、
 * 不丢文本；只有「值类型明显错误」（如对象出现在字符串位置）才降级为空串并记警告。
 */
import type {
  LessonBasicInfo,
  LessonEvaluationFeedback,
  LessonPlanData,
  LessonTeachingAnalysis,
  LessonTeachingStrategy,
  LessonType,
  ProcessItem,
  ProcessItemV2,
  ProcessPhase,
} from '@/contracts/lesson-plans';

export const LESSON_TYPES: readonly LessonType[] = ['new', 'review', 'exercise', 'experiment', 'other'];

export const PROCESS_PHASES: readonly ProcessPhase[] = [
  'warmup',
  'introduction',
  'exploration',
  'practice',
  'conclusion',
];

export const PHASE_LABELS: Record<ProcessPhase, string> = {
  warmup: '课前热身',
  introduction: '课程引入',
  exploration: '深入研讨',
  practice: '练习巩固',
  conclusion: '总结提升',
};

export function emptyBasicInfo(): LessonBasicInfo {
  return {
    courseName: '',
    teacher: '',
    audience: '',
    hours: '',
    teachingTime: '',
    location: '',
    chapter: '',
  };
}

export function emptyAnalysis(): LessonTeachingAnalysis {
  return { learning: '', textbook: '', content: '', ideological: '' };
}

export function emptyStrategy(): LessonTeachingStrategy {
  return { designThinking: '', teachingFlow: '', methods: '' };
}

export function emptyEvaluation(): LessonEvaluationFeedback {
  return { afterClassTest: '', homework: '' };
}

export function emptyProcessV2Row(): ProcessItemV2 {
  return {
    id: newId(),
    phase: 'exploration',
    phaseLabel: '',
    title: '',
    teacherActivity: '',
    studentActivity: '',
    intent: '',
  };
}

export function emptyLessonData(): LessonPlanData {
  return {
    title: '',
    totalLessons: '1',
    currentLessonNo: '1',
    lessonTypes: ['new'],
    otherTypeText: '',
    coreCompetencies: '',
    keyPoints: '',
    teachingDesign: '',
    process: [],
    exercises: '',
    reflection: '',
    basic: emptyBasicInfo(),
    analysis: emptyAnalysis(),
    strategy: emptyStrategy(),
    evaluation: emptyEvaluation(),
    processV2: [],
  };
}

/** 唯一 id：`crypto.randomUUID` 不可用时退回时间+随机（仅用于行/模块标识，不是安全标识）。 */
export function newId(): string {
  const globalCrypto = typeof globalThis !== 'undefined' ? globalThis.crypto : undefined;
  if (globalCrypto && typeof globalCrypto.randomUUID === 'function') return globalCrypto.randomUUID();
  return `id-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
}

function text(value: unknown): string {
  return typeof value === 'string' ? value : '';
}

function record(value: unknown): Record<string, unknown> | null {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

export function normalizeBasicInfo(value: unknown): LessonBasicInfo {
  const source = record(value);
  return {
    courseName: text(source?.courseName),
    teacher: text(source?.teacher),
    audience: text(source?.audience),
    hours: text(source?.hours),
    teachingTime: text(source?.teachingTime),
    location: text(source?.location),
    chapter: text(source?.chapter),
  };
}

export function normalizeAnalysis(value: unknown): LessonTeachingAnalysis {
  const source = record(value);
  return {
    learning: text(source?.learning),
    textbook: text(source?.textbook),
    content: text(source?.content),
    ideological: text(source?.ideological),
  };
}

export function normalizeStrategy(value: unknown): LessonTeachingStrategy {
  const source = record(value);
  return {
    designThinking: text(source?.designThinking),
    teachingFlow: text(source?.teachingFlow),
    methods: text(source?.methods),
  };
}

export function normalizeEvaluation(value: unknown): LessonEvaluationFeedback {
  const source = record(value);
  return {
    afterClassTest: text(source?.afterClassTest),
    homework: text(source?.homework),
  };
}

function normalizeProcessItem(value: unknown, index: number): ProcessItem {
  const source = record(value);
  return {
    id: text(source?.id) || `process-${index}`,
    stage: text(source?.stage),
    design: text(source?.design),
    secondary: text(source?.secondary),
  };
}

function normalizePhase(value: unknown): ProcessPhase {
  return typeof value === 'string' && (PROCESS_PHASES as readonly string[]).includes(value)
    ? (value as ProcessPhase)
    : 'exploration';
}

export function normalizeProcessV2Row(value: unknown, index: number): ProcessItemV2 {
  const source = record(value);
  return {
    id: text(source?.id) || `p2-${index}`,
    phase: normalizePhase(source?.phase),
    phaseLabel: text(source?.phaseLabel),
    title: text(source?.title),
    teacherActivity: text(source?.teacherActivity),
    studentActivity: text(source?.studentActivity),
    intent: text(source?.intent),
  };
}

/**
 * 旧两列 `process` → v2 三列行的展示兜底（stage→环节名、design→教师活动、secondary→设计意图）。
 * 只在 `processV2` 为空时使用；不写回数据。
 */
export function processToV2(data: LessonPlanData): ProcessItemV2[] {
  const rows = data.processV2 ?? [];
  if (rows.length > 0) return rows;
  return (data.process ?? []).map((item, index) => ({
    id: item.id || `process-${index}`,
    phase: 'exploration' as ProcessPhase,
    phaseLabel: '',
    title: item.stage,
    teacherActivity: item.design,
    studentActivity: '',
    intent: item.secondary,
  }));
}

/** 容错补全：把任意记录补成完整 `LessonPlanData`；非对象输入返回空文档。 */
export function withLessonDefaults(value: unknown): LessonPlanData {
  const source = record(value);
  if (!source) return emptyLessonData();
  const defaultTypes: LessonType[] = ['new'];
  const lessonTypes: LessonType[] = Array.isArray(source.lessonTypes)
    ? source.lessonTypes.filter((item): item is LessonType =>
        typeof item === 'string' && (LESSON_TYPES as readonly string[]).includes(item),
      )
    : defaultTypes;
  return {
    title: text(source.title),
    totalLessons: text(source.totalLessons) || '1',
    currentLessonNo: text(source.currentLessonNo) || '1',
    lessonTypes: lessonTypes.length > 0 ? lessonTypes : defaultTypes,
    otherTypeText: text(source.otherTypeText),
    coreCompetencies: text(source.coreCompetencies),
    keyPoints: text(source.keyPoints),
    teachingDesign: text(source.teachingDesign),
    process: Array.isArray(source.process)
      ? source.process.map(normalizeProcessItem)
      : [],
    exercises: text(source.exercises),
    reflection: text(source.reflection),
    basic: normalizeBasicInfo(source.basic),
    analysis: normalizeAnalysis(source.analysis),
    strategy: normalizeStrategy(source.strategy),
    evaluation: normalizeEvaluation(source.evaluation),
    processV2: Array.isArray(source.processV2)
      ? source.processV2.map(normalizeProcessV2Row)
      : [],
  };
}

/** 结构化克隆，保证 store 快照不与组件共享引用。 */
export function cloneLessonData(data: LessonPlanData): LessonPlanData {
  return {
    ...data,
    lessonTypes: [...data.lessonTypes],
    process: data.process.map((item) => ({ ...item })),
    basic: { ...normalizeBasicInfo(data.basic) },
    analysis: { ...normalizeAnalysis(data.analysis) },
    strategy: { ...normalizeStrategy(data.strategy) },
    evaluation: { ...normalizeEvaluation(data.evaluation) },
    processV2: (data.processV2 ?? []).map((row) => ({ ...row })),
  };
}
