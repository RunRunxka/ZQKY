import type { LessonPlanData, DraftEnvelope } from '@/contracts/lesson-plans';
export type { LessonType, ProcessItem, LessonPlanData, DraftEnvelope } from '@/contracts/lesson-plans';
export const lessonTypeLabels = {
  new: '新课',
  review: '复习课',
  exercise: '试题讲评课',
  experiment: '实验课',
  other: '其它',
} as const;
export type TextField = Exclude<keyof LessonPlanData, 'lessonTypes' | 'process'>;
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
