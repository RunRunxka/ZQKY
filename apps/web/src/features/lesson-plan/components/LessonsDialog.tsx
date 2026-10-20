'use client';
/**
 * 本地教案对话框（R7-FE；R10-FE 2026-10-13 去「云端」措辞 + 加删除）。
 *
 * 教案实际存在**本机后端**（FastAPI + 数据目录 `.local-data`，不联网、不外发），
 * 因此界面统一叫「本地教案」，不再用"云端"这种会让人以为数据上云的措辞。
 *
 * 列出 `GET /lesson-plans` 的教案：打开 / 新建 / **彻底删除**（无归档）。
 * 列表读取失败时显示真实原因与重试入口；**不当空目录**（空列表必须来自服务端的空 items）。
 */
import { useCallback, useEffect, useState } from 'react';
import { LoaderCircle, Plus, RefreshCw, Trash2 } from 'lucide-react';
import { fetchTextbookTaxonomy } from '@/services/textbook-api';
import { listClasses } from '@/services/assessments-api';
import { Modal } from '@/components/ui/Modal';
import { ApiError } from '@/services/api-client';
import { LESSON_PLANS_CHANGED_EVENT } from '@/services/lesson-plans-events';
import type { LessonSummary } from '@/contracts/lesson-plans';
import type { LessonPlansApi } from '@/services/lesson-plans-api';

type ListState =
  | { status: 'loading' }
  | { status: 'ready'; items: LessonSummary[]; total: number }
  | { status: 'error'; message: string };

/** 删除二次确认：把会一起删掉的东西与不受影响的东西都写明（删除不可恢复）。 */
export function deleteLessonConfirmText(title: string | null | undefined): string {
  return (
    `彻底删除教案「${title || '（未命名教案）'}」？\n\n` +
    '这会物理删除这份教案及其全部历史（修订、AI 生成输入与候选、校对记录），不可恢复。\n' +
    '学生、班级、成绩、学情报告与试卷不受影响。'
  );
}

/** 归属选项的加载入口（可注入测试替身）：学科来自教材分类字典，班级来自班级管理。 */
export interface LessonOwnershipServices {
  loadSubjects: () => Promise<{ id: string; label: string }[]>;
  loadClasses: () => Promise<{ id: string; name: string }[]>;
}

const defaultOwnershipServices: LessonOwnershipServices = {
  loadSubjects: async () => (await fetchTextbookTaxonomy()).subjects,
  loadClasses: async () => (await listClasses({ limit: 200 })).items,
};

export function LessonsDialog({
  api,
  currentPlanId,
  ownership,
  onOwnershipChange,
  onOpen,
  onCreate,
  onDeleted,
  ownershipServices = defaultOwnershipServices,
  onClose,
}: {
  api: LessonPlansApi;
  currentPlanId: string | null;
  /** 教案归属（学科 + 班级）：教案必须属于某班某科，后端要求非空。 */
  ownership: { subjectId: string; classId: string };
  onOwnershipChange: (ownership: { subjectId: string; classId: string }) => void;
  onOpen: (lessonPlanId: string) => Promise<unknown>;
  onCreate: () => Promise<unknown>;
  /** 删除成功回执（由工作台清掉"当前教案"并给提示）。 */
  onDeleted?: (result: { lessonPlanId: string; title: string; removedRevisions: number }) => void;
  ownershipServices?: LessonOwnershipServices;
  onClose: () => void;
}) {
  const [state, setState] = useState<ListState>({ status: 'loading' });
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  /** 归属字典（学科 / 班级）：读取失败如实显示并可重试；空列表给出建班/配字典的去处。 */
  const [subjects, setSubjects] = useState<{ id: string; label: string }[] | null>(null);
  const [classes, setClasses] = useState<{ id: string; name: string }[] | null>(null);
  const [ownershipError, setOwnershipError] = useState<string | null>(null);

  const loadOwnership = useCallback(async () => {
    setOwnershipError(null);
    try {
      const [subjectList, classList] = await Promise.all([
        ownershipServices.loadSubjects(),
        ownershipServices.loadClasses(),
      ]);
      setSubjects(subjectList);
      setClasses(classList);
    } catch (error) {
      setSubjects(null);
      setClasses(null);
      setOwnershipError(
        error instanceof ApiError ? `${error.code}：${error.message}` : (error instanceof Error ? error.message : '未知错误'),
      );
    }
  }, [ownershipServices]);

  useEffect(() => {
    void loadOwnership();
  }, [loadOwnership]);

  /* 首次进来归属为空时给一个**可见、可改**的默认（取字典/班级列表第一项），
     而不是让"新建"键一直灰着；用户改了会写入本机记忆。 */
  useEffect(() => {
    if (ownership.subjectId || ownership.classId) return;
    const firstSubject = subjects?.[0]?.id ?? '';
    const firstClass = classes?.[0]?.id ?? '';
    if (firstSubject || firstClass) {
      onOwnershipChange({ subjectId: firstSubject, classId: firstClass });
    }
  }, [classes, onOwnershipChange, ownership.classId, ownership.subjectId, subjects]);

  const load = useCallback(async () => {
    setState({ status: 'loading' });
    try {
      const page = await api.listLessonPlans();
      setState({ status: 'ready', items: page.items, total: page.total });
    } catch (error) {
      setState({
        status: 'error',
        message:
          error instanceof ApiError
            ? `${error.code}：${error.message}`
            : error instanceof Error
              ? error.message
              : '未知错误',
      });
    }
  }, [api]);

  useEffect(() => {
    void load();
  }, [load]);

  /* 对话里生成/应用教案成功后广播事件：已打开的列表立即重载（不要求教师手动刷新）。 */
  useEffect(() => {
    const onChange = () => void load();
    window.addEventListener(LESSON_PLANS_CHANGED_EVENT, onChange);
    return () => window.removeEventListener(LESSON_PLANS_CHANGED_EVENT, onChange);
  }, [load]);

  const run = async (id: string | null, action: () => Promise<unknown>) => {
    setBusyId(id ?? 'new');
    setActionError(null);
    try {
      await action();
      onClose();
    } catch (error) {
      setActionError(error instanceof Error ? error.message : '操作失败。');
    } finally {
      setBusyId(null);
    }
  };

  /**
   * 彻底删除一份教案：二次确认点名后果 → `DELETE ?expectedRevision=N`（乐观锁用列表里的修订号）
   * → 从列表就地移除（不留已删行）。失败（409 乐观锁 / 404 / 引用守卫）原样显示服务端 code。
   */
  const removeLesson = async (item: LessonSummary, title: string) => {
    if (busyId !== null) return;
    if (!window.confirm(deleteLessonConfirmText(title))) return;
    setBusyId(item.lessonPlanId);
    setActionError(null);
    try {
      const result = await api.deleteLessonPlan(item.lessonPlanId, item.revision);
      setState((current) =>
        current.status === 'ready'
          ? {
              ...current,
              items: current.items.filter((entry) => entry.lessonPlanId !== item.lessonPlanId),
              total: Math.max(0, current.total - 1),
            }
          : current,
      );
      onDeleted?.({
        lessonPlanId: item.lessonPlanId,
        title,
        removedRevisions: result.removedRevisions,
      });
    } catch (error) {
      setActionError(
        error instanceof ApiError
          ? `删除教案失败（${error.code}）：${error.message}`
          : `删除教案失败：${error instanceof Error ? error.message : '未知错误'}`,
      );
    } finally {
      setBusyId(null);
    }
  };

  return (
    <Modal title="本地教案" onClose={onClose}>
      <div className="lw-dialog" data-testid="lw-lessons-dialog">
        <p className="lw-note">
          教案保存在本机后端（数据目录 <code>.local-data</code>，不联网、不外发）；
          这里可以打开、新建或彻底删除（删除不可恢复，不做归档）。
        </p>
        <div className="lw-dialog-ownership">
          <strong>教案归属</strong>
          {ownershipError && (
            <span className="lw-error" role="alert" data-testid="lw-dialog-ownership-error">
              学科/班级读取失败（{ownershipError}）
              <button type="button" className="lw-button small" onClick={() => void loadOwnership()}>
                重试
              </button>
            </span>
          )}
          <label className="lw-field">
            学科
            <select
              className="lw-select"
              aria-label="教案学科"
              data-testid="lw-dialog-subject"
              value={ownership.subjectId}
              disabled={busyId !== null || subjects === null}
              onChange={(event) => onOwnershipChange({ ...ownership, subjectId: event.target.value })}
            >
              <option value="">请选择学科</option>
              {(subjects ?? []).map((subject) => (
                <option key={subject.id} value={subject.id}>
                  {subject.label}
                </option>
              ))}
            </select>
          </label>
          <label className="lw-field">
            班级
            <select
              className="lw-select"
              aria-label="教案班级"
              data-testid="lw-dialog-class"
              value={ownership.classId}
              disabled={busyId !== null || classes === null}
              onChange={(event) => onOwnershipChange({ ...ownership, classId: event.target.value })}
            >
              <option value="">请选择班级</option>
              {(classes ?? []).map((klass) => (
                <option key={klass.id} value={klass.id}>
                  {klass.name}
                </option>
              ))}
            </select>
          </label>
          {classes !== null && classes.length === 0 && (
            <span className="lw-note" data-testid="lw-dialog-no-class">
              还没有班级：先到「班级管理」新建班级，再回来保存教案。
            </span>
          )}
          {subjects !== null && subjects.length === 0 && (
            <span className="lw-note">学科字典为空：先到「教材资料库」确认学科配置。</span>
          )}
          <span className="lw-note">教案必须属于某班某科（保存后「班级管理」里能看到这份教案的归属）。</span>
        </div>

        <div className="lw-dialog-actions">
          <button
            type="button"
            className="lw-button primary"
            data-testid="lw-dialog-create"
            disabled={busyId !== null || !ownership.subjectId || !ownership.classId}
            title={
              !ownership.subjectId || !ownership.classId
                ? '先选择教案归属（学科 + 班级）'
                : '把当前编辑内容保存为一份新的本地教案'
            }
            onClick={() => void run(null, onCreate)}
          >
            {busyId === 'new' ? <LoaderCircle size={15} className="lw-spin" /> : <Plus size={15} />}
            新建本地教案
          </button>
          <button type="button" className="lw-button" onClick={() => void load()}>
            <RefreshCw size={15} aria-hidden />
            刷新列表
          </button>
        </div>

        {state.status === 'loading' && <p className="lw-note" role="status">正在读取本地教案…</p>}
        {state.status === 'error' && (
          <p className="lw-error" data-testid="lw-dialog-error">
            教案列表读取失败：{state.message}
          </p>
        )}
        {state.status === 'ready' && state.items.length === 0 && (
          <p className="lw-note" data-testid="lw-dialog-empty">
            本机还没有教案；点「新建本地教案」会把当前编辑内容保存为第一份。
          </p>
        )}
        {state.status === 'ready' && state.items.length > 0 && (
          <ul className="lw-dialog-list" data-testid="lw-dialog-list">
            {state.items.map((item) => {
              const title = item.title || '（未命名教案）';
              return (
                <li key={item.lessonPlanId}>
                  <div className="lw-dialog-item">
                    <strong>{title}</strong>
                    <small>
                      修订 {item.revision} ·{' '}
                      {item.updatedAt ? item.updatedAt.slice(0, 16).replace('T', ' ') : '时间未知'}
                    </small>
                  </div>
                  <button
                    type="button"
                    className="lw-button small"
                    data-testid={`lw-dialog-open-${item.lessonPlanId}`}
                    disabled={busyId !== null || item.lessonPlanId === currentPlanId}
                    onClick={() => void run(item.lessonPlanId, () => onOpen(item.lessonPlanId))}
                  >
                    {item.lessonPlanId === currentPlanId ? '当前打开' : '打开'}
                  </button>
                  <button
                    type="button"
                    className="lw-button small danger"
                    data-testid={`lw-dialog-delete-${item.lessonPlanId}`}
                    disabled={busyId !== null}
                    title={`彻底删除「${title}」（不可恢复）`}
                    onClick={() => void removeLesson(item, title)}
                  >
                    {busyId === item.lessonPlanId ? (
                      <LoaderCircle size={14} className="lw-spin" aria-hidden />
                    ) : (
                      <Trash2 size={14} aria-hidden />
                    )}
                    删除
                  </button>
                </li>
              );
            })}
          </ul>
        )}
        {actionError && (
          <p className="lw-error" data-testid="lw-dialog-action-error">
            操作失败：{actionError}
          </p>
        )}
        <p className="lw-note">
          打开本地教案会以本机后端保存的版本替换本页内容；本机草稿在同步前仍保留在浏览器里。
        </p>
      </div>
    </Modal>
  );
}
