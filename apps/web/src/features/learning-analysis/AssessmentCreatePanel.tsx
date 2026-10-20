'use client';

/**
 * 新建施测（闭环补齐 2026-10-13）：修复「导入的试卷在学情分析里看不到」。
 *
 * 数据模型：学情分析顶部「试卷」下拉列的是**施测**（班级 × 原卷修订的一次具体考试），
 * 它是成绩链的所有者——参测人次、成绩导入、成绩修订、学情报告、派生练习都挂在它下面。
 * 原卷入库只代表卷子可用，不等于它已施测；此前界面没有任何建施测的入口，导入并确认的
 * 原卷因此进不了学情分析。本面板补这一环：挑**已确认**的原卷 + 一个班级，把该班在册学生
 * 一次性列为参测人次，创建后施测即出现在「试卷」下拉里。
 *
 * 口径（跟随后端，不发明）：
 * - 只列 `currentState === 'confirmed'` 的原卷：草稿会被服务端 422 拒绝，界面不提前放行；
 * - 参测名单 = 该班 `status === 'active'` 的成员；姓名/学号由服务端按 `studentId` 读取后
 *   冻结，前端不送姓名，也不把读失败当空名单；
 * - 「显式确认本次班级」用于归属历史未覆盖施测日期的场景（例如补录历史考试）：勾选后随行送
 *   `classConfirmed + classConfirmationNote`，服务端不会自动改归属历史；不勾选时由服务端
 *   按归属覆盖判定，未覆盖就以 422 逐行给出原因（原样展示）；
 * - 创建是逻辑确认（冻结 `submissionId` + 原样载荷）：结果未知时重试复用同一标识，
 *   幂等不重复建；成功后由调用方刷新施测列表并选中新施测。
 */

import { useEffect, useMemo, useState } from 'react';
import { Plus, X } from 'lucide-react';
import type {
  AssessmentCreateResult,
  AssessmentType,
  ClassView,
} from '@/contracts/learning-analysis';
import { learningAnalysisApi as api } from '@/services/learning-analysis-api';
import { Modal } from '@/components/ui/Modal';
import { useAsyncResource, useFrozenSubmission } from './score-hooks';
import { shortId } from './score-labels';

const TYPE_OPTIONS: readonly { id: AssessmentType; label: string }[] = [
  { id: 'exam', label: '考试' },
  { id: 'quiz', label: '测验' },
  { id: 'practice', label: '练习' },
];

const HELD_ON_PATTERN = /^\d{4}-\d{2}-\d{2}$/;

/** 本地日期（YYYY-MM-DD）：施测日期默认今天（在事件里取，渲染期不读时钟）。 */
function todayIso(): string {
  const now = new Date();
  const pad = (value: number) => String(value).padStart(2, '0');
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

/** 逻辑确认冻结的原样载荷：重试必须按它原样重发（不随后续表单编辑偷换）。 */
interface CreatePayload {
  paperRevisionId: string;
  title: string;
  assessmentType: AssessmentType;
  heldOn: string;
  classId: string;
  studentIds: string[];
  classConfirmed: boolean;
  classConfirmationNote: string;
}

export interface AssessmentCreatePanelProps {
  /** 班级目录由页面统一读取（避免重复请求）；读取失败时面板显式说明并禁用提交。 */
  classes: readonly ClassView[];
  classesFailed: boolean;
  onCreated: (result: AssessmentCreateResult) => void;
  onClose: () => void;
}

export function AssessmentCreatePanel({
  classes,
  classesFailed,
  onCreated,
  onClose,
}: AssessmentCreatePanelProps) {
  const papers = useAsyncResource(
    (signal) => api.listPapers({ limit: 200 }, signal),
    'la-create-assessment-papers',
  );
  /** 可建施测的原卷：只有已确认入库的修订（草稿没有可用的固定拆题）。 */
  const confirmedPapers = useMemo(
    () =>
      (papers.lastData?.items ?? []).filter(
        (item) =>
          item.currentState === 'confirmed' &&
          typeof item.currentRevisionId === 'string' &&
          item.currentRevisionId !== '',
      ),
    [papers.lastData],
  );

  const [paperId, setPaperId] = useState('');
  const [classId, setClassId] = useState('');
  const [titleDraft, setTitleDraft] = useState('');
  const [assessmentType, setAssessmentType] = useState<AssessmentType>('exam');
  const [heldOn, setHeldOn] = useState(todayIso);
  const [confirmClass, setConfirmClass] = useState(false);
  const [confirmNote, setConfirmNote] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);

  // 默认选中第一份已确认原卷；列表刷新后原选择失效（已删/转回草稿）时同样回落。
  useEffect(() => {
    if (confirmedPapers.length === 0) return;
    if (!confirmedPapers.some((item) => item.paperId === paperId)) {
      setPaperId(confirmedPapers[0].paperId);
    }
  }, [confirmedPapers, paperId]);

  const selectedPaper = confirmedPapers.find((item) => item.paperId === paperId) ?? null;

  const students = useAsyncResource(
    (signal) => (classId ? api.listClassStudents(classId, signal) : Promise.resolve(null)),
    `la-create-assessment-students|${classId || 'none'}`,
  );
  const activeStudents = (students.lastData?.items ?? []).filter(
    (student) => student.status === 'active',
  );

  const confirmation = useFrozenSubmission<CreatePayload, AssessmentCreateResult>();
  /** 在途禁用；「结果未知」保持可点：重试按冻结标识与原样载荷幂等重发（不换标识重做）。 */
  const busy = confirmation.busy;

  async function submit() {
    if (busy) return;
    const paper = selectedPaper;
    if (!paper?.currentRevisionId) {
      setLocalError('请先选择一份已确认入库的原卷；没有的话先到「试卷管理」导入并确认原卷入库。');
      return;
    }
    if (!classId) {
      setLocalError('请选择本次施测的班级（参测名单取该班在册学生）。');
      return;
    }
    const title = titleDraft.trim() || paper.title;
    if (!title) {
      setLocalError('施测名称不能为空。');
      return;
    }
    if (!HELD_ON_PATTERN.test(heldOn)) {
      setLocalError('施测日期要写成 YYYY-MM-DD。');
      return;
    }
    if (students.state.phase !== 'ready') {
      setLocalError('参测名单尚未读取完成（或读取失败）：请等名单读回成功再创建，不把失败当空名单。');
      return;
    }
    if (activeStudents.length === 0) {
      setLocalError('该班没有在册学生：先到「班级管理」导入名单，再回来建施测。');
      return;
    }
    if (confirmClass && confirmNote.trim() === '') {
      setLocalError('勾选「显式确认本次班级」时必须填写依据（服务端要求 classConfirmationNote）。');
      return;
    }
    setLocalError(null);
    const payload: CreatePayload = {
      paperRevisionId: paper.currentRevisionId,
      title,
      assessmentType,
      heldOn,
      classId,
      studentIds: activeStudents.map((student) => student.id),
      classConfirmed: confirmClass,
      classConfirmationNote: confirmNote.trim(),
    };
    const result = await confirmation.submit(payload, (frozen) =>
      api.createAssessment({
        submissionId: frozen.submissionId,
        paperRevisionId: frozen.payload.paperRevisionId,
        title: frozen.payload.title,
        assessmentType: frozen.payload.assessmentType,
        heldOn: frozen.payload.heldOn,
        classIds: [frozen.payload.classId],
        participants: frozen.payload.studentIds.map((studentId) => ({
          studentId,
          classId: frozen.payload.classId,
          ...(frozen.payload.classConfirmed
            ? {
                classConfirmed: true,
                classConfirmationNote: frozen.payload.classConfirmationNote,
              }
            : {}),
        })),
      }),
    );
    if (result) onCreated(result);
  }

  const error = confirmation.error;
  const formError = localError
    ? localError
    : error
      ? `新建施测失败（${error.code}）：${error.message}`
      : null;

  return (
    <Modal title="新建施测" onClose={onClose}>
      <form
        className="assessments-form"
        aria-label="新建施测"
        data-testid="la-create-assessment"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <p className="assessments-hint">
          「试卷」下拉里列的是施测（班级 × 原卷的一次具体考试），它是成绩链的所有者；
          原卷确认入库后还要建一场施测，才能导入小题分并生成学情报告。
        </p>

        {papers.state.phase === 'failed' && (
          <p className="space-banner error" role="alert" data-testid="la-create-papers-error">
            原卷目录读取失败（{papers.state.error.code}）：{papers.state.error.message}
            这不是「没有已确认试卷」。
            <button className="space-button" type="button" onClick={papers.reload}>
              重试读取原卷
            </button>
          </p>
        )}
        {papers.state.phase === 'ready' && confirmedPapers.length === 0 && (
          <p className="space-empty" data-testid="la-create-no-paper">
            <strong>没有可用的已确认原卷</strong>
            <span>先到「试卷管理」导入试卷，校对拆题并点击「确认原卷入库」，再回来建施测。</span>
          </p>
        )}

        <label className="assessments-field">
          <span>原卷（已确认入库）</span>
          <select
            className="space-select"
            aria-label="新建施测原卷"
            value={paperId}
            disabled={busy || confirmedPapers.length === 0}
            onChange={(event) => setPaperId(event.target.value)}
          >
            {confirmedPapers.length === 0 && <option value="">（没有已确认原卷）</option>}
            {confirmedPapers.map((paper) => (
              <option key={paper.paperId} value={paper.paperId}>
                {paper.title} · v{paper.version} · 计分叶 {paper.scoredLeafCount}
              </option>
            ))}
          </select>
        </label>

        <label className="assessments-field">
          <span>班级（参测名单取该班在册学生）</span>
          <select
            className="space-select"
            aria-label="新建施测班级"
            value={classId}
            disabled={busy || classesFailed}
            onChange={(event) => setClassId(event.target.value)}
          >
            <option value="">请选择班级</option>
            {classes.map((item) => (
              <option key={item.id} value={item.id}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        {classesFailed && (
          <p className="space-banner error" role="alert" data-testid="la-create-classes-error">
            班级目录读取失败：没有班级无法建施测（参测名单按班读取）。请先修复上方班级筛选的重试。
          </p>
        )}
        {classId && students.state.phase === 'failed' && (
          <p className="space-banner error" role="alert" data-testid="la-create-students-error">
            参测名单读取失败（{students.state.error.code}）：{students.state.error.message}
            这不是「该班没有学生」。
            <button className="space-button" type="button" onClick={students.reload}>
              重试读取名单
            </button>
          </p>
        )}
        {classId && students.state.phase === 'ready' && (
          <p className="assessments-hint" data-testid="la-create-participant-count">
            将把该班 {activeStudents.length} 名在册学生列为参测人次（共{' '}
            {students.lastData?.total ?? 0} 名成员，已排除已移除学生）；姓名/学号由服务端按学生
            id 读取后冻结。
          </p>
        )}

        <label className="assessments-field">
          <span>施测名称</span>
          <input
            className="assessments-input"
            aria-label="新建施测名称"
            placeholder={selectedPaper ? selectedPaper.title : ''}
            value={titleDraft}
            disabled={busy}
            onChange={(event) => setTitleDraft(event.target.value)}
          />
        </label>

        <div className="assessments-mapping-grid">
          <label className="assessments-field">
            <span>类型</span>
            <select
              className="space-select"
              aria-label="新建施测类型"
              value={assessmentType}
              disabled={busy}
              onChange={(event) => setAssessmentType(event.target.value as AssessmentType)}
            >
              {TYPE_OPTIONS.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="assessments-field">
            <span>施测日期</span>
            <input
              className="assessments-input assessments-input-narrow"
              type="date"
              aria-label="新建施测日期"
              value={heldOn}
              disabled={busy}
              onChange={(event) => setHeldOn(event.target.value)}
            />
          </label>
        </div>

        <label className="assessments-check">
          <input
            type="checkbox"
            aria-label="显式确认本次班级"
            checked={confirmClass}
            disabled={busy}
            onChange={(event) => setConfirmClass(event.target.checked)}
          />
          <span>
            显式确认本次班级（仅当该班归属记录未覆盖施测日期时需要，例如补录历史考试；
            服务端不会自动改归属历史）
          </span>
        </label>
        {confirmClass && (
          <label className="assessments-field">
            <span>确认依据（必填）</span>
            <input
              className="assessments-input"
              aria-label="班级确认依据"
              value={confirmNote}
              disabled={busy}
              onChange={(event) => setConfirmNote(event.target.value)}
            />
          </label>
        )}

        {formError && (
          <p className="space-banner error" role="alert" data-testid="la-create-error">
            {formError}
          </p>
        )}
        {error?.details?.issues && error.details.issues.length > 0 && (
          <ul className="assessments-issue-list" data-testid="la-create-issues">
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
          <p className="space-banner" role="status" data-testid="la-create-unknown">
            {confirmation.unknownNotice}
          </p>
        )}

        <div className="assessments-form-footer">
          <button className="space-button" type="button" disabled={busy} onClick={onClose}>
            <X size={14} aria-hidden /> 取消
          </button>
          <button
            className="space-button primary"
            type="submit"
            disabled={busy || confirmedPapers.length === 0 || classesFailed}
            data-testid="la-create-submit"
          >
            <Plus size={14} aria-hidden />
            {confirmation.busy
              ? '创建中…'
              : confirmation.phase === 'unknown'
                ? '重试创建施测'
                : '创建施测'}
          </button>
        </div>
        <p className="assessments-hint">
          提交标识随本次编辑冻结：结果未知时重试会复用同一标识，服务端幂等处理、不会重复建。
          {selectedPaper ? ` 当前原卷修订 ${shortId(selectedPaper.currentRevisionId)}。` : ''}
        </p>
      </form>
    </Modal>
  );
}

export default AssessmentCreatePanel;
