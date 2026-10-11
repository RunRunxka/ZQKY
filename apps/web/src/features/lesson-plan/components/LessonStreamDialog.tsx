'use client';
import { useMemo, useRef, useState } from 'react';
import { LoaderCircle, Sparkles, X } from 'lucide-react';
import type { LessonPlanData, ProcessItemV2, ProcessPhase } from '@/contracts/lesson-plans';
import { listAnalysisRuns } from '@/services/teaching-loop-b4-api';
import { useModelCatalog } from '@/features/model-settings/useModelCatalog';
import { streamLessonModules, type LessonStreamModule } from '@/services/lesson-stream';

const MODULE_LABELS: Record<LessonStreamModule, string> = {
  analysis: '教学分析', objectives: '教学目标', strategy: '教学策略', process: '教学过程',
  exercises: '练习与作业', evaluation: '评价反馈', reflection: '教学反思',
};
const ALL_MODULES = Object.keys(MODULE_LABELS) as LessonStreamModule[];
const PHASE_ORDER: ProcessPhase[] = ['warmup', 'introduction', 'exploration', 'practice', 'conclusion'];

/** 【小节名】文本 → 字段映射（与生成指令的标签约定一致）。 */
function splitByTags(text: string, map: Record<string, string>): Record<string, string> {
  const out: Record<string, string> = {};
  const regex = /【([^】]+)】([^【]*)/g;
  let matched = false;
  for (const m of text.matchAll(regex)) {
    const field = map[m[1]!.trim()];
    if (field) {
      matched = true;
      out[field] = (out[field] ? `${out[field]}\n` : '') + m[2]!.trim();
    }
  }
  return matched ? out : { __raw: text };
}

/** 教学过程文本（「环节名 | 教师 | 学生 | 意图」，空行分段）→ processV2 行。 */
function parseProcessRows(text: string): ProcessItemV2[] {
  const rows: ProcessItemV2[] = [];
  for (const block of text.split(/\n\s*\n/)) {
    const parts = block.split('|').map((s) => s.trim());
    if (parts.length < 2 || !parts[0]) continue;
    const title = parts[0]!;
    const phase = PHASE_ORDER.find((p) => title.includes(
      { warmup: '热身', introduction: '引入', practice: '练习', conclusion: '总结', exploration: '' }[p]!,
    )) ?? 'exploration';
    rows.push({
      id: crypto.randomUUID(), phase, phaseLabel: '', title,
      teacherActivity: parts[1] ?? '', studentActivity: parts[2] ?? '', intent: parts[3] ?? '',
    });
  }
  return rows;
}

/**
 * AI 逐模块生成对话框（C3-3）：选模型/学情/知识点/要求 → 流式生成 →
 * module.done 时解析该模块文本写入编辑草稿（可撤销）；生成过程各模块状态与流式预览可见。
 */
export function LessonStreamDialog({
  data,
  onClose,
  onApply,
}: {
  data: LessonPlanData;
  onClose(): void;
  /** 模块文本解析后的局部 patch（由对话框构造，经 editor.set 入稿）。 */
  onApply(patch: Partial<LessonPlanData>): void;
}) {
  const { catalog } = useModelCatalog();
  const profiles = useMemo(() => catalog?.profiles ?? [], [catalog]);
  const defaultProfileId = catalog?.defaultChatProfileId ?? '';
  const [profileId, setProfileId] = useState('');
  const effectiveProfile = profileId || defaultProfileId;

  const [runs, setRuns] = useState<Array<{ runId: string; paperTitle: string }>>([]);
  const [analysisRunId, setAnalysisRunId] = useState('');
  const [requirements, setRequirements] = useState('');
  const [selected, setSelected] = useState<Set<LessonStreamModule>>(new Set(ALL_MODULES));

  const [running, setRunning] = useState(false);
  const [status, setStatus] = useState<Record<string, 'pending' | 'running' | 'done' | 'error'>>({});
  const [previews, setPreviews] = useState<Record<string, string>>({});
  const [errors, setErrors] = useState<string[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const buffers = useRef<Record<string, string>>({});

  async function loadRuns() {
    try {
      const page = await listAnalysisRuns({ archived: false }, undefined);
      setRuns(page.items.map((r) => ({ runId: r.runId, paperTitle: r.paperTitle })));
    } catch {
      setRuns([]);
    }
  }

  function applyModule(module: LessonStreamModule, text: string) {
    const patch: Partial<LessonPlanData> = {};
    if (module === 'analysis') {
      const current = data.analysis ?? { learning: '', textbook: '', content: '', ideological: '' };
      Object.assign(current, splitByTags(text, { 学情分析: 'learning', 教材分析: 'textbook', 教学内容: 'content', 思政资源: 'ideological' }));
      patch.analysis = { ...current };
    } else if (module === 'objectives') {
      patch.coreCompetencies = text;
    } else if (module === 'strategy') {
      const current = data.strategy ?? { designThinking: '', teachingFlow: '', methods: '' };
      Object.assign(current, splitByTags(text, { 设计思路: 'designThinking', 教学流程: 'teachingFlow', 教学手段: 'methods' }));
      patch.strategy = { ...current };
    } else if (module === 'process') {
      const rows = parseProcessRows(text);
      if (rows.length) patch.processV2 = [...(data.processV2 ?? []), ...rows];
      else patch.teachingDesign = (data.teachingDesign ? `${data.teachingDesign}\n` : '') + text;
    } else if (module === 'exercises') {
      patch.exercises = text;
    } else if (module === 'evaluation') {
      const current = data.evaluation ?? { afterClassTest: '', homework: '' };
      Object.assign(current, splitByTags(text, { 课后测试情况: 'afterClassTest', 作业情况: 'homework' }));
      patch.evaluation = { ...current };
    } else if (module === 'reflection') {
      patch.reflection = text;
    }
    onApply(patch);
  }

  async function generate() {
    if (running || !effectiveProfile || selected.size === 0) return;
    setRunning(true);
    setErrors([]);
    setStatus(Object.fromEntries([...selected].map((m) => [m, 'pending'])));
    setPreviews({});
    buffers.current = {};
    const controller = new AbortController();
    abortRef.current = controller;
    try {
      await streamLessonModules(
        {
          requestId: crypto.randomUUID(),
          modelProfileId: effectiveProfile,
          courseName: data.title,
          requirements,
          ...(analysisRunId ? { analysisRunId } : {}),
          modules: [...selected],
          signal: controller.signal,
        },
        {
          onModuleStart: (m) => setStatus((s) => ({ ...s, [m]: 'running' })),
          onModuleDelta: (m, delta) => {
            buffers.current[m] = (buffers.current[m] ?? '') + delta;
            const text = buffers.current[m]!;
            setPreviews((p) => ({ ...p, [m]: text }));
          },
          onModuleDone: (m) => {
            applyModule(m as LessonStreamModule, buffers.current[m] ?? '');
            setStatus((s) => ({ ...s, [m]: 'done' }));
          },
          onModuleError: (m, message) => {
            setStatus((s) => ({ ...s, [m]: 'error' }));
            setErrors((e) => [...e, `${MODULE_LABELS[m as LessonStreamModule] ?? m}：${message}`]);
          },
        },
      );
    } catch (error) {
      if (!(error instanceof DOMException && error.name === 'AbortError')) {
        const e = error as { code?: string; message?: string };
        setErrors((list) => [...list, e.message ?? '生成失败。']);
      }
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  }

  return (
    <div className="lesson-stream-mask" role="dialog" aria-modal="true" aria-label="AI 逐模块生成教案">
      <div className="lesson-stream-dialog">
        <header className="lesson-stream-head">
          <h3><Sparkles size={15} aria-hidden /> AI 逐模块生成（候选文本，可直接编辑）</h3>
          <button type="button" className="icon-button" aria-label="关闭" onClick={onClose}><X size={16} /></button>
        </header>
        <div className="lesson-stream-body">
          <div className="lesson-stream-config">
            <label className="lesson-field">
              <span>模型</span>
              <select value={profileId} onChange={(e) => setProfileId(e.target.value)} disabled={running}>
                <option value="">默认对话模型</option>
                {profiles.map((p) => <option key={p.id} value={p.id}>{p.displayName}</option>)}
              </select>
            </label>
            <label className="lesson-field">
              <span>学情报告（可选）</span>
              <span className="lesson-stream-run">
                <select value={analysisRunId} onChange={(e) => setAnalysisRunId(e.target.value)} disabled={running}>
                  <option value="">不使用学情</option>
                  {runs.map((r) => <option key={r.runId} value={r.runId}>{r.paperTitle}</option>)}
                </select>
                <button type="button" className="space-button" onClick={() => void loadRuns()}>刷新报告</button>
              </span>
            </label>
            <label className="lesson-field">
              <span>生成要求（可选）</span>
              <textarea rows={2} value={requirements} onChange={(e) => setRequirements(e.target.value)} disabled={running}
                placeholder="如：侧重分数运算的薄弱知识点，四环节结构" />
            </label>
            <div className="lesson-stream-modules" role="group" aria-label="生成模块">
              {ALL_MODULES.map((m) => (
                <label key={m} className={selected.has(m) ? 'checked' : ''}>
                  <input
                    type="checkbox"
                    checked={selected.has(m)}
                    disabled={running}
                    onChange={(e) => {
                      const next = new Set(selected);
                      if (e.target.checked) next.add(m); else next.delete(m);
                      setSelected(next);
                    }}
                  />
                  {MODULE_LABELS[m]}
                </label>
              ))}
            </div>
            <div className="lesson-stream-actions">
              <button
                type="button"
                className="space-button primary"
                disabled={running || !effectiveProfile || selected.size === 0}
                onClick={() => void generate()}
              >
                {running ? <LoaderCircle size={13} className="chat-tool-spin" aria-hidden /> : <Sparkles size={13} aria-hidden />}
                {running ? '生成中…' : '开始生成'}
              </button>
              {running && (
                <button type="button" className="space-button" onClick={() => abortRef.current?.abort()}>停止</button>
              )}
            </div>
            {errors.length > 0 && (
              <div className="lesson-stream-errors" role="alert">
                {errors.map((e, i) => <p key={i}>{e}</p>)}
              </div>
            )}
          </div>
          <div className="lesson-stream-progress" aria-label="生成进度">
            {Object.entries(previews).length === 0 && <p className="b4-meta">生成的各模块文本会在这里流式显示，完成后自动填入对应表格（可撤销）。</p>}
            {ALL_MODULES.filter((m) => previews[m]).map((m) => (
              <section key={m} className="lesson-stream-preview" data-status={status[m] ?? 'pending'}>
                <h4>{MODULE_LABELS[m]}
                  <span className="lesson-stream-state">
                    {status[m] === 'running' && <LoaderCircle size={11} className="chat-tool-spin" aria-hidden />}
                    {status[m] === 'done' && '已填入'}
                    {status[m] === 'error' && '失败'}
                  </span>
                </h4>
                <pre>{previews[m]}</pre>
              </section>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
