'use client';
import { Plus, Trash2 } from 'lucide-react';
import type { LessonPlanData, ProcessItemV2, ProcessPhase } from '@/contracts/lesson-plans';
import { lessonTypeLabels } from '../model/types';
import { processToV2, type LessonModuleId } from '../model/modules';

const PHASE_LABELS: Record<ProcessPhase, string> = {
  warmup: '课前热身', introduction: '课程引入', exploration: '深入研讨', practice: '练习巩固', conclusion: '总结提升',
};

/**
 * 三栏式中栏（C3-2）：按左侧选中模块切换对应编辑表单；全部写经 editor 的 set/updateText，
 * 持久化与撤销/重做沿用既有 store。教学过程编辑三列（教师/学生活动 + 设计意图）。
 */
export function ModuleEditor({
  data,
  selected,
  onSet,
  onAddProcess,
  onUpdateProcess,
  onRemoveProcess,
}: {
  data: LessonPlanData;
  selected: LessonModuleId;
  onSet(patch: Partial<LessonPlanData>): void;
  onAddProcess(): void;
  onUpdateProcess(id: string, patch: Partial<ProcessItemV2>): void;
  onRemoveProcess(id: string): void;
}) {
  const basic = data.basic ?? { courseName: '', teacher: '', audience: '', hours: '', teachingTime: '', location: '', chapter: '' };
  const analysis = data.analysis ?? { learning: '', textbook: '', content: '', ideological: '' };
  const strategy = data.strategy ?? { designThinking: '', teachingFlow: '', methods: '' };
  const evaluation = data.evaluation ?? { afterClassTest: '', homework: '' };
  const rows = processToV2(data);

  return (
    <div className="lesson-modeditor">
      {selected === 'basic' && (
        <>
          <Field label="课题" value={data.title} onChange={(v) => onSet({ title: v })} />
          <div className="lesson-form-grid">
            <Field label="课程名称" value={basic.courseName} onChange={(v) => onSet({ basic: { ...basic, courseName: v } })} />
            <Field label="授课教师" value={basic.teacher} onChange={(v) => onSet({ basic: { ...basic, teacher: v } })} />
            <Field label="授课对象" value={basic.audience} onChange={(v) => onSet({ basic: { ...basic, audience: v } })} />
            <Field label="授课学时" value={basic.hours} onChange={(v) => onSet({ basic: { ...basic, hours: v } })} />
            <Field label="授课时间" value={basic.teachingTime} onChange={(v) => onSet({ basic: { ...basic, teachingTime: v } })} />
            <Field label="授课地点" value={basic.location} onChange={(v) => onSet({ basic: { ...basic, location: v } })} />
          </div>
          <Field label="教学章节" value={basic.chapter} onChange={(v) => onSet({ basic: { ...basic, chapter: v } })} multiline />
          <div className="lesson-form-grid">
            <Field label="本课题总课时" value={data.totalLessons} onChange={(v) => onSet({ totalLessons: v })} />
            <Field label="本节课" value={data.currentLessonNo} onChange={(v) => onSet({ currentLessonNo: v })} />
          </div>
          <div className="lesson-form-checks" role="group" aria-label="课型">
            {(Object.keys(lessonTypeLabels) as Array<keyof typeof lessonTypeLabels>).map((t) => (
              <label key={t}>
                <input
                  type="checkbox"
                  checked={data.lessonTypes.includes(t)}
                  onChange={(e) => onSet({ lessonTypes: e.target.checked ? [...data.lessonTypes, t] : data.lessonTypes.filter((x) => x !== t) })}
                />
                {lessonTypeLabels[t]}
              </label>
            ))}
          </div>
        </>
      )}
      {selected === 'analysis' && (
        <>
          <Field label="学情分析" value={analysis.learning} onChange={(v) => onSet({ analysis: { ...analysis, learning: v } })} multiline />
          <Field label="教材分析" value={analysis.textbook} onChange={(v) => onSet({ analysis: { ...analysis, textbook: v } })} multiline />
          <Field label="教学内容" value={analysis.content} onChange={(v) => onSet({ analysis: { ...analysis, content: v } })} multiline />
          <Field label="思政资源" value={analysis.ideological} onChange={(v) => onSet({ analysis: { ...analysis, ideological: v } })} multiline />
        </>
      )}
      {selected === 'objectives' && (
        <>
          <Field label="核心素养目标" value={data.coreCompetencies} onChange={(v) => onSet({ coreCompetencies: v })} multiline rows={7} />
          <Field label="教学重、难点" value={data.keyPoints} onChange={(v) => onSet({ keyPoints: v })} multiline rows={6} />
        </>
      )}
      {selected === 'strategy' && (
        <>
          <Field label="教学设计" value={data.teachingDesign} onChange={(v) => onSet({ teachingDesign: v })} multiline />
          <Field label="教学流程" value={strategy.teachingFlow} onChange={(v) => onSet({ strategy: { ...strategy, teachingFlow: v } })} multiline />
          <Field label="设计思路（v2）" value={strategy.designThinking} onChange={(v) => onSet({ strategy: { ...strategy, designThinking: v } })} multiline />
          <Field label="教学手段" value={strategy.methods} onChange={(v) => onSet({ strategy: { ...strategy, methods: v } })} multiline />
        </>
      )}
      {selected === 'process' && (
        <div className="lesson-process-editor">
          <div className="lesson-process-toolbar">
            <span className="b4-meta">三列过程：教师活动 / 学生活动 / 设计意图；空表时预览沿用旧「教学过程」字段。</span>
            <button type="button" className="space-button" onClick={onAddProcess}>
              <Plus size={13} aria-hidden /> 添加环节
            </button>
          </div>
          {rows.map((row, index) => (
            <fieldset key={row.id} className="lesson-process-row">
              <legend>环节 {index + 1}</legend>
              <div className="lesson-form-grid">
                <label className="lesson-field">
                  阶段
                  <select
                    value={row.phase}
                    onChange={(e) => onUpdateProcess(row.id, { phase: e.target.value as ProcessPhase })}
                  >
                    {(Object.keys(PHASE_LABELS) as ProcessPhase[]).map((p) => (
                      <option key={p} value={p}>{PHASE_LABELS[p]}</option>
                    ))}
                  </select>
                </label>
                <Field label="环节名称" value={row.title} onChange={(v) => onUpdateProcess(row.id, { title: v })} />
              </div>
              <Field label="教师活动" value={row.teacherActivity} onChange={(v) => onUpdateProcess(row.id, { teacherActivity: v })} multiline />
              <Field label="学生活动" value={row.studentActivity} onChange={(v) => onUpdateProcess(row.id, { studentActivity: v })} multiline />
              <Field label="设计意图" value={row.intent} onChange={(v) => onUpdateProcess(row.id, { intent: v })} multiline />
              <button
                type="button"
                className="lesson-process-remove"
                aria-label={`删除环节 ${index + 1}`}
                onClick={() => onRemoveProcess(row.id)}
              >
                <Trash2 size={13} aria-hidden /> 删除本环节
              </button>
            </fieldset>
          ))}
          {rows.length === 0 && <p className="b4-meta">还没有教学环节；点「添加环节」开始，或在对话里让 AI 生成。</p>}
        </div>
      )}
      {selected === 'exercises' && (
        <>
          <Field label="练习与作业" value={data.exercises} onChange={(v) => onSet({ exercises: v })} multiline />
          <Field label="课后测试情况" value={evaluation.afterClassTest} onChange={(v) => onSet({ evaluation: { ...evaluation, afterClassTest: v } })} multiline />
          <Field label="作业情况" value={evaluation.homework} onChange={(v) => onSet({ evaluation: { ...evaluation, homework: v } })} multiline />
        </>
      )}
      {selected === 'reflection' && (
        <Field label="教学反思" value={data.reflection} onChange={(v) => onSet({ reflection: v })} multiline rows={10} />
      )}
    </div>
  );
}

function Field({
  label, value, onChange, multiline = false, rows = 3,
}: {
  label: string;
  value: string;
  onChange(value: string): void;
  multiline?: boolean;
  rows?: number;
}) {
  return (
    <label className="lesson-field">
      <span>{label}</span>
      {multiline ? (
        <textarea value={value} rows={rows} onChange={(e) => onChange(e.target.value)} />
      ) : (
        <input type="text" value={value} onChange={(e) => onChange(e.target.value)} />
      )}
    </label>
  );
}
