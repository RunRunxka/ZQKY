'use client';

import type { PracticeConstraints } from '@/contracts/b4';
import { DIFFICULTY_LABEL, QUESTION_TYPE_LABEL } from '@/contracts/question-bank';

export const defaultConstraints: PracticeConstraints = {
  count: 3, questionTypes: [], difficulties: [], includeUnknownDifficulty: false,
  excludeOriginal: true, deduplicate: true,
};
export function ConstraintsFields({ value, onChange, disabled = false }: {
  value: PracticeConstraints; onChange: (value: PracticeConstraints) => void; disabled?: boolean;
}) {
  const toggle = (field: 'questionTypes' | 'difficulties', item: string, checked: boolean) => {
    const previous = value[field] ?? [];
    onChange({ ...value, [field]: checked ? [...previous.filter((entry) => entry !== item), item] : previous.filter((entry) => entry !== item) });
  };
  return <fieldset disabled={disabled}>
    <legend>练习约束</legend>
    <label className="b4-field">题量<input aria-label="练习题量" type="number" min={1} max={100} value={value.count} onChange={(event) => onChange({ ...value, count: Number(event.target.value) })} /></label>
    <p className="b4-hint">不选题型或难度表示该维度不限；未标注难度需单独允许。缺题不会自动放宽条件。</p>
    <div className="b4-checks" aria-label="题型">
      {Object.entries(QUESTION_TYPE_LABEL).map(([type, label]) => <label key={type}><input type="checkbox" checked={(value.questionTypes ?? []).includes(type)} onChange={(event) => toggle('questionTypes', type, event.target.checked)} />{label}</label>)}
    </div>
    <div className="b4-checks" aria-label="难度">
      {Object.entries(DIFFICULTY_LABEL).filter(([difficulty]) => difficulty !== 'unspecified').map(([difficulty, label]) => <label key={difficulty}><input type="checkbox" checked={(value.difficulties ?? []).includes(difficulty)} onChange={(event) => toggle('difficulties', difficulty, event.target.checked)} />{label}</label>)}
      <label><input type="checkbox" checked={value.includeUnknownDifficulty === true} onChange={(event) => onChange({ ...value, includeUnknownDifficulty: event.target.checked })} />允许未标注难度</label>
    </div>
    <div className="b4-checks">
      <label><input type="checkbox" checked={value.excludeOriginal !== false} onChange={(event) => onChange({ ...value, excludeOriginal: event.target.checked })} />排除原测题</label>
      <label><input type="checkbox" checked={value.deduplicate !== false} onChange={(event) => onChange({ ...value, deduplicate: event.target.checked })} />排除内容重复题</label>
    </div>
  </fieldset>;
}
