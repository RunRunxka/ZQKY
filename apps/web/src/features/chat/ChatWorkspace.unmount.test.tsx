import { afterEach, describe, expect, it, vi } from 'vitest';
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { ChatWorkspace } from './ChatWorkspace';

// Canvas 动画由真实浏览器回归验收；此处只测会话卸载生命周期。
vi.mock('./vendor/thinking-orbs', () => ({ ThinkingOrb: () => null }));

/**
 * 审查 R1 回归：客户端路由卸载（不触发 pagehide、不经过侧栏 beforeNavigate）时，
 * ChatProvider 的清理必须取消两个 store 中仍在生成的请求。
 * 探针服务捕获请求的 AbortSignal，卸载后断言其已 aborted。
 */
const probe = vi.hoisted(() => ({
  signal: null as AbortSignal | null,
  release: null as null | (() => void),
  reset() {
    probe.signal = null;
    probe.release = null;
  },
}));

vi.mock('next/navigation', () => ({
  usePathname: () => '/chat',
  useRouter: () => ({ push: vi.fn() }),
}));
vi.mock('@/features/model-settings/useModelCatalog', () => ({
  useModelCatalog: () => ({ catalog: null, loading: false, error: null, refresh: vi.fn() }),
}));
vi.mock('@/services/chat-repository', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/chat-repository')>();
  return { ...actual, createIdbChatRepository: () => actual.createMemoryChatRepository() };
});
vi.mock('@/features/chat/model/chat-service', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/features/chat/model/chat-service')>();
  return {
    ...actual,
    createMockChatService: () => ({
      kind: 'mock' as const,
      armFailure: vi.fn(),
      run: (request: { signal: AbortSignal }) => {
        probe.signal = request.signal;
        return new Promise<void>((resolve) => {
          probe.release = resolve;
        });
      },
    }),
  };
});

afterEach(() => {
  cleanup();
  probe.reset();
});

function mockMatchMedia() {
  window.matchMedia = vi.fn().mockReturnValue({
    matches: false,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  });
}

async function sendInMockMode() {
  fireEvent.click(screen.getByRole('button', { name: '模拟' }));
  const input = screen.getByRole('textbox', { name: '输入问题' });
  await waitFor(() => expect(input).not.toBeDisabled());
  fireEvent.change(input, { target: { value: '测试卸载' } });
  fireEvent.click(screen.getByRole('button', { name: '发送' }));
  await waitFor(() => expect(probe.signal).not.toBeNull());
}

describe('聊天页面卸载清理（审查 R1）', () => {
  it('客户端卸载立即取消仍在生成的请求，不依赖 pagehide', async () => {
    mockMatchMedia();
    const ui = render(<ChatWorkspace />);
    await sendInMockMode();
    const signal = probe.signal!;
    ui.unmount();
    expect(signal.aborted).toBe(true);
    await act(async () => {
      probe.release?.();
    });
  });

  it('React StrictMode 下挂载、发送与卸载取消均正常', async () => {
    mockMatchMedia();
    const ui = render(
      <StrictMode>
        <ChatWorkspace />
      </StrictMode>,
    );
    await sendInMockMode();
    const signal = probe.signal!;
    ui.unmount();
    expect(signal.aborted).toBe(true);
    await act(async () => {
      probe.release?.();
    });
  });
});
