/**
 * 字典（学段/年级/学科/版本）到可见标签的索引。
 * 未知 id 一律返回原 id 本身：不猜造名称、不翻译成「未知」后丢失原始标识。
 */

import type {
  EditionView,
  GradeView,
  StageView,
  SubjectView,
  TextbookTaxonomy,
} from '@/contracts/textbook';

export interface TaxonomyIndex {
  /** 字典是否已就绪（未就绪时筛选条只显示提示，不阻塞列表）。 */
  ready: boolean;
  stages: StageView[];
  grades: GradeView[];
  subjects: SubjectView[];
  editions: EditionView[];
  stageLabel: (id: string | null | undefined) => string;
  gradeLabel: (id: string | null | undefined) => string;
  subjectLabel: (id: string | null | undefined) => string;
  editionLabel: (id: string | null | undefined) => string;
  /** 多年级（书册可跨年级）→ 顿号分隔；空数组返回空串。 */
  gradeLabels: (ids: readonly string[]) => string;
  gradesOfStage: (stageId: string | null | undefined) => GradeView[];
}

const EMPTY: TextbookTaxonomy = { stages: [], grades: [], subjects: [], editions: [] };

export function buildTaxonomyIndex(taxonomy: TextbookTaxonomy | null): TaxonomyIndex {
  const source = taxonomy ?? EMPTY;
  const stages = new Map(source.stages.map((item) => [item.id, item.label]));
  const grades = new Map(source.grades.map((item) => [item.id, item.label]));
  const subjects = new Map(source.subjects.map((item) => [item.id, item.label]));
  const editions = new Map(source.editions.map((item) => [item.id, item.label]));

  const labelOf = (map: Map<string, string>, id: string | null | undefined): string =>
    id ? (map.get(id) ?? id) : '';

  return {
    ready: taxonomy !== null,
    stages: source.stages,
    grades: source.grades,
    subjects: source.subjects,
    editions: source.editions,
    stageLabel: (id) => labelOf(stages, id),
    gradeLabel: (id) => labelOf(grades, id),
    subjectLabel: (id) => labelOf(subjects, id),
    editionLabel: (id) => labelOf(editions, id),
    gradeLabels: (ids) =>
      ids
        .map((id) => labelOf(grades, id))
        .filter((label) => label.length > 0)
        .join('、'),
    gradesOfStage: (stageId) =>
      stageId ? source.grades.filter((grade) => grade.stageId === stageId) : source.grades,
  };
}
