/**
 * /api/v1/lesson-plans/generation-stream 的流式客户端（C3-3）：
 * 教案候选按模块流式生成——module.delta 累积到生成缓冲，module.done 后由调用方解析入稿。
 * 本模块不存储任何凭证。
 */

import { API_BASE_PATH, ApiError } from './api-client';
import { createSseParser } from './chat-sse';

export type LessonStreamModule =
  | 'analysis' | 'objectives' | 'strategy' | 'process'
  | 'exercises' | 'evaluation' | 'reflection';

export interface LessonStreamInput {
  requestId: string;
  modelProfileId: string;
  courseName: string;
  requirements?: string;
  analysisRunId?: string;
  selectedKnowledgePointIds?: string[];
  modules?: LessonStreamModule[];
  signal?: AbortSignal;
}

export interface LessonStreamHandlers {
  onStart?: (info: { requestId: string; modules: string[] }) => void;
  onModuleStart?: (module: string, label: string) => void;
  onModuleDelta?: (module: string, delta: string) => void;
  onModuleError?: (module: string, message: string) => void;
  onModuleDone?: (module: string) => void;
  onEnd?: (finishReason: string) => void;
  onError?: (error: { code: string; message: string; retryable?: boolean }) => void;
}

const KNOWN_EVENTS = new Set([
  'message.start', 'module.start', 'module.delta', 'module.error', 'module.done', 'message.end', 'error',
]);

export async function streamLessonModules(input: LessonStreamInput, handlers: LessonStreamHandlers): Promise<void> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_PATH}/lesson-plans/generation-stream`, {
      method: 'POST',
      headers: { 'content-type': 'application/json', accept: 'text/event-stream' },
      body: JSON.stringify({
        requestId: input.requestId,
        modelProfileId: input.modelProfileId,
        courseName: input.courseName,
        ...(input.requirements ? { requirements: input.requirements } : {}),
        ...(input.analysisRunId ? { analysisRunId: input.analysisRunId } : {}),
        ...(input.selectedKnowledgePointIds?.length ? { selectedKnowledgePointIds: input.selectedKnowledgePointIds } : {}),
        ...(input.modules?.length ? { modules: input.modules } : {}),
      }),
      signal: input.signal,
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
      throw new ApiError(envelope.code, envelope.message ?? '请求失败。', response.status, envelope.retryable ?? false);
    }
    if (response.status >= 500) throw new ApiError('SERVICE_UNAVAILABLE', '后端服务不可用。', response.status, true);
    throw new ApiError('REQUEST_FAILED', `请求失败（HTTP ${response.status}）。`, response.status, false);
  }
  if (!response.body || !response.headers.get('content-type')?.includes('text/event-stream')) {
    throw new ApiError('SERVICE_UNAVAILABLE', '后端未返回流式响应。', response.status, true);
  }
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
        modules: Array.isArray(payload.modules) ? payload.modules.map(String) : [],
      });
    } else if (name === 'module.start') {
      handlers.onModuleStart?.(String(payload.module ?? ''), String(payload.label ?? ''));
    } else if (name === 'module.delta') {
      if (typeof payload.text === 'string' && payload.text) handlers.onModuleDelta?.(String(payload.module ?? ''), payload.text);
    } else if (name === 'module.error') {
      handlers.onModuleError?.(String(payload.module ?? ''), String(payload.message ?? '生成失败。'));
    } else if (name === 'module.done') {
      handlers.onModuleDone?.(String(payload.module ?? ''));
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
      parser.push(decoder.decode(value, { stream: true }));
      if (terminal) break;
    }
    parser.push(decoder.decode());
    parser.end();
    if (!terminal) throw new ApiError('STREAM_INTERRUPTED', '连接中断，已保留收到的内容。', 0, true);
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
