import type { LessonPlanData, DraftEnvelope } from '@/contracts/lesson-plans';
export type { LessonType, ProcessItem, LessonPlanData, DraftEnvelope } from '@/contracts/lesson-plans';
export type {
  LessonBasicInfo, LessonTeachingAnalysis, LessonTeachingStrategy,
  LessonEvaluationFeedback, ProcessItemV2, ProcessPhase,
} from '@/contracts/lesson-plans';
export const lessonTypeLabels = {
  new: '新课',
  review: '复习课',
  exercise: '试题讲评课',
  experiment: '实验课',
  other: '其它',
} as const;
/** 规则填充可写的字符串字段（模板 v2 的对象字段与三列过程不由自然语言规则填充）。 */
export type TextField = Exclude<keyof LessonPlanData,
  'lessonTypes' | 'process' | 'basic' | 'analysis' | 'strategy' | 'evaluation' | 'processV2'>;
export interface FillProposal {
  patch: Partial<LessonPlanData>;
  warnings: string[];
  source: string;
}
export interface FillProvider {
  id: string;
  parse(input: string, signal?: AbortSignal): Promise<FillProposal>;
}
export interface DraftRepository {
  load(): DraftEnvelope | null | Promise<DraftEnvelope | null>;
  save(draft: DraftEnvelope): void | Promise<void>;
}
export interface LessonPlanServices {
  fillProvider?: FillProvider;
  repository?: DraftRepository;
  onChange?: (draft: DraftEnvelope) => void;
}
