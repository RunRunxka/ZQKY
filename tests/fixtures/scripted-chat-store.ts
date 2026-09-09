/** 历史事件回归专用适配器，不被任何生产入口引用。脚本和测试档案只在此注入。 */
import {
  createChatStore,
  type ChatDeps,
  type ChatProfileSelection,
} from '@/features/chat/model/store';
import type { ChatService } from '@/features/chat/model/chat-service';

const profile: ChatProfileSelection = {
  id: 'scripted-test-profile',
  modelLabel: '测试模型 · 本地脚本',
  contextTokens: 4000,
  maxOutputTokens: 1000,
};
type ScriptedService = ChatService & {
  armFailure?(): void;
  armAskUser?(): void;
  armReplyFailure?(): void;
};
export function createScriptedChatStore(
  deps: ChatDeps & {
    mode?: 'real' | 'mock';
    services?: { real?: ChatService; mock?: ScriptedService };
  },
) {
  const testing = deps.mode === 'mock';
  const service = testing ? deps.services?.mock : deps.services?.real;
  const store = createChatStore({ repository: deps.repository, stream: deps.stream, service });
  if (testing) {
    if (!service) throw new Error('Inject an explicit scripted service');
    const { send, retry, retryLast } = store.getState();
    store.setState({
      send: (text, selection, extensions, accepted) =>
        send(text, selection ?? profile, extensions, accepted),
      retry: (id, selection) => retry(id, selection ?? profile),
      retryLast: (selection) => retryLast(selection ?? profile),
    });
  }
  return store;
}
