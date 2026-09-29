/**
 * 「AI 整理」使用的**当前聊天模型**（RAG-QUALITY v1.1：语义改回聊天模型，本地或云端一视同仁）。
 *
 * 契约（总控冻结，后端 B3 同步）：
 * - `OrganizeRequest.modelProfileId` = **当前聊天模型的 profile id**（如 `p-chat-1`），
 *   不是模型名、不是本机 Ollama 模型名；后端经共享 `resolve_chat_model` 解析，
 *   解析失败给可读错误。
 * - 来源与 `/chat` 同一处：`GET /api/v1/model-catalog` 的 `profiles` 与 `defaultChatProfileId`
 *   （`features/chat/ChatWorkspace.tsx` 的选择规则是
 *   `store.modelProfileId ?? catalog.defaultChatProfileId`；题库页没有会话上下文，
 *   因此取聊天配置的默认模型）。
 * - 判定「可调用」与后端闸门一致：连接 `callable`（缺凭证的云连接为 false，本机免 Key 服务为
 *   true）；连接视图缺失时退回与 `/chat` 相同的 `connection.hasCredential`。
 * - 已显式选择但模型失效（profile 不存在 / 连接不可调用）→ 返回可读修复原因，
 *   **绝不在前端另选一个模型顶上**。
 *
 * 本模块不做任何请求副作用以外的写入：只读 `/model-catalog`，不调用模型。
 */

import type { ModelCatalog, ModelProfileView } from '@/contracts/model-settings';

/** 可在按钮附近展示的模型说明；`available` 为假时界面必须禁用「AI 整理草稿」。 */
export interface OrganizerChatModel {
  /** 冻结进 `OrganizeRequest.modelProfileId` 的聊天模型 profile id；不可用时为空串。 */
  profileId: string;
  /** 展示用模型名（与 /chat 一致：`显示名 · 模型 id`）；不可用时为空串。 */
  modelLabel: string;
  available: boolean;
  /** 不可用原因（可读中文，含修复动作）；可用时为 null。 */
  reason: string | null;
  /** 请求体会离开本机（模型地址不是回环地址，或地址未知）→ 界面必须标注数据外发。 */
  cloud: boolean;
}

/** 云模型的额外标注（任务卡要求逐字出现）。 */
export const ORGANIZER_CLOUD_NOTICE = '将所选题目文本发送至该模型服务';

export const ORGANIZER_MODEL_LOADING = '正在读取聊天模型配置…';

export const ORGANIZER_NO_DEFAULT_REASON =
  '聊天配置还没有默认模型：请到「模型设置」选择默认问答模型后再整理。';

/** 读取目录失败时的可读原因（保留错误码，不把失败当空目录）。 */
export function organizerCatalogErrorReason(code: string, message: string): string {
  return `读取模型配置失败（${code}）：${message}`;
}

/** 不可用态（读取失败 / 无默认模型 / 连接不可调用）；界面据此禁用入口并展示原因。 */
export function unavailableOrganizerModel(reason: string): OrganizerChatModel {
  return { profileId: '', modelLabel: '', available: false, reason, cloud: false };
}

const unavailable = unavailableOrganizerModel;

const LOOPBACK_HOSTS = new Set(['localhost', '127.0.0.1', '0.0.0.0', '::1', '[::1]']);

/**
 * 是否指向本机地址。地址缺失或无法解析时返回 false（按云端处理）：
 * 提示「文本会发送到模型服务」总比漏报一次数据外发安全。
 */
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

/**
 * 按指定 profile id 解析可用的聊天模型；`profileId` 为空表示「没有显式选择与默认模型」。
 * 只消化冻结契约的目录数据，不猜模型名、不做默认回退。
 */
export function resolveOrganizerChatModel(
  catalog: ModelCatalog | null,
  profileId: string | null | undefined,
): OrganizerChatModel {
  if (!catalog) return unavailable(ORGANIZER_MODEL_LOADING);
  const wanted = (profileId ?? '').trim();
  if (!wanted) return unavailable(ORGANIZER_NO_DEFAULT_REASON);

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
    // 以运行期实际地址判定是否离开本机（与后端发起调用用的地址同源）
    cloud: !isLoopbackBaseUrl(connection?.resolvedBaseUrl),
  };
}

/**
 * 当前有效聊天模型 = 聊天配置的默认模型（`defaultChatProfileId`）。
 * 未配置默认模型时不猜造候选（与 /chat 的 blocked 语义一致）。
 */
export function pickOrganizerChatModel(catalog: ModelCatalog | null): OrganizerChatModel {
  return resolveOrganizerChatModel(catalog, catalog?.defaultChatProfileId ?? '');
}
