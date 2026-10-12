'use client';

/**
 * 练习草稿编辑（R8-FE 2026-10-12，语义取自归档 `features/practices/PracticeEditor.tsx`）。
 *
 * 归档语义（本页沿用，不发明新写入通道）：
 * - 练习草稿保存 = `PATCH /practice-sets/{id}/draft`（CAS `expectedRevision` + 冻结 `submissionId`）；
 *   结果未知时**只能重试原包**，期间编辑锁定，避免产生第二份提交；
 * - 「获取题库选拔建议」= `POST /practice-sets/{id}/suggestions`，只读地把已确认题库按约束
 *   选拔为候选；教师**显式采用**才成为计分叶，AI/后端选择绝不自动写入草稿；
 * - 逐题题干/选项/答案/解析/难度的内容编辑走题库的草稿→确认链（本题库页），练习侧只编辑
 *   选择与计分结构（归档 `_active_refs` 要求题目身份与内容哈希不变）；
 * - 审核 = `POST /practice-sets/{id}/review`：冻结题目、计分叶、材料、知识点与答案；
 *   审核后当前修订只读，继续修改需「基于审核版本建立新草稿」（`POST /revisions`）。
 *
 * 未保存稿按练习集独立保留在本机（`session.ts`），刷新/关闭后可恢复；恢复不会自动保存或审核。
 */

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import type {
  PracticeDraftItem,
  PracticeNode,
  PracticeReviewRequest,
  PracticeSetView,
  PracticeSuggestion,
  PracticeSuggestions,
} from '@/contracts/b4';
import type { Difficulty, RichContentV2 } from '@/contracts/question-bank';
import { b4Api } from '@/services/teaching-loop-b4-api';
import { getQuestionAsset } from '@/services/question-bank-api';
import { asApiError, useFrozenSubmission } from '@/features/assessments/hooks';
import { ApiError } from '@/services/api-client';
import { ANSWER_STATE_LABEL, difficultyBadgeClass, difficultyLabel } from '@/features/question-bank/labels';
import { ConstraintsFields } from './ConstraintsFields';
import { itemFromSuggestion, moveItem, renumber, withNode } from './draft';
import {
  initialPracticeSession,
  readPracticeSession,
  writePracticeSession,
  type PracticeSaveContent,
  type PracticeSession,
} from './session';
import { ErrorNotice, RichReview, SubmissionNotice, nameOrShortId, shortId } from './ui';

export interface PracticeEditorProps {
  view: PracticeSetView;
  services?: typeof b4Api;
  onSaved: (view: PracticeSetView) => void;
  onLocked?: (locked: boolean) => void;
  /** 新建后首次进入时的自动选拔（只读建议，仍需显式采用）。 */
  autoSuggest?: boolean;
}

interface Candidate {
  suggestion: PracticeSuggestion;
  difficulty: Difficulty | null;
}

export function PracticeEditor({
  view,
  services = b4Api,
  onSaved,
  onLocked,
  autoSuggest = false,
}: PracticeEditorProps) {
  // 初值直接取服务端基线（而不是空列表）：首帧就没有「0 题」的假过渡，
  // 恢复稿只在挂载后覆盖它（见会话装载 effect）。
  const [items, setItems] = useState<PracticeDraftItem[]>(() => structuredClone(view.currentRevision.draftItems));
  const [constraints, setConstraints] = useState(() => structuredClone(view.currentRevision.constraints));
  const [serverRevision, setServerRevision] = useState(view.revision);
  const [dirty, setDirty] = useState(false);
  const [cacheReady, setCacheReady] = useState(false);
  const [cacheError, setCacheError] = useState('');
  const cacheBlocked = useRef(false);
  const [suggestions, setSuggestions] = useState<PracticeSuggestions | null>(null);
  const [candidates, setCandidates] = useState<Record<string, Candidate>>({});
  const [suggesting, setSuggesting] = useState(false);
  const [suggestionError, setSuggestionError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState('');
  const [confirmReview, setConfirmReview] = useState(false);
  const [newRevisionBusy, setNewRevisionBusy] = useState(false);
  const [newRevisionError, setNewRevisionError] = useState<ApiError | null>(null);
  /** 恢复稿里带着的未确认结果操作（保存或审核）：只能原包重试，不能换标识重做。 */
  const [restoredOperation, setRestoredOperation] = useState<'save' | 'review' | null>(null);
  const [replaying, setReplaying] = useState(false);
  const [replayError, setReplayError] = useState<ApiError | null>(null);
  const alive = useRef(true);
  const suggestBusy = useRef(false);
  const session = useRef<PracticeSession>(initialPracticeSession(view));
  const save = useFrozenSubmission<PracticeSaveContent, PracticeSetView>();
  const review = useFrozenSubmission<PracticeReviewRequest, PracticeSetView>();
  const reviewState = view.currentRevision.state;
  const reviewed = reviewState === 'reviewed';
  const baselineTaken = useRef(false);

  const pendingUnknown = save.phase === 'unknown' || review.phase === 'unknown' || restoredOperation !== null;
  const locked = !cacheReady || cacheBlocked.current || reviewed || pendingUnknown || review.busy;

  const targets = useMemo(
    () => view.currentRevision.targetKnowledgePoints.map((point) => point.knowledgePointId),
    [view.currentRevision.targetKnowledgePoints],
  );
  /** 覆盖口径与后端 review 一致：只统计有计分叶（units>0）的节点知识点。 */
  const coverage = useMemo(() => {
    const covered = new Set<string>();
    items.forEach((item) =>
      item.itemStructure.nodes.forEach((node) => {
        if (!node.isScored) return;
        const scored = node.maxScore !== null && node.maxScore !== '' && Number(node.maxScore) > 0;
        if (!scored) return;
        (node.knowledgePointIds ?? []).forEach((id) => covered.add(id));
      }),
    );
    return covered;
  }, [items]);
  const missingTargets = targets.filter((id) => !coverage.has(id));
  const countGap = (constraints.count ?? 0) - items.length;
  const reviewReady = !dirty && items.length > 0 && countGap === 0 && missingTargets.length === 0;

  const persist = useCallback((): boolean => {
    if (cacheBlocked.current || !cacheReady) return false;
    try {
      writePracticeSession(localStorage, session.current);
      setCacheError('');
      return true;
    } catch (cause) {
      setCacheError(`恢复缓存写入失败：${(cause as Error).message}。输入保留，发送已暂停。`);
      return false;
    }
  }, [cacheReady]);

  /* ------------------------------------------------ 会话装载：恢复本机稿或对齐服务端基线 */
  useEffect(() => {
    alive.current = true;
    cacheBlocked.current = false;
    setCacheReady(false);
    setCacheError('');
    setSuggestions(null);
    setCandidates({});
    setNotice('');
    setConfirmReview(false);
    setRestoredOperation(null);
    setReplayError(null);
    save.release();
    review.release();
    session.current = initialPracticeSession(view);
    setItems(session.current.items);
    setConstraints(session.current.constraints);
    setServerRevision(session.current.serverRevision);
    setDirty(false);
    try {
      const restored = readPracticeSession(localStorage, view.practiceSetId);
      if (restored && (restored.dirty || restored.saveOperation || restored.reviewOperation || restored.identityConflict)) {
        session.current = restored;
        setItems(structuredClone(restored.items));
        setConstraints(structuredClone(restored.constraints));
        setServerRevision(restored.serverRevision);
        setDirty(restored.dirty);
        setRestoredOperation(restored.saveOperation ? 'save' : restored.reviewOperation ? 'review' : null);
        setNotice('已恢复此练习的独立本机稿；恢复不会自动保存或审核，未知保存/审核须重试原包。');
      }
      setCacheReady(true);
    } catch (cause) {
      cacheBlocked.current = true;
      setCacheError(`恢复稿读取失败：${(cause as Error).message}。原字节未覆盖，保存已暂停。`);
    }
    return () => {
      alive.current = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view.practiceSetId, view.currentRevision.practiceRevisionId]);

  /* ------------------------------------------------ 服务端基线推进：无本地改动才对齐 */
  useEffect(() => {
    const current = session.current;
    if (!cacheReady || cacheBlocked.current) return;
    if (current.dirty || current.saveOperation || current.reviewOperation || current.identityConflict) return;
    if (view.revision >= current.serverRevision) {
      session.current = { ...initialPracticeSession(view), editGeneration: current.editGeneration };
      setItems(session.current.items);
      setConstraints(session.current.constraints);
      setServerRevision(view.revision);
      setDirty(false);
    }
  }, [view, cacheReady]);

  useEffect(() => {
    const leave = (event: BeforeUnloadEvent) => {
      if (session.current.dirty || session.current.saveOperation || session.current.reviewOperation) {
        persist();
        event.preventDefault();
        event.returnValue = '';
      }
    };
    const hide = () => {
      if (session.current.dirty || session.current.saveOperation || session.current.reviewOperation) persist();
    };
    window.addEventListener('beforeunload', leave);
    window.addEventListener('pagehide', hide);
    return () => {
      window.removeEventListener('beforeunload', leave);
      window.removeEventListener('pagehide', hide);
    };
  }, [persist]);

  useEffect(() => {
    onLocked?.(save.busy || review.busy || pendingUnknown);
    return () => onLocked?.(false);
  }, [save.busy, review.busy, pendingUnknown, onLocked]);

  function edit(next: PracticeDraftItem[]) {
    session.current = {
      ...session.current,
      editGeneration: session.current.editGeneration + 1,
      dirty: true,
      items: structuredClone(next),
    };
    setDirty(true);
    setItems(next);
    persist();
  }

  function changeConstraints(value: typeof constraints) {
    session.current = {
      ...session.current,
      editGeneration: session.current.editGeneration + 1,
      dirty: true,
      constraints: structuredClone(value),
    };
    setDirty(true);
    setConstraints(value);
    setSuggestions(null);
    persist();
  }

  /* ------------------------------------------------ 题库选拔建议（只读候选，显式采用） */
  const suggest = useCallback(
    async (constraintsOverride?: typeof constraints) => {
      if (suggestBusy.current) return;
      suggestBusy.current = true;
      setSuggesting(true);
      setSuggestionError(null);
      const generation = session.current.editGeneration;
      try {
        const result = await services.suggestPractice(view.practiceSetId, {
          expectedRevision: session.current.serverRevision,
          constraints: structuredClone(constraintsOverride ?? session.current.constraints),
        });
        if (!alive.current) return;
        if (session.current.editGeneration !== generation) {
          setNotice('约束或选题已变化，旧请求的建议未采用，请重新获取建议。');
        } else {
          setSuggestions(result);
          setCandidates((previous) => {
            const next = { ...previous };
            result.items.forEach((item) => {
              next[item.questionRevisionId] = {
                suggestion: item,
                difficulty: (item.difficulty as Difficulty | null) ?? null,
              };
            });
            return next;
          });
        }
      } catch (cause) {
        if (alive.current) setSuggestionError(asApiError(cause));
      } finally {
        if (alive.current) {
          suggestBusy.current = false;
          setSuggesting(false);
        }
      }
    },
    [services, view.practiceSetId],
  );

  // 新建后的首次进入：草稿为空、未审核、未采纳任何题 → 自动做一次只读选拔，教师仍需显式采用。
  useEffect(() => {
    if (!autoSuggest || !cacheReady || reviewed) return;
    if (baselineTaken.current) return;
    if (view.currentRevision.draftItems.length > 0 || session.current.items.length > 0) return;
    baselineTaken.current = true;
    void suggest();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoSuggest, cacheReady, reviewed]);

  /* ------------------------------------------------ 保存 / 审核（CAS + 冻结提交） */
  async function saveDraft(): Promise<boolean> {
    if (save.busy || review.busy || cacheBlocked.current || !cacheReady) return false;
    let explicitFailure = false;
    const receipt = await save.submit(
      {
        expectedRevision: session.current.serverRevision,
        items: structuredClone(session.current.items),
        constraints: structuredClone(session.current.constraints),
      },
      (frozen) => {
        session.current.saveOperation = frozen;
        if (!persist()) {
          explicitFailure = true;
          throw new ApiError('RECOVERY_CACHE_FAILED', '发送前无法保存原操作恢复包，请修复本机缓存后重试。', 503, true);
        }
        return services
          .patchPracticeDraft(view.practiceSetId, { ...frozen.payload, submissionId: frozen.submissionId })
          .catch((cause: unknown) => {
            if (asApiError(cause).status !== 0) explicitFailure = true;
            throw cause;
          });
      },
    );
    if (!receipt) {
      if (!alive.current) return false;
      if (explicitFailure) {
        session.current.saveOperation = null;
        persist();
      }
      return false;
    }
    session.current.saveOperation = null;
    applyBaseline(receipt, '草稿已保存。审核是另一步：确认后才进入导出。');
    return true;
  }

  async function reviewDraft() {
    if (review.busy || save.busy || cacheBlocked.current) return;
    if (!reviewReady) return;
    let explicitFailure = false;
    const receipt = await review.submit(
      { submissionId: '', expectedRevision: session.current.serverRevision },
      (frozen) => {
        session.current.reviewOperation = frozen;
        if (!persist()) {
          explicitFailure = true;
          throw new ApiError('RECOVERY_CACHE_FAILED', '发送前无法保存审核恢复包。', 503, true);
        }
        return services
          .reviewPractice(view.practiceSetId, { ...frozen.payload, submissionId: frozen.submissionId })
          .catch((cause: unknown) => {
            if (asApiError(cause).status !== 0) explicitFailure = true;
            throw cause;
          });
      },
    );
    if (!receipt) {
      if (alive.current && explicitFailure) {
        session.current.reviewOperation = null;
        persist();
      }
      return;
    }
    session.current.reviewOperation = null;
    setConfirmReview(false);
    applyBaseline(receipt, '已审核：该修订被冻结，现在可以进入「导出预览」。');
  }

  /** 收到明确回执后推进服务端基线（保存/审核/原包重试共用）。 */
  function applyBaseline(receipt: PracticeSetView, message: string) {
    session.current.serverRevision = receipt.revision;
    session.current.serverRevisionId = receipt.currentRevision.practiceRevisionId;
    setServerRevision(receipt.revision);
    session.current.items = structuredClone(receipt.currentRevision.draftItems);
    session.current.constraints = structuredClone(receipt.currentRevision.constraints);
    session.current.dirty = false;
    setItems(session.current.items);
    setConstraints(session.current.constraints);
    setDirty(false);
    setNotice(message);
    persist();
    onSaved(receipt);
  }

  /**
   * 恢复稿里的未确认操作只按原包重试：沿用原 `submissionId` 与原样载荷，不换标识重做；
   * 服务端明确拒绝（非 0 状态）时解除恢复包并保留输入，让教师显式修正后重新提交。
   */
  async function replayRestoredOperation() {
    if (replaying || !restoredOperation || cacheBlocked.current || !cacheReady) return;
    const kind = restoredOperation;
    setReplaying(true);
    setReplayError(null);
    try {
      if (kind === 'save') {
        const operation = session.current.saveOperation;
        if (!operation) throw new ApiError('RECOVERY_OPERATION_MISSING', '恢复稿里没有原保存包。', 500, false);
        const receipt = await services.patchPracticeDraft(view.practiceSetId, {
          ...operation.payload,
          submissionId: operation.submissionId,
        });
        if (!alive.current) return;
        session.current.saveOperation = null;
        setRestoredOperation(null);
        applyBaseline(receipt, '原保存包已按同一提交标识重试成功。');
      } else {
        const operation = session.current.reviewOperation;
        if (!operation) throw new ApiError('RECOVERY_OPERATION_MISSING', '恢复稿里没有原审核包。', 500, false);
        const receipt = await services.reviewPractice(view.practiceSetId, {
          ...operation.payload,
          submissionId: operation.submissionId,
        });
        if (!alive.current) return;
        session.current.reviewOperation = null;
        setRestoredOperation(null);
        setConfirmReview(false);
        applyBaseline(receipt, '原审核包已按同一提交标识重试成功。');
      }
    } catch (cause) {
      const apiError = asApiError(cause);
      if (!alive.current) return;
      if (apiError.status !== 0) {
        if (kind === 'save') session.current.saveOperation = null;
        else session.current.reviewOperation = null;
        setRestoredOperation(null);
        persist();
      }
      setReplayError(apiError);
    } finally {
      if (alive.current) setReplaying(false);
    }
  }

  async function createNewDraft() {
    if (newRevisionBusy || !reviewed) return;
    setNewRevisionBusy(true);
    setNewRevisionError(null);
    try {
      const next = await services.createPracticeRevision(view.practiceSetId, {
        submissionId: crypto.randomUUID(),
        sourceRevisionId: view.currentRevision.practiceRevisionId,
      });
      if (!alive.current) return;
      setNotice('已基于审核版本建立新草稿：修改后需要重新保存并审核。');
      onSaved(next);
    } catch (cause) {
      if (alive.current) setNewRevisionError(asApiError(cause));
    } finally {
      if (alive.current) setNewRevisionBusy(false);
    }
  }

  function adopt(suggestion: PracticeSuggestion) {
    const key = crypto.randomUUID();
    edit([...items, itemFromSuggestion(suggestion, key, items.length + 1)]);
  }

  function adoptAll() {
    const remaining = (suggestions?.items ?? []).filter(
      (suggestion) => !items.some((item) => item.questionRevisionId === suggestion.questionRevisionId),
    );
    if (remaining.length === 0) return;
    const base = items.length;
    // 逐个采用时先递增 ordinal，最后由 renumber 统一重排，保证题号与顺序一致。
    const appended = remaining.reduce<PracticeDraftItem[]>(
      (acc, suggestion, index) => [...acc, itemFromSuggestion(suggestion, crypto.randomUUID(), base + index + 1)],
      [],
    );
    edit(renumber([...items, ...appended]));
  }

  const itemContent = (item: PracticeDraftItem): { content: RichContentV2 | null; questionId: string | null; answerState: string | null } => {
    const fixed = view.currentRevision.items.find((candidate) => candidate.itemKey === item.itemKey);
    if (fixed) return { content: fixed.content, questionId: fixed.questionId, answerState: fixed.answerState };
    const cached = candidates[item.questionRevisionId]?.suggestion;
    if (cached) return { content: cached.content, questionId: cached.questionId, answerState: cached.answerState };
    return { content: null, questionId: null, answerState: null };
  };

  return (
    <section className="practices-card" aria-label="练习草稿编辑" data-testid="practices-editor">
      <header className="practices-card-head">
        <h2>生成后微调</h2>
        <p className="practices-hint">
          来源报告 {nameOrShortId(view.currentRevision.sourcePaperTitle, view.currentRevision.analysisRunId)} · 编辑版本 r
          {serverRevision} · {dirty ? '有未保存修改' : '当前草稿与服务端一致'}。
          {reviewed ? ' 当前修订已审核（只读）；继续修改请建立新草稿。' : ' 保存不等于审核：AI 与后端选拔只进候选，教师显式采用并审核后才进入导出。'}
        </p>
      </header>

      {cacheError && (
        <p className="space-banner error" role="alert" data-testid="practices-cache-error">
          {cacheError}
        </p>
      )}
      {notice && (
        <p className="practices-hint" role="status" data-testid="practices-editor-notice">
          {notice}
        </p>
      )}
      {pendingUnknown && (
        <div className="space-banner" role="alert">
          <p>上次提交结果未知：编辑已锁定，请先重试原包（同一提交标识、同一载荷，不会重复写入）。</p>
          {restoredOperation !== null && (
            <div className="practices-actions">
              <button
                className="space-button primary"
                data-testid="practices-replay-restored"
                disabled={replaying || cacheBlocked.current}
                onClick={() => void replayRestoredOperation()}
              >
                {replaying
                  ? '正在重放原包…'
                  : restoredOperation === 'save'
                    ? '重试刷新前的原保存包'
                    : '重试刷新前的原审核包'}
              </button>
              <span className="practices-hint">本机恢复稿保留了刷新前那次提交的标识与载荷。</span>
            </div>
          )}
          <ErrorNotice error={replayError} />
        </div>
      )}
      {reviewed && (
        <div className="practices-actions">
          <button className="space-button" data-testid="practices-new-revision" disabled={newRevisionBusy} onClick={() => void createNewDraft()}>
            {newRevisionBusy ? '正在建立…' : '基于此审核版本建立新草稿'}
          </button>
          <span className="practices-hint">新草稿复制该审核版本的选题与计分结构；审核版本本身保持冻结。</span>
        </div>
      )}
      <ErrorNotice error={newRevisionError} />

      <ConstraintsFields value={constraints} onChange={changeConstraints} disabled={locked || reviewed} />

      <div className="practices-actions">
        <button
          type="button"
          className="space-button"
          data-testid="practices-suggest"
          disabled={locked || reviewed || save.busy || review.busy}
          onClick={() => void suggest()}
        >
          {suggesting ? '正在按约束选拔…' : '获取题库选拔建议'}
        </button>
        <span className="practices-hint">只读地把已确认题库按约束选拔为候选；采用与写入都由教师显式操作。</span>
      </div>
      {suggesting && <p role="status">正在按明确约束从已确认题库选拔…</p>}
      <ErrorNotice error={suggestionError} />

      {suggestions && (
        <section className="practices-suggestions" aria-label="题库选拔建议" data-testid="practices-suggestions">
          <h3>
            选拔结果：{suggestions.selectedCount} / {suggestions.requestedCount}
          </h3>
          <p className="practices-hint">
            覆盖：
            {Object.entries(suggestions.coverage)
              .map(([id, count]) => `${view.currentRevision.targetKnowledgePoints.find((p) => p.knowledgePointId === id)?.name ?? shortId(id)} ${count}`)
              .join('；') || '无覆盖'}
          </p>
          {suggestions.gaps.length > 0 ? (
            <div className="space-banner" role="alert">
              <strong>仍有缺口</strong>
              {suggestions.gaps.map((gap, index) => (
                <p key={index}>{gap}</p>
              ))}
              <p>请调整明确约束，或先用「教师描述」让 AI 补题并在题库校对确认；不会自动放宽条件或自动写入草稿。</p>
            </div>
          ) : (
            <p className="practices-hint">后端未报告缺口。</p>
          )}
          {suggestions.items.length > 0 && (
            <div className="practices-actions">
              <button className="space-button" data-testid="practices-adopt-all" disabled={locked || reviewed} onClick={adoptAll}>
                按建议顺序全部采用（{suggestions.items.length} 题）
              </button>
              <span className="practices-hint">采用后仍可逐题调整顺序、分值与知识点，再统一保存。</span>
            </div>
          )}
          {suggestions.items.map((suggestion) => {
            const adopted = items.some((item) => item.questionRevisionId === suggestion.questionRevisionId);
            const loadAsset = (assetId: string, signal: AbortSignal) =>
              getQuestionAsset('question', suggestion.questionId, assetId, signal);
            return (
              <details key={suggestion.questionRevisionId} className="practices-suggestion" data-testid={`practices-suggestion-${suggestion.questionRevisionId}`}>
                <summary>
                  <span>题 {shortId(suggestion.questionId)}</span>
                  <span className={difficultyBadgeClass((suggestion.difficulty as Difficulty | null) ?? 'unspecified')}>
                    {difficultyLabel((suggestion.difficulty as Difficulty | null) ?? 'unspecified')}
                  </span>
                  <span className="practices-meta">{suggestion.reason}</span>
                </summary>
                <RichReview content={suggestion.content} loadAsset={loadAsset} assetScope={`${suggestion.questionId}|${suggestion.questionRevisionId}`} teacher />
                <p className="practices-meta">
                  固定题修订 {shortId(suggestion.questionRevisionId)} · {suggestion.questionType ?? '题型未标注'} ·{' '}
                  {ANSWER_STATE_LABEL[(suggestion.answerState as keyof typeof ANSWER_STATE_LABEL) ?? 'not_provided'] ?? suggestion.answerState}
                </p>
                <button
                  className="space-button"
                  data-testid={`practices-adopt-${suggestion.questionRevisionId}`}
                  disabled={locked || reviewed || adopted}
                  onClick={() => adopt(suggestion)}
                >
                  {adopted ? '已采用' : '作为一计分叶加入，随后复核结构'}
                </button>
              </details>
            );
          })}
        </section>
      )}

      {items.length === 0 && (
        <p className="practices-hint" data-testid="practices-empty-items">
          草稿还没有选题：先「获取题库选拔建议」再显式采用，或到题库补齐已确认题目后重新选拔。
        </p>
      )}

      <div className="practices-item-list">
        {items.map((item, index) => (
          <DraftItemEditor
            key={item.itemKey}
            item={item}
            index={index}
            count={items.length}
            locked={locked || reviewed}
            difficulty={(candidates[item.questionRevisionId]?.difficulty ?? null) as Difficulty | null}
            answerState={itemContent(item).answerState}
            content={itemContent(item).content}
            questionId={itemContent(item).questionId}
            onChange={(next) => edit(items.map((old, position) => (position === index ? next : old)))}
            onMove={(direction) => edit(moveItem(items, index, direction))}
            onRemove={() => edit(renumber(items.filter((_, position) => position !== index)))}
          />
        ))}
      </div>

      <section className="practices-gate" aria-label="审核门槛" data-testid="practices-review-gate">
        <h3>确认门槛</h3>
        <ul>
          <li className={items.length > 0 ? 'ok' : 'gap'}>
            已选题目 {items.length} 题{items.length === 0 ? '：至少需要一题' : ''}
          </li>
          <li className={countGap === 0 ? 'ok' : 'gap'}>
            题量约束 {items.length} / {constraints.count}
            {countGap > 0 ? `：还差 ${countGap} 题` : countGap < 0 ? `：超出 ${-countGap} 题` : '：满足'}
          </li>
          <li className={missingTargets.length === 0 ? 'ok' : 'gap'}>
            目标知识点覆盖 {targets.length - missingTargets.length} / {targets.length}
            {missingTargets.length > 0
              ? `：未覆盖 ${missingTargets
                  .map((id) => view.currentRevision.targetKnowledgePoints.find((point) => point.knowledgePointId === id)?.name ?? shortId(id))
                  .join('、')}`
              : ''}
          </li>
          <li className={dirty ? 'gap' : 'ok'}>{dirty ? '有未保存修改：先保存草稿才能审核' : '草稿已保存'}</li>
        </ul>
        <div className="practices-actions">
          <button
            className="space-button"
            data-testid="practices-save"
            disabled={
              !cacheReady ||
              cacheBlocked.current ||
              save.busy ||
              review.busy ||
              reviewed ||
              restoredOperation !== null ||
              review.phase === 'unknown'
            }
            onClick={() => void saveDraft()}
          >
            {save.phase === 'unknown' ? '重试原草稿保存' : save.busy ? '保存中…' : '保存草稿'}
          </button>
          {confirmReview ? (
            <>
              <button
                className="space-button primary"
                data-testid="practices-review-confirm"
                disabled={review.busy || (!reviewReady && review.phase !== 'unknown') || save.phase === 'unknown' || restoredOperation !== null}
                onClick={() => void reviewDraft()}
              >
                {review.phase === 'unknown' ? '重试原审核提交' : review.busy ? '审核中…' : '确认审核（冻结此修订）'}
              </button>
              <button className="space-button" disabled={review.busy} onClick={() => setConfirmReview(false)}>
                取消
              </button>
            </>
          ) : (
            <button
              className="space-button primary"
              data-testid="practices-review"
              disabled={!reviewReady || reviewed || review.busy || save.phase === 'unknown' || review.phase === 'unknown' || restoredOperation !== null}
              onClick={() => setConfirmReview(true)}
            >
              提交审核（确认后进入导出）
            </button>
          )}
        </div>
        {!reviewReady && !reviewed && (
          <p className="practices-hint" role="status">
            审核要求：无未保存修改、题量与题量约束一致、目标知识点全部被计分叶覆盖（与后端校验一致）。
          </p>
        )}
        {confirmReview && (
          <p className="practices-hint" role="alert">
            审核会冻结该修订的题目、计分叶、材料、知识点与答案；冻结后本修订不可再修改，导出只从已审核修订生成。
          </p>
        )}
        <SubmissionNotice submission={save} />
        <SubmissionNotice submission={review} />
      </section>
    </section>
  );
}

function DraftItemEditor({
  item,
  index,
  count,
  locked,
  difficulty,
  answerState,
  content,
  questionId,
  onChange,
  onMove,
  onRemove,
}: {
  item: PracticeDraftItem;
  index: number;
  count: number;
  locked: boolean;
  difficulty: Difficulty | null;
  answerState: string | null;
  content: RichContentV2 | null;
  questionId: string | null;
  onChange: (item: PracticeDraftItem) => void;
  onMove: (direction: -1 | 1) => void;
  onRemove: () => void;
}) {
  const loadAsset = questionId
    ? (assetId: string, signal: AbortSignal) => getQuestionAsset('question', questionId, assetId, signal)
    : undefined;
  const blockOptions = content ? [...content.stemBlocks, ...Object.values(content.optionBlocks).flat()] : [];
  const updateNode = (position: number, patch: Partial<PracticeNode>) => onChange(withNode(item, position, patch));
  return (
    <article className="practices-item" aria-label={`练习第${index + 1}题`} data-testid={`practices-item-${index}`}>
      <header className="practices-item-head">
        <h3>第{index + 1}题</h3>
        <span className={difficultyBadgeClass(difficulty ?? 'unspecified')}>{difficultyLabel(difficulty ?? 'unspecified')}</span>
        {answerState && (
          <span className="practices-meta">{ANSWER_STATE_LABEL[answerState as keyof typeof ANSWER_STATE_LABEL] ?? answerState}</span>
        )}
        <span className="practices-meta" title={`固定题修订 ${item.questionRevisionId}`}>
          固定修订 {shortId(item.questionRevisionId)} · 整题 {item.maxScore} 分
        </span>
        <div className="practices-actions">
          <button className="space-button" disabled={locked || index === 0} onClick={() => onMove(-1)} aria-label={`第${index + 1}题上移`}>
            上移
          </button>
          <button
            className="space-button"
            disabled={locked || index === count - 1}
            onClick={() => onMove(1)}
            aria-label={`第${index + 1}题下移`}
          >
            下移
          </button>
          <button className="space-button" disabled={locked} onClick={onRemove} aria-label={`移除第${index + 1}题`}>
            移除
          </button>
        </div>
      </header>

      {content ? (
        <>
          <details className="practices-item-view">
            <summary>学生视角题面（题干与选项）</summary>
            <RichReview content={content} loadAsset={loadAsset} assetScope={`${questionId ?? item.itemKey}|${item.questionRevisionId}`} teacher={false} />
          </details>
          <details className="practices-item-view">
            <summary>答案与解析（教师视角）</summary>
            <RichReview content={content} loadAsset={loadAsset} assetScope={`${questionId ?? item.itemKey}|${item.questionRevisionId}`} teacher />
          </details>
        </>
      ) : (
        <p className="practices-hint" data-testid={`practices-item-${index}-no-content`}>
          该选题尚未在服务端物化题面：保存草稿后按固定题修订显示；内容编辑在题库的草稿→确认链完成。
        </p>
      )}

      <p className="practices-hint">
        题干、选项、答案、解析与难度属于题库题目内容，请在题库对应题目上走「草稿 → 确认」修改；练习侧只调整选择与计分结构。
        <span className="practices-link">
          <a
            href={`/question-bank?revision=${encodeURIComponent(item.questionRevisionId)}`}
            target="_blank"
            rel="noreferrer"
            title={`题库暂不支持按题直达；请按固定题修订 ${item.questionRevisionId} 在题库定位（查询参数已带上，供后续深链支持）`}
          >
            打开题库修改该题内容
          </a>
        </span>
        （题库页面暂不支持按题直达，需在题库中按该固定题修订定位。）
      </p>

      <fieldset className="practices-fieldset" disabled={locked}>
        <legend>计分结构</legend>
        <label className="practices-field">
          整题满分（十进制文本）
          <input
            aria-label={`第${index + 1}题整题满分`}
            inputMode="decimal"
            value={item.maxScore}
            onChange={(event) => onChange({ ...item, maxScore: event.target.value })}
          />
        </label>
        <p className="practices-hint">整题满分须与计分叶合计一致；分值、结构与知识点引用由服务端核验。</p>
        {item.itemStructure.nodes.map((node, position) => (
          <div key={node.nodeKey} className="practices-node">
            <strong>结构节点 {position + 1}</strong>
            <span className="practices-meta">{shortId(node.nodeKey)}</span>
            <div className="practices-fields">
              <label className="practices-field">
                题号
                <input
                  aria-label={`第${index + 1}题节点${position + 1}题号`}
                  value={node.questionNo}
                  onChange={(event) => updateNode(position, { questionNo: event.target.value })}
                />
              </label>
              <label className="practices-field">
                计分叶满分
                <input
                  aria-label={`第${index + 1}题节点${position + 1}满分`}
                  inputMode="decimal"
                  value={node.maxScore ?? ''}
                  disabled={!node.isScored}
                  onChange={(event) => updateNode(position, { maxScore: event.target.value })}
                />
              </label>
            </div>
            <label>
              <input
                type="checkbox"
                aria-label={`第${index + 1}题节点${position + 1}计分`}
                checked={node.isScored}
                onChange={(event) => updateNode(position, { isScored: event.target.checked, maxScore: event.target.checked ? node.maxScore ?? '1' : null })}
              />
              该节点是计分叶（参与覆盖统计）
            </label>
            {node.isScored && (
              <div className="practices-nodes-points" aria-label={`第${index + 1}题节点${position + 1}知识点`}>
                {(node.knowledgePointIds ?? []).length > 0 ? (
                  (node.knowledgePointIds ?? []).map((id) => (
                    <span key={id} className="practices-chip">
                      {id}
                    </span>
                  ))
                ) : (
                  <span className="practices-meta">未分配知识点：该计分叶不计入目标覆盖。</span>
                )}
              </div>
            )}
            {blockOptions.length > 0 && (
              <div className="practices-checks">
                {blockOptions.map((block, blockIndex) => (
                  <label key={block.id}>
                    <input
                      type="checkbox"
                      checked={(node.sourceBlockIds ?? []).includes(block.id)}
                      aria-label={`第${index + 1}题节点${position + 1}题面块${blockIndex + 1}`}
                      onChange={(event) =>
                        updateNode(position, {
                          sourceBlockIds: event.target.checked
                            ? [...(node.sourceBlockIds ?? []), block.id]
                            : (node.sourceBlockIds ?? []).filter((id) => id !== block.id),
                        })
                      }
                    />
                    内容{blockIndex + 1} ·{' '}
                    {block.kind === 'paragraph'
                      ? block.text.slice(0, 30)
                      : { table: '表格', formula: '公式', image: '图片' }[block.kind]}
                  </label>
                ))}
              </div>
            )}
          </div>
        ))}
      </fieldset>
    </article>
  );
}
