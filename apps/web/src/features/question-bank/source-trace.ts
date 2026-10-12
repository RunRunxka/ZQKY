/**
 * AI 候选来源追溯（TEACHING-LOOP B3 · F10-QB）。
 *
 * 已入库题目的 `sourceImportId` 指向冻结它的导入批次；批次里的草稿带
 * `extractionMethod`（`rule` / `ai` / `manual`）。界面据此**如实**说明本题批次里是否存在
 * AI 候选：AI 候选只可能是 `needs_review` 草稿，经人工校对与确认后才入库
 * （确认闸门由后端保证，前端不声称任何自动入库路径）。
 *
 * 读取失败时不得猜造来源：调用方必须区分「批次里没有 AI 候选」与「读不到批次，无法核对」。
 */

import type { QuestionImportDetail } from '@/contracts/question-bank';

export interface AiSourceTrace {
  /** 批次里 `extractionMethod === 'ai'` 的草稿数；0 = 没有 AI 候选。 */
  aiDraftCount: number;
  draftCount: number;
  /** 批次是否已确认入库（AI 候选必须先经人工确认；不自动入库）。 */
  confirmed: boolean;
}

export function aiSourceTraceOf(detail: QuestionImportDetail): AiSourceTrace {
  const drafts = Array.isArray(detail.drafts) ? detail.drafts : [];
  return {
    aiDraftCount: drafts.filter((draft) => draft.extractionMethod === 'ai').length,
    draftCount: drafts.length,
    confirmed: detail.state === 'confirmed',
  };
}

export function aiSourceTraceText(trace: AiSourceTrace): string {
  if (trace.aiDraftCount === 0) {
    return `该批次没有 AI 来源草稿（共 ${trace.draftCount} 道，均为规则拆题或人工拆分）。`;
  }
  const state = trace.confirmed ? '批次已确认入库' : '批次还未确认入库';
  return `该批次含 ${trace.aiDraftCount}/${trace.draftCount} 道 AI 候选草稿（extractionMethod=ai），${state}；AI 候选只作为待校对草稿，必须人工校对并确认后才成为题目。`;
}

/** 读取批次详情失败时的说明（保留错误码；不把失败当「没有 AI 候选」）。 */
export function aiSourceTraceUnavailableText(code: string, message: string): string {
  return `来源批次详情读取失败（${code}）：无法核对本题是否来自 AI 候选；这不影响题目本身，可稍后重试。${message}`;
}
