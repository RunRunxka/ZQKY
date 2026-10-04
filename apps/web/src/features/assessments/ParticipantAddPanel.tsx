'use client';

import { useState } from 'react';
import type { AssessmentDetailView, ParticipantAddRequest, ParticipantMutationResult } from '@/contracts/assessments';
import type { Attendance } from '@/contracts/roster';
import { addAssessmentParticipants, listClassStudents } from '@/services/assessments-api';
import { useAsyncResource, useFrozenSubmission } from './hooks';
import { attendanceLabel, issueLocationLabel } from './labels';

/** 补录/补考只引用已有学生；服务器读取并冻结身份，不修改旧人次或成绩。 */
export function ParticipantAddPanel({ detail, onChanged, onRefresh }: {
  detail: AssessmentDetailView;
  onChanged: () => void;
  onRefresh: () => void;
}) {
  const { assessment, participants } = detail;
  const [classId, setClassId] = useState(assessment.classIds?.[0] ?? '');
  const [studentId, setStudentId] = useState('');
  const [attemptNo, setAttemptNo] = useState(1);
  const [attendance, setAttendance] = useState<Attendance>('present');
  const [classNote, setClassNote] = useState('');
  const [formError, setFormError] = useState<string | null>(null);
  const submission = useFrozenSubmission<ParticipantAddRequest, ParticipantMutationResult>();
  const students = useAsyncResource((signal) => classId ? listClassStudents(classId, signal)
    : Promise.resolve({ items: [], total: 0, offset: 0, limit: 50 }), `participant-add-students|${classId}`);
  const locked = submission.busy || submission.phase === 'unknown';

  async function add(confirmClass = false) {
    setFormError(null);
    if (!classId || !studentId) { setFormError('请选择本施测班级内的既有学生。'); return; }
    if (!Number.isInteger(attemptNo) || attemptNo < 1) { setFormError('人次序号必须是正整数。'); return; }
    if (confirmClass && !classNote.trim()) { setFormError('显式确认本次班级必须填写依据。'); return; }
    const payload: ParticipantAddRequest = submission.phase === 'unknown' && submission.frozen
      ? submission.frozen.payload
      : { submissionId: '', expectedRevision: assessment.revision, participants: [{ studentId, classId,
        attemptNo, attendance, ...(confirmClass ? { classConfirmed: true, classConfirmationNote: classNote.trim() } : {}) }] };
    const result = await submission.submit(payload, (frozen) => addAssessmentParticipants(assessment.assessmentId,
      { ...frozen.payload, submissionId: frozen.submissionId }));
    if (result) onChanged();
  }

  return <section className="assessments-subpanel" aria-label="补录与补考人次" data-testid="participant-add-panel">
    <h4>补录与补考人次</h4>
    <p className="assessments-hint">选择已登记学生并明确人次序号；补考新增人次，已有参测记录和历史成绩快照保留。</p>
    <div className="assessments-form">
      <label className="assessments-field"><span>本施测班级</span><select className="space-select" aria-label="补录班级" value={classId} disabled={locked} onChange={(event) => { setClassId(event.target.value); setStudentId(''); }}>
        <option value="">选择班级</option>{(assessment.classIds ?? []).map((id) => <option key={id} value={id}>{id}</option>)}
      </select></label>
      <label className="assessments-field"><span>既有学生</span><select className="space-select" aria-label="补录学生" value={studentId} disabled={locked || students.state.phase !== 'ready'} onChange={(event) => {
        setStudentId(event.target.value);
        const previous = participants.filter((participant) => participant.studentId === event.target.value);
        setAttemptNo(previous.reduce((max, participant) => Math.max(max, participant.attemptNo), 0) + 1);
      }}><option value="">选择学生</option>{(students.lastData?.items ?? []).map((student) => <option key={student.id} value={student.id}>{student.name} · 学号 {student.studentNo ?? '无'}</option>)}</select></label>
      <label className="assessments-field"><span>人次序号（教师确认）</span><input className="assessments-input assessments-input-narrow" aria-label="补录人次序号" type="number" min={1} value={attemptNo} disabled={locked} onChange={(event) => setAttemptNo(Number(event.target.value))} /></label>
      <label className="assessments-field"><span>出勤</span><select className="space-select" aria-label="补录出勤" value={attendance} disabled={locked} onChange={(event) => setAttendance(event.target.value as Attendance)}>{(['present', 'absent', 'exempt'] as const).map((value) => <option key={value} value={value}>{attendanceLabel(value)}</option>)}</select></label>
      <button className="space-button primary" disabled={submission.busy || !studentId || !classId} onClick={() => void add()}>{submission.busy ? '补录中…' : submission.phase === 'unknown' ? '重试原人次补录' : '新增参测人次'}</button>
    </div>
    {students.state.phase === 'failed' && <p className="space-banner error" role="alert">班级学生读取失败（{students.state.error.code}）。<button className="space-button" onClick={students.reload}>重试补录学生</button></p>}
    {students.state.phase === 'ready' && students.lastData?.items.length === 0 && <p className="assessments-hint">该班没有可选学生；先在名单步骤建立学生与归属。</p>}
    {formError && <p className="space-banner error" role="alert">{formError}</p>}
    {submission.error && <div className="space-banner error" role="alert" data-testid="participant-add-error">
      补录失败（{submission.error.code}）：{submission.error.message} 当前学生、人次与出勤已保留。
      {submission.error.status === 409 && <p>当前施测版本 {submission.error.details?.currentRevision ?? '未知'}，请刷新对照。</p>}
      {(submission.error.details?.issues ?? []).map((issue, index) => <p key={index}>{issueLocationLabel(issue)}{issue.message}</p>)}
      <button className="space-button" onClick={onRefresh}>刷新参测对照</button>
      {submission.error.code === 'PARTICIPANT_CLASS_UNCONFIRMED' && <>
        <label className="assessments-field"><span>本次班级确认依据</span><input className="assessments-input" aria-label="补录班级确认依据" value={classNote} onChange={(event) => setClassNote(event.target.value)} /></label>
        <button className="space-button" disabled={!classNote.trim() || submission.busy} onClick={() => void add(true)}>显式确认补录班级并重试</button>
      </>}
    </div>}
    {submission.unknownNotice && <p className="space-banner error" role="alert">{submission.unknownNotice}</p>}
    {submission.result && <p className="space-banner info" role="status" data-testid="participant-add-result">
      {submission.result.replayed ? '已新增参测人次（重放）' : '已新增参测人次'}，施测 r{submission.result.assessment.revision}。
      请在成绩步骤明确刷新预览并重新承认；旧成绩仍按自己的参测快照读取。
    </p>}
  </section>;
}
