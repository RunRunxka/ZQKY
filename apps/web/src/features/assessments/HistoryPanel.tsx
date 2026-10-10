'use client';

/**
 * 第五步「历史」：成绩修订列表 + 只读矩阵（分页）+ 修正入口。
 *
 * - 矩阵 = 冻结参测人次 × 固定计分叶；`totalUnits` 只在该人次**全员 recorded** 时非空，
 *   含 missing/缺考/免考一律不展示总分（也不用 0 代替）；
 * - 修正 = 从**不可变 base** 复制全矩阵 + 修正当时的参测快照生成新完整版本；
 *   `baseScoreRevisionId` 必须是当前生效版本（本页按最高已确认版本推断；见结果卡契约缺口）；
 * - 修正自身即一次完整确认：`submissionId` 冻结，同载荷重试按幂等处理；
 * - 彻底删除 = 受引用守卫的物理删除（二次确认）：被学情报告/更新版本/导入批次引用时 409
 *   `SCORE_REVISION_IN_USE`，逐项列出 `details.counts`；删掉正在展示的版本时立即切走，不读取已删版本。
 */

import { useRef, useState } from 'react';
import Link from 'next/link';
import { Plus, RefreshCw } from 'lucide-react';
import type {
  ScoreCorrectionEntry,
  ScoreRevisionCorrectRequest,
  ScoreRevisionCorrectResult,
  ScoreRevisionView,
} from '@/contracts/scores';
import type { ScoreStatus } from '@/contracts/teaching-loop';
import {
  correctScoreRevision,
  deleteScoreRevision,
  getAssessment,
  getScoreMatrix,
  getScoreRevision,
  listScoreRevisions,
} from '@/services/assessments-api';
import { asApiError, useAsyncResource, useClassNameMap, useFrozenSubmission } from './hooks';
import {
  attendanceLabel,
  cellValueText,
  formatScoreUnits,
  matrixRowTotalText,
  referenceCounts,
  SCORE_REVISION_REFERENCE_LABELS,
  scoreRevisionStateLabel,
  scoreStatusLabel,
  shortId,
} from './labels';
import { DeleteGuardNotice, type DeleteGuardState } from './DeleteGuardNotice';
import { ScoreStatusBadge, ScoreStatusLegend } from './ScoreStatusBadge';

const ROWS_PER_PAGE = 50;
const STATUS_OPTIONS: ScoreStatus[] = ['recorded', 'missing', 'absent', 'exempt'];

export function HistoryPanel({
  assessmentId,
  refreshToken,
  onChanged,
}: {
  assessmentId: string | null;
  refreshToken: number;
  onChanged: () => void;
}) {
  const [selectedRevisionId, setSelectedRevisionId] = useState<string | null>(null);
  const [page, setPage] = useState(0);
  const [localRefresh, setLocalRefresh] = useState(0);
  const [reason, setReason] = useState('');
  const [participantId, setParticipantId] = useState('');
  const [itemId, setItemId] = useState('');
  const [status, setStatus] = useState<ScoreStatus>('recorded');
  const [scoreText, setScoreText] = useState('');
  const [corrections, setCorrections] = useState<ScoreCorrectionEntry[]>([]);
  const [formError, setFormError] = useState<string | null>(null);
  /** 彻底删除（物理删除）的写操作身份与提示；与修正提交互斥。 */
  const [deleteBusyId, setDeleteBusyId] = useState<string | null>(null);
  const [deleteGuard, setDeleteGuard] = useState<DeleteGuardState | null>(null);
  const [deleteNotice, setDeleteNotice] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const deleteBusyRef = useRef(false);
  /** 已删除版本：列表/施测详情读回前也不读取已删版本（矩阵与修正基准）。 */
  const [removedRevisionIds, setRemovedRevisionIds] = useState<string[]>([]);
  const submission = useFrozenSubmission<ScoreRevisionCorrectRequest, ScoreRevisionCorrectResult>();
  /** 班名映射（只读）：修正人次下拉显示班名；映射缺失/读取失败回落短号。 */
  const classNames = useClassNameMap(`history|${assessmentId ?? 'none'}`);

  const revisions = useAsyncResource(
    (signal) =>
      assessmentId
        ? listScoreRevisions(assessmentId, signal)
        : Promise.resolve({ items: [], total: 0 }),
    `assessments-history-revisions|${assessmentId ?? 'none'}|${refreshToken}|${localRefresh}`,
  );
  const detail = useAsyncResource(
    (signal) => (assessmentId ? getAssessment(assessmentId, signal) : Promise.resolve(null)),
    `assessments-history-detail|${assessmentId ?? 'none'}|${refreshToken}|${localRefresh}`,
  );

  const revisionItems: ScoreRevisionView[] = (revisions.lastData?.items ?? []).filter(
    (revision) => !removedRevisionIds.includes(revision.revisionId),
  );
  const confirmed = revisionItems.filter((revision) => revision.state === 'confirmed');
  /** 权威字段优先：施测记录里的当前生效成绩修订（B3 契约 `activeScoreRevisionId`）。 */
  const activeFromAssessment = detail.lastData?.assessment.activeScoreRevisionId ?? null;
  /** 回退推断：版本号最大的已确认修订（旧后端缺字段时才使用）。 */
  const activeRevisionEntity = confirmed.reduce<ScoreRevisionView | null>(
    (best, revision) => (best === null || revision.version > best.version ? revision : best),
    null,
  );
  const activeRevisionId = activeFromAssessment ?? activeRevisionEntity?.revisionId ?? null;
  const activeIsAuthoritative = activeFromAssessment !== null;
  const selectedOrActiveRevisionId = selectedRevisionId ?? activeRevisionId;
  /** 已彻底删除的版本不再读取（施测详情/列表读回前也不闪读已删版本）。 */
  const activeRevisionIdSafe =
    selectedOrActiveRevisionId && !removedRevisionIds.includes(selectedOrActiveRevisionId)
      ? selectedOrActiveRevisionId
      : null;
  const activeRevision =
    confirmed.find((revision) => revision.revisionId === activeRevisionIdSafe) ?? null;

  const revisionDetail = useAsyncResource(
    (signal) =>
      activeRevisionIdSafe
        ? getScoreRevision(activeRevisionIdSafe, signal)
        : Promise.resolve(null),
    `assessments-history-revision|${activeRevisionIdSafe ?? 'none'}|${localRefresh}`,
  );

  const matrix = useAsyncResource(
    (signal) =>
      activeRevisionIdSafe
        ? getScoreMatrix(activeRevisionIdSafe, { offset: page * ROWS_PER_PAGE, limit: ROWS_PER_PAGE }, signal)
        : Promise.resolve(null),
    `assessments-history-matrix|${activeRevisionIdSafe ?? 'none'}|${page}|${localRefresh}`,
  );
  const matrixPage = matrix.lastData;
  const totalRows = matrixPage?.total ?? 0;

  const participantSnapshots = revisionDetail.lastData?.participantSnapshot ?? [];
  const itemSnapshots = revisionDetail.lastData?.itemSnapshot ?? [];

  function addCorrection() {
    setFormError(null);
    if (!participantId || !itemId) {
      setFormError('请选择要修正的人次与计分叶。');
      return;
    }
    if (status === 'recorded') {
      const parsed = scoreText.trim();
      if (!/^\d{1,4}(\.\d{1,2})?$/.test(parsed)) {
        setFormError('recorded 必须提供 0–9999、最多两位小数的分数文本。');
        return;
      }
      setCorrections((prev) => [
        ...prev.filter((entry) => !(entry.participantId === participantId && entry.itemId === itemId)),
        { participantId, itemId, status, scoreText: parsed },
      ]);
    } else {
      setCorrections((prev) => [
        ...prev.filter((entry) => !(entry.participantId === participantId && entry.itemId === itemId)),
        { participantId, itemId, status, scoreText: null },
      ]);
    }
    setScoreText('');
  }

  async function submitCorrection() {
    setFormError(null);
    const frozenPayload = submission.phase === 'unknown' ? submission.frozen?.payload : null;
    const assessmentRevision = detail.lastData?.assessment.revision;
    if (!frozenPayload && (!activeRevisionId || assessmentRevision === undefined || assessmentRevision === null)) {
      setFormError('缺少当前生效版本或施测版本，无法修正；请先刷新。');
      return;
    }
    if (!frozenPayload && reason.trim() === '') {
      setFormError('修正理由必填（审计保留原值/新值/理由/坐标）。');
      return;
    }
    if (!frozenPayload && corrections.length === 0) {
      setFormError('至少添加一条修正。');
      return;
    }
    const payload: ScoreRevisionCorrectRequest = frozenPayload ?? {
      baseScoreRevisionId: activeRevisionId!,
      expectedAssessmentRevision: assessmentRevision!,
      submissionId: '',
      reason: reason.trim(),
      corrections,
    };
    const result = await submission.submit(payload, async (frozen) => {
      const body = { ...(frozen.payload as ScoreRevisionCorrectRequest) };
      return correctScoreRevision(assessmentId as string, {
        ...body,
        submissionId: frozen.submissionId,
      });
    });
    if (result) {
      setCorrections([]);
      setReason('');
      setSelectedRevisionId(result.revisionId);
      setLocalRefresh((value) => value + 1);
      onChanged();
    }
  }

  const conflictError =
    submission.error && submission.error.code.toUpperCase().includes('CONFLICT')
      ? submission.error
      : null;
  const editingLocked = submission.busy || submission.phase === 'unknown';
  /** 删除在途时同样禁止提交修正：一次只允许一个写操作。 */
  const writingLocked = editingLocked || deleteBusyId !== null;

  /**
   * 彻底删除成绩版本（受引用守卫的物理删除，二次确认）：
   * 被学情报告/基于它的更新版本/基于它的导入批次引用 → 409 `SCORE_REVISION_IN_USE`，
   * 把服务端 message 与 `details.counts` 逐项列出；其它错误按既有错误区呈现。
   */
  async function deleteRevisionItem(revision: ScoreRevisionView) {
    if (deleteBusyRef.current) return;
    if (
      !window.confirm(
        `彻底删除成绩版本 v${revision.version}？这是物理删除、不可恢复；若它是当前生效版本，删除后本施测将没有生效成绩。`,
      )
    ) {
      return;
    }
    deleteBusyRef.current = true;
    setDeleteBusyId(revision.revisionId);
    setDeleteGuard(null);
    setDeleteNotice(null);
    setDeleteError(null);
    try {
      await deleteScoreRevision(revision.revisionId);
      // 已删版本立即从列表与读取路径剔除（施测详情/列表读回前不闪读已删版本）
      setRemovedRevisionIds((prev) => [...prev, revision.revisionId]);
      if (revision.revisionId === activeRevisionIdSafe) {
        const remaining = revisionItems.filter((item) => item.revisionId !== revision.revisionId);
        setSelectedRevisionId(remaining[0]?.revisionId ?? null);
        setPage(0);
      }
      setDeleteNotice(`已彻底删除成绩版本 v${revision.version}：物理删除完成，不可恢复。`);
      revisions.reload();
      detail.reload();
      onChanged();
    } catch (cause) {
      const error = asApiError(cause);
      if (error.status === 409 && error.code === 'SCORE_REVISION_IN_USE') {
        setDeleteGuard({
          targetId: revision.revisionId,
          error,
          reasons: referenceCounts(error.details, SCORE_REVISION_REFERENCE_LABELS),
        });
      } else {
        setDeleteError(`彻底删除成绩版本失败（${error.code}）：${error.message}`);
      }
    } finally {
      deleteBusyRef.current = false;
      setDeleteBusyId(null);
    }
  }

  if (!assessmentId) {
    return (
      <div className="assessments-panel" data-testid="assessments-history-panel">
        <p className="space-empty" data-testid="assessments-history-no-assessment">
          <strong>未选择施测</strong>
          <span>先在「施测」步骤选择一个施测，历史修订与只读矩阵会显示在这里。</span>
        </p>
      </div>
    );
  }

  /** 删除被拒时的对象显示名：仍能从列表读到版本号就用 `v{n}`，否则回落短号。 */
  const guardTargetRevision =
    deleteGuard === null
      ? null
      : revisionItems.find((revision) => revision.revisionId === deleteGuard.targetId) ?? null;

  return (
    <div className="assessments-panel" data-testid="assessments-history-panel">
      <section className="assessments-subpanel" aria-label="成绩修订列表">
        <div className="assessments-subpanel-head">
          <h3>成绩修订</h3>
          <button className="space-button" onClick={() => setLocalRefresh((value) => value + 1)}>
            <RefreshCw size={13} aria-hidden /> 刷新
          </button>
        </div>
        {revisions.state.phase === 'failed' && !revisions.lastData && (
          <div className="space-banner error" role="alert" data-testid="assessments-revisions-error">
            修订列表读取失败（{revisions.state.error.code}）：{revisions.state.error.message}
          </div>
        )}
        {revisionItems.length === 0 && revisions.state.phase === 'ready' && (
          <p className="space-empty" data-testid="assessments-history-empty">
            <strong>还没有成绩修订</strong>
            <span>先在「成绩」步骤上传并确认一次导入，之后这里会出现不可变修订与只读矩阵。</span>
          </p>
        )}
        <ul className="assessments-list" aria-label="成绩修订列表">
          {revisionItems.map((revision) => (
            <li key={revision.revisionId}>
              <div className="assessments-actions">
                <button
                  type="button"
                  className={
                    revision.revisionId === activeRevisionIdSafe
                      ? 'assessments-list-item current'
                      : 'assessments-list-item'
                  }
                  aria-pressed={revision.revisionId === activeRevisionIdSafe}
                  data-testid={`assessments-revision-${revision.revisionId}`}
                  onClick={() => {
                    setSelectedRevisionId(revision.revisionId);
                    setPage(0);
                  }}
                >
                  <strong>v{revision.version}</strong>
                  <span
                    className="assessments-meta"
                    title={`修订 ${revision.revisionId}${revision.baseRevisionId ? ` · 基于 ${revision.baseRevisionId}` : ' · 首版'}`}
                  >
                    {scoreRevisionStateLabel(revision.state)} · {shortId(revision.revisionId)} · 人次{' '}
                    {revision.participantSnapshot?.length ?? 0} · 叶{' '}
                    {revision.itemSnapshot?.length ?? 0}
                    {revision.baseRevisionId ? ` · 基于 ${shortId(revision.baseRevisionId)}` : ' · 首版'}
                    {revision.revisionId === activeRevisionId ? ' · 当前生效' : ''}
                  </span>
                </button>
                <button
                  type="button"
                  className="space-button danger"
                  aria-label={`彻底删除成绩版本 v${revision.version}`}
                  data-testid={`assessments-revision-delete-${revision.revisionId}`}
                  disabled={deleteBusyId !== null}
                  onClick={() => void deleteRevisionItem(revision)}
                >
                  {deleteBusyId === revision.revisionId ? '删除中…' : '彻底删除'}
                </button>
              </div>
            </li>
          ))}
        </ul>
        {deleteNotice && (
          <p className="space-banner info" role="status" data-testid="assessments-revision-delete-notice">
            {deleteNotice}
          </p>
        )}
        {deleteError && (
          <p className="space-banner error" role="alert" data-testid="assessments-revision-delete-error">
            {deleteError}
          </p>
        )}
        {deleteGuard && (
          <DeleteGuardNotice
            state={deleteGuard}
            targetName={
              guardTargetRevision ? `v${guardTargetRevision.version}` : shortId(deleteGuard.targetId)
            }
            testId="assessments-revision-delete-guard"
          />
        )}
      </section>

      {activeRevisionIdSafe && (
        <section className="assessments-subpanel" aria-label="只读成绩矩阵">
          <div className="assessments-subpanel-head">
            <h3 title={activeRevisionIdSafe ? `只读矩阵（修订 ${activeRevisionIdSafe}）` : undefined}>
              只读矩阵（{shortId(activeRevisionIdSafe)}）
            </h3>
            {assessmentId && revisions.state.phase === 'ready' && activeRevision?.assessmentId === assessmentId && (
              <Link className="space-button" href={`/learning-analysis?assessmentId=${encodeURIComponent(assessmentId)}&scoreRevisionId=${encodeURIComponent(activeRevision.revisionId)}`}>
                分析这份固定成绩
              </Link>
            )}
            <span className="assessments-hint" data-testid="assessments-matrix-page">
              第 {page + 1} 页 · 共 {totalRows} 人次 · 每页 {ROWS_PER_PAGE}
            </span>
          </div>

          <ScoreStatusLegend testId="score-matrix-legend" />

          {matrix.state.phase === 'failed' && !matrix.lastData && (
            <div className="space-banner error" role="alert" data-testid="assessments-matrix-error">
              矩阵读取失败（{matrix.state.error.code}）：{matrix.state.error.message}
            </div>
          )}

          {matrixPage && (
            <>
              <div className="assessments-actions">
                <span className="space-chip">缺考班 {matrixPage.absentClassIds?.length ?? 0}</span>
                <span className="space-chip amber">
                  空白 {matrixPage.missingCellCount} 单元 / {matrixPage.missingParticipantIds?.length ?? 0} 人次
                </span>
              </div>
              <div className="score-matrix-wrap">
                <table className="score-matrix" data-testid="assessments-matrix">
                  <caption className="visually-hidden">成绩只读矩阵（分页）</caption>
                  <thead>
                    <tr>
                      <th scope="col">人次</th>
                      <th scope="col">出勤</th>
                      {matrixPage.items.map((item) => (
                        <th key={item.itemId} scope="col" data-testid={`assessments-matrix-head-${item.itemId}`}>
                          {item.itemPath}
                          <span className="assessments-meta">
                            满分 {formatScoreUnits(item.maxScoreUnits)}
                          </span>
                        </th>
                      ))}
                      <th scope="col">总分</th>
                    </tr>
                  </thead>
                  <tbody>
                    {matrixPage.rows.map((row) => (
                      <tr
                        key={row.participant.participantId}
                        data-testid={`assessments-matrix-row-${row.participant.participantId}`}
                        data-all-recorded={
                          row.participant.totalUnits === null ? 'false' : 'true'
                        }
                      >
                        <th scope="row">
                          {row.participant.name}
                          <span className="assessments-meta">
                            {row.participant.studentNo ? `学号 ${row.participant.studentNo} · ` : ''}
                            人次 {row.participant.attemptNo}
                          </span>
                        </th>
                        <td>{attendanceLabel(row.participant.attendance)}</td>
                        {row.cells.map((cell) => (
                          <td key={`${row.participant.participantId}-${cell.itemId}`}>
                            <ScoreStatusBadge
                              status={cell.status}
                              text={cellValueText(cell)}
                              testId={`assessments-matrix-cell-${row.participant.participantId}-${cell.itemId}`}
                            />
                          </td>
                        ))}
                        <td data-testid={`assessments-matrix-total-${row.participant.participantId}`}>
                          {matrixRowTotalText(row.participant)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
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
                  disabled={(page + 1) * ROWS_PER_PAGE >= totalRows}
                  onClick={() => setPage((value) => value + 1)}
                >
                  下一页
                </button>
              </div>
            </>
          )}
        </section>
      )}

      {activeRevisionIdSafe && (
        <section className="assessments-subpanel" aria-label="成绩修正">
          <div className="assessments-subpanel-head">
            <h3
              title={activeRevisionId ? `修正（基于当前生效版本 ${activeRevisionId}）` : undefined}
            >
              修正（基于当前生效版本 {activeRevisionId ? shortId(activeRevisionId) : '（无）'}）
            </h3>
            <span className="assessments-hint">
              修正会生成新的完整版本，旧报告仍依据旧版本；审计保留原值/新值/理由/坐标。
            </span>
          </div>
          <p className="assessments-hint">
            当前生效版本：{activeRevision ? `v${activeRevision.version}` : '无'}
            （{activeIsAuthoritative ? '取自施测记录的权威字段' : '推断自最高已确认版本（后端未提供权威字段）'}）；
            修正默认 base 必须等于当前生效版本。
          </p>

          <div className="assessments-form" aria-label="添加修正">
            <label className="assessments-field">
              <span>人次</span>
              <select
                className="space-select"
                aria-label="修正人次"
                disabled={editingLocked}
                value={participantId}
                onChange={(event) => setParticipantId(event.target.value)}
              >
                <option value="">选择人次</option>
                {participantSnapshots.map((participant) => (
                  <option key={participant.participantId} value={participant.participantId}>
                    {participant.name}（{classNames.nameOf(participant.classId)} · 人次{' '}
                    {participant.attemptNo}）
                  </option>
                ))}
              </select>
            </label>
            <label className="assessments-field">
              <span>计分叶</span>
              <select
                className="space-select"
                aria-label="修正计分叶"
                disabled={editingLocked}
                value={itemId}
                onChange={(event) => setItemId(event.target.value)}
              >
                <option value="">选择计分叶</option>
                {itemSnapshots.map((item) => (
                  <option key={item.itemId} value={item.itemId}>
                    {item.itemPath}（满分 {formatScoreUnits(item.maxScoreUnits)}）
                  </option>
                ))}
              </select>
            </label>
            <label className="assessments-field">
              <span>新状态</span>
              <select
                className="space-select"
                aria-label="修正状态"
                disabled={editingLocked}
                value={status}
                onChange={(event) => setStatus(event.target.value as ScoreStatus)}
              >
                {STATUS_OPTIONS.map((option) => (
                  <option key={option} value={option}>
                    {scoreStatusLabel(option)}
                  </option>
                ))}
              </select>
            </label>
            {status === 'recorded' && (
              <label className="assessments-field">
                <span>新分数（十进制文本）</span>
                <input
                  className="assessments-input assessments-input-narrow"
                  aria-label="修正分数"
                  disabled={editingLocked}
                  value={scoreText}
                  onChange={(event) => setScoreText(event.target.value)}
                  placeholder="如 7.5"
                />
              </label>
            )}
            <button className="space-button" type="button" disabled={editingLocked} onClick={addCorrection}>
              <Plus size={13} aria-hidden /> 加入修正列表
            </button>
          </div>

          {corrections.length > 0 && (
            <ul className="assessments-list" aria-label="待提交修正">
              {corrections.map((entry) => (
                <li key={`${entry.participantId}-${entry.itemId}`} className="assessments-list-static">
                  <span title={`人次 ${entry.participantId} · 计分叶 ${entry.itemId}`}>
                    {participantSnapshots.find((item) => item.participantId === entry.participantId)?.name ??
                      shortId(entry.participantId)}{' '}
                    ·{' '}
                    {itemSnapshots.find((item) => item.itemId === entry.itemId)?.itemPath ??
                      shortId(entry.itemId)}{' '}
                    → {scoreStatusLabel(entry.status)}
                    {entry.status === 'recorded' && entry.scoreText ? `（${entry.scoreText} 分）` : ''}
                  </span>
                  <button
                    className="space-button"
                    aria-label={`移除修正 ${entry.itemId}`}
                    disabled={editingLocked}
                    onClick={() =>
                      setCorrections((prev) =>
                        prev.filter(
                          (item) =>
                            !(item.participantId === entry.participantId && item.itemId === entry.itemId),
                        ),
                      )
                    }
                  >
                    移除
                  </button>
                </li>
              ))}
            </ul>
          )}

          <label className="assessments-field">
            <span>修正理由（必填）</span>
            <input
              className="assessments-input"
              aria-label="修正理由"
              disabled={editingLocked}
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>

          <div className="assessments-actions">
            <button
              className="space-button primary"
              data-testid="assessments-correct-submit"
              disabled={
                writingLocked || (submission.phase !== 'unknown' && (corrections.length === 0 || reason.trim() === '' || !activeRevisionId))
              }
              onClick={() => void submitCorrection()}
            >
              {submission.busy ? '提交中…' : '提交修正（生成新版本）'}
            </button>
            {submission.frozen && (
              <span
                className="space-chip"
                title={`提交标识 ${submission.frozen.submissionId}`}
                data-testid="assessments-correct-submission"
              >
                提交标识 {shortId(submission.frozen.submissionId)}
              </span>
            )}
          </div>

          {conflictError && (
            <div className="space-banner error" role="alert" data-testid="assessments-correct-conflict">
              <p>
                修正被拒绝（{conflictError.code}）：{conflictError.message}
                {conflictError.details?.currentRevision !== undefined
                  ? `（当前版本 ${conflictError.details.currentRevision}）`
                  : ''}
                。数据已变化，请刷新对照；你的修正列表已保留。
              </p>
              <button className="space-button" onClick={() => setLocalRefresh((value) => value + 1)}>
                显式刷新对照
              </button>
            </div>
          )}
          {submission.error && !conflictError && (
            <p className="space-banner error" role="alert" data-testid="assessments-correct-error">
              修正失败（{submission.error.code}）：{submission.error.message}
              修正列表已保留，可修正后重试。
            </p>
          )}
          {submission.unknownNotice && (
            <p className="space-banner error" role="alert" data-testid="assessments-correct-unknown">
              {submission.unknownNotice}
            </p>
          )}
          {submission.result && (
            <p
              className="space-banner info"
              role="status"
              title={`修订 ${submission.result.revisionId}${submission.result.replayed ? '' : ` · 基于 ${submission.result.baseRevisionId}`}`}
              data-testid="assessments-correct-result"
            >
              已生成新版本 v{submission.result.version}（修订 {shortId(submission.result.revisionId)}；
              {submission.result.replayed
                ? '重放，未重复写入'
                : `基于 ${shortId(submission.result.baseRevisionId)}`}
              ）。
            </p>
          )}
          {formError && (
            <p className="space-banner error" role="alert">
              {formError}
            </p>
          )}
        </section>
      )}
    </div>
  );
}
