import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useState } from 'react';
import '@testing-library/jest-dom/vitest';
import { LessonsDialog } from './LessonsDialog';
import { ApiError } from '@/services/api-client';
import type { LessonPlansApi } from '@/services/lesson-plans-api';

const SUBJECTS = [{ id: 'chinese', label: '语文' }];
const CLASSES = [{ id: 'class-1', name: '高一（1）班' }];

function fakeApi(): LessonPlansApi {
  return {
    listLessonPlans: vi.fn(async () => ({ items: [], total: 0, offset: 0, limit: 0 })),
    deleteLessonPlan: vi.fn(async () => ({ deleted: true, lessonPlanId: 'x', removedRevisions: 0 })),
  } as unknown as LessonPlansApi;
}

function renderDialog(options: {
  ownership: { subjectId: string; classId: string };
  onChange?: (next: { subjectId: string; classId: string }) => void;
  onCreate?: () => Promise<unknown>;
  api?: LessonPlansApi;
  classes?: { id: string; name: string }[];
}) {
  const onChange = options.onChange ?? vi.fn();
  const onCreate = options.onCreate ?? vi.fn(async () => undefined);

  function Harness() {
    const [ownership, setOwnership] = useState(options.ownership);
    return (
      <LessonsDialog
        api={options.api ?? fakeApi()}
        currentPlanId={null}
        ownership={ownership}
        onOwnershipChange={(next) => {
          onChange(next);
          setOwnership(next);
        }}
        onOpen={async () => undefined}
        onCreate={onCreate}
        onClose={() => undefined}
        ownershipServices={{
          loadSubjects: async () => SUBJECTS,
          loadClasses: async () => options.classes ?? CLASSES,
        }}
      />
    );
  }

  render(<Harness />);
  return { onChange, onCreate };
}

beforeAll(() => {
  if (typeof HTMLDialogElement !== 'undefined' && !HTMLDialogElement.prototype.showModal) {
    HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
      this.setAttribute('open', '');
    };
    HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
      this.removeAttribute('open');
    };
  }
});

afterEach(cleanup);

describe('本地教案对话框 · 归属对账', () => {
  it('记住的班级已不存在：清空并要求重选，不静默换班', async () => {
    const { onChange } = renderDialog({
      ownership: { subjectId: 'chinese', classId: 'stale-class' },
    });
    await waitFor(() =>
      expect(onChange).toHaveBeenCalledWith({ subjectId: 'chinese', classId: '' }),
    );
    expect(await screen.findByTestId('lw-dialog-ownership-notice')).toHaveTextContent(
      '原选择的班级已不存在',
    );
    expect(screen.getByTestId('lw-dialog-create')).toBeDisabled();
  });

  it('有效归属保持不变，新建键可用', async () => {
    const { onChange } = renderDialog({
      ownership: { subjectId: 'chinese', classId: 'class-1' },
    });
    await waitFor(() => expect(screen.getByTestId('lw-dialog-create')).not.toBeDisabled());
    expect(onChange).not.toHaveBeenCalled();
  });

  it('没有班级时清空旧班级并显示建班提示', async () => {
    const { onChange } = renderDialog({
      ownership: { subjectId: 'chinese', classId: 'stale-class' },
      classes: [],
    });
    await waitFor(() =>
      expect(onChange).toHaveBeenCalledWith({ subjectId: 'chinese', classId: '' }),
    );
    expect(await screen.findByTestId('lw-dialog-no-class')).toHaveTextContent('还没有班级');
    expect(screen.getByTestId('lw-dialog-create')).toBeDisabled();
  });

  it('新建返回 CLASS_NOT_FOUND：清空 classId 并显示可读原因', async () => {
    const { onChange } = renderDialog({
      ownership: { subjectId: 'chinese', classId: 'class-1' },
      onCreate: async () => {
        throw new ApiError('CLASS_NOT_FOUND', '班级不存在或已删除，请重新选择班级。', 404, false);
      },
    });
    await waitFor(() => expect(screen.getByTestId('lw-dialog-create')).not.toBeDisabled());
    fireEvent.click(screen.getByTestId('lw-dialog-create'));
    await waitFor(() =>
      expect(onChange).toHaveBeenCalledWith({ subjectId: 'chinese', classId: '' }),
    );
    expect(await screen.findByTestId('lw-dialog-action-error')).toHaveTextContent(
      '班级不存在或已删除',
    );
    expect(screen.getByTestId('lw-dialog-ownership-notice')).toHaveTextContent(
      '请重新选择班级',
    );
  });
});
