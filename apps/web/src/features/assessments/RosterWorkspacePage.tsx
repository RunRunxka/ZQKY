'use client';

/**
 * 班级管理独立页（`/assessments/roster`，R5-FE 2026-10-11）。
 *
 * 版面（对齐用户参考图）：顶部班级选择（班级维度保留归档的班级选择器 + 新建/归档/彻底删除），
 * 下方「学生列表」卡：操作行 = 新增学生（主色）/ 批量导入（次色）/ 批量删除（红描边），
 * 再下方搜索框（占位「搜索学生姓名」），表格列 = 复选框 / 姓名 / 学号 / 性别 / 操作（编辑、删除），
 * 底部「共 N 条记录」+ 页码控件。批量导入沿用归档 `RosterImportPanel`（xlsx/csv → 审阅行 →
 * 确认落库，错误原样展示）。
 *
 * 真实状态全部来自 FastAPI：读取失败显示错误码与重试入口，**绝不显示成空名单**；
 * 删除是**归档**（软删除，可恢复，保留历史归属与既有施测记录），归档对象在「显示已归档」里可恢复。
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { Pencil, Plus, RefreshCw, RotateCcw, Trash2, Upload, UserPlus } from 'lucide-react';
import type { ClassView, StudentView } from '@/contracts/roster';
import {
  archiveClass,
  archiveStudent,
  createClass,
  createStudent,
  deleteClass,
  listClassStudents,
  listClasses,
  restoreClass,
  restoreStudent,
  updateStudent,
} from '@/services/assessments-api';
import { fetchTextbookTaxonomy } from '@/services/textbook-api';
import { Modal } from '@/components/ui/Modal';
import { useEntrance } from '@/components/motion/useEntrance';
import '@/components/layout/space.css';
import '@/features/assessments/styles/assessments.css';
import { asApiError, useAsyncResource } from './hooks';
import {
  CLASS_REFERENCE_LABELS,
  clampPage,
  filterStudentsByName,
  genderText,
  nameOrShortId,
  pageCount,
  referenceCounts,
} from './labels';
import { DeleteGuardNotice, type DeleteGuardState } from './DeleteGuardNotice';
import { RosterImportPanel } from './RosterImportPanel';

/** 每页行数（学生表）：服务端没有分页参数，翻页是视图层对真实全集的切片。 */
export const STUDENT_PAGE_SIZE = 10;

/** 表单字段的简短错误文案（保留服务端 code 与原话，不吞原因）。 */
function writeErrorText(action: string, error: { code: string; message: string }): string {
  return `${action}失败（${error.code}）：${error.message}`;
}

export function RosterWorkspacePage() {
  const pageRef = useRef<HTMLDivElement>(null);
  const tableRef = useRef<HTMLElement>(null);
  const importRef = useRef<HTMLDivElement>(null);
  const [refreshToken, setRefreshToken] = useState(0);
  /** 默认只取活跃班；打开后不传 status（服务端默认口径 = 全部）。归档班仍可读。 */
  const [showArchivedClasses, setShowArchivedClasses] = useState(false);
  const [selectedClassId, setSelectedClassId] = useState<string | null>(null);
  /** 归档写操作身份（禁用按钮防重入）与错误提示。 */
  const [writeBusyId, setWriteBusyId] = useState<string | null>(null);
  const [writeError, setWriteError] = useState<string | null>(null);
  const [deleteGuard, setDeleteGuard] = useState<DeleteGuardState | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [createClassOpen, setCreateClassOpen] = useState(false);
  const [createStudentOpen, setCreateStudentOpen] = useState(false);
  const [editStudent, setEditStudent] = useState<StudentView | null>(null);
  const [importOpen, setImportOpen] = useState(false);

  const classes = useAsyncResource(
    (signal) =>
      listClasses(
        showArchivedClasses ? { limit: 200 } : { status: 'active', limit: 200 },
        signal,
      ),
    `assessments-classes|${refreshToken}|${showArchivedClasses ? 'all' : 'active'}`,
  );
  const [refreshStudents, setRefreshStudents] = useState(0);
  const [showArchivedStudents, setShowArchivedStudents] = useState(false);
  const classItems = useMemo(() => classes.lastData?.items ?? [], [classes.lastData]);
  /**
   * 当前班级：显式选择优先；未选择（或所选班级已不在列表里）时回落到列表第一条。
   * 只读派生，不写状态——列表刷新后不会因为 effect 竞态选中不存在的班级。
   */
  const currentClass: ClassView | null = useMemo(() => {
    if (classItems.length === 0) return null;
    return classItems.find((item) => item.id === selectedClassId) ?? classItems[0];
  }, [classItems, selectedClassId]);
  const currentClassId = currentClass?.id ?? null;
  const students = useAsyncResource(
    (signal) =>
      currentClassId
        ? listClassStudents(currentClassId, { includeArchived: showArchivedStudents }, signal)
        : Promise.resolve({ items: [], total: 0, offset: 0, limit: 0 }),
    `assessments-class-students|${currentClassId ?? 'none'}|${
      showArchivedStudents ? 'all' : 'active'
    }|${refreshStudents}`,
  );

  const [studentQuery, setStudentQuery] = useState('');
  const [page, setPage] = useState(0);
  const [selectedIds, setSelectedIds] = useState<ReadonlySet<string>>(() => new Set());

  useEntrance(pageRef, { preset: 'page' });
  useEntrance(tableRef, { preset: 'panel', triggerKey: currentClassId ?? 'none' });
  useEntrance(importRef, { preset: 'panel', enabled: importOpen });

  // 切班/换筛选即清空选择：批量操作的集合不能跨班级偷渡。
  useEffect(() => {
    setSelectedIds(new Set());
    setPage(0);
  }, [currentClassId, showArchivedStudents]);

  const allStudents = useMemo(
    () => students.lastData?.items ?? [],
    [students.lastData],
  );
  const filtered = useMemo(
    () => filterStudentsByName(allStudents, studentQuery),
    [allStudents, studentQuery],
  );
  const pages = pageCount(filtered.length, STUDENT_PAGE_SIZE);
  const currentPage = clampPage(page, pages);
  const rows = filtered.slice(currentPage * STUDENT_PAGE_SIZE, (currentPage + 1) * STUDENT_PAGE_SIZE);
  const selectableRows = rows.filter((row) => row.status === 'active');
  const allRowsSelected = selectableRows.length > 0 && selectableRows.every((row) => selectedIds.has(row.id));

  const taxonomy = useAsyncResource(fetchTextbookTaxonomy, 'assessments-class-taxonomy');
  const gradeLabel = (gradeId: string) =>
    taxonomy.lastData?.grades.find((grade) => grade.id === gradeId)?.label ?? null;

  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  function reloadAll() {
    classes.reload();
    setRefreshStudents((value) => value + 1);
    setRefreshToken((value) => value + 1);
  }

  async function writeClass(
    item: ClassView,
    archived: boolean,
    confirmText?: string,
  ): Promise<boolean> {
    if (writeBusyId !== null) return false;
    if (confirmText && !window.confirm(confirmText)) return false;
    setWriteBusyId(item.id);
    setWriteError(null);
    setNotice(null);
    try {
      if (archived) await restoreClass(item.id, { expectedRevision: item.revision });
      else await archiveClass(item.id, { expectedRevision: item.revision });
      if (!mounted.current) return true;
      setNotice(`已${archived ? '恢复' : '归档'}班级「${item.name}」。`);
      reloadAll();
      return true;
    } catch (cause) {
      if (!mounted.current) return false;
      setWriteError(writeErrorText(`${archived ? '恢复' : '归档'}班级`, asApiError(cause)));
      return false;
    } finally {
      if (mounted.current) setWriteBusyId(null);
    }
  }

  /**
   * 彻底删除班级（受引用守卫的物理删除，二次确认）：被归属/名单导入/施测范围/教案任一引用时
   * 服务端 409 `CLASS_IN_USE`，把 message 与 `details.counts` 逐项显示，并给「改为归档」；
   * 乐观锁冲突 / 404 按既有错误区呈现（不伪装成引用问题）。
   */
  async function deleteClassItem(item: ClassView) {
    if (writeBusyId !== null) return;
    if (
      !window.confirm(
        `彻底删除班级「${item.name}」？这是物理删除、不可恢复；被归属记录/名单导入/施测范围/教案引用时会被拒绝并逐项列出引用。`,
      )
    ) {
      return;
    }
    setWriteBusyId(item.id);
    setWriteError(null);
    setDeleteGuard(null);
    setNotice(null);
    try {
      await deleteClass(item.id, item.revision);
      if (!mounted.current) return;
      setNotice(`已彻底删除班级「${item.name}」：物理删除完成，不可恢复。`);
      setSelectedClassId(null);
      reloadAll();
    } catch (cause) {
      if (!mounted.current) return;
      const error = asApiError(cause);
      if (error.status === 409 && error.code === 'CLASS_IN_USE') {
        setDeleteGuard({
          targetId: item.id,
          error,
          reasons: referenceCounts(error.details, CLASS_REFERENCE_LABELS),
        });
      } else {
        setWriteError(writeErrorText('彻底删除班级', error));
      }
    } finally {
      if (mounted.current) setWriteBusyId(null);
    }
  }

  /** 归档学生（软删除）：历史归属与既有施测记录保留，可在「显示已归档」里恢复。 */
  async function archiveStudentItem(student: StudentView) {
    if (writeBusyId !== null) return;
    if (
      !window.confirm(
        `删除学生「${student.name}」？删除为归档：本班名单不再显示，历史归属与既有施测记录保留，可在「显示已归档」中恢复。`,
      )
    ) {
      return;
    }
    setWriteBusyId(student.id);
    setWriteError(null);
    setNotice(null);
    try {
      await archiveStudent(student.id, { expectedRevision: student.revision });
      if (!mounted.current) return;
      setNotice(`已删除（归档）学生「${student.name}」，可随时恢复。`);
      setSelectedIds((current) => {
        const next = new Set(current);
        next.delete(student.id);
        return next;
      });
      reloadAll();
    } catch (cause) {
      if (!mounted.current) return;
      setWriteError(writeErrorText('删除学生', asApiError(cause)));
    } finally {
      if (mounted.current) setWriteBusyId(null);
    }
  }

  async function restoreStudentItem(student: StudentView) {
    if (writeBusyId !== null) return;
    setWriteBusyId(student.id);
    setWriteError(null);
    setNotice(null);
    try {
      await restoreStudent(student.id, { expectedRevision: student.revision });
      if (!mounted.current) return;
      setNotice(`已恢复学生「${student.name}」。`);
      reloadAll();
    } catch (cause) {
      if (!mounted.current) return;
      setWriteError(writeErrorText('恢复学生', asApiError(cause)));
    } finally {
      if (mounted.current) setWriteBusyId(null);
    }
  }

  /**
   * 批量删除（归档）：逐名学生走同一条受守卫接口；失败**不静默**——列出失败姓名与原因，
   * 已成功的照常刷新，未成功的保持选中，便于重试（不做"部分成功却报成功"）。
   */
  async function batchArchive() {
    if (writeBusyId !== null) return;
    const targets = allStudents.filter((student) => selectedIds.has(student.id));
    if (targets.length === 0) return;
    if (
      !window.confirm(
        `删除选中的 ${targets.length} 名学生？删除为归档：本班名单不再显示，历史归属与既有施测记录保留，可在「显示已归档」中恢复。`,
      )
    ) {
      return;
    }
    setWriteBusyId('batch');
    setWriteError(null);
    setNotice(null);
    const failures: string[] = [];
    const done = new Set<string>();
    for (const student of targets) {
      try {
        await archiveStudent(student.id, { expectedRevision: student.revision });
        done.add(student.id);
      } catch (cause) {
        const error = asApiError(cause);
        failures.push(`${student.name}（${error.code}：${error.message}）`);
      }
      if (!mounted.current) return;
    }
    if (!mounted.current) return;
    setWriteBusyId(null);
    setSelectedIds(new Set(targets.filter((s) => !done.has(s.id)).map((s) => s.id)));
    if (failures.length > 0) {
      setWriteError(
        `批量删除未全部完成：成功 ${done.size} 人；失败 ${failures.length} 人——${failures.join('；')}`,
      );
    } else {
      setNotice(`已删除（归档）选中的 ${done.size} 名学生，可随时恢复。`);
    }
    reloadAll();
  }

  return (
    <div ref={pageRef} className="space-page assessments-page">
      <header className="space-header" data-motion-reveal>
        <div className="space-header-row">
          <h1>班级管理</h1>
          <div className="assessments-actions">
            <label className="assessments-check">
              <input
                type="checkbox"
                aria-label="显示已归档班级"
                checked={showArchivedClasses}
                onChange={(event) => setShowArchivedClasses(event.target.checked)}
              />
              <span>显示已归档班级</span>
            </label>
            <button className="space-button" onClick={reloadAll}>
              <RefreshCw size={13} aria-hidden /> 刷新
            </button>
          </div>
        </div>
        <p className="space-description">
          按班级维护学生名单：支持一键导入 xlsx/csv 名单、逐个添加与编辑、删除（归档可恢复）。
          名单里的学生身份来自后端真实数据，未出现的学生不会自动退班。
        </p>
      </header>

      <main className="space-content">
        <section className="assessments-subpanel" aria-label="班级">
          <div className="assessments-subpanel-head">
            <h2 className="assessments-card-title">班级</h2>
            {currentClass && (
              <span className="space-chip">{currentClass.studentCount} 名学生</span>
            )}
          </div>
          {classes.state.phase === 'failed' && (
            <p className="space-banner error" role="alert" data-testid="assessments-classes-error">
              班级列表读取失败（{classes.state.error.code}）：{classes.state.error.message}
              {classes.lastData ? ' 下方仍显示上一次成功读取的班级。' : ''}
              <button className="space-button" onClick={classes.reload}>
                重试读取班级
              </button>
            </p>
          )}
          {classes.state.phase === 'ready' && classItems.length === 0 && (
            <p className="space-empty" data-testid="assessments-classes-empty">
              <strong>还没有班级</strong>
              <span>先新建一个班级，再导入或添加学生名单。</span>
            </p>
          )}
          {classItems.length > 0 && (
            <div className="assessments-form">
              <label className="assessments-field">
                <span>当前班级</span>
                <select
                  className="space-select"
                  aria-label="当前班级"
                  value={currentClassId ?? ''}
                  disabled={writeBusyId !== null}
                  onChange={(event) => setSelectedClassId(event.target.value)}
                >
                  {classItems.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                      {item.status === 'archived' ? '（已归档）' : ''}
                      {` · ${item.code}`}
                    </option>
                  ))}
                </select>
              </label>
              {currentClass && gradeLabel(currentClass.gradeId) && (
                <span className="assessments-field-static">
                  年级 {gradeLabel(currentClass.gradeId)} · 学年 {currentClass.schoolYear}
                </span>
              )}
              <button
                className="space-button primary"
                disabled={writeBusyId !== null}
                onClick={() => setCreateClassOpen(true)}
              >
                <Plus size={13} aria-hidden /> 新建班级
              </button>
              {currentClass && currentClass.status === 'active' && (
                <button
                  className="space-button"
                  disabled={writeBusyId !== null}
                  data-testid={`assessments-class-archive-${currentClass.id}`}
                  onClick={() =>
                    void writeClass(
                      currentClass,
                      false,
                      `归档班级「${currentClass.name}」？归档班级仍可读，但不能再导入名单；历史归属与既有施测保留。`,
                    )
                  }
                >
                  {writeBusyId === currentClass.id ? '归档中…' : '归档班级'}
                </button>
              )}
              {currentClass && currentClass.status === 'archived' && (
                <button
                  className="space-button"
                  disabled={writeBusyId !== null}
                  data-testid={`assessments-class-restore-${currentClass.id}`}
                  onClick={() => void writeClass(currentClass, true)}
                >
                  {writeBusyId === currentClass.id ? '恢复中…' : '恢复班级'}
                </button>
              )}
              {currentClass && (
                <button
                  className="space-button danger"
                  disabled={writeBusyId !== null}
                  data-testid={`assessments-class-delete-${currentClass.id}`}
                  onClick={() => void deleteClassItem(currentClass)}
                >
                  {writeBusyId === currentClass.id ? '删除中…' : '彻底删除班级'}
                </button>
              )}
            </div>
          )}
          {writeError && (
            <p className="space-banner error" role="alert" data-testid="assessments-roster-write-error">
              {writeError}
            </p>
          )}
          {notice && (
            <p className="space-banner info" role="status" data-testid="assessments-roster-notice">
              {notice}
            </p>
          )}
          {deleteGuard && (
            <DeleteGuardNotice
              state={deleteGuard}
              targetName={nameOrShortId(
                classItems.find((item) => item.id === deleteGuard.targetId)?.name,
                deleteGuard.targetId,
              )}
              archiving={writeBusyId === deleteGuard.targetId}
              testId="assessments-class-delete-guard"
              onArchive={() => {
                const target = classItems.find((item) => item.id === deleteGuard.targetId);
                if (target) void writeClass(target, false);
              }}
            />
          )}
        </section>

        <section className="assessments-subpanel" ref={tableRef} aria-label="学生列表">
          <div className="assessments-subpanel-head">
            <h2 className="assessments-card-title">学生列表</h2>
            {currentClass && <span className="space-chip">{currentClass.name}</span>}
            <label className="assessments-check">
              <input
                type="checkbox"
                aria-label="显示已归档学生"
                checked={showArchivedStudents}
                onChange={(event) => setShowArchivedStudents(event.target.checked)}
              />
              <span>显示已归档</span>
            </label>
          </div>

          {!currentClassId && (
            <p className="space-empty" data-testid="assessments-students-no-class">
              <strong>请先选择或新建一个班级</strong>
              <span>学生名单按班级维护：选定班级后即可添加、导入与编辑学生。</span>
            </p>
          )}

          {currentClassId && (
            <>
              <div className="assessments-actions" role="group" aria-label="学生列表操作">
                <button
                  className="space-button primary"
                  disabled={writeBusyId !== null}
                  data-testid="assessments-student-add"
                  onClick={() => setCreateStudentOpen(true)}
                >
                  <UserPlus size={14} aria-hidden /> 新增学生
                </button>
                <button
                  className="space-button"
                  disabled={writeBusyId !== null}
                  data-testid="assessments-student-import"
                  onClick={() => setImportOpen(true)}
                >
                  <Upload size={14} aria-hidden /> 批量导入
                </button>
                <button
                  className="space-button danger"
                  disabled={writeBusyId !== null || selectedIds.size === 0}
                  data-testid="assessments-student-batch-delete"
                  onClick={() => void batchArchive()}
                >
                  <Trash2 size={14} aria-hidden /> 批量删除
                  {selectedIds.size > 0 ? `（${selectedIds.size}）` : ''}
                </button>
              </div>

              <label className="assessments-field assessments-search-field">
                <span className="visually-hidden">搜索学生姓名</span>
                <input
                  className="assessments-input assessments-search"
                  type="search"
                  placeholder="搜索学生姓名"
                  aria-label="搜索学生姓名"
                  value={studentQuery}
                  onChange={(event) => {
                    setStudentQuery(event.target.value);
                    setPage(0);
                  }}
                />
              </label>

              {students.state.phase === 'failed' && (
                <p className="space-banner error" role="alert" data-testid="assessments-students-error">
                  学生名单读取失败（{students.state.error.code}）：{students.state.error.message}
                  {students.lastData ? ' 下方仍显示上一次成功读取的名单。' : ' 这不是空名单。'}
                  <button className="space-button" onClick={students.reload}>
                    重试读取名单
                  </button>
                </p>
              )}

              {students.state.phase === 'ready' && allStudents.length === 0 && (
                <p className="space-empty" data-testid="assessments-students-empty">
                  <strong>这个班级还没有学生</strong>
                  <span>用「新增学生」逐个添加，或用「批量导入」上传 xlsx/csv 名单并校对。</span>
                </p>
              )}

              {allStudents.length > 0 && (
                <>
                  <div className="assessments-table-wrap" tabIndex={0} aria-label="学生名单表格，可横向滚动">
                    <table className="assessments-table">
                      <caption className="visually-hidden">
                        {currentClass?.name ?? ''} 学生名单（姓名、学号、性别与操作）
                      </caption>
                      <thead>
                        <tr>
                          <th scope="col" className="assessments-col-check">
                            <input
                              type="checkbox"
                              aria-label="全选本页学生"
                              checked={allRowsSelected}
                              disabled={selectableRows.length === 0}
                              onChange={(event) =>
                                setSelectedIds((current) => {
                                  const next = new Set(current);
                                  for (const row of selectableRows) {
                                    if (event.target.checked) next.add(row.id);
                                    else next.delete(row.id);
                                  }
                                  return next;
                                })
                              }
                            />
                          </th>
                          <th scope="col">姓名</th>
                          <th scope="col">学号</th>
                          <th scope="col">性别</th>
                          <th scope="col">操作</th>
                        </tr>
                      </thead>
                      <tbody>
                        {rows.map((student) => (
                          <tr
                            key={student.id}
                            data-testid={`assessments-student-${student.id}`}
                            className={student.status === 'archived' ? 'archived' : undefined}
                          >
                            <td className="assessments-col-check">
                              <input
                                type="checkbox"
                                aria-label={`选择学生 ${student.name}`}
                                checked={selectedIds.has(student.id)}
                                disabled={student.status === 'archived'}
                                onChange={(event) =>
                                  setSelectedIds((current) => {
                                    const next = new Set(current);
                                    if (event.target.checked) next.add(student.id);
                                    else next.delete(student.id);
                                    return next;
                                  })
                                }
                              />
                            </td>
                            <td>
                              <span className="assessments-student-name">{student.name}</span>
                              {student.status === 'archived' && (
                                <span className="space-chip" data-testid={`assessments-student-archived-${student.id}`}>
                                  已归档
                                </span>
                              )}
                            </td>
                            <td className="assessments-cell-num">
                              {student.studentNo ?? <span className="assessments-cell-muted">未记录</span>}
                            </td>
                            <td>{genderText(student.gender)}</td>
                            <td>
                              <div className="assessments-row-actions">
                                <button
                                  className="assessments-link-button"
                                  disabled={writeBusyId !== null}
                                  data-testid={`assessments-student-edit-${student.id}`}
                                  onClick={() => setEditStudent(student)}
                                >
                                  <Pencil size={12} aria-hidden /> 编辑
                                </button>
                                {student.status === 'archived' ? (
                                  <button
                                    className="assessments-link-button"
                                    disabled={writeBusyId !== null}
                                    data-testid={`assessments-student-restore-${student.id}`}
                                    onClick={() => void restoreStudentItem(student)}
                                  >
                                    <RotateCcw size={12} aria-hidden /> 恢复
                                  </button>
                                ) : (
                                  <button
                                    className="assessments-link-button danger"
                                    disabled={writeBusyId !== null}
                                    data-testid={`assessments-student-delete-${student.id}`}
                                    onClick={() => void archiveStudentItem(student)}
                                  >
                                    <Trash2 size={12} aria-hidden /> 删除
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  {filtered.length === 0 && (
                    <p className="assessments-hint" data-testid="assessments-students-no-match">
                      没有姓名匹配「{studentQuery.trim()}」的学生。
                    </p>
                  )}
                  <div className="assessments-pagination">
                    <span data-testid="assessments-students-total">共 {filtered.length} 条记录</span>
                    <div className="assessments-actions">
                      <button
                        className="space-button"
                        disabled={currentPage === 0}
                        aria-label="上一页"
                        onClick={() => setPage(Math.max(0, currentPage - 1))}
                      >
                        上一页
                      </button>
                      <span className="assessments-meta" data-testid="assessments-students-page">
                        第 {currentPage + 1} / {pages} 页
                      </span>
                      <button
                        className="space-button"
                        disabled={currentPage >= pages - 1}
                        aria-label="下一页"
                        onClick={() => setPage(Math.min(pages - 1, currentPage + 1))}
                      >
                        下一页
                      </button>
                    </div>
                  </div>
                </>
              )}
            </>
          )}
        </section>

        <p className="space-footnote">
          班级、学生与导入批次都以后端为准：读取失败会显示具体错误码并保留上一次成功数据，
          删除是归档（可恢复）而不是抹除历史，导入的每一行都要人工确认后才落库。
        </p>
      </main>

      {createClassOpen && (
        <CreateClassDialog
          grades={taxonomy.lastData?.grades ?? []}
          taxonomyError={
            taxonomy.state.phase === 'failed'
              ? `${taxonomy.state.error.code}：${taxonomy.state.error.message}`
              : null
          }
          onRetryTaxonomy={taxonomy.reload}
          onClose={() => setCreateClassOpen(false)}
          onCreated={(created) => {
            setCreateClassOpen(false);
            setSelectedClassId(created.id);
            setNotice(`已新建班级「${created.name}」。`);
            reloadAll();
          }}
        />
      )}

      {createStudentOpen && currentClassId && (
        <StudentFormDialog
          mode="create"
          classId={currentClassId}
          className={currentClass?.name ?? ''}
          student={null}
          onClose={() => setCreateStudentOpen(false)}
          onSaved={() => {
            setCreateStudentOpen(false);
            reloadAll();
          }}
        />
      )}

      {editStudent && (
        <StudentFormDialog
          mode="edit"
          classId={currentClassId ?? ''}
          className={currentClass?.name ?? ''}
          student={editStudent}
          onClose={() => setEditStudent(null)}
          onSaved={() => {
            setEditStudent(null);
            reloadAll();
          }}
        />
      )}

      {importOpen && currentClassId && (
        <Modal title={`批量导入学生 · ${currentClass?.name ?? ''}`} onClose={() => setImportOpen(false)}>
          <div ref={importRef}>
            <RosterImportPanel
              classId={currentClassId}
              onChanged={() => {
                setRefreshStudents((value) => value + 1);
                setRefreshToken((value) => value + 1);
              }}
            />
          </div>
        </Modal>
      )}
    </div>
  );
}

/** 新建班级：编码 / 名称 / 学年 / 年级（年级字典来自 `GET /textbook-taxonomy`）。 */
function CreateClassDialog({
  grades,
  taxonomyError,
  onRetryTaxonomy,
  onClose,
  onCreated,
}: {
  grades: { id: string; label: string }[];
  taxonomyError: string | null;
  onRetryTaxonomy: () => void;
  onClose: () => void;
  onCreated: (created: ClassView) => void;
}) {
  const [code, setCode] = useState('');
  const [name, setName] = useState('');
  const [schoolYear, setSchoolYear] = useState(String(new Date().getFullYear()));
  const [gradeId, setGradeId] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const created = await createClass({
        code: code.trim(),
        name: name.trim(),
        schoolYear: schoolYear.trim(),
        gradeId: gradeId.trim(),
      });
      onCreated(created);
    } catch (cause) {
      const issue = asApiError(cause);
      setError(`${writeErrorText('建立班级', issue)} 输入已保留，可修改后重试。`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="新建班级" onClose={onClose}>
      <form
        className="assessments-form"
        aria-label="新建班级"
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <label className="assessments-field">
          <span>班级名称</span>
          <input
            className="assessments-input"
            aria-label="班级名称"
            value={name}
            disabled={busy}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label className="assessments-field">
          <span>班级编码</span>
          <input
            className="assessments-input"
            aria-label="班级编码"
            value={code}
            disabled={busy}
            onChange={(event) => setCode(event.target.value)}
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
          />
        </label>
        <label className="assessments-field">
          <span>年级</span>
          <select
            className="space-select"
            aria-label="年级"
            value={gradeId}
            disabled={busy || grades.length === 0}
            onChange={(event) => setGradeId(event.target.value)}
          >
            <option value="">请选择年级</option>
            {grades.map((grade) => (
              <option key={grade.id} value={grade.id}>
                {grade.label}
              </option>
            ))}
          </select>
        </label>
        {taxonomyError && (
          <p className="space-banner error" role="alert">
            年级字典读取失败（{taxonomyError}）——没有年级无法建立班级。
            <button className="space-button" type="button" onClick={onRetryTaxonomy}>
              重试读取年级
            </button>
          </p>
        )}
        {error && (
          <p className="space-banner error" role="alert">
            {error}
          </p>
        )}
        <div className="assessments-form-footer">
          <button className="space-button" type="button" disabled={busy} onClick={onClose}>
            取消
          </button>
          <button
            className="space-button primary"
            type="submit"
            disabled={busy || !code.trim() || !name.trim() || !schoolYear.trim() || !gradeId.trim()}
          >
            {busy ? '建立中…' : '建立班级'}
          </button>
        </div>
      </form>
    </Modal>
  );
}

/** 新增 / 编辑学生：姓名 + 学号（学号按文本保存，保留前导零）。 */
function StudentFormDialog({
  mode,
  classId,
  className,
  student,
  onClose,
  onSaved,
}: {
  mode: 'create' | 'edit';
  classId: string;
  className: string;
  student: StudentView | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(student?.name ?? '');
  const [studentNo, setStudentNo] = useState(student?.studentNo ?? '');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [conflictRevision, setConflictRevision] = useState<number | null>(null);

  async function submit() {
    if (busy) return;
    setBusy(true);
    setError(null);
    setConflictRevision(null);
    try {
      if (mode === 'create') {
        await createStudent({
          name: name.trim(),
          studentNo: studentNo.trim() === '' ? null : studentNo.trim(),
          classId: classId || null,
        });
      } else if (student) {
        await updateStudent(student.id, {
          expectedRevision: student.revision,
          name: name.trim(),
          // 空学号必须显式送 null（服务端按文本保存：空串与"未记录"语义不同）
          studentNo: studentNo.trim() === '' ? null : studentNo.trim(),
        });
      }
      onSaved();
    } catch (cause) {
      const issue = asApiError(cause);
      setError(`${writeErrorText(mode === 'create' ? '添加学生' : '保存学生', issue)} 输入已保留，可修改后重试。`);
      if (issue.status === 409 && typeof issue.details?.currentRevision === 'number') {
        setConflictRevision(issue.details.currentRevision);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={mode === 'create' ? `新增学生 · ${className}` : `编辑学生 · ${student?.name ?? ''}`} onClose={onClose}>
      <form
        className="assessments-form"
        aria-label={mode === 'create' ? '新增学生' : '编辑学生'}
        onSubmit={(event) => {
          event.preventDefault();
          void submit();
        }}
      >
        <label className="assessments-field">
          <span>姓名</span>
          <input
            className="assessments-input"
            aria-label="学生姓名"
            value={name}
            disabled={busy}
            onChange={(event) => setName(event.target.value)}
          />
        </label>
        <label className="assessments-field">
          <span>学号（可留空）</span>
          <input
            className="assessments-input"
            aria-label="学生学号"
            value={studentNo}
            disabled={busy}
            onChange={(event) => setStudentNo(event.target.value)}
          />
        </label>
        {mode === 'edit' && (
          <p className="assessments-hint">
            性别列来自后端名单数据；后端未提供该字段时显示「未记录」，本页不手工改写。
          </p>
        )}
        {error && (
          <p className="space-banner error" role="alert" data-testid="assessments-student-form-error">
            {error}
            {conflictRevision !== null && (
              <span> 服务端当前版本 r{conflictRevision}；请刷新名单后再对照保存，不会静默覆盖。</span>
            )}
          </p>
        )}
        <div className="assessments-form-footer">
          <button className="space-button" type="button" disabled={busy} onClick={onClose}>
            取消
          </button>
          <button className="space-button primary" type="submit" disabled={busy || !name.trim()}>
            {busy ? '保存中…' : mode === 'create' ? '添加学生' : '保存修改'}
          </button>
        </div>
      </form>
    </Modal>
  );
}
