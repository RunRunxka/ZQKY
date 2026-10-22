import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import type { ModelConnectionView } from '@/contracts/model-settings';
import { ProfileForm } from './ProfileForm';

const api = vi.hoisted(() => ({
  previewProfileMetadata: vi.fn(),
}));
vi.mock('@/services/model-settings-api', () => api);

const connection: ModelConnectionView = {
  id: 'c',
  displayName: '测试供应商',
  providerId: 'deepseek',
  providerLabel: 'DeepSeek',
  protocol: 'openai-chat',
  apiFormat: 'auto',
  apiVersion: null,
  baseUrl: 'https://api.deepseek.com',
  resolvedBaseUrl: 'https://api.deepseek.com',
  hasCredential: true,
  hasManagedCredential: true,
  callable: true,
  callableReason: null,
  credentialScope: 'process',
  extraHeaderNames: [],
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
};

afterEach(() => {
  cleanup();
  api.previewProfileMetadata.mockReset();
});

describe('模型档案表单：自动获取模型信息', () => {
  it('点击后填充上下文/输出上限并显示来源与匹配模型', async () => {
    api.previewProfileMetadata.mockResolvedValue({
      connectionId: 'c',
      modelId: 'deepseek-flash',
      metadata: {
        contextTokens: 1_000_000,
        maxOutputTokens: 384_000,
        supportedParams: ['temperature'],
        capabilities: { toolCall: true, reasoning: true, structuredOutput: true, inputModalities: ['text'] },
        source: 'models.dev',
        sources: { contextTokens: 'models.dev', maxOutputTokens: 'models.dev' },
        matchedProvider: 'deepseek',
        matchedModelId: 'deepseek-v4-flash',
        notes: [],
      },
    });

    render(
      <ProfileForm
        profile={null}
        connections={[connection]}
        initialConnectionId="c"
        onCancel={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText('模型 ID'), {
      target: { value: 'deepseek-flash' },
    });
    fireEvent.click(screen.getByRole('button', { name: '自动获取模型信息' }));

    await waitFor(() =>
      expect(api.previewProfileMetadata).toHaveBeenCalledWith({
        connectionId: 'c',
        modelId: 'deepseek-flash',
      }),
    );
    expect((screen.getByLabelText('上下文长度') as HTMLInputElement).value).toBe('1000000');
    expect((screen.getByLabelText('输出上限') as HTMLInputElement).value).toBe('384000');
    expect(screen.getByRole('status')).toHaveTextContent('已填充上下文、输出上限（models.dev）');
    expect(screen.getByRole('status')).toHaveTextContent('匹配 deepseek-v4-flash');
    expect(screen.getByText(/能力：工具调用 · 推理 · 结构化输出/)).toBeInTheDocument();
  });

  it('上游无数据时保留手填值并给出原因', async () => {
    api.previewProfileMetadata.mockResolvedValue({
      connectionId: 'c',
      modelId: 'unknown-model',
      metadata: {
        contextTokens: null,
        maxOutputTokens: null,
        supportedParams: [],
        capabilities: {},
        source: 'unavailable',
        sources: {},
        matchedProvider: null,
        matchedModelId: null,
        notes: ['模型元数据目录获取失败（RuntimeError）。'],
      },
    });

    render(
      <ProfileForm
        profile={null}
        connections={[connection]}
        initialConnectionId="c"
        onCancel={vi.fn()}
        onSave={vi.fn()}
      />,
    );

    fireEvent.change(screen.getByLabelText('模型 ID'), {
      target: { value: 'unknown-model' },
    });
    fireEvent.change(screen.getByLabelText('上下文长度'), { target: { value: '8000' } });
    fireEvent.click(screen.getByRole('button', { name: '自动获取模型信息' }));

    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('未获取到'));
    expect((screen.getByLabelText('上下文长度') as HTMLInputElement).value).toBe('8000');
  });
});
