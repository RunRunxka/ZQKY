/**
 * AI 评价与导出（R6-FE）：候选文本不落库、可存为教师备注（同一提交标识幂等重试）、
 * 导出分析报告走冻结端点并下载后端给出的 fileName。
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { ApiError } from '@/services/api-client';
import type { LearningAnalysisApi } from '@/services/learning-analysis-api';
import { AiCommentaryPanel } from './AiCommentaryPanel';

const mocks = vi.hoisted(() => ({ api: {} as Record<string, unknown> }));

vi.mock('@/features/model-settings/useModelCatalog', () => ({
  useModelCatalog: () => ({
    catalog: {
      revision: 1,
      defaultChatProfileId: 'profile-1',
      connections: [],
      profiles: [{ id: 'profile-1', displayName: '本地模型' }],
    },
    error: null,
    loading: false,
    refresh: vi.fn(),
  }),
}));

function baseApi() {
  return {
    generateAnalysisCommentary: vi.fn(async () => ({
      commentary: '# 班级学情评价\n\n整体得分率偏低。',
      degraded: false,
      reason: null,
    })),
    createAnalysisNote: vi.fn(async () => ({
      noteId: 'note-1',
      runId: 'run-1',
      participantId: null,
      knowledgePointId: null,
      note: '文本',
      createdAt: '2026-10-05T09:00:00Z',
      replayed: false,
    })),
    createAnalysisReport: vi.fn(async () => ({
      artifact: { artifactId: 'art-1', fileName: '学情分析报告.xlsx', byteSize: 4096 },
    })),
    downloadExportArtifact: vi.fn(async () => ({
      blob: new Blob(['report-bytes']),
      fileName: '学情分析报告.xlsx',
    })),
  };
}

function installApi(overrides: Record<string, unknown> = {}) {
  const api = baseApi();
  Object.assign(mocks.api, api, overrides);
  return mocks.api as unknown as Record<string, ReturnType<typeof vi.fn>>;
}

function renderPanel() {
  return render(
    <AiCommentaryPanel runId="run-1" services={mocks.api as unknown as LearningAnalysisApi} />,
  );
}

beforeEach(() => {
  for (const key of Object.keys(mocks.api)) delete mocks.api[key];
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe('AI 评价与导出', () => {
  it('生成候选评价（用当前模型）并可存为教师备注', async () => {
    const api = installApi();
    renderPanel();

    fireEvent.click(screen.getByRole('button', { name: /生成 AI 评价/ }));
    await waitFor(() =>
      expect(api.generateAnalysisCommentary).toHaveBeenCalledWith('run-1', 'profile-1'),
    );
    expect(await screen.findByText('整体得分率偏低。')).toBeInTheDocument();
    expect(screen.getByText(/学生以代称进模型，不传姓名\/学号/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '存为教师备注' }));
    await waitFor(() => expect(api.createAnalysisNote).toHaveBeenCalledTimes(1));
    const [, body] = api.createAnalysisNote.mock.calls[0] as [string, { submissionId: string; note: string }];
    expect(body.note).toContain('整体得分率偏低');
    expect(body.submissionId).toBeTruthy();
    expect(await screen.findByRole('button', { name: '已存为教师备注' })).toBeDisabled();
  });

  it('存备注结果未知时保留候选文本，重试复用同一 submissionId（不重复写入）', async () => {
    const save = vi
      .fn()
      .mockRejectedValueOnce(new ApiError('RESPONSE_LOST', '响应丢失', 0, true))
      .mockResolvedValue({
        noteId: 'note-1',
        runId: 'run-1',
        participantId: null,
        knowledgePointId: null,
        note: '文本',
        createdAt: '2026-10-05T09:00:00Z',
        replayed: true,
      });
    const api = installApi({ createAnalysisNote: save });
    renderPanel();

    fireEvent.click(screen.getByRole('button', { name: /生成 AI 评价/ }));
    await screen.findByText('整体得分率偏低。');

    fireEvent.click(screen.getByRole('button', { name: '存为教师备注' }));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(1));
    expect(await screen.findByRole('alert')).toHaveTextContent('RESPONSE_LOST');
    // 候选文本仍在，可直接重试
    expect(screen.getByText('整体得分率偏低。')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '存为教师备注' }));
    await waitFor(() => expect(save).toHaveBeenCalledTimes(2));
    expect((save.mock.calls[1][1] as { submissionId: string }).submissionId).toBe(
      (save.mock.calls[0][1] as { submissionId: string }).submissionId,
    );
    expect(api.createAnalysisNote).toBeDefined();
  });

  it('降级（模型未返回）：显示原因提示、不出现评价正文、可重试', async () => {
    const generate = vi
      .fn()
      .mockResolvedValueOnce({
        commentary: '',
        degraded: true,
        reason: 'MODEL_EMPTY_REPLY',
      })
      .mockResolvedValueOnce({
        commentary: '重试后的评价正文。',
        degraded: false,
        reason: null,
      });
    const api = installApi({ generateAnalysisCommentary: generate });
    renderPanel();

    fireEvent.click(screen.getByRole('button', { name: /生成 AI 评价/ }));
    const notice = await screen.findByTestId('analysis-ai-degraded');
    expect(notice).toHaveTextContent('MODEL_EMPTY_REPLY');
    expect(screen.queryByText('重试后的评价正文。')).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: '存为教师备注' })).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /生成 AI 评价/ }));
    expect(await screen.findByText('重试后的评价正文。')).toBeInTheDocument();
    expect(screen.queryByTestId('analysis-ai-degraded')).not.toBeInTheDocument();
    expect(api.createAnalysisNote).toBeDefined();
  });

  it('导出分析报告：生成产物后下载后端给的文件名', async () => {
    const api = installApi();
    const createObjectURL = vi.fn(() => 'blob:report');
    const revokeObjectURL = vi.fn();
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL, revokeObjectURL }));
    const clickSpy = vi
      .spyOn(HTMLAnchorElement.prototype, 'click')
      .mockImplementation(() => undefined);
    renderPanel();

    fireEvent.click(screen.getByRole('button', { name: /导出分析报告/ }));
    await waitFor(() => expect(api.createAnalysisReport).toHaveBeenCalledWith('run-1'));
    await waitFor(() => expect(api.downloadExportArtifact).toHaveBeenCalledWith('art-1'));
    expect(await screen.findByTestId('analysis-export-notice')).toHaveTextContent(
      '已导出「学情分析报告.xlsx」（4096 字节）',
    );
    expect(clickSpy).toHaveBeenCalled();
    expect(createObjectURL).toHaveBeenCalled();
    expect(revokeObjectURL).toHaveBeenCalledWith('blob:report');
    // 产物已生成：再次下载不重复生成报告
    fireEvent.click(screen.getByRole('button', { name: '再次下载' }));
    await waitFor(() => expect(api.downloadExportArtifact).toHaveBeenCalledTimes(2));
    expect(api.createAnalysisReport).toHaveBeenCalledTimes(1);
    clickSpy.mockRestore();
  });

  it('导出失败原样报错且不下载半截文件，可重试', async () => {
    const create = vi
      .fn()
      .mockRejectedValueOnce(new ApiError('SERVICE_UNAVAILABLE', '后端未上线', 501, true))
      .mockResolvedValue({ artifact: { artifactId: 'art-1', fileName: '报告.xlsx', byteSize: 12 } });
    const download = vi.fn(async () => ({ blob: new Blob(['x']), fileName: '报告.xlsx' }));
    const api = installApi({ createAnalysisReport: create, downloadExportArtifact: download });
    renderPanel();

    fireEvent.click(screen.getByRole('button', { name: /导出分析报告/ }));
    const error = await screen.findByTestId('analysis-export-error');
    expect(error).toHaveTextContent('SERVICE_UNAVAILABLE');
    expect(error).toHaveTextContent('未下载任何文件');
    expect(download).not.toHaveBeenCalled();
    expect(api.createAnalysisReport).toHaveBeenCalledTimes(1);

    fireEvent.click(screen.getByRole('button', { name: /导出分析报告/ }));
    await waitFor(() => expect(create).toHaveBeenCalledTimes(2));
  });
});
