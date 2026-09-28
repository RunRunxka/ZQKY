/**
 * 教材 RAG v2 本地类型层（F1-CHAT）。
 *
 * 背景：C0 冻结契约已包含 `contracts/chat.ts`（v1 `RagTurnState`）与
 * `contracts/textbook.ts`，但**尚未**包含 `apps/api/app/schemas/rag_v2.py` 的
 * `ScopeSnapshot / EvidenceRef / TextbookEvidence / RagResultV2`。共享契约由总控独占
 * （本卡禁止修改 `contracts/**`），因此这里在 chat 模块内**逐字段镜像**后端 schema，
 * 并在本文件用模块扩充（declaration merging）为消息补上 v2 落库字段。
 *
 * 边界：
 * - 这里只做「后端已给出的字段」的类型镜像与运行时校验，**不构造快照、不伪造证据**；
 * - 字段名/可空性与 `apps/api/app/schemas/rag_v2.py` 一致；后端若变更需同步本文件；
 * - 扩充的字段全部可选：旧消息缺少时按「无该信息」只读展示，不猜造引用。
 */

import type { AskUserInteraction, ChatMessage } from '@/contracts/chat';
import type { LocatorView, TextbookSelection } from '@/contracts/textbook';

/* ------------------------------------------------------------------ 冻结范围快照 */

export interface ScopeDocument {
  documentId: string;
  documentRevisionId: string;
  metadataRevisionId: string;
}

/** 服务端在定位时冻结的范围事实；客户端只回传，不构造判定。 */
export interface ScopeSnapshot {
  schemaVersion: 2;
  selection: TextbookSelection;
  documents: ScopeDocument[];
  embeddingGenerationId: string;
  scopeHash: string;
}

/* ------------------------------------------------------------------ 证据与结果 */

/** 详解引用（/rag/explain/stream 的最小引用形状）。 */
export interface EvidenceRef {
  evidenceId: string;
  documentRevisionId: string;
  normalizedTextSha256: string;
  charStart: number;
  charEnd: number;
}

/** 教材原文证据（字段与后端 TextbookEvidence 一致，含来源定位）。 */
export interface TextbookEvidence extends EvidenceRef {
  documentId: string;
  title: string;
  editionLabel: string;
  subjectLabel: string;
  chapterPath: string[];
  text: string;
  originalFileSha256: string;
  locator: LocatorView;
  /** 教材已更新：该引用属于历史修订，必须明确标注且不隐藏 */
  isSuperseded: boolean;
}

export type RagPointStatus = 'ok' | 'partial' | 'uncertain' | 'no_evidence';

export interface RagPoint {
  pointId: string;
  title: string;
  summary: string;
  evidenceIds: string[];
}

export interface RagResultV2 {
  contractVersion: 2;
  resultId: string;
  status: RagPointStatus;
  scopeSnapshot: ScopeSnapshot;
  points: RagPoint[];
  evidence: TextbookEvidence[];
  reason?: string | null;
}

/* ------------------------------------------------------------------ 定位请求范围入参 */

export interface RagScopeSelectionInput {
  kind: 'selection';
  selection: TextbookSelection;
}

export interface RagScopeFrozenInput {
  kind: 'frozen';
  snapshot: ScopeSnapshot;
}

export type RagScopeInput = RagScopeSelectionInput | RagScopeFrozenInput;

/* ------------------------------------------------------------------ 详解请求 */

export interface RagExplainHistoryMessage {
  role: 'user' | 'assistant';
  content: string;
}

export interface RagExplainRequest {
  requestId: string;
  sessionId: string;
  turnId: string;
  modelProfileId: string;
  originalQuestion: string;
  followUp: string;
  scopeSnapshot: ScopeSnapshot;
  evidenceRefs: EvidenceRef[];
  history: RagExplainHistoryMessage[];
  maxOutputTokens: number | null;
}

/** 详解轮在消息上的冻结事实（随消息持久化；重试沿用，不因默认模型变化换模型）。 */
export interface RagExplainState {
  turnId: string;
  modelProfileId: string;
  modelLabel: string;
  followUp: string;
  status: 'streaming' | 'done' | 'error' | 'stopped';
  error?: { code: string; message: string; retryable?: boolean };
  originalQuestion: string;
  scopeSnapshot: ScopeSnapshot;
  evidenceRefs: EvidenceRef[];
  history: RagExplainHistoryMessage[];
  maxOutputTokens: number | null;
}

/** 详解引导卡片的本地生命周期（不占用服务端追问等待身份）。 */
export interface RagGuidanceState {
  /** 「忽略」只置此位：不调用 RAG reply/cancel，也不调用 LLM */
  dismissed?: boolean;
  /** 已派发的详解轮次：存在时再次提交 = 重试该轮，不新建 */
  targetTurnId?: string;
}

/* ------------------------------------------------------------------ 契约扩充（仅类型可见，不改共享文件） */

declare module '../../../contracts/chat' {
  interface AskUserDraft {
    /** v2 追问卡作答去向；旧草稿缺省按「未作答」处理 */
    disposition?: 'unanswered' | 'answered' | 'skipped';
  }
  interface AskUserInteraction {
    /** 卡片种类：服务端澄清卡 or 本终态后本地创建的详解引导卡 */
    kind?: 'clarification' | 'guidance';
    guidance?: RagGuidanceState;
  }
  interface ChatMessage {
    /** 本轮定位冻结的范围快照（来自 message.start；刷新后随消息保留） */
    ragScope?: ScopeSnapshot;
    /** 结构化结果（与正文、游标同一次持久化写入） */
    ragResult?: RagResultV2;
    /** 教材证据（等同 ragResult.evidence；独立保存便于历史只读展示） */
    ragEvidence?: TextbookEvidence[];
    /** 详解轮冻结事实（独立轮次，不计入「首次定位＋最多两次澄清」） */
    ragExplain?: RagExplainState;
  }
}

/** 类型占位：让模块扩充在仅类型引用时也被编译（避免 lint 未使用报错）。 */
export type RagAugmentedMessage = ChatMessage;
export type RagAugmentedInteraction = AskUserInteraction;

/* ------------------------------------------------------------------ 运行时校验（事件载荷不可信） */

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((item) => typeof item === 'string');
}

export function isScopeSnapshot(value: unknown): value is ScopeSnapshot {
  if (!isRecord(value)) return false;
  const selection = value.selection;
  return (
    value.schemaVersion === 2 &&
    isRecord(selection) &&
    typeof selection.gradeId === 'string' &&
    typeof selection.subjectId === 'string' &&
    typeof selection.editionId === 'string' &&
    isStringArray(selection.documentIds) &&
    Array.isArray(value.documents) &&
    value.documents.every(
      (doc) =>
        isRecord(doc) &&
        typeof doc.documentId === 'string' &&
        typeof doc.documentRevisionId === 'string' &&
        typeof doc.metadataRevisionId === 'string',
    ) &&
    typeof value.embeddingGenerationId === 'string' &&
    typeof value.scopeHash === 'string'
  );
}

export function isLocatorView(value: unknown): value is LocatorView {
  if (!isRecord(value)) return false;
  const nullable = (item: unknown) => item === null || typeof item === 'number';
  return (
    ['markdown', 'pdf', 'docx'].includes(String(value.kind)) &&
    nullable(value.lineStart) &&
    nullable(value.lineEnd) &&
    nullable(value.pageStart) &&
    nullable(value.pageEnd) &&
    nullable(value.blockStart) &&
    nullable(value.blockEnd)
  );
}

export function isTextbookEvidence(value: unknown): value is TextbookEvidence {
  if (!isRecord(value)) return false;
  return (
    typeof value.evidenceId === 'string' &&
    typeof value.documentRevisionId === 'string' &&
    typeof value.normalizedTextSha256 === 'string' &&
    typeof value.charStart === 'number' &&
    typeof value.charEnd === 'number' &&
    typeof value.documentId === 'string' &&
    typeof value.title === 'string' &&
    typeof value.editionLabel === 'string' &&
    typeof value.subjectLabel === 'string' &&
    isStringArray(value.chapterPath) &&
    typeof value.text === 'string' &&
    typeof value.originalFileSha256 === 'string' &&
    isLocatorView(value.locator) &&
    typeof value.isSuperseded === 'boolean'
  );
}

export function isRagResultV2(value: unknown): value is RagResultV2 {
  if (!isRecord(value)) return false;
  return (
    value.contractVersion === 2 &&
    typeof value.resultId === 'string' &&
    ['ok', 'partial', 'uncertain', 'no_evidence'].includes(String(value.status)) &&
    isScopeSnapshot(value.scopeSnapshot) &&
    Array.isArray(value.points) &&
    value.points.every(
      (point) =>
        isRecord(point) &&
        typeof point.pointId === 'string' &&
        typeof point.title === 'string' &&
        typeof point.summary === 'string' &&
        isStringArray(point.evidenceIds),
    ) &&
    Array.isArray(value.evidence) &&
    value.evidence.every(isTextbookEvidence) &&
    (value.reason === undefined || value.reason === null || typeof value.reason === 'string')
  );
}

/** 证据 → 详解引用（1..20 条，逐条来自后端已核验证据，不补造定位）。 */
export function toEvidenceRefs(evidence: TextbookEvidence[], limit = 20): EvidenceRef[] {
  return evidence.slice(0, limit).map((item) => ({
    evidenceId: item.evidenceId,
    documentRevisionId: item.documentRevisionId,
    normalizedTextSha256: item.normalizedTextSha256,
    charStart: item.charStart,
    charEnd: item.charEnd,
  }));
}

/** locator 的可读定位（markdown 行号 / pdf 页码 / docx 段落）；无编号时如实返回空。 */
export function locatorLabel(locator: LocatorView | undefined): string {
  if (!locator) return '';
  if (locator.kind === 'markdown' && locator.lineStart !== null && locator.lineEnd !== null)
    return `第 ${locator.lineStart}–${locator.lineEnd} 行`;
  if (locator.kind === 'pdf' && locator.pageStart !== null && locator.pageEnd !== null)
    return `第 ${locator.pageStart}–${locator.pageEnd} 页`;
  if (locator.kind === 'docx' && locator.blockStart !== null && locator.blockEnd !== null)
    return `第 ${locator.blockStart}–${locator.blockEnd} 段`;
  return '';
}

/** 结果状态文案（不把部分概括说成完整结论）。 */
export const RAG_RESULT_STATUS_LABEL: Record<RagPointStatus, string> = {
  ok: '已定位',
  partial: '已定位（本地概括未完成）',
  uncertain: '证据不确定',
  no_evidence: '证据不足',
};
