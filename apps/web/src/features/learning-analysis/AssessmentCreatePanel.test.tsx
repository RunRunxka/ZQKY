/**
 * 新建施测（闭环补齐 2026-10-13）：「导入的试卷在学情分析里看不到」的根因修复。
 *
 * 覆盖：只列已确认原卷（草稿不进候选）、参测名单取该班在册学生（姓名不进前端载荷）、
 * 逻辑确认冻结（结果未知后重试复用同一 `submissionId` 与原样载荷）、422 逐行 issues
 * 原样展示不回调成功、没有已确认原卷/没有在册学生/班级目录失败三个不可提交路径。
 */

import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { ApiError } from '@/services/api-client';
import type { AssessmentCreateResult, PaperOptionView } from '@/contracts/learning-analysis';
import { AssessmentCreatePanel } from './AssessmentCreatePanel';

const mocks = vi.hoisted(() => ({ api: {} as Record<string, unknown> }));

vi.mock('@/services/learning-analysis-api', () => ({
  learningAnalysisApi: mocks.api,
  COLUMN_PATTERN: /^[A-Za-z]{1,3}$/,
}));

const CONFIRMED_PAPER: PaperOptionView = {
  paperId: 'paper-1',
  title: '函数与导数单元测试',
  version: 1,
  currentRevisionId: 'rev-1',
  currentState: 'confirmed',
  scoredLeafCount: 16,
};

const DRAFT_PAPER: PaperOptionView = {
  ...CONFIRMED_PAPER,
  paperId: 'paper-2',
  title: '还没确认的草稿卷',
  currentRevisionId: 'rev-2',
  currentState: 'draft',
};

const STUDENTS = {
  items: [
    { id: 's1', name: '甲', studentNo: '001', status: 'active' as const },
    { id: 's2', name: '乙', studentNo: '002', status: 'active' as const },
    { id: 's3', name: '丙（已归档）', studentNo: '003', status: 'archived' as const },
  ],
  total: 3,
};

const CREATED: AssessmentCreateResult = {
  assessment: {
    assessmentId: 'asm-9',
    paperId: 'paper-1',
    paperRevisionId: 'rev-1',
    paperTitle: '函数与导数单元测试',
    title: '函数与导数单元测试',
    heldOn: '2026-10-13',
    revision: 0,
    participantCount: 2,
    classIds: ['class-a'],
  },
  participants: [
    {
      participantId: 'p1',
      studentId: 's1',
      nameSnapshot: '甲',
      classId: 'class-a',
      attemptNo: 1,
      attendance: 'present',
    },
    {
      participantId: 'p2',
      studentId: 's2',
      nameSnapshot: '乙',
      classId: 'class-a',
      attemptNo: 1,
      attendance: 'present',
    },
  ],
  replayed: false,
};

function baseApi() {
  return {
    listPapers: vi.fn(async () => ({
      items: [CONFIRMED_PAPER, DRAFT_PAPER],
      total: 2,
      offset: 0,
      limit: 200,
    })),
    listClassStudents: vi.fn(async () => STUDENTS),
    createAssessment: vi.fn(async () => CREATED),
  };
}

function installApi(overrides: Record<string, unknown> = {}) {
  Object.assign(mocks.api, baseApi(), overrides);
  return mocks.api as unknown as Record<string, ReturnType<typeof vi.fn>>;
}

function renderPanel(options: { classesFailed?: boolean } = {}) {
  const onCreated = vi.fn();
  const onClose = vi.fn();
  render(
    <AssessmentCreatePanel
      classes={options.classesFailed ? [] : [{ id: 'class-a', name: '高一(1)班' }]}
      classesFailed={Boolean(options.classesFailed)}
      onCreated={onCreated}
      onClose={onClose}
    />,
  );
  return { onCreated, onClose };
}

/** 选好班级并等名单读回（提交前的必经读取）。 */
async function pickClassAndWait() {
  await screen.findByRole('option', { name: /函数与导数单元测试/ });
  fireEvent.change(screen.getByLabelText('新建施测班级'), { target: { value: 'class-a' } });
  await screen.findByTestId('la-create-participant-count');
}

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal() {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function close() {
    this.open = false;
  };
});

beforeEach(() => {
  for (const key of Object.keys(mocks.api)) delete mocks.api[key];
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('新建施测：已确认原卷 + 班级 → 施测', () => {
  it('只列已确认原卷（草稿不进候选），提交把该班在册学生列为参测人次且不送姓名', async () => {
    const api = installApi();
    const { onCreated } = renderPanel();

    // 默认选中第一份已确认原卷；草稿卷不在候选里（后端会 422，界面不提前放行）
    const paperSelect = await screen.findByLabelText('新建施测原卷');
    await waitFor(() => expect(paperSelect).toHaveValue('paper-1'));
    expect(within(paperSelect).getByRole('option', { name: /函数与导数单元测试/ })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: /还没确认的草稿卷/ })).not.toBeInTheDocument();

    await pickClassAndWait();
    // 在册 2 名（已归档的丙不计），并说明姓名由服务端按 id 读取
    expect(screen.getByTestId('la-create-participant-count')).toHaveTextContent(
      '将把该班 2 名在册学生列为参测人次',
    );

    fireEvent.click(screen.getByTestId('la-create-submit'));
    await waitFor(() => expect(api.createAssessment).toHaveBeenCalledTimes(1));

    const body = api.createAssessment.mock.calls[0][0];
    expect(body.paperRevisionId).toBe('rev-1');
    expect(body.classIds).toEqual(['class-a']);
    expect(body.heldOn).toMatch(/^\d{4}-\d{2}-\d{2}$/);
    expect(body.assessmentType).toBe('exam');
    // 名称缺省取原卷标题；载荷只带 studentId/classId，不带姓名/学号
    expect(body.title).toBe('函数与导数单元测试');
    expect(body.participants).toEqual([
      { studentId: 's1', classId: 'class-a' },
      { studentId: 's2', classId: 'class-a' },
    ]);
    expect(typeof body.submissionId).toBe('string');
    expect(onCreated).toHaveBeenCalledWith(CREATED);
  });

  it('结果未知后重试：复用同一 submissionId 与原样载荷，不重复建', async () => {
    vi.spyOn(crypto, 'randomUUID').mockImplementation(() => 'frozen-id' as `${string}-${string}-${string}-${string}-${string}`);
    const createAssessment = vi
      .fn()
      .mockRejectedValueOnce(new ApiError('NETWORK_ERROR', '拿不到响应', 0, true))
      .mockResolvedValueOnce(CREATED);
    installApi({ createAssessment });
    const { onCreated } = renderPanel();
    await pickClassAndWait();

    fireEvent.click(screen.getByTestId('la-create-submit'));
    const unknown = await screen.findByTestId('la-create-unknown');
    expect(unknown).toHaveTextContent('结果未知');
    expect(onCreated).not.toHaveBeenCalled();
    // 未知后按钮改为「重试创建施测」且仍可点
    expect(screen.getByTestId('la-create-submit')).toHaveTextContent('重试创建施测');

    fireEvent.click(screen.getByTestId('la-create-submit'));
    await waitFor(() => expect(createAssessment).toHaveBeenCalledTimes(2));
    expect(createAssessment.mock.calls[0][0].submissionId).toBe('frozen-id');
    expect(createAssessment.mock.calls[1][0].submissionId).toBe('frozen-id');
    expect(createAssessment.mock.calls[1][0]).toEqual(createAssessment.mock.calls[0][0]);
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(CREATED));
  });

  it('422 归属未覆盖：错误与逐行 issues 原样展示，不回调成功', async () => {
    const createAssessment = vi.fn(async () => {
      throw new ApiError(
        'PARTICIPANT_CLASS_UNCONFIRMED',
        '参测名单的历史归属未覆盖 2026-09-01：有 1 个参测人次的历史归属未覆盖 2026-09-01；请重新确认本次班级后重试（不会自动修改归属历史）。',
        422,
        false,
        undefined,
        {
          issues: [
            {
              row: 0,
              field: 'classId',
              code: 'PARTICIPANT_CLASS_UNCONFIRMED',
              message: '第 1 个参测行（学生 甲，班级 class-a，第 1 人次）的班级归属未覆盖 2026-09-01',
            },
          ],
        },
      );
    });
    installApi({ createAssessment });
    const { onCreated } = renderPanel();
    await pickClassAndWait();

    fireEvent.change(screen.getByLabelText('新建施测日期'), { target: { value: '2026-09-01' } });
    fireEvent.click(screen.getByTestId('la-create-submit'));

    const error = await screen.findByTestId('la-create-error');
    expect(error).toHaveTextContent('PARTICIPANT_CLASS_UNCONFIRMED');
    expect(error).toHaveTextContent('请重新确认本次班级后重试');
    const issues = await screen.findByTestId('la-create-issues');
    expect(issues).toHaveTextContent('PARTICIPANT_CLASS_UNCONFIRMED：第 1 个参测行');
    expect(issues).toHaveTextContent('第 1 个参测行（学生 甲，班级 class-a，第 1 人次）');
    expect(onCreated).not.toHaveBeenCalled();
  });

  it('勾选「显式确认本次班级」必须填依据，否则不发请求', async () => {
    const api = installApi();
    renderPanel();
    await pickClassAndWait();

    fireEvent.click(screen.getByLabelText('显式确认本次班级'));
    fireEvent.click(screen.getByTestId('la-create-submit'));
    expect(await screen.findByTestId('la-create-error')).toHaveTextContent('必须填写依据');
    expect(api.createAssessment).not.toHaveBeenCalled();

    // 填了依据后随行送 classConfirmed + 依据（服务端口径）
    fireEvent.change(screen.getByLabelText('班级确认依据'), { target: { value: '补录历史考试，名单以教务处记录为准' } });
    fireEvent.click(screen.getByTestId('la-create-submit'));
    await waitFor(() => expect(api.createAssessment).toHaveBeenCalledTimes(1));
    expect(api.createAssessment.mock.calls[0][0].participants[0]).toEqual({
      studentId: 's1',
      classId: 'class-a',
      classConfirmed: true,
      classConfirmationNote: '补录历史考试，名单以教务处记录为准',
    });
  });

  it('没有已确认原卷：给出到试卷管理的指引，提交禁用', async () => {
    installApi({
      listPapers: vi.fn(async () => ({
        items: [DRAFT_PAPER],
        total: 1,
        offset: 0,
        limit: 200,
      })),
    });
    const { onCreated } = renderPanel();

    expect(await screen.findByTestId('la-create-no-paper')).toHaveTextContent('没有可用的已确认原卷');
    expect(screen.getByTestId('la-create-no-paper')).toHaveTextContent('确认原卷入库');
    expect(screen.getByTestId('la-create-submit')).toBeDisabled();
    expect(onCreated).not.toHaveBeenCalled();
  });

  it('原卷目录读取失败：不当「没有已确认试卷」，可重试', async () => {
    const listPapers = vi
      .fn()
      .mockRejectedValueOnce(new ApiError('SERVICE_UNAVAILABLE', '后端未运行', 503, true))
      .mockResolvedValueOnce({ items: [CONFIRMED_PAPER], total: 1, offset: 0, limit: 200 });
    installApi({ listPapers });
    renderPanel();

    const failed = await screen.findByTestId('la-create-papers-error');
    expect(failed).toHaveTextContent('SERVICE_UNAVAILABLE');
    expect(failed).toHaveTextContent('这不是「没有已确认试卷」');
    expect(screen.queryByTestId('la-create-no-paper')).not.toBeInTheDocument();

    fireEvent.click(within(failed).getByRole('button', { name: '重试读取原卷' }));
    await waitFor(() => expect(listPapers).toHaveBeenCalledTimes(2));
    await screen.findByRole('option', { name: /函数与导数单元测试/ });
  });

  it('班级没有在册学生：本地拦住，不发创建请求', async () => {
    const api = installApi({
      listClassStudents: vi.fn(async () => ({
        items: [{ id: 's3', name: '丙', studentNo: '003', status: 'archived' }],
        total: 1,
      })),
    });
    renderPanel();
    await pickClassAndWait();

    fireEvent.click(screen.getByTestId('la-create-submit'));
    expect(await screen.findByTestId('la-create-error')).toHaveTextContent('该班没有在册学生');
    expect(api.createAssessment).not.toHaveBeenCalled();
  });

  it('班级目录读取失败：说明原因并禁用提交（参测名单按班读取）', async () => {
    installApi();
    renderPanel({ classesFailed: true });

    expect(await screen.findByTestId('la-create-classes-error')).toHaveTextContent(
      '班级目录读取失败',
    );
    expect(screen.getByTestId('la-create-submit')).toBeDisabled();
  });
});
