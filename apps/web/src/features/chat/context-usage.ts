/**
 * 上下文占用计算：真实用量优先，估算只覆盖「尚未发送」的内容。
 *
 * 参考 Cline / Roo Code / Claude Code 的做法：上下文占用以最近一次 API 返回的
 * input tokens 为基准（供应商已把系统提示、历史、工具结果算进去），而不是把可见文本
 * 重新按字符估算。旧会话没有 usage 时才整体退化为本地估算，并在 UI 明确标注。
 */
import type { ChatMessage } from '@/contracts/chat';

// CJK 统一表意文字 / 扩展 A / 兼容表意文字 / 日文假名 / 韩文
const CJK_CHAR = /[\u3400-\u4DBF\u4E00-\u9FFF\uF900-\uFAFF\u3040-\u30FF\uAC00-\uD7AF]/g;

/**
 * 轻量语言感知估算（DeepSeek 官方口径：中文约 0.6 token/字，英文约 0.3 token/字符）。
 * 仅用于输入框草稿与旧会话兜底；真实请求以供应商返回的 usage 为准。
 */
export function estimateTokens(text: string): number {
  if (!text) return 0;
  const cjk = (text.match(CJK_CHAR) ?? []).length;
  const other = text.length - cjk;
  return Math.ceil(cjk * 0.6 + other * 0.3);
}

export interface ContextUsage {
  /** 当前上下文占用（真实基准 + 之后新增估算 + 草稿估算） */
  usedTokens: number;
  /** provider=至少有一条真实 usage；estimate=全部本地估算 */
  source: 'provider' | 'estimate';
  /** 最近一轮真实请求的输入 tokens；估算模式为 null */
  baselineTokens: number | null;
  /** 基准之后新增消息的估算 tokens */
  tailTokens: number;
  /** 输入框草稿的估算 tokens */
  draftTokens: number;
  /** 基准轮累计输出 tokens */
  outputTokens: number | null;
  /** 基准轮缓存命中输入 tokens */
  cachedInputTokens: number | null;
  /** 作为基准的助手消息 id（用于诊断/测试） */
  baselineMessageId: string | null;
}

function hasRealInput(message: ChatMessage): boolean {
  const value = message.usage?.inputTokens;
  return typeof value === 'number' && Number.isFinite(value) && value > 0;
}

/**
 * 计算当前上下文占用。
 *
 * - 优先找**当前模型**最近一条带真实 `usage.inputTokens` 的助手消息；
 * - `used = 真实输入 + 该消息之后新增消息估算 + 草稿估算`；
 * - 找不到（旧会话/供应商不回 usage/切换了模型）时，整体按可见消息估算。
 */
export function computeContextUsage(
  messages: ChatMessage[],
  draft: string,
  currentProfileId: string | null,
): ContextUsage {
  const draftTokens = estimateTokens(draft);
  let baselineIndex = -1;
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    const message = messages[index]!;
    if (message.role !== 'assistant' || !hasRealInput(message)) continue;
    if (currentProfileId && message.modelProfileId !== currentProfileId) continue;
    baselineIndex = index;
    break;
  }

  if (baselineIndex >= 0) {
    const baseline = messages[baselineIndex]!;
    const tailTokens = messages
      .slice(baselineIndex + 1)
      .reduce((total, message) => total + estimateTokens(message.content), 0);
    const baselineTokens = baseline.usage?.inputTokens ?? null;
    return {
      usedTokens: (baselineTokens ?? 0) + tailTokens + draftTokens,
      source: 'provider',
      baselineTokens,
      tailTokens,
      draftTokens,
      outputTokens: baseline.usage?.outputTokens ?? null,
      cachedInputTokens: baseline.usage?.cachedInputTokens ?? null,
      baselineMessageId: baseline.id,
    };
  }

  const estimated = messages.reduce(
    (total, message) => total + estimateTokens(message.content),
    0,
  );
  return {
    usedTokens: estimated + draftTokens,
    source: 'estimate',
    baselineTokens: null,
    tailTokens: estimated,
    draftTokens,
    outputTokens: null,
    cachedInputTokens: null,
    baselineMessageId: null,
  };
}

export function formatTokenCount(value: number | null | undefined): string {
  if (typeof value !== 'number' || !Number.isFinite(value)) return '—';
  return value.toLocaleString();
}
