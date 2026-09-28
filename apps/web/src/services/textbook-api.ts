/**
 * 教材目录 / 导入 / 任教范围 / Embedding / 索引代的 /api/v1 客户端（RAG-REBUILD v1.0 · F0-TEXTBOOK）。
 *
 * 视图类型来自冻结契约 `@/contracts/textbook`；请求体与后端
 * `apps/api/app/schemas/textbook.py` 的 StrictModel 一一对应（字段名与长度限制一致，
 * 让「未知字段一律 422」的严格校验在前端就前置暴露）。契约文件未导出的请求体在此
 * 镜像，不修改共享契约。
 *
 * 一律使用相对路径 `/api/v1`（`@/services/api-client` 的 `apiRequest`）：
 * 失败统一抛 `ApiError`，绝不把失败降级为空列表。
 */

import { apiRequest } from '@/services/api-client';
import type {
  DocumentDetail,
  DocumentList,
  DocumentMetadataInput,
  DocumentSummary,
  EmbeddingModelList,
  EmbeddingProfileList,
  EmbeddingProbeRequest,
  EmbeddingProbeView,
  EmbeddingProfileView,
  ImportCreateResponse,
  ImportDraftView,
  IndexStatusView,
  JobList,
  JobView,
  LibraryDetail,
  LibraryKind,
  LibraryList,
  LibrarySummary,
  ScopeCheckView,
  SourceSpanView,
  TextbookSelection,
  TextbookTaxonomy,
  TeachingSettingsView,
} from '@/contracts/textbook';

/* ------------------------------------------------------------------ 请求体（镜像后端 StrictModel） */

export interface LibraryQuery {
  kind?: LibraryKind;
  gradeId?: string;
  subjectId?: string;
  editionId?: string;
  includeDeleted?: boolean;
}

export interface DocumentQuery {
  libraryId?: string;
  gradeId?: string;
  subjectId?: string;
  editionId?: string;
  includeDeleted?: boolean;
}

export interface LibraryCreateRequest {
  kind: LibraryKind;
  displayName: string;
  gradeId?: string | null;
  subjectId: string;
  editionId: string;
}

export interface LibraryPatchRequest {
  expectedRevision: number;
  displayName?: string;
  gradeId?: string | null;
  editionId?: string | null;
}

export interface DocumentPatchRequest {
  expectedRevision: number;
  metadata: DocumentMetadataInput;
  libraryIds: string[];
}

/** 裸实体删除（书册/逻辑库）共用的乐观锁请求体，镜像后端 `DocumentDeleteRequest`。 */
export interface RevisionDeleteRequest {
  expectedRevision: number;
}

export interface ImportPatchRequest {
  expectedRevision: number;
  metadata: DocumentMetadataInput;
}

export interface ImportCommitRequest {
  expectedRevision: number;
  submissionId: string;
  libraryIds: string[];
  acknowledgeWarnings?: boolean;
}

export interface TeachingSettingsUpdateRequest {
  expectedRevision: number;
  selection: TextbookSelection | null;
}

export interface ScopeCheckRequest {
  selection: TextbookSelection;
}

export interface RebuildCreateRequest {
  submissionId: string;
  profileId: string;
}

/* ------------------------------------------------------------------ 查询串与请求辅助 */

/** 拼接查询串：只写有值的键（空串/undefined/null/false 不写），并做 URL 编码。 */
export function textbookQuery(
  params: Record<string, string | number | boolean | undefined | null>,
): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '' || value === false) continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

/**
 * 204 归一：后端对「无返回体的成功」以 204 应答时 `apiRequest` 返回 undefined，
 * 一律归一为 null，避免调用方把 undefined 当数据（乐观锁写入统一走这里）。
 */
async function apiRequestNullable<T>(path: string, init?: RequestInit): Promise<T | null> {
  const value = await apiRequest<T | null | undefined>(path, init);
  return value ?? null;
}

function jsonInit(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  };
}

/* ------------------------------------------------------------------ 字典 */

export function fetchTextbookTaxonomy(signal?: AbortSignal): Promise<TextbookTaxonomy> {
  return apiRequest<TextbookTaxonomy>('/textbook-taxonomy', { signal });
}

/* ------------------------------------------------------------------ 逻辑库 */

export function listLibraries(
  query: LibraryQuery = {},
  signal?: AbortSignal,
): Promise<LibraryList> {
  return apiRequest<LibraryList>(
    `/textbook-libraries${textbookQuery({
      kind: query.kind,
      gradeId: query.gradeId,
      subjectId: query.subjectId,
      editionId: query.editionId,
      includeDeleted: query.includeDeleted,
    })}`,
    { signal },
  );
}

export function getLibrary(id: string, signal?: AbortSignal): Promise<LibraryDetail> {
  return apiRequest<LibraryDetail>(`/textbook-libraries/${encodeURIComponent(id)}`, { signal });
}

export function createLibrary(body: LibraryCreateRequest): Promise<LibrarySummary> {
  return apiRequest<LibrarySummary>('/textbook-libraries', jsonInit('POST', body));
}

/** 返回更新后的库视图；服务端若以 204 应答返回 null（调用方重新读取权威状态）。 */
export function patchLibrary(
  id: string,
  body: LibraryPatchRequest,
): Promise<LibrarySummary | null> {
  return apiRequestNullable<LibrarySummary>(
    `/textbook-libraries/${encodeURIComponent(id)}`,
    jsonInit('PATCH', body),
  );
}

/** 停用逻辑库；服务端若以 204 应答返回 null（调用方重新读取权威状态）。 */
export function deleteLibrary(
  id: string,
  body: RevisionDeleteRequest,
): Promise<LibrarySummary | null> {
  return apiRequestNullable<LibrarySummary>(
    `/textbook-libraries/${encodeURIComponent(id)}`,
    jsonInit('DELETE', body),
  );
}

/* ------------------------------------------------------------------ 书册 */

export function listDocuments(
  query: DocumentQuery = {},
  signal?: AbortSignal,
): Promise<DocumentList> {
  return apiRequest<DocumentList>(
    `/textbooks${textbookQuery({
      libraryId: query.libraryId,
      gradeId: query.gradeId,
      subjectId: query.subjectId,
      editionId: query.editionId,
      includeDeleted: query.includeDeleted,
    })}`,
    { signal },
  );
}

export function getDocument(id: string, signal?: AbortSignal): Promise<DocumentDetail> {
  return apiRequest<DocumentDetail>(`/textbooks/${encodeURIComponent(id)}`, { signal });
}

export function patchDocument(
  id: string,
  body: DocumentPatchRequest,
): Promise<DocumentDetail | null> {
  return apiRequestNullable<DocumentDetail>(
    `/textbooks/${encodeURIComponent(id)}`,
    jsonInit('PATCH', body),
  );
}

export function deleteDocument(
  id: string,
  body: RevisionDeleteRequest,
): Promise<DocumentSummary | null> {
  return apiRequestNullable<DocumentSummary>(
    `/textbooks/${encodeURIComponent(id)}`,
    jsonInit('DELETE', body),
  );
}

/** 受控原文：按不可变修订与半开字符区间读取，返回规范化文本与来源定位。 */
export function getDocumentSource(
  revisionId: string,
  charStart: number,
  charEnd: number,
  signal?: AbortSignal,
): Promise<SourceSpanView> {
  return apiRequest<SourceSpanView>(
    `/textbook-revisions/${encodeURIComponent(revisionId)}/source${textbookQuery({
      charStart,
      charEnd,
    })}`,
    { signal },
  );
}

/* ------------------------------------------------------------------ 导入草稿 */

/**
 * `metadataJson` 部件的信封（F0 v1.1 冻结）：未知字段一律 422，字段名不可漂移。
 * - 省略 `targetDocumentId` = 新增书册；传了 = 更新该书册；
 * - 传 `targetDocumentId` 而不传 `expectedCurrentRevisionId` 时，服务端以该册当前修订为期望值；
 * - `confirmMetadata: true` 表示用户已在表单中确认这批元数据（影响 canCommit）。
 */
export interface ImportMetadataEnvelope {
  metadata?: DocumentMetadataInput;
  targetDocumentId?: string;
  expectedCurrentRevisionId?: string;
  confirmMetadata?: boolean;
}

/**
 * 上传文件创建解析草稿（multipart：`file` + 可选 `metadataJson`）。
 * 信封为空对象时省略 `metadataJson` 部件（仅上传解析，元数据稍后经 PATCH 补）。
 */
export function createImport(
  file: File,
  payload: ImportMetadataEnvelope | null,
  signal?: AbortSignal,
): Promise<ImportCreateResponse> {
  const form = new FormData();
  form.append('file', file);
  if (payload && Object.keys(payload).length > 0) {
    form.append('metadataJson', JSON.stringify(payload));
  }
  // 不手写 content-type：交给 fetch 生成 multipart boundary
  return apiRequest<ImportCreateResponse>('/textbook-imports', {
    method: 'POST',
    body: form,
    signal,
  });
}

export function getImport(id: string, signal?: AbortSignal): Promise<ImportDraftView> {
  return apiRequest<ImportDraftView>(`/textbook-imports/${encodeURIComponent(id)}`, { signal });
}

export function patchImport(id: string, body: ImportPatchRequest): Promise<ImportDraftView | null> {
  return apiRequestNullable<ImportDraftView>(
    `/textbook-imports/${encodeURIComponent(id)}`,
    jsonInit('PATCH', body),
  );
}

/**
 * 提交入库：`POST /textbook-imports/{id}/commit` 直接返回裸 `JobView`（F0 v1.1 冻结）。
 * 草稿的新状态由调用方随后 `GET /textbook-imports/{id}` 读取，不在这里猜造。
 */
export function commitImport(id: string, body: ImportCommitRequest): Promise<JobView> {
  return apiRequest<JobView>(
    `/textbook-imports/${encodeURIComponent(id)}/commit`,
    jsonInit('POST', body),
  );
}

/* ------------------------------------------------------------------ 入库任务 */

export function listJobs(signal?: AbortSignal): Promise<JobList> {
  return apiRequest<JobList>('/textbook-jobs', { signal });
}

export function getJob(id: string, signal?: AbortSignal): Promise<JobView> {
  return apiRequest<JobView>(`/textbook-jobs/${encodeURIComponent(id)}`, { signal });
}

/** 请求取消；返回最新任务视图（服务端若 204 返回 null，调用方重新读取列表）。 */
export function cancelJob(id: string): Promise<JobView | null> {
  return apiRequestNullable<JobView>(`/textbook-jobs/${encodeURIComponent(id)}/cancel`, {
    method: 'POST',
  });
}

export function retryJob(id: string): Promise<JobView | null> {
  return apiRequestNullable<JobView>(`/textbook-jobs/${encodeURIComponent(id)}/retry`, {
    method: 'POST',
  });
}

/* ------------------------------------------------------------------ 任教范围 */

export function getTeachingSettings(signal?: AbortSignal): Promise<TeachingSettingsView> {
  return apiRequest<TeachingSettingsView>('/teaching-settings', { signal });
}

export function putTeachingSettings(
  body: TeachingSettingsUpdateRequest,
): Promise<TeachingSettingsView | null> {
  return apiRequestNullable<TeachingSettingsView>('/teaching-settings', jsonInit('PUT', body));
}

export function checkScope(
  selection: TextbookSelection,
  signal?: AbortSignal,
): Promise<ScopeCheckView> {
  return apiRequest<ScopeCheckView>('/teaching-settings/scope-check', {
    ...jsonInit('POST', { selection }),
    signal,
  });
}

/* ------------------------------------------------------------------ Embedding */

export function listEmbeddingModels(signal?: AbortSignal): Promise<EmbeddingModelList> {
  return apiRequest<EmbeddingModelList>('/embedding-models', { signal });
}

export function probeEmbeddingModel(body: EmbeddingProbeRequest): Promise<EmbeddingProbeView> {
  return apiRequest<EmbeddingProbeView>('/embedding-probes', jsonInit('POST', body));
}

export function listEmbeddingProfiles(signal?: AbortSignal): Promise<EmbeddingProfileList> {
  return apiRequest<EmbeddingProfileList>('/embedding-profiles', { signal });
}

/** 保存配置；服务端若 204 返回 null（调用方重新读取配置列表）。 */
export function createEmbeddingProfile(
  body: EmbeddingProbeRequest,
): Promise<EmbeddingProfileView | null> {
  return apiRequestNullable<EmbeddingProfileView>('/embedding-profiles', jsonInit('POST', body));
}

/* ------------------------------------------------------------------ 索引代 */

export function getIndexStatus(signal?: AbortSignal): Promise<IndexStatusView> {
  return apiRequest<IndexStatusView>('/textbook-index/status', { signal });
}

/** 新建重建任务；返回任务视图（服务端若 204 返回 null，调用方以 getIndexStatus 轮询为准）。 */
export function startRebuild(body: RebuildCreateRequest): Promise<JobView | null> {
  return apiRequestNullable<JobView>('/textbook-index/rebuilds', jsonInit('POST', body));
}
