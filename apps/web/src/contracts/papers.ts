/**
 * 原卷（试卷）契约镜像（TEACHING-LOOP B2 / T40；R5-FE 取回最小子集）。
 *
 * 与后端 `apps/api/app/contracts/papers.py` 逐字段对应（camelCase）；修改任一侧必须同步另一侧。
 * 分值一律十进制字符串（`maxScore` / `totalScore`），整数单位 `*ScoreUnits` = 分数 × 100；
 * 前端格式化只做字符串运算，不做浮点累加。
 *
 * 重建期取回说明（R5-FE 2026-10-11）：本模块只做「试卷管理」页（导入 → 校对确认 → 列表 +
 * AI 知识点分类占比）。**不提供整卷内容阅读器**，因此契约里与内容渲染有关的字段
 * （`PaperItemView.content` / `PaperSourceBlockView.content`）在本模块只用于**原样回传**
 * （草稿 PATCH 必须把服务端给的内容原封不动送回去），界面不渲染题面、图片与公式。
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
  /** 服务端持久化内容快照；本模块只原样回传，不渲染。 */
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
  /** 持久化块内容快照；本模块只用其**结构摘要**（块类型与关键字存在性），不渲染原文。 */
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

/** 试卷知识点占比桶（`GET /papers/{id}/knowledge-distribution` 的元素；C4-3 环状图数据源）。 */
export interface KnowledgeDistributionBucket {
  knowledgePointId: string;
  name: string;
  itemCount: number;
  /** 该知识点小题的满分合计（整数单位 = 分数 × 100）。 */
  totalScoreUnits: number;
  /** 占比（0..1）；服务端无法给出时为 null（界面显示「占比未知」，不自己算）。 */
  scoreRatio: number | null;
}
