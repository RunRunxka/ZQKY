'use client';
/**
 * 中栏模块表单（按内置模块的表格字段结构）。
 *
 * - 教学目标用 `readObjectives/writeObjectives` 行编解码（知识/能力/思政），旧整体文本
 *   退回单框编辑——不猜测、不重排、不丢字；
 * - 教学过程行支持增删、上下移动、阶段（phase）与阶段小标题；
 * - 自定义模块编辑标题与正文。
 */
import { ArrowDown, ArrowUp, Plus, Trash2 } from 'lucide-react';
import type { LessonPlanData, ProcessItemV2, ProcessPhase } from '@/contracts/lesson-plans';
import { PHASE_LABELS, PROCESS_PHASES, emptyProcessV2Row } from '../model/lesson-data';
import { builtinDef, type LessonModuleEntry } from '../model/modules';
import { readKeyPoints, readObjectives, writeKeyPoints, writeObjectives } from '../model/objectives';

export interface ModuleEditorProps {
  entry: LessonModuleEntry;
  data: LessonPlanData;
  setData: (patch: Partial<LessonPlanData>) => void;
  updateData: (updater: (data: LessonPlanData) => LessonPlanData) => void;
  renameCustomModule: (id: string, label: string) => void;
  setCustomBody: (id: string, body: string) => void;
}

function TextField({
  id,
  label,
  value,
  placeholder,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  placeholder?: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="lw-field" htmlFor={id}>
      <span>{label}</span>
      <input
        id={id}
        data-testid={`lw-field-${id}`}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function TextArea({
  id,
  label,
  value,
  rows = 4,
  placeholder,
  hint,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  rows?: number;
  placeholder?: string;
  hint?: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="lw-field" htmlFor={id}>
      <span>
        {label}
        {hint && <small>{hint}</small>}
      </span>
      <textarea
        id={id}
        data-testid={`lw-field-${id}`}
        rows={rows}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function ProcessRowEditor({
  row,
  index,
  count,
  onChange,
  onMove,
  onRemove,
}: {
  row: ProcessItemV2;
  index: number;
  count: number;
  onChange: (patch: Partial<ProcessItemV2>) => void;
  onMove: (delta: number) => void;
  onRemove: () => void;
}) {
  return (
    <li className="lw-process-row" data-testid={`lw-process-row-${index}`}>
      <div className="lw-process-row-head">
        <strong>环节 {index + 1}</strong>
        <span className="lw-process-row-actions">
          <button
            type="button"
            className="lw-icon-button"
            aria-label={`上移环节 ${index + 1}`}
            disabled={index === 0}
            onClick={() => onMove(-1)}
          >
            <ArrowUp size={14} />
          </button>
          <button
            type="button"
            className="lw-icon-button"
            aria-label={`下移环节 ${index + 1}`}
            disabled={index === count - 1}
            onClick={() => onMove(1)}
          >
            <ArrowDown size={14} />
          </button>
          <button
            type="button"
            className="lw-icon-button danger"
            aria-label={`删除环节 ${index + 1}`}
            onClick={onRemove}
          >
            <Trash2 size={14} />
          </button>
        </span>
      </div>
      <div className="lw-process-row-grid">
        <label className="lw-field" htmlFor={`lw-process-phase-${index}`}>
          <span>阶段</span>
          <select
            id={`lw-process-phase-${index}`}
            value={row.phase}
            onChange={(event) => onChange({ phase: event.target.value as ProcessPhase })}
          >
            {PROCESS_PHASES.map((phase) => (
              <option key={phase} value={phase}>
                {PHASE_LABELS[phase]}
              </option>
            ))}
          </select>
        </label>
        <TextField
          id={`lw-process-phase-label-${index}`}
          label="阶段小标题"
          value={row.phaseLabel}
          placeholder="留空则用阶段名"
          onChange={(value) => onChange({ phaseLabel: value })}
        />
        <TextField
          id={`lw-process-title-${index}`}
          label="教学环节"
          value={row.title}
          onChange={(value) => onChange({ title: value })}
        />
      </div>
      <TextArea
        id={`lw-process-teacher-${index}`}
        label="教师活动"
        value={row.teacherActivity}
        rows={3}
        onChange={(value) => onChange({ teacherActivity: value })}
      />
      <TextArea
        id={`lw-process-student-${index}`}
        label="学生活动"
        value={row.studentActivity}
        rows={3}
        onChange={(value) => onChange({ studentActivity: value })}
      />
      <TextArea
        id={`lw-process-intent-${index}`}
        label="设计意图"
        value={row.intent}
        rows={2}
        onChange={(value) => onChange({ intent: value })}
      />
    </li>
  );
}

export function ModuleEditor({
  entry,
  data,
  setData,
  updateData,
  renameCustomModule,
  setCustomBody,
}: ModuleEditorProps) {
  const def = entry.kind === 'builtin' ? builtinDef(entry.builtinId ?? '') : undefined;

  if (entry.kind === 'custom') {
    return (
      <section className="lw-card" aria-label={`编辑模块：${entry.label}`} data-testid="lw-module-editor">
        <header className="lw-card-head">
          <h2>自定义模块</h2>
          <span className="lw-card-hint">预览中追加一张单独的表格</span>
        </header>
        <TextField
          id="lw-custom-title"
          label="模块标题"
          value={entry.label}
          onChange={(value) => renameCustomModule(entry.id, value)}
        />
        <TextArea
          id="lw-custom-body"
          label="模块正文"
          value={entry.body ?? ''}
          rows={10}
          placeholder="填写这一节的内容，预览与导出会照此排入新表格。"
          onChange={(value) => setCustomBody(entry.id, value)}
        />
      </section>
    );
  }

  const basic = data.basic!;
  const analysis = data.analysis!;
  const strategy = data.strategy!;
  const evaluation = data.evaluation!;
  const objectives = readObjectives(data.coreCompetencies);
  const keyPoints = readKeyPoints(data.keyPoints);
  const rows = data.processV2 ?? [];

  return (
    <section className="lw-card" aria-label={`编辑模块：${entry.label}`} data-testid="lw-module-editor">
      <header className="lw-card-head">
        <h2>{def ? `${def.no}、${def.label}` : entry.label}</h2>
        <span className="lw-card-hint">{def?.hint}</span>
      </header>

      {entry.builtinId === 'basic' && (
        <>
          <TextField
            id="lw-basic-courseName"
            label="课程名称"
            value={basic.courseName}
            onChange={(value) => setData({ basic: { ...basic, courseName: value } })}
          />
          <div className="lw-field-grid">
            <TextField
              id="lw-basic-audience"
              label="授课对象"
              value={basic.audience}
              onChange={(value) => setData({ basic: { ...basic, audience: value } })}
            />
            <TextField
              id="lw-basic-teachingTime"
              label="授课时间"
              value={basic.teachingTime}
              onChange={(value) => setData({ basic: { ...basic, teachingTime: value } })}
            />
            <TextField
              id="lw-basic-location"
              label="授课地点"
              value={basic.location}
              onChange={(value) => setData({ basic: { ...basic, location: value } })}
            />
            <TextField
              id="lw-basic-chapter"
              label="教学章节"
              value={basic.chapter}
              onChange={(value) => setData({ basic: { ...basic, chapter: value } })}
            />
          </div>
          <p className="lw-note">封面另用：授课教师、授课学时（导出时自动排入封面表）。</p>
          <div className="lw-field-grid">
            <TextField
              id="lw-basic-teacher"
              label="授课教师（封面）"
              value={basic.teacher}
              onChange={(value) => setData({ basic: { ...basic, teacher: value } })}
            />
            <TextField
              id="lw-basic-hours"
              label="授课学时（封面）"
              value={basic.hours}
              onChange={(value) => setData({ basic: { ...basic, hours: value } })}
            />
          </div>
        </>
      )}

      {entry.builtinId === 'analysis' && (
        <>
          <TextArea
            id="lw-analysis-learning"
            label="学情分析"
            value={analysis.learning}
            hint="可从学情报告一键带入"
            onChange={(value) => setData({ analysis: { ...analysis, learning: value } })}
          />
          <TextArea
            id="lw-analysis-textbook"
            label="教材分析"
            value={analysis.textbook}
            onChange={(value) => setData({ analysis: { ...analysis, textbook: value } })}
          />
          <TextArea
            id="lw-analysis-content"
            label="教学内容"
            value={analysis.content}
            onChange={(value) => setData({ analysis: { ...analysis, content: value } })}
          />
          <TextArea
            id="lw-analysis-ideological"
            label="思政资源"
            value={analysis.ideological}
            onChange={(value) => setData({ analysis: { ...analysis, ideological: value } })}
          />
        </>
      )}

      {entry.builtinId === 'objectives' && (
        <>
          {objectives.structured ? (
            <>
              <TextArea
                id="lw-objectives-knowledge"
                label="知识"
                value={objectives.rows.knowledge}
                rows={3}
                onChange={(value) => {
                  const view = { ...objectives, structured: true };
                  view.rows = { ...view.rows, knowledge: value };
                  setData({ coreCompetencies: writeObjectives(view) });
                }}
              />
              <TextArea
                id="lw-objectives-ability"
                label="能力"
                value={objectives.rows.ability}
                rows={3}
                onChange={(value) => {
                  const view = { ...objectives, structured: true };
                  view.rows = { ...view.rows, ability: value };
                  setData({ coreCompetencies: writeObjectives(view) });
                }}
              />
              <TextArea
                id="lw-objectives-ideological"
                label="思政"
                value={objectives.rows.ideological}
                rows={3}
                onChange={(value) => {
                  const view = { ...objectives, structured: true };
                  view.rows = { ...view.rows, ideological: value };
                  setData({ coreCompetencies: writeObjectives(view) });
                }}
              />
              {objectives.other.length > 0 && (
                <p className="lw-note" data-testid="lw-objectives-other">
                  另有 {objectives.other.length} 行未归类内容，保留在目标字段并随导出一起带上。
                </p>
              )}
            </>
          ) : (
            <TextArea
              id="lw-objectives-legacy"
              label="教学目标（整体文本）"
              value={data.coreCompetencies}
              rows={6}
              hint="按「知识：/能力：/思政：」分行后可切换为三行编辑"
              onChange={(value) => setData({ coreCompetencies: value })}
            />
          )}
          <TextArea
            id="lw-objectives-key"
            label="教学重点"
            value={keyPoints.key}
            rows={2}
            onChange={(value) =>
              setData({ keyPoints: writeKeyPoints({ ...keyPoints, key: value }) })
            }
          />
          <TextArea
            id="lw-objectives-difficulty"
            label="教学难点"
            value={keyPoints.difficulty}
            rows={2}
            onChange={(value) =>
              setData({ keyPoints: writeKeyPoints({ ...keyPoints, difficulty: value }) })
            }
          />
        </>
      )}

      {entry.builtinId === 'strategy' && (
        <>
          <TextArea
            id="lw-strategy-designThinking"
            label="设计思路"
            value={strategy.designThinking}
            onChange={(value) => setData({ strategy: { ...strategy, designThinking: value } })}
          />
          <TextArea
            id="lw-strategy-teachingFlow"
            label="教学流程"
            value={strategy.teachingFlow}
            hint="可含图（当前按文本排入模板）"
            onChange={(value) => setData({ strategy: { ...strategy, teachingFlow: value } })}
          />
          <TextArea
            id="lw-strategy-methods"
            label="教学手段"
            value={strategy.methods}
            onChange={(value) => setData({ strategy: { ...strategy, methods: value } })}
          />
          <TextArea
            id="lw-strategy-teachingDesign"
            label="教学设计（板书/思路）"
            value={data.teachingDesign}
            rows={3}
            onChange={(value) => setData({ teachingDesign: value })}
          />
        </>
      )}

      {entry.builtinId === 'process' && (
        <>
          <p className="lw-note">
            每个环节一行；预览中按阶段插入小标题行（如「课程引入」）。
          </p>
          <ul className="lw-process-list">
            {rows.map((row, index) => (
              <ProcessRowEditor
                key={row.id}
                row={row}
                index={index}
                count={rows.length}
                onChange={(patch) =>
                  updateData((current) => ({
                    ...current,
                    processV2: (current.processV2 ?? []).map((item) =>
                      item.id === row.id ? { ...item, ...patch } : item,
                    ),
                  }))
                }
                onMove={(delta) =>
                  updateData((current) => {
                    const list = [...(current.processV2 ?? [])];
                    const from = list.findIndex((item) => item.id === row.id);
                    const to = from + delta;
                    if (from < 0 || to < 0 || to >= list.length) return current;
                    const [item] = list.splice(from, 1);
                    list.splice(to, 0, item);
                    return { ...current, processV2: list };
                  })
                }
                onRemove={() =>
                  updateData((current) => ({
                    ...current,
                    processV2: (current.processV2 ?? []).filter((item) => item.id !== row.id),
                  }))
                }
              />
            ))}
          </ul>
          <button
            type="button"
            className="lw-button"
            data-testid="lw-process-add"
            onClick={() =>
              updateData((current) => ({
                ...current,
                processV2: [...(current.processV2 ?? []), emptyProcessV2Row()],
              }))
            }
          >
            <Plus size={15} aria-hidden />
            添加教学环节
          </button>
        </>
      )}

      {entry.builtinId === 'evaluation' && (
        <>
          <TextArea
            id="lw-evaluation-exercises"
            label="练习与作业"
            value={data.exercises}
            onChange={(value) => setData({ exercises: value })}
          />
          <TextArea
            id="lw-evaluation-afterClassTest"
            label="课后测试情况"
            value={evaluation.afterClassTest}
            onChange={(value) => setData({ evaluation: { ...evaluation, afterClassTest: value } })}
          />
          <TextArea
            id="lw-evaluation-homework"
            label="作业情况"
            value={evaluation.homework}
            onChange={(value) => setData({ evaluation: { ...evaluation, homework: value } })}
          />
        </>
      )}

      {entry.builtinId === 'reflection' && (
        <TextArea
          id="lw-reflection"
          label="教学反思"
          value={data.reflection}
          rows={8}
          placeholder="目标达成度 / 教学特色 / 改进方向"
          onChange={(value) => setData({ reflection: value })}
        />
      )}
    </section>
  );
}
