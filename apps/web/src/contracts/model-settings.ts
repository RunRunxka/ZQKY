/** 模型设置契约（D03）。字段与 apps/api 的 schemas/model_config.py 及路由视图保持一致。 */

export type ModelProtocol = 'openai-chat' | 'openai-responses' | 'anthropic-messages';

export const MODEL_PROTOCOL_LABELS: Record<ModelProtocol, string> = {
  'openai-chat': 'OpenAI 兼容 Chat Completions',
  'openai-responses': 'OpenAI Responses',
  'anthropic-messages': 'Anthropic Messages',
};

export type CapabilityEvidence = 'verified' | 'claimed' | 'unknown';

export const CAPABILITY_EVIDENCE_LABELS: Record<CapabilityEvidence, string> = {
  verified: '已验证',
  claimed: '人工声明',
  unknown: '未知',
};

export interface ModelConnectionView {
  id: string;
  displayName: string;
  protocol: ModelProtocol;
  baseUrl: string;
  hasCredential: boolean;
  credentialScope: 'process';
  extraHeaderNames: string[];
  createdAt: string;
  updatedAt: string;
}

export interface ModelConnectionSummary {
  displayName: string;
  protocol: ModelProtocol;
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
  capabilities: Record<string, CapabilityEvidence>;
  connection: ModelConnectionSummary | null;
  createdAt: string;
  updatedAt: string;
}

export interface ConnectionInput {
  displayName: string;
  protocol: ModelProtocol;
  baseUrl: string;
  apiKey?: string;
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

export const KNOWN_PARAM_LABELS: Record<(typeof KNOWN_GENERATION_PARAMS)[number], string> = {
  temperature: '温度（temperature）',
  top_p: '核采样（top_p）',
};
