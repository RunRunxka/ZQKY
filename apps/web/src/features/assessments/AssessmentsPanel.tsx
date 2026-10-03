'use client';

/**
 * 第三步「施测」：真实创建/查看施测（标题/类型/日期/班级/参测人次）。
 *
 * - 只接受已确认原卷修订（第一步原卷的选择）；`submissionId` 冻结：同载荷重试命中幂等，
 *   结果未知时不换标识（`hooks.ts` 的 `useFrozenSubmission`）；
 * - 参测人次默认全部出勤、每人 1 次；可逐人改出勤（缺考/免考）与人次序号；
 * - `PARTICIPANT_CLASS_UNCONFIRMED`（422，`issues[].row` 是参测人次列表的 0 基下标）：
 *   逐行列出受影响学生，必须由教师**显式确认本次班级**并填写依据，才带
 *   `classConfirmed=true + classConfirmationNote` 重新提交；不自动改归属。
 */

import { useEffect, useRef, useState } from 'react';
import { ClipboardList, RefreshCw } from 'lucide-react';
import type {
  AssessmentCreateRequest,
  AssessmentCreateResult,
  AssessmentDetailView,
  AssessmentParticipantInput,
  AssessmentType,
  AssessmentView,
} from '@/contracts/assessments';
import type { Attendance, StudentView } from '@/contracts/roster';
import {
  createAssessment,
  getAssessment,
  listAssessments,
  listClassStudents,
} from '@/services/assessments-api';
import { useAsyncResource, useFrozenSubmission } from './hooks';
import { assessmentStateLabel, assessmentTypeLabel, attendanceLabel, issueLocationLabel } from './labels';
import type { SelectedPaper } from './PapersPanel';
import { ParticipantAttendanceEditor } from './ParticipantAttendanceEditor';
import { ParticipantAddPanel } from './ParticipantAddPanel';

const TYPE_OPTIONS: { value: AssessmentType; label: string }[] = [
  { value: 'exam', label: '考试' },
  { value: 'quiz', label: '测验' },
  { value: 'practice', label: '练习' },
];

const ATTENDANCE_OPTIONS: { value: Attendance; label: string }[] = [
  { value: 'present', label: '出勤' },
  { value: 'absent', label: '缺考' },
  { value: 'exempt', label: '免考' },
];

function todayText(): string {
  const now = new Date();
  const month = String(now.getMonth() + 1).padStart(2, '0');
  const day = String(now.getDate()).padStart(2, '0');
  return `${now.getFullYear()}-${month}-${day}`;
}

interface ParticipantDraft {
  checked: boolean;
  attendance: Attendance;
  attemptNo: number;
}

export function AssessmentsPanel({
  selectedPaper,
  classId,
  className,
  selectedAssessmentId,
  onSelectAssessment,
  onOpenScore,
  refreshToken,
  rosterRefreshToken = 0,
  onChanged,
}: {
  selectedPaper: SelectedPaper | null;
  classId: string | null;
  className: string | null;
  selectedAssessmentId: string | null;
  onSelectAssessment: (assessmentId: string) => void;
  onOpenScore: () => void;
  refreshToken: number;
  rosterRefreshToken?: number;
  onChanged: () => void;
}) {
  const [title, setTitle] = useState('');
  const [assessmentType, setAssessmentType] = useState<AssessmentType>('exam');
  const [heldOn, setHeldOn] = useState(todayText());
  const [drafts, setDrafts] = useState<Record<string, ParticipantDraft>>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [classNote, setClassNote] = useState('');
  const [created, setCreated] = useState<AssessmentCreateResult | null>(null);
  const [rosterNotice, setRosterNotice] = useState<string | null>(null);
  const submission = useFrozenSubmission<Record<string, unknown>, AssessmentCreateResult>();
  const editingLocked = submission.busy || submission.phase === 'unknown';
  const context = `${classId ?? ''}|${selectedPaper?.paperRevisionId ?? ''}|${selectedAssessmentId ?? ''}`;
  const contextRef = useRef(context);
  contextRef.current = context;

  const students = useAsyncResource(
    (signal) =>
      classId
        ? listClassStudents(classId, signal)
        : Promise.resolve({ items: [], total: 0, offset: 0, limit: 50 }),
    `assessments-step3-students|${classId ?? 'none'}`,
  );
  // 名单步骤保持挂载；已确认的新增/导入/转班通知触发同 key 读回，保留合法人次草稿。
  const reloadStudents = students.reload;
  useEffect(() => {
    reloadStudents();
  }, [rosterRefreshToken, reloadStudents]);
  const previousStudents = useRef<Map<string, StudentView>>(new Map());
  useEffect(() => {
    if (students.state.phase !== 'ready' || !students.lastData) return;
    const nextIds = new Set(students.lastData.items.map((student) => student.id));
    const removed = Array.from(previousStudents.current.values()).filter((student) => !nextIds.has(student.id));
    if (removed.length > 0) {
      setDrafts((previous) => Object.fromEntries(
        Object.entries(previous).filter(([studentId]) => nextIds.has(studentId)),
      ));
      setRosterNotice(`名单已更新：${removed.map((student) => student.name).join('、')}已不在本班当前名单，已撤销其参测选择及人次草稿；其余选择、出勤和人次已保留。`);
    }
    previousStudents.current = new Map(students.lastData.items.map((student) => [student.id, student]));
  }, [students.state, students.lastData]);
  const assessments = useAsyncResource(
    (signal) => listAssessments({ classId: classId ?? undefined, limit: 100 }, signal),
    `assessments-step3-list|${classId ?? 'all'}|${refreshToken}`,
  );
  const detail = useAsyncResource(
    (signal) =>
      selectedAssessmentId
        ? getAssessment(selectedAssessmentId, signal)
        : Promise.resolve(null),
    `assessments-step3-detail|${selectedAssessmentId ?? 'none'}|${refreshToken}`,
  );

  const studentItems: StudentView[] = students.lastData?.items ?? [];
  const assessmentItems: AssessmentView[] = assessments.lastData?.items ?? [];

  const draftOf = (studentId: string): ParticipantDraft =>
    drafts[studentId] ?? { checked: true, attendance: 'present', attemptNo: 1 };

  const participants: AssessmentParticipantInput[] = classId
    ? studentItems
        .filter((student) => draftOf(student.id).checked)
        .map((student) => {
          const draft = draftOf(student.id);
          return {
            studentId: student.id,
            classId,
            attendance: draft.attendance,
            attemptNo: draft.attemptNo,
          };
        })
    : [];

  /** 提交载荷不含 submissionId：标识由逻辑确认冻结后注入（同载荷重试才能命中幂等）。 */
  function buildPayload(confirmNote: string | null, confirmedIndexes: number[]): Record<string, unknown> {
    return {
      paperRevisionId: selectedPaper?.paperRevisionId ?? null,
      title: title.trim(),
      assessmentType,
      heldOn,
      classIds: classId ? [classId] : [],
      participants: participants.map((participant, index) =>
        confirmNote !== null && confirmedIndexes.includes(index)
          ? {
              ...participant,
              classConfirmed: true,
              classConfirmationNote: confirmNote,
            }
          : participant,
      ),
    };
  }

  async function submitCreate(confirmedIndexes: number[] = []) {
    setFormError(null);
    const frozenPayload = submission.phase === 'unknown' ? submission.frozen?.payload : null;
    if (!frozenPayload && !selectedPaper) {
      setFormError('还没有选定已确认原卷修订：请先在「原卷」步骤选用。');
      return;
    }
    if (!frozenPayload && !classId) {
      setFormError('还没有选择班级：请先在「名单」步骤选择或建立班级。');
      return;
    }
    if (!frozenPayload && students.state.phase !== 'ready') {
      setFormError('参测名单正在读取或读取失败，请重试并核对名单后创建施测。');
      return;
    }
    if (!frozenPayload && participants.length === 0) {
      setFormError('参测人次为空：请至少勾选一名学生（缺考也要按人次登记）。');
      return;
    }
    const note = confirmedIndexes.length > 0 ? classNote.trim() : null;
    if (!frozenPayload && confirmedIndexes.length > 0 && !note) {
      setFormError('显式确认本次班级必须填写依据（classConfirmationNote）。');
      return;
    }
    const payload = frozenPayload ?? buildPayload(note, confirmedIndexes);
    const requestContext = contextRef.current;
    const result = await submission.submit(payload, (frozen) =>
      createAssessment({
        ...(frozen.payload as unknown as AssessmentCreateRequest),
        submissionId: frozen.submissionId,
      }),
    );
    // submit 先验证挂载和操作代次；失效请求不能先改变父级选择。
    if (result && contextRef.current === requestContext) {
      setCreated(result);
      onSelectAssessment(result.assessment.assessmentId);
      onChanged();
    }
  }

  // 422 班级归属未确认：解析 issues[].row（0 基下标）定位到学生
  const classConflict =
    submission.error?.code === 'PARTICIPANT_CLASS_UNCONFIRMED' ? submission.error : null;

  return (
    <div className="assessments-panel" data-testid="assessments-assessments-panel">
      <section className="assessments-subpanel" aria-label="新建施测">
        <div className="assessments-subpanel-head">
          <h3>
            <ClipboardList size={15} aria-hidden /> 新建施测
          </h3>
          <span className="assessments-hint">
            原卷：{selectedPaper ? `${selectedPaper.title}（${selectedPaper.paperRevisionId}）` : '未选用'}
          </span>
        </div>

        <form
          className="assessments-form"
          aria-label="新建施测"
          onSubmit={(event) => {
            event.preventDefault();
            void submitCreate([]);
          }}
        >
          <label className="assessments-field">
            <span>标题</span>
            <input
              className="assessments-input"
              aria-label="施测标题"
              disabled={editingLocked}
              value={title}
              onChange={(event) => setTitle(event.target.value)}
              required
            />
          </label>
          <label className="assessments-field">
            <span>类型</span>
            <select
              className="space-select"
              aria-label="施测类型"
              disabled={editingLocked}
              value={assessmentType}
              onChange={(event) => setAssessmentType(event.target.value as AssessmentType)}
            >
              {TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </select>
          </label>
          <label className="assessments-field">
            <span>日期</span>
            <input
              className="assessments-input"
              type="date"
              aria-label="施测日期"
              disabled={editingLocked}
              value={heldOn}
              onChange={(event) => setHeldOn(event.target.value)}
              required
            />
          </label>
          <span className="assessments-field-static">
            班级：{className ?? '（未选择）'} · 参测 {participants.length} 人次
          </span>
          <button className="space-button primary" type="submit" disabled={submission.busy || (submission.phase !== 'unknown' && students.state.phase !== 'ready')}>
            {submission.busy ? '创建中…' : '创建施测'}
          </button>
        </form>

        <button className="space-button" disabled={!classId} onClick={students.reload}>刷新参测名单</button>
        {students.state.phase === 'loading' && <p className="assessments-hint" role="status">正在刷新参测名单，已有合法人次草稿保留。</p>}
        {students.state.phase === 'failed' && <p className="space-banner error" role="alert" data-testid="assessments-roster-error">
          参测名单读取失败（{students.state.error.code}）：{students.state.error.message}。已有选择和人次草稿保留，请刷新参测名单对照。
        </p>}
        {rosterNotice && <p className="assessments-hint" role="status" data-testid="assessments-roster-notice">{rosterNotice}</p>}

        {studentItems.length === 0 && classId && students.state.phase === 'ready' && (
          <p className="assessments-hint" data-testid="assessments-step3-no-students">
            该班还没有学生：回到「名单」步骤添加学生后再创建施测。
          </p>
        )}

        {studentItems.length > 0 && (
          <fieldset className="assessments-participants" aria-label="参测人次">
            <legend>参测人次（缺考也要按人次登记）</legend>
            {studentItems.map((student) => {
              const draft = draftOf(student.id);
              return (
                <div key={student.id} className="assessments-participant-row" data-testid={`assessments-participant-${student.id}`}>
                  <label className="assessments-check">
                    <input
                      type="checkbox"
                      aria-label={`参测 ${student.name}`}
                      checked={draft.checked}
                      disabled={editingLocked}
                      onChange={(event) =>
                        setDrafts((prev) => ({
                          ...prev,
                          [student.id]: { ...draftOf(student.id), checked: event.target.checked },
                        }))
                      }
                    />
                    <span>
                      {student.name}
                      <span className="assessments-meta">
                        {student.studentNo ? ` · 学号 ${student.studentNo}` : ' · 无学号'}
                      </span>
                    </span>
                  </label>
                  <label className="assessments-field assessments-field-inline">
                    <span>出勤</span>
                    <select
                      className="space-select"
                      aria-label={`${student.name} 出勤`}
                      value={draft.attendance}
                      disabled={!draft.checked || editingLocked}
                      onChange={(event) =>
                        setDrafts((prev) => ({
                          ...prev,
                          [student.id]: {
                            ...draftOf(student.id),
                            attendance: event.target.value as Attendance,
                          },
                        }))
                      }
                    >
                      {ATTENDANCE_OPTIONS.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="assessments-field assessments-field-inline">
                    <span>人次</span>
                    <input
                      className="assessments-input assessments-input-narrow"
                      type="number"
                      min={1}
                      aria-label={`${student.name} 人次序号`}
                      value={draft.attemptNo}
                      disabled={!draft.checked || editingLocked}
                      onChange={(event) =>
                        setDrafts((prev) => ({
                          ...prev,
                          [student.id]: {
                            ...draftOf(student.id),
                            attemptNo: Number(event.target.value) || 1,
                          },
                        }))
                      }
                    />
                  </label>
                </div>
              );
            })}
          </fieldset>
        )}

        {classConflict && (
          <div className="space-banner error" role="alert" data-testid="assessments-class-unconfirmed">
            <p>
              班级归属未确认（{classConflict.code}）：{classConflict.message}
            </p>
            <ul className="assessments-issue-list">
              {(classConflict.details?.issues ?? []).map((issue, index) => (
                <li key={`${issue.code}-${index}`}>
                  {issueLocationLabel(issue)}
                  {issue.message}
                  {typeof issue.row === 'number' && studentItems[issue.row] && (
                    <strong> → {studentItems[issue.row].name}</strong>
                  )}
                </li>
              ))}
            </ul>
            <p className="assessments-hint">
              不会自动修改归属历史：请确认这些人次在本次日期下确实属于本班，填写依据后显式确认。
            </p>
            <label className="assessments-field">
              <span>确认依据（必填）</span>
              <input
                className="assessments-input"
                aria-label="班级确认依据"
                value={classNote}
                onChange={(event) => setClassNote(event.target.value)}
              />
            </label>
            <div className="assessments-actions">
              <button
                className="space-button primary"
                disabled={submission.busy || classNote.trim() === ''}
                data-testid="assessments-class-confirm-retry"
                onClick={() => {
                  const indexes = participants.map((_, index) => index);
                  void submitCreate(indexes);
                }}
              >
                显式确认本次班级并重试
              </button>
            </div>
          </div>
        )}

        {submission.error && submission.error.code !== 'PARTICIPANT_CLASS_UNCONFIRMED' && (
          <p className="space-banner error" role="alert" data-testid="assessments-create-error">
            创建失败（{submission.error.code}）：{submission.error.message}
            你的表单与参测选择已保留，可直接重试。
          </p>
        )}
        {submission.unknownNotice && (
          <p className="space-banner error" role="alert" data-testid="assessments-create-unknown">
            {submission.unknownNotice}
          </p>
        )}
        {formError && (
          <p className="space-banner error" role="alert">
            {formError}
          </p>
        )}

        {created && (
          <p className="space-banner info" role="status" data-testid="assessments-create-result">
            {created.replayed ? '已创建（重放）' : '已创建施测'}：{created.assessment.title} ·{' '}
            {created.participants.length} 人次 · revision {created.assessment.revision}
            <button className="space-button" onClick={onOpenScore}>
              去「成绩」导入
            </button>
          </p>
        )}
      </section>

      <section className="assessments-subpanel" aria-label="施测列表与详情">
        <div className="assessments-subpanel-head">
          <h3>现有施测</h3>
          <button className="space-button" onClick={assessments.reload}>
            <RefreshCw size={13} aria-hidden /> 刷新
          </button>
        </div>
        {assessments.state.phase === 'failed' && !assessments.lastData && (
          <div className="space-banner error" role="alert" data-testid="assessments-list-error">
            施测列表读取失败（{assessments.state.error.code}）：{assessments.state.error.message}
          </div>
        )}
        {assessmentItems.length === 0 && assessments.state.phase === 'ready' && (
          <p className="space-empty" data-testid="assessments-list-empty">
            <strong>还没有施测</strong>
            <span>选定已确认原卷与班级后，在上方创建第一次施测。</span>
          </p>
        )}
        <ul className="assessments-list" aria-label="施测列表">
          {assessmentItems.map((assessment) => (
            <li key={assessment.assessmentId}>
              <button
                type="button"
                className={
                  assessment.assessmentId === selectedAssessmentId
                    ? 'assessments-list-item current'
                    : 'assessments-list-item'
                }
                aria-pressed={assessment.assessmentId === selectedAssessmentId}
                data-testid={`assessments-assessment-${assessment.assessmentId}`}
                onClick={() => onSelectAssessment(assessment.assessmentId)}
              >
                <strong>{assessment.title}</strong>
                <span className="assessments-meta">
                  {assessmentTypeLabel(assessment.assessmentType)} · {assessment.heldOn} ·{' '}
                  {assessmentStateLabel(assessment.state)} · {assessment.participantCount} 人次 ·
                  r{assessment.revision}
                </span>
              </button>
            </li>
          ))}
        </ul>

        {detail.state.phase === 'failed' && (
          <div className="space-banner error" role="alert" data-testid="assessments-detail-error">
            施测详情读取失败（{detail.state.error.code}）：{detail.state.error.message}
          </div>
        )}
        {detail.lastData && <AssessmentDetail detail={detail.lastData}
          onRefresh={detail.reload} onChanged={() => { detail.reload(); onChanged(); }} />}
        {selectedAssessmentId && !detail.lastData && detail.state.phase === 'loading' && (
          <div className="space-skeleton" style={{ height: 120 }} aria-hidden />
        )}
        {!selectedAssessmentId && (
          <p className="assessments-hint">选择一个施测查看参测人次快照；成绩导入基于选中的施测。</p>
        )}
      </section>
    </div>
  );
}

function AssessmentDetail({ detail, onChanged, onRefresh }: {
  detail: AssessmentDetailView;
  onChanged: () => void;
  onRefresh: () => void;
}) {
  const { assessment, participants } = detail;
  return (
    <div className="assessments-detail" data-testid={`assessments-detail-${assessment.assessmentId}`}>
      <div className="space-meta-row">
        <span className="space-chip">原卷修订 {assessment.paperRevisionId}</span>
        <span className="space-chip">施测 revision {assessment.revision}</span>
        <span className="space-chip">参测 {assessment.participantCount} 人次</span>
      </div>
      <ul className="assessments-list" aria-label="参测人次快照">
        {participants.map((participant) => (
          <li
            key={participant.participantId}
            className="assessments-list-static"
            data-testid={`assessments-detail-participant-${participant.participantId}`}
          >
            <strong>{participant.nameSnapshot}</strong>
            <span className="assessments-meta">
              学号 {participant.studentNoSnapshot ?? '（无）'} · 人次 {participant.attemptNo} ·{' '}
              {attendanceLabel(participant.attendance)}
              {participant.classConfirmed
                ? ` · 已显式确认班级${participant.classConfirmationNote ? `（${participant.classConfirmationNote}）` : ''}`
                : ''}
            </span>
            <ParticipantAttendanceEditor
              key={`${assessment.assessmentId}|${participant.participantId}`}
              assessmentId={assessment.assessmentId} participant={participant}
              revision={assessment.revision} onChanged={onChanged} onRefresh={onRefresh}
            />
          </li>
        ))}
      </ul>
      <ParticipantAddPanel key={assessment.assessmentId} detail={detail}
        onChanged={onChanged} onRefresh={onRefresh} />
    </div>
  );
}
