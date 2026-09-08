/**
 * /api/v1 的同源 HTTP 适配器：只用相对路径请求本机代理，不直接访问外部主机。
 * 错误统一转换为 ApiError；后端不可达或网关错误时给出准确原因，不伪造成功。
 */

import type { ApiErrorEnvelope, CapabilitiesResponse, HealthResponse } from '@/contracts/api';

export const API_BASE_PATH = '/api/v1';

export class ApiError extends Error {
  constructor(
    readonly code: string,
    message: string,
    readonly status: number,
    readonly retryable: boolean,
    readonly requestId?: string,
  ) {
    super(message);
    this.name = 'ApiError';
  }
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

export async function apiRequest<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_PATH}${path}`, {
      ...init,
      headers: { accept: 'application/json', ...init?.headers },
    });
  } catch {
    throw new ApiError('SERVICE_UNAVAILABLE', '后端服务未运行或无法连接。', 0, true);
  }
  if (!response.ok) {
    const envelope = await parseEnvelope(response);
    if (envelope) {
      throw new ApiError(
        envelope.code,
        envelope.message,
        response.status,
        envelope.retryable ?? false,
        envelope.requestId,
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
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function fetchHealth(signal?: AbortSignal): Promise<HealthResponse> {
  return apiRequest<HealthResponse>('/health', { signal });
}

export function fetchCapabilities(signal?: AbortSignal): Promise<CapabilitiesResponse> {
  return apiRequest<CapabilitiesResponse>('/capabilities', { signal });
}
