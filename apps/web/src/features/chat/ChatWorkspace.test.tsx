import type { ReactNode } from 'react';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import type { ModelCatalog, ModelProfileView } from '@/contracts/model-settings';
import type { ChatState } from './model/store';

/** 组件级夹具：不连后端、不落 IndexedDB（store 与目录都以 mock 注入）。 */
const mocks = vi.hoisted(() => ({
  catalog: null as ModelCatalog | null,
  store: null as ChatState | null,
}));
const apiMocks = vi.hoisted(() => ({
  refreshProfileMetadata: vi.fn(),
  notifyModelCatalogChanged: vi.fn(),
}));
vi.mock('@/services/model-settings-api', () => apiMocks);

vi.mock('next/navigation', () => ({
  usePathname: () => '/chat',
  useRouter: () => ({ push: vi.fn(), replace: vi.fn(), prefetch: vi.fn() }),
}));
vi.mock('./model/ChatContext', () => ({
  ChatProvider: ({ children }: { children?: ReactNode }) => children,
  useChatStore: () => mocks.store,
}));
vi.mock('@/features/model-settings/useModelCatalog', () => ({
  useModelCatalog: () => ({ catalog: mocks.catalog, error: null, loading: false, refresh: vi.fn() }),
}));
vi.mock('@/features/model-settings/ModelSelector', () => ({
  ModelSelector: ({
    catalog,
    value,
    onChange,
  }: {
    catalog: ModelCatalog | null;
    value: string | null;
    onChange: (id: string | null) => void;
  }) => (
    <select
      aria-label="测试模型切换"
      value={value ?? ''}
      onChange={(event) => onChange(event.target.value || null)}
    >
      {catalog?.profiles.map((profile) => (
        <option key={profile.id} value={profile.id}>
          {profile.displayName}
        </option>
      ))}
    </select>
  ),
}));
// 外壳（导航/侧栏）由 WorkspaceShell.test 覆盖；此处只聚焦编辑区控件。
vi.mock('@/components/layout/WorkspaceShell', () => ({
  WorkspaceShell: ({ children }: { children?: ReactNode }) => children,
}));

import { ChatWorkspace } from './ChatWorkspace';

function profileFixture(overrides: Partial<ModelProfileView> = {}): ModelProfileView {
  return {
    id: 'profile-1',
    connectionId: 'connection-1',
    displayName: '测试模型',
    modelId: 'test-model',
    purpose: 'chat',
    contextTokens: null,
    maxOutputTokens: null,
    supportedParams: [],
    reasoningEnabled: null,
    reasoningEffort: null,
    reasoningStyle: null,
    capabilities: {},
    connection: {
      displayName: '测试连接',
      providerId: 'deepseek',
      providerLabel: 'DeepSeek',
      protocol: 'openai-chat',
      apiFormat: 'auto',
      hasCredential: true,
    },
    createdAt: '2026-01-01T00:00:00Z',
    updatedAt: '2026-01-01T00:00:00Z',
    ...overrides,
  };
}

function makeStore(overrides: Partial<ChatState> = {}): ChatState {
  const noop = () => {};
  return {
    ready: true,
    loadError: null,
    storageWarning: null,
    budgetNotice: null,
    serviceNotice: null,
    mode: 'real',
    conversations: [],
    activeId: null,
    messages: [],
    sending: false,
    draft: '',
    modelProfileId: null,
    waitingInteractionId: null,
    submittingReply: false,
    askFocus: null,
    askNotice: null,
    chatProfile: null,
    init: vi.fn(async () => {}),
    newConversation: noop,
    selectConversation: vi.fn(async () => {}),
    renameConversation: vi.fn(async () => {}),
    removeConversation: vi.fn(async () => {}),
    deactivate: noop,
    send: vi.fn(async () => {}),
    stop: noop,
    retryLast: vi.fn(async () => {}),
    retry: vi.fn(async () => {}),
    setAskDraft: noop,
    submitReply: vi.fn(async () => true),
    continueAsk: vi.fn(async () => true),
    skipAskQuestion: vi.fn(async () => true),
    setAskFocus: noop,
    dismissAskNotice: noop,
    submitComposerReply: vi.fn(async () => true),
    setChatProfile: noop,
    setDraft: noop,
    setModel: noop,
    dismissBudgetNotice: noop,
    flush: vi.fn(async () => true),
    dispose: noop,
    exportActive: () => '',
    ...overrides,
  };
}

function renderWorkspace(profile: ModelProfileView, draft = '') {
  return renderWorkspaceWith([profile], { draft });
}

function renderWorkspaceWith(profiles: ModelProfileView[], overrides: Partial<ChatState> = {}) {
  const first = profiles[0]!;
  mocks.catalog = {
    revision: 1,
    defaultChatProfileId: first.id,
    connections: [],
    profiles,
  };
  mocks.store = makeStore({ modelProfileId: first.id, ...overrides });
  return render(<ChatWorkspace />);
}

function effortOptions(): string[] {
  const select = screen.getByRole('combobox', { name: '思考强度' });
  return within(select)
    .getAllByRole('option')
    .map((option) => option.textContent ?? '');
}

function effortSelect(): HTMLSelectElement {
  return screen.getByRole('combobox', { name: '思考强度' }) as HTMLSelectElement;
}

function switchModel(profileId: string): void {
  fireEvent.change(screen.getByLabelText('测试模型切换'), { target: { value: profileId } });
}

function baseSupport(
  overrides: Partial<NonNullable<ModelProfileView['reasoningSupport']>> = {},
): NonNullable<ModelProfileView['reasoningSupport']> {
  return {
    supported: true,
    selectable: true,
    levels: [
      { value: 'minimal' as const, label: '最低' },
      { value: 'low' as const, label: '低' },
      { value: 'medium' as const, label: '中' },
      { value: 'high' as const, label: '高' },
    ],
    default: null,
    style: 'openai_effort' as const,
    source: 'model-family' as const,
    note: null,
    ...overrides,
  };
}

describe('对话编辑区：思考档位与上下文环数据源', () => {
  beforeEach(() => {
    apiMocks.refreshProfileMetadata.mockReset();
    apiMocks.notifyModelCatalogChanged.mockReset();
    window.matchMedia = vi
      .fn()
      .mockReturnValue({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() });
    // jsdom 未实现元素滚动；消息列跟随滚动在此处为无关行为
    Element.prototype.scrollTo = vi.fn() as unknown as typeof Element.prototype.scrollTo;
  });
  afterEach(cleanup);

  it('reasoningSupport 决定档位：只渲染受支持三项与后端默认项', () => {
    renderWorkspace(
      profileFixture({
        reasoningEnabled: true,
        reasoningSupport: baseSupport({
          levels: [
            { value: 'low', label: '低' },
            { value: 'medium', label: '中' },
            { value: 'high', label: '高' },
          ],
          default: 'medium',
        }),
      }),
    );
    expect(effortOptions()).toEqual(['默认（中）', '低', '中', '高']);
    expect(effortSelect().value).toBe('');
  });

  it('旧后端 supported=false 且无 selectable 时隐藏（兼容旧契约）', () => {
    renderWorkspace(
      profileFixture({
        reasoningEnabled: true,
        reasoningSupport: {
          supported: false,
          levels: [],
          default: null,
          style: null,
          source: 'registry',
          note: '该模型不支持思考档位',
        },
      }),
    );
    expect(screen.queryByRole('combobox', { name: '思考强度' })).toBeNull();
  });

  it('档案显式关闭思考（selectable=false）时隐藏', () => {
    renderWorkspace(
      profileFixture({
        reasoningEnabled: false,
        reasoningSupport: baseSupport({ supported: false, selectable: false, levels: [] }),
      }),
    );
    expect(screen.queryByRole('combobox', { name: '思考强度' })).toBeNull();
  });

  it('未声明支持的模型仍渲染控件，并带后端警告 note', () => {
    const note = '未在注册表标注该模型支持思考；档位作为本轮覆盖发送，上游可能忽略或报错。';
    renderWorkspace(
      profileFixture({
        reasoningSupport: baseSupport({ supported: false, source: 'fallback', note }),
      }),
    );
    const select = effortSelect();
    expect(select).toBeInTheDocument();
    expect(select.closest('label')).toHaveAttribute('title', note);
    expect(effortOptions()).toEqual(['默认', '最低', '低', '中', '高']);
  });

  it('deepseek-flash → deepseek-v4-pro 切换后思考强度控件仍在，档位跟随新模型', () => {
    const flash = profileFixture({
      id: 'flash',
      displayName: 'deepseek-flash',
      modelId: 'deepseek-flash',
      reasoningEnabled: true,
      reasoningEffort: 'max',
      reasoningSupport: baseSupport({
        levels: [
          { value: 'minimal', label: '最低' },
          { value: 'low', label: '低' },
          { value: 'medium', label: '中' },
          { value: 'high', label: '高' },
          { value: 'max', label: '最高' },
        ],
        default: 'max',
        source: 'profile',
      }),
    });
    const pro = profileFixture({
      id: 'pro',
      displayName: 'deepseek-v4-pro',
      modelId: 'deepseek-v4-pro',
      reasoningEnabled: null,
      reasoningEffort: null,
      reasoningSupport: baseSupport({ source: 'model-family' }),
    });
    renderWorkspaceWith([flash, pro]);
    expect(effortOptions()).toEqual(['默认（最高）', '最低', '低', '中', '高', '最高']);

    switchModel('pro');

    expect(effortSelect()).toBeInTheDocument();
    expect(effortOptions()).toEqual(['默认', '最低', '低', '中', '高']);
  });

  it('切换模型后旧档位不在新集合内时回到“默认”，不会静默发送旧值', () => {
    const flash = profileFixture({
      id: 'flash',
      modelId: 'deepseek-flash',
      reasoningSupport: baseSupport(),
    });
    const pro = profileFixture({
      id: 'pro',
      modelId: 'deepseek-v4-pro',
      reasoningSupport: baseSupport({
        levels: [{ value: 'high', label: '高' }],
      }),
    });
    renderWorkspaceWith([flash, pro]);
    fireEvent.change(effortSelect(), { target: { value: 'low' } });
    expect(effortSelect().value).toBe('low');

    switchModel('pro');

    expect(effortOptions()).toEqual(['默认', '高']);
    expect(effortSelect().value).toBe('');
  });

  it('未验证模型的档位会随本轮发送提交', () => {
    renderWorkspace(
      profileFixture({
        reasoningSupport: baseSupport({ supported: false, source: 'fallback', note: '未验证' }),
      }),
      '你好',
    );
    fireEvent.change(effortSelect(), { target: { value: 'low' } });
    fireEvent.click(screen.getByRole('button', { name: '发送' }));

    const send = mocks.store!.send as unknown as ReturnType<typeof vi.fn>;
    expect(send).toHaveBeenCalledTimes(1);
    const extensions = send.mock.calls[0]?.[2] as {
      capability?: { config?: Record<string, unknown> };
    };
    expect(extensions.capability?.config?.reasoningEffort).toBe('low');
  });

  it('发送键是向上箭头（向下箭头只留给滚动到底部）', () => {
    renderWorkspace(profileFixture(), '你好');
    const send = screen.getByRole('button', { name: '发送' });
    expect(send.querySelector('.lucide-arrow-up')).toBeTruthy();
    expect(send.querySelector('.lucide-arrow-down')).toBeNull();
  });

  it('缺失 reasoningSupport 时回退旧行为（含 none 之外的全量档位表）', () => {
    renderWorkspace(profileFixture({ reasoningEnabled: true, reasoningEffort: 'low' }));
    expect(effortOptions()).toEqual(['默认（低）', '最低', '低', '中', '高', '很高', '最高']);
  });

  it('上下文环用最近一轮真实 input tokens + 草稿估算，并标注真实来源', () => {
    const profile = profileFixture({ contextTokens: 8000 });
    const messages: ChatState['messages'] = [
      { id: 'u1', role: 'user', content: '你好', status: 'done' },
      {
        id: 'a1',
        role: 'assistant',
        content: '回答',
        status: 'done',
        modelProfileId: profile.id,
        usage: { inputTokens: 1000, outputTokens: 50, cachedInputTokens: 200 },
      },
    ];
    const { container } = renderWorkspaceWith([profile], {
      messages,
      draft: 'x'.repeat(100),
    });
    // 1000 真实输入 + 100 个 ASCII 字符估算 30 → 1030 / 8000 = 12.875% → 13%
    expect(screen.getByLabelText('上下文占用 13%')).toBeInTheDocument();
    const popover = container.querySelector('.chat-chip-popover');
    expect(popover).toHaveTextContent('当前约 1,030 tokens');
    expect(popover).toHaveTextContent('基准是最近一轮供应商返回的输入 1,000 tokens');
    expect(popover).toHaveTextContent('其后新增约 0 tokens、输入框约 30 tokens 为本地估算');
    expect(popover).toHaveTextContent('基准轮输出累计 50 tokens');
    expect(popover).toHaveTextContent('其中缓存命中输入 200 tokens');
  });

  it('没有真实 usage 时回退本地估算并明确标注', () => {
    const { container } = renderWorkspace(
      profileFixture({ contextTokens: 8000 }),
      'x'.repeat(200),
    );
    // 200 个 ASCII 字符 ≈ 60 tokens → 60 / 8000 = 0.75% → 1%（旧的 /2 会显示 2%）
    expect(screen.getByLabelText('上下文占用 1%')).toBeInTheDocument();
    const popover = container.querySelector('.chat-chip-popover');
    expect(popover).toHaveTextContent('当前约 60 tokens');
    expect(popover).toHaveTextContent(
      '尚无可用的真实用量，按可见消息与输入框约 60 tokens 估算',
    );
  });

  it('档案 contextTokens 优先于后端派生估算（flash 1M 不被 128k 覆盖）', () => {
    const { container } = renderWorkspace(
      profileFixture({
        contextTokens: 1_000_000,
        contextWindow: { tokens: 128000, source: 'model-table', note: '按模型族暂估' },
      }),
      'x'.repeat(200),
    );
    const popover = container.querySelector('.chat-chip-popover');
    expect(popover).toHaveTextContent('模型上下文上限 1,000,000（来自模型档案）');
    expect(popover).not.toHaveTextContent('128,000');
    expect(screen.queryByRole('button', { name: '读取模型信息' })).toBeNull();
  });

  it('档案为空时取解析后的 contextWindow.tokens，并标注按模型族暂估的来源', () => {
    const { container } = renderWorkspace(
      profileFixture({
        contextTokens: null,
        contextWindow: { tokens: 128000, source: 'model-table', note: '按模型族暂估' },
      }),
      'x'.repeat(200),
    );
    // 60 tokens / 128000 → 1%
    expect(screen.getByLabelText('上下文占用 1%')).toBeInTheDocument();
    const popover = container.querySelector('.chat-chip-popover');
    expect(popover).toHaveTextContent('当前约 60 tokens');
    expect(popover).toHaveTextContent('模型上下文上限约 128,000（按模型族暂估');
  });

  it('精确模型来源显示“按模型 ID 已知值”，且不再提供读取按钮', () => {
    const { container } = renderWorkspace(
      profileFixture({
        contextTokens: null,
        contextWindow: { tokens: 1_000_000, source: 'model', note: '按模型 ID 精确匹配' },
      }),
    );
    expect(container.querySelector('.chat-chip-popover')).toHaveTextContent(
      '模型上下文上限 1,000,000（按模型 ID 已知值）',
    );
    expect(screen.queryByRole('button', { name: '读取模型信息' })).toBeNull();
  });

  it('上限来自估算时可读取模型信息，成功后刷新目录并显示回执', async () => {
    apiMocks.refreshProfileMetadata.mockResolvedValue({
      updated: true,
      changes: [
        { field: 'contextTokens', label: '上下文', oldValue: 128000, newValue: 1_000_000, source: 'models.dev' },
        { field: 'maxOutputTokens', label: '输出上限', oldValue: null, newValue: 384_000, source: 'models.dev' },
      ],
      metadata: {
        contextTokens: 1_000_000,
        maxOutputTokens: 384_000,
        supportedParams: [],
        capabilities: {},
        source: 'models.dev',
        sources: { contextTokens: 'models.dev', maxOutputTokens: 'models.dev' },
        matchedProvider: 'deepseek',
        matchedModelId: 'deepseek-v4-flash',
        notes: [],
      },
      message:
        '已更新：上下文 128,000 → 1,000,000（models.dev）；输出上限 — → 384,000（models.dev）。',
    });
    const profile = profileFixture({
      contextTokens: null,
      contextWindow: { tokens: 128000, source: 'model-table', note: '按模型族暂估' },
    });
    const { container } = renderWorkspace(profile);
    const button = screen.getByRole('button', { name: '读取模型信息' });
    fireEvent.click(button);

    await waitFor(() => {
      expect(apiMocks.refreshProfileMetadata).toHaveBeenCalledWith(profile.id);
      expect(apiMocks.notifyModelCatalogChanged).toHaveBeenCalledTimes(1);
    });
    expect(container.querySelector('.chat-chip-popover')).toHaveTextContent(
      '上下文 128,000 → 1,000,000',
    );
    expect(container.querySelector('.chat-chip-popover')).toHaveTextContent(
      '输出上限 — → 384,000',
    );
  });

  it('缺失 contextWindow 时上下文环继续用旧 contextTokens 与现文案', () => {
    const { container } = renderWorkspace(profileFixture({ contextTokens: 8000 }), 'x'.repeat(200));
    expect(screen.getByLabelText('上下文占用 1%')).toBeInTheDocument();
    expect(container.querySelector('.chat-chip-popover')).toHaveTextContent('模型上下文上限 8,000');
  });
});
