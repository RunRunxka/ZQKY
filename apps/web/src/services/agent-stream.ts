/**
 * /api/v1/agent/* 的流式客户端：POST fetch + ReadableStream 消费 SSE。
 * 与 chat-stream 同一消费模式；本模块不存储任何凭证。
 *
 * - streamAgent：发起一轮对话（可附上传文件引用）；
 * - confirmAgent：教师对写操作确认卡的决定，恢复被 interrupt 挂起的图（同样是 SSE 流）；
 * - uploadAgent：先落 blob 拿 assetRef，随 streamAgent 的 attachments 传入。
 */

import { API_BASE_PATH, ApiError } from './api-client';
import { createSseParser } from './chat-sse';

export interface AgentAttachment {
  assetId: string;
  fileName: string;
  mediaType: string;
  kind?: 'auto' | 'textbook' | 'paper' | 'roster' | 'score' | 'question';
}

export interface AgentUploadResult {
  assetId: string;
  fileName: string;
  mediaType: string;
  byteSize: number;
  sha256: string;
}

export interface AgentStreamInput {
  requestId: string;
  threadId: string;
  message: string;
  modelProfileId: string;
  attachments?: AgentAttachment[];
  signal?: AbortSignal;
}

export interface AgentConfirmInput {
  submissionId: string;
  requestId: string;
  threadId: string;
  modelProfileId: string;
  confirmId: string;
  decision: 'approve' | 'reject';
  signal?: AbortSignal;
}

export interface AgentConfirmPayload {
  /** 写操作确认卡的负载（由后端 interrupt value 给出，原样透传给确认卡渲染） */
  [key: string]: unknown;
}

export interface AgentStreamHandlers {
  onStart?: (info: { requestId: string; messageId: string; threadId: string; modelProfileId: string }) => void;
  onText?: (delta: string) => void;
  onToolCall?: (call: { name: string; args: Record<string, unknown>; callId: string }) => void;
  onToolResult?: (result: { name: string; callId: string; output: string }) => void;
  onWaitConfirm?: (confirm: { confirmId: string; payload: AgentConfirmPayload }) => void;
  onEnd?: (finishReason: string) => void;
  onError?: (error: { code: string; message: string; retryable?: boolean }) => void;
}

const KNOWN_EVENTS = new Set([
  'message.start',
  'text.delta',
  'tool.call',
  'tool.result',
  'wait-confirm',
  'message.end',
  'error',
]);

async function postSse(path: string, body: Record<string, unknown>, signal?: AbortSignal): Promise<Response> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_PATH}${path}`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'text/event-stream' },
      body: JSON.stringify(body),
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError('SERVICE_UNAVAILABLE', '后端服务未运行或无法连接。', 0, true);
  }
  if (!response.ok) {
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
    throw new ApiError('REQUEST_FAILED', `请求失败（HTTP ${response.status}）。`, response.status, false);
  }
  if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream')) {
    throw new ApiError('SERVICE_UNAVAILABLE', '后端未返回流式响应。', response.status, true);
  }
  return response;
}

async function consume(response: Response, handlers: AgentStreamHandlers): Promise<void> {
  const decoder = new TextDecoder('utf-8');
  let terminal = false;
  const parser = createSseParser(({ name, data }) => {
    if (terminal || !KNOWN_EVENTS.has(name)) return;
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
        threadId: String(payload.threadId ?? ''),
        modelProfileId: String(payload.modelProfileId ?? ''),
      });
    } else if (name === 'text.delta') {
      if (typeof payload.text === 'string' && payload.text.length > 0) handlers.onText?.(payload.text);
    } else if (name === 'tool.call') {
      handlers.onToolCall?.({
        name: String(payload.name ?? 'tool'),
        args: (payload.args as Record<string, unknown>) ?? {},
        callId: String(payload.callId ?? ''),
      });
    } else if (name === 'tool.result') {
      handlers.onToolResult?.({
        name: String(payload.name ?? 'tool'),
        callId: String(payload.callId ?? ''),
        output: String(payload.output ?? ''),
      });
    } else if (name === 'wait-confirm') {
      handlers.onWaitConfirm?.({
        confirmId: String(payload.confirmId ?? ''),
        payload: (payload.payload as AgentConfirmPayload) ?? {},
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

  const reader = response.body!.getReader();
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
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

export async function streamAgent(input: AgentStreamInput, handlers: AgentStreamHandlers): Promise<void> {
  const response = await postSse(
    '/agent/stream',
    {
      requestId: input.requestId,
      threadId: input.threadId,
      message: input.message,
      modelProfileId: input.modelProfileId,
      ...(input.attachments && input.attachments.length > 0 ? { attachments: input.attachments } : {}),
    },
    input.signal,
  );
  await consume(response, handlers);
}

export async function confirmAgent(input: AgentConfirmInput, handlers: AgentStreamHandlers): Promise<void> {
  const response = await postSse(
    '/agent/confirm',
    {
      submissionId: input.submissionId,
      requestId: input.requestId,
      threadId: input.threadId,
      modelProfileId: input.modelProfileId,
      confirmId: input.confirmId,
      decision: input.decision,
    },
    input.signal,
  );
  await consume(response, handlers);
}

export async function uploadAgent(file: File, signal?: AbortSignal): Promise<AgentUploadResult> {
  const form = new FormData();
  form.append('file', file, file.name);
  let response: Response;
  try {
    response = await fetch(`${API_BASE_PATH}/agent/upload`, {
      method: 'POST',
      body: form,
      signal,
    });
  } catch (error) {
    if (error instanceof DOMException && error.name === 'AbortError') throw error;
    throw new ApiError('SERVICE_UNAVAILABLE', '后端服务未运行或无法连接。', 0, true);
  }
  if (!response.ok) {
    let envelope: { code?: string; message?: string; retryable?: boolean } | null = null;
    try {
      envelope = await response.json();
    } catch {
      envelope = null;
    }
    if (envelope && typeof envelope.code === 'string') {
      throw new ApiError(
        envelope.code,
        envelope.message ?? '上传失败。',
        response.status,
        envelope.retryable ?? false,
      );
    }
    throw new ApiError('REQUEST_FAILED', `上传失败（HTTP ${response.status}）。`, response.status, false);
  }
  return (await response.json()) as AgentUploadResult;
}
