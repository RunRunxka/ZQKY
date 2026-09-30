/**
 * 知识点库 v1 契约镜像（TEACHING-LOOP B1 / T20）。
 *
 * 与后端 `apps/api/app/contracts/knowledge.py` 逐字段对应（camelCase）；
 * 修改任一侧必须同步另一侧。B1 不新增页面，本文件只维护类型单一来源。
 */

import type { ErrorIssue } from '@/contracts/api';
import type { AssetRef } from '@/contracts/teaching-loop';

export type KnowledgePointStatus = 'active' | 'archived';
export type KnowledgeImportState = 'uploaded' | 'reviewing' | 'confirmed' | 'failed' | 'cancelled';
export type KnowledgeImportSource = 'file' | 'ai';
export type KnowledgeRowAction = 'create' | 'update' | 'ignore';
export type KnowledgeLinkSource = 'human' | 'ai_confirmed';

export interface KnowledgePointView {
  id: string;
  subjectId: string;
  code: string;
  name: string;
  description: string;
  parentId: string | null;
  parentCode: string | null;
  sortOrder: number;
  status: KnowledgePointStatus;
  /** 乐观锁（可变实体编辑版本） */
  revision: number;
  /** 固定内容修订身份（不可变） */
  revisionId: string | null;
  version: number;
  aliases: string[];
  createdAt: string;
}

export interface KnowledgePointList {
  items: KnowledgePointView[];
  total: number;
  offset: number;
  limit: number;
}

export interface KnowledgePointCreateRequest {
  subjectId: string;
  code: string;
  name: string;
  description?: string;
  parentId?: string | null;
  parentCode?: string | null;
  sortOrder?: number;
  aliases?: string[];
}

export interface KnowledgePointUpdateRequest {
  expectedRevision: number;
  name?: string | null;
  description?: string | null;
  parentId?: string | null;
  parentCode?: string | null;
  sortOrder?: number | null;
  aliases?: string[] | null;
  /** 明确清空（description / parentId / aliases）；空白默认不修改 */
  clearFields?: Array<'description' | 'parentId' | 'aliases'>;
}

export interface KnowledgeImportRowView {
  rowNo: number;
  name: string;
  code: string;
  parentCode: string | null;
  description: string;
  aliases: string[];
  targetKnowledgePointId: string | null;
  baseRevision: number | null;
  baseVersion: number | null;
  decision: KnowledgeRowAction | null;
  issues: ErrorIssue[];
}

export interface KnowledgeImportView {
  importId: string;
  source: KnowledgeImportSource;
  subjectId: string;
  state: KnowledgeImportState;
  revision: number;
  fileAsset: AssetRef;
  headers: string[];
  mapping: Record<string, string>;
  warnings: string[];
  issues: ErrorIssue[];
  rows: KnowledgeImportRowView[];
  createdAt: string;
  updatedAt: string;
}

export interface KnowledgeImportSummary {
  importId: string;
  source: KnowledgeImportSource;
  subjectId: string;
  state: KnowledgeImportState;
  revision: number;
  rowCount: number;
  blockingIssueCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface KnowledgeImportList {
  items: KnowledgeImportSummary[];
  total: number;
  offset: number;
  limit: number;
}

export interface KnowledgeImportRowPatch {
  rowNo: number;
  decision: KnowledgeRowAction;
  expectedRevision?: number | null;
}

export interface KnowledgeImportPatchRequest {
  expectedRevision: number;
  mapping?: Record<string, string> | null;
  rows?: KnowledgeImportRowPatch[] | null;
}

export interface KnowledgeImportConfirmRequest {
  expectedRevision: number;
  submissionId: string;
  actions?: KnowledgeImportRowPatch[] | null;
}

export interface KnowledgeAppliedRow {
  rowNo: number;
  knowledgePointId: string;
  revisionId: string;
  version: number;
}

export interface KnowledgeImportConfirmResult {
  importId: string;
  state: KnowledgeImportState;
  created: KnowledgeAppliedRow[];
  updated: KnowledgeAppliedRow[];
  ignored: number[];
  replayed: boolean;
}

export interface TextbookEvidenceInput {
  documentRevisionId: string;
  charStart: number;
  charEnd: number;
}

export interface TextbookLinkCreateRequest {
  expectedRevision: number;
  documentRevisionId: string;
  charStart: number;
  charEnd: number;
  source?: KnowledgeLinkSource;
}

export interface TextbookLinkView {
  linkId: string;
  knowledgePointId: string;
  knowledgeRevisionId: string;
  documentRevisionId: string;
  charStart: number;
  charEnd: number;
  titleSnapshot: string;
  locatorHash: string;
  source: KnowledgeLinkSource;
  createdAt: string;
}

export interface TextbookLinkList {
  items: TextbookLinkView[];
}

export interface KnowledgeMaterialInput {
  id: string;
  text: string;
}

export interface KnowledgeSuggestionRequest {
  modelProfileId: string;
  subjectId: string;
  materials?: KnowledgeMaterialInput[];
  textbookEvidence?: TextbookEvidenceInput[];
  instructions?: string | null;
}

export interface KnowledgeSuggestionCandidate {
  code: string;
  name: string;
  description: string;
  parentCode: string | null;
  aliases: string[];
  existingKnowledgePointId: string | null;
  evidenceIds: string[];
}

/** 导入表字段（表头映射只允许这六个） */
export const KNOWLEDGE_IMPORT_FIELDS = [
  'subjectCode',
  'code',
  'name',
  'description',
  'parentCode',
  'aliases',
] as const;
