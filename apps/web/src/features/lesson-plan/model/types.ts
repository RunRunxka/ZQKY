export const lessonTypeLabels = {
  new: '新课',
  review: '复习课',
  exercise: '试题讲评课',
  experiment: '实验课',
  other: '其它',
} as const;
export type LessonType = keyof typeof lessonTypeLabels;
export interface ProcessItem {
  id: string;
  stage: string;
  design: string;
  secondary: string;
}
export interface LessonPlanData {
  title: string;
  totalLessons: string;
  currentLessonNo: string;
  lessonTypes: LessonType[];
  otherTypeText: string;
  coreCompetencies: string;
  keyPoints: string;
  teachingDesign: string;
  process: ProcessItem[];
  exercises: string;
  reflection: string;
}
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
export interface DraftEnvelope {
  schemaVersion: 1;
  revision: number;
  updatedAt: string;
  data: LessonPlanData;
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
