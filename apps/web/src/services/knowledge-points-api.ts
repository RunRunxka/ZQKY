/**
 * 知识点库 `/api/v1` 客户端（TEACHING-LOOP B2 · F10-KP）。
 *
 * 视图与请求体类型全部来自冻结契约 `@/contracts/knowledge`（B1），任务视图来自
 * `@/contracts/teaching-loop`；本文件只做路径拼接与 JSON/multipart 编码，
 * **不复制第二份类型**、不改写服务端语义。
 *
 * 一律经 `@/services/api-client` 的相对路径 `/api/v1` 请求：失败统一抛 `ApiError`
 * （含 `details.currentRevision` / `details.issues`），绝不把失败降级为空列表或假成功。
 *
 * 学科字典不在这里：不存在 `/subjects` 接口，学科列表来自
 * `GET /api/v1/textbook-taxonomy`（见 `@/services/textbook-api`）。
 */

import { apiRequest } from '@/services/api-client';
import type {
  KnowledgeImportConfirmRequest,
  KnowledgeImportConfirmResult,
  KnowledgeImportList,
  KnowledgeImportPatchRequest,
  KnowledgeImportView,
  KnowledgePointCreateRequest,
  KnowledgePointList,
  KnowledgePointStatus,
  KnowledgePointUpdateRequest,
  KnowledgePointView,
  KnowledgeSuggestionRequest,
  TextbookLinkCreateRequest,
  TextbookLinkList,
  TextbookLinkView,
} from '@/contracts/knowledge';
import type { JobView } from '@/contracts/teaching-loop';

/* ------------------------------------------------------------------ 查询串与请求辅助 */

/** 拼接查询串：只写有值的键（undefined/null/空串跳过），并做 URL 编码。 */
export function knowledgeQuery(params: Record<string, string | number | undefined | null>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value === undefined || value === null || value === '') continue;
    search.set(key, String(value));
  }
  const text = search.toString();
  return text ? `?${text}` : '';
}

function jsonInit(method: string, body: unknown): RequestInit {
  return {
    method,
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
  };
}

/* ------------------------------------------------------------------ 知识点 */

/** 知识点列表筛选（对应后端 `list_knowledge_points` 的查询参数）。 */
export interface KnowledgePointQuery {
  subjectId?: string;
  status?: KnowledgePointStatus;
  parentId?: string;
  q?: string;
  offset?: number;
  limit?: number;
}

export function listKnowledgePoints(
  query: KnowledgePointQuery = {},
  signal?: AbortSignal,
): Promise<KnowledgePointList> {
  return apiRequest<KnowledgePointList>(
    `/knowledge-points${knowledgeQuery({
      subjectId: query.subjectId,
      status: query.status,
      parentId: query.parentId,
      q: query.q,
      offset: query.offset,
      limit: query.limit,
    })}`,
    { signal },
  );
}

/** 人工建立知识点（201）；同 `(subjectId, code)` 冲突返回 409 `KNOWLEDGE_CODE_CONFLICT`。 */
export function createKnowledgePoint(
  body: KnowledgePointCreateRequest,
): Promise<KnowledgePointView> {
  return apiRequest<KnowledgePointView>('/knowledge-points', jsonInit('POST', body));
}

export function getKnowledgePoint(id: string, signal?: AbortSignal): Promise<KnowledgePointView> {
  return apiRequest<KnowledgePointView>(`/knowledge-points/${encodeURIComponent(id)}`, { signal });
}

/**
 * 更新知识点：`expectedRevision` 是可变实体乐观锁；改名 = 追加修订（返回新的
 * `revisionId`/`version`）。可选字段空白默认不修改，`clearFields` 才明确清空。
 */
export function updateKnowledgePoint(
  id: string,
  body: KnowledgePointUpdateRequest,
): Promise<KnowledgePointView> {
  return apiRequest<KnowledgePointView>(
    `/knowledge-points/${encodeURIComponent(id)}`,
    jsonInit('PATCH', body),
  );
}

/** 归档（保留历史引用；新引用禁选归档）。 */
export function archiveKnowledgePoint(
  id: string,
  expectedRevision: number,
): Promise<KnowledgePointView> {
  return apiRequest<KnowledgePointView>(
    `/knowledge-points/${encodeURIComponent(id)}/archive`,
    jsonInit('POST', { expectedRevision }),
  );
}

export function restoreKnowledgePoint(
  id: string,
  expectedRevision: number,
): Promise<KnowledgePointView> {
  return apiRequest<KnowledgePointView>(
    `/knowledge-points/${encodeURIComponent(id)}/restore`,
    jsonInit('POST', { expectedRevision }),
  );
}

/* ------------------------------------------------------------------ 教材依据 */

export function listTextbookLinks(
  pointId: string,
  signal?: AbortSignal,
): Promise<TextbookLinkList> {
  return apiRequest<TextbookLinkList>(
    `/knowledge-points/${encodeURIComponent(pointId)}/textbook-links`,
    { signal },
  );
}

/** 新增教材依据：区间由服务端向教材目录核验并冻结标题；教材不可用 → 503。 */
export function createTextbookLink(
  pointId: string,
  body: TextbookLinkCreateRequest,
): Promise<TextbookLinkView> {
  return apiRequest<TextbookLinkView>(
    `/knowledge-points/${encodeURIComponent(pointId)}/textbook-links`,
    jsonInit('POST', body),
  );
}

/** 删除教材依据（204 无返回体）；`expectedRevision` 走查询参数。 */
export function deleteTextbookLink(
  pointId: string,
  linkId: string,
  expectedRevision: number,
): Promise<void> {
  return apiRequest<void>(
    `/knowledge-points/${encodeURIComponent(pointId)}/textbook-links/${encodeURIComponent(
      linkId,
    )}${knowledgeQuery({ expectedRevision })}`,
    { method: 'DELETE' },
  );
}

/* ------------------------------------------------------------------ 表格导入 */

export interface KnowledgeImportCreateMeta {
  subjectId: string;
  /** 表头映射（字段名 → 表头）；缺省由服务端自动映射。 */
  mapping?: Record<string, string> | null;
  /** 多工作表 XLSX 指定工作表名；缺省用第一个。 */
  sheetName?: string | null;
}

/**
 * 上传表格（.xlsx / .csv）创建待校对批次（multipart）。
 * 不手写 content-type，交给 fetch 生成 multipart boundary。
 */
export function createKnowledgeImport(
  file: File,
  meta: KnowledgeImportCreateMeta,
  signal?: AbortSignal,
): Promise<KnowledgeImportView> {
  const form = new FormData();
  form.append('file', file);
  form.append('subjectId', meta.subjectId);
  if (meta.mapping && Object.keys(meta.mapping).length > 0) {
    form.append('mappingJson', JSON.stringify(meta.mapping));
  }
  if (meta.sheetName) form.append('sheetName', meta.sheetName);
  return apiRequest<KnowledgeImportView>('/knowledge-imports', {
    method: 'POST',
    body: form,
    signal,
  });
}

export interface KnowledgeImportQuery {
  state?: string;
  offset?: number;
  limit?: number;
}

export function listKnowledgeImports(
  query: KnowledgeImportQuery = {},
  signal?: AbortSignal,
): Promise<KnowledgeImportList> {
  return apiRequest<KnowledgeImportList>(
    `/knowledge-imports${knowledgeQuery({
      state: query.state,
      offset: query.offset,
      limit: query.limit,
    })}`,
    { signal },
  );
}

export function getKnowledgeImport(id: string, signal?: AbortSignal): Promise<KnowledgeImportView> {
  return apiRequest<KnowledgeImportView>(`/knowledge-imports/${encodeURIComponent(id)}`, {
    signal,
  });
}

/** 改映射 / 行处理动作（`expectedRevision` 乐观锁；返回重算后的权威批次视图）。 */
export function patchKnowledgeImport(
  id: string,
  body: KnowledgeImportPatchRequest,
): Promise<KnowledgeImportView> {
  return apiRequest<KnowledgeImportView>(
    `/knowledge-imports/${encodeURIComponent(id)}`,
    jsonInit('PATCH', body),
  );
}

/**
 * 整批确认（幂等 `submissionId`）：同 `submissionId` 同载荷重放返回原结果
 * （`replayed: true`，不重复写入）。
 */
export function confirmKnowledgeImport(
  id: string,
  body: KnowledgeImportConfirmRequest,
): Promise<KnowledgeImportConfirmResult> {
  return apiRequest<KnowledgeImportConfirmResult>(
    `/knowledge-imports/${encodeURIComponent(id)}/confirm`,
    jsonInit('POST', body),
  );
}

/* ------------------------------------------------------------------ AI 候选 */

/**
 * 发起知识点 AI 候选（202 只代表任务被接受）。
 *
 * - `modelProfileId` 必须是**当前聊天模型的 profile id**（点击那一刻冻结）；
 * - 至少一份证据（`materials` 或 `textbookEvidence`），否则 422
 *   `KNOWLEDGE_SUGGESTION_NO_EVIDENCE`；
 * - 任务状态经 `@/services/workflow-jobs-api` 的 `observeJob('knowledge', …)` 观察，
 *   成功结果的 `result.importId` 指向 `source="ai"` 的待确认批次。
 */
export function createKnowledgeSuggestionJob(body: KnowledgeSuggestionRequest): Promise<JobView> {
  return apiRequest<JobView>('/knowledge-suggestion-jobs', jsonInit('POST', body));
}
