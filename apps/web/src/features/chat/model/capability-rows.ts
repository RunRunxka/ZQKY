/**
 * 「对话能力边界」行状态推导（F1-CHAT v1.1 · 修复 A1 r1 D6）。
 *
 * 背景：面板原先把「教材检索（RAG）与来源引用」硬编码为「规划中」，而本批 RAG 已是
 * 真实实现（`/api/v1/rag/*` v2 + 真实 Qdrant/bge-m3/本地概括），文案与实现矛盾。
 *
 * 本模块把每一行改为**由真实接口状态驱动**：
 * - `/capabilities` 的 `feature` 项（`status`/`detail`）表示「工程实现与装配」；
 * - `/rag/status` 的分项（`retrieval/summarization/sourceAccess/scope`）表示「此刻能否用」。
 *
 * 底线（不夸大、不猜造）：
 * - 读取失败 → 「状态未知 / 读取失败（可重试）」，**不回落成「规划中」或「可用」**；
 * - `retrieval.available=false` 时绝不显示为可用，必须给出原因；
 * - 即使检索可用，也始终保留「人工教学质量尚未验收」的口径（后端 `humanQuality`）。
 */

import type { ApiCapability } from '@/contracts/api';
import type { RagServiceStatus } from './rag-service';

export type CapabilityTone = 'ok' | 'warn' | 'muted';

export interface CapabilityRowView {
  key: string;
  name: string;
  badge: string;
  tone: CapabilityTone;
  /** 逐条如实说明（分项原因 / 质量口径 / 后端说明），不做结论性夸大 */
  details: string[];
  /** 读取失败或无法判定时给出重试入口 */
  retry?: boolean;
}

export interface CapabilityRowInput {
  /** `/capabilities` 按 feature 索引；读取失败或未完成时为 null */
  features: Record<string, ApiCapability> | null;
  /** 归一后的 `/rag/status`；读取失败或未完成时为 null */
  rag: RagServiceStatus | null;
  capsError: string | null;
  ragError: string | null;
}

export const RAG_CAPABILITY_FEATURE = 'rag';
export const RAG_ROW_NAME = '教材检索（RAG）与来源引用';
/** 前端实际门控：真实问答未接入文件解析/上传通道（无对应接口可判定） */
export const ATTACHMENT_ROW_NAME = '附件与图片解析';

const STATUS_UNKNOWN = '状态未知';

function sectionText(label: string, ok: boolean, reason: string | null, okSuffix = ''): string {
  return ok ? `${label}：可用${okSuffix}` : `${label}：不可用（${reason ?? '原因未报告'}）`;
}

/** 人工教学质量口径：`not_run`/缺失都如实说「尚未验收」，不写「已验收」 */
export function humanQualityText(humanQuality?: string): string {
  const value = (humanQuality ?? '').trim();
  if (!value || value === 'not_run') return '人工教学质量：尚未验收';
  return `人工教学质量：${value}`;
}

/** 教材检索（RAG）与来源引用：状态来自两个真实接口，永不显示「规划中」 */
export function ragRow(input: CapabilityRowInput): CapabilityRowView {
  const base = { key: RAG_CAPABILITY_FEATURE, name: RAG_ROW_NAME };
  const failure = input.ragError ?? input.capsError;
  if (failure)
    return {
      ...base,
      badge: STATUS_UNKNOWN,
      tone: 'warn',
      details: [
        `读取失败：${failure}`,
        '未取到真实状态时不做就绪判断；请点“重新读取状态”重试。',
      ],
      retry: true,
    };
  if (!input.features || !input.rag)
    // 尚未取到结果（在途）：不给结论，也不冒充「状态未知」
    return {
      ...base,
      badge: '读取中…',
      tone: 'muted',
      details: ['正在读取能力状态…'],
    };
  const cap = input.features[RAG_CAPABILITY_FEATURE];
  if (!cap)
    return {
      ...base,
      badge: STATUS_UNKNOWN,
      tone: 'warn',
      details: ['能力清单未报告 rag 项，无法判定工程实现状态。'],
      retry: true,
    };
  const rag = input.rag;
  const details = [
    sectionText(
      '检索',
      rag.retrieval.available,
      rag.retrieval.reason,
      rag.retrieval.vectorStore && rag.retrieval.queryEmbedding ? '（向量 + 词法）' : '',
    ),
    sectionText(
      '本地概括',
      rag.summarization.available,
      rag.summarization.reason,
      rag.summarization.model ? `（${rag.summarization.model}）` : '',
    ),
    sectionText(
      '原文访问',
      rag.sourceAccess.available,
      rag.sourceAccess.reason,
      rag.sourceAccess.verifiesHash ? '（核验规范化文本散列）' : '',
    ),
    rag.scope.ready
      ? '任教范围：已就绪'
      : `任教范围：未就绪（${rag.scope.reason ?? '尚未保存任教范围'}）`,
    humanQualityText(rag.humanQuality),
  ];
  let badge: string;
  let tone: CapabilityTone;
  if (cap.status === 'planned') {
    badge = '后端报告未实现';
    tone = 'warn';
  } else if (!rag.retrieval.available) {
    badge = '已实现 · 检索不可用';
    tone = 'warn';
  } else if (!rag.scope.ready) {
    badge = '已实现 · 范围未就绪';
    tone = 'warn';
  } else if (cap.status !== 'ready') {
    badge = '已实现 · 当前不可用';
    tone = 'warn';
  } else if (!rag.summarization.available || !rag.sourceAccess.available) {
    badge = '已实现 · 部分不可用';
    tone = 'warn';
  } else {
    badge = '已实现 · 就绪';
    tone = 'ok';
  }
  if (cap.status !== 'ready' && cap.detail) details.push(`后端说明：${cap.detail}`);
  return { ...base, badge, tone, details };
}

/** 其它条目：能从 `/capabilities` 判定就按接口状态显示，判定不了才说状态未知 */
function capabilityRow(
  key: string,
  name: string,
  input: CapabilityRowInput,
): CapabilityRowView {
  const base = { key, name };
  if (input.capsError)
    return {
      ...base,
      badge: STATUS_UNKNOWN,
      tone: 'warn',
      details: [`读取失败：${input.capsError}`, '未取到能力清单时不做就绪判断。'],
      retry: true,
    };
  if (!input.features)
    return { ...base, badge: '读取中…', tone: 'muted', details: ['正在读取能力状态…'] };
  const cap = input.features[key];
  if (!cap)
    return {
      ...base,
      badge: STATUS_UNKNOWN,
      tone: 'warn',
      details: ['能力清单未报告该项，无法判定。'],
      retry: true,
    };
  const map: Record<string, { badge: string; tone: CapabilityTone }> = {
    ready: { badge: '已接入', tone: 'ok' },
    // 后端枚举 planned：如实显示「未接入」并附后端说明，不写「已实现」
    planned: { badge: '未接入', tone: 'muted' },
    unconfigured: { badge: '未配置', tone: 'warn' },
    unavailable: { badge: '当前不可用', tone: 'warn' },
  };
  const view = map[cap.status] ?? { badge: STATUS_UNKNOWN, tone: 'warn' };
  return { ...base, ...view, details: cap.detail ? [cap.detail] : [] };
}

/** 面板行（顺序对照原列表）：RAG → 附件 → MCP → Skills */
export function buildCapabilityRows(input: CapabilityRowInput): CapabilityRowView[] {
  return [
    ragRow(input),
    {
      key: 'attachments',
      name: ATTACHMENT_ROW_NAME,
      badge: '暂未接入',
      tone: 'muted',
      details: [
        '当前真实问答未接入文件解析/上传通道：添加附件后发送会被阻断并保留内容（不静默剥离、不伪装解析成功）。',
      ],
    },
    capabilityRow('mcp', 'MCP 工具调用', input),
    capabilityRow('skills', 'Skills 技能', input),
  ];
}
