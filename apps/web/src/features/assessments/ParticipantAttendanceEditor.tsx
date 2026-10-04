'use client';

import { useState } from 'react';
import type { AssessmentParticipantView, ParticipantMutationResult } from '@/contracts/assessments';
import type { Attendance } from '@/contracts/roster';
import { correctParticipantAttendance } from '@/services/assessments-api';
import { useFrozenSubmission } from './hooks';
import { attendanceLabel, issueLocationLabel } from './labels';

interface AttendancePayload {
  expectedRevision: number;
  attendance: Attendance;
  reason: string;
}

/** 当前施测人次出勤校正；旧成绩快照保持不可变，导入预览须另行显式刷新。 */
export function ParticipantAttendanceEditor({
  assessmentId, participant, revision, onChanged, onRefresh,
}: {
  assessmentId: string;
  participant: AssessmentParticipantView;
  revision: number;
  onChanged: () => void;
  onRefresh: () => void;
}) {
  const [attendance, setAttendance] = useState(participant.attendance);
  const [reason, setReason] = useState('');
  const submission = useFrozenSubmission<AttendancePayload, ParticipantMutationResult>();
  const locked = submission.busy || submission.phase === 'unknown';

  async function save() {
    const payload = submission.phase === 'unknown' && submission.frozen
      ? submission.frozen.payload
      : { expectedRevision: revision, attendance, reason: reason.trim() };
    if (!payload.reason) return;
    const result = await submission.submit(payload, (frozen) => correctParticipantAttendance(
      assessmentId, participant.participantId,
      { ...frozen.payload, submissionId: frozen.submissionId },
    ));
    if (result) onChanged();
  }

  return (
    <div className="assessments-form" aria-label={`${participant.nameSnapshot} 人次 ${participant.attemptNo} 出勤校正`}>
      <label className="assessments-field">
        <span>校正出勤</span>
        <select className="space-select" aria-label={`${participant.nameSnapshot} 人次 ${participant.attemptNo} 校正出勤`}
          value={attendance} disabled={locked} onChange={(event) => setAttendance(event.target.value as Attendance)}>
          {(['present', 'absent', 'exempt'] as const).map((value) => (
            <option key={value} value={value}>{attendanceLabel(value)}</option>
          ))}
        </select>
      </label>
      <label className="assessments-field">
        <span>校正理由（必填）</span>
        <input className="assessments-input" aria-label={`${participant.nameSnapshot} 人次 ${participant.attemptNo} 出勤校正理由`}
          value={reason} disabled={locked} onChange={(event) => setReason(event.target.value)} />
      </label>
      <button className="space-button" disabled={submission.busy || reason.trim() === ''}
        onClick={() => void save()}>
        {submission.busy ? '保存中…' : submission.phase === 'unknown' ? '重试原出勤校正' : '保存出勤校正'}
      </button>
      {submission.error && (
        <div className="space-banner error" role="alert">
          出勤校正失败（{submission.error.code}）：{submission.error.message}
          {submission.error.status === 409 && <span> 当前版本 {submission.error.details?.currentRevision ?? '未知'}；编辑已保留，请刷新对照。</span>}
          {(submission.error.details?.issues ?? []).map((issue, index) => <p key={index}>
            {issueLocationLabel(issue)}{issue.message}
          </p>)}
          <button className="space-button" onClick={onRefresh}>刷新出勤对照</button>
        </div>
      )}
      {submission.unknownNotice && <p className="space-banner error" role="alert">{submission.unknownNotice}</p>}
      {submission.result && <p className="space-banner info" role="status">
        {submission.result.replayed ? '已保存出勤校正（重放）' : '已保存出勤校正'}；施测 r{submission.result.assessment.revision}。
        请在成绩步骤明确刷新预览，重新核对并承认当前范围；既有成绩版本保持原快照。
      </p>}
    </div>
  );
}
