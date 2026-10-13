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

/**
 * 错误详情冻结形状：409 版本冲突用 currentRevision，422 用 issues（简单字段错误可用 fields），
 * 受引用守卫的 409（如 `*_IN_USE`）用 counts 逐项列出引用条数。
 */
export interface ApiErrorDetails {
  currentRevision?: number;
  issues?: ErrorIssue[];
  fields?: string[];
  /**
   * 受引用守卫 409 的逐项引用计数（键 → 条数）。键名是**域内词表**，由各页的标签表解释
   * （如 `referenceCounts(details, ASSESSMENT_COUNT_LABELS)`）；未知键按原样显示，不隐藏引用。
   */
  counts?: Record<string, number>;
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
