'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import type { AssessmentParticipantInput } from '@/contracts/assessments';
import type { PracticeConversionRequest, PracticeConversionReceipt, PracticeRevisionView } from '@/contracts/b4';
import type { StudentView, Attendance } from '@/contracts/roster';
import { b4Api } from '@/services/teaching-loop-b4-api';
import { listClasses, listClassStudents } from '@/services/assessments-api';
import { useAsyncResource, useFrozenSubmission } from '@/features/assessments/hooks';
import { ReadNotice, SubmissionNotice, attendanceLabel } from '@/features/learning-analysis/ui';

type Selection = { key: string; student: StudentView; input: AssessmentParticipantInput };
type FrozenConversion = { setId: string; revisionId: string; body: PracticeConversionRequest };

export function PracticeConversion({ revision, services, onConverted, onLocked }: {
  revision: PracticeRevisionView; services: typeof b4Api; onConverted: (receipt: PracticeConversionReceipt) => void; onLocked: (locked: boolean) => void;
}) {
  const [title, setTitle] = useState(`${revision.title}施测`);
  const [heldOn, setHeldOn] = useState('');
  const [classId, setClassId] = useState('');
  const [classOffset, setClassOffset] = useState(0);
  const [selections, setSelections] = useState<Selection[]>([]);
  const submission = useFrozenSubmission<FrozenConversion, PracticeConversionReceipt>();
  const locked = submission.busy || submission.phase === 'unknown';
  const classes = useAsyncResource((signal) => listClasses({ status: 'active', offset: classOffset, limit: 50 }, signal), `practice-conversion-classes|${classOffset}`);
  const members = useAsyncResource((signal) => classId ? listClassStudents(classId, signal) : Promise.resolve(null), `practice-conversion-members|${classId}`);
  useEffect(() => { onLocked(locked); return () => onLocked(false); }, [locked, onLocked]);
  function change(key: string, patch: Partial<AssessmentParticipantInput>) { setSelections((previous) => previous.map((entry) => entry.key === key ? { ...entry, input: { ...entry.input, ...patch } } : entry)); }
  async function convert() {
    const result = await submission.submit({ setId: revision.practiceSetId, revisionId: revision.practiceRevisionId, body: {
      submissionId: '', title: title.trim(), heldOn, classIds: [...new Set(selections.map((entry) => entry.input.classId))], participants: selections.map((entry) => entry.input),
    } }, (frozen) => services.convertPractice(frozen.payload.setId, frozen.payload.revisionId, { ...frozen.payload.body, submissionId: frozen.submissionId }));
    if (result) onConverted(result);
  }
  return <section className="b4-section" aria-label="练习转换施测"><h2>转换为施测，回到成绩工作区</h2><p className="b4-hint">固定练习 {revision.practiceRevisionId}。选择实际日期和参测人次；姓名/学号由服务端冻结。补考须明确人次序号，不自动代替原人次。</p>
    <fieldset disabled={locked}><div className="b4-fields"><label className="b4-field">施测标题<input aria-label="练习施测标题" value={title} onChange={(event) => setTitle(event.target.value)} /></label><label className="b4-field">施测日期<input aria-label="练习施测日期" type="date" value={heldOn} onChange={(event) => setHeldOn(event.target.value)} /></label><label className="b4-field">查看班级<select aria-label="练习施测班级" className="space-select" value={classId} onChange={(event) => setClassId(event.target.value)}><option value="">明确选择班级</option>{classes.lastData?.items.map((item) => <option key={item.id} value={item.id}>{item.name} · {item.code}</option>)}</select></label></div>
      <ReadNotice resource={classes} label="当前班级" />
      <div className="b4-actions"><button className="space-button" disabled={classOffset === 0} onClick={() => setClassOffset((n) => Math.max(0, n - 50))}>上一页班级</button><button className="space-button" disabled={!classes.lastData || classOffset + 50 >= classes.lastData.total} onClick={() => setClassOffset((n) => n + 50)}>下一页班级</button></div>
      {classId && <><ReadNotice resource={members} label="当前班级成员" /><div className="b4-checks">{members.lastData?.items.map((student) => { const key = `${classId}|${student.id}`; return <label key={key}><input type="checkbox" aria-label={`练习参测 ${student.name}`} checked={selections.some((entry) => entry.key === key)} disabled={members.state.phase !== 'ready'} onChange={(event) => setSelections((previous) => event.target.checked ? [...previous, { key, student, input: { studentId: student.id, classId, attendance: 'present', attemptNo: 1, classConfirmed: false, classConfirmationNote: null } }] : previous.filter((entry) => entry.key !== key))} />{student.name} · 学号 {student.studentNo ?? '未记录'}</label>; })}</div>{members.state.phase === 'ready' && members.lastData?.items.length === 0 && <p>此班没有当前成员。请先在现有名单工作区处理，不会生成虚拟学生。</p>}</>}
      <p className="b4-hint">已选择 {selections.length}人次。可以依次查看多个班级；取消某人勾选才移除该人次。</p>
      {selections.map((selection) => <article className="b4-node" key={selection.key}><strong>{selection.student.name} · {selection.input.classId}</strong><div className="b4-fields"><label className="b4-field">出勤<select className="space-select" aria-label={`${selection.student.name} 练习出勤`} value={selection.input.attendance ?? 'present'} onChange={(event) => change(selection.key, { attendance: event.target.value as Attendance })}>{Object.entries(attendanceLabel).map(([value, label]) => <option key={value} value={value}>{label}</option>)}</select></label><label className="b4-field">人次序号<input aria-label={`${selection.student.name} 练习人次`} type="number" min={1} value={selection.input.attemptNo ?? ''} onChange={(event) => change(selection.key, { attemptNo: event.target.value ? Number(event.target.value) : null })} /></label></div>
        <label><input type="checkbox" aria-label={`${selection.student.name} 确认本次班级`} checked={selection.input.classConfirmed === true} onChange={(event) => change(selection.key, { classConfirmed: event.target.checked })} />明确确认历史归属未覆盖施测日期时的本次班级</label>
        {selection.input.classConfirmed && <label className="b4-field">班级确认依据<input aria-label={`${selection.student.name} 班级确认依据`} value={selection.input.classConfirmationNote ?? ''} onChange={(event) => change(selection.key, { classConfirmationNote: event.target.value })} /></label>}
        <button className="space-button" onClick={() => setSelections((previous) => previous.filter((entry) => entry.key !== selection.key))}>取消此参测人次</button>
      </article>)}
    </fieldset>
    <SubmissionNotice submission={submission} /><button className="space-button primary" disabled={submission.busy || (submission.phase !== 'unknown' && (!title.trim() || !heldOn || selections.length === 0))} onClick={() => void convert()}>{submission.phase === 'unknown' ? '重试原转换提交' : '转换固定练习为施测'}</button>
    {submission.result && <div className="b4-chain"><span>练习 {submission.result.practiceRevisionId} → 原卷 {submission.result.paperRevisionId} → 施测 {submission.result.assessmentId}</span><Link href={`/assessments?assessmentId=${encodeURIComponent(submission.result.assessmentId)}&step=score`}>进入现有成绩工作区</Link><span>{submission.result.replayed ? '原提交已重放，同一施测身份' : '施测已创建'}</span></div>}
    <p className="b4-hint">在现有成绩工作区完成上传、校对与确认，再从新成绩历史创建新学情报告。新报告产生前，尚未完成回流。</p>
  </section>;
}
