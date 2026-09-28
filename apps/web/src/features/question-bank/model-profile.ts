/**
 * AI 整理使用的模型（v1.1 修复 D2）。
 *
 * 契约（总控裁定，B3 同步）：AI 整理**只用本机 Ollama 模型**，不调用云端；
 * `OrganizeRequest.modelProfileId` 是**可选的本地模型名**，空串 = 服务端默认（`qwen2.5:7b`）。
 * 取值来源：`GET /api/v1/rag/status` 的 `summarization.model`（本机在用的本地概括模型名）。
 *
 * 绝不把聊天模型 profileId（UUID）当成本地模型名发出去；读不到就如实说明原因并禁用入口。
 */

import { apiRequest } from '@/services/api-client';
import { asApiError } from './hooks';

export interface LocalOrganizerModel {
  /** 传给 `organize` 的本地模型名；空串表示使用服务端默认模型。 */
  modelName: string;
  /** `summarization.available`；为假时界面必须禁用「AI 整理」并给出原因。 */
  available: boolean;
  /** 不可用原因（可读中文）；可用时为 null。 */
  reason: string | null;
  providerUrl: string | null;
}

export const DEFAULT_ORGANIZER_UNAVAILABLE_REASON =
  '本机概括模型不可用：请确认本机 Ollama 正在运行且已拉取默认模型（如 qwen2.5:7b）后重试。';

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function textOrNull(value: unknown): string | null {
  return typeof value === 'string' && value.trim() ? value.trim() : null;
}

/** 解析 `/rag/status` 的 `summarization` 分区；形状不认识时按不可用处理，不猜造可用性。 */
export function parseLocalOrganizerModel(raw: unknown): LocalOrganizerModel {
  const summarization = isRecord(raw) && isRecord(raw.summarization) ? raw.summarization : null;
  if (!summarization) {
    return {
      modelName: '',
      available: false,
      reason: '教材服务未报告本机概括模型状态（服务未装配或返回旧版状态）。',
      providerUrl: null,
    };
  }
  const available = summarization.available === true;
  const model = textOrNull(summarization.model);
  const reason = textOrNull(summarization.reason);
  return {
    // 可用但未报告模型名时仍传空串，由服务端使用默认本机模型
    modelName: available ? (model ?? '') : '',
    available,
    reason: available ? null : (reason ?? DEFAULT_ORGANIZER_UNAVAILABLE_REASON),
    providerUrl: textOrNull(summarization.providerUrl),
  };
}

export async function fetchLocalOrganizerModel(signal?: AbortSignal): Promise<LocalOrganizerModel> {
  try {
    const raw = await apiRequest<unknown>('/rag/status', { signal });
    return parseLocalOrganizerModel(raw);
  } catch (cause) {
    const error = asApiError(cause);
    return {
      modelName: '',
      available: false,
      reason: `读取本机模型状态失败（${error.code}）：${error.message}`,
      providerUrl: null,
    };
  }
}

/** 界面展示用的模型说明（如实说明本机来源与模型名，不外发云端）。 */
export function organizerModelLabel(model: LocalOrganizerModel | null): string {
  if (!model) return '正在读取本机模型状态…';
  if (!model.available) return model.reason ?? DEFAULT_ORGANIZER_UNAVAILABLE_REASON;
  return model.modelName
    ? `使用本机模型 ${model.modelName}${model.providerUrl ? `（${model.providerUrl}）` : ''}`
    : '使用本机默认模型（服务端默认）';
}
