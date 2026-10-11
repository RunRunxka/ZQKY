/**
 * 教案工作台排版与模块登记（C3-2 三栏复刻）。
 *
 * 模块按用户模板七大目录组织；字段映射到 LessonPlanData（v2 新字段 + 旧字段），
 * 一期顺序固定（模板目录序），显隐/字体为会话内排版偏好。
 */
import type { LessonPlanData, ProcessItemV2 } from '@/contracts/lesson-plans';

export type LessonModuleId =
  | 'basic'
  | 'analysis'
  | 'objectives'
  | 'strategy'
  | 'process'
  | 'exercises'
  | 'reflection';

export interface LessonModuleDef {
  id: LessonModuleId;
  label: string;
  /** 模板目录序号（一~七） */
  no: string;
  /** 固定模块（不可显隐，如基本信息） */
  fixed?: boolean;
}

export const LESSON_MODULES: LessonModuleDef[] = [
  { id: 'basic', label: '基本信息', no: '一', fixed: true },
  { id: 'analysis', label: '教学分析', no: '二' },
  { id: 'objectives', label: '教学目标', no: '三' },
  { id: 'strategy', label: '教学策略', no: '四' },
  { id: 'process', label: '教学过程', no: '五' },
  { id: 'exercises', label: '练习与评价', no: '六' },
  { id: 'reflection', label: '教学反思', no: '七' },
];

/** 字体清单：普惠体自托管（默认），其余走系统字体（教案常用，导出依赖本机字体）。 */
export const LESSON_FONTS = [
  { id: 'puhuiti', label: '阿里巴巴普惠体', family: "'Alibaba PuHuiTi', 'Microsoft YaHei', sans-serif" },
  { id: 'yahei', label: '微软雅黑', family: "'Microsoft YaHei', sans-serif" },
  { id: 'fangsong', label: '仿宋', family: "'FangSong', 'FangSong_GB2312', serif" },
  { id: 'kaiti', label: '楷体', family: "'KaiTi', 'KaiTi_GB2312', serif" },
  { id: 'songti', label: '宋体', family: "'SimSun', serif" },
] as const;

export interface LessonStyleState {
  fontId: string;
  fontSize: number;
  lineHeight: number;
  hiddenModules: LessonModuleId[];
}

export const DEFAULT_LESSON_STYLE: LessonStyleState = {
  fontId: 'puhuiti',
  fontSize: 14,
  lineHeight: 1.7,
  hiddenModules: [],
};

export function fontFamilyOf(fontId: string): string {
  return (LESSON_FONTS.find((f) => f.id === fontId) ?? LESSON_FONTS[0]!).family;
}

/** 旧三列 process → v2 行映射（展示兜底：stage→标题，design→教师活动，secondary→设计意图）。 */
export function processToV2(data: LessonPlanData): ProcessItemV2[] {
  if (data.processV2 && data.processV2.length > 0) return data.processV2;
  return data.process.map((p) => ({
    id: p.id,
    phase: 'exploration' as const,
    phaseLabel: '',
    title: p.stage,
    teacherActivity: p.design,
    studentActivity: '',
    intent: p.secondary,
  }));
}

/** 模块完成度（进度统计用）：核心字段有值即算完成。 */
export function moduleFilled(id: LessonModuleId, data: LessonPlanData): boolean {
  switch (id) {
    case 'basic':
      return !!data.title.trim();
    case 'analysis':
      return !!data.analysis && Object.values(data.analysis).some((v) => v.trim());
    case 'objectives':
      return !!data.coreCompetencies.trim() || !!data.keyPoints.trim();
    case 'strategy':
      return (!!data.strategy && Object.values(data.strategy).some((v) => v.trim())) || !!data.teachingDesign.trim();
    case 'process':
      return processToV2(data).length > 0;
    case 'exercises':
      return !!data.exercises.trim() || (!!data.evaluation && Object.values(data.evaluation).some((v) => v.trim()));
    case 'reflection':
      return !!data.reflection.trim();
  }
}
