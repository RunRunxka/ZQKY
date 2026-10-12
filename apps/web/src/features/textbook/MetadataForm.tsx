'use client';

/**
 * 教材分类元数据表单（导入面板与书册「编辑分类」共用）。
 * 字段与后端 `DocumentMetadataInput` 一致：标题、学段、年级（多选，最多 3）、学科、版本、版次说明、册次。
 */

import type { DocumentMetadataInput } from '@/contracts/textbook';
import type { TaxonomyIndex } from './taxonomy';

export const EMPTY_METADATA: DocumentMetadataInput = {
  title: '',
  stageId: '',
  gradeIds: [],
  subjectId: '',
  editionId: '',
  publicationLabel: '',
  volumeLabel: '',
};

/** 后端约束：年级 1–3 个且不重复；其余必填。返回逐条原因，空数组表示通过。 */
export function metadataErrors(value: DocumentMetadataInput): string[] {
  const errors: string[] = [];
  if (!value.title.trim()) errors.push('请填写标题。');
  if (!value.stageId) errors.push('请选择学段。');
  if (value.gradeIds.length === 0) errors.push('请至少选择一个年级。');
  if (value.gradeIds.length > 3) errors.push('年级最多选择 3 个。');
  if (new Set(value.gradeIds).size !== value.gradeIds.length) errors.push('年级不允许重复。');
  if (!value.subjectId) errors.push('请选择学科。');
  if (!value.editionId) errors.push('请选择版本。');
  return errors;
}

/** 提交前归一：去空白、年级去重保序，与后端校验口径一致。 */
export function normalizeMetadata(value: DocumentMetadataInput): DocumentMetadataInput {
  return {
    title: value.title.trim(),
    stageId: value.stageId,
    gradeIds: [...new Set(value.gradeIds)],
    subjectId: value.subjectId,
    editionId: value.editionId,
    publicationLabel: value.publicationLabel.trim(),
    volumeLabel: value.volumeLabel.trim(),
  };
}

export function MetadataForm({
  value,
  onChange,
  taxonomy,
  idPrefix,
  disabled = false,
}: {
  value: DocumentMetadataInput;
  onChange: (next: DocumentMetadataInput) => void;
  taxonomy: TaxonomyIndex;
  /** 多个表单共存时保证 label 关联唯一 */
  idPrefix: string;
  disabled?: boolean;
}) {
  const field = (name: keyof DocumentMetadataInput) => `${idPrefix}-${name}`;
  const grades = taxonomy.gradesOfStage(value.stageId || null);
  const update = (patch: Partial<DocumentMetadataInput>) => onChange({ ...value, ...patch });

  return (
    <div className="textbook-metadata">
      <label className="textbook-field" htmlFor={field('title')}>
        <span>标题</span>
        <input
          id={field('title')}
          value={value.title}
          disabled={disabled}
          maxLength={200}
          placeholder="例如：人教版七年级数学上册"
          onChange={(event) => update({ title: event.target.value })}
        />
      </label>

      <label className="textbook-field" htmlFor={field('stageId')}>
        <span>学段</span>
        <select
          id={field('stageId')}
          className="space-select"
          value={value.stageId}
          disabled={disabled}
          onChange={(event) => {
            const stageId = event.target.value;
            const allowed = new Set(taxonomy.gradesOfStage(stageId).map((grade) => grade.id));
            update({
              stageId,
              gradeIds: value.gradeIds.filter((id) => allowed.has(id)),
            });
          }}
        >
          <option value="">请选择学段</option>
          {taxonomy.stages.map((stage) => (
            <option key={stage.id} value={stage.id}>
              {stage.label}
            </option>
          ))}
        </select>
      </label>

      <fieldset className="textbook-field textbook-field-wide" disabled={disabled}>
        <legend>年级（可多选，最多 3 个）</legend>
        {grades.length === 0 ? (
          <p className="textbook-hint">
            {taxonomy.ready ? '当前字典没有可用年级。' : '字典未加载，暂不能选择年级。'}
          </p>
        ) : (
          <div className="textbook-grade-options">
            {grades.map((grade) => {
              const checked = value.gradeIds.includes(grade.id);
              return (
                <label key={grade.id} className="textbook-check">
                  <input
                    type="checkbox"
                    checked={checked}
                    onChange={() => {
                      if (checked) {
                        update({ gradeIds: value.gradeIds.filter((id) => id !== grade.id) });
                        return;
                      }
                      if (value.gradeIds.length >= 3) return;
                      update({ gradeIds: [...value.gradeIds, grade.id] });
                    }}
                  />
                  {grade.label}
                </label>
              );
            })}
          </div>
        )}
      </fieldset>

      <label className="textbook-field" htmlFor={field('subjectId')}>
        <span>学科</span>
        <select
          id={field('subjectId')}
          className="space-select"
          value={value.subjectId}
          disabled={disabled}
          onChange={(event) => update({ subjectId: event.target.value })}
        >
          <option value="">请选择学科</option>
          {taxonomy.subjects.map((subject) => (
            <option key={subject.id} value={subject.id}>
              {subject.label}
            </option>
          ))}
        </select>
      </label>

      <label className="textbook-field" htmlFor={field('editionId')}>
        <span>版本</span>
        <select
          id={field('editionId')}
          className="space-select"
          value={value.editionId}
          disabled={disabled}
          onChange={(event) => update({ editionId: event.target.value })}
        >
          <option value="">请选择版本</option>
          {taxonomy.editions.map((edition) => (
            <option key={edition.id} value={edition.id}>
              {edition.label}
            </option>
          ))}
        </select>
      </label>

      <label className="textbook-field" htmlFor={field('publicationLabel')}>
        <span>版次说明</span>
        <input
          id={field('publicationLabel')}
          value={value.publicationLabel}
          disabled={disabled}
          maxLength={120}
          placeholder="例如：2024 年 6 月第 1 版"
          onChange={(event) => update({ publicationLabel: event.target.value })}
        />
      </label>

      <label className="textbook-field" htmlFor={field('volumeLabel')}>
        <span>册次</span>
        <input
          id={field('volumeLabel')}
          value={value.volumeLabel}
          disabled={disabled}
          maxLength={120}
          placeholder="例如：上册"
          onChange={(event) => update({ volumeLabel: event.target.value })}
        />
      </label>
    </div>
  );
}
