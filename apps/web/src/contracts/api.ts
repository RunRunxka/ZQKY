/**
 * 后端 /api/v1 契约（D02）。字段与 apps/api 的 schemas 保持一致；
 * 修改任一侧时必须同步另一侧并更新测试。
 */

/** 422 行列错误：定位到原行/原列，不回显请求内容（TEACHING-LOOP B0 冻结）。 */
export interface ErrorIssue {
  row?: number;
  column?: string;
  field?: string;
  code: string;
  message: string;
}

/** 错误详情冻结形状：409 版本冲突用 currentRevision，422 用 issues（简单字段错误可用 fields）。 */
export interface ApiErrorDetails {
  currentRevision?: number;
  issues?: ErrorIssue[];
  fields?: string[];
}

export interface ApiErrorEnvelope {
  code: string;
  message: string;
  requestId?: string;
  retryable?: boolean;
  details?: ApiErrorDetails;
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
