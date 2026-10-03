'use client';

/**
 * 第一步「名单」：选择/创建班级 + 查看与补充班级成员（参测人次从这里来）。
 *
 * 班级与成员、CSV/XLSX 名单校对确认、学生转班和归属历史。
 * 读取失败显示错误与重试入口，绝不显示成空名单。
 */

import { useEffect, useRef, useState } from 'react';
import { RefreshCw, UserPlus, Users } from 'lucide-react';
import type { ClassView, StudentView } from '@/contracts/roster';
import {
  createClass,
  createStudent,
  listClasses,
  listClassStudents,
  transferStudent,
} from '@/services/assessments-api';
import { fetchTextbookTaxonomy } from '@/services/textbook-api';
import { asApiError, useAsyncResource } from './hooks';
import { RosterImportPanel } from './RosterImportPanel';

export function RosterPanel({
  selectedClassId,
  onSelectClass,
  refreshToken,
  onChanged,
}: {
  selectedClassId: string | null;
  onSelectClass: (classId: string) => void;
  refreshToken: number;
  onChanged?: () => void;
}) {
  const classes = useAsyncResource(
    (signal) => listClasses({ status: 'active', limit: 100 }, signal),
    `assessments-classes|${refreshToken}`,
  );
  const taxonomy = useAsyncResource(
    (signal) => fetchTextbookTaxonomy(signal),
    'assessments-taxonomy',
  );
  const [refreshStudents, setRefreshStudents] = useState(0);
  const students = useAsyncResource(
    (signal) =>
      selectedClassId
        ? listClassStudents(selectedClassId, signal)
        : Promise.resolve({ items: [], total: 0, offset: 0, limit: 50 }),
    `assessments-class-students|${selectedClassId ?? 'none'}|${refreshStudents}`,
  );

  const [createOpen, setCreateOpen] = useState(false);
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [schoolYear, setSchoolYear] = useState(String(new Date().getFullYear()));
  const [gradeId, setGradeId] = useState('');
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [studentName, setStudentName] = useState('');
  const [studentNo, setStudentNo] = useState('');
  const [studentBusy, setStudentBusy] = useState(false);
  const [studentError, setStudentError] = useState<string | null>(null);
  const mounted = useRef(true);
  const generation = useRef(0);
  const contextClass = useRef(selectedClassId);
  contextClass.current = selectedClassId;
  useEffect(() => {
    mounted.current = true;
    setBusy(false);
    setStudentBusy(false);
    return () => {
      mounted.current = false;
      generation.current += 1;
    };
  }, [selectedClassId]);
  const active = (token: number, classId: string | null) =>
    mounted.current && token === generation.current && classId === contextClass.current;

  const grades = taxonomy.state.phase === 'ready' ? taxonomy.state.data.grades : [];

  function rosterChanged() {
    setRefreshStudents((value) => value + 1);
    classes.reload();
    onChanged?.();
  }

  async function submitClass() {
    const token = generation.current;
    const classId = selectedClassId;
    setBusy(true);
    setFormError(null);
    try {
      const created = await createClass({
        code: code.trim(),
        name: name.trim(),
        schoolYear: schoolYear.trim(),
        gradeId: gradeId.trim(),
      });
      if (!active(token, classId)) return;
      setCreateOpen(false);
      setCode('');
      setName('');
      classes.reload();
      onSelectClass(created.id);
    } catch (cause) {
      if (!active(token, classId)) return;
      const error = cause as { code?: string; message?: string };
      setFormError(`建立班级失败（${error.code ?? 'UNKNOWN'}）：${error.message ?? '请求失败'}`);
    } finally {
      if (active(token, classId)) setBusy(false);
    }
  }

  async function submitStudent() {
    if (!selectedClassId) return;
    const token = generation.current;
    const classId = selectedClassId;
    setStudentBusy(true);
    setStudentError(null);
    try {
      await createStudent({
        name: studentName.trim(),
        studentNo: studentNo.trim() === '' ? null : studentNo.trim(),
        classId: selectedClassId,
      });
      if (!active(token, classId)) return;
      setStudentName('');
      setStudentNo('');
      rosterChanged();
    } catch (cause) {
      if (!active(token, classId)) return;
      const error = cause as { code?: string; message?: string };
      setStudentError(
        `添加学生失败（${error.code ?? 'UNKNOWN'}）：${error.message ?? '请求失败'} 输入已保留，可重试。`,
      );
    } finally {
      if (active(token, classId)) setStudentBusy(false);
    }
  }

  const classItems: ClassView[] =
    classes.state.phase === 'ready' ? classes.state.data.items : (classes.lastData?.items ?? []);

  return (
    <div className="assessments-panel" data-testid="assessments-roster-panel">
      <section className="assessments-subpanel" aria-label="班级">
        <div className="assessments-subpanel-head">
          <h3>
            <Users size={15} aria-hidden /> 班级
          </h3>
          <div className="assessments-actions">
            <button className="space-button" onClick={() => setCreateOpen((value) => !value)}>
              {createOpen ? '收起新建' : '新建班级'}
            </button>
            <button className="space-button" onClick={classes.reload}>
              <RefreshCw size={13} aria-hidden /> 刷新
            </button>
          </div>
        </div>

        {createOpen && (
          <form
            className="assessments-form"
            aria-label="新建班级"
            onSubmit={(event) => {
              event.preventDefault();
              void submitClass();
            }}
          >
            <label className="assessments-field">
              <span>班级编码</span>
              <input
                className="assessments-input"
                aria-label="班级编码"
                value={code}
                disabled={busy}
                onChange={(event) => setCode(event.target.value)}
                required
              />
            </label>
            <label className="assessments-field">
              <span>班级名称</span>
              <input
                className="assessments-input"
                aria-label="班级名称"
                value={name}
                disabled={busy}
                onChange={(event) => setName(event.target.value)}
                required
              />
            </label>
            <label className="assessments-field">
              <span>学年</span>
              <input
                className="assessments-input"
                aria-label="学年"
                value={schoolYear}
                disabled={busy}
                onChange={(event) => setSchoolYear(event.target.value)}
                required
              />
            </label>
            <label className="assessments-field">
              <span>年级</span>
              {/* 年级 id 允许手填：教材字典不可用时也不阻塞建班（datalist 只做建议） */}
              <input
                className="assessments-input"
                aria-label="年级"
                list="assessments-grade-options"
                value={gradeId}
                disabled={busy}
                onChange={(event) => setGradeId(event.target.value)}
                placeholder="年级 id（如 grade-1）"
                required
              />
              <datalist id="assessments-grade-options">
                {grades.map((grade) => (
                  <option key={grade.id} value={grade.id}>
                    {grade.label}
                  </option>
                ))}
              </datalist>
            </label>
            <button className="space-button primary" type="submit" disabled={busy}>
              {busy ? '建立中…' : '建立班级'}
            </button>
            {formError && (
              <p className="assessments-error" role="alert">
                {formError}
              </p>
            )}
          </form>
        )}

        {classes.state.phase === 'failed' && !classes.lastData && (
          <div className="space-banner error" role="alert" data-testid="assessments-classes-error">
            <div className="space-banner-row">
              <span>
                班级列表读取失败（{classes.state.error.code}）：{classes.state.error.message}
              </span>
              <button className="space-button" onClick={classes.reload}>
                <RefreshCw size={13} aria-hidden /> 重试
              </button>
            </div>
          </div>
        )}

        {classItems.length === 0 && classes.state.phase === 'ready' && (
          <p className="space-empty" data-testid="assessments-classes-empty">
            <strong>还没有班级</strong>
            <span>先建立班级，再在「施测」里选择参测人次。</span>
          </p>
        )}

        <ul className="assessments-list" aria-label="班级列表">
          {classItems.map((item) => (
            <li key={item.id}>
              <button
                type="button"
                className={
                  item.id === selectedClassId
                    ? 'assessments-list-item current'
                    : 'assessments-list-item'
                }
                aria-pressed={item.id === selectedClassId}
                data-testid={`assessments-class-${item.id}`}
                onClick={() => onSelectClass(item.id)}
              >
                <strong>{item.name}</strong>
                <span className="assessments-meta">
                  {item.code} · {item.schoolYear} · 学生 {item.studentCount}
                </span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      <section className="assessments-subpanel" aria-label="班级成员">
        <div className="assessments-subpanel-head">
          <h3>
            <UserPlus size={15} aria-hidden /> 班级成员
          </h3>
          <button className="space-button" disabled={!selectedClassId} onClick={students.reload}>
            <RefreshCw size={13} aria-hidden /> 刷新成员
          </button>
        </div>
        {!selectedClassId && (
          <p className="space-empty">
            <strong>未选择班级</strong>
            <span>从左侧选择一个班级，查看成员并补充参测学生。</span>
          </p>
        )}
        {selectedClassId && students.state.phase === 'failed' && !students.lastData && (
          <div className="space-banner error" role="alert" data-testid="assessments-students-error">
            成员读取失败（{students.state.error.code}）：{students.state.error.message}
          </div>
        )}
        {selectedClassId && (
          <>
            <ul className="assessments-list" aria-label="班级成员列表">
              {(students.lastData?.items ?? []).map((student: StudentView) => (
                <li
                  key={student.id}
                  className="assessments-list-static"
                  data-testid={`assessments-student-${student.id}`}
                >
                  <strong>{student.name}</strong>
                  <span className="assessments-meta">
                    学号 {student.studentNo ?? '（无，按姓名人工确认）'}
                  </span>
                  {student.memberships?.map((membership) => (
                    <span className="assessments-meta" key={membership.membershipId}>
                      {membership.className}：{membership.joinedOn} —{' '}
                      {membership.leftOn ?? '当前归属'}
                    </span>
                  ))}
                </li>
              ))}
            </ul>
            {(students.lastData?.items.length ?? 0) === 0 && students.state.phase === 'ready' && (
              <p className="assessments-hint" data-testid="assessments-students-empty">
                该班还没有学生；可在下面逐个添加（学号可留空，姓名不是主键）。
              </p>
            )}
            <form
              className="assessments-form"
              aria-label="添加学生"
              onSubmit={(event) => {
                event.preventDefault();
                void submitStudent();
              }}
            >
              <label className="assessments-field">
                <span>姓名</span>
                <input
                  className="assessments-input"
                  aria-label="学生姓名"
                  value={studentName}
                  disabled={studentBusy}
                  onChange={(event) => setStudentName(event.target.value)}
                  required
                />
              </label>
              <label className="assessments-field">
                <span>学号（可空，按文本保存）</span>
                <input
                  className="assessments-input"
                  aria-label="学生学号"
                  value={studentNo}
                  disabled={studentBusy}
                  onChange={(event) => setStudentNo(event.target.value)}
                />
              </label>
              <button className="space-button" type="submit" disabled={studentBusy}>
                {studentBusy ? '添加中…' : '添加学生'}
              </button>
              {studentError && (
                <p className="assessments-error" role="alert">
                  {studentError}
                </p>
              )}
            </form>
          </>
        )}
      </section>
      {selectedClassId && (
        <>
          <RosterImportPanel
            classId={selectedClassId}
            onChanged={rosterChanged}
          />
          <MembershipTransferPanel
            key={selectedClassId}
            classId={selectedClassId}
            classes={classItems}
            students={students.lastData?.items ?? []}
            onChanged={rosterChanged}
          />
        </>
      )}
    </div>
  );
}

function MembershipTransferPanel({
  classId,
  classes,
  students,
  onChanged,
}: {
  classId: string;
  classes: ClassView[];
  students: StudentView[];
  onChanged: () => void;
}) {
  const [studentId, setStudentId] = useState('');
  const [toClassId, setToClassId] = useState('');
  const [movedOn, setMovedOn] = useState(() => {
    const now = new Date();
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')}`;
  });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<StudentView | null>(null);
  const mounted = useRef(true);
  const generation = useRef(0);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      generation.current += 1;
    };
  }, []);
  const selected = students.find((student) => student.id === studentId);

  async function transfer() {
    if (!selected || !toClassId || !movedOn || busy) return;
    const token = generation.current;
    setBusy(true);
    setError(null);
    try {
      const updated = await transferStudent(selected.id, {
        expectedStudentRevision: selected.revision,
        fromClassId: classId,
        toClassId,
        movedOn,
      });
      if (!mounted.current || token !== generation.current) return;
      setResult(updated);
      onChanged();
    } catch (cause) {
      if (!mounted.current || token !== generation.current) return;
      const apiError = asApiError(cause);
      setError(
        `转班失败（${apiError.code}）：${apiError.message} 日期与选择已保留。` +
          (apiError.status === 0
            ? '结果未知，请先刷新成员和归属历史对照。'
            : '请核对学生最新版本后重试。'),
      );
    } finally {
      if (mounted.current && token === generation.current) setBusy(false);
    }
  }

  return (
    <section className="assessments-subpanel" aria-label="学生转班">
      <h3>学生转班与归属历史</h3>
      <p className="assessments-hint">
        转班按指定日期结束旧归属并建立新归属，保留旧班级历史；名单导入不会代替转班。
      </p>
      <div className="assessments-form">
        <label className="assessments-field">
          转班学生
          <select
            aria-label="转班学生"
            value={studentId}
            disabled={busy}
            onChange={(event) => setStudentId(event.target.value)}
          >
            <option value="">请选择学生</option>
            {students.map((student) => (
              <option key={student.id} value={student.id}>
                {student.name} · {student.studentNo ?? '无学号'}
              </option>
            ))}
          </select>
        </label>
        <label className="assessments-field">
          目标班级
          <select
            aria-label="转入班级"
            value={toClassId}
            disabled={busy}
            onChange={(event) => setToClassId(event.target.value)}
          >
            <option value="">请选择目标班级</option>
            {classes
              .filter((item) => item.id !== classId)
              .map((item) => (
                <option value={item.id} key={item.id}>
                  {item.name}
                </option>
              ))}
          </select>
        </label>
        <label className="assessments-field">
          转班日期
          <input
            aria-label="转班日期"
            className="assessments-input"
            type="date"
            value={movedOn}
            disabled={busy}
            onChange={(event) => setMovedOn(event.target.value)}
          />
        </label>
        {selected && <span className="assessments-meta">学生版本 r{selected.revision}</span>}
        <button
          className="space-button"
          disabled={busy || !selected || !toClassId || !movedOn}
          onClick={() => void transfer()}
        >
          {busy ? '转班中…' : '确认转班'}
        </button>
      </div>
      {error && (
        <p role="alert" className="assessments-error">
          {error}
        </p>
      )}
      {result && (
        <div role="status" data-testid="roster-transfer-result">
          <strong>
            {result.name} 已转班（版本 r{result.revision}）
          </strong>
          <ul className="assessments-list" aria-label="转班后的归属历史">
            {result.memberships.map((membership) => (
              <li key={membership.membershipId}>
                {membership.className}：{membership.joinedOn} — {membership.leftOn ?? '当前归属'}
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
