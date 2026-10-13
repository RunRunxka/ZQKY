/**
 * 生成学情报告（闭环补齐 2026-10-13）：从所选施测的已确认成绩修订创建报告。
 *
 * 覆盖：默认选中版本号最大的已确认修订（草稿不算）、人次取自该修订的 `participantSnapshot`
 * 并原样送服务端、ruleCode 口径、没有已确认成绩的空态、快照缺失时诚实拦住不发请求、
 * 修订列表读取失败不当空态。
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { ApiError } from '@/services/api-client';
import type { AnalysisRunReceipt, ScoreRevisionView } from '@/contracts/learning-analysis';
import { AnalysisRunCreatePanel } from './AnalysisRunCreatePanel';

const mocks = vi.hoisted(() => ({ api: {} as Record<string, unknown> }));

vi.mock('@/services/learning-analysis-api', () => ({
  learningAnalysisApi: mocks.api,
  COLUMN_PATTERN: /^[A-Za-z]{1,3}$/,
}));

const CONFIRMED_V1: ScoreRevisionView = {
  revisionId: 'rev-1',
  assessmentId: 'asm-1',
  paperRevisionId: 'paper-1',
  version: 1,
  state: 'confirmed',
  confirmedAt: '2026-10-13T09:00:00Z',
  createdAt: '2026-10-13T08:00:00Z',
  participantSnapshot: [
    { participantId: 'p1', studentId: 's1', studentNo: '001', name: '甲', classId: 'class-a', attemptNo: 1, attendance: 'present' },
    { participantId: 'p2', studentId: 's2', studentNo: '002', name: '乙', classId: 'class-a', attemptNo: 1, attendance: 'present' },
  ],
};

const CONFIRMED_V2: ScoreRevisionView = {
  ...CONFIRMED_V1,
  revisionId: 'rev-2',
  version: 2,
  confirmedAt: '2026-10-13T10:00:00Z',
  participantSnapshot: [
    { participantId: 'p1', studentId: 's1', studentNo: '001', name: '甲', classId: 'class-a', attemptNo: 1, attendance: 'present' },
    { participantId: 'p2', studentId: 's2', studentNo: '002', name: '乙', classId: 'class-a', attemptNo: 1, attendance: 'present' },
    { participantId: 'p3', studentId: 's3', studentNo: '003', name: '丙', classId: 'class-a', attemptNo: 1, attendance: 'present' },
  ],
};

const DRAFT_V3: ScoreRevisionView = {
  ...CONFIRMED_V1,
  revisionId: 'rev-3',
  version: 3,
  state: 'draft',
  confirmedAt: null,
  participantSnapshot: [],
};

const RECEIPT: AnalysisRunReceipt = {
  runId: 'run-9',
  inputHash: 'hash-9',
  scoreRevisionId: 'rev-2',
  paperRevisionId: 'paper-1',
  replayed: false,
  reused: false,
};

function baseApi() {
  return {
    listScoreRevisions: vi.fn(async () => ({
      items: [CONFIRMED_V1, CONFIRMED_V2, DRAFT_V3],
      total: 3,
    })),
    createAnalysisRun: vi.fn(async () => RECEIPT),
  };
}

function installApi(overrides: Record<string, unknown> = {}) {
  Object.assign(mocks.api, baseApi(), overrides);
  return mocks.api as unknown as Record<string, ReturnType<typeof vi.fn>>;
}

function renderPanel(options: { activeScoreRevisionId?: string | null } = {}) {
  const onCreated = vi.fn();
  const onClose = vi.fn();
  render(
    <AnalysisRunCreatePanel
      assessmentId="asm-1"
      activeScoreRevisionId={options.activeScoreRevisionId ?? null}
      onCreated={onCreated}
      onClose={onClose}
    />,
  );
  return { onCreated, onClose };
}

beforeEach(() => {
  for (const key of Object.keys(mocks.api)) delete mocks.api[key];
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('生成学情报告：已确认成绩修订 → 学情报告', () => {
  it('默认选中版本号最大的已确认修订（草稿更高版本不算），人次取该修订快照原样送服务端', async () => {
    const api = installApi();
    const { onCreated } = renderPanel();

    const select = await screen.findByLabelText('生成报告的成绩修订');
    await waitFor(() => expect(select).toHaveValue('rev-2'));
    expect(within(select).getByRole('option', { name: /v1 ·/ })).toBeInTheDocument();
    expect(within(select).getByRole('option', { name: /v2 ·/ })).toBeInTheDocument();
    expect(within(select).queryByRole('option', { name: /v3 ·/ })).not.toBeInTheDocument();
    expect(screen.getByTestId('la-create-run-participant-count')).toHaveTextContent(
      '将对该版本的 3 个人次生成',
    );

    fireEvent.click(screen.getByTestId('la-create-run-submit'));
    await waitFor(() => expect(api.createAnalysisRun).toHaveBeenCalledTimes(1));

    const [assessmentId, body] = api.createAnalysisRun.mock.calls[0];
    expect(assessmentId).toBe('asm-1');
    expect(body.scoreRevisionId).toBe('rev-2');
    expect(body.selectedParticipantIds).toEqual(['p1', 'p2', 'p3']);
    expect(body.ruleCode).toBe('any_loss_v1');
    expect(typeof body.submissionId).toBe('string');
    expect(onCreated).toHaveBeenCalledWith(RECEIPT);
  });

  it('施测当前生效成绩修订是已确认版本时优先选中它（而不是版本号最大）', async () => {
    installApi();
    renderPanel({ activeScoreRevisionId: 'rev-1' });
    const select = await screen.findByLabelText('生成报告的成绩修订');
    await waitFor(() => expect(select).toHaveValue('rev-1'));
  });

  it('没有已确认的小题分成绩：空态指引（去导入并确认），不渲染提交按钮', async () => {
    installApi({
      listScoreRevisions: vi.fn(async () => ({ items: [DRAFT_V3], total: 1 })),
    });
    const { onCreated } = renderPanel();

    const empty = await screen.findByTestId('la-create-run-no-revision');
    expect(empty).toHaveTextContent('该施测还没有已确认的小题分成绩');
    expect(empty).toHaveTextContent('导入小题分');
    expect(screen.queryByTestId('la-create-run-submit')).not.toBeInTheDocument();
    expect(onCreated).not.toHaveBeenCalled();
  });

  it('快照缺失：诚实拦住并说明原因，不发请求（不擅自挑人次）', async () => {
    const missing: ScoreRevisionView = {
      revisionId: 'rev-9',
      assessmentId: 'asm-1',
      version: 9,
      state: 'confirmed',
      confirmedAt: '2026-10-13T11:00:00Z',
      createdAt: '2026-10-13T11:00:00Z',
    };
    const api = installApi({
      listScoreRevisions: vi.fn(async () => ({ items: [missing], total: 1 })),
    });
    renderPanel();

    await screen.findByLabelText('生成报告的成绩修订');
    fireEvent.click(screen.getByTestId('la-create-run-submit'));
    expect(await screen.findByTestId('la-create-run-error')).toHaveTextContent(
      '服务端未返回该成绩版本的人次快照',
    );
    expect(api.createAnalysisRun).not.toHaveBeenCalled();
  });

  it('修订列表读取失败：显示原因与重试，不当「没有已确认成绩」', async () => {
    const listScoreRevisions = vi
      .fn()
      .mockRejectedValueOnce(new ApiError('SERVICE_UNAVAILABLE', '后端未运行', 503, true))
      .mockResolvedValueOnce({ items: [CONFIRMED_V2], total: 1 });
    installApi({ listScoreRevisions });
    renderPanel();

    const failed = await screen.findByTestId('la-create-run-revisions-error');
    expect(failed).toHaveTextContent('SERVICE_UNAVAILABLE');
    expect(failed).toHaveTextContent('这不是「没有已确认成绩」');
    expect(screen.queryByTestId('la-create-run-no-revision')).not.toBeInTheDocument();

    fireEvent.click(within(failed).getByRole('button', { name: '重试读取' }));
    await waitFor(() => expect(listScoreRevisions).toHaveBeenCalledTimes(2));
    await waitFor(() =>
      expect(screen.getByLabelText('生成报告的成绩修订')).toHaveValue('rev-2'),
    );
  });

  it('生成失败（服务端 422）：错误按服务端原文展示，不回调成功', async () => {
    const api = installApi({
      createAnalysisRun: vi.fn(async () => {
        throw new ApiError(
          'ANALYSIS_SELECTION_INVALID',
          '人次不属于固定成绩修订。',
          422,
          false,
          undefined,
          {
            issues: [
              {
                row: 0,
                field: 'selectedParticipantIds[0]',
                code: 'PARTICIPANT_NOT_IN_REVISION',
                message: '人次不属于固定成绩修订。',
              },
            ],
          },
        );
      }),
    });
    const { onCreated } = renderPanel();
    await screen.findByLabelText('生成报告的成绩修订');

    fireEvent.click(screen.getByTestId('la-create-run-submit'));
    const error = await screen.findByTestId('la-create-run-error');
    expect(error).toHaveTextContent('ANALYSIS_SELECTION_INVALID');
    expect(await screen.findByTestId('la-create-run-issues')).toHaveTextContent(
      'PARTICIPANT_NOT_IN_REVISION',
    );
    expect(onCreated).not.toHaveBeenCalled();
    expect(api.createAnalysisRun).toHaveBeenCalledTimes(1);
  });
});
