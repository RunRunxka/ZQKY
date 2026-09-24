'use client';
import { useRef } from 'react';
import { BarChart3, Check, FileText, PenLine, type LucideIcon } from 'lucide-react';
import {
  QUIZ_QUESTION_TYPE_LABELS,
  VISUALIZE_RENDER_LABELS,
  type CapabilityFormState,
} from '@/services/capability-catalog';

const CARD_META: Record<string, { icon: LucideIcon; label: string }> = {
  deep_question: { icon: PenLine, label: '出题设置' },
  visualize: { icon: BarChart3, label: '可视化设置' },
};

/**
 * 能力配置卡（S2）：对照参考 CapabilityConfigCard 的骨架——
 * 头部（图标 + 名称 + 已确认/必填徽标）、表单体（各能力字段）、
 * 校验错误列表、底部确认区。发送前必须确认；任何字段编辑都会使确认失效
 * （由父级在变更时重置 confirmed，对照参考 page.tsx 行为）。
 * 字段与默认值对照参考 QuizConfigPanel / VisualizeConfigPanel。
 * UX-PERF-CLOSEOUT v1：ResearchConfigPanel 随“更多能力”飞出层一并移除。
 */
export function CapabilityConfigCard({
  capability,
  forms,
  confirmed,
  errors,
  onConfirm,
  onChange,
}: {
  capability: string;
  forms: CapabilityFormState;
  confirmed: boolean;
  errors: string[];
  onConfirm(): void;
  onChange(next: CapabilityFormState): void;
}) {
  const meta = CARD_META[capability];
  if (!meta) return null;
  const MetaIcon = meta.icon;
  const hasErrors = errors.length > 0;
  return (
    <section className="chat-cap-config" aria-label={meta.label}>
      <header>
        <MetaIcon size={13} strokeWidth={1.8} />
        <span className="chat-cap-config-title">{meta.label}</span>
        {confirmed ? (
          <span className="chat-cap-config-badge confirmed">
            <Check size={10} strokeWidth={2.5} /> 已确认
          </span>
        ) : (
          <span className="chat-cap-config-badge">必填</span>
        )}
      </header>
      <div className="chat-cap-config-body">
        {capability === 'deep_question' && (
          <QuizFields
            forms={forms}
            onChange={onChange}
          />
        )}
        {capability === 'visualize' && (
          <VisualizeFields forms={forms} onChange={onChange} />
        )}
      </div>
      {hasErrors && (
        <ul className="chat-cap-config-errors">
          {errors.map((err) => (
            <li key={err}>• {err}</li>
          ))}
        </ul>
      )}
      <footer>
        <span>{confirmed ? '编辑任意字段后需重新确认。' : '确认设置后才能发送。'}</span>
        <button
          type="button"
          className="chat-cap-config-confirm"
          disabled={confirmed || hasErrors}
          onClick={onConfirm}
        >
          {confirmed ? '已确认' : '确认'}
        </button>
      </footer>
    </section>
  );
}

function QuizFields({
  forms,
  onChange,
}: {
  forms: CapabilityFormState;
  onChange(next: CapabilityFormState): void;
}) {
  const quiz = forms.deep_question;
  const fileRef = useRef<HTMLInputElement>(null);
  const set = (patch: Partial<CapabilityFormState['deep_question']>) =>
    onChange({ ...forms, deep_question: { ...quiz, ...patch } });
  return (
    <>
      <div className="chat-field-row">
        <span className="chat-field-label">出题模式</span>
        <div className="chat-field-segment" role="group" aria-label="出题模式">
          <button
            type="button"
            aria-pressed={quiz.mode === 'custom'}
            onClick={() => set({ mode: 'custom' })}
          >
            自定义
          </button>
          <button
            type="button"
            aria-pressed={quiz.mode === 'mimic'}
            onClick={() => set({ mode: 'mimic' })}
          >
            仿照试卷
          </button>
        </div>
      </div>
      {quiz.mode === 'custom' ? (
        <label className="chat-field-row">
          <span className="chat-field-label">出题主题</span>
          <input
            type="text"
            value={quiz.topic}
            placeholder="例如：二次函数的图像与性质"
            onChange={(e) => set({ topic: e.target.value })}
          />
        </label>
      ) : (
        <div className="chat-field-row">
          <span className="chat-field-label">试卷文件</span>
          <input type="text" value={quiz.paper_name} readOnly aria-label="已上传试卷文件名" placeholder="尚未上传" />
          <button type="button" className="chat-field-button" onClick={() => fileRef.current?.click()}>
            <FileText size={13} /> 上传（演示）
          </button>
          <input
            ref={fileRef}
            type="file"
            accept=".pdf,application/pdf"
            hidden
            onChange={(e) => {
              const file = e.target.files?.[0];
              if (file) set({ paper_name: file.name });
              e.target.value = '';
            }}
          />
        </div>
      )}
      <label className="chat-field-row">
        <span className="chat-field-label">题目数量</span>
        <input
          type="number"
          min={1}
          max={10}
          value={quiz.num_questions}
          onChange={(e) => set({ num_questions: Math.max(1, Math.min(10, Number(e.target.value) || 1)) })}
        />
      </label>
      <label className="chat-field-row">
        <span className="chat-field-label">难度</span>
        <select value={quiz.difficulty} onChange={(e) => set({ difficulty: e.target.value })}>
          <option value="auto">自动</option>
          <option value="easy">简单</option>
          <option value="medium">中等</option>
          <option value="hard">困难</option>
        </select>
      </label>
      <div className="chat-field-row chat-field-top">
        <span className="chat-field-label">题型（可多选，空=自动）</span>
        <div className="chat-field-chips">
          {QUIZ_QUESTION_TYPE_LABELS.map((type) => {
            const selected = quiz.question_types.includes(type.value);
            return (
              <button
                key={type.value}
                type="button"
                aria-pressed={selected}
                onClick={() =>
                  set({
                    question_types: selected
                      ? quiz.question_types.filter((t) => t !== type.value)
                      : [...quiz.question_types, type.value],
                  })
                }
              >
                {type.label}
              </button>
            );
          })}
        </div>
      </div>
    </>
  );
}

function VisualizeFields({
  forms,
  onChange,
}: {
  forms: CapabilityFormState;
  onChange(next: CapabilityFormState): void;
}) {
  const vis = forms.visualize;
  const set = (patch: Partial<CapabilityFormState['visualize']>) =>
    onChange({ ...forms, visualize: { ...vis, ...patch } });
  return (
    <>
      <label className="chat-field-row">
        <span className="chat-field-label">渲染模式</span>
        <select value={vis.render_mode} onChange={(e) => set({ render_mode: e.target.value })}>
          {VISUALIZE_RENDER_LABELS.map((item) => (
            <option key={item.value} value={item.value}>
              {item.label}
            </option>
          ))}
        </select>
      </label>
      <label className="chat-field-row">
        <span className="chat-field-label">质量</span>
        <select
          value={vis.quality}
          onChange={(e) => set({ quality: e.target.value as CapabilityFormState['visualize']['quality'] })}
        >
          <option value="low">低</option>
          <option value="medium">中</option>
          <option value="high">高</option>
        </select>
      </label>
      <label className="chat-field-row">
        <span className="chat-field-label">风格提示</span>
        <input
          type="text"
          value={vis.style_hint}
          placeholder="例如：简洁教学风格、蓝色主题（可选）"
          onChange={(e) => set({ style_hint: e.target.value })}
        />
      </label>
    </>
  );
}
