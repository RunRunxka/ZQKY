'use client';
import {
  ArrowUp,
  ArrowDown,
  Plus,
  Check,
  FileText,
  Route,
  Trash2,
  GripVertical,
} from 'lucide-react';
import { useLessonEditor } from '../model/EditorContext';
import { sections } from '../model/sections';
import { Field } from '@/components/ui/Field';
import { lessonTypeLabels } from '../model/types';
export function FormPanel() {
  const { data, set, notice, updateText, updateProcess, reorder } = useLessonEditor();
  return (
    <>
      <section className="form-section" id="field-basic">
        <div className="form-section-heading">
          <span className="section-icon">
            <FileText size={18} />
          </span>
          <div>
            <h2>基本信息</h2>
            <p>从课题开始，搭好这节课的框架。</p>
          </div>
        </div>
        <Field label="课题" hint="必填">
          <input
            aria-label="课题"
            maxLength={80}
            placeholder="例如：荷塘月色"
            value={data.title}
            onChange={(e) => updateText('title', e.target.value)}
          />
        </Field>
        <div className="field-pair">
          <Field label="本课题总课时">
            <div className="input-suffix">
              <input
                aria-label="本课题总课时"
                type="number"
                min="1"
                max="99"
                value={data.totalLessons}
                onChange={(e) => updateText('totalLessons', e.target.value)}
              />
              <span>课时</span>
            </div>
          </Field>
          <Field label="本节课">
            <div className="input-suffix">
              <input
                aria-label="本节课"
                type="number"
                min="1"
                max="99"
                value={data.currentLessonNo}
                onChange={(e) => updateText('currentLessonNo', e.target.value)}
              />
              <span>课时</span>
            </div>
          </Field>
        </div>
        {(+data.currentLessonNo > +data.totalLessons ||
          +data.totalLessons < 1 ||
          +data.currentLessonNo < 1) && (
          <p className="validation-message">请检查课时：至少为1，本节课不能超过总课时。</p>
        )}
        <div className="field">
          <span className="field-label">
            课型<small>可多选</small>
          </span>
          <div className="lesson-types">
            {Object.entries(lessonTypeLabels).map(([type, label]) => (
              <label
                className={`type-chip ${data.lessonTypes.includes(type as keyof typeof lessonTypeLabels) ? 'checked' : ''}`}
                key={type}
              >
                <input
                  type="checkbox"
                  checked={data.lessonTypes.includes(type as keyof typeof lessonTypeLabels)}
                  onChange={(e) =>
                    set({
                      lessonTypes: e.target.checked
                        ? [...data.lessonTypes, type as keyof typeof lessonTypeLabels]
                        : data.lessonTypes.filter((t) => t !== type),
                    })
                  }
                />
                <span className="chip-checkbox">
                  {data.lessonTypes.includes(type as keyof typeof lessonTypeLabels) && (
                    <Check size={11} />
                  )}
                </span>
                {label}
              </label>
            ))}
          </div>
        </div>
        {data.lessonTypes.includes('other') && (
          <Field label="其他课型说明">
            <input
              maxLength={80}
              value={data.otherTypeText}
              onChange={(e) => set({ otherTypeText: e.target.value })}
            />
          </Field>
        )}
      </section>
      {sections
        .filter((s) => 'field' in s)
        .slice(0, 3)
        .map((s) => (
          <section className="form-section" id={`field-${s.id}`} key={s.id}>
            <div className="form-section-heading">
              <span className="section-icon">
                <s.icon size={18} />
              </span>
              <div>
                <h2>{s.label}</h2>
                <p>
                  {s.id === 'core'
                    ? '这节课，你希望学生获得什么？'
                    : s.id === 'key'
                      ? '明确课堂重点，找到学习突破口。'
                      : '记录板书思路、教学方法与组织方式。'}
                </p>
              </div>
            </div>
            {'field' in s && (
              <>
                <textarea
                  aria-label={s.label}
                  rows={s.id === 'core' ? 7 : 5}
                  value={data[s.field]}
                  placeholder={`填写${s.label}…`}
                  onChange={(e) => updateText(s.field, e.target.value)}
                />
                <div className="textarea-meta">
                  <span>支持换行，内容自动撑开</span>
                  <span>{data[s.field].length} 字</span>
                </div>
              </>
            )}
          </section>
        ))}
      <section className="form-section" id="field-process">
        <div className="form-section-heading">
          <span className="section-icon">
            <Route size={18} />
          </span>
          <div>
            <h2>教学过程</h2>
            <p>串联教学环节，记录二次备课。</p>
          </div>
          <span className="small-badge">{data.process.length} 个环节</span>
        </div>
        {data.process.map((item, i) => (
          <div className="process-editor" key={item.id}>
            <div className="process-editor-top">
              <GripVertical size={15} />
              <span>环节 {i + 1}</span>
              <div className="process-row-actions">
                <button
                  className="icon-button"
                  aria-label={`上移环节${i + 1}`}
                  disabled={i === 0}
                  onClick={() => reorder(i, -1)}
                >
                  <ArrowUp size={14} />
                </button>
                <button
                  className="icon-button"
                  aria-label={`下移环节${i + 1}`}
                  disabled={i === data.process.length - 1}
                  onClick={() => reorder(i, 1)}
                >
                  <ArrowDown size={14} />
                </button>
                <button
                  className="icon-button danger"
                  aria-label={`删除环节${i + 1}`}
                  onClick={() => {
                    set({ process: data.process.filter((p) => p.id !== item.id) });
                    notice('环节已删除，可点击撤销恢复');
                  }}
                >
                  <Trash2 size={14} />
                </button>
              </div>
            </div>
            <Field label="环节名称">
              <input
                maxLength={120}
                value={item.stage}
                onChange={(e) => updateProcess(item.id, { stage: e.target.value })}
              />
            </Field>
            <Field label="教学设计">
              <textarea
                rows={4}
                value={item.design}
                onChange={(e) => updateProcess(item.id, { design: e.target.value })}
              />
            </Field>
            <Field label="二次备课">
              <textarea
                rows={2}
                placeholder="记录调整思路或课堂观察…"
                value={item.secondary}
                onChange={(e) => updateProcess(item.id, { secondary: e.target.value })}
              />
            </Field>
          </div>
        ))}
        <button
          className="add-stage"
          disabled={data.process.length >= 100}
          onClick={() =>
            set({
              process: [
                ...data.process,
                {
                  id: crypto.randomUUID(),
                  stage: `教学环节 ${data.process.length + 1}`,
                  design: '',
                  secondary: '',
                },
              ],
            })
          }
        >
          <Plus size={16} />
          添加教学环节
        </button>
      </section>
      {sections
        .filter((s) => 'field' in s)
        .slice(3)
        .map((s) => (
          <section className="form-section" id={`field-${s.id}`} key={s.id}>
            <div className="form-section-heading">
              <span className="section-icon">
                <s.icon size={18} />
              </span>
              <div>
                <h2>{s.label}</h2>
                <p>
                  {s.id === 'reflection'
                    ? '课后回顾，为下一次课堂留点启发。'
                    : '让课堂所学，在练习中得到巩固。'}
                </p>
              </div>
            </div>
            {'field' in s && (
              <textarea
                aria-label={s.label}
                rows={5}
                value={data[s.field]}
                placeholder={
                  s.id === 'reflection' ? '可以课后再来补充…' : '填写课堂练习与课后作业…'
                }
                onChange={(e) => updateText(s.field, e.target.value)}
              />
            )}
          </section>
        ))}
    </>
  );
}
