/**
 * 字典（学段/年级/学科/版本）到可见标签的索引（题库模块本地副本）。
 * 未知 id 一律返回原 id 本身：不猜造名称、不静默丢失原始标识。
 * 字典读取失败时 `ready=false`，表单降级为直接填写 id，不假装有选项。
 */

import type { TextbookTaxonomy } from '@/contracts/textbook';

export interface TaxonomyIndex {
  ready: boolean;
  stages: TextbookTaxonomy['stages'];
  grades: TextbookTaxonomy['grades'];
  subjects: TextbookTaxonomy['subjects'];
  editions: TextbookTaxonomy['editions'];
  stageLabel: (id: string | null | undefined) => string;
  gradeLabel: (id: string | null | undefined) => string;
  subjectLabel: (id: string | null | undefined) => string;
  editionLabel: (id: string | null | undefined) => string;
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
  };
}
