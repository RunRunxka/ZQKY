/** 真实本地教材服务；独立于普通聊天模型目录，不包含云端回退。 */
import type { AskUserAnswer, AskUserInteraction, TurnExtensionSnapshot } from '@/contracts/chat';
import { API_BASE_PATH, ApiError, apiRequest } from '@/services/api-client';
import { createSseParser } from '@/services/chat-sse';
import type { ChatReplyAck, ChatService, ChatServiceEvent, ChatServiceRequest } from './chat-service';

export const LOCAL_RAG_PROFILE = {
  id: 'local-textbook-rag',
  modelLabel: '本地教材引擎',
  contextTokens: 8000,
  maxOutputTokens: 2048,
};

export function isRagCapability(extensions?: TurnExtensionSnapshot): boolean {
  return ['rag', 'ask_questions'].includes(extensions?.capability?.value ?? '');
}

export interface RagServiceStatus {
  available: boolean;
  detail: string;
  humanQuality?: string;
}

export function fetchRagStatus(signal?: AbortSignal): Promise<RagServiceStatus> {
  return apiRequest<RagServiceStatus>('/rag/status', { signal });
}

function protocolError(): never {
  throw new ApiError('RAG_PROTOCOL_ERROR', '教材服务返回的数据不完整，本轮已中断。', 0, false);
}

function parseInteraction(value: unknown): Pick<AskUserInteraction, 'interactionId' | 'intro' | 'questions' | 'status'> {
  if (!value || typeof value !== 'object') return protocolError();
  const card = value as AskUserInteraction;
  if (typeof card.interactionId !== 'string' || card.status !== 'waiting' ||
      (card.intro !== undefined && typeof card.intro !== 'string') ||
      !Array.isArray(card.questions) || !card.questions.length ||
      card.questions.some((q) => !q || typeof q.questionId !== 'string' || typeof q.prompt !== 'string' ||
        (q.options !== undefined && (!Array.isArray(q.options) || q.options.some((o) => typeof o?.label !== 'string')))))
    return protocolError();
  return card;
}

export async function streamRag(request: ChatServiceRequest, emit: (event: ChatServiceEvent) => void): Promise<void> {
  const question = request.rag?.question ?? [...request.messages].reverse().find((m) => m.role === 'user')?.content ?? '';
  const response = await fetch(`${API_BASE_PATH}/rag/stream`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', accept: 'text/event-stream' },
    body: JSON.stringify({
      requestId: request.turnId,
      sessionId: request.sessionId,
      turnId: request.turnId,
      question,
      ...(request.rag ? { afterEventId: request.rag.lastEventId } : {}),
    }),
    signal: request.signal,
  }).catch((error: unknown) => {
    if (request.signal.aborted) throw error;
    throw new ApiError('RAG_DISCONNECTED', '无法连接教材服务，输入和已收到的内容已保留。', 0, true);
  });
  if (!response.ok) {
    const failure = await response.json().catch(() => null) as { code?: string; message?: string; detail?: string; retryable?: boolean } | null;
    throw new ApiError(failure?.code ?? 'RAG_UNAVAILABLE', failure?.message ?? failure?.detail ?? `教材服务不可用（HTTP ${response.status}）。`, response.status, failure?.retryable ?? response.status >= 500);
  }
  if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream')) protocolError();
  let lastId = request.rag?.lastEventId ?? 0;
  let terminal = false;
  const decoder = new TextDecoder();
  const parser = createSseParser(({ name, data, id }) => {
    if (terminal) return;
    const eventId = Number(id);
    if (!Number.isSafeInteger(eventId) || eventId < 1) protocolError();
    // 重连可能重送最后一条事件；游标去重，永不再次追加已持久化文本。
    if (eventId <= lastId) return;
    if (eventId !== lastId + 1) protocolError();
    let payload: Record<string, unknown>;
    try { payload = JSON.parse(data) as Record<string, unknown>; } catch { return protocolError(); }
    if (!payload || payload.sessionId !== request.sessionId || payload.turnId !== request.turnId) protocolError();
    const base = { sessionId: request.sessionId, turnId: request.turnId, eventId };
    if (name === 'message.start') emit({ ...base, type: 'turn-start' });
    else if (name === 'text.delta') {
      if (typeof payload.text !== 'string') protocolError();
      emit({ ...base, type: 'text', delta: payload.text });
    } else if (name === 'wait-user') emit({ ...base, type: 'wait-user', interaction: parseInteraction(payload.interaction) });
    else if (name === 'reply.accepted') {
      if (typeof payload.interactionId !== 'string' || typeof payload.submissionId !== 'string' || !Array.isArray(payload.answers)) protocolError();
      if (payload.answers.some((a: unknown) => !a || typeof a !== 'object' ||
        typeof (a as AskUserAnswer).questionId !== 'string' || !Array.isArray((a as AskUserAnswer).labels) ||
        (a as AskUserAnswer).labels.some((label) => typeof label !== 'string') ||
        ((a as AskUserAnswer).freeText !== undefined && typeof (a as AskUserAnswer).freeText !== 'string'))) protocolError();
      emit({ ...base, type: 'reply-accepted', interactionId: payload.interactionId, submissionId: payload.submissionId, answers: payload.answers as AskUserAnswer[] });
    } else if (name === 'message.end') {
      emit({ ...base, type: 'end', finishReason: String(payload.finishReason ?? 'stop') });
      terminal = true;
    } else if (name === 'error') {
      emit({ ...base, type: 'error', error: { code: String(payload.code ?? 'RAG_ERROR'), message: String(payload.message ?? '教材服务执行失败。'), retryable: Boolean(payload.retryable) } });
      terminal = true;
    } else {
      // rag.result 的证据已由服务端渲染为正文；仍保存其游标，不将不认识的事件冒充完成。
      emit({ ...base, type: 'checkpoint' });
    }
    lastId = eventId;
  });
  const reader = response.body!.getReader();
  try {
    while (!terminal) {
      const { value, done } = await reader.read();
      if (done) break;
      parser.push(decoder.decode(value, { stream: true }));
    }
    parser.push(decoder.decode());
    parser.end();
    if (!terminal) throw new ApiError('RAG_DISCONNECTED', '教材服务连接中断。可继续本轮恢复已完成的结果；不会重新开始推理。', 0, true);
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}

export function createRagChatService(): ChatService {
  return {
    kind: 'real',
    run: streamRag,
    checkRagAvailable: fetchRagStatus,
    submitReply: ({ sessionId, turnId, interactionId, submissionId, answers, signal }) => apiRequest<ChatReplyAck>('/rag/reply', {
      method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ sessionId, turnId, interactionId, submissionId, answers }), signal,
    }),
    cancel: ({ sessionId, turnId }) => apiRequest('/rag/cancel', {
      method: 'POST', headers: { 'content-type': 'application/json' }, body: JSON.stringify({ sessionId, turnId }),
    }),
  };
}
