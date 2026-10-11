/**
 * 对话状态（推倒重做骨架版）：会话 CRUD、消息状态机、Agent/直连两条通道、追问卡。
 *
 * - 权威源为内存 docs（会话全量），UI 投影写入 zustand store（messages/conversations）；
 * - 持久化经 ChatRepository（IndexedDB）：修订号防跨标签覆盖；
 * - 事件必须匹配当前轮次与会话：迟到、串会话与重复事件一律丢弃；
 * - 无课程归属、无教材 RAG 通道（骨架只保留对话与 Agent）。
 */
import { createStore } from 'zustand/vanilla';
import {
  type AskUserAnswer,
  type AskUserDraft,
  type AskUserInteraction,
  type ChatMessage,
  type ChatServiceKind,
  type Conversation,
  type ConversationMeta,
  type ToolCallRecord,
  type TurnExtensionSnapshot,
} from '@/contracts/chat';
import { createIdbChatRepository, type ChatRepository, toMeta } from '@/services/chat-repository';
import { streamChat, type ChatStreamInput } from '@/services/chat-stream';
import { createRealChatService, type ChatService, type ChatServiceEvent } from './chat-service';
import { buildChatRequest, requestHistory } from './request-budget';
import { buildNewConversation } from './new-conversation';

export interface ChatProfileSelection {
  id: string;
  modelLabel: string;
  contextTokens?: number | null;
  maxOutputTokens?: number | null;
}
export interface ChatDeps {
  /** 当前会话仓储，默认只打开真实问答库。 */
  repository?: ChatRepository;
  /** 兼容旧测试/回退：注入真实服务的底层 SSE 客户端（走普通 /chat/stream） */
  stream?: (input: ChatStreamInput, handlers: Parameters<typeof streamChat>[1]) => Promise<void>;
  service?: ChatService;
}
/** 追问卡当前聚焦的题（主输入框补充回答与「继续」共用同一聚焦语义） */
export interface AskFocus {
  interactionId: string;
  questionId: string;
}
/** 追问卡的即时提示（随题绑定，切题即清） */
export interface AskNotice extends AskFocus {
  text: string;
}

export interface ChatState {
  ready: boolean;
  loadError: string | null;
  storageWarning: string | null;
  budgetNotice: string | null;
  serviceNotice: string | null;
  mode: ChatServiceKind;
  conversations: ConversationMeta[];
  activeId: string | null;
  messages: ChatMessage[];
  sending: boolean;
  draft: string;
  modelProfileId: string | null;
  waitingInteractionId: string | null;
  submittingReply: boolean;
  askFocus: AskFocus | null;
  askNotice: AskNotice | null;
  chatProfile: ChatProfileSelection | null;
  init(): Promise<void>;
  newConversation(options?: { title?: string }): void;
  selectConversation(id: string): Promise<void>;
  renameConversation(id: string, title: string): Promise<void>;
  removeConversation(id: string): Promise<void>;
  deactivate(): void;
  send(
    text: string,
    profile: ChatProfileSelection | null,
    extensions?: TurnExtensionSnapshot,
    onAccepted?: () => void,
  ): Promise<void>;
  stop(): void;
  retryLast(profile: ChatProfileSelection | null): Promise<void>;
  retry(id: string, profile: ChatProfileSelection | null): Promise<void>;
  setAskDraft(interactionId: string, questionId: string, draft: AskUserDraft): void;
  submitReply(answers: AskUserAnswer[]): Promise<boolean>;
  continueAsk(interactionId: string): Promise<boolean>;
  skipAskQuestion(interactionId: string): Promise<boolean>;
  setAskFocus(interactionId: string, questionId: string): void;
  dismissAskNotice(): void;
  submitComposerReply(text: string): Promise<boolean>;
  setChatProfile(profile: ChatProfileSelection | null): void;
  setDraft(text: string): void;
  setModel(id: string | null): void;
  dismissBudgetNotice(): void;
  flush(): Promise<boolean>;
  dispose(): void;
  exportActive(): string;
}

interface GenerationToken {
  controller: AbortController;
  conversationId: string;
  assistantId: string;
  turnId: string;
  terminal: boolean;
  endReason: 'done' | 'error' | 'cancelled' | null;
}

const uid = () => crypto.randomUUID();
const now = () => new Date().toISOString();

export function createChatStore(deps: ChatDeps = {}) {
  const repository = deps.repository ?? createIdbChatRepository();
  const service = deps.service ?? createRealChatService({ stream: deps.stream });

  /** 内存权威源：会话全量；UI 为投影 */
  const docs = new Map<string, Conversation>();
  const revisions = new Map<string, number>();
  let activeToken: GenerationToken | null = null;
  let disposed = false;
  /** 本地卡状态（wait-user 卡由事件驱动；本表存草稿/状态补充） */
  const localAsk = new Map<string, AskUserInteraction>();

  const store = createStore<ChatState>((set, get) => {
    function publish(): void {
      const active = get().activeId ? docs.get(get().activeId!) : undefined;
      set({
        conversations: [...docs.values()]
          .map(toMeta)
          .sort((a, b) => b.updatedAt.localeCompare(a.updatedAt)),
        messages: active ? structuredClone(active.messages) : [],
      });
    }

    function change(id: string, mutate: (conversation: Conversation) => Conversation | void): void {
      const current = docs.get(id);
      if (!current) return;
      const next = mutate(structuredClone(current)) ?? current;
      next.updatedAt = now();
      docs.set(id, next);
      publish();
      void persist(id);
    }

    async function persist(id: string): Promise<boolean> {
      const conversation = docs.get(id);
      if (!conversation) return true;
      const expected = revisions.get(id);
      try {
        const revision = await repository.save(structuredClone(conversation), expected);
        revisions.set(id, revision);
        if (get().storageWarning) set({ storageWarning: null });
        return true;
      } catch (error) {
        if (error instanceof Error && error.name === 'ChatStorageConflict') {
          set({ storageWarning: '此会话已在其他标签页更新：当前内容保留在本页，请备份后重新载入。' });
        } else {
          set({ storageWarning: '本地保存失败：内容保留在当前页面，可稍后重试。' });
        }
        return false;
      }
    }

    function activeConversation(): Conversation | undefined {
      const id = get().activeId;
      return id ? docs.get(id) : undefined;
    }

    function findAskCard(sessionId: string, interactionId: string): AskUserInteraction | null {
      return (
        localAsk.get(interactionId) ??
        docs
          .get(sessionId)
          ?.messages.flatMap((m) => m.asks ?? [])
          .find((a) => a.interactionId === interactionId) ??
        null
      );
    }

    const hasAnswer = (draft?: AskUserDraft): boolean =>
      !!draft && (draft.labels.length > 0 || !!draft.freeText.trim());

    function updateAsk(
      sessionId: string,
      interactionId: string,
      mutate: (card: AskUserInteraction) => AskUserInteraction,
    ): void {
      const existing = findAskCard(sessionId, interactionId);
      if (!existing) return;
      localAsk.set(interactionId, mutate(existing));
      change(sessionId, (conversation) => {
        for (const message of conversation.messages) {
          const index = message.asks?.findIndex((a) => a.interactionId === interactionId) ?? -1;
          if (index >= 0 && message.asks) {
            message.asks[index] = mutate(message.asks[index]!);
            return conversation;
          }
        }
        return conversation;
      });
    }

    /** 全套答案序列化：未作答按 skipped 提交（后端逐题校验） */
    function serializeAnswers(card: AskUserInteraction): AskUserAnswer[] {
      return card.questions.map((q) => {
        const draft = card.drafts[q.questionId];
        if (!hasAnswer(draft)) {
          return { questionId: q.questionId, labels: [], freeText: '', skipped: true };
        }
        return {
          questionId: q.questionId,
          labels: [...(draft!.labels ?? [])],
          freeText: (draft!.freeText ?? '').trim(),
          skipped: false,
        };
      });
    }

    function updateAssistant(
      token: GenerationToken,
      mutate: (message: ChatMessage) => ChatMessage,
    ): void {
      if (disposed) return;
      change(token.conversationId, (conversation) => {
        const index = conversation.messages.findIndex((m) => m.id === token.assistantId);
        if (index < 0) return;
        conversation.messages[index] = mutate(conversation.messages[index]!);
      });
    }

    function patchAsk(
      sessionId: string,
      interactionId: string,
      patch: Partial<AskUserInteraction>,
    ): void {
      if (!findAskCard(sessionId, interactionId)) return;
      updateAsk(sessionId, interactionId, (card) => ({ ...card, ...patch }));
    }

    function makeEmitter(token: GenerationToken): (event: ChatServiceEvent) => void {
      return function emit(event: ChatServiceEvent): void {
        if (token.terminal || disposed) return;
        if (event.sessionId !== token.conversationId) return;
        if (event.turnId !== token.turnId) return;
        switch (event.type) {
          case 'turn-start':
            return;
          case 'text':
            updateAssistant(token, (m) =>
              event.replace
                ? { ...m, content: event.delta }
                : { ...m, content: m.content + event.delta },
            );
            return;
          case 'reasoning':
            updateAssistant(token, (m) => ({ ...m, reasoning: (m.reasoning ?? '') + event.delta }));
            return;
          case 'process':
            updateAssistant(token, (m) => ({ ...m, processNote: event.delta }));
            return;
          case 'stage':
            updateAssistant(token, (m) => {
              const stages = [...(m.stages ?? [])];
              const stageId = event.stageId ?? event.label;
              const index = stages.findIndex((s) => s.stageId === stageId);
              const status = event.phase === 'start' ? ('running' as const) : ('done' as const);
              if (index >= 0) stages[index] = { ...stages[index]!, status };
              else stages.push({ stageId, label: event.label, status, startedAt: now() });
              return { ...m, stages, stageLabel: event.label };
            });
            return;
          case 'tool':
            updateAssistant(token, (m) => {
              const calls = [...(m.toolCalls ?? [])];
              const index = calls.findIndex((c) => c.callId === event.call.callId);
              const record: ToolCallRecord = {
                callId: event.call.callId,
                kind: event.call.kind,
                name: event.call.name,
                status: event.call.status,
                ...(event.call.note ? { note: event.call.note } : {}),
                ...(event.call.detail ? { detail: event.call.detail } : {}),
                startedAt: now(),
                ...(event.call.status !== 'running' ? { endedAt: now() } : {}),
              };
              if (index >= 0) calls[index] = record;
              else calls.push(record);
              return { ...m, toolCalls: calls };
            });
            return;
          case 'artifact':
            updateAssistant(token, (m) => {
              const artifacts = [...(m.artifacts ?? [])];
              const artifact = { ...event.artifact, createdAt: now() };
              const index = artifacts.findIndex((a) => a.id === artifact.id);
              if (index >= 0) artifacts[index] = artifact;
              else artifacts.push(artifact);
              return { ...m, artifacts };
            });
            return;
          case 'usage':
            updateAssistant(token, (m) => ({ ...m, usage: event.usage }));
            return;
          case 'wait-user': {
            updateAssistant(token, (m) => {
              const asks = [...(m.asks ?? [])];
              const index = asks.findIndex(
                (a) => a.interactionId === event.interaction.interactionId,
              );
              const previous = index >= 0 ? asks[index]! : null;
              const merged: AskUserInteraction = {
                interactionId: event.interaction.interactionId,
                questions: event.interaction.questions,
                status: event.interaction.status,
                drafts: previous?.drafts ?? {},
                ...(event.interaction.intro ? { intro: event.interaction.intro } : {}),
                ...(previous?.answers ? { answers: previous.answers } : {}),
              };
              localAsk.set(merged.interactionId, merged);
              if (index >= 0) asks[index] = merged;
              else asks.push(merged);
              return { ...m, asks };
            });
            const card = findAskCard(token.conversationId, event.interaction.interactionId);
            if (card) {
              set({
                waitingInteractionId: card.interactionId,
                askFocus: {
                  interactionId: card.interactionId,
                  questionId: card.questions[0]?.questionId ?? '',
                },
              });
            }
            return;
          }
          case 'reply-accepted': {
            patchAsk(token.conversationId, event.interactionId, {
              status: 'answered',
              answers: event.answers,
            });
            if (get().waitingInteractionId === event.interactionId) {
              set({ waitingInteractionId: null, submittingReply: false });
            }
            return;
          }
          case 'checkpoint':
            void persist(token.conversationId);
            return;
          case 'end': {
            token.terminal = true;
            token.endReason = 'done';
            updateAssistant(token, (m) => ({
              ...m,
              status: 'done',
              finishReason: event.finishReason,
              finishedAt: now(),
            }));
            set({ sending: false });
            void get().flush();
            return;
          }
          case 'error': {
            token.terminal = true;
            token.endReason = 'error';
            updateAssistant(token, (m) => ({
              ...m,
              status: 'error',
              error: { code: event.error.code, message: event.error.message },
              finishedAt: now(),
            }));
            set({ sending: false });
            return;
          }
        }
      };
    }

    return {
      ready: false,
      loadError: null,
      storageWarning: null,
      budgetNotice: null,
      serviceNotice: null,
      mode: 'real' as ChatServiceKind,
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

      async init(): Promise<void> {
        if (get().ready) return;
        try {
          const metas = await repository.list();
          let newest: Conversation | null = null;
          for (const meta of metas) {
            const conversation = await repository.load(meta.id);
            if (!conversation) continue;
            docs.set(conversation.id, conversation);
            if (!newest || conversation.updatedAt > newest.updatedAt) newest = conversation;
          }
          if (newest) {
            // 中断遗留的流式消息恢复为 interrupted（不重放）
            for (const message of newest.messages) {
              if (message.status === 'streaming') message.status = 'stopped';
            }
            set({ activeId: newest.id, modelProfileId: newest.modelProfileId ?? null });
            void persist(newest.id);
          } else {
            const id = uid();
            docs.set(id, buildNewConversation(id, '', now));
            set({ activeId: id });
          }
          set({ ready: true, loadError: null });
          publish();
        } catch (error) {
          set({ ready: true, loadError: (error as Error).message || '本地会话读取失败。' });
        }
      },

      newConversation(options): void {
        const id = uid();
        docs.set(id, buildNewConversation(id, options?.title ?? '', now));
        localAsk.clear();
        set({
          activeId: id,
          budgetNotice: null,
          serviceNotice: null,
          waitingInteractionId: null,
          askFocus: null,
          askNotice: null,
        });
        publish();
        void persist(id);
      },

      async selectConversation(id): Promise<void> {
        if (!docs.has(id) || get().activeId === id) return;
        get().stop();
        localAsk.clear();
        const conversation = docs.get(id)!;
        set({
          activeId: id,
          modelProfileId: conversation.modelProfileId ?? null,
          waitingInteractionId: null,
          askFocus: null,
          askNotice: null,
          budgetNotice: null,
          serviceNotice: null,
        });
        publish();
      },

      async renameConversation(id, title): Promise<void> {
        const next = title.trim();
        if (!next) return;
        change(id, (conversation) => {
          conversation.title = next.slice(0, 80);
        });
        await get().flush();
      },

      async removeConversation(id): Promise<void> {
        if (!docs.has(id)) return;
        if (get().activeId === id) get().stop();
        docs.delete(id);
        revisions.delete(id);
        try {
          await repository.remove(id);
        } catch {
          set({ storageWarning: '本地删除失败：会话可能仍在其他标签页可见。' });
        }
        if (get().activeId === id) {
          const remainder = [...docs.values()].sort((a, b) =>
            b.updatedAt.localeCompare(a.updatedAt),
          )[0];
          if (remainder) set({ activeId: remainder.id });
          else {
            const freshId = uid();
            docs.set(freshId, buildNewConversation(freshId, '', now));
            set({ activeId: freshId });
          }
        }
        publish();
      },

      deactivate(): void {
        get().stop();
        set({
          activeId: null,
          messages: [],
          waitingInteractionId: null,
          askFocus: null,
          askNotice: null,
        });
      },

      async send(text, profile, extensions, onAccepted): Promise<void> {
        const sessionId = get().activeId;
        if (!sessionId || !docs.has(sessionId)) return;
        if (!profile) {
          set({ serviceNotice: '尚未选择可用的模型：请先在设置中配置模型连接与模型。' });
          return;
        }
        if (!text.trim()) return;
        const token: GenerationToken = {
          controller: new AbortController(),
          conversationId: sessionId,
          assistantId: uid(),
          turnId: uid(),
          terminal: false,
          endReason: null,
        };
        activeToken = token;
        const conversation = docs.get(sessionId)!;
        const prepared = buildChatRequest({
          history: requestHistory(conversation.messages),
          question: text.trim(),
          contextTokens: profile.contextTokens ?? null,
          maxOutputTokens: profile.maxOutputTokens ?? null,
        });
        if (prepared.notes.length > 0) set({ budgetNotice: prepared.notes.join(' ') });
        change(sessionId, (doc) => {
          doc.modelProfileId = profile.id;
          doc.messages.push({
            id: uid(),
            role: 'user',
            content: text.trim(),
            status: 'done',
            startedAt: now(),
            finishedAt: now(),
          });
          doc.messages.push({
            id: token.assistantId,
            role: 'assistant',
            content: '',
            status: 'streaming',
            startedAt: now(),
            modelLabel: profile.modelLabel,
            modelProfileId: profile.id,
            requestBudget: prepared.record,
            ...(extensions ? { extensions: structuredClone(extensions) } : {}),
          });
          if (!doc.title.trim()) doc.title = text.trim().slice(0, 30);
        });
        set({ sending: true, serviceNotice: null, draft: '', modelProfileId: profile.id });
        onAccepted?.();
        try {
          await service.run(
            {
              sessionId,
              turnId: token.turnId,
              messages: prepared.messages
                .filter((m) => m.role !== 'system')
                .map((m) => ({
                  role: m.role === 'assistant' ? ('assistant' as const) : ('user' as const),
                  content: m.content,
                })),
              modelProfileId: profile.id,
              maxOutputTokens: profile.maxOutputTokens ?? undefined,
              ...(extensions ? { extensions: structuredClone(extensions) } : {}),
              signal: token.controller.signal,
            },
            makeEmitter(token),
          );
          if (!token.terminal) {
            token.terminal = true;
            token.endReason = 'done';
            updateAssistant(token, (m) => ({ ...m, status: 'done', finishedAt: now() }));
          }
        } catch (error) {
          if (!token.terminal) {
            const aborted =
              token.controller.signal.aborted ||
              (error instanceof DOMException && error.name === 'AbortError') ||
              (error instanceof Error && error.name === 'AbortError');
            token.terminal = true;
            token.endReason = aborted ? 'cancelled' : 'error';
            updateAssistant(token, (m) => ({
              ...m,
              status: aborted ? 'stopped' : 'error',
              ...(aborted
                ? {}
                : {
                    error: {
                      code: 'REQUEST_FAILED',
                      message: (error as Error).message || '请求失败。',
                    },
                  }),
              finishedAt: now(),
            }));
          }
        } finally {
          set({ sending: false });
          void get().flush();
        }
      },

      stop(): void {
        if (activeToken && !activeToken.terminal) {
          const token = activeToken;
          token.terminal = true;
          token.endReason = 'cancelled';
          token.controller.abort();
          void service.cancel?.({ sessionId: token.conversationId, turnId: token.turnId });
        }
        activeToken = null;
        set({ sending: false, submittingReply: false });
      },

      async retryLast(profile): Promise<void> {
        const conversation = activeConversation();
        if (!conversation) return;
        const lastUser = [...conversation.messages].reverse().find((m) => m.role === 'user');
        if (!lastUser) return;
        await get().retry(lastUser.id, profile);
      },

      async retry(id, profile): Promise<void> {
        const conversation = activeConversation();
        if (!conversation) return;
        const index = conversation.messages.findIndex((m) => m.id === id && m.role === 'user');
        if (index < 0) return;
        const text = conversation.messages[index]!.content;
        const sessionId = conversation.id;
        change(sessionId, (doc) => {
          doc.messages = doc.messages.slice(0, index);
        });
        await get().send(text, profile);
      },

      setAskDraft(interactionId, questionId, draft): void {
        const sessionId = get().activeId;
        if (!sessionId) return;
        updateAsk(sessionId, interactionId, (card) => ({
          ...card,
          drafts: { ...card.drafts, [questionId]: draft },
        }));
        set({ askNotice: null });
      },

      async submitReply(answers): Promise<boolean> {
        const sessionId = get().activeId;
        const interactionId = get().waitingInteractionId;
        if (!sessionId || !interactionId) return false;
        set({ submittingReply: true });
        try {
          const ack = await service.submitReply?.({
            sessionId,
            turnId: activeToken?.turnId ?? '',
            interactionId,
            submissionId: uid(),
            answers,
            signal: new AbortController().signal,
          });
          if (!ack || !ack.accepted) {
            set({ serviceNotice: ack?.message ?? '追问提交失败。', submittingReply: false });
            return false;
          }
          patchAsk(sessionId, interactionId, { status: 'answered', answers });
          set({ waitingInteractionId: null, submittingReply: false, askFocus: null });
          return true;
        } catch (error) {
          set({
            serviceNotice: (error as Error).message || '追问提交失败。',
            submittingReply: false,
          });
          return false;
        }
      },

      async continueAsk(interactionId): Promise<boolean> {
        const sessionId = get().activeId;
        if (!sessionId) return false;
        const card = findAskCard(sessionId, interactionId);
        if (!card) return false;
        const pending = card.questions.filter((q) => !hasAnswer(card.drafts[q.questionId]));
        const focusState = get().askFocus;
        const focusId = focusState?.interactionId === interactionId ? focusState.questionId : null;
        if (pending.length > 0 && pending[0]!.questionId !== focusId) {
          const first = pending[0]!;
          set({
            askFocus: { interactionId, questionId: first.questionId },
            askNotice: { interactionId, questionId: first.questionId, text: '还有问题尚未确认' },
          });
          return false;
        }
        return get().submitReply(serializeAnswers(card));
      },

      async skipAskQuestion(interactionId): Promise<boolean> {
        const sessionId = get().activeId;
        if (!sessionId) return false;
        const card = findAskCard(sessionId, interactionId);
        if (!card) return false;
        const focusState = get().askFocus;
        const current =
          focusState?.interactionId === interactionId
            ? focusState.questionId
            : card.questions[0]?.questionId;
        const index = card.questions.findIndex((q) => q.questionId === current);
        const next = card.questions[index + 1];
        if (next) {
          set({ askFocus: { interactionId, questionId: next.questionId }, askNotice: null });
          return false;
        }
        return get().submitReply(serializeAnswers(card));
      },

      setAskFocus(interactionId, questionId): void {
        set({ askFocus: { interactionId, questionId }, askNotice: null });
      },

      dismissAskNotice(): void {
        set({ askNotice: null });
      },

      async submitComposerReply(text): Promise<boolean> {
        const sessionId = get().activeId;
        const interactionId = get().waitingInteractionId;
        if (!sessionId || !interactionId) return false;
        const card = findAskCard(sessionId, interactionId);
        if (!card) return false;
        const focusState = get().askFocus;
        const focus =
          focusState?.interactionId === interactionId
            ? focusState.questionId
            : card.questions[0]?.questionId ?? '';
        const existing = card.drafts[focus] ?? { labels: [], freeText: '' };
        updateAsk(sessionId, interactionId, (c) => ({
          ...c,
          drafts: { ...c.drafts, [focus]: { labels: existing.labels, freeText: text.trim() } },
        }));
        set({ draft: '' });
        return get().submitReply(serializeAnswers(findAskCard(sessionId, interactionId)!));
      },

      setChatProfile(profile): void {
        set({ chatProfile: profile });
      },

      setDraft(text): void {
        set({ draft: text });
      },

      setModel(id): void {
        set({ modelProfileId: id });
        const sessionId = get().activeId;
        if (sessionId) {
          change(sessionId, (conversation) => {
            conversation.modelProfileId = id;
          });
        }
      },

      dismissBudgetNotice(): void {
        set({ budgetNotice: null });
      },

      async flush(): Promise<boolean> {
        const sessionId = get().activeId;
        if (!sessionId) return true;
        return persist(sessionId);
      },

      dispose(): void {
        disposed = true;
        get().stop();
      },

      exportActive(): string {
        const conversation = activeConversation();
        if (!conversation) return '';
        return JSON.stringify(conversation, null, 2);
      },
    };
  });

  return store;
}

export type ChatStore = ReturnType<typeof createChatStore>;
export type { ConversationMeta };
