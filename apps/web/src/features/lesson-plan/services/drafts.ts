import type { DraftEnvelope, DraftRepository, LessonPlanData } from '../model/types';
const KEY = 'zhiqikeyuan:lesson-plan:v1';
export function validateData(value: unknown): asserts value is LessonPlanData {
  if (!value || typeof value !== 'object') throw new Error('教案数据格式不正确');
  const d = value as Record<string, unknown>;
  for (const key of [
    'title',
    'totalLessons',
    'currentLessonNo',
    'otherTypeText',
    'coreCompetencies',
    'keyPoints',
    'teachingDesign',
    'exercises',
    'reflection',
  ])
    if (typeof d[key] !== 'string' || (d[key] as string).length > 100000)
      throw new Error(`字段 ${key} 缺失或内容过长`);
  if ((d.title as string).length > 80 || (d.otherTypeText as string).length > 80)
    throw new Error('课题和其他课型说明最多80字');
  if (
    !Array.isArray(d.lessonTypes) ||
    d.lessonTypes.some((x) => !['new', 'review', 'exercise', 'experiment', 'other'].includes(x))
  )
    throw new Error('课型格式不正确');
  if (
    !Array.isArray(d.process) ||
    d.process.length > 100 ||
    d.process.some(
      (p) =>
        !p ||
        ['id', 'stage', 'design', 'secondary'].some(
          (k) => typeof p[k] !== 'string' || p[k].length > 100000,
        ),
    )
  )
    throw new Error('教学过程格式不正确（最多100个环节）');
  if (new Set(d.process.map((p) => p.id)).size !== d.process.length)
    throw new Error('教学环节编号重复');
  if (d.process.some((p) => p.stage.length > 120)) throw new Error('环节名称最多120字');
}
export const localDraftRepository: DraftRepository = {
  load() {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (parsed.schemaVersion !== 1) throw new Error('草稿版本不兼容，请先导出备份');
    validateData(parsed.data);
    return parsed;
  },
  save(draft) {
    localStorage.setItem(KEY, JSON.stringify(draft));
  },
};
export function makeEnvelope(data: LessonPlanData, revision: number): DraftEnvelope {
  return { schemaVersion: 1, revision, updatedAt: new Date().toISOString(), data };
}
