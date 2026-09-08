/**
 * 后端 /api/v1 契约（D02）。字段与 apps/api 的 schemas 保持一致；
 * 修改任一侧时必须同步另一侧并更新测试。
 */

export interface ApiErrorEnvelope {
  code: string;
  message: string;
  requestId?: string;
  retryable?: boolean;
  details?: Record<string, unknown>;
}

export type CapabilityStatus = 'planned' | 'ready' | 'unconfigured' | 'unavailable';

export interface ApiCapability {
  feature: string;
  label: string;
  status: CapabilityStatus;
  detail: string;
}

export interface CapabilitiesResponse {
  service: string;
  apiVersion: string;
  generatedAt: string;
  capabilities: ApiCapability[];
}

export interface HealthResponse {
  status: string;
  service: string;
  apiVersion: string;
  time: string;
}
