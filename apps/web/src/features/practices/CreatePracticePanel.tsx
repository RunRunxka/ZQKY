'use client';

/**
 * 新建练习（R8-FE 2026-10-12，对齐用户口径的三条来源，收敛为一屏切换）。
 *
 * - 来源一「学情分析报告」：选 `GET /analysis-runs` 的报告 → 显示其知识点与得分率
 *   （`GET /analysis-runs/{id}/knowledge-stats`，后端按得分率降序）→ 自动勾选目标知识点，
 *   创建后由后端按约束从已确认题库选拔固定题（`POST /practice-sets`；不存在的题不补齐、
 *   不放宽约束，缺口在编辑态由建议接口如实给出）。
 * - 来源二「教师描述」：自由文本 + 知识点多选 + 数量 + 难度 → 触发题库 AI 出题
 *   （`POST /question-generation-jobs`）→ 产出 `needs_review` 草稿，**必须到题库校对确认入库**，
 *   才会进入练习选拔；这里绝不把任务接受当成题已生成。
 * - 可组合：同一屏内两个来源都可勾选；描述的 KPs 未选报告时读 `GET /knowledge-points`。
 *
 * 不发明第三种后端：所有写入都落在归档冻结的 practice / question 通道上。
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import Link from 'next/link';
import type { AnalysisRunView, PracticeConstraints, PracticeCreateRequest, PracticeSetView } from '@/contracts/b4';
import type { Difficulty, QuestionType } from '@/contracts/question-bank';
import { QUESTION_TYPE_LABEL } from '@/contracts/question-bank';
import { b4Api } from '@/services/teaching-loop-b4-api';
import { createQuestionGenerationJob } from '@/services/question-bank-api';
import { listKnowledgePoints } from '@/services/knowledge-points-api';
import { getAnalysisKnowledgeStats } from '@/services/learning-analysis-api';
import { useModelCatalog } from '@/features/model-settings/useModelCatalog';
import { useQuestionJob } from '@/features/question-bank/jobs';
import { asApiError, useAsyncResource, useFrozenSubmission } from '@/features/assessments/hooks';
import { ApiError } from '@/services/api-client';
import { ConstraintsFields, defaultConstraints } from './ConstraintsFields';
import { ErrorNotice, JobStatusNotice, ReadNotice, SubmissionNotice, nameOrShortId, shortId, stampText } from './ui';
import type { GenerationJobView } from '@/contracts/question-bank';

const DIFFICULTY_CHOICES: Array<{ value: '' | Difficulty; label: string }> = [
  { value: '', label: '不限难度' },
  { value: 'easy', label: '基础' },
  { value: 'medium', label: '中等' },
  { value: 'hard', label: '困难' },
];

/** 报告知识点得分率（只读展示；读取失败不阻塞创建，只显示原因）。 */
function RunKnowledgeStats({ runId, knowledgePointIds }: { runId: string; knowledgePointIds: string[] }) {
  const stats = useAsyncResource((signal) => getAnalysisKnowledgeStats(runId, signal), `practice-run-stats|${runId}`);
  const rows = useMemo(() => {
    if (!stats.lastData) return null;
    const byId = new Map(stats.lastData.items.map((item) => [item.knowledgePointId, item]));
    const known = knowledgePointIds
      .map((id) => byId.get(id))
      .filter((item): item is NonNullable<typeof item> => item !== undefined);
    // 后端按得分率降序；薄弱在前 = 升序（不改数值，只调整展示顺序）。
    return [...known].sort((a, b) => a.scoreRate - b.scoreRate);
  }, [stats.lastData, knowledgePointIds]);
  if (stats.state.phase === 'loading') return <p role="status">正在读取报告知识点得分率…</p>;
  if (stats.state.phase === 'failed') {
    return (
      <p className="practices-hint">
        知识点得分率读取失败（{stats.state.error.code}：{stats.state.error.message}）；报告目标知识点仍可正常选择。
      </p>
    );
  }
  if (!rows || rows.length === 0) {
    return <p className="practices-hint">该报告没有可展示的知识点得分率；目标知识点仍按报告冻结快照选择。</p>;
  }
  return (
    <div className="practices-stats" data-testid="practices-run-stats">
      <p className="practices-hint">薄弱在前（按报告知识点得分率由低到高；得分率由后端冻结口径计算）：</p>
      <ul>
        {rows.map((item) => (
          <li key={item.knowledgePointId}>
            <span>{item.name}</span>
            <span className="practices-meta">{Math.round(item.scoreRate * 100)}%（小题 {item.questionCount}）</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export interface CreatePracticePanelProps {
  services?: typeof b4Api;
  onCreated: (view: PracticeSetView) => void;
  onLocked?: (locked: boolean) => void;
}

export function CreatePracticePanel({ services = b4Api, onCreated, onLocked }: CreatePracticePanelProps) {
  const { catalog } = useModelCatalog();
  const [useRun, setUseRun] = useState(true);
  const [useDescription, setUseDescription] = useState(false);
  const [runId, setRunId] = useState('');
  const [title, setTitle] = useState('');
  const [targets, setTargets] = useState<string[]>([]);
  const [constraints, setConstraints] = useState<PracticeConstraints>({ ...defaultConstraints });
  // 教师描述（来源二）
  const [note, setNote] = useState('');
  const [aiCount, setAiCount] = useState(5);
  const [aiDifficulty, setAiDifficulty] = useState<'' | Difficulty>('');
  const [aiTypes, setAiTypes] = useState<QuestionType[]>([]);
  const [aiTargets, setAiTargets] = useState<string[]>([]);
  const [aiNotice, setAiNotice] = useState<string | null>(null);
  const [aiError, setAiError] = useState<ApiError | null>(null);
  const [generating, setGenerating] = useState(false);
  const generation = useQuestionJob({
    onTerminal: (view: GenerationJobView) => {
      if (view.state === 'succeeded') {
        setAiNotice(
          `AI 已生成 ${view.candidateCount} 道候选题${view.importId ? `（导入批 ${shortId(view.importId)}）` : ''}：` +
            '候选题状态是 needs_review，必须到题库逐题校对确认入库，确认后才会被练习选拔采用。',
        );
      } else {
        setAiNotice(`AI 出题任务结束：${view.state}${view.errorCode ? `（${view.errorCode}）` : ''}；不会自动重试。`);
      }
    },
  });
  const submission = useFrozenSubmission<PracticeCreateRequest, PracticeSetView>();
  const runs = useAsyncResource(
    (signal) => services.listAnalysisRuns({ limit: 50 }, signal),
    'practices-create-runs',
  );
  const run: AnalysisRunView | null = useMemo(
    () => runs.lastData?.items.find((item) => item.runId === runId) ?? null,
    [runs.lastData, runId],
  );
  const runPoints = useMemo(() => {
    const points = run?.knowledgePoints ?? [];
    const seen = new Set<string>();
    return points.filter((point) => {
      if (seen.has(point.knowledgePointId)) return false;
      seen.add(point.knowledgePointId);
      return true;
    });
  }, [run]);
  /** 描述来源的知识点选择：选了报告用报告目标，否则读用户知识点库（失败如实显示，不静默为空）。 */
  const knowledge = useAsyncResource(
    (signal) => (useDescription && !run ? listKnowledgePoints({ limit: 200 }, signal) : Promise.resolve(null)),
    `practices-create-knowledge|${useDescription && !run ? 'standalone' : 'run'}`,
  );
  const descriptionPoints = useMemo(
    () => (knowledge.lastData?.items ?? []).map((item) => ({ id: item.id, name: item.name })),
    [knowledge.lastData],
  );
  const locked =
    submission.busy || submission.phase === 'unknown' || generating || generation.pending !== null;
  const alive = useRef(true);
  useEffect(() => {
    alive.current = true;
    return () => {
      alive.current = false;
    };
  }, []);
  useEffect(() => {
    onLocked?.(locked);
    return () => onLocked?.(false);
  }, [locked, onLocked]);

  // 选中报告后自动勾选其全部冻结目标知识点（教师可再取消）；换报告时重新对齐，不跨报告残留。
  useEffect(() => {
    setTargets(run ? runPoints.map((point) => point.knowledgePointId) : []);
    if (run) {
      setTitle((current) => (current.trim() ? current : `${nameOrShortId(run.paperTitle, run.runId)} 针对性练习`));
      setAiTargets((current) => (current.length > 0 ? current : runPoints.map((point) => point.knowledgePointId)));
    }
  }, [run, runPoints]);

  const readyRun = run !== null && run.reportReady && run.job.state === 'succeeded';
  const canCreate =
    readyRun && title.trim().length > 0 && targets.length > 0 && submission.phase !== 'unknown';
  const createBlockReason = !run
    ? '请选择一份学情分析报告：练习按报告冻结的目标知识点选拔题库固定题。'
    : !run.reportReady || run.job.state !== 'succeeded'
      ? '该报告尚未就绪，不能创建练习。'
      : !title.trim()
        ? '请填写练习标题。'
        : targets.length === 0
          ? '请至少选择一个目标知识点。'
          : '';

  async function create() {
    if (!run) return;
    await submission.submit(
      {
        submissionId: '',
        analysisRunId: run.runId,
        title: title.trim(),
        targetKnowledgePointIds: targets,
        constraints,
      },
      (frozen) => services.createPractice({ ...frozen.payload, submissionId: frozen.submissionId }),
    );
  }
  useEffect(() => {
    if (submission.result && alive.current) onCreated(submission.result);
    // 只在新的成功回执上回调一次；重复渲染不重复打开。
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [submission.result]);

  async function requestAiQuestions() {
    const modelProfileId = catalog?.defaultChatProfileId ?? '';
    const knowledgePointIds = run ? (aiTargets.length > 0 ? aiTargets : runPoints.map((point) => point.knowledgePointId)) : aiTargets;
    if (!modelProfileId || knowledgePointIds.length === 0) return;
    setAiNotice(null);
    setAiError(null);
    setGenerating(true);
    generation.reset();
    try {
      const view = await createQuestionGenerationJob({
        modelProfileId,
        ...(run?.subjectId ? { subjectId: run.subjectId } : {}),
        knowledgePointIds,
        ...(aiDifficulty ? { difficulty: aiDifficulty } : {}),
        ...(aiTypes.length > 0 ? { questionTypes: aiTypes } : {}),
        count: aiCount,
        instructions: note.trim() || null,
      });
      if (!alive.current) return;
      generation.adopt(view);
    } catch (cause) {
      if (alive.current) setAiError(asApiError(cause));
    } finally {
      if (alive.current) setGenerating(false);
    }
  }

  const aiKnowledgePoints = run
    ? runPoints.map((point) => ({ id: point.knowledgePointId, name: point.name }))
    : descriptionPoints;
  const aiKnowledgeUnavailable = !run && knowledge.state.phase === 'failed';

  return (
    <section className="practices-card" aria-label="新建练习" data-testid="practices-create-panel">
      <header className="practices-card-head">
        <h2>新建练习</h2>
        <p className="practices-hint">
          两条来源可在同一屏组合使用：报告决定「练什么」（目标知识点与排除原题依据），教师描述决定
          「补什么」（AI 候选题进题库，校对确认后才可用于选拔）。
        </p>
      </header>

      <div className="practices-source-switch" role="group" aria-label="练习来源">
        <label className={useRun ? 'practices-source current' : 'practices-source'}>
          <input
            type="checkbox"
            data-testid="practices-source-run"
            checked={useRun}
            onChange={(event) => {
              setUseRun(event.target.checked);
              if (!event.target.checked) setRunId('');
            }}
          />
          <span>
            <strong>学情分析报告</strong>
            <small>选报告 → 看薄弱知识点 → 创建后按约束选拔题库固定题</small>
          </span>
        </label>
        <label className={useDescription ? 'practices-source current' : 'practices-source'}>
          <input
            type="checkbox"
            data-testid="practices-source-description"
            checked={useDescription}
            onChange={(event) => setUseDescription(event.target.checked)}
          />
          <span>
            <strong>教师描述</strong>
            <small>自由文本 + 知识点 + 数量 + 难度 → AI 出题进题库（待校对）</small>
          </span>
        </label>
      </div>

      {useRun && (
        <div className="practices-subsection" data-testid="practices-run-section">
          <h3>来源一 · 学情分析报告</h3>
          <ReadNotice resource={runs} label="学情报告" />
          {runs.state.phase === 'ready' && runs.lastData?.items.length === 0 && (
            <p className="practices-hint">还没有学情报告。请先在「学情分析」完成成绩导入与报告生成；练习按报告目标选拔题目。</p>
          )}
          {runs.lastData && runs.lastData.items.length > 0 && (
            <ul className="practices-run-list" aria-label="选择学情报告">
              {runs.lastData.items.map((item) => {
                const ready = item.reportReady && item.job.state === 'succeeded';
                return (
                  <li key={item.runId}>
                    <label className={runId === item.runId ? 'current' : ''}>
                      <input
                        type="radio"
                        name="practices-run"
                        data-testid={`practices-run-${item.runId}`}
                        checked={runId === item.runId}
                        disabled={!ready}
                        onChange={() => setRunId(item.runId)}
                      />
                      <span>
                        <strong>{nameOrShortId(item.paperTitle, item.runId)}</strong>
                        <small className="practices-meta">
                          {stampText(item.createdAt)} · {ready ? '报告就绪' : '报告未就绪'}
                        </small>
                      </span>
                    </label>
                  </li>
                );
              })}
            </ul>
          )}
          {run && (
            <>
              <RunKnowledgeStats runId={run.runId} knowledgePointIds={runPoints.map((point) => point.knowledgePointId)} />
              <fieldset className="practices-fieldset">
                <legend>目标知识点（练习选拔范围）</legend>
                <div className="practices-checks" aria-label="练习目标知识点">
                  {runPoints.map((point) => (
                    <label key={point.knowledgePointId}>
                      <input
                        type="checkbox"
                        data-testid={`practices-target-${point.knowledgePointId}`}
                        checked={targets.includes(point.knowledgePointId)}
                        onChange={(event) =>
                          setTargets((previous) =>
                            event.target.checked
                              ? [...previous, point.knowledgePointId]
                              : previous.filter((id) => id !== point.knowledgePointId),
                          )
                        }
                      />
                      <span>
                        {point.name}
                        <small className="practices-meta">固定修订 {shortId(point.knowledgeRevisionId)}</small>
                      </span>
                    </label>
                  ))}
                </div>
              </fieldset>
              <label className="practices-field">
                练习标题
                <input
                  data-testid="practices-create-title"
                  maxLength={200}
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                />
              </label>
              <ConstraintsFields value={constraints} onChange={setConstraints} disabled={locked} />
            </>
          )}
          {useRun && run && createBlockReason && <p className="practices-hint" role="status">{createBlockReason}</p>}
        </div>
      )}

      {useDescription && (
        <div className="practices-subsection" data-testid="practices-description-section">
          <h3>来源二 · 教师描述（AI 出题进题库）</h3>
          <label className="practices-field">
            出题要求
            <textarea
              data-testid="practices-ai-note"
              rows={3}
              maxLength={500}
              placeholder="例如：围绕通感的表达效果出基础巩固题，贴近课本例题。"
              value={note}
              onChange={(event) => setNote(event.target.value)}
            />
          </label>
          <div className="practices-ai-row">
            <label className="practices-field">
              数量
              <input
                type="number"
                min={1}
                max={20}
                data-testid="practices-ai-count"
                value={aiCount}
                onChange={(event) => setAiCount(Math.max(1, Math.min(20, Number(event.target.value) || 5)))}
              />
            </label>
            <label className="practices-field">
              难度
              <select
                className="space-select"
                data-testid="practices-ai-difficulty"
                value={aiDifficulty}
                onChange={(event) => setAiDifficulty(event.target.value as '' | Difficulty)}
              >
                {DIFFICULTY_CHOICES.map((choice) => (
                  <option key={choice.value} value={choice.value}>
                    {choice.label}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <div className="practices-checks" aria-label="AI 出题题型">
            {Object.entries(QUESTION_TYPE_LABEL).map(([type, label]) => (
              <label key={type}>
                <input
                  type="checkbox"
                  checked={aiTypes.includes(type as QuestionType)}
                  onChange={(event) =>
                    setAiTypes((previous) =>
                      event.target.checked
                        ? [...previous, type as QuestionType]
                        : previous.filter((entry) => entry !== type),
                    )
                  }
                />
                {label}
              </label>
            ))}
          </div>
          {aiKnowledgeUnavailable && <ErrorNotice error={knowledge.state.phase === 'failed' ? knowledge.state.error : null} />}
          {aiKnowledgePoints.length > 0 ? (
            <fieldset className="practices-fieldset">
              <legend>出题知识点</legend>
              <div className="practices-checks" aria-label="AI 出题知识点">
                {aiKnowledgePoints.map((point) => (
                  <label key={point.id}>
                    <input
                      type="checkbox"
                      data-testid={`practices-ai-point-${point.id}`}
                      checked={aiTargets.includes(point.id)}
                      onChange={(event) =>
                        setAiTargets((previous) =>
                          event.target.checked ? [...previous, point.id] : previous.filter((id) => id !== point.id),
                        )
                      }
                    />
                    {point.name}
                  </label>
                ))}
              </div>
            </fieldset>
          ) : (
            <p className="practices-hint">
              {run ? '先在来源一选择报告，其目标知识点即为出题范围。' : '选择报告或先建立知识点后，才能指定出题知识点。'}
            </p>
          )}
          <div className="practices-actions">
            <button
              type="button"
              className="space-button"
              data-testid="practices-ai-generate"
              disabled={
                locked ||
                aiKnowledgePoints.length === 0 ||
                (run ? false : aiTargets.length === 0) ||
                !(catalog?.defaultChatProfileId ?? '')
              }
              onClick={() => void requestAiQuestions()}
            >
              {generating ? '正在提交…' : `AI 生成 ${aiCount} 道候选题`}
            </button>
            <span className="practices-hint">
              {catalog?.defaultChatProfileId
                ? '使用当前默认对话模型；任务重试沿用服务端冻结的输入与模型。'
                : '尚未配置默认对话模型：请先在「设置 · 模型与连接」选择默认模型。'}
            </span>
          </div>
          {aiNotice && (
            <p className="practices-hint" role="status" data-testid="practices-ai-status">
              {aiNotice}
            </p>
          )}
          <JobStatusNotice
            job={generation.view}
            pending={generation.pending !== null}
            onRetry={generation.retry}
            onCancel={generation.cancel}
          />
          <ErrorNotice error={aiError} />
          <p className="practices-hint">
            确认入库在题库完成：
            <Link href="/question-bank"> 打开题库校对 AI 候选题 </Link>
            （候选不入库就不会出现在练习选拔里）。
          </p>
        </div>
      )}

      <div className="practices-create-footer">
        <SubmissionNotice submission={submission} />
        <button
          className="space-button primary"
          data-testid="practices-create-submit"
          disabled={submission.busy || (!canCreate && submission.phase !== 'unknown')}
          onClick={() => void create()}
        >
          {submission.phase === 'unknown' ? '重试原创建练习提交' : '创建练习（按约束选拔题库固定题）'}
        </button>
        {!canCreate && submission.phase !== 'unknown' && (
          <p className="practices-hint" role="status" data-testid="practices-create-reason">
            {createBlockReason || '填写完成后即可创建。'}
          </p>
        )}
        {submission.phase === 'unknown' && (
          <p className="practices-hint" role="alert">
            上次创建的结果未知：请用同一提交标识重试；不会因重试产生第二份练习。
          </p>
        )}
      </div>
    </section>
  );
}
