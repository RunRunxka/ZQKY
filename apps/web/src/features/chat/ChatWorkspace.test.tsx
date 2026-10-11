import type { ReactNode } from 'react';
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import '@testing-library/jest-dom/vitest';
import type { ModelCatalog, ModelProfileView } from '@/contracts/model-settings';
import type { ChatState } from './model/store';

/** 组件级夹具：不连后端、不落 IndexedDB（store 与目录都以 mock 注入）。 */
const mocks = vi.hoisted(() => ({
  catalog: null as ModelCatalog | null,
  store: null as ChatState | null,
}));

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
vi.mock('@/features/model-settings/ModelSelector', () => ({ ModelSelector: () => null }));
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
  mocks.catalog = { revision: 1, defaultChatProfileId: profile.id, connections: [], profiles: [profile] };
  mocks.store = makeStore({ draft });
  return render(<ChatWorkspace />);
}

function effortOptions(): string[] {
  const select = screen.getByRole('combobox', { name: '思考强度' });
  return within(select)
    .getAllByRole('option')
    .map((option) => option.textContent ?? '');
}

describe('对话编辑区：思考档位与上下文环数据源', () => {
  beforeEach(() => {
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
        reasoningSupport: {
          supported: true,
          levels: [
            { value: 'low', label: '低' },
            { value: 'medium', label: '中' },
            { value: 'high', label: '高' },
          ],
          default: 'medium',
          style: 'openai_effort',
          source: 'registry',
          note: null,
        },
      }),
    );
    expect(effortOptions()).toEqual(['默认（中）', '低', '中', '高']);
    expect((screen.getByRole('combobox', { name: '思考强度' }) as HTMLSelectElement).value).toBe('');
  });

  it('supported=false 时不渲染下拉（旧字段 reasoningEnabled=true 也不显示）', () => {
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

  it('缺失 reasoningSupport 时回退旧行为（含 none 之外的全量档位表）', () => {
    renderWorkspace(profileFixture({ reasoningEnabled: true, reasoningEffort: 'low' }));
    expect(effortOptions()).toEqual(['默认（低）', '最低', '低', '中', '高', '很高', '最高']);
  });

  it('上下文环取解析后的 contextWindow.tokens，并标注按模型族推断的来源', () => {
    const { container } = renderWorkspace(
      profileFixture({
        contextTokens: 8000,
        contextWindow: { tokens: 128000, source: 'model-table', note: '按模型族推断' },
      }),
      'x'.repeat(200),
    );
    // 200 字符 ≈ 100 tokens：按 128000 计为 1%（按旧的 8000 会显示 2%）
    expect(screen.getByLabelText('上下文估算 1%')).toBeInTheDocument();
    const popover = container.querySelector('.chat-chip-popover');
    expect(popover).toHaveTextContent('当前消息与输入约 100 tokens');
    expect(popover).toHaveTextContent(
      '模型上下文上限约 128,000（按模型族推断，可在设置→模型档案中手填覆盖）',
    );
  });

  it('缺失 contextWindow 时上下文环继续用旧 contextTokens 与现文案', () => {
    const { container } = renderWorkspace(profileFixture({ contextTokens: 8000 }), 'x'.repeat(200));
    expect(screen.getByLabelText('上下文估算 2%')).toBeInTheDocument();
    expect(container.querySelector('.chat-chip-popover')).toHaveTextContent('模型上下文上限 8,000');
  });
});
