'use client';

/**
 * 成绩导入的校对（行定位 / 单元格校正）→ 预览承认 → 确认入库。
 *
 * 硬要求（TEACHING-LOOP B3 · F20-I）：
 * - 每个异常显示**原表物理地址**（行号 + 列字母），编辑器保留原表坐标；
 * - 0 / missing / absent / exempt 显著区分（徽章 + 文案 + 图例，不只靠颜色）；
 * - 409：保留当前编辑与用户输入，提示「数据已变化，请刷新对照」并提供显式刷新；
 * - 422：保留校对状态并定位到该行该列（`details.issues[].row/column`）；
 * - 确认是逻辑确认：冻结 `submissionId` + 原样载荷，结果未知时按幂等重试同一标识；
 * - 承认：逐班列举 absent 人次 + missing 人次与单元数，勾选后才能提交，
 *   服务端 422 `SCORE_ACKNOWLEDGEMENT_MISMATCH` 的定位原样显示。
 */

import { useEffect, useRef, useState } from 'react';
import { CheckCheck, RefreshCw, Save } from 'lucide-react';
import type { ErrorIssue } from '@/contracts/api';
import type {
  ScoreImportConfirmRequest,
  ScoreImportConfirmResult,
  ScoreImportView,
} from '@/contracts/scores';
import { Modal } from '@/components/ui/Modal';
import { confirmScoreImport, listScoreImportRows } from '@/services/assessments-api';
import {
  scoreFlowStep,
  useAsyncResource,
  useClassNameMap,
  useFrozenSubmission,
  useScoreDrafts,
  type ScoreFlowStep,
} from './hooks';
import {
  issueLocationLabel,
  rawCellReading,
  scoreImportStateChipClass,
  scoreImportStateLabel,
  type ParticipantLite,
} from './labels';
import { ScoreStatusBadge } from './ScoreStatusBadge';

const ROWS_PER_PAGE = 50;
const STEPS: { id: ScoreFlowStep; label: string }[] = [
  { id: 'upload', label: '上传' },
  { id: 'mapping', label: '列映射' },
  { id: 'review', label: '行校对' },
  { id: 'acknowledge', label: '预览承认' },
  { id: 'confirmed', label: '确认入库' },
];

export function ScoreImportReview({
  view,
  reloadToken,
  participants,
  assessmentRevision,
  mappingPending = false,
  onReload,
  onReloadAssessment,
  onChanged,
  onOpenHistory,
}: {
  view: ScoreImportView;
  /** 父级显式刷新对照时递增：强制重读原表行（保留本地编辑）。 */
  reloadToken: number;
  leaves: { itemId: string; questionNo: string }[];
  participants: ParticipantLite[];
  assessmentRevision: number | null;
  /** 未保存/在途映射不能确认旧矩阵；未知确认仍重放原冻结包。 */
  mappingPending?: boolean;
  onReload: () => void;
  onReloadAssessment: () => void;
  onChanged: () => void;
  onOpenHistory: () => void;
}) {
  const [page, setPage] = useState(0);
  const [stage, setStage] = useState<'review' | 'acknowledge'>('review');
  const [focused, setFocused] = useState<{ row: number; column: string } | null>(null);
  const [ackAbsences, setAckAbsences] = useState(false);
  const [ackMissing, setAckMissing] = useState(false);
  const [confirmOpen, setConfirmOpen] = useState(false);
  /** 班名映射（只读）：候选人次与缺考分组显示班名；映射缺失/读取失败回落短号。 */
  const classNames = useClassNameMap(`score-review|${view.assessmentId}`);
  const drafts = useScoreDrafts(view);
  const submission = useFrozenSubmission<ScoreImportConfirmRequest, ScoreImportConfirmResult>();
  const editingLocked = submission.busy || submission.phase === 'unknown';
  const [savedPreview, setSavedPreview] = useState<{ revision: number; previewVersion: number } | null>(null);
  const saveInFlight = useRef(false);
  const edited = useRef(false);
  edited.current = drafts.dirty;
  const waitingForSavedPreview = savedPreview !== null && (
    view.revision < savedPreview.revision || view.previewVersion < savedPreview.previewVersion
  );
  const confirmationBlocked = drafts.dirty || drafts.saving || saveInFlight.current ||
    waitingForSavedPreview || mappingPending;

  function invalidateAcknowledgement() {
    setStage('review');
    setAckAbsences(false);
    setAckMissing(false);
    setConfirmOpen(false);
  }

  function editDraft(edit: () => void) {
    if (editingLocked || saveInFlight.current || drafts.saving) return;
    // 同步守卫：即使点击仍指向弹窗的旧 DOM，也不能提交旧矩阵。
    edited.current = true;
    invalidateAcknowledgement();
    edit();
  }

  async function saveDrafts() {
    if (saveInFlight.current || editingLocked || !drafts.dirty) return;
    saveInFlight.current = true;
    invalidateAcknowledgement();
    try {
      const next = await drafts.save();
      if (next) {
        setSavedPreview({ revision: next.revision, previewVersion: next.previewVersion });
        edited.current = false;
        onReload();
        onChanged();
      }
    } finally {
      saveInFlight.current = false;
    }
  }

  const rows = useAsyncResource(
    (signal) =>
      listScoreImportRows(
        view.importId,
        { offset: page * ROWS_PER_PAGE, limit: ROWS_PER_PAGE },
        signal,
      ),
    `assessments-score-rows|${view.importId}|${page}|${view.revision}`,
  );

  // 父级「显式刷新对照」：同一批次内重读原表行（不换 key，行列表不闪空、草稿不丢）
  const rowsReload = rows.reload;
  const firstRowsReload = useRef(true);
  useEffect(() => {
    if (firstRowsReload.current) {
      firstRowsReload.current = false;
      return;
    }
    rowsReload();
  }, [reloadToken, rowsReload]);

  // 保存/刷新得到新预览时，教师必须重新承认服务端当前范围。
  useEffect(() => {
    setAckAbsences(false);
    setAckMissing(false);
    setConfirmOpen(false);
  }, [view.importId, view.revision, view.previewVersion, assessmentRevision]);

  // 422 定位：滚动到出问题的行/列（jsdom 无 scrollIntoView 时静默跳过）
  useEffect(() => {
    if (!focused) return;
    const selector = `[data-testid="score-cell-${focused.row}-${focused.column}"]`;
    const element = document.querySelector(selector);
    element?.scrollIntoView?.({ block: 'center' });
  }, [focused]);

  // 服务端 422 逐条定位：自动聚焦到第一条问题的行/列（保留校对状态）
  const issueSignature = drafts.issues
    .map((issue) => `${issue.row ?? ''}:${issue.column ?? ''}`)
    .join(',');
  useEffect(() => {
    if (drafts.issues.length === 0) return;
    const first = drafts.issues[0];
    if (typeof first.row === 'number' && first.column) {
      setFocused({ row: first.row, column: first.column });
    }
  }, [issueSignature, drafts.issues]);

  const step = scoreFlowStep(view, { acknowledgeRequested: stage === 'acknowledge' });
  // 与确认闸门同源的有效矩阵范围；原表空白仅用于展示，不能替代服务端状态。
  const acknowledgement = view.requiredAcknowledgements;
  const absences = acknowledgement?.absences ?? [];
  const missing = acknowledgement?.missing ?? null;
  const frozenConfirmation = submission.phase === 'unknown' ? submission.frozen?.payload : null;
  const confirmationAbsences = frozenConfirmation ? frozenConfirmation.absences ?? [] : absences;
  const confirmationMissing = frozenConfirmation ? frozenConfirmation.missing ?? null : missing;
  const confirmedParticipants = (id: string) =>
    participants.find((participant) => participant.participantId === id);

  const issues = [...(view.issues ?? []), ...drafts.issues];
  const conflict = drafts.conflict;
  const confirmError = submission.error;
  const conflictError =
    confirmError && confirmError.code.toUpperCase().includes('REVISION_CONFLICT') ? confirmError : null;

  function applyIssueFocus(issue: ErrorIssue | undefined) {
    if (issue && typeof issue.row === 'number' && issue.column) {
      setFocused({ row: issue.row, column: issue.column });
    }
  }

  function buildConfirmPayload(): ScoreImportConfirmRequest | null {
    if (submission.phase === 'unknown' && submission.frozen) return submission.frozen.payload;
    if (
      confirmationBlocked || edited.current || stage !== 'acknowledge' ||
      assessmentRevision === null || !acknowledgement ||
      (absences.length > 0 && !ackAbsences) || (missing !== null && !ackMissing)
    ) return null;
    return {
      expectedImportRevision: view.revision,
      expectedAssessmentRevision: assessmentRevision,
      baseScoreRevisionId: view.baseScoreRevisionId ?? null,
      previewVersion: view.previewVersion,
      submissionId: '', // 由冻结的逻辑确认注入
      absences: ackAbsences ? absences : [],
      missing: ackMissing && missing ? missing : null,
    };
  }

  async function submitConfirm() {
    if (submission.phase !== 'unknown' && (confirmationBlocked || edited.current)) return;
    const payload = buildConfirmPayload();
    if (!payload) return;
    const result = await submission.submit(payload, async (frozen) => {
      const body = { ...(frozen.payload as ScoreImportConfirmRequest) };
      return confirmScoreImport(view.importId, { ...body, submissionId: frozen.submissionId });
    });
    if (result) {
      // 明确成功：关弹窗并把权威状态（已确认 + 新修订）读回来
      setConfirmOpen(false);
      onReload();
      onChanged();
    }
  }

  const rowItems = rows.lastData?.items ?? [];
  const total = rows.lastData?.total ?? view.rowCount;

  return (
    <section className="assessments-subpanel" aria-label="成绩校对与确认" data-testid="score-import-review">
      <div className="assessments-subpanel-head">
        <h3>成绩校对与确认</h3>
        <span className={scoreImportStateChipClass(view.state)} data-testid="score-import-state">
          {scoreImportStateLabel(view.state)}
        </span>
        <span className="assessments-meta">
          {view.fileAsset.originalName} · 行 {view.rowCount} · 已定位 {view.resolvedRowCount} · 空白单元{' '}
          {view.missingCellCount}
        </span>
      </div>

      <ol className="score-steps" aria-label="成绩导入步骤">
        {STEPS.map((entry) => (
          <li
            key={entry.id}
            className={entry.id === step ? 'score-step current' : 'score-step'}
            aria-current={entry.id === step ? 'step' : undefined}
            data-testid={`score-step-${entry.id}`}
          >
            {entry.label}
          </li>
        ))}
      </ol>

      {conflict && (
        <div className="space-banner error" role="alert" data-testid="score-conflict">
          <p>
            数据已变化，请刷新对照（服务端当前版本 {conflict.currentRevision ?? '未知'}）：
            {conflict.message} 你的编辑与输入都已保留。
          </p>
          <div className="assessments-actions">
            <button className="space-button" data-testid="score-refresh-compare" onClick={onReload}>
              <RefreshCw size={13} aria-hidden /> 显式刷新对照
            </button>
          </div>
        </div>
      )}

      {conflictError && (
        <div className="space-banner error" role="alert" data-testid="score-confirm-conflict">
          <p>
            确认被拒绝：{conflictError.message}
            {conflictError.details?.currentRevision !== undefined
              ? `（当前版本 ${conflictError.details.currentRevision}）`
              : ''}
            。原因可能是导入批次、施测或正式成绩版本在你校对期间变化；请刷新对照后重试，
            当前载荷与提交标识仍按逻辑确认冻结。
          </p>
          <div className="assessments-actions">
            <button
              className="space-button"
              onClick={() => {
                onReload();
                onReloadAssessment();
              }}
            >
              <RefreshCw size={13} aria-hidden /> 刷新批次与施测
            </button>
          </div>
        </div>
      )}

      {confirmError && confirmError.code === 'SCORE_ACKNOWLEDGEMENT_MISMATCH' && (
        <div className="space-banner error" role="alert" data-testid="score-ack-mismatch">
          <p>承认范围与预览不一致（{confirmError.code}）：{confirmError.message}</p>
          <ul className="assessments-issue-list">
            {(confirmError.details?.issues ?? []).map((issue, index) => (
              <li key={`${issue.code}-${index}`}>
                {issueLocationLabel(issue)}
                {issue.message}
              </li>
            ))}
          </ul>
        </div>
      )}

      {submission.unknownNotice && (
        <p className="space-banner error" role="alert" data-testid="score-confirm-unknown">
          {submission.unknownNotice}
        </p>
      )}

      <section className="score-rows" aria-label="原表行校对">
        <div className="assessments-subpanel-head">
          <h4>行校对（原表物理坐标）</h4>
          <span className="assessments-hint" data-testid="score-rows-page">
            第 {page + 1} 页 · 共 {total} 行 · 每页 {ROWS_PER_PAGE} 行
          </span>
        </div>

        {rows.state.phase === 'failed' && !rows.lastData && (
          <div className="space-banner error" role="alert" data-testid="score-rows-error">
            原表行读取失败（{rows.state.error.code}）：{rows.state.error.message}
            <button className="space-button" onClick={rows.reload}>
              重试
            </button>
          </div>
        )}

        {rows.state.phase === 'loading' && !rows.lastData && (
          <p className="assessments-hint" role="status" data-testid="score-rows-loading">
            正在读取原表行（保留原表物理坐标）…
          </p>
        )}

        <ul className="score-row-list">
          {rowItems.map((row) => (
            <li
              key={row.rowNo}
              className="score-row"
              data-testid={`score-row-${row.rowNo}`}
              data-issue-row={row.rowNo}
            >
              <div className="score-row-head">
                <span className="space-chip">原表第 {row.rowNo} 行</span>
                {row.participantId ? (
                  <span className="space-chip blue">
                    人次 {row.participantName ?? row.participantId}
                  </span>
                ) : (
                  <span className="space-chip amber">未匹配人次（需人工指定）</span>
                )}
                {(row.candidates?.length ?? 0) > 0 && (
                  <label className="assessments-field assessments-field-inline">
                    <span>人工指定人次</span>
                    <select
                      className="space-select"
                      aria-label={`第 ${row.rowNo} 行指定人次`}
                      value={drafts.edits.participants[row.rowNo] ?? row.participantId ?? ''}
                      disabled={drafts.saving || editingLocked}
                      onChange={(event) => editDraft(() => drafts.setParticipant(row.rowNo, event.target.value))}
                    >
                      <option value="">未指定</option>
                      {(row.candidates ?? []).map((candidate) => {
                        const participant = confirmedParticipants(candidate);
                        return (
                          <option key={candidate} value={candidate}>
                            {participant
                              ? `${participant.name}（${classNames.nameOf(participant.classId)}）`
                              : candidate}
                          </option>
                        );
                      })}
                    </select>
                  </label>
                )}
              </div>

              {(row.issues ?? []).length > 0 && (
                <ul className="assessments-issue-list">
                  {(row.issues ?? []).map((issue, index) => (
                    <li key={`${row.rowNo}-${issue.code}-${index}`}>
                      {issueLocationLabel(issue)}
                      {issue.code}：{issue.message}
                      {typeof issue.row === 'number' && issue.column && (
                        <button
                          className="space-button"
                          onClick={() => applyIssueFocus(issue)}
                          aria-label={`定位第 ${issue.row} 行列 ${issue.column}`}
                        >
                          定位
                        </button>
                      )}
                    </li>
                  ))}
                </ul>
              )}

              <ul className="score-cell-list">
                {(row.cells ?? []).map((cell) => {
                  const key = `${cell.row}:${cell.column}`;
                  const draftValue = drafts.edits.cells[key];
                  const reading = rawCellReading(draftValue !== undefined ? { text: draftValue } : cell);
                  const original = rawCellReading({ text: cell.originalText ?? cell.text,
                    cachedText: cell.originalCachedText ?? cell.cachedText, isFormula: cell.isFormula });
                  const isFocused =
                    focused?.row === cell.row && focused?.column === cell.column;
                  return (
                    <li
                      key={key}
                      className={isFocused ? 'score-cell focused' : 'score-cell'}
                      data-testid={`score-cell-${cell.row}-${cell.column}`}
                      data-issue={isFocused ? 'true' : undefined}
                    >
                      <span className="score-cell-address">
                        第 {cell.row} 行 · 列 {cell.column}
                      </span>
                      <ScoreStatusBadge
                        status={reading.kind}
                        text={reading.displayText}
                        testId={`score-cell-status-${cell.row}-${cell.column}`}
                      />
                      {reading.note && <span className="score-cell-note">{reading.note}</span>}
                      <span className="score-cell-note" data-testid={`score-original-${cell.row}-${cell.column}`}>
                        原件：{original.displayText}{original.note ? `（${original.note}）` : ''}
                      </span>
                      {cell.correctedText !== undefined && cell.correctedText !== null && (
                        <span className="score-cell-note" data-testid={`score-corrected-${cell.row}-${cell.column}`}>
                          已保存校正：{cell.correctedText === '' ? '（空白）' : cell.correctedText}
                        </span>
                      )}
                      {draftValue !== undefined && <span className="score-cell-note">未保存校正预览</span>}
                      <input
                        className="assessments-input assessments-input-narrow"
                        aria-label={`第 ${cell.row} 行 列 ${cell.column} 校正`}
                        placeholder={cell.text || '（空白）'}
                        value={draftValue ?? ''}
                        disabled={drafts.saving || editingLocked}
                        onChange={(event) => editDraft(() => drafts.setCell(cell.row, cell.column, event.target.value))}
                      />
                      {draftValue !== undefined && (
                        <button
                          className="space-button"
                          aria-label={`撤销第 ${cell.row} 行 列 ${cell.column} 的校正`}
                          disabled={drafts.saving || editingLocked}
                          onClick={() => editDraft(() => drafts.clearCell(cell.row, cell.column))}
                        >
                          撤销校正
                        </button>
                      )}
                    </li>
                  );
                })}
              </ul>
            </li>
          ))}
        </ul>

        {rowItems.length === 0 && rows.state.phase === 'ready' && (
          <p className="space-empty" data-testid="score-rows-empty">
            <strong>该批次没有已解析的原表行</strong>
            <span>可能是工作表/表头行/映射还不对；先在「列映射」里修正，或重新上传。</span>
          </p>
        )}

        <div className="assessments-actions">
          <button
            className="space-button"
            disabled={page === 0}
            onClick={() => setPage((value) => Math.max(0, value - 1))}
          >
            上一页
          </button>
          <button
            className="space-button"
            disabled={(page + 1) * ROWS_PER_PAGE >= total}
            onClick={() => setPage((value) => value + 1)}
          >
            下一页
          </button>
          <button
            className="space-button"
            disabled={drafts.saving || !drafts.dirty || editingLocked}
            data-testid="score-save-drafts"
            onClick={() => void saveDrafts()}
          >
            <Save size={13} aria-hidden />
            {drafts.saving ? '保存中…' : '保存校对'}
          </button>
          {drafts.dirty && <span className="space-chip amber">有未保存的校对</span>}
          <button
            className="space-button primary"
            disabled={confirmationBlocked || editingLocked || view.state === 'confirmed'}
            data-testid="score-goto-acknowledge"
            onClick={() => {
              if (!confirmationBlocked && !edited.current && !editingLocked) setStage('acknowledge');
            }}
          >
            进入预览承认
          </button>
          {drafts.dirty && (
            <span className="assessments-hint">先保存或撤销校对编辑，再进入承认。</span>
          )}
          {waitingForSavedPreview && <span className="assessments-hint" data-testid="score-waiting-preview">
            校对已保存，正在等待读回新权威预览；读取失败时请刷新对照，再重新承认。
          </span>}
        </div>

        {!drafts.dirty && drafts.notice && (
          <p className="space-banner info" role="status" data-testid="score-draft-notice">
            {drafts.notice}
          </p>
        )}
      </section>

      <section className="score-acknowledge" aria-label="预览承认">
        <div className="assessments-subpanel-head">
          <h4>预览承认</h4>
          <button className="space-button" onClick={onReload} data-testid="score-ack-refresh">
            <RefreshCw size={13} aria-hidden /> 刷新对照
          </button>
        </div>

        {stage !== 'acknowledge' ? (
          <p className="assessments-hint" data-testid="score-ack-pending">
            行校对完成后点击「进入预览承认」：逐班列举缺考人次 + 空白单元范围，勾选后才能确认。
          </p>
        ) : (
          <>
            <div className="score-ack-group" data-testid="score-ack-absences">
              <h5>缺考人次（按班）</h5>
              {absences.length === 0 ? (
                <p className="assessments-hint">没有缺考人次。</p>
              ) : (
                <ul className="assessments-list">
                  {absences.map((group) => (
                    <li key={group.classId} className="assessments-list-static">
                      <label className="assessments-check">
                        <input
                          type="checkbox"
                          aria-label={`承认 ${classNames.nameOf(group.classId)} 缺考 ${group.participantIds.length} 人次`}
                          checked={ackAbsences}
                          disabled={editingLocked}
                          onChange={(event) => setAckAbsences(event.target.checked)}
                        />
                        <span>
                          {classNames.nameOf(group.classId)}：{group.participantIds.length} 名缺考人次
                          <span className="assessments-meta">
                            {group.participantIds
                              .map((id) => confirmedParticipants(id)?.name ?? id)
                              .join('、')}
                          </span>
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              )}
            </div>

            <div className="score-ack-group" data-testid="score-ack-missing">
              <h5>空白单元范围</h5>
              {!acknowledgement ? (
                <p className="space-banner error" role="alert" data-testid="score-ack-unavailable">
                  服务端尚未提供本预览的承认范围，请刷新对照后确认。
                </p>
              ) : !missing ? (
                <p className="assessments-hint">没有空白单元。</p>
              ) : (
                <label className="assessments-check">
                  <input
                    type="checkbox"
                    aria-label={`承认空白 ${missing.cellCount} 个单元覆盖 ${missing.participantIds.length} 人次`}
                    checked={ackMissing}
                    disabled={editingLocked}
                    onChange={(event) => setAckMissing(event.target.checked)}
                  />
                  <span>
                    {missing.cellCount} 个空白单元，覆盖 {missing.participantIds.length} 人次
                    <span className="assessments-meta">
                      {missing.participantIds
                        .map((id) => confirmedParticipants(id)?.name ?? id)
                        .join('、')}
                    </span>
                  </span>
                </label>
              )}
              <p className="assessments-hint">
                空白按 missing 落库（不补 0）；未映射的计分叶同样按 missing 处理。
              </p>
            </div>

            <div className="assessments-actions">
              <button
                className="space-button primary"
                data-testid="score-open-confirm"
                disabled={
                  submission.busy || (submission.phase !== 'unknown' && (
                    confirmationBlocked ||
                    !acknowledgement ||
                    (absences.length > 0 && !ackAbsences) ||
                    (missing !== null && !ackMissing) || view.state === 'confirmed'
                  ))
                }
                onClick={() => {
                  if (buildConfirmPayload()) setConfirmOpen(true);
                }}
              >
                <CheckCheck size={14} aria-hidden /> 确认入库
              </button>
              {((absences.length > 0 && !ackAbsences) || (missing !== null && !ackMissing)) && (
                <span className="assessments-hint" data-testid="score-ack-blocker">
                  勾选上述承认项后才能确认。
                </span>
              )}
            </div>
          </>
        )}
      </section>

      {submission.result && (
        <p className="space-banner info" role="status" data-testid="score-confirm-result">
          {submission.result.replayed
            ? `已确认（重放）：同一提交标识此前已入库，本次未重复写入（修订 ${submission.result.revisionId}）。`
            : `已确认入库：修订 ${submission.result.revisionId}，施测 revision ${submission.result.assessmentRevision}。`}
          <button className="space-button" onClick={onOpenHistory}>
            去「历史」查看只读矩阵
          </button>
        </p>
      )}

      {confirmOpen && (
        <Modal title="确认成绩入库" onClose={() => setConfirmOpen(false)}>
          <p className="assessments-hint">
            确认是一次完整的事务：重放校验 → 预览版本 → 施测版本 → 承认范围 → 落库 → 封存。
            三个版本字段互不替代，任一不符会被 409 拒绝并保留当前编辑。
          </p>
          <dl className="score-confirm-summary">
            <div>
              <dt>导入批次修订</dt>
              <dd>r{frozenConfirmation?.expectedImportRevision ?? view.revision}（预览 v{frozenConfirmation?.previewVersion ?? view.previewVersion}）</dd>
            </div>
            <div>
              <dt>施测修订</dt>
              <dd>{frozenConfirmation?.expectedAssessmentRevision ?? assessmentRevision ?? '（读取中）'}</dd>
            </div>
            <div>
              <dt>基于正式版本</dt>
              <dd>{(frozenConfirmation ? frozenConfirmation.baseScoreRevisionId : view.baseScoreRevisionId) ?? '（首版）'}</dd>
            </div>
            <div>
              <dt>缺考承认</dt>
              <dd>
                {confirmationAbsences.length === 0
                  ? '无缺考人次'
                  : `${confirmationAbsences.length} 个班 / ${confirmationAbsences.reduce((sum, group) => sum + group.participantIds.length, 0)} 人次`}
              </dd>
            </div>
            <div>
              <dt>空白承认</dt>
              <dd>{confirmationMissing ? `${confirmationMissing.cellCount} 个单元 / ${confirmationMissing.participantIds.length} 人次` : '无空白单元'}</dd>
            </div>
            <div>
              <dt>提交标识</dt>
              <dd data-testid="score-submission-id">{submission.frozen?.submissionId ?? '（提交时生成）'}</dd>
            </div>
          </dl>
          <p className="assessments-hint">
            同一提交标识与同一载荷重试按幂等处理；结果未知（拿不到响应）时请直接重试，不要修改数据。
          </p>
          <div className="assessments-actions">
            <button
              className="space-button primary"
              data-testid="score-confirm-submit"
              disabled={submission.busy || (submission.phase !== 'unknown' && (
                confirmationBlocked || stage !== 'acknowledge' || assessmentRevision === null || !acknowledgement ||
                (absences.length > 0 && !ackAbsences) || (missing !== null && !ackMissing)
              ))}
              onClick={() => void submitConfirm()}
            >
              {submission.busy ? '确认中…' : '确认入库'}
            </button>
            <button
              className="space-button"
              disabled={submission.busy}
              onClick={() => setConfirmOpen(false)}
            >
              取消
            </button>
          </div>
        </Modal>
      )}

      {issues.length > 0 && (
        <ul className="assessments-issue-list" data-testid="score-issue-list">
          {issues.map((issue, index) => (
            <li key={`${issue.code}-${index}`}>
              {issueLocationLabel(issue)}
              {issue.code}：{issue.message}
              {typeof issue.row === 'number' && issue.column && (
                <button className="space-button" onClick={() => applyIssueFocus(issue)}>
                  定位到第 {issue.row} 行 列 {issue.column}
                </button>
              )}
            </li>
          ))}
        </ul>
      )}

      {drafts.error && drafts.error.status !== 422 && (
        <p className="space-banner error" role="alert" data-testid="score-draft-error">
          保存校对失败（{drafts.error.code}）：{drafts.error.message} 当前编辑已保留，可直接重试。
        </p>
      )}

      {view.state === 'confirmed' && (
        <p className="space-banner info" role="status" data-testid="score-import-confirmed">
          该批次已确认入库（本页若无本次会话回执则不显示写入计数，也不重复写入）。
        </p>
      )}
    </section>
  );
}
