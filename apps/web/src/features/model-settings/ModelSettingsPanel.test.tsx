import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { ModelSettingsPanel } from './ModelSettingsPanel';
const mocks = vi.hoisted(() => ({
  loadModelCatalog: vi.fn(),
  setDefaultModel: vi.fn(),
  notifyModelCatalogChanged: vi.fn(),
}));
vi.mock('@/services/model-settings-api', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  ...mocks,
}));
const connection = {
  id: 'c',
  displayName: '测试供应商',
  protocol: 'openai-chat',
  baseUrl: 'https://example.com/v1',
  hasCredential: true,
  extraHeaderNames: [],
};
const profile = {
  id: 'p',
  connectionId: 'c',
  displayName: '测试模型',
  modelId: 'test-model',
  purpose: 'chat',
  supportedParams: [],
  capabilities: { chat: 'unknown' },
  connection,
};
describe('模型管理', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });
  it('后端不可用时显示重试', async () => {
    mocks.loadModelCatalog.mockRejectedValue(new Error('后端服务不可用。'));
    render(<ModelSettingsPanel />);
    expect(await screen.findByRole('alert')).toHaveTextContent('后端服务不可用');
    expect(screen.getByRole('button', { name: '重试' })).toBeInTheDocument();
  });
  it('按连接组织模型，普通能力未知不能冒充流式验证', async () => {
    mocks.loadModelCatalog.mockResolvedValue({
      revision: 3,
      defaultChatProfileId: null,
      connections: [connection],
      profiles: [profile],
    });
    render(<ModelSettingsPanel />);
    expect(await screen.findByText('测试模型')).toBeInTheDocument();
    expect(screen.getByText('凭证已配置')).toBeInTheDocument();
    expect(screen.getByText('流式 · 未知')).toBeInTheDocument();
    expect(screen.getByText('test-model')).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: '删除连接 测试供应商' }));
    expect(screen.getByRole('alert')).toHaveTextContent('仍被模型引用');
  });
  it('搜索不修改目录，设置默认值携带版本', async () => {
    mocks.loadModelCatalog.mockResolvedValue({
      revision: 3,
      defaultChatProfileId: null,
      connections: [connection],
      profiles: [profile],
    });
    mocks.setDefaultModel.mockResolvedValue({});
    render(<ModelSettingsPanel />);
    await screen.findByText('测试模型');
    fireEvent.click(screen.getByRole('button', { name: '设为默认' }));
    expect(mocks.setDefaultModel).toHaveBeenCalledWith('p', 3);
    await screen.findByText('默认模型已更新');
    fireEvent.change(screen.getByRole('textbox', { name: '搜索连接或模型' }), {
      target: { value: '无匹配' },
    });
    expect(screen.queryByText('测试模型')).not.toBeInTheDocument();
  });
});
