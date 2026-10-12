/**
 * 「AI 候选」使用的**当前聊天模型**（与题库页 `features/question-bank/model-profile.ts`
 * 同一套冻结语义，本模块只做知识点侧的文案与类型，不改成共享契约）：
 *
 * - `KnowledgeSuggestionRequest.modelProfileId` = 当前聊天模型的 profile id（如 `p-chat-1`），
 *   不是模型名；后端经共享 `resolve_chat_model` 解析，失败给可读错误；
 * - 来源：`GET /api/v1/model-catalog` 的 `profiles` 与 `defaultChatProfileId`
 *   （与 /chat 的 `store.modelProfileId ?? catalog.defaultChatProfileId` 同源）；
 * - 判定可调用与后端闸门一致：连接 `callable`（缺凭证的云连接为 false，本机免 Key 为 true）；
 * - 已显式选择但模型失效 → 返回可读修复原因，**绝不在前端另选一个模型顶上**。
 *
 * 只读 `/model-catalog`，不调用模型。
 */

import type { ModelCatalog, ModelProfileView } from '@/contracts/model-settings';

export interface SuggestionChatModel {
  /** 冻结进请求体的 profile id；不可用时为空串。 */
  profileId: string;
  /** 展示用模型名（`显示名 · 模型 id`）；不可用时为空串。 */
  modelLabel: string;
  available: boolean;
  reason: string | null;
  /** 请求体会离开本机 → 界面必须标注数据外发。 */
  cloud: boolean;
}

/** 云模型的额外标注（知识点候选发送的是教师提供的资料文本）。 */
export const SUGGESTION_CLOUD_NOTICE = '将资料文本发送至该模型服务';

export const SUGGESTION_MODEL_LOADING = '正在读取聊天模型配置…';

export const SUGGESTION_NO_DEFAULT_REASON =
  '聊天配置还没有默认模型：请到「模型设置」选择默认问答模型后再生成候选。';

/** 读取目录失败时的可读原因（保留错误码，不把失败当空目录）。 */
export function suggestionCatalogErrorReason(code: string, message: string): string {
  return `读取模型配置失败（${code}）：${message}`;
}

export function unavailableSuggestionModel(reason: string): SuggestionChatModel {
  return { profileId: '', modelLabel: '', available: false, reason, cloud: false };
}

const unavailable = unavailableSuggestionModel;

const LOOPBACK_HOSTS = new Set(['localhost', '127.0.0.1', '0.0.0.0', '::1', '[::1]']);

/** 是否指向本机地址；地址缺失或无法解析按云端处理（宁可多提示一次数据外发）。 */
export function isLoopbackBaseUrl(value: string | null | undefined): boolean {
  if (!value) return false;
  let hostname: string;
  try {
    hostname = new URL(value).hostname.toLowerCase();
  } catch {
    return false;
  }
  return LOOPBACK_HOSTS.has(hostname) || hostname.endsWith('.localhost');
}

function modelLabelOf(profile: ModelProfileView): string {
  return `${profile.displayName} · ${profile.modelId}`;
}

export function resolveSuggestionChatModel(
  catalog: ModelCatalog | null,
  profileId: string | null | undefined,
): SuggestionChatModel {
  if (!catalog) return unavailable(SUGGESTION_MODEL_LOADING);
  const wanted = (profileId ?? '').trim();
  if (!wanted) return unavailable(SUGGESTION_NO_DEFAULT_REASON);

  const profile = catalog.profiles.find((item) => item.id === wanted);
  if (!profile) {
    return unavailable(
      `所选聊天模型配置已不存在（${wanted}）：请到「模型设置」重新选择默认问答模型；不会自动改用其他模型。`,
    );
  }
  if (profile.purpose !== null && profile.purpose !== 'chat') {
    return unavailable(
      `模型「${profile.displayName}」的用途是 ${profile.purpose}，不是聊天：请到「模型设置」改选聊天模型；不会自动改用其他模型。`,
    );
  }
  const connection = catalog.connections.find((item) => item.id === profile.connectionId) ?? null;
  const callable = connection ? connection.callable : profile.connection?.hasCredential === true;
  if (!callable) {
    const why = connection?.callableReason?.trim();
    return unavailable(
      `聊天模型「${modelLabelOf(profile)}」当前不可调用${why ? `（${why}）` : ''}：请到「模型设置」修复该连接；不会自动改用其他模型。`,
    );
  }
  return {
    profileId: profile.id,
    modelLabel: modelLabelOf(profile),
    available: true,
    reason: null,
    cloud: !isLoopbackBaseUrl(connection?.resolvedBaseUrl),
  };
}

/** 当前有效聊天模型 = 聊天配置的默认模型；未配置时不猜造候选。 */
export function pickSuggestionChatModel(catalog: ModelCatalog | null): SuggestionChatModel {
  return resolveSuggestionChatModel(catalog, catalog?.defaultChatProfileId ?? '');
}
