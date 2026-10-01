'use client';

/**
 * 第五步「历史」：成绩修订列表 + 只读矩阵（分页）+ 修正入口。
 *
 * - 矩阵 = 冻结参测人次 × 固定计分叶；`totalUnits` 只在该人次**全员 recorded** 时非空，
 *   含 missing/缺考/免考一律不展示总分（也不用 0 代替）；
 * - 修正 = 从**不可变 base** 复制全矩阵 + 修正当时的参测快照生成新完整版本；
 *   `baseScoreRevisionId` 必须是当前生效版本（本页按最高已确认版本推断；见结果卡契约缺口）；
 * - 修正自身即一次完整确认：`submissionId` 冻结，同载荷重试按幂等处理。
 */

import { useState } from 'react';
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
  getAssessment,
  getScoreMatrix,
  getScoreRevision,
  listScoreRevisions,
} from '@/services/assessments-api';
import { useAsyncResource, useFrozenSubmission } from './hooks';
import {
  attendanceLabel,
  cellValueText,
  formatScoreUnits,
  matrixRowTotalText,
  scoreRevisionStateLabel,
  scoreStatusLabel,
} from './labels';
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
  const submission = useFrozenSubmission<ScoreRevisionCorrectRequest, ScoreRevisionCorrectResult>();

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

  const revisionItems: ScoreRevisionView[] = revisions.lastData?.items ?? [];
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
  const activeRevisionIdSafe = selectedRevisionId ?? activeRevisionId;
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
    const assessmentRevision = detail.lastData?.assessment.revision;
    if (!activeRevisionId || assessmentRevision === undefined || assessmentRevision === null) {
      setFormError('缺少当前生效版本或施测版本，无法修正；请先刷新。');
      return;
    }
    if (reason.trim() === '') {
      setFormError('修正理由必填（审计保留原值/新值/理由/坐标）。');
      return;
    }
    if (corrections.length === 0) {
      setFormError('至少添加一条修正。');
      return;
    }
    const payload: ScoreRevisionCorrectRequest = {
      baseScoreRevisionId: activeRevisionId,
      expectedAssessmentRevision: assessmentRevision,
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
                <span className="assessments-meta">
                  {scoreRevisionStateLabel(revision.state)} · {revision.revisionId} · 人次{' '}
                  {revision.participantSnapshot?.length ?? 0} · 叶{' '}
                  {revision.itemSnapshot?.length ?? 0}
                  {revision.baseRevisionId ? ` · 基于 ${revision.baseRevisionId}` : ' · 首版'}
                  {revision.revisionId === activeRevisionId ? ' · 当前生效' : ''}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      {activeRevisionIdSafe && (
        <section className="assessments-subpanel" aria-label="只读成绩矩阵">
          <div className="assessments-subpanel-head">
            <h3>只读矩阵（{activeRevisionIdSafe}）</h3>
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
            <h3>修正（基于当前生效版本 {activeRevisionId ?? '（无）'}）</h3>
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
                value={participantId}
                onChange={(event) => setParticipantId(event.target.value)}
              >
                <option value="">选择人次</option>
                {participantSnapshots.map((participant) => (
                  <option key={participant.participantId} value={participant.participantId}>
                    {participant.name}（{participant.classId} · 人次 {participant.attemptNo}）
                  </option>
                ))}
              </select>
            </label>
            <label className="assessments-field">
              <span>计分叶</span>
              <select
                className="space-select"
                aria-label="修正计分叶"
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
                  value={scoreText}
                  onChange={(event) => setScoreText(event.target.value)}
                  placeholder="如 7.5"
                />
              </label>
            )}
            <button className="space-button" type="button" onClick={addCorrection}>
              <Plus size={13} aria-hidden /> 加入修正列表
            </button>
          </div>

          {corrections.length > 0 && (
            <ul className="assessments-list" aria-label="待提交修正">
              {corrections.map((entry) => (
                <li key={`${entry.participantId}-${entry.itemId}`} className="assessments-list-static">
                  <span>
                    {participantSnapshots.find((item) => item.participantId === entry.participantId)?.name ??
                      entry.participantId}{' '}
                    ·{' '}
                    {itemSnapshots.find((item) => item.itemId === entry.itemId)?.itemPath ?? entry.itemId}{' '}
                    → {scoreStatusLabel(entry.status)}
                    {entry.status === 'recorded' && entry.scoreText ? `（${entry.scoreText} 分）` : ''}
                  </span>
                  <button
                    className="space-button"
                    aria-label={`移除修正 ${entry.itemId}`}
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
              value={reason}
              onChange={(event) => setReason(event.target.value)}
            />
          </label>

          <div className="assessments-actions">
            <button
              className="space-button primary"
              data-testid="assessments-correct-submit"
              disabled={
                submission.busy || corrections.length === 0 || reason.trim() === '' || !activeRevisionId
              }
              onClick={() => void submitCorrection()}
            >
              {submission.busy ? '提交中…' : '提交修正（生成新版本）'}
            </button>
            {submission.frozen && (
              <span className="space-chip" data-testid="assessments-correct-submission">
                提交标识 {submission.frozen.submissionId}
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
            <p className="space-banner info" role="status" data-testid="assessments-correct-result">
              已生成新版本 v{submission.result.version}（修订 {submission.result.revisionId}；
              {submission.result.replayed ? '重放，未重复写入' : `基于 ${submission.result.baseRevisionId}`}）。
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
