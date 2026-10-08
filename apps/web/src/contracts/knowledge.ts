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

/**
 * 知识点列表的教材范围（后端 `list_points(scope=…)`）：
 * `taught` = 任教范围内有教材依据（列表默认口径）；`subject` = 该学科全部教材依据。
 * 缺省（不传）保持旧行为（不过滤）；取值非法由后端 422。
 */
export type KnowledgePointScope = 'taught' | 'subject';

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
  /**
   * 教材依据文档的年级去重集合（后端只读展示字段；老响应/无依据时可能缺省或为空）。
   * 缺省与空数组含义不同：缺省 = 未返回，界面不据此断定「没有年级」。
   */
  gradeIds?: string[];
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
  /** 原始上传文件名（服务端读不到时为 null/缺省；界面回退到短号，不伪造文件名）。 */
  uploadedFileName?: string | null;
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
  /** 原始上传文件名（服务端读不到时为 null/缺省；界面回退到短号，不伪造文件名）。 */
  uploadedFileName?: string | null;
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

/**
 * 放弃未确认知识点批次（对应后端 `KnowledgeImportDiscardRequest`）：
 * 只把状态置 `cancelled`；批次记录、原始文件与预览行保留。
 */
export interface KnowledgeImportDiscardRequest {
  expectedRevision: number;
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

/* ------------------------------------------------------------------ 彻底删除的引用计数 */

/**
 * 知识点彻底删除被拒时 `details.counts` 的单项（后端 `ReferenceCounts.as_details()`）：
 * `library` 是库名（knowledge / teaching / question_bank），`key` 是具体引用表，
 * `count` 是行数。界面只渲染 `count > 0` 的项，逐项给出「为什么不能删」。
 */
export interface KnowledgePointReferenceCount {
  library: string;
  key: string;
  count: number;
}

/* ------------------------------------------------------------------ 从教材提取（AI 候选） */

/** 预览清单里的一本教材：取材范围 + 就绪状态（未就绪书册带 reason，不伪造就绪）。 */
export interface KnowledgeExtractionDocument {
  documentId: string;
  title: string;
  gradeIds: string[];
  /** 当前修订 id（无修订为 null → 必然未就绪）。 */
  revisionId: string | null;
  chunkCount: number;
  approxChars: number;
  /** 当前索引代是否包含该修订（正文分块可作 AI 证据）。 */
  indexReady: boolean;
  /** 未就绪原因（就绪书册为 null）。 */
  reason: string | null;
}

/**
 * `GET /knowledge-extraction/preview?subjectId=` 的响应。
 * 合计字段是**扁平**的（`totalDocuments` / `readyDocuments` / `totalChunks` / `approxChars`），
 * 不是嵌套 `totals` 对象——以后端实现为准。
 */
export interface KnowledgeExtractionPreview {
  subjectId: string;
  documents: KnowledgeExtractionDocument[];
  totalDocuments: number;
  readyDocuments: number;
  totalChunks: number;
  approxChars: number;
}

/** 镜像后端 `KnowledgeExtractionRequest`（严格模型）：每个书册一个 AI 候选任务。 */
export interface KnowledgeExtractionRequest {
  submissionId: string;
  modelProfileId: string;
  subjectId: string;
  /** 缺省 = 该学科全部就绪书册；指定含未就绪书册 → 409 逐册列出，不部分受理。 */
  documentIds?: string[] | null;
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
