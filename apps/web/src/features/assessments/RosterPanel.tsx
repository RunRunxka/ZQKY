'use client';

/**
 * 第一步「名单」：选择/创建班级 + 查看与补充班级成员（参测人次从这里来）。
 *
 * 班级与成员、CSV/XLSX 名单校对确认、学生转班和归属历史。
 * 读取失败显示错误与重试入口，绝不显示成空名单。
 */

import { useEffect, useRef, useState } from 'react';
import { RefreshCw, UserPlus, Users } from 'lucide-react';
import type { BatchStudentAddResult, BatchStudentItem, ClassView, StudentView } from '@/contracts/roster';
import {
  archiveClass,
  archiveStudent,
  batchAddStudents,
  createClass,
  createStudent,
  deleteClass,
  listClasses,
  listClassStudents,
  restoreClass,
  restoreStudent,
  transferStudent,
} from '@/services/assessments-api';
import { fetchTextbookTaxonomy } from '@/services/textbook-api';
import { Modal } from '@/components/ui/Modal';
import { asApiError, useAsyncResource, useFrozenSubmission } from './hooks';
import { CLASS_REFERENCE_LABELS, referenceCounts, shortId } from './labels';
import { DeleteGuardNotice, type DeleteGuardState } from './DeleteGuardNotice';
import { RosterImportPanel } from './RosterImportPanel';

/** 批量添加一次最多 200 行（与服务端 `BatchStudentAddRequest.items` 上限一致）。 */
const BATCH_MAX_ROWS = 200;
/** 与服务端 `row_analysis` 的长度上限同口径（本地先标出，服务端仍会 422 整批拒绝）。 */
const BATCH_MAX_TEXT_CHARS = 200;

export function RosterPanel({
  selectedClassId,
  onSelectClass,
  refreshToken,
  onChanged,
}: {
  selectedClassId: string | null;
  /** 选中班级时回传 `(classId, name)`：工作区状态条据此显示班名（不再显示长 id）。 */
  onSelectClass: (classId: string, name: string) => void;
  refreshToken: number;
  onChanged?: () => void;
}) {
  /**
   * 「显示已归档」开关：默认只取活跃班；打开后不传 status（服务端默认口径 = 全部）。
   * 归档班级仍可读，但不能再导入名单/转入学生，所以默认不展示。
   */
  const [showArchivedClasses, setShowArchivedClasses] = useState(false);
  const classes = useAsyncResource(
    (signal) =>
      listClasses(
        showArchivedClasses ? { limit: 100 } : { status: 'active', limit: 100 },
        signal,
      ),
    `assessments-classes|${refreshToken}|${showArchivedClasses ? 'all' : 'active'}`,
  );
  const taxonomy = useAsyncResource(
    (signal) => fetchTextbookTaxonomy(signal),
    'assessments-taxonomy',
  );
  const [refreshStudents, setRefreshStudents] = useState(0);
  /** 学生成员同理：打开后带 includeArchived=true 才看得到归档学生。 */
  const [showArchivedStudents, setShowArchivedStudents] = useState(false);
  const students = useAsyncResource(
    (signal) =>
      selectedClassId
        ? listClassStudents(
            selectedClassId,
            { includeArchived: showArchivedStudents },
            signal,
          )
        : Promise.resolve({ items: [], total: 0, offset: 0, limit: 50 }),
    `assessments-class-students|${selectedClassId ?? 'none'}|${
      showArchivedStudents ? 'all' : 'active'
    }|${refreshStudents}`,
  );

  const [createOpen, setCreateOpen] = useState(false);
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [schoolYear, setSchoolYear] = useState(String(new Date().getFullYear()));
  const [gradeId, setGradeId] = useState('');
  const [busy, setBusy] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  /** 归档/恢复的写操作身份（禁用按钮防重入）；busyRef 阻止状态更新前的连点。 */
  const [rosterWriteId, setRosterWriteId] = useState<string | null>(null);
  const [writeError, setWriteError] = useState<{ scope: 'class' | 'student'; message: string } | null>(
    null,
  );
  const writeBusyRef = useRef(false);
  /** 彻底删除：被引用守卫 409 的原因清单 + 成功回执；写锁与归档/恢复共用（同一时刻一个写）。 */
  const [deleteGuard, setDeleteGuard] = useState<DeleteGuardState | null>(null);
  const [deleteNotice, setDeleteNotice] = useState<string | null>(null);
  /** 仅在途删除的按钮文案（`rosterWriteId` 负责禁用，两者分开便于失败后仍显示原因清单）。 */
  const [deleteBusyId, setDeleteBusyId] = useState<string | null>(null);
  const [batchOpen, setBatchOpen] = useState(false);

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
    // 切班即失效在途写入与旧班落的错误提示（迟到响应由 generation 拦下）。
    setRosterWriteId(null);
    setWriteError(null);
    setDeleteGuard(null);
    setDeleteNotice(null);
    setBatchOpen(false);
    writeBusyRef.current = false;
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
      onSelectClass(created.id, created.name);
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

  /** 班级归档/恢复（守卫式）：成功刷新班级列表，失败把服务端 message 显示在既有错误区。 */
  async function writeClass(item: ClassView) {
    if (writeBusyRef.current) return;
    const archived = item.status === 'archived';
    if (
      !archived &&
      !window.confirm(
        `归档班级「${item.name}」？归档班级仍可读，但不能再导入名单/转入学生；历史归属与既有施测保留。`,
      )
    ) {
      return;
    }
    const token = generation.current;
    const classId = selectedClassId;
    writeBusyRef.current = true;
    setRosterWriteId(item.id);
    setWriteError(null);
    try {
      if (archived) await restoreClass(item.id, { expectedRevision: item.revision });
      else await archiveClass(item.id, { expectedRevision: item.revision });
      if (!active(token, classId)) return;
      rosterChanged();
    } catch (cause) {
      if (!active(token, classId)) return;
      const error = asApiError(cause);
      setWriteError({
        scope: 'class',
        message: `${archived ? '恢复' : '归档'}班级失败（${error.code}）：${error.message}`,
      });
    } finally {
      writeBusyRef.current = false;
      if (active(token, classId)) setRosterWriteId(null);
    }
  }

  /**
   * 彻底删除班级（受引用守卫的物理删除，二次确认）：
   * 被归属/名单导入/施测范围/教案任一引用时服务端 409 `CLASS_IN_USE`，
   * 把 message 与 `details.counts` 逐项显示在组件内错误区，并给「改为归档」；
   * 404 与乐观锁冲突按既有错误区呈现（不伪装成引用问题）。
   */
  async function deleteClassItem(item: ClassView) {
    if (writeBusyRef.current) return;
    if (
      !window.confirm(
        `彻底删除班级「${item.name}」？这是物理删除、不可恢复；被归属记录/名单导入/施测范围/教案引用时会被拒绝并逐项列出引用。`,
      )
    ) {
      return;
    }
    const token = generation.current;
    const classId = selectedClassId;
    writeBusyRef.current = true;
    setRosterWriteId(item.id);
    setDeleteBusyId(item.id);
    setWriteError(null);
    setDeleteGuard(null);
    setDeleteNotice(null);
    try {
      await deleteClass(item.id, item.revision);
      if (!active(token, classId)) return;
      setDeleteNotice(`已彻底删除班级「${item.name}」：物理删除完成，不可恢复。`);
      // 被删班级若正被选中，取消选择，避免成员区继续读取已不存在的班级。
      if (item.id === classId) onSelectClass('', '');
      rosterChanged();
    } catch (cause) {
      if (!active(token, classId)) return;
      const error = asApiError(cause);
      if (error.status === 409 && error.code === 'CLASS_IN_USE') {
        setDeleteGuard({
          targetId: item.id,
          error,
          reasons: referenceCounts(error.details, CLASS_REFERENCE_LABELS),
        });
      } else {
        setWriteError({ scope: 'class', message: `彻底删除班级失败（${error.code}）：${error.message}` });
      }
    } finally {
      writeBusyRef.current = false;
      if (active(token, classId)) {
        setRosterWriteId(null);
        setDeleteBusyId(null);
      }
    }
  }

  /** 学生归档/恢复：归属历史保留；成功后刷新成员并通知同班施测刷新参测名单。 */
  async function writeStudent(student: StudentView) {
    if (writeBusyRef.current) return;
    const archived = student.status === 'archived';
    if (
      !archived &&
      !window.confirm(
        `归档学生「${student.name}」？归属历史保留；归档后不再出现在默认名单与参测选择中，已有成绩快照不动。`,
      )
    ) {
      return;
    }
    const token = generation.current;
    const classId = selectedClassId;
    writeBusyRef.current = true;
    setRosterWriteId(student.id);
    setWriteError(null);
    try {
      if (archived) await restoreStudent(student.id, { expectedRevision: student.revision });
      else await archiveStudent(student.id, { expectedRevision: student.revision });
      if (!active(token, classId)) return;
      rosterChanged();
    } catch (cause) {
      if (!active(token, classId)) return;
      const error = asApiError(cause);
      setWriteError({
        scope: 'student',
        message: `${archived ? '恢复' : '归档'}学生失败（${error.code}）：${error.message}`,
      });
    } finally {
      writeBusyRef.current = false;
      if (active(token, classId)) setRosterWriteId(null);
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
            <label className="assessments-check">
              <input
                type="checkbox"
                aria-label="显示已归档班级"
                checked={showArchivedClasses}
                onChange={(event) => setShowArchivedClasses(event.target.checked)}
              />
              <span>显示已归档</span>
            </label>
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
              <div className="assessments-actions">
                <button
                  type="button"
                  className={
                    item.id === selectedClassId
                      ? 'assessments-list-item current'
                      : 'assessments-list-item'
                  }
                  aria-pressed={item.id === selectedClassId}
                  data-testid={`assessments-class-${item.id}`}
                  onClick={() => onSelectClass(item.id, item.name)}
                >
                  <strong>{item.name}</strong>
                  <span className="assessments-meta">
                    {item.code} · {item.schoolYear} · 学生 {item.studentCount}
                  </span>
                </button>
                {item.status === 'archived' && (
                  <span
                    className="space-chip"
                    data-testid={`assessments-class-archived-${item.id}`}
                  >
                    已归档
                  </span>
                )}
                {item.status === 'archived' ? (
                  <button
                    className="space-button"
                    data-testid={`assessments-class-restore-${item.id}`}
                    disabled={rosterWriteId !== null}
                    onClick={() => void writeClass(item)}
                  >
                    {rosterWriteId === item.id ? '恢复中…' : '恢复'}
                  </button>
                ) : (
                  <button
                    className="space-button danger"
                    data-testid={`assessments-class-archive-${item.id}`}
                    disabled={rosterWriteId !== null}
                    onClick={() => void writeClass(item)}
                  >
                    {rosterWriteId === item.id ? '归档中…' : '归档'}
                  </button>
                )}
                {/* 次级危险操作：物理删除只在无引用时通过（归档对象同样受守卫） */}
                <button
                  className="space-button danger"
                  data-testid={`assessments-class-delete-${item.id}`}
                  disabled={rosterWriteId !== null}
                  onClick={() => void deleteClassItem(item)}
                >
                  {deleteBusyId === item.id ? '删除中…' : '彻底删除'}
                </button>
              </div>
            </li>
          ))}
        </ul>
        {writeError?.scope === 'class' && (
          <p className="space-banner error" role="alert" data-testid="assessments-class-write-error">
            {writeError.message}
          </p>
        )}
        {deleteNotice && (
          <p className="space-banner info" role="status" data-testid="assessments-class-delete-notice">
            {deleteNotice}
          </p>
        )}
        {deleteGuard && (
          <DeleteGuardNotice
            state={deleteGuard}
            targetName={
              classItems.find((item) => item.id === deleteGuard.targetId)?.name ?? shortId(deleteGuard.targetId)
            }
            archiving={rosterWriteId === deleteGuard.targetId}
            testId="assessments-class-delete-guard"
            onArchive={() => {
              const item = classItems.find((entry) => entry.id === deleteGuard.targetId);
              if (item) void writeClass(item);
            }}
          />
        )}
      </section>

      <section className="assessments-subpanel" aria-label="班级成员">
        <div className="assessments-subpanel-head">
          <h3>
            <UserPlus size={15} aria-hidden /> 班级成员
          </h3>
          <div className="assessments-actions">
            <label className="assessments-check">
              <input
                type="checkbox"
                aria-label="显示已归档成员"
                checked={showArchivedStudents}
                onChange={(event) => setShowArchivedStudents(event.target.checked)}
              />
              <span>显示已归档成员</span>
            </label>
            <button
              className="space-button"
              data-testid="assessments-batch-open"
              disabled={!selectedClassId}
              onClick={() => setBatchOpen(true)}
            >
              <UserPlus size={13} aria-hidden /> 批量添加学生
            </button>
            <button className="space-button" disabled={!selectedClassId} onClick={students.reload}>
              <RefreshCw size={13} aria-hidden /> 刷新成员
            </button>
          </div>
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
                  <div className="assessments-actions">
                    {student.status === 'archived' && (
                      <span
                        className="space-chip"
                        data-testid={`assessments-student-archived-${student.id}`}
                      >
                        已归档
                      </span>
                    )}
                    {student.status === 'archived' ? (
                      <button
                        className="space-button"
                        data-testid={`assessments-student-restore-${student.id}`}
                        disabled={rosterWriteId !== null}
                        onClick={() => void writeStudent(student)}
                      >
                        {rosterWriteId === student.id ? '恢复中…' : '恢复'}
                      </button>
                    ) : (
                      <button
                        className="space-button danger"
                        data-testid={`assessments-student-archive-${student.id}`}
                        disabled={rosterWriteId !== null}
                        onClick={() => void writeStudent(student)}
                      >
                        {rosterWriteId === student.id ? '归档中…' : '归档'}
                      </button>
                    )}
                  </div>
                </li>
              ))}
            </ul>
            {writeError?.scope === 'student' && (
              <p
                className="space-banner error"
                role="alert"
                data-testid="assessments-student-write-error"
              >
                {writeError.message}
              </p>
            )}
            {(students.lastData?.items.length ?? 0) === 0 && students.state.phase === 'ready' && (
              <p className="assessments-hint" data-testid="assessments-students-empty">
                该班还没有学生；可在下面逐个添加（学号可留空，姓名不是主键），
                或用「批量添加学生」从名单/Excel 直接粘贴多行。
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
            classes={classItems.filter((item) => item.status !== 'archived')}
            students={(students.lastData?.items ?? []).filter(
              (student) => student.status !== 'archived',
            )}
            onChanged={rosterChanged}
          />
          {batchOpen && (
            /* 不设 key：与成员/转班面板的 key 冲突会触发 React 重复 key 警告；切班即卸载重置 */
            <BatchStudentDialog
              classId={selectedClassId}
              className={
                classItems.find((item) => item.id === selectedClassId)?.name
                  ?? `未命名班级（${shortId(selectedClassId)}）`
              }
              onClose={() => setBatchOpen(false)}
              onDone={rosterChanged}
            />
          )}
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

/* ------------------------------------------------------------------ 批量添加学生 */

interface BatchParseRow {
  /** 原文 1 基行号（空行不产生行）。 */
  lineNo: number;
  /** 该行原文（提交成功后从输入框移除已提交行时保留需处理行）。 */
  raw: string;
  studentNo: string;
  name: string;
  /** 非空 = 该行不会提交（识别不到学号/姓名/超长），可修好后重新提交。 */
  issue: string | null;
  /** 本批内学号重复（仍提交，服务端按学号跳过并如实报告）。 */
  duplicate: boolean;
}

/**
 * 粘贴文本 → 预览行。每行一位：`学号 姓名`（逗号/制表符/空格分隔，姓名在前不识别）。
 * 空行自动忽略；识别不到学号、姓名为空或超长的行只标记不提交（不猜、不合并）。
 */
function parseBatchStudents(text: string): BatchParseRow[] {
  const rows: BatchParseRow[] = [];
  const seenNo = new Set<string>();
  text.split(/\r?\n/).forEach((line, index) => {
    const raw = line;
    const trimmed = line.trim();
    if (trimmed === '') return;
    const tokens = trimmed.split(/[,，\t]|\s+/).filter((token) => token !== '');
    const studentNo = tokens[0] ?? '';
    const name = tokens.slice(1).join('');
    let issue: string | null = null;
    if (tokens.length < 2) issue = '未识别到学号（每行需要「学号 姓名」）';
    else if (studentNo.length > BATCH_MAX_TEXT_CHARS) issue = `学号超过 ${BATCH_MAX_TEXT_CHARS} 字`;
    else if (name === '') issue = '姓名为空';
    else if (name.length > BATCH_MAX_TEXT_CHARS) issue = `姓名超过 ${BATCH_MAX_TEXT_CHARS} 字`;
    const duplicate = issue === null && seenNo.has(studentNo);
    if (issue === null) seenNo.add(studentNo);
    rows.push({ lineNo: index + 1, raw, studentNo, name, issue, duplicate });
  });
  return rows;
}

/** 逐行结论徽章：需处理（红）/ 本批重复（黄）/ 新建（绿）。 */
function BatchRowConclusion({ row }: { row: BatchParseRow }) {
  if (row.issue) return <span className="space-chip score-chip-danger">{row.issue}</span>;
  if (row.duplicate) return <span className="space-chip amber">本批重复（服务端会跳过）</span>;
  return <span className="space-chip green">新建</span>;
}

/**
 * 批量添加学生对话框：粘贴多行 → 本地预览 → 一次提交。
 *
 * - `submissionId` 由 `useFrozenSubmission` 冻结：同载荷重试复用同一标识（服务端幂等），
 *   结果未知时锁定原包原标识，不重复建档；
 * - 提交成功后刷新成员列表，并把已提交行从输入框移除（需处理行保留可继续修）；
 * - 超过 200 行前端先提示并禁用提交（后端同样拒绝）。
 */
function BatchStudentDialog({
  classId,
  className,
  onClose,
  onDone,
}: {
  classId: string;
  className: string;
  onClose: () => void;
  onDone: () => void;
}) {
  const [text, setText] = useState('');
  /** 本次已提交的行（用于把服务端 0 基下标映射回原文行号）。 */
  const [submittedRows, setSubmittedRows] = useState<BatchParseRow[]>([]);
  const submission = useFrozenSubmission<{ items: BatchStudentItem[] }, BatchStudentAddResult>();

  const rows = parseBatchStudents(text);
  const submittable = rows.filter((row) => row.issue === null);
  const fresh = submittable.filter((row) => !row.duplicate);
  const problems = rows.filter((row) => row.issue !== null);
  const overLimit = submittable.length > BATCH_MAX_ROWS;
  const result = submission.result;

  const lineNoOf = (index: number): number => submittedRows[index]?.lineNo ?? index + 1;

  async function submit() {
    if (submission.busy || submittable.length === 0 || overLimit) return;
    // 结果未知时的重试必须沿用冻结的原包与原标识：不覆盖上一次提交的行映射。
    if (submission.phase !== 'unknown') setSubmittedRows(submittable);
    const payload = {
      items: submittable.map((row) => ({ studentNo: row.studentNo, name: row.name })),
    };
    const outcome = await submission.submit(payload, (frozen) =>
      batchAddStudents(classId, { ...frozen.payload, submissionId: frozen.submissionId }),
    );
    if (outcome) {
      onDone();
      // 已提交行出输入框；需处理行留在原位继续修改（重提交会形成新的逻辑确认）。
      setText(problems.map((row) => row.raw).join('\n'));
    }
  }

  return (
    <Modal title={`批量添加学生 · ${className}`} onClose={onClose}>
      <p className="assessments-hint">
        从名单或 Excel 直接粘贴：每行一位，`学号 姓名`（逗号、制表符或空格分隔）。
        空行自动忽略；识别不到学号的行会标为需处理，不会提交。
      </p>
      <label className="assessments-field">
        <span>粘贴多行（每行一位）</span>
        <textarea
          className="assessments-input"
          aria-label="批量学生文本"
          rows={6}
          value={text}
          disabled={submission.busy}
          placeholder={'T260031, 沈予安\nT260032, 顾时雨'}
          onChange={(event) => setText(event.target.value)}
        />
      </label>

      {rows.length > 0 && (
        <div data-testid="roster-batch-preview">
          <div className="assessments-actions">
            <span className="space-chip green" data-testid="roster-batch-fresh">
              可建立 {fresh.length} 名
            </span>
            {submittable.length - fresh.length > 0 && (
              <span className="space-chip amber">本批重复 {submittable.length - fresh.length} 行</span>
            )}
            {problems.length > 0 && (
              <span className="space-chip score-chip-danger" data-testid="roster-batch-problems">
                需处理 {problems.length} 行
              </span>
            )}
            {overLimit && (
              <span className="space-chip score-chip-danger" data-testid="roster-batch-over-limit">
                超过一次 {BATCH_MAX_ROWS} 行上限
              </span>
            )}
          </div>
          <ul className="assessments-list" aria-label="批量添加预览">
            {rows.map((row) => (
              <li
                key={row.lineNo}
                className="assessments-list-static assessments-batch-row"
                data-testid={`roster-batch-row-${row.lineNo}`}
              >
                <span className="assessments-meta">第 {row.lineNo} 行</span>
                <strong>{row.studentNo}</strong>
                <span>{row.name || '（无姓名）'}</span>
                <BatchRowConclusion row={row} />
              </li>
            ))}
          </ul>
        </div>
      )}

      {submission.error && submission.error.status !== 422 && (
        <div className="space-banner error" role="alert" data-testid="roster-batch-error">
          批量添加失败（{submission.error.code}）：{submission.error.message}
          输入已保留，重试会复用同一提交标识。
        </div>
      )}
      {submission.error?.status === 422 && (
        <div className="space-banner error" role="alert" data-testid="roster-batch-error">
          <p>
            批量添加被拒绝（{submission.error.code}）：{submission.error.message}
            整批未写入；请修好这些行后重试。
          </p>
          <ul className="assessments-issue-list" aria-label="行级问题">
            {(submission.error.details?.issues ?? []).map((issue, index) => (
              <li key={`${issue.code}-${index}`}>
                {typeof issue.row === 'number' ? `第 ${lineNoOf(issue.row)} 行：` : ''}
                {issue.code}：{issue.message}
              </li>
            ))}
          </ul>
        </div>
      )}
      {submission.unknownNotice && (
        <p className="space-banner error" role="alert" data-testid="roster-batch-unknown">
          {submission.unknownNotice}
        </p>
      )}

      {result && (
        <div className="space-banner info" role="status" data-testid="roster-batch-result">
          <p>
            {result.replayed ? '已批量添加（幂等重放）' : '已批量添加'}：新建{' '}
            {result.created.length} 名学生
            {result.skipped.length > 0 ? `，跳过 ${result.skipped.length} 行` : ''}。
          </p>
          {result.created.length > 0 && (
            <p className="assessments-meta">
              新建：
              {result.created
                .map((student) => `${student.name}${student.studentNo ? `（${student.studentNo}）` : ''}`)
                .join('、')}
            </p>
          )}
          {result.skipped.length > 0 && (
            <ul className="assessments-issue-list" aria-label="跳过行原因">
              {result.skipped.map((row) => (
                <li key={row.index} data-testid={`roster-batch-skipped-${row.index}`}>
                  第 {lineNoOf(row.index)} 行：{row.reason}
                  {row.existingName
                    ? `（既有学生：${row.existingName}${
                        row.existingStudentId ? ` · ${shortId(row.existingStudentId)}` : ''
                      }）`
                    : ''}
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="assessments-actions">
        <button
          className="space-button primary"
          data-testid="roster-batch-submit"
          disabled={submission.busy || submittable.length === 0 || overLimit}
          onClick={() => void submit()}
        >
          {submission.busy
            ? '建立中…'
            : submission.phase === 'unknown'
              ? `重试同一提交（${submittable.length} 行）`
              : `一次建立 ${fresh.length} 名学生${
                  problems.length > 0 ? `（另 ${problems.length} 行需处理，不提交）` : ''
                }`}
        </button>
        <button className="space-button" disabled={submission.busy} onClick={onClose}>
          关闭
        </button>
      </div>
      <p className="assessments-hint">
        服务端一次事务逐行写入：学号已存在的行只跳过该行并如实报告；任一行非法则整批不写入。
      </p>
    </Modal>
  );
}
