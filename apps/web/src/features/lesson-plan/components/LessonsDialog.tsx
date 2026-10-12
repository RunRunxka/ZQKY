'use client';
/**
 * 云端教案对话框（R7-FE）：列出 `GET /lesson-plans` 的教案，打开或新建。
 *
 * 列表读取失败时显示真实原因与重试入口；**不当空目录**（空列表必须来自服务端的空 items）。
 */
import { useCallback, useEffect, useState } from 'react';
import { LoaderCircle, Plus, RefreshCw } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import { ApiError } from '@/services/api-client';
import type { LessonSummary } from '@/contracts/lesson-plans';
import type { LessonPlansApi } from '@/services/lesson-plans-api';

type ListState =
  | { status: 'loading' }
  | { status: 'ready'; items: LessonSummary[]; total: number }
  | { status: 'error'; message: string };

export function LessonsDialog({
  api,
  currentPlanId,
  onOpen,
  onCreate,
  onClose,
}: {
  api: LessonPlansApi;
  currentPlanId: string | null;
  onOpen: (lessonPlanId: string) => Promise<unknown>;
  onCreate: () => Promise<unknown>;
  onClose: () => void;
}) {
  const [state, setState] = useState<ListState>({ status: 'loading' });
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

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

  return (
    <Modal title="云端教案" onClose={onClose}>
      <div className="lw-dialog" data-testid="lw-lessons-dialog">
        <div className="lw-dialog-actions">
          <button
            type="button"
            className="lw-button primary"
            data-testid="lw-dialog-create"
            disabled={busyId !== null}
            onClick={() => void run(null, onCreate)}
          >
            {busyId === 'new' ? <LoaderCircle size={15} className="lw-spin" /> : <Plus size={15} />}
            新建云端教案
          </button>
          <button type="button" className="lw-button" onClick={() => void load()}>
            <RefreshCw size={15} aria-hidden />
            刷新列表
          </button>
        </div>

        {state.status === 'loading' && <p className="lw-note" role="status">正在读取云端教案…</p>}
        {state.status === 'error' && (
          <p className="lw-error" data-testid="lw-dialog-error">
            教案列表读取失败：{state.message}
          </p>
        )}
        {state.status === 'ready' && state.items.length === 0 && (
          <p className="lw-note" data-testid="lw-dialog-empty">
            云端还没有教案；点「新建云端教案」会把当前编辑内容保存为第一份。
          </p>
        )}
        {state.status === 'ready' && state.items.length > 0 && (
          <ul className="lw-dialog-list" data-testid="lw-dialog-list">
            {state.items.map((item) => (
              <li key={item.lessonPlanId}>
                <div className="lw-dialog-item">
                  <strong>{item.title || '（未命名教案）'}</strong>
                  <small>
                    修订 {item.revision} · {item.updatedAt ? item.updatedAt.slice(0, 16).replace('T', ' ') : '时间未知'}
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
              </li>
            ))}
          </ul>
        )}
        {actionError && <p className="lw-error">操作失败：{actionError}</p>}
        <p className="lw-note">打开云端教案会以服务器版本替换本页内容；本机草稿在同步前仍保留在浏览器里。</p>
      </div>
    </Modal>
  );
}
