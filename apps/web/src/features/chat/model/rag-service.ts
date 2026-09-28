/** 真实本地教材服务（RAG v2）；独立于普通聊天模型目录，不包含云端回退。 */
import type { AskUserAnswer, AskUserInteraction, TurnExtensionSnapshot } from '@/contracts/chat';
import type { TextbookSelection } from '@/contracts/textbook';
import { API_BASE_PATH, ApiError, apiRequest } from '@/services/api-client';
import { createSseParser } from '@/services/chat-sse';
import type { ChatReplyAck, ChatService, ChatServiceEvent, ChatServiceRequest } from './chat-service';
import { isRagResultV2, isScopeSnapshot, type RagExplainRequest } from './rag-v2';

export const LOCAL_RAG_PROFILE = {
  id: 'local-textbook-rag',
  modelLabel: '本地教材引擎',
  contextTokens: 8000,
  maxOutputTokens: 2048,
};

export function isRagCapability(extensions?: TurnExtensionSnapshot): boolean {
  return ['rag', 'ask_questions'].includes(extensions?.capability?.value ?? '');
}

/* ------------------------------------------------------------------ /rag/status（v2 分项） */

export interface RagSectionStatus {
  available: boolean;
  reason: string | null;
}

export interface RagRetrievalStatus extends RagSectionStatus {
  vectorStore: boolean;
  queryEmbedding: boolean;
  denseLimit: number | null;
  lexicalLimit: number | null;
  rrfK: number | null;
}

export interface RagSummarizationStatus extends RagSectionStatus {
  model: string | null;
  providerUrl: string | null;
}

export interface RagSourceAccessStatus extends RagSectionStatus {
  verifiesHash: boolean;
}

export interface RagScopeStatus {
  ready: boolean;
  reason: string | null;
  selection: TextbookSelection | null;
}

/**
 * 归一后的服务状态：检索 / 本地概括 / 原文访问**分别报告**，另给范围与人工教学质量位。
 * `available` 仅作「检索可用且范围就绪」的合成结论（既有调用点兼容），不是单一 localOnly。
 */
export interface RagServiceStatus {
  available: boolean;
  detail: string;
  humanQuality?: string;
  retrieval: RagRetrievalStatus;
  summarization: RagSummarizationStatus;
  sourceAccess: RagSourceAccessStatus;
  scope: RagScopeStatus;
  generation: unknown | null;
  /** 旧版结构（无 retrieval/scope）：按不可用处理并说明原因，不猜测可用性 */
  legacy: boolean;
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function textOrNull(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value : null;
}

function numberOrNull(value: unknown): number | null {
  return typeof value === 'number' && Number.isFinite(value) ? value : null;
}

function isTextbookSelection(value: unknown): value is TextbookSelection {
  return (
    isRecord(value) &&
    typeof value.gradeId === 'string' &&
    typeof value.subjectId === 'string' &&
    typeof value.editionId === 'string' &&
    Array.isArray(value.documentIds) &&
    value.documentIds.every((id) => typeof id === 'string')
  );
}

function section(value: unknown, missingReason: string): RagSectionStatus {
  if (!isRecord(value)) return { available: false, reason: missingReason };
  const available = value.available === true;
  const reason = textOrNull(value.reason);
  return { available, reason: available ? reason : (reason ?? missingReason) };
}

function legacyStatus(raw: unknown): RagServiceStatus {
  const detail = isRecord(raw) ? textOrNull(raw.detail) : null;
  const reason = detail ?? '教材服务返回旧版状态，未分别报告检索、概括与原文访问。';
  return {
    available: false,
    detail: `教材服务状态不可用（旧版结构）：${reason}`,
    ...(isRecord(raw) && typeof raw.humanQuality === 'string'
      ? { humanQuality: raw.humanQuality }
      : {}),
    retrieval: {
      ...section(null, '旧版状态未报告检索分区。'),
      vectorStore: false,
      queryEmbedding: false,
      denseLimit: null,
      lexicalLimit: null,
      rrfK: null,
    },
    summarization: {
      ...section(null, '旧版状态未报告本地概括分区。'),
      model: null,
      providerUrl: null,
    },
    sourceAccess: { ...section(null, '旧版状态未报告原文访问分区。'), verifiesHash: false },
    scope: { ready: false, reason: '旧版状态未报告任教范围。', selection: null },
    generation: null,
    legacy: true,
  };
}

/** v2 状态归一；旧结构或缺字段一律按不可用处理并给出可读原因，不抛错、不伪造可用。 */
export function normalizeRagStatus(raw: unknown): RagServiceStatus {
  if (!isRecord(raw) || (!('retrieval' in raw) && !('scope' in raw))) return legacyStatus(raw);
  const retrievalRaw = isRecord(raw.retrieval) ? raw.retrieval : null;
  const summarizationRaw = isRecord(raw.summarization) ? raw.summarization : null;
  const sourceRaw = isRecord(raw.sourceAccess) ? raw.sourceAccess : null;
  const scopeRaw = isRecord(raw.scope) ? raw.scope : null;
  const retrieval: RagRetrievalStatus = {
    ...section(retrievalRaw, '检索分区未报告。'),
    vectorStore: retrievalRaw?.vectorStore === true,
    queryEmbedding: retrievalRaw?.queryEmbedding === true,
    denseLimit: numberOrNull(retrievalRaw?.denseLimit),
    lexicalLimit: numberOrNull(retrievalRaw?.lexicalLimit),
    rrfK: numberOrNull(retrievalRaw?.rrfK),
  };
  const summarization: RagSummarizationStatus = {
    ...section(summarizationRaw, '本地概括分区未报告。'),
    model: textOrNull(summarizationRaw?.model),
    providerUrl: textOrNull(summarizationRaw?.providerUrl),
  };
  const sourceAccess: RagSourceAccessStatus = {
    ...section(sourceRaw, '原文访问分区未报告。'),
    verifiesHash: sourceRaw?.verifiesHash === true,
  };
  const scope: RagScopeStatus = {
    ready: scopeRaw?.ready === true,
    reason: textOrNull(scopeRaw?.reason),
    selection: isTextbookSelection(scopeRaw?.selection) ? scopeRaw.selection : null,
  };
  const available = retrieval.available && scope.ready;
  const parts: string[] = [];
  if (!retrieval.available)
    parts.push(`检索不可用：${retrieval.reason ?? '当前没有可发布的教材索引代'}`);
  if (!summarization.available)
    parts.push(`本地概括不可用：${summarization.reason ?? '未配置本机概括模型'}`);
  if (!sourceAccess.available)
    parts.push(`原文访问不可用：${sourceAccess.reason ?? '原文读取通道未就绪'}`);
  if (!scope.ready) parts.push(`任教范围未就绪：${scope.reason ?? '尚未保存任教范围'}`);
  return {
    available,
    detail: parts.length ? parts.join('；') : '教材检索、本地概括与原文访问均可用。',
    ...(typeof raw.humanQuality === 'string' ? { humanQuality: raw.humanQuality } : {}),
    retrieval,
    summarization,
    sourceAccess,
    scope,
    generation: raw.generation ?? null,
    legacy: false,
  };
}

export async function fetchRagStatus(signal?: AbortSignal): Promise<RagServiceStatus> {
  const raw = await apiRequest<unknown>('/rag/status', { signal });
  return normalizeRagStatus(raw);
}

/* ------------------------------------------------------------------ SSE 协议辅助 */

function protocolError(): never {
  throw new ApiError('RAG_PROTOCOL_ERROR', '教材服务返回的数据不完整，本轮已中断。', 0, false);
}

function parseInteraction(
  value: unknown,
): Pick<AskUserInteraction, 'interactionId' | 'intro' | 'questions' | 'status'> {
  // v2 为扁平载荷；兼容旧包装 {interaction: {...}}（历史测试替身与旧服务）。
  const card = isRecord(value) && isRecord(value.interaction) ? value.interaction : value;
  if (!isRecord(card)) return protocolError();
  const questions = card.questions;
  if (
    typeof card.interactionId !== 'string' ||
    card.status !== 'waiting' ||
    (card.intro !== undefined && typeof card.intro !== 'string') ||
    !Array.isArray(questions) ||
    !questions.length ||
    questions.some(
      (q) =>
        !isRecord(q) ||
        typeof q.questionId !== 'string' ||
        typeof q.prompt !== 'string' ||
        (q.header !== undefined && typeof q.header !== 'string') ||
        (q.multiSelect !== undefined && typeof q.multiSelect !== 'boolean') ||
        (q.allowFreeText !== undefined && typeof q.allowFreeText !== 'boolean') ||
        (q.options !== undefined &&
          (!Array.isArray(q.options) ||
            q.options.some(
              (o) =>
                !isRecord(o) ||
                typeof o.label !== 'string' ||
                (o.description !== undefined && typeof o.description !== 'string'),
            ))),
    )
  )
    return protocolError();
  return {
    interactionId: card.interactionId,
    status: 'waiting',
    ...(typeof card.intro === 'string' ? { intro: card.intro } : {}),
    questions: questions as AskUserInteraction['questions'],
  };
}

function parseReplyAnswers(value: unknown): AskUserAnswer[] {
  if (!Array.isArray(value)) return protocolError();
  for (const answer of value) {
    if (
      !isRecord(answer) ||
      typeof answer.questionId !== 'string' ||
      !Array.isArray(answer.labels) ||
      answer.labels.some((label) => typeof label !== 'string') ||
      (answer.freeText !== undefined && typeof answer.freeText !== 'string')
    )
      return protocolError();
  }
  return value as AskUserAnswer[];
}

/** 读流循环：所有 SSE 通道共用（断流在未收到终态事件时如实失败）。 */
async function pumpSse(
  response: Response,
  push: (text: string) => void,
  isTerminal: () => boolean,
  disconnected: () => ApiError,
): Promise<void> {
  if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream'))
    protocolError();
  const decoder = new TextDecoder();
  const reader = response.body.getReader();
  try {
    while (!isTerminal()) {
      const { value, done } = await reader.read();
      if (done) break;
      push(decoder.decode(value, { stream: true }));
    }
    push(decoder.decode());
    if (!isTerminal()) throw disconnected();
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}

async function ensureStreamResponse(
  path: string,
  body: unknown,
  signal: AbortSignal | undefined,
  connectMessage: string,
): Promise<Response> {
  const response = await fetch(`${API_BASE_PATH}${path}`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', accept: 'text/event-stream' },
    body: JSON.stringify(body),
    ...(signal ? { signal } : {}),
  }).catch((error: unknown) => {
    if (signal?.aborted) throw error;
    throw new ApiError('RAG_DISCONNECTED', connectMessage, 0, true);
  });
  if (!response.ok) {
    const failure = (await response.json().catch(() => null)) as
      | { code?: string; message?: string; detail?: string; retryable?: boolean }
      | null;
    throw new ApiError(
      failure?.code ?? 'RAG_UNAVAILABLE',
      failure?.message ?? failure?.detail ?? `教材服务不可用（HTTP ${response.status}）。`,
      response.status,
      failure?.retryable ?? response.status >= 500,
    );
  }
  return response;
}

/* ------------------------------------------------------------------ /rag/stream（定位） */

export async function streamRag(
  request: ChatServiceRequest,
  emit: (event: ChatServiceEvent) => void,
): Promise<void> {
  const rag = request.rag;
  // v2 必须带范围（首次=selection，续传=frozen 快照）；缺失时不发请求，明确报错。
  if (!rag?.scope) protocolError();
  const question =
    rag.question || [...request.messages].reverse().find((m) => m.role === 'user')?.content || '';
  const response = await ensureStreamResponse(
    '/rag/stream',
    {
      requestId: request.turnId,
      sessionId: request.sessionId,
      turnId: request.turnId,
      question,
      scope: rag.scope,
      afterEventId: rag.lastEventId ?? 0,
    },
    request.signal,
    '无法连接教材服务，输入和已收到的内容已保留。',
  );
  let lastId = rag.lastEventId ?? 0;
  let terminal = false;
  const parser = createSseParser(({ name, data, id }) => {
    if (terminal) return;
    const eventId = Number(id);
    if (!Number.isSafeInteger(eventId) || eventId < 1) protocolError();
    // 重连可能重送最后一条事件；游标去重，永不再次追加已持久化文本。
    if (eventId <= lastId) return;
    if (eventId !== lastId + 1) protocolError();
    let payload: Record<string, unknown>;
    try {
      payload = JSON.parse(data) as Record<string, unknown>;
    } catch {
      return protocolError();
    }
    if (!isRecord(payload) || payload.sessionId !== request.sessionId || payload.turnId !== request.turnId)
      protocolError();
    const base = { sessionId: request.sessionId, turnId: request.turnId, eventId };
    if (name === 'message.start') {
      if (!isScopeSnapshot(payload.scopeSnapshot)) protocolError();
      emit({ ...base, type: 'turn-start', scopeSnapshot: payload.scopeSnapshot });
    } else if (name === 'rag.result') {
      if (!isRagResultV2(payload.result)) protocolError();
      emit({ ...base, type: 'rag-result', result: payload.result });
    } else if (name === 'text.delta') {
      // v2：整段渲染好的正文，替换本轮正文（不是增量片段）
      if (typeof payload.text !== 'string') protocolError();
      emit({ ...base, type: 'text', delta: payload.text, replace: true });
    } else if (name === 'wait-user') {
      emit({ ...base, type: 'wait-user', interaction: parseInteraction(payload) });
    } else if (name === 'reply.accepted') {
      if (
        typeof payload.interactionId !== 'string' ||
        typeof payload.submissionId !== 'string' ||
        !Array.isArray(payload.answers)
      )
        protocolError();
      emit({
        ...base,
        type: 'reply-accepted',
        interactionId: payload.interactionId,
        submissionId: payload.submissionId,
        answers: parseReplyAnswers(payload.answers),
      });
    } else if (name === 'message.end') {
      emit({ ...base, type: 'end', finishReason: String(payload.finishReason ?? 'stop') });
      terminal = true;
    } else if (name === 'error') {
      emit({
        ...base,
        type: 'error',
        error: {
          code: String(payload.code ?? 'RAG_ERROR'),
          message: String(payload.message ?? '教材服务执行失败。'),
          retryable: Boolean(payload.retryable),
        },
      });
      terminal = true;
    } else {
      // 未知事件不冒充完成；仅推进游标，保留可续传位置。
      emit({ ...base, type: 'checkpoint' });
    }
    lastId = eventId;
  });
  await pumpSse(
    response,
    (text) => parser.push(text),
    () => terminal,
    () =>
      new ApiError(
        'RAG_DISCONNECTED',
        '教材服务连接中断。可继续本轮恢复已完成的结果；不会重新开始推理。',
        0,
        true,
      ),
  );
  parser.end();
}

/* ------------------------------------------------------------------ /rag/explain/stream（详解） */

export interface RagExplainHandlers {
  onStart?(info: { messageId: string; modelProfileId: string }): void;
  onText(delta: string): void;
  onEnd?(finishReason: string): void;
  onError?(error: { code: string; message: string; retryable: boolean }): void;
}

/**
 * 所选聊天模型的详解流：普通聊天 SSE 语义（`message.start / text.delta / message.end / error`），
 * **没有事件编号游标**；断开或停止即关闭上游（AbortSignal 直接传到底层 fetch）。
 * `text.delta` 是增量片段（与定位的整段正文不同）。
 */
export async function streamExplain(
  body: RagExplainRequest,
  handlers: RagExplainHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const response = await ensureStreamResponse(
    '/rag/explain/stream',
    body,
    signal,
    '无法连接教材详解服务，已保留题目、选择与已收到的内容。',
  );
  let messageId: string | null = null;
  let terminal = false;
  const parser = createSseParser(({ name, data }) => {
    if (terminal) return;
    let payload: Record<string, unknown>;
    try {
      payload = JSON.parse(data) as Record<string, unknown>;
    } catch {
      return protocolError();
    }
    if (!isRecord(payload)) return protocolError();
    if (name === 'message.start') {
      if (
        payload.sessionId !== body.sessionId ||
        payload.turnId !== body.turnId ||
        payload.requestId !== body.requestId ||
        typeof payload.messageId !== 'string'
      )
        protocolError();
      messageId = payload.messageId;
      handlers.onStart?.({
        messageId: payload.messageId,
        modelProfileId:
          typeof payload.modelProfileId === 'string' ? payload.modelProfileId : body.modelProfileId,
      });
    } else if (name === 'text.delta') {
      if (
        payload.sessionId !== body.sessionId ||
        payload.turnId !== body.turnId ||
        typeof payload.text !== 'string'
      )
        protocolError();
      if (payload.text) handlers.onText(payload.text);
    } else if (name === 'message.end') {
      if (payload.sessionId !== body.sessionId || payload.turnId !== body.turnId) protocolError();
      terminal = true;
      handlers.onEnd?.(String(payload.finishReason ?? 'stop'));
    } else if (name === 'error') {
      // 详解错误事件只有 requestId/messageId（无会话/轮次字段）：按已确认的 messageId 核对
      if (
        messageId &&
        typeof payload.messageId === 'string' &&
        payload.messageId !== messageId
      )
        protocolError();
      terminal = true;
      handlers.onError?.({
        code: String(payload.code ?? 'RAG_ERROR'),
        message: String(payload.message ?? '教材详解执行失败。'),
        retryable: Boolean(payload.retryable),
      });
    }
  });
  await pumpSse(
    response,
    (text) => parser.push(text),
    () => terminal,
    () =>
      new ApiError(
        'RAG_DISCONNECTED',
        '教材详解连接中断。可重试本轮详解（沿用同一模型与证据）。',
        0,
        true,
      ),
  );
  parser.end();
}

/* ------------------------------------------------------------------ 服务装配 */

export function createRagChatService(): ChatService {
  return {
    kind: 'real',
    run: streamRag,
    checkRagAvailable: fetchRagStatus,
    submitReply: ({ sessionId, turnId, interactionId, submissionId, answers, signal }) =>
      apiRequest<ChatReplyAck>('/rag/reply', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ requestId: submissionId, sessionId, turnId, interactionId, submissionId, answers }),
        signal,
      }),
    cancel: ({ sessionId, turnId }) =>
      apiRequest('/rag/cancel', {
        method: 'POST',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({ sessionId, turnId }),
      }),
  };
}
