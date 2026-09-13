import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { ModelSettingsPanel } from './ModelSettingsPanel';
import type { ModelConnectionView } from '@/contracts/model-settings';

/**
 * 1805397 独立审查的前端行为回归（MR-02/07/08/12/13/16）。
 *
 * 只替换 API 层，针对真实组件断言期望行为；命名与断言对应审查报告中的
 * 8 个期望行为用例，修复后应全部通过。
 */
const mocks = vi.hoisted(() => ({
  createConnection: vi.fn(),
  updateConnection: vi.fn(),
  updateProfile: vi.fn(),
  createProfile: vi.fn(),
  loadModelCatalog: vi.fn(),
  loadProviderDirectory: vi.fn(),
  setDefaultModel: vi.fn(),
  discoverModels: vi.fn(),
  notifyModelCatalogChanged: vi.fn(),
  getAuthStatus: vi.fn(),
  startAuth: vi.fn(),
  cancelAuth: vi.fn(),
  logoutAuth: vi.fn(),
}));
vi.mock('@/services/model-settings-api', async (importOriginal) => ({
  ...(await importOriginal<object>()),
  ...mocks,
}));

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
  connection: {
    displayName: '测试供应商',
    providerId: 'deepseek',
    providerLabel: 'DeepSeek',
    protocol: 'openai-chat',
    apiFormat: 'auto',
    hasCredential: true,
  },
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

describe('模型管理审查回归', () => {
  beforeAll(() => {
    HTMLDialogElement.prototype.showModal = function showModal() {
      this.open = true;
    };
    HTMLDialogElement.prototype.close = function close() {
      this.open = false;
    };
  });
  afterEach(() => {
    cleanup();
    vi.resetAllMocks();
  });

  async function open(conn = connection) {
    mockCatalog({ revision: 3, defaultChatProfileId: null, connections: [conn], profiles: [profile] });
    render(<ModelSettingsPanel />);
    fireEvent.click(await screen.findByRole('button', { name: `打开 ${conn.displayName} 的详情` }));
  }

  it('保存后用服务端返回值刷新表单，再保存不会写回旧值（MR-07）', async () => {
    await open();
    const changed = { ...connection, baseUrl: 'https://new.example.com/v1' };
    mocks.updateConnection.mockResolvedValue(changed);
    mocks.loadModelCatalog.mockResolvedValue({
      revision: 4,
      defaultChatProfileId: null,
      connections: [changed],
      profiles: [profile],
    });
    fireEvent.change(screen.getByLabelText(/^Base URL/), { target: { value: changed.baseUrl } });
    fireEvent.click(screen.getByRole('button', { name: '保存修改' }));
    await screen.findByText('连接已保存');
    expect(screen.getByLabelText(/^Base URL/)).toHaveValue(changed.baseUrl);
    // 保存成功且用服务端值重建草稿后，不再处于 dirty 状态
    expect(screen.getByRole('button', { name: '保存修改' })).toBeDisabled();
  });

  it('X 关闭在有未保存更改时先确认，不直接丢弃（MR-12）', async () => {
    await open();
    fireEvent.change(screen.getByLabelText(/^Base URL/), { target: { value: 'https://new.example.com/v1' } });
    fireEvent.click(screen.getByRole('button', { name: '关闭对话框' }));
    expect(screen.getByRole('alertdialog', { name: '放弃未保存的更改' })).toBeInTheDocument();
  });

  it('导入失败保留勾选并在弹窗内显示错误（MR-13）', async () => {
    await open();
    mocks.discoverModels.mockResolvedValue({ models: [{ id: 'new-model' }], source: 'upstream' });
    mocks.createProfile.mockRejectedValue(new Error('MODEL_IMPORT_FAILED'));
    fireEvent.click(screen.getByRole('button', { name: /从服务获取/ }));
    fireEvent.click(await screen.findByRole('checkbox', { name: 'new-model' }));
    fireEvent.click(screen.getByRole('button', { name: '添加所选 1 个' }));
    await screen.findByRole('button', { name: '添加所选 1 个' });
    expect(screen.getByRole('checkbox', { name: 'new-model' })).toBeChecked();
    expect(screen.getByRole('alert')).toHaveTextContent('MODEL_IMPORT_FAILED');
  });

  it('本机免 Key 供应商可发起连接测试（MR-02）', async () => {
    await open({
      ...connection,
      providerId: 'ollama',
      providerLabel: 'Ollama',
      hasCredential: false,
      hasManagedCredential: false,
      callable: true,
      callableReason: null,
    });
    expect(screen.getByRole('button', { name: '连接测试 测试模型' })).toBeEnabled();
  });

  it('云服务缺凭证时测试被禁用并给出原因（MR-02）', async () => {
    await open({
      ...connection,
      hasCredential: false,
      hasManagedCredential: false,
      callable: false,
      callableReason: '该连接未保存凭证，请先填写 API Key。',
    });
    expect(screen.getByRole('button', { name: '连接测试 测试模型' })).toBeDisabled();
  });

  it('模型移到另一连接后详情加载目标连接草稿（MR-08）', async () => {
    const second = {
      ...connection,
      id: 'c2',
      displayName: '第二供应商',
      baseUrl: 'https://second.example.com/v1',
      resolvedBaseUrl: 'https://second.example.com/v1',
    };
    mockCatalog({ revision: 3, defaultChatProfileId: null, connections: [connection, second], profiles: [profile] });
    mocks.updateProfile.mockResolvedValue({ ...profile, connectionId: 'c2' });
    render(<ModelSettingsPanel />);
    fireEvent.click(await screen.findByRole('button', { name: '打开 测试供应商 的详情' }));
    fireEvent.click(screen.getByRole('button', { name: '编辑 测试模型' }));
    fireEvent.change(screen.getByLabelText('所属连接'), { target: { value: 'c2' } });
    fireEvent.click(screen.getByRole('button', { name: '保存修改' }));
    await screen.findByText('模型已保存');
    expect(screen.getByRole('dialog', { name: '连接 · 第二供应商' })).toBeInTheDocument();
    expect(screen.getByLabelText(/^Base URL/)).toHaveValue(second.baseUrl);
  });

  it.each([
    ['custom', '自定义（OpenAI 兼容）'],
    ['azure_openai', 'Azure OpenAI'],
    ['vllm', 'vLLM'],
  ])('无默认地址的 %s 先收集必填 Base URL 再创建（MR-16）', async (providerId, label) => {
    mockCatalog({ revision: 3, defaultChatProfileId: null, connections: [connection], profiles: [profile] });
    mocks.loadProviderDirectory.mockResolvedValue({
      providers: [{ ...directory.providers[0], providerId, label, defaultApiBase: '', baseUrlsByFormat: {} }],
      legacy: [],
    });
    // 后端对空 baseUrl 返回 422；正确行为是根本不会先提交空地址
    mocks.createConnection.mockResolvedValue({ ...connection, id: 'new', providerId });
    render(<ModelSettingsPanel />);
    await screen.findByRole('button', { name: '打开 测试供应商 的详情' });
    fireEvent.click(screen.getAllByRole('button', { name: '添加连接' })[0]);
    fireEvent.click(await screen.findByRole('button', { name: new RegExp(label.replace(/[（）]/g, '.')) }));

    // 先出现可编辑草稿，且未提交
    const baseInput = await screen.findByLabelText(/^Base URL/);
    expect(mocks.createConnection).not.toHaveBeenCalled();

    // 未填必填地址时不能提交
    expect(screen.getByRole('button', { name: '创建连接' })).toBeDisabled();
    fireEvent.change(baseInput, { target: { value: 'https://new.example.com/v1' } });
    fireEvent.click(screen.getByRole('button', { name: '创建连接' }));
    await waitFor(() =>
      expect(mocks.createConnection).toHaveBeenCalledWith(
        expect.objectContaining({ providerId, baseUrl: 'https://new.example.com/v1' }),
      ),
    );
  });

  it('创建失败保留表单与错误，可修正后重试（MR-16）', async () => {
    mockCatalog({ revision: 3, defaultChatProfileId: null, connections: [connection], profiles: [profile] });
    mocks.loadProviderDirectory.mockResolvedValue({
      providers: [{ ...directory.providers[0], providerId: 'custom', label: '自定义（OpenAI 兼容）', defaultApiBase: '' }],
      legacy: [],
    });
    mocks.createConnection.mockRejectedValueOnce(new Error('该供应商需要填写 Base URL。'));
    render(<ModelSettingsPanel />);
    await screen.findByRole('button', { name: '打开 测试供应商 的详情' });
    fireEvent.click(screen.getAllByRole('button', { name: '添加连接' })[0]);
    fireEvent.click(await screen.findByRole('button', { name: /自定义/ }));
    const baseInput = await screen.findByLabelText(/^Base URL/);
    fireEvent.change(baseInput, { target: { value: 'https://bad.example.com/v1' } });
    fireEvent.click(screen.getByRole('button', { name: '创建连接' }));
    // 失败后表单与输入仍在，错误可见
    expect(await screen.findByRole('alert')).toHaveTextContent('Base URL');
    expect(screen.getByLabelText(/^Base URL/)).toHaveValue('https://bad.example.com/v1');
    // 修正后重试成功
    mocks.createConnection.mockResolvedValue({ ...connection, id: 'new', providerId: 'custom' });
    fireEvent.change(screen.getByLabelText(/^Base URL/), { target: { value: 'https://good.example.com/v1' } });
    fireEvent.click(screen.getByRole('button', { name: '创建连接' }));
    await waitFor(() => expect(mocks.createConnection).toHaveBeenCalledTimes(2));
  });

  it('详情可维护附加请求头（MR-14）', async () => {
    await open();
    expect(screen.getByLabelText(/每行“名称: 值”/)).toBeInTheDocument();
  });

  it('受管认证可断开时点击后面板刷新目录（AuthPanel 接线）', async () => {
    mocks.getAuthStatus.mockResolvedValue({
      connection: 'connected',
      authMode: 'oauth',
      provider: 'github_copilot',
      available: true,
      userLabel: '已登录',
    });
    mocks.logoutAuth.mockResolvedValue({
      ok: true,
      status: { connection: 'disconnected', authMode: 'oauth', provider: 'github_copilot', available: false },
    });
    await open({ ...connection, providerId: 'github_copilot', providerLabel: 'GitHub Copilot' });
    // AuthPanel 读到已连接状态
    await screen.findByText('已连接');
    const callsBefore = mocks.loadModelCatalog.mock.calls.length;
    fireEvent.click(screen.getByRole('button', { name: /断开连接/ }));
    // 认证变化回调应触发父层刷新目录（不再是无操作）
    await waitFor(() =>
      expect(mocks.loadModelCatalog.mock.calls.length).toBeGreaterThan(callsBefore),
    );
  });
});
