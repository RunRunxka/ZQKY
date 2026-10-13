'use client';

/**
 * 生成学情报告（闭环补齐 2026-10-13）：补齐「已确认小题分 → 学情报告」的界面入口。
 *
 * 此前学情分析页只读既有报告（「报告由后端创建、本页只读取」，后端已就绪但界面无入口），
 * 教师从导入小题分到看到五图之间是死路。本面板对**所选施测**的已确认成绩修订生成报告：
 * - 人次取自该修订的 `participantSnapshot`（服务端按冻结快照逐项校验：不属于该修订 / 重复
 *   人次 / 同学生重复都会 422；前端不替它猜，也不因快照缺失而擅自选人次）；
 * - 同输入已有报告时服务端直接复用同一 `runId`（`reused`），同提交标识重放（`replayed`）
 *   也不重复建；
 * - 报告由后台任务计算：受理后由调用方刷新报告列表，`reportReady` 就绪后才读五图
 *   （未就绪时列表与详情会显式标注「尚未准备」，不画空图）。
 */

import { useMemo, useState } from 'react';
import { FilePlus2, X } from 'lucide-react';
import type {
  AnalysisRunReceipt,
  ScoreRevisionView,
} from '@/contracts/learning-analysis';
import { learningAnalysisApi as api } from '@/services/learning-analysis-api';
import { useAsyncResource, useFrozenSubmission } from './score-hooks';
import { shortId } from './score-labels';

/** 逻辑确认冻结的原样载荷：重试必须按它原样重发（不随后续选择偷换）。 */
interface CreateRunPayload {
  scoreRevisionId: string;
  participantIds: string[];
}

export interface AnalysisRunCreatePanelProps {
  /** 报告挂载的施测（必填：报告只能从一场施测的已确认成绩修订生成）。 */
  assessmentId: string;
  /** 施测当前生效的成绩修订（若有）：是已确认修订时默认选中它。 */
  activeScoreRevisionId?: string | null;
  onCreated: (receipt: AnalysisRunReceipt) => void;
  onClose: () => void;
}

function revisionLabel(revision: ScoreRevisionView): string {
  const stamp = revision.confirmedAt?.slice(0, 10) ?? revision.createdAt.slice(0, 10);
  const participants = revision.participantSnapshot?.length;
  return `v${revision.version} · ${shortId(revision.revisionId)} · ${
    participants === undefined ? '人次未知' : `${participants} 人次`
  } · ${stamp}`;
}

export function AnalysisRunCreatePanel({
  assessmentId,
  activeScoreRevisionId = null,
  onCreated,
  onClose,
}: AnalysisRunCreatePanelProps) {
  const revisions = useAsyncResource(
    (signal) => api.listScoreRevisions(assessmentId, signal),
    `la-create-run-revisions|${assessmentId}`,
  );
  const confirmedRevisions = useMemo(
    () => (revisions.lastData?.items ?? []).filter((revision) => revision.state === 'confirmed'),
    [revisions.lastData],
  );

  const [revisionDraft, setRevisionDraft] = useState<string | null>(null);
  const [localError, setLocalError] = useState<string | null>(null);
  const confirmation = useFrozenSubmission<CreateRunPayload, AnalysisRunReceipt>();
  const busy = confirmation.busy;

  /**
   * 默认选中：施测当前生效的正式成绩版本（已确认时）；否则版本号最大的已确认修订。
   * 选择是**派生**的（不是 effect 里同步 state）：列表刷新后原选择失效（已删/已失效）时
   * 立即回落到默认值，不把旧选择留给服务端，也不存在「渲染与选中之间」的空窗。
   */
  const fallbackRevisionId = useMemo(() => {
    if (confirmedRevisions.length === 0) return '';
    const preferred = confirmedRevisions.find(
      (revision) => revision.revisionId === activeScoreRevisionId,
    );
    return (preferred ?? confirmedRevisions[confirmedRevisions.length - 1]).revisionId;
  }, [confirmedRevisions, activeScoreRevisionId]);
  const revisionId =
    revisionDraft !== null && confirmedRevisions.some((item) => item.revisionId === revisionDraft)
      ? revisionDraft
      : fallbackRevisionId;

  const selectedRevision =
    confirmedRevisions.find((revision) => revision.revisionId === revisionId) ?? null;
  const participantIds = selectedRevision?.participantSnapshot?.map((item) => item.participantId);

  async function submit() {
    if (busy) return;
    if (!selectedRevision) {
      setLocalError('请选择要生成报告的已确认成绩修订。');
      return;
    }
    if (!participantIds || participantIds.length === 0) {
      setLocalError(
        selectedRevision.participantSnapshot === undefined
          ? '服务端未返回该成绩版本的人次快照：无法确定分析人次。请点「刷新报告」重试读取，或换一个版本。'
          : '该成绩版本的人次快照为空：没有可分析的人次，请先检查小题分导入与确认结果。',
      );
      return;
    }
    setLocalError(null);
    const payload: CreateRunPayload = {
      scoreRevisionId: selectedRevision.revisionId,
      participantIds,
    };
    const receipt = await confirmation.submit(payload, (frozen) =>
      api.createAnalysisRun(assessmentId, {
        submissionId: frozen.submissionId,
        scoreRevisionId: frozen.payload.scoreRevisionId,
        selectedParticipantIds: frozen.payload.participantIds,
        ruleCode: 'any_loss_v1',
      }),
    );
    if (receipt) onCreated(receipt);
  }

  const error = confirmation.error;
  const formError = localError
    ? localError
    : error
      ? `生成学情报告失败（${error.code}）：${error.message}`
      : null;

  return (
    <section
      className="assessments-panel"
      aria-label="生成学情报告"
      data-testid="la-create-run-panel"
    >
      <div className="assessments-subpanel-head">
        <h3>
          <FilePlus2 size={15} aria-hidden /> 生成学情报告
        </h3>
        <button className="space-button" aria-label="关闭生成报告面板" onClick={onClose}>
          <X size={14} aria-hidden /> 关闭
        </button>
      </div>
      <p className="assessments-hint">
        从该施测已确认的小题分成绩修订生成报告（分析口径固定在这个版本上，不随成绩修正而变）。
        人次取自该版本的人次快照；同一成绩版本重复生成会直接复用已有报告，不重复建。
      </p>

      {revisions.state.phase === 'failed' && (
        <div className="space-banner error" role="alert" data-testid="la-create-run-revisions-error">
          成绩修订列表读取失败（{revisions.state.error.code}）：{revisions.state.error.message}
          这不是「没有已确认成绩」。
          <button className="space-button" onClick={revisions.reload}>
            重试读取
          </button>
        </div>
      )}
      {revisions.state.phase === 'loading' && <p className="assessments-hint">正在读取成绩修订…</p>}
      {revisions.state.phase === 'ready' && confirmedRevisions.length === 0 && (
        <p className="space-empty" data-testid="la-create-run-no-revision">
          <strong>该施测还没有已确认的小题分成绩</strong>
          <span>先在「导入小题分」里上传成绩表、校对列映射与四态，并完成整批确认，再回来生成报告。</span>
        </p>
      )}

      {confirmedRevisions.length > 0 && (
        <>
          <label className="assessments-field">
            <span>成绩修订（已确认）</span>
            <select
              className="space-select"
              aria-label="生成报告的成绩修订"
              value={revisionId}
              disabled={busy}
              onChange={(event) => setRevisionDraft(event.target.value)}
            >
              {confirmedRevisions.map((revision) => (
                <option key={revision.revisionId} value={revision.revisionId}>
                  {revisionLabel(revision)}
                </option>
              ))}
            </select>
          </label>
          {selectedRevision && (
            <p className="assessments-hint" data-testid="la-create-run-participant-count">
              将对该版本的 {participantIds?.length ?? '—'} 个人次生成班级学情图表与 AI 评价
              （学生以代称进模型，不传姓名/学号）。
            </p>
          )}
          <div className="assessments-actions">
            <button
              className="space-button primary"
              disabled={busy}
              data-testid="la-create-run-submit"
              onClick={() => void submit()}
            >
              <FilePlus2 size={13} aria-hidden />
              {confirmation.busy
                ? '生成中…'
                : confirmation.phase === 'unknown'
                  ? '重试生成报告'
                  : '生成学情报告'}
            </button>
          </div>
        </>
      )}

      {formError && (
        <p className="space-banner error" role="alert" data-testid="la-create-run-error">
          {formError}
        </p>
      )}
      {error?.details?.issues && error.details.issues.length > 0 && (
        <ul className="assessments-issue-list" data-testid="la-create-run-issues">
          {error.details.issues.map((issue, index) => (
            // 服务端 issues 的定位已在 message 里（「第 N 个参测行…」）；`row` 是 0 基下标，
            // 这里不再叠一层行号标签，避免把「第 0 行」这种口径外的话说给教师。
            <li key={index}>
              {issue.code}：{issue.message}
            </li>
          ))}
        </ul>
      )}
      {confirmation.unknownNotice && (
        <p className="space-banner" role="status" data-testid="la-create-run-unknown">
          {confirmation.unknownNotice}
        </p>
      )}
    </section>
  );
}

export default AnalysisRunCreatePanel;
