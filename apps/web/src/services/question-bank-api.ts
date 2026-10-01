/**
 * 独立题库 /api/v1 客户端（RAG-REBUILD v1.0 · F2-QBANK）。
 *
 * 视图类型全部来自冻结契约 `@/contracts/question-bank`；请求体镜像后端
 * `apps/api/app/schemas/question_bank.py` 的 StrictModel（字段名与取值一致，
 * 让「未知字段一律 422」的严格校验在前端就暴露）。契约未导出的请求体在此镜像，
 * 不修改共享契约。
 *
 * 一律经 `@/services/api-client` 的相对路径 `/api/v1` 请求：失败统一抛 `ApiError`，
 * 绝不把失败降级为空列表或假成功。
 */

import { apiRequest } from '@/services/api-client';
import { isJobTerminal, type JobState, type JobView } from '@/contracts/teaching-loop';
import type {
  ConfirmResult,
  DraftPatchRequest,
  DraftSplitRequest,
  DraftView,
  GenerationJobView,
  OrganizeBatchFailure,
  OrganizeJobView,
  QuestionConfirmRequest,
  QuestionDetail,
  QuestionGenerationRequest,
  QuestionImportDetail,
  QuestionImportList,
  QuestionList,
  QuestionPatchRequest,
  QuestionStatus,
  SuggestionView,
} from '@/contracts/question-bank';

/* ------------------------------------------------------------------ 请求体（镜像后端 StrictModel） */

/** 导入创建的可选分类字段：只写有值的表单字段（空串省略）。 */
export interface QuestionImportMeta {
  subjectId?: string;
  gradeId?: string;
}

/** 镜像后端 `DraftMergeRequest`：至少两道草稿及其期望修订。 */
export interface DraftMergeRequest {
  expectedRevisions: Record<string, number>;
}

/** 镜像后端 `OrganizeRequest`（严格模型，字段名与取值必须一致）。 */
export interface OrganizeQuestionsRequest {
  draftIds: string[];
  includeUnassigned: boolean;
  /**
   * **当前聊天模型的 profile id**（RAG-QUALITY v1.1；本地或云端一视同仁）。
   * 不是模型名、不是空串：后端经共享 `resolve_chat_model` 解析，解析失败返回可读错误。
   */
  modelProfileId: string;
}

/** 镜像后端 `SuggestionApplyRequest`；`accept: false` 即「忽略该建议」。 */
export interface SuggestionApplyRequest {
  expectedDraftRevision: number;
  accept: boolean;
}

/** 题目列表筛选（对应后端 `list_questions` 的查询参数）。 */
export interface QuestionQuery {
  subjectId?: string;
  gradeId?: string;
  editionId?: string;
  status?: QuestionStatus;
  q?: string;
  /**
   * 按**正式**知识点关联筛选（后端只匹配当前最新修订上的关联；历史修订不算当前归属）。
   * B3/F10-QB 新增；缺省不筛。
   */
  knowledgePointId?: string;
  offset?: number;
  limit?: number;
}

/**
 * `organize` 的结果视图 = 冻结契约的 `OrganizeJobView`（六态 + `attempt`、`suggestions`、`failures`）。
 *
 * 保留 `normalizeOrganizeResult` 的原因：响应缺字段或形状不认识时必须显式失败
 * （不能让界面把未知响应当成功），也不能用假数据补齐。
 */
export type OrganizeJobResult = OrganizeJobView;

/** 六态白名单：服务端给出未知状态时按失败处理（不把未知当成功）。 */
const ORGANIZE_JOB_STATES: readonly JobState[] = [
  'queued',
  'running',
  'succeeded',
  'failed',
  'cancelled',
  'interrupted',
];

function asJobState(value: unknown): OrganizeJobView['state'] {
  return typeof value === 'string' && (ORGANIZE_JOB_STATES as readonly string[]).includes(value)
    ? (value as OrganizeJobView['state'])
    : 'failed';
}

/** 任务是否仍在进行（统一任务引擎接管后 POST 可能先返回 queued/running）。 */
export function organizeJobPending(job: OrganizeJobView): boolean {
  return !isJobTerminal(job.state);
}

/* ------------------------------------------------------------------ 查询串 */

/** 拼接查询串：只写有值的键（undefined/null/空串跳过），并做 URL 编码。 */
export function questionBankQuery(
  params: Record<string, string | number | undefined | null>,
): string {
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

/* ------------------------------------------------------------------ 导入批次 */

/**
 * 上传试题文件创建解析导入（multipart）。
 * - `file`：原始文件（.md / .pdf / .docx）；
 * - `meta.subjectId` / `meta.gradeId`：可选的表单字段，空值不写入。
 * 不手写 content-type，交给 fetch 生成 multipart boundary。
 */
export function createQuestionImport(
  file: File,
  meta: QuestionImportMeta = {},
  signal?: AbortSignal,
): Promise<QuestionImportDetail> {
  const form = new FormData();
  form.append('file', file);
  if (meta.subjectId) form.append('subjectId', meta.subjectId);
  if (meta.gradeId) form.append('gradeId', meta.gradeId);
  return apiRequest<QuestionImportDetail>('/question-imports', {
    method: 'POST',
    body: form,
    signal,
  });
}

export function listQuestionImports(signal?: AbortSignal): Promise<QuestionImportList> {
  return apiRequest<QuestionImportList>('/question-imports', { signal });
}

export function getQuestionImport(id: string, signal?: AbortSignal): Promise<QuestionImportDetail> {
  return apiRequest<QuestionImportDetail>(`/question-imports/${encodeURIComponent(id)}`, {
    signal,
  });
}

/* ------------------------------------------------------------------ 草稿校对 */

/** 保存草稿（乐观锁 `expectedRevision`）；返回服务端权威草稿视图。 */
export function patchQuestionDraft(draftId: string, body: DraftPatchRequest): Promise<DraftView> {
  return apiRequest<DraftView>(
    `/question-drafts/${encodeURIComponent(draftId)}`,
    jsonInit('PATCH', body),
  );
}

/**
 * 按字符偏移拆分草稿；`draftId` 走查询参数 `?draftId=`（后端契约如此）。
 * 未指定草稿时省略该参数，由后端按偏移解析目标。
 */
export function splitQuestionDraft(
  importId: string,
  draftId: string | null,
  body: DraftSplitRequest,
): Promise<QuestionImportDetail> {
  return apiRequest<QuestionImportDetail>(
    `/question-imports/${encodeURIComponent(importId)}/split${questionBankQuery({ draftId })}`,
    jsonInit('POST', body),
  );
}

export function mergeQuestionDrafts(
  importId: string,
  body: DraftMergeRequest,
): Promise<QuestionImportDetail> {
  return apiRequest<QuestionImportDetail>(
    `/question-imports/${encodeURIComponent(importId)}/merge`,
    jsonInit('POST', body),
  );
}

/* ------------------------------------------------------------------ AI 整理 */

/**
 * 发起 AI 整理：`modelProfileId` 由调用方在**点击那一刻**冻结为当前聊天模型的 profile id
 * （重复发起同一任务时沿用冻结值，不因聊天模型被切换而更改）。
 * 失败一律抛 `ApiError`（含任务级错误码），绝不降级为空建议或假成功。
 */
export function organizeQuestions(
  importId: string,
  body: OrganizeQuestionsRequest,
): Promise<OrganizeJobResult> {
  return apiRequest<unknown>(
    `/question-imports/${encodeURIComponent(importId)}/organize`,
    jsonInit('POST', body),
  ).then(normalizeOrganizeResult);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null;
}

/** 建议明细：只收下具备必要字段的条目，形状不认识的一律丢弃（不猜造）。 */
function asSuggestion(value: unknown): SuggestionView | null {
  if (!isRecord(value)) return null;
  if (typeof value.suggestionId !== 'string' || typeof value.targetDraftId !== 'string') {
    return null;
  }
  if (typeof value.baseDraftRevision !== 'number') return null;
  return value as unknown as SuggestionView;
}

/** 归一 `organize` 响应：任务字段原样取用，建议明细与失败批缺省为空数组。 */
export function normalizeOrganizeResult(raw: unknown): OrganizeJobResult {
  if (!isRecord(raw)) {
    return {
      jobId: '',
      state: 'failed',
      suggestionCount: 0,
      failedBatches: 0,
      errorCode: 'INVALID_RESPONSE',
      suggestions: [],
      failures: [],
    };
  }
  const suggestions = asSuggestions(raw.suggestions) ?? [];
  const failures = asFailures(raw.failures) ?? [];
  const result: OrganizeJobResult = {
    jobId: typeof raw.jobId === 'string' ? raw.jobId : '',
    state: asJobState(raw.state),
    suggestionCount: typeof raw.suggestionCount === 'number' ? raw.suggestionCount : 0,
    failedBatches: typeof raw.failedBatches === 'number' ? raw.failedBatches : 0,
    errorCode: typeof raw.errorCode === 'string' ? raw.errorCode : null,
    suggestions,
    failures,
  };
  // attempt 由统一任务引擎维护（B2 六态）：响应带就保留，缺省不补 0（0 是真实尝试号）
  if (typeof raw.attempt === 'number') result.attempt = raw.attempt;
  return result;
}

/** 建议明细：字段不存在返回 null（保持「未提供」与「空数组」的差别）；形状不认识的条目丢弃。 */
function asSuggestions(raw: unknown): SuggestionView[] | null {
  if (!Array.isArray(raw)) return null;
  const suggestions: SuggestionView[] = [];
  for (const item of raw) {
    const parsed = asSuggestion(item);
    if (parsed) suggestions.push(parsed);
  }
  return suggestions;
}

function asFailures(raw: unknown): OrganizeBatchFailure[] | null {
  if (!Array.isArray(raw)) return null;
  return raw.filter(isRecord).map((item) => ({
    batchIndex: typeof item.batchIndex === 'number' ? item.batchIndex : -1,
    code: typeof item.code === 'string' ? item.code : 'ORGANIZER_UNKNOWN',
    message: typeof item.message === 'string' ? item.message : '',
  }));
}

/**
 * 把公共任务视图（`GET /workflow-jobs/{id}?domain=question`）转换成整理视图的**可识别字段**。
 *
 * 纪律：只取服务端明确给出的字段（`result.suggestions` / `suggestionCount` / `failures` /
 * `failedBatches` / `errorCode`）；没有的字段一律不写，界面保留上一份权威数据，
 * 不猜造、不清零。`state` / `attempt` / `jobId` 始终来自任务视图；`view.error` 只在
 * 整理视图还没有错误码时用于补充。
 */
export function organizeFieldsFromJobView(view: JobView): Partial<OrganizeJobResult> {
  const patch: Partial<OrganizeJobResult> = {
    jobId: view.jobId,
    state: asJobState(view.state),
  };
  if (typeof view.attempt === 'number') patch.attempt = view.attempt;
  const result = isRecord(view.result) ? view.result : null;
  if (result) {
    const suggestions = asSuggestions(result.suggestions);
    if (suggestions) patch.suggestions = suggestions;
    const failures = asFailures(result.failures);
    if (failures) patch.failures = failures;
    if (typeof result.suggestionCount === 'number') patch.suggestionCount = result.suggestionCount;
    if (typeof result.failedBatches === 'number') patch.failedBatches = result.failedBatches;
    if (typeof result.errorCode === 'string' || result.errorCode === null) {
      patch.errorCode = typeof result.errorCode === 'string' ? result.errorCode : null;
    }
  }
  return patch;
}

/** 用一次任务观察更新整理视图：状态/尝试号来自任务视图，其余字段只在服务端给出时更新。 */
export function mergeOrganizeObservation(
  current: OrganizeJobResult,
  view: JobView,
): OrganizeJobResult {
  const patch = organizeFieldsFromJobView(view);
  return {
    ...current,
    ...patch,
    errorCode: patch.errorCode ?? current.errorCode ?? view.error?.code ?? null,
  };
}

/** 应用（accept=true）或忽略（accept=false）一条 AI 建议；返回重校后的草稿。 */
export function applyQuestionSuggestion(
  suggestionId: string,
  body: SuggestionApplyRequest,
): Promise<DraftView> {
  return apiRequest<DraftView>(
    `/question-suggestions/${encodeURIComponent(suggestionId)}/apply`,
    jsonInit('POST', body),
  );
}

/* ------------------------------------------------------------------ AI 补题（生成） */

/**
 * 发起 AI 补题：`modelProfileId` 由调用方在**点击那一刻**冻结为当前聊天模型的 profile id
 * （重试由后端沿用冻结输入与模型指纹，前端不换模型重发）。
 *
 * `202` 只代表任务被接受，绝不代表已生成草稿：结果经
 * `GET /workflow-jobs/{jobId}?domain=question` 观察（六态 + `attempt`），
 * 失败一律抛 `ApiError`，不降级为空批次或假成功。
 */
export function createQuestionGenerationJob(
  body: QuestionGenerationRequest,
): Promise<GenerationJobView> {
  return apiRequest<unknown>('/question-generation-jobs', jsonInit('POST', body)).then(
    normalizeGenerationResult,
  );
}

/**
 * 归一补题任务响应：`state` 只认六态白名单（未知按失败处理），`jobId`/`importId`/
 * `candidateCount`/`errorCode` 形状不认识时给显式兜底。
 * `attempt` 保留（含 0）：缺字段不补 0（0 是真实尝试号，不能与「缺省」混为一谈）。
 */
export function normalizeGenerationResult(raw: unknown): GenerationJobView {
  if (!isRecord(raw)) {
    return {
      jobId: '',
      state: 'failed',
      importId: null,
      candidateCount: 0,
      errorCode: 'INVALID_RESPONSE',
    };
  }
  const result: GenerationJobView = {
    jobId: typeof raw.jobId === 'string' ? raw.jobId : '',
    state: asJobState(raw.state),
    importId: typeof raw.importId === 'string' && raw.importId ? raw.importId : null,
    candidateCount: typeof raw.candidateCount === 'number' ? raw.candidateCount : 0,
    errorCode: typeof raw.errorCode === 'string' && raw.errorCode ? raw.errorCode : null,
  };
  if (typeof raw.attempt === 'number') result.attempt = raw.attempt;
  return result;
}

/**
 * 把公共任务视图（`GET /workflow-jobs/{id}?domain=question`）转换成补题视图的**可识别字段**。
 *
 * 纪律：只取服务端明确给出的字段（`result.importId` / `result.candidateCount` /
 * `result.errorCode`）；没有的字段一律不写，界面保留上一份权威数据，不猜造、不清零。
 * 补题没有「批级部分结果」：`importId` 只在任务成功发布后由服务端给出。
 */
export function generationFieldsFromJobView(view: JobView): Partial<GenerationJobView> {
  const patch: Partial<GenerationJobView> = {
    jobId: view.jobId,
    state: asJobState(view.state),
  };
  if (typeof view.attempt === 'number') patch.attempt = view.attempt;
  const result = isRecord(view.result) ? view.result : null;
  if (result) {
    if (typeof result.importId === 'string' && result.importId) patch.importId = result.importId;
    if (typeof result.candidateCount === 'number') {
      patch.candidateCount = result.candidateCount;
    }
    if (typeof result.errorCode === 'string' || result.errorCode === null) {
      patch.errorCode = typeof result.errorCode === 'string' ? result.errorCode : null;
    }
  }
  return patch;
}

/**
 * 用一次任务观察更新补题视图：状态/尝试号来自任务视图，其余字段只在服务端给出时更新；
 * 上次的 `importId`/`candidateCount` 在任务视图没有结果时不回退、不清零。
 */
export function mergeGenerationObservation(
  current: GenerationJobView | null,
  view: JobView,
): GenerationJobView | null {
  if (!current) return null;
  const patch = generationFieldsFromJobView(view);
  return {
    ...current,
    ...patch,
    errorCode: patch.errorCode ?? current.errorCode ?? view.error?.code ?? null,
  };
}



/**
 * 确认入库（幂等 `submissionId`）。
 * 语义：HTTP 200 + `failures` 非空表示「整体不确认、逐条给原因」，
 * 此时服务端不登记提交，修正后可用**同一个** submissionId 重试。
 */
export function confirmQuestionImport(
  importId: string,
  body: QuestionConfirmRequest,
): Promise<ConfirmResult> {
  return apiRequest<ConfirmResult>(
    `/question-imports/${encodeURIComponent(importId)}/confirm`,
    jsonInit('POST', body),
  );
}

/* ------------------------------------------------------------------ 已入库题目 */

export function listQuestions(
  query: QuestionQuery = {},
  signal?: AbortSignal,
): Promise<QuestionList> {
  return apiRequest<QuestionList>(
    `/questions${questionBankQuery({
      subjectId: query.subjectId,
      gradeId: query.gradeId,
      editionId: query.editionId,
      status: query.status,
      q: query.q,
      knowledgePointId: query.knowledgePointId,
      offset: query.offset,
      limit: query.limit,
    })}`,
    { signal },
  );
}

export function getQuestion(id: string, signal?: AbortSignal): Promise<QuestionDetail> {
  return apiRequest<QuestionDetail>(`/questions/${encodeURIComponent(id)}`, { signal });
}

export function patchQuestion(id: string, body: QuestionPatchRequest): Promise<QuestionDetail> {
  return apiRequest<QuestionDetail>(
    `/questions/${encodeURIComponent(id)}`,
    jsonInit('PATCH', body),
  );
}

/**
 * 归档删除题目；`expectedRevision` 是可选查询参数。
 * 后端以 204 应答（无返回体），`apiRequest` 归一为 undefined。
 */
export function deleteQuestion(id: string, expectedRevision?: number): Promise<void> {
  return apiRequest<void>(
    `/questions/${encodeURIComponent(id)}${questionBankQuery({ expectedRevision })}`,
    { method: 'DELETE' },
  );
}
