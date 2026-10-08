'use client';

/**
 * AI 补题入口（TEACHING-LOOP B3 · F10-QB）。
 *
 * 语义边界（界面必须显式说明）：
 * - `202` 只代表任务被接受；结果必须经统一任务视图观察（六态 + `attempt`）——
 *   轮询仍是 `queued` 就仍是排队中，绝不显示成功；
 * - 模型在**点击那一刻**冻结为当前聊天模型的 profile id；重试由服务端沿用冻结输入与模型
 *   指纹（界面不换模型重发）；
 * - 取消是协作式的：发布前取消 = 零批次、零草稿；发布后的批次不受影响；
 * - 补题产物是 `needs_review` 的 AI 候选草稿（`extraction_method=ai` + 草稿关联 source=ai），
 *   必须走既有校对 → 人工确认链，**永不自动入库**。
 */

import { useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { RefreshCw, Sparkles } from 'lucide-react';
import type { Difficulty, GenerationJobView, QuestionType } from '@/contracts/question-bank';
import { DIFFICULTY_LABEL, QUESTION_TYPE_LABEL } from '@/contracts/question-bank';
import { isJobTerminal } from '@/contracts/teaching-loop';
import { loadModelCatalog } from '@/services/model-settings-api';
import { createQuestionGenerationJob } from '@/services/question-bank-api';
import { ErrorNotice } from './ErrorNotice';
import {
  GENERATION_CANCELLED_NOTICE,
  GENERATION_INTERRUPTED_NOTICE,
  GENERATION_RETRY_SEMANTICS,
  GENERATION_SUGGESTION_SEMANTICS,
  generationFailureText,
} from './generation-notice';
import { useAsyncResource, asApiError } from './hooks';
import { useQuestionJob } from './jobs';
import { organizeStateChipClass, organizeStateLabel } from './labels';
import { KnowledgePointChecklist } from './KnowledgePointFields';
import {
  ORGANIZER_CLOUD_NOTICE,
  QUESTION_MODEL_SETTINGS_HREF,
  pickOrganizerChatModel,
  resolveOrganizerChatModel,
  unavailableOrganizerModel,
  type OrganizerChatModel,
} from './model-profile';
import type { ObserveJobOptions } from '@/services/workflow-jobs-api';
import type { TaxonomyIndex } from './taxonomy';

const QUESTION_TYPES = Object.keys(QUESTION_TYPE_LABEL) as QuestionType[];
const DIFFICULTIES = Object.keys(DIFFICULTY_LABEL) as Difficulty[];
const MAX_INSTRUCTIONS = 2000;

export interface GenerationPanelProps {
  taxonomy: TaxonomyIndex;
  onClose: () => void;
  /** 任务成功发布候选批次后的入口（跳到校对页）。 */
  onOpenImport: (importId: string) => void;
  /** 任务成功发布候选批次后通知父级（批次列表需要刷新）。 */
  onPublished?: () => void;
  /** 测试注入点：透传给任务观察的等待实现与计时来源（生产不传）。 */
  polling?: Pick<ObserveJobOptions, 'sleep' | 'now'>;
}

export function GenerationPanel({
  taxonomy,
  onClose,
  onOpenImport,
  onPublished,
  polling,
}: GenerationPanelProps) {
  const [subjectId, setSubjectId] = useState('');
  const [knowledgePointIds, setKnowledgePointIds] = useState<string[]>([]);
  const [questionTypes, setQuestionTypes] = useState<QuestionType[]>([]);
  const [count, setCount] = useState(3);
  const [difficulty, setDifficulty] = useState<Difficulty>('unspecified');
  const [instructions, setInstructions] = useState('');
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const catalog = useAsyncResource(() => loadModelCatalog(), 'qb-generation-model');
  const catalogData = catalog.state.phase === 'ready' ? catalog.state.data : null;
  const currentModel: OrganizerChatModel = useMemo(() => {
    if (catalog.state.phase === 'failed') {
      const error = catalog.state.error;
      return unavailableOrganizerModel(`读取模型配置失败（${error.code}）：${error.message}`);
    }
    return pickOrganizerChatModel(catalogData);
  }, [catalog.state, catalogData]);

  /** 点击时冻结的模型快照：任务未成功结束前重试沿用同一个 profile id，不因聊天模型被切换而改。 */
  const [frozenModel, setFrozenModel] = useState<OrganizerChatModel | null>(null);
  const frozenNow = useMemo(
    () =>
      frozenModel && catalogData
        ? resolveOrganizerChatModel(catalogData, frozenModel.profileId)
        : null,
    [frozenModel, catalogData],
  );
  const frozenStale = !!frozenModel && catalog.state.phase === 'ready' && frozenNow?.available !== true;
  const activeModel = frozenModel ?? currentModel;
  /** 冻结模型与当前可用模型不同时，给出显式的「改用当前聊天模型」出口（绝不自动替换）。 */
  const canSwitchModel =
    !!frozenModel && currentModel.available && currentModel.profileId !== frozenModel.profileId;

  /** 显式改用当前可用模型：清掉冻结快照，不自动重发（下一次点击才调用模型）。 */
  function useCurrentModelInstead() {
    setFrozenModel(null);
    setSubmitError(null);
  }

  const job = useQuestionJob({
    onTerminal: (view) => {
      if (view.state === 'succeeded') {
        setFrozenModel(null);
        if (view.importId) onPublished?.();
      }
    },
    polling,
  });

  // 目录变化（在「模型设置」改完默认模型回到本页）重新读取：只读目录，不调用模型
  const reloadCatalog = catalog.reload;
  useEffect(() => {
    const refresh = () => reloadCatalog();
    window.addEventListener('focus', refresh);
    window.addEventListener('model-catalog-changed', refresh);
    return () => {
      window.removeEventListener('focus', refresh);
      window.removeEventListener('model-catalog-changed', refresh);
    };
  }, [reloadCatalog]);
  const view = job.view;
  const terminal = view ? isJobTerminal(view.state) : false;
  const running = view !== null && !terminal;

  function toggleType(type: QuestionType, checked: boolean) {
    setQuestionTypes((prev) =>
      checked ? [...prev.filter((item) => item !== type), type] : prev.filter((item) => item !== type),
    );
  }

  async function submit() {
    if (!activeModel.available) {
      setSubmitError(activeModel.reason ?? '当前聊天模型不可用：请到「模型设置」选择默认问答模型。');
      return;
    }
    const trimmedSubject = subjectId.trim();
    if (!trimmedSubject && knowledgePointIds.length === 0) {
      setSubmitError('请先选择学科或至少一个知识点：没有它们就无法约束命题与关联。');
      return;
    }
    if (!Number.isInteger(count) || count < 1 || count > 10) {
      setSubmitError('补题数量需要是 1–10 的整数。');
      return;
    }
    setSubmitting(true);
    setSubmitError(null);
    setFrozenModel(activeModel);
    try {
      const created: GenerationJobView = await createQuestionGenerationJob({
        // 云端聊天模型 profile id（题库 AI 不使用本机模型）；绝不是模型名、不是空串
        modelProfileId: activeModel.profileId,
        subjectId: trimmedSubject,
        knowledgePointIds,
        questionTypes,
        difficulty,
        count,
        instructions: instructions.trim() || null,
      });
      // 任务已接受：清空上一轮视图（旧观察与旧重试的迟到响应一律失效，B2-RV10）后接管
      job.reset();
      job.adopt(created);
      if (created.state === 'succeeded') setFrozenModel(null);
    } catch (cause) {
      const error = asApiError(cause);
      setSubmitError(
        `AI 补题未创建任务（${error.code}）：${generationFailureText(
          error.code,
          error.message,
        )} 没有调用模型，也没有生成任何草稿。`,
      );
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="qb-panel qb-generation" data-testid="qb-generation-panel">
      <p className="qb-hint">{GENERATION_SUGGESTION_SEMANTICS}</p>

      {catalog.state.phase === 'failed' ? (
        <ErrorNotice
          label="模型配置读取失败"
          error={catalog.state.error}
          onRetry={catalog.reload}
        />
      ) : activeModel.available ? (
        <p className="qb-hint" data-testid="qb-generation-model">
          使用<strong>{activeModel.modelLabel}</strong>补题。
        </p>
      ) : (
        <p className="qb-hint qb-warn-text" role="status" data-testid="qb-generation-model">
          {activeModel.reason ?? '聊天配置还没有默认模型：请到「模型设置」选择默认问答模型后再补题。'}
          <Link className="space-button" href={QUESTION_MODEL_SETTINGS_HREF}>
            去设置默认问答模型
          </Link>
        </p>
      )}

      {activeModel.available &&
        (activeModel.cloud ? (
          <p className="qb-dataflow-note" data-testid="qb-generation-dataflow">
            云端模型：{ORGANIZER_CLOUD_NOTICE}。
          </p>
        ) : (
          <p className="qb-hint" data-testid="qb-generation-dataflow">
            本机模型：命题请求不会发送到外部模型服务。
          </p>
        ))}

      {frozenModel && !terminal && (
        <p className="qb-hint" data-testid="qb-generation-frozen">
          本次任务已冻结该模型：{GENERATION_RETRY_SEMANTICS}
        </p>
      )}
      {frozenStale && (
        <p className="space-banner error" role="alert">
          冻结的模型「{frozenModel?.modelLabel}」在当前模型配置里已不可用：不会自动改用其他模型；
          请到「模型设置」修复后重新发起补题
          {canSwitchModel ? '，或点「改用当前聊天模型」再发起。' : '。'}
        </p>
      )}

      <div className="qb-form-grid">
        <label className="qb-field" htmlFor="qb-generation-subject">
          学科
          {taxonomy.ready ? (
            <select
              id="qb-generation-subject"
              className="space-select"
              value={subjectId}
              disabled={running}
              onChange={(event) => {
                setSubjectId(event.target.value);
                // 学科变化：已选知识点可能属于旧学科，清空避免跨学科提交（后端会 422）
                setKnowledgePointIds([]);
              }}
            >
              <option value="">未指定</option>
              {taxonomy.subjects.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.label}
                </option>
              ))}
            </select>
          ) : (
            <input
              id="qb-generation-subject"
              value={subjectId}
              placeholder="学科 id"
              disabled={running}
              onChange={(event) => {
                setSubjectId(event.target.value);
                setKnowledgePointIds([]);
              }}
            />
          )}
        </label>
        <label className="qb-field" htmlFor="qb-generation-count">
          题数（1–10）
          <input
            id="qb-generation-count"
            type="number"
            min={1}
            max={10}
            value={count}
            disabled={running}
            onChange={(event) => setCount(Number(event.target.value))}
          />
        </label>
        <label className="qb-field" htmlFor="qb-generation-difficulty">
          难度
          <select
            id="qb-generation-difficulty"
            className="space-select"
            value={difficulty}
            disabled={running}
            onChange={(event) => setDifficulty(event.target.value as Difficulty)}
          >
            {DIFFICULTIES.map((item) => (
              <option key={item} value={item}>
                {DIFFICULTY_LABEL[item]}
              </option>
            ))}
          </select>
        </label>
      </div>

      <fieldset className="qb-fieldset">
        <legend>知识点（只列当前学科的在用知识点）</legend>
        <KnowledgePointChecklist
          idPrefix="qb-generation"
          subjectId={subjectId.trim()}
          selected={knowledgePointIds}
          disabled={running}
          onChange={setKnowledgePointIds}
        />
        <p className="qb-hint">
          不选知识点时按学科命题：候选不会有正式知识点关联，需要在校对时人工补充。
        </p>
      </fieldset>

      <fieldset className="qb-fieldset">
        <legend>题型</legend>
        <div className="qb-radio-list">
          {QUESTION_TYPES.map((type) => (
            <label key={type} className="qb-check">
              <input
                type="checkbox"
                checked={questionTypes.includes(type)}
                disabled={running}
                onChange={(event) => toggleType(type, event.target.checked)}
              />
              {QUESTION_TYPE_LABEL[type]}
            </label>
          ))}
        </div>
        <p className="qb-hint">不勾选表示不限题型，由模型按题干判断。</p>
      </fieldset>

      <label className="qb-field" htmlFor="qb-generation-instructions">
        补充要求（可选，最多 {MAX_INSTRUCTIONS} 字）
        <textarea
          id="qb-generation-instructions"
          className="qb-textarea"
          rows={3}
          maxLength={MAX_INSTRUCTIONS}
          value={instructions}
          disabled={running}
          placeholder="例如：只考有理数的加减法，避免负数乘除。"
          onChange={(event) => setInstructions(event.target.value)}
        />
      </label>
      <p className="qb-hint">
        本版补题不附带教材原文/证据材料：模型只依据所选知识点、学科与补充要求命题；
        任何网址或文件路径都会被后端拒绝。
      </p>

      {submitError && (
        <p className="space-banner error" role="alert" data-testid="qb-generation-error">
          {submitError}
        </p>
      )}
      {job.actionError && (
        <p className="space-banner error" role="alert" data-testid="qb-generation-error">
          任务操作失败（{job.actionError.code}）：{job.actionError.message}
        </p>
      )}
      {job.observationNotice && (
        <p className="space-banner info" role="status" data-testid="qb-generation-observe-notice">
          {job.observationNotice}
        </p>
      )}

      {view && (
        <div className="qb-subpanel" data-testid="qb-generation-job">
          <div className="space-meta-row">
            <span className={organizeStateChipClass(view.state)} data-testid="qb-generation-state">
              {organizeStateLabel(view.state)}
            </span>
            {typeof view.attempt === 'number' && (
              <span className="space-chip" data-testid="qb-generation-attempt">
                第 {view.attempt} 次尝试
              </span>
            )}
            {view.jobId && <span className="space-chip">任务 {view.jobId}</span>}
            {job.observing && <span className="space-chip blue">正在观察</span>}
          </div>

          {(view.state === 'queued' || view.state === 'running') && (
            <p className="space-banner info" role="status" data-testid="qb-generation-pending">
              任务已提交（{organizeStateLabel(view.state)}）：本页会持续观察直到服务端给出终态；
              排队中不等于成功，离开页面只停止观察、不会取消任务。
            </p>
          )}

          {view.state === 'failed' && (
            <p className="space-banner error" role="alert" data-testid="qb-generation-failed">
              补题失败（{view.errorCode ?? '未知错误码'}）：
              {generationFailureText(view.errorCode)}
              没有生成任何草稿；可点「重试补题」按服务端冻结的输入重试。
            </p>
          )}
          {view.state === 'cancelled' && (
            <p className="space-banner info" role="status" data-testid="qb-generation-cancelled">
              {GENERATION_CANCELLED_NOTICE}
            </p>
          )}
          {view.state === 'interrupted' && (
            <p className="space-banner error" role="alert" data-testid="qb-generation-interrupted">
              {GENERATION_INTERRUPTED_NOTICE}
            </p>
          )}
          {view.state === 'succeeded' && (
            <div className="space-banner info" role="status" data-testid="qb-generation-succeeded">
              补题完成：生成 {view.candidateCount} 道待校对候选草稿。
              {view.importId ? (
                <>
                  <div className="qb-actions">
                    <button
                      className="space-button primary"
                      data-testid="qb-generation-import"
                      onClick={() => onOpenImport(view.importId as string)}
                    >
                      打开候选批次校对
                    </button>
                  </div>
                  <p className="qb-hint">
                    候选在批次 {view.importId} 里，状态为待校对；AI 候选不会自动入库，
                    必须人工逐题校对后确认。
                  </p>
                </>
              ) : (
                <p className="qb-hint" role="alert">
                  任务已成功但服务端没有返回候选批次 id：请到「导入批次」列表里核对最新批次，
                  不要凭空假定已生成内容。
                </p>
              )}
            </div>
          )}

          <div className="qb-actions">
            {running && (
              <button
                className="space-button"
                data-testid="qb-generation-cancel"
                disabled={job.pending !== null}
                onClick={job.cancel}
              >
                {job.pending === 'cancel' ? '正在取消…' : '取消任务'}
              </button>
            )}
            {(view.state === 'failed' ||
              view.state === 'interrupted' ||
              view.state === 'cancelled') && (
              <button
                className="space-button"
                data-testid="qb-generation-retry"
                disabled={job.pending !== null || job.observing}
                onClick={job.retry}
              >
                {job.pending === 'retry' ? '正在重试…' : '重试补题'}
              </button>
            )}
            {terminal && (
              <button
                className="space-button"
                data-testid="qb-generation-reset"
                disabled={job.pending !== null}
                onClick={job.reset}
              >
                清空任务状态
              </button>
            )}
            <button
              className="space-button"
              data-testid="qb-generation-new-task"
              disabled={running}
              onClick={job.reset}
            >
              发起新任务
            </button>
          </div>
          <p className="qb-hint">{GENERATION_RETRY_SEMANTICS}</p>
        </div>
      )}

      <div className="qb-actions">
        <button
          className="space-button primary"
          data-testid="qb-generation-submit"
          disabled={submitting || running || !activeModel.available}
          onClick={() => void submit()}
        >
          <Sparkles size={14} aria-hidden />
          {submitting ? '提交中…' : '开始补题'}
        </button>
        <button className="space-button" disabled={running} onClick={catalog.reload}>
          <RefreshCw size={13} aria-hidden />
          重新读取模型配置
        </button>
        {/* 与 ReviewWorkspace 的 AI 整理同一模式：冻结模型与当前可用模型不同时给显式出口 */}
        {frozenModel && canSwitchModel && (
          <button
            className="space-button"
            data-testid="qb-generation-switch-model"
            disabled={running || submitting}
            onClick={useCurrentModelInstead}
          >
            改用当前聊天模型
          </button>
        )}
        <button className="space-button" onClick={onClose}>
          关闭
        </button>
      </div>
    </div>
  );
}
