'use client';
import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';
import { useStore } from 'zustand';
import { createMockChatService, type MockChatService } from './chat-service';
import { createChatStore, type ChatState } from './store';
import type { ChatServiceKind } from '@/contracts/chat';
import { createIdbChatRepository } from '@/services/chat-repository';

export interface ChatSession {
  mode: ChatServiceKind;
  setMode(mode: ChatServiceKind): void;
  /** 模拟服务实例：界面用它布防“模拟一次失败”演示 */
  mockService: MockChatService;
}

interface ChatSessionContextValue extends ChatSession {
  stores: Record<ChatServiceKind, ReturnType<typeof createChatStore>>;
}

const ChatSessionContext = createContext<ChatSessionContextValue | null>(null);

export function ChatProvider({ children }: { children: ReactNode }) {
  const [mockService] = useState(() => createMockChatService());
  // 真实与模拟各用独立 store 实例：R2——每个 store 只挂载和读写自己的仓储
  const [stores] = useState(() => ({
    real: createChatStore({ mode: 'real' }),
    mock: createChatStore({
      mode: 'mock',
      repository: createIdbChatRepository('zhiqikeyuan-chat-mock'),
      services: { mock: mockService },
    }),
  }));
  const [mode, setMode] = useState<ChatServiceKind>('real');
  const value = useMemo<ChatSessionContextValue>(
    () => ({ mode, setMode, mockService, stores }),
    [mode, mockService, stores],
  );
  useEffect(() => {
    // 两个模式的会话存储都初始化；切换模式时历史立即可见
    void stores.real.getState().init();
    void stores.mock.getState().init();
    const save = () => {
      void stores.real.getState().flush();
      void stores.mock.getState().flush();
    };
    const hide = () => {
      if (document.visibilityState === 'hidden') save();
    };
    const onPageHide = () => {
      stores.real.getState().dispose();
      stores.mock.getState().dispose();
    };
    window.addEventListener('pagehide', onPageHide);
    document.addEventListener('visibilitychange', hide);
    // R1：唯一的卸载清理责任——客户端路由切换/浏览器返回导致的卸载不触发 pagehide，
    // 卸载时必须取消生成并冲正保存。dispose 幂等，兼容 React StrictMode 的
    // setup-cleanup-setup（重挂载后 init 幂等复用，store 继续可用）。
    return () => {
      window.removeEventListener('pagehide', onPageHide);
      document.removeEventListener('visibilitychange', hide);
      stores.real.getState().dispose();
      stores.mock.getState().dispose();
    };
  }, [stores]);
  return <ChatSessionContext.Provider value={value}>{children}</ChatSessionContext.Provider>;
}

export function useChatSession(): ChatSessionContextValue {
  const ctx = useContext(ChatSessionContext);
  if (!ctx) throw new Error('ChatProvider is required');
  return ctx;
}

/** 订阅当前模式的 store；模式切换时自动切换订阅 */
export function useChatStore(): ChatState {
  const { mode, stores } = useChatSession();
  return useStore(mode === 'mock' ? stores.mock : stores.real);
}
