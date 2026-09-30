/**
 * /api/v1 的同源 HTTP 适配器：只用相对路径请求本机代理，不直接访问外部主机。
 * 错误统一转换为 ApiError；后端不可达或网关错误时给出准确原因，不伪造成功。
 *
 * TEACHING-LOOP B0 补齐三个缺口：
 * 1. 错误信封的 `details`（`currentRevision` / `issues` / `fields`）随 ApiError 保留，
 *    调用方无需重新读响应体；
 * 2. 取消语义：`AbortError` 原样向上抛（配 `isAbortError` 判定），不再被吞成
 *    `SERVICE_UNAVAILABLE`；
 * 3. Blob 下载适配 `apiRequestBlob`（导出产物等二进制响应）。
 */

import type {
  ApiErrorDetails,
  ApiErrorEnvelope,
  CapabilitiesResponse,
  HealthResponse,
} from '@/contracts/api';

export const API_BASE_PATH = '/api/v1';

export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
    readonly retryable: boolean,
    readonly requestId?: string,
    readonly details?: ApiErrorDetails,
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

/** 判定 fetch/AbortSignal 引发的取消；取消不是失败，调用方应静默或恢复原状态。 */
export function isAbortError(error: unknown): boolean {
  if (typeof DOMException !== 'undefined' && error instanceof DOMException) {
    return error.name === 'AbortError';
  }
  return (
    typeof error === 'object' &&
    error !== null &&
    (error as { name?: unknown }).name === 'AbortError'
  );
}

async function parseEnvelope(response: Response): Promise<ApiErrorEnvelope | null> {
  try {
    const data: unknown = await response.json();
    if (data && typeof data === 'object' && typeof (data as ApiErrorEnvelope).code === 'string') {
      return data as ApiErrorEnvelope;
    }
    return null;
  } catch {
    return null;
  }
}

function errorFromResponse(response: Response, envelope: ApiErrorEnvelope | null): ApiError {
  if (envelope) {
    return new ApiError(
      envelope.code,
      envelope.message,
      response.status,
      envelope.retryable ?? false,
      envelope.requestId,
      envelope.details,
    );
  }
  if (response.status >= 500) {
    return new ApiError('SERVICE_UNAVAILABLE', '后端服务不可用。', response.status, true);
  }
  return new ApiError(
    'REQUEST_FAILED',
    `请求失败（HTTP ${response.status}）。`,
    response.status,
    false,
  );
}

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_PATH}${path}`, {
      ...init,
      headers: { accept: 'application/json', ...init?.headers },
    });
  } catch (error) {
    if (isAbortError(error)) {
      throw error;
    }
    throw new ApiError('SERVICE_UNAVAILABLE', '后端服务未运行或无法连接。', 0, true);
  }
  if (!response.ok) {
    throw errorFromResponse(response, await parseEnvelope(response));
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export interface BlobDownload {
  blob: Blob;
  /** 后端 `Content-Disposition` 给出的文件名（解码后）；没有则为 null。 */
  fileName: string | null;
}

/** 解析 `Content-Disposition` 的文件名（优先 RFC 5987 `filename*`，失败回退 `filename`）。 */
export function filenameFromDisposition(header: string | null): string | null {
  if (!header) {
    return null;
  }
  const extended = /filename\*=UTF-8''([^;]+)/i.exec(header);
  if (extended) {
    try {
      return decodeURIComponent(extended[1].trim());
    } catch {
      return extended[1].trim();
    }
  }
  const plain = /filename="?([^";]+)"?/i.exec(header);
  return plain ? plain[1].trim() : null;
}

/** 下载二进制产物；失败仍转换为 ApiError（含 details），不返回半截文件。 */
export async function apiRequestBlob(path: string, init?: RequestInit): Promise<BlobDownload> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_PATH}${path}`, { ...init });
  } catch (error) {
    if (isAbortError(error)) {
      throw error;
    }
    throw new ApiError('SERVICE_UNAVAILABLE', '后端服务未运行或无法连接。', 0, true);
  }
  if (!response.ok) {
    throw errorFromResponse(response, await parseEnvelope(response));
  }
  return {
    blob: await response.blob(),
    fileName: filenameFromDisposition(response.headers.get('content-disposition')),
  };
}

export function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiRequest<HealthResponse>('/health', { signal });
}

export function fetchCapabilities(signal?: AbortSignal): Promise<CapabilitiesResponse> {
  return apiRequest<CapabilitiesResponse>('/capabilities', { signal });
}
