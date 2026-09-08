/**
 * /api/v1/chat/stream 的流式客户端：POST fetch + ReadableStream 消费 SSE。
 * 未实现能力（RAG、附件、工具）不提供入口；本模块不存储任何凭证。
 */

import { API_BASE_PATH, ApiError } from './api-client';
import { createSseParser } from './chat-sse';
import type { ChatRole } from '@/contracts/chat';

export interface ChatStreamInput {
  requestId: string;
  modelProfileId: string;
  messages: { role: ChatRole; content: string }[];
  maxOutputTokens?: number;
  params?: Record<string, unknown>;
  signal?: AbortSignal;
}

export interface ChatStreamHandlers {
  onStart?: (info: { requestId: string; messageId: string; modelProfileId: string }) => void;
  onText?: (delta: string) => void;
  /** 推理模型的思考过程增量（DeepSeek reasoning_content / Anthropic thinking 等） */
  onReasoning?: (delta: string) => void;
  onUsage?: (usage: { inputTokens?: number | null; outputTokens?: number | null }) => void;
  onEnd?: (finishReason: string) => void;
  onError?: (error: { code: string; message: string; retryable?: boolean }) => void;
}

export async function streamChat(
  input: ChatStreamInput,
  handlers: ChatStreamHandlers,
): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_PATH}/chat/stream`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'text/event-stream' },
      body: JSON.stringify({
        requestId: input.requestId,
        modelProfileId: input.modelProfileId,
        messages: input.messages,
        ...(input.maxOutputTokens ? { maxOutputTokens: input.maxOutputTokens } : {}),
        ...(input.params ? { params: input.params } : {}),
      }),
      signal: input.signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError('SERVICE_UNAVAILABLE', '后端服务未运行或无法连接。', 0, true);
  }
  if (!response.ok) {
    // 流开始前失败：优先使用后端错误信封，否则按网关/网络错误处理
    let envelope: { code?: string; message?: string; retryable?: boolean } | null = null;
    try {
      envelope = await response.json();
    } catch {
      envelope = null;
    }
    if (envelope && typeof envelope.code === 'string') {
      throw new ApiError(
        envelope.code,
        envelope.message ?? '请求失败。',
        response.status,
        envelope.retryable ?? false,
      );
    }
    if (response.status >= 500) {
      throw new ApiError('SERVICE_UNAVAILABLE', '后端服务不可用。', response.status, true);
    }
    throw new ApiError(
      'REQUEST_FAILED',
      `请求失败（HTTP ${response.status}）。`,
      response.status,
      false,
    );
  }
  if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream')) {
    throw new ApiError('SERVICE_UNAVAILABLE', '后端未返回流式响应。', response.status, true);
  }

  const decoder = new TextDecoder('utf-8');
  let terminal = false;
  const parser = createSseParser(({ name, data }) => {
    if (terminal) return;
    if (!KNOWN_EVENTS.has(name)) {
      return; // 未知事件版本化前忽略，避免新字段导致崩溃
    }
    let payload: Record<string, unknown>;
    try {
      payload = JSON.parse(data) as Record<string, unknown>;
    } catch {
      return;
    }
    if (name === 'message.start') {
      handlers.onStart?.({
        requestId: String(payload.requestId ?? ''),
        messageId: String(payload.messageId ?? ''),
        modelProfileId: String(payload.modelProfileId ?? ''),
      });
    } else if (name === 'text.delta') {
      if (typeof payload.text === 'string' && payload.text.length > 0) {
        handlers.onText?.(payload.text);
      }
    } else if (name === 'reasoning.delta') {
      if (typeof payload.text === 'string' && payload.text.length > 0) {
        handlers.onReasoning?.(payload.text);
      }
    } else if (name === 'usage') {
      handlers.onUsage?.({
        inputTokens: (payload.inputTokens as number | null | undefined) ?? null,
        outputTokens: (payload.outputTokens as number | null | undefined) ?? null,
      });
    } else if (name === 'message.end') {
      terminal = true;
      handlers.onEnd?.(String(payload.finishReason ?? 'unknown'));
    } else if (name === 'error') {
      terminal = true;
      handlers.onError?.({
        code: String(payload.code ?? 'UPSTREAM_ERROR'),
        message: String(payload.message ?? '上游流异常结束。'),
        retryable: Boolean(payload.retryable),
      });
    }
  });

  const reader = response.body.getReader();
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      // stream:true 保留解码器状态，UTF-8 字符跨网络分块时也能正确解码
      parser.push(decoder.decode(value, { stream: true }));
      if (terminal) break;
    }
    parser.push(decoder.decode());
    parser.end();
    if (!terminal)
      throw new ApiError('STREAM_INTERRUPTED', '连接中断，已保留收到的内容。', 0, true);
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}

const KNOWN_EVENTS = new Set([
  'message.start',
  'text.delta',
  'reasoning.delta',
  'usage',
  'message.end',
  'error',
]);
