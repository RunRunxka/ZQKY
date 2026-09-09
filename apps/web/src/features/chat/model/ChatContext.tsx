'use client';
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react';
import { useStore } from 'zustand';
import { createChatStore, type ChatState } from './store';

interface ChatSessionContextValue {
  stores: { real: ReturnType<typeof createChatStore> };
}
const ChatSessionContext = createContext<ChatSessionContextValue | null>(null);

export function ChatProvider({ children }: { children: ReactNode }) {
  const [value] = useState(() => ({ stores: { real: createChatStore() } }));
  useEffect(() => {
    const store = value.stores.real;
    void store.getState().init();
    const hide = () => {
      if (document.visibilityState === 'hidden') void store.getState().flush();
    };
    const dispose = () => store.getState().dispose();
    window.addEventListener('pagehide', dispose);
    document.addEventListener('visibilitychange', hide);
    return () => {
      window.removeEventListener('pagehide', dispose);
      document.removeEventListener('visibilitychange', hide);
      dispose();
    };
  }, [value]);
  return <ChatSessionContext.Provider value={value}>{children}</ChatSessionContext.Provider>;
}

export function useChatSession(): ChatSessionContextValue {
  const ctx = useContext(ChatSessionContext);
  if (!ctx) throw new Error('ChatProvider is required');
  return ctx;
}

export function useChatStore(): ChatState {
  return useStore(useChatSession().stores.real);
}
