/** 模型设置契约（contract-v1）。字段与 apps/api 的 schemas/model_config.py 及路由视图保持一致。 */

export type ModelProtocol = 'openai-chat' | 'openai-responses' | 'anthropic-messages';

export const MODEL_PROTOCOL_LABELS: Record<ModelProtocol, string> = {
  'openai-chat': 'OpenAI 兼容 Chat Completions',
  'openai-responses': 'OpenAI Responses',
  'anthropic-messages': 'Anthropic Messages',
};

/** 连接声明的 API 格式；auto 由后端在请求开始前按供应商/模型解析。 */
export type ApiFormat = 'auto' | 'openai_chat' | 'openai_responses' | 'anthropic';

export const API_FORMAT_LABELS: Record<ApiFormat, string> = {
  auto: '自动（按供应商与模型判断）',
  openai_chat: 'OpenAI Chat Completions',
  openai_responses: 'OpenAI Responses',
  anthropic: 'Anthropic Messages',
};

/** 受控推理深度全集；实际可用子集由供应商/模型限制（后端校验）。 */
export type ReasoningEffort = 'none' | 'minimal' | 'low' | 'medium' | 'high' | 'xhigh' | 'max';

export const REASONING_EFFORT_VALUES: ReasoningEffort[] = [
  'none',
  'minimal',
  'low',
  'medium',
  'high',
  'xhigh',
  'max',
];

export const REASONING_EFFORT_LABELS: Record<ReasoningEffort, string> = {
  none: '关闭',
  minimal: '最低',
  low: '低',
  medium: '中',
  high: '高',
  xhigh: '很高',
  max: '最高',
};

/** 只读派生：该供应商用哪种字段表达推理（thinking/enable_thinking/reasoning_split）。 */
export type ReasoningStyle = 'thinking_type' | 'enable_thinking' | 'reasoning_split';

export const REASONING_STYLE_LABELS: Record<ReasoningStyle, string> = {
  thinking_type: 'thinking.type',
  enable_thinking: 'enable_thinking',
  reasoning_split: 'reasoning_split',
};

export type CapabilityEvidence = 'verified' | 'claimed' | 'unknown';

export const CAPABILITY_EVIDENCE_LABELS: Record<CapabilityEvidence, string> = {
  verified: '已验证',
  claimed: '人工声明',
  unknown: '未知',
};

/** 供应商模式（D15：后端不下发原始 backend）。 */
export type ProviderMode = 'standard' | 'gateway' | 'local' | 'direct' | 'oauth';
export type ProviderAuthMode = 'api_key' | 'oauth' | 'none';

export const PROVIDER_MODE_LABELS: Record<ProviderMode, string> = {
  standard: '标准云服务',
  gateway: '聚合网关',
  local: '本机服务',
  direct: '自定义',
  oauth: '专用认证',
};

export const AUTH_MODE_LABELS: Record<ProviderAuthMode, string> = {
  api_key: 'API Key',
  oauth: '授权登录',
  none: '无需凭证',
};

export interface ModelProviderView {
  providerId: string;
  label: string;
  aliases: string[];
  mode: ProviderMode;
  authMode: ProviderAuthMode;
  apiFormats: ApiFormat[];
  defaultApiFormat: ApiFormat;
  defaultApiBase: string;
  baseUrlsByFormat: Record<string, string>;
  supportsWireApiSelection: boolean;
  supportsModelDiscovery: boolean;
  requiresKey: boolean;
  isLegacy: boolean;
  legacyOf: string[];
  thinkingStyle: ReasoningStyle | null;
  /** 认证可用性（Codex OAuth 缺自有应用凭据时为 false） */
  authAvailable?: boolean;
  authUnavailableReason?: string | null;
}

export interface ModelConnectionView {
  id: string;
  displayName: string;
  providerId: string | null;
  providerLabel: string | null;
  protocol: ModelProtocol;
  apiFormat: ApiFormat;
  apiVersion: string | null;
  /** 用户原值；空字符串表示使用供应商默认地址 */
  baseUrl: string;
  /** 运行期实际地址（baseUrl 或供应商默认） */
  resolvedBaseUrl: string;
  hasCredential: boolean;
  credentialScope: 'process' | 'env-file';
  credentialEnvName?: string;
  extraHeaderNames: string[];
  createdAt: string;
  updatedAt: string;
}

export interface ModelConnectionSummary {
  displayName: string;
  providerId: string | null;
  providerLabel: string | null;
  protocol: ModelProtocol;
  apiFormat: ApiFormat;
  hasCredential: boolean;
}

export interface ModelProfileView {
  id: string;
  connectionId: string;
  displayName: string;
  modelId: string;
  purpose: string | null;
  contextTokens: number | null;
  maxOutputTokens: number | null;
  supportedParams: string[];
  params?: Record<string, number>;
  reasoningEnabled: boolean | null;
  reasoningEffort: ReasoningEffort | null;
  /** 只读派生；不接受写入 */
  reasoningStyle: ReasoningStyle | null;
  capabilities: Record<string, CapabilityEvidence>;
  connection: ModelConnectionSummary | null;
  createdAt: string;
  updatedAt: string;
}

export interface ConnectionInput {
  displayName: string;
  providerId?: string | null;
  protocol?: ModelProtocol;
  apiFormat?: ApiFormat;
  baseUrl?: string;
  apiVersion?: string | null;
  apiKey?: string;
  credentialAction?: 'keep' | 'replace' | 'clear';
  extraHeaders?: Record<string, string>;
  expectedRevision?: number;
}

export interface ProfileInput {
  connectionId: string;
  displayName: string;
  modelId: string;
  purpose?: string | null;
  contextTokens?: number | null;
  maxOutputTokens?: number | null;
  supportedParams?: string[];
  params?: Record<string, number>;
  capabilities?: Record<string, CapabilityEvidence>;
  reasoningEnabled?: boolean | null;
  reasoningEffort?: ReasoningEffort | null;
  expectedRevision?: number;
}

export type ModelTestResult =
  | {
      ok: true;
      text: string;
      finishReason: string;
      usage: { inputTokens: number | null; outputTokens: number | null } | null;
      latencyMs: number;
      stream?: { chunks: number; firstTextMs: number | null; lastTextMs: number | null };
    }
  | { ok: false; error: { code: string; message: string; retryable?: boolean } };

export const KNOWN_GENERATION_PARAMS = ['temperature', 'top_p'] as const;

export interface ModelCatalog {
  revision: number;
  defaultChatProfileId: string | null;
  connections: ModelConnectionView[];
  profiles: ModelProfileView[];
}

export interface ModelProviderDirectory {
  providers: ModelProviderView[];
  legacy: ModelProviderView[];
}

/** 模型发现来源：upstream=上游实时；catalog=有来源的目录；manual=无发现能力。 */
export type DiscoverySource = 'upstream' | 'manual' | `catalog:${string}`;

export interface DiscoveryResult {
  models: { id: string }[];
  source: DiscoverySource;
  note?: string;
}

export const DISCOVERY_SOURCE_LABELS: Record<string, string> = {
  upstream: '来自上游实时接口',
  manual: '该供应商无模型列表接口，需手工添加',
};

/** 认证四态状态机（D10）。 */
export type AuthConnectionState = 'disconnected' | 'authorizing' | 'connected' | 'error';

export interface AuthStatus {
  connection: AuthConnectionState;
  authMode: ProviderAuthMode | null;
  provider?: string;
  operationId?: string;
  operationState?: 'waiting' | 'completed' | 'cancelled' | 'expired' | 'failed';
  authorizeUrl?: string | null;
  expiresIn?: number;
  errorCode?: string | null;
  userLabel?: string;
  accountId?: string | null;
  available?: boolean;
  unavailableReason?: string | null;
  note?: string;
  hasCachedAccessToken?: boolean;
  supportedModes?: string[];
}

export interface AuthActionResult {
  ok: boolean;
  status?: AuthStatus;
  errorCode?: string;
  message?: string;
  nextSteps?: string[];
}

export const AUTH_STATE_LABELS: Record<AuthConnectionState, string> = {
  disconnected: '未连接',
  authorizing: '等待授权',
  connected: '已连接',
  error: '需要处理',
};

export const KNOWN_PARAM_LABELS: Record<(typeof KNOWN_GENERATION_PARAMS)[number], string> = {
  temperature: '温度（temperature）',
  top_p: '核采样（top_p）',
};
