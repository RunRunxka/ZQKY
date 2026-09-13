import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, fireEvent } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { ModelSettingsPanel } from './ModelSettingsPanel';

const mocks = vi.hoisted(() => ({
  loadModelCatalog: vi.fn(),
  loadProviderDirectory: vi.fn(),
  setDefaultModel: vi.fn(),
  discoverModels: vi.fn(),
  notifyModelCatalogChanged: vi.fn(),
}));
vi.mock('@/services/model-settings-api', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  ...mocks,
}));

const connection = {
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
  credentialScope: 'process',
  credentialEnvName: 'ZQKY_API_KEY_c',
  extraHeaderNames: [],
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
};
const profile = {
  id: 'p',
  connectionId: 'c',
  displayName: '测试模型',
  modelId: 'test-model',
  purpose: 'chat',
  contextTokens: null,
  maxOutputTokens: null,
  supportedParams: [],
  params: {},
  reasoningEnabled: null,
  reasoningEffort: null,
  reasoningStyle: 'thinking_type',
  capabilities: { chat: 'unknown' },
  connection: { displayName: '测试供应商', providerId: 'deepseek', providerLabel: 'DeepSeek', protocol: 'openai-chat', apiFormat: 'auto', hasCredential: true },
  createdAt: '2026-01-01T00:00:00Z',
  updatedAt: '2026-01-01T00:00:00Z',
};
const directory = {
  providers: [
    {
      providerId: 'deepseek',
      label: 'DeepSeek',
      aliases: [],
      mode: 'standard',
      authMode: 'api_key',
      apiFormats: ['auto', 'openai_chat', 'openai_responses'],
      defaultApiFormat: 'auto',
      defaultApiBase: 'https://api.deepseek.com',
      baseUrlsByFormat: {},
      supportsWireApiSelection: true,
      supportsModelDiscovery: true,
      requiresKey: true,
      isLegacy: false,
      legacyOf: [],
      thinkingStyle: 'thinking_type',
    },
  ],
  legacy: [],
};

function mockCatalog(catalog: object) {
  mocks.loadModelCatalog.mockResolvedValue(catalog);
  mocks.loadProviderDirectory.mockResolvedValue(directory);
}

describe('模型管理', () => {
  beforeAll(() => {
    // jsdom 未实现 <dialog> 的方法；补最小实现以驱动 Modal
    HTMLDialogElement.prototype.showModal = function showModal() {
      this.open = true;
    };
    HTMLDialogElement.prototype.close = function close() {
      this.open = false;
    };
  });

  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('后端不可用时显示重试', async () => {
    mocks.loadModelCatalog.mockRejectedValue(new Error('后端服务不可用。'));
    mocks.loadProviderDirectory.mockResolvedValue(directory);
    render(<ModelSettingsPanel />);
    expect(await screen.findByRole('alert')).toHaveTextContent('后端服务不可用');
    expect(screen.getByRole('button', { name: '重试' })).toBeInTheDocument();
  });

  it('供应商以卡片展示，打开详情才显示模型', async () => {
    mockCatalog({ revision: 3, defaultChatProfileId: null, connections: [connection], profiles: [profile] });
    render(<ModelSettingsPanel />);
    // 卡片层：不直接展示模型
    expect(await screen.findByRole('button', { name: '打开 测试供应商 的详情' })).toBeInTheDocument();
    expect(screen.getByText('凭证已配置')).toBeInTheDocument();
    expect(screen.queryByText('测试模型')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '打开 测试供应商 的详情' }));
    expect(await screen.findByText('测试模型')).toBeInTheDocument();
    expect(screen.getByText('test-model')).toBeInTheDocument();
    // 详情中提供真实的测试动作
    expect(screen.getByRole('button', { name: /连接测试/ })).toBeInTheDocument();
  });

  it('打开卡片不切换默认模型；用于问答才调用默认接口', async () => {
    mockCatalog({ revision: 3, defaultChatProfileId: null, connections: [connection], profiles: [profile] });
    mocks.setDefaultModel.mockResolvedValue({});
    render(<ModelSettingsPanel />);
    fireEvent.click(await screen.findByRole('button', { name: '打开 测试供应商 的详情' }));
    // 仅打开详情不应触发默认模型写入
    expect(mocks.setDefaultModel).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '用于问答' }));
    expect(mocks.setDefaultModel).toHaveBeenCalledWith('p', 3);
  });

  it('搜索按连接名过滤且不修改目录', async () => {
    mockCatalog({ revision: 3, defaultChatProfileId: null, connections: [connection], profiles: [profile] });
    render(<ModelSettingsPanel />);
    await screen.findByRole('button', { name: '打开 测试供应商 的详情' });
    fireEvent.change(screen.getByRole('textbox', { name: '搜索连接或模型' }), {
      target: { value: '无匹配名称' },
    });
    expect(screen.queryByRole('button', { name: '打开 测试供应商 的详情' })).not.toBeInTheDocument();
  });

  it('发现无列表接口时说明需手工添加，不冒充成功', async () => {
    mockCatalog({
      revision: 3,
      defaultChatProfileId: null,
      connections: [{ ...connection, providerId: 'openai_codex', providerLabel: 'OpenAI Codex' }],
      profiles: [],
    });
    mocks.discoverModels.mockResolvedValue({
      models: [],
      source: 'manual',
      note: '该供应商没有公开模型列表接口，请手工添加模型 ID。',
    });
    render(<ModelSettingsPanel />);
    fireEvent.click(await screen.findByRole('button', { name: '打开 测试供应商 的详情' }));
    fireEvent.click(screen.getByRole('button', { name: /从服务获取/ }));
    expect(await screen.findByText(/没有公开的模型列表接口/)).toBeInTheDocument();
  });
});
