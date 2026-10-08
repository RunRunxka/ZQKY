/**
 * 原卷 v1 契约镜像（TEACHING-LOOP B2 / T40）。
 *
 * 与后端 `apps/api/app/contracts/papers.py` 逐字段对应（camelCase）；
 * 修改任一侧必须同步另一侧。分值一律十进制字符串（服务端转 ×100 整数单位）。
 */

import type { ErrorIssue } from '@/contracts/api';

export type PaperStatus = 'active' | 'archived';
export type PaperRevisionState = 'draft' | 'confirmed';
export type PaperKnowledgeRole = 'primary' | 'secondary';
export type PaperKnowledgeSource = 'human' | 'ai_confirmed' | 'bank_confirmed';
export type PaperBlockKind = 'paragraph' | 'table' | 'formula' | 'image' | 'unknown';
export type PaperBlockDisposition = 'item' | 'shared_material' | 'excluded' | 'unassigned';
export type PaperIssueSeverity = 'info' | 'warning' | 'blocking';
export type PaperIssueStatus = 'open' | 'resolved' | 'excluded';
export type ProposalState = 'pending' | 'applied' | 'rejected' | 'stale';

export interface PaperItemKnowledgeInput {
  knowledgePointId: string;
  role?: PaperKnowledgeRole;
}

export interface PaperItemInput {
  itemId?: string | null;
  parentItemId?: string | null;
  questionNo: string;
  ordinal: number;
  isScored: boolean;
  /** 十进制字符串（最多两位小数）；isScored=true 时必填 */
  maxScore?: string | null;
  content?: Record<string, unknown>;
  sourceLocator?: Record<string, unknown>;
  knowledge?: PaperItemKnowledgeInput[];
}

export interface PaperBlockPatch {
  blockId: string;
  disposition: PaperBlockDisposition;
  itemId?: string | null;
  excludeReason?: string | null;
}

/** 内容损失类问题（必须"补录"后才能解决，不能仅以排除放行） */
export const CONTENT_LOSS_ISSUE_CODES: readonly string[] = [
  'UNSUPPORTED_OBJECT',
  'RICH_IMAGE_UNSUPPORTED',
  'FORMULA_CONVERSION_FAILED',
  'DOCUMENT_PARSE_FAILED',
  'CONTENT_LOSS',
];

/** 结构化问题处置（B3/G0）：补录必须写进目标块；排除仅限非内容损失且需理由。 */
export interface PaperIssueResolution {
  kind: 'supplement_text' | 'supplement_asset' | 'exclude';
  targetBlockId?: string | null;
  text?: string | null;
  assetId?: string | null;
  reason?: string | null;
}

export interface PaperIssuePatch {
  issueId: string;
  status: PaperIssueStatus;
  resolution?: PaperIssueResolution | null;
}

export interface PaperDraftPatchRequest {
  expectedRevision: number;
  title?: string | null;
  items?: PaperItemInput[] | null;
  blocks?: PaperBlockPatch[] | null;
  issues?: PaperIssuePatch[] | null;
}

export interface PaperConfirmRequest {
  expectedRevision: number;
  submissionId: string;
}

/** 原卷归档/恢复（对应后端 `PaperRevisionRequest`：只带乐观锁修订号，不携带内容）。 */
export interface PaperRevisionRequest {
  expectedRevision: number;
}

export interface PaperProposalJobRequest {
  modelProfileId: string;
  expectedRevision: number;
}

export interface PaperProposalSelection {
  itemId: string;
  knowledgePointId: string;
}

export interface PaperProposalDecisionRequest {
  expectedRevision: number;
  selections?: PaperProposalSelection[];
}

export interface PaperItemKnowledgeView {
  knowledgePointId: string;
  knowledgeRevisionId: string;
  knowledgeNameSnapshot: string;
  role: PaperKnowledgeRole;
  source: PaperKnowledgeSource;
}

export interface PaperItemView {
  itemId: string;
  parentItemId: string | null;
  questionNo: string;
  ordinal: number;
  isScored: boolean;
  maxScoreUnits: number | null;
  maxScore: string | null;
  content: Record<string, unknown>;
  sourceLocator: Record<string, unknown>;
  knowledge: PaperItemKnowledgeView[];
}

export interface PaperSourceBlockView {
  blockId: string;
  ordinal: number;
  kind: PaperBlockKind;
  locator: Record<string, unknown>;
  disposition: PaperBlockDisposition;
  itemId: string | null;
  excludeReason: string | null;
  /** 持久化块内容快照；图片块含受管 assetId，字节经受控资产内容接口读取 */
  content: Record<string, unknown>;
}

export interface PaperIssueView {
  issueId: string;
  code: string;
  severity: PaperIssueSeverity;
  message: string;
  blockId: string | null;
  locator: Record<string, unknown>;
  status: PaperIssueStatus;
  resolution: Record<string, unknown> | null;
}

export interface PaperRevisionContentView {
  paperId: string;
  paperRevisionId: string;
  version: number;
  state: PaperRevisionState;
  subjectId: string;
  title: string;
  totalScoreUnits: number;
  totalScore: string;
  confirmedAt: string | null;
  createdAt: string;
  items: PaperItemView[];
  blocks: PaperSourceBlockView[];
  issues: PaperIssueView[];
}

export interface PaperView {
  paperId: string;
  subjectId: string;
  title: string;
  status: PaperStatus;
  revision: number;
  currentRevisionId: string | null;
  currentState: PaperRevisionState | null;
  version: number;
  totalScoreUnits: number;
  totalScore: string;
  itemCount: number;
  scoredLeafCount: number;
  blockingIssueCount: number;
  createdAt: string;
}

export interface PaperImportView {
  paper: PaperView;
  revision: PaperRevisionContentView;
  warnings: string[];
}

export interface PaperList {
  items: PaperView[];
  total: number;
  offset: number;
  limit: number;
}

export interface PaperConfirmResult {
  paperId: string;
  paperRevisionId: string;
  state: PaperRevisionState;
  totalScoreUnits: number;
  scoredLeafCount: number;
  replayed: boolean;
}

/**
 * 彻底删除原卷回执（200）：物理删除不可恢复。
 * 被施测引用 → 409 `PAPER_IN_USE`（`details.counts.assessments`）；
 * 有已确认修订 → 409 `PAPER_HAS_CONFIRMED_REVISION`（`details.counts.confirmedRevisions`，只能归档）。
 */
export interface PaperDeleteResult {
  deleted: boolean;
  paperId: string;
}

/** 原卷 409 守卫的逐项引用计数（两键不会同时出现；未知键由界面原样列出）。 */
export interface PaperReferenceCounts {
  assessments: number;
  confirmedRevisions: number;
}

export interface PaperProposalItemView {
  itemId: string;
  questionNo: string;
  knowledgePointId: string | null;
  proposedCode: string | null;
  proposedName: string | null;
  evidence: string[];
  ambiguity: boolean;
}

export interface PaperProposalView {
  proposalId: string;
  jobId: string;
  state: ProposalState;
  baseRevision: number;
  stale: boolean;
  items: PaperProposalItemView[];
  issues: ErrorIssue[];
  createdAt: string;
}
