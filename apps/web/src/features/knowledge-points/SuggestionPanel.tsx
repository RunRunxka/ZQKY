'use client';

/**
 * AI 候选：冻结当前聊天模型 → 提交 `POST /knowledge-suggestion-jobs`（202）→
 * 经公共任务客户端 `observeJob('knowledge', jobId, { expectedAttempt })` 观察六态 →
 * 成功后切到生成的 `source="ai"` 待确认批次走同一套确认流程。
 *
 * 纪律：
 * - **候选不是正式知识点**：界面全程标注「候选批次（待确认）」；正式表只在确认后写入；
 * - 模型在任务创建成功后冻结：中途在「模型设置」切换聊天模型不影响该任务；
 *   重试沿用同一任务（后端保留冻结输入与模型指纹），「重新发起」才用当时的当前模型；
 * - 轮询守卫 `jobId` + `attempt`，组件卸载即停（停止观察不取消任务；取消要点「取消任务」）；
 * - interrupted（无执行器在跑）解除「进行中」状态并保留已有候选，重试后按新 attempt 继续。
 */

import { useEffect, useRef, useState } from 'react';
import { RefreshCw, RotateCcw, Sparkles, StopCircle, Trash2, X } from 'lucide-react';
import type { KnowledgeMaterialInput, KnowledgePointView } from '@/contracts/knowledge';
import { loadModelCatalog } from '@/services/model-settings-api';
import { createKnowledgeSuggestionJob, listTextbookLinks } from '@/services/knowledge-points-api';
import type { ObserveJobOptions } from '@/services/workflow-jobs-api';
import { asApiError, useAsyncResource, useKnowledgeJob } from './hooks';
import {
  SUGGESTION_CLOUD_NOTICE,
  SUGGESTION_NO_DEFAULT_REASON,
  pickSuggestionChatModel,
  resolveSuggestionChatModel,
  suggestionCatalogErrorReason,
  unavailableSuggestionModel,
  type SuggestionChatModel,
} from './model-profile';
import {
  SUGGESTION_INTERRUPTED_NOTICE,
  TEXTBOOK_EVIDENCE_UNAVAILABLE_CODE,
  TEXTBOOK_EVIDENCE_UNAVAILABLE_TEXT,
  jobStateLabel,
} from './labels';

const MAX_MATERIAL_CHARS = 20000;
const MAX_INSTRUCTIONS = 2000;

export function SuggestionPanel({
  subjects,
  taxonomyReady,
  defaultSubjectId,
  selectedPoint,
  onOpenBatch,
  polling,
}: {
  subjects: { id: string; label: string }[];
  taxonomyReady: boolean;
  defaultSubjectId: string;
  selectedPoint: KnowledgePointView | null;
  onOpenBatch: (importId: string) => void;
  /** 测试注入点：透传给 `observeJob`。 */
  polling?: Pick<ObserveJobOptions, 'sleep' | 'now'>;
}) {
  const catalog = useAsyncResource(() => loadModelCatalog(), 'kp-model-catalog');
  const catalogData = catalog.state.phase === 'ready' ? catalog.state.data : null;
  const currentModel: SuggestionChatModel =
    catalog.state.phase === 'failed'
      ? unavailableSuggestionModel(
          suggestionCatalogErrorReason(catalog.state.error.code, catalog.state.error.message),
        )
      : pickSuggestionChatModel(catalogData);

  const [frozenModel, setFrozenModel] = useState<SuggestionChatModel | null>(null);
  const frozenNow =
    frozenModel && catalogData
      ? resolveSuggestionChatModel(catalogData, frozenModel.profileId)
      : null;
  const frozenStale =
    !!frozenModel && catalog.state.phase === 'ready' && frozenNow?.available !== true;
  const activeModel = frozenModel ?? currentModel;

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

  /* ---------------------------------------------------------------- 证据 */

  const [materials, setMaterials] = useState<KnowledgeMaterialInput[]>([]);
  const [materialDraft, setMaterialDraft] = useState('');
  const [usePointEvidence, setUsePointEvidence] = useState(false);
  const [instructions, setInstructions] = useState('');
  const materialSeq = useRef(0);
  const [subjectDraft, setSubjectDraft] = useState(defaultSubjectId);

  useEffect(() => {
    if (defaultSubjectId) setSubjectDraft(defaultSubjectId);
  }, [defaultSubjectId]);

  const links = useAsyncResource(
    (signal) =>
      selectedPoint
        ? listTextbookLinks(selectedPoint.id, signal).then((list) => list.items)
        : Promise.resolve([]),
    `kp-suggestion-links|${selectedPoint?.id ?? ''}`,
  );
  const evidenceLinks = links.state.phase === 'ready' ? links.state.data : [];
  const evidenceUnavailable =
    links.state.phase === 'failed' && links.state.error.code === TEXTBOOK_EVIDENCE_UNAVAILABLE_CODE;

  const subjectId = selectedPoint ? selectedPoint.subjectId : subjectDraft;
  /** 学科是服务端必填项：未选择时入口禁用并给可读原因，不猜造、不静默替换。 */
  const subjectReady = subjectId.trim() !== '';

  /* ---------------------------------------------------------------- 任务 */

  const [startError, setStartError] = useState<string | null>(null);
  const [startedNotice, setStartedNotice] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const job = useKnowledgeJob({
    polling,
    onTerminal: (view) => {
      if (view.state === 'succeeded') {
        setFrozenModel(null);
        const importId = typeof view.result?.importId === 'string' ? view.result.importId : null;
        if (importId) {
          setStartedNotice(
            `候选批次已生成（${view.result?.candidateCount ?? 0} 条候选），已切换到待确认批次。`,
          );
          onOpenBatch(importId);
        } else {
          setStartedNotice(
            '任务成功，但结果里没有批次 id：请到「表格导入」查看最新批次，不在此处编造批次。',
          );
        }
      }
    },
  });

  async function startJob() {
    if (!activeModel.available) {
      setStartError(activeModel.reason ?? SUGGESTION_NO_DEFAULT_REASON);
      return;
    }
    if (!subjectId.trim()) {
      setStartError('请选择批次学科（AI 候选需要 subjectId）。');
      return;
    }
    const evidence = usePointEvidence ? evidenceLinks : [];
    if (materials.length === 0 && evidence.length === 0) {
      setStartError('至少需要一份证据：添加资料文本，或勾选「把选中知识点的教材依据作为证据」。');
      return;
    }
    setBusy(true);
    setStartError(null);
    setStartedNotice(null);
    job.reset();
    try {
      const view = await createKnowledgeSuggestionJob({
        modelProfileId: activeModel.profileId,
        subjectId: subjectId.trim(),
        materials,
        textbookEvidence: evidence.map((link) => ({
          documentRevisionId: link.documentRevisionId,
          charStart: link.charStart,
          charEnd: link.charEnd,
        })),
        instructions: instructions.trim() || null,
      });
      setFrozenModel(activeModel);
      job.adopt(view);
    } catch (cause) {
      const error = asApiError(cause);
      setStartError(
        `发起 AI 候选失败（${error.code}）：${error.message} 没有创建任务，也没有写入候选。`,
      );
    } finally {
      setBusy(false);
    }
  }

  function addMaterial() {
    const text = materialDraft.trim();
    if (!text) {
      setStartError('资料文本不能为空。');
      return;
    }
    if (text.length > MAX_MATERIAL_CHARS) {
      setStartError(`单条资料最长 ${MAX_MATERIAL_CHARS} 个字符。`);
      return;
    }
    materialSeq.current += 1;
    setMaterials((prev) => [...prev, { id: `m${materialSeq.current}`, text }]);
    setMaterialDraft('');
    setStartError(null);
  }

  const view = job.view;
  const terminal = view
    ? ['succeeded', 'failed', 'cancelled', 'interrupted'].includes(view.state)
    : false;
  const jobError = view?.error ?? null;
  const importId = typeof view?.result?.importId === 'string' ? view.result.importId : null;
  const candidateCount =
    typeof view?.result?.candidateCount === 'number' ? view.result.candidateCount : null;

  return (
    <section className="kp-suggestion" aria-label="AI 候选">
      <header className="kp-subpanel-head">
        <h3>
          <Sparkles size={14} aria-hidden />
          AI 候选（待确认，不直接入库）
        </h3>
        <button className="space-button" onClick={catalog.reload}>
          <RefreshCw size={13} aria-hidden />
          重新读取模型配置
        </button>
      </header>

      <p className="kp-hint">
        候选经模型生成后落在 source=「ai」的待确认批次里，逐行校对并整批确认后才写入正式知识点表；
        这与「知识点」页的正式数据是两套东西。
      </p>

      {activeModel.available ? (
        <p className="kp-hint" data-testid="kp-suggestion-model">
          使用<strong>{activeModel.modelLabel}</strong>生成候选。
        </p>
      ) : (
        <p
          className="kp-hint kp-warn-text"
          role={catalog.state.phase === 'failed' ? 'alert' : 'status'}
          data-testid="kp-suggestion-model"
        >
          {activeModel.reason ?? SUGGESTION_NO_DEFAULT_REASON}
        </p>
      )}
      {frozenModel && (
        <p className="kp-hint" data-testid="kp-suggestion-frozen">
          本次任务已冻结该模型：任务未成功结束前切换聊天模型不影响它，重试沿用同一模型与输入。
        </p>
      )}
      {activeModel.available &&
        (activeModel.cloud ? (
          <p className="kp-dataflow-note" data-testid="kp-suggestion-dataflow">
            云端模型：{SUGGESTION_CLOUD_NOTICE}。
          </p>
        ) : (
          <p className="kp-hint" data-testid="kp-suggestion-dataflow">
            本机模型：资料文本不会发送到外部模型服务。
          </p>
        ))}
      {frozenStale && (
        <p className="space-banner error" role="alert">
          冻结的模型「{frozenModel?.modelLabel}」在当前模型配置里已不可用：不会自动改用其他模型；
          请到「模型设置」修复后重试（重试沿用冻结输入），或点「重新发起」用当前聊天模型。
        </p>
      )}

      <div className="kp-subpanel">
        <h4>证据（至少一份）</h4>
        <div className="kp-materials">
          {materials.map((material) => (
            <div key={material.id} className="kp-material">
              <span className="space-chip blue">{material.id}</span>
              <span className="kp-material-text">{material.text}</span>
              <button
                className="space-button danger"
                aria-label={`删除资料 ${material.id}`}
                onClick={() =>
                  setMaterials((prev) => prev.filter((item) => item.id !== material.id))
                }
              >
                <Trash2 size={13} aria-hidden />
              </button>
            </div>
          ))}
        </div>
        <label className="kp-field">
          <span className="kp-field-label">新增资料文本（教师提供的受管资料）</span>
          <textarea
            value={materialDraft}
            aria-label="新增资料文本"
            rows={3}
            maxLength={MAX_MATERIAL_CHARS}
            onChange={(event) => setMaterialDraft(event.target.value)}
          />
        </label>
        <div className="kp-actions">
          <button className="space-button" onClick={addMaterial}>
            添加资料块
          </button>
          {materials.length > 0 && (
            <button className="space-button" onClick={() => setMaterials([])}>
              <X size={13} aria-hidden />
              清空资料
            </button>
          )}
        </div>

        <div className="kp-evidence-pick">
          <label className="space-toggle">
            <input
              type="checkbox"
              checked={usePointEvidence}
              disabled={!selectedPoint || evidenceLinks.length === 0}
              aria-label="把选中知识点的教材依据作为证据"
              onChange={(event) => setUsePointEvidence(event.target.checked)}
            />
            把选中知识点的教材依据作为证据（{selectedPoint ? evidenceLinks.length : 0} 条）
          </label>
          {!selectedPoint && (
            <span className="kp-hint">先在「知识点」页选中一个知识点，才能引用它的教材依据。</span>
          )}
          {selectedPoint && evidenceUnavailable && (
            <span className="kp-hint kp-warn-text" data-testid="kp-suggestion-evidence-unavailable">
              {TEXTBOOK_EVIDENCE_UNAVAILABLE_TEXT}：现在无法引用教材依据，可用资料文本作为证据。
            </span>
          )}
          {selectedPoint && links.state.phase === 'ready' && evidenceLinks.length === 0 && (
            <span className="kp-hint">该知识点当前没有教材依据（服务端已成功读取）。</span>
          )}
        </div>

        <label className="kp-field">
          <span className="kp-field-label">生成要求（可选，≤{MAX_INSTRUCTIONS} 字）</span>
          <input
            value={instructions}
            aria-label="生成要求"
            maxLength={MAX_INSTRUCTIONS}
            onChange={(event) => setInstructions(event.target.value)}
          />
        </label>
      </div>

      <div className="kp-subpanel">
        <h4>任务</h4>
        <div className="space-meta-row">
          <span className="space-chip">学科 {subjectId || '（未选择）'}</span>
          {selectedPoint && (
            <span className="space-chip blue">随选中知识点 {selectedPoint.code}</span>
          )}
          {view && <span className="space-chip">任务 {view.jobId}</span>}
          {view && <span className="space-chip">第 {view.attempt} 次尝试</span>}
          {view && (
            <span className="space-chip blue" data-testid="kp-suggestion-state">
              {jobStateLabel(view.state)}
            </span>
          )}
          {job.observing && <span className="space-chip amber">观察中…</span>}
        </div>

        {!selectedPoint && taxonomyReady && (
          <label className="kp-field">
            <span className="kp-field-label">批次学科（无选中知识点时必填）</span>
            <select
              className="space-select"
              value={subjectDraft}
              aria-label="批次学科"
              disabled={busy}
              onChange={(event) => setSubjectDraft(event.target.value)}
            >
              <option value="">请选择学科</option>
              {subjects.map((subject) => (
                <option key={subject.id} value={subject.id}>
                  {subject.label}
                </option>
              ))}
            </select>
          </label>
        )}
        {!selectedPoint && !taxonomyReady && (
          <label className="kp-field">
            <span className="kp-field-label">批次学科（学科字典未读出，直接填 id）</span>
            <input
              value={subjectDraft}
              aria-label="批次学科"
              disabled={busy}
              onChange={(event) => setSubjectDraft(event.target.value)}
            />
          </label>
        )}

        <div className="kp-actions">
          <button
            className="space-button primary"
            disabled={busy || job.observing || !activeModel.available || !subjectReady}
            onClick={() => void startJob()}
          >
            <Sparkles size={14} aria-hidden />
            {busy ? '提交中…' : terminal || !view ? '发起 AI 候选' : '重新发起（新任务）'}
          </button>
          {view && (view.state === 'queued' || view.state === 'running') && (
            <button className="space-button danger" onClick={job.cancel}>
              <StopCircle size={14} aria-hidden />
              取消任务
            </button>
          )}
          {view && terminal && view.state !== 'succeeded' && (
            <button className="space-button" onClick={job.retry}>
              <RotateCcw size={14} aria-hidden />
              重试（沿用冻结模型）
            </button>
          )}
        </div>

        {!subjectReady && (
          <p className="kp-hint" data-testid="kp-subject-required">
            请先选择批次学科（AI 候选需要 subjectId）；不猜造学科、也不静默改用其他学科。
          </p>
        )}

        {view && (view.state === 'queued' || view.state === 'running') && (
          <p className="space-banner info" role="status">
            任务在后台执行（{jobStateLabel(view.state)}）；模型只在任务开始时被调用。
            离开本页会停止观察，但不会取消任务；要取消请点「取消任务」。
          </p>
        )}

        {view?.state === 'interrupted' && (
          <p className="space-banner error" role="alert" data-testid="kp-interrupted">
            {SUGGESTION_INTERRUPTED_NOTICE}
            ：任务没有自动重跑，已生成的候选仍保留；点「重试」按新尝试继续。
          </p>
        )}
        {view?.state === 'cancelled' && (
          <p className="space-banner info" role="status">
            任务已取消：在途未完成的候选不会写入批次；已完成的候选仍可查看。
          </p>
        )}
        {view?.state === 'failed' && (
          <p className="space-banner error" role="alert">
            任务失败{jobError ? `（${jobError.code}）` : ''}：
            {jobError?.message ?? '未提供错误说明。'}
            没有候选被写入；可点「重试」沿用冻结输入。
          </p>
        )}
        {view?.state === 'succeeded' && (
          <div className="space-banner info" role="status" data-testid="kp-suggestion-succeeded">
            <span>
              候选已生成{candidateCount !== null ? `（${candidateCount} 条）` : ''}
              {importId ? `：批次 ${importId}` : '：结果未给出批次 id'}。
            </span>
            {importId && (
              <button className="space-button" onClick={() => onOpenBatch(importId)}>
                打开候选批次
              </button>
            )}
          </div>
        )}

        {job.observationNotice && (
          <p className="space-banner info" role="status">
            {job.observationNotice}
          </p>
        )}
        {job.actionError && (
          <p className="space-banner error" role="alert">
            任务操作失败（{job.actionError.code}）：{job.actionError.message}
          </p>
        )}
        {startError && (
          <p className="space-banner error" role="alert">
            {startError}
          </p>
        )}
        {startedNotice && (
          <p className="space-banner info" role="status" data-testid="kp-suggestion-notice">
            {startedNotice}
          </p>
        )}
      </div>
    </section>
  );
}
