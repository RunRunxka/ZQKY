/**
 * 教案工作台 `/api/v1` 客户端（R7-FE，2026-10-12）。
 *
 * 只用相对路径经 `@/services/api-client` 请求，失败统一抛 `ApiError`（含 `details`），
 * **绝不把失败降级为空列表或假成功**：后端未上线时页面必须看到真实错误（404/501/503）。
 *
 * 冻结端点（本卡）：
 * - `GET /lesson-plans`（列表）/ `POST /lesson-plans`（创建，body `{submissionId, data}`）；
 * - `GET /lesson-plans/{id}`；
 * - `PATCH /lesson-plans/{id}/draft`（autosave，body 与归档 `LessonSaveRequest` 同构：
 *   `{submissionId, expectedRevision, data, context, source}`；409 → `details.currentRevision`）；
 * - `POST /lesson-plans/{id}/export` → 202 `{artifact:{artifactId,fileName}}`（后端组装 docx，
 *   前端只触发 + 下载；body 携带装配所需的正文/排版/模块顺序，见 `LessonExportRequest`）；
 * - `GET /export-artifacts/{artifactId}/download`；
 * - `POST /lesson-plans/source-uploads`（multipart 上传学情文件 → `assetRef`）。
 *
 * 服务端视图做**容错归一**（`normalizeLessonView`）：接受 `currentRevision` 嵌套或扁平返回；
 * 正文缺省由 `features/lesson-plan/model/lesson-data.ts` 的 `withLessonDefaults` 补齐
 * （旧数据向后兼容），结构完全无法识别时抛错，由界面显示失败而不是伪造空文档。
 */

import { apiRequest, apiRequestBlob, type BlobDownload } from '@/services/api-client';
import type {
  LessonCreateRequest,
  LessonDeleteResult,
  LessonDraftPatchRequest,
  LessonExportReceipt,
  LessonExportRequest,
  LessonPlanData,
  LessonSourceUpload,
  LessonSummary,
  LessonSummaryPage,
  LessonView,
} from '@/contracts/lesson-plans';

const key = encodeURIComponent;

function jsonInit(method: string, body: unknown, signal?: AbortSignal): RequestInit {
  return {
    method,
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  };
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

/* ------------------------------------------------------------------ 容错归一 */

/** 正文可识别的键（至少命中一个才算教案文档；否则视为结构损坏，不伪造空文档）。 */
const LESSON_DATA_KEYS = [
  'title',
  'basic',
  'analysis',
  'strategy',
  'evaluation',
  'processV2',
  'coreCompetencies',
  'keyPoints',
  'teachingDesign',
  'reflection',
] as const;

export function isLessonDataShaped(value: unknown): value is Record<string, unknown> {
  return isRecord(value) && LESSON_DATA_KEYS.some((name) => name in value);
}

/** 从 `{currentRevision:{data}}` 或扁平 `{data}` 中取正文；都没有 → 抛错。 */
export function extractLessonData(value: unknown): LessonPlanData {
  if (!isRecord(value)) throw new Error('教案文档结构无法识别：响应不是对象。');
  const revision = value.currentRevision;
  const nested = isRecord(revision) ? revision.data : undefined;
  const data = isLessonDataShaped(nested) ? nested : isLessonDataShaped(value.data) ? value.data : undefined;
  if (!data) throw new Error('教案文档结构无法识别：缺少正文 data。');
  // 缺省补全在进入工作台时统一做（withLessonDefaults），这里只做形状判定。
  return data as unknown as LessonPlanData;
}

export function normalizeLessonView(value: unknown): LessonView {
  if (!isRecord(value)) throw new Error('教案读取失败：响应不是对象。');
  const id = value.lessonPlanId;
  if (typeof id !== 'string' || !id) throw new Error('教案读取失败：缺少 lessonPlanId。');
  const revision = typeof value.revision === 'number' && Number.isFinite(value.revision) ? value.revision : 0;
  const current = isRecord(value.currentRevision) ? value.currentRevision : {};
  return {
    protocolVersion: typeof value.protocolVersion === 'number' ? value.protocolVersion : undefined,
    lessonPlanId: id,
    subjectId: typeof value.subjectId === 'string' ? value.subjectId : undefined,
    classId: typeof value.classId === 'string' ? value.classId : undefined,
    revision,
    currentRevisionId:
      typeof value.currentRevisionId === 'string'
        ? value.currentRevisionId
        : typeof current.revisionId === 'string'
          ? current.revisionId
          : '',
    currentRevision: {
      lessonPlanId: typeof current.lessonPlanId === 'string' ? current.lessonPlanId : id,
      revisionId: typeof current.revisionId === 'string' ? current.revisionId : '',
      version: typeof current.version === 'number' ? current.version : revision,
      data: extractLessonData(value),
      contentHash: typeof current.contentHash === 'string' ? current.contentHash : undefined,
      reviewState:
        current.reviewState === 'reviewed' || current.reviewState === 'unreviewed'
          ? current.reviewState
          : undefined,
      createdAt: typeof current.createdAt === 'string' ? current.createdAt : undefined,
    },
    replayed: value.replayed === true,
  };
}

function normalizeSummaries(value: unknown): LessonSummary[] {
  const items =
    isRecord(value) && Array.isArray(value.items) ? value.items : Array.isArray(value) ? value : null;
  if (!items) throw new Error('教案列表结构无法识别：缺少 items。');
  return items.filter(isRecord).map((item) => ({
    lessonPlanId: String(item.lessonPlanId ?? ''),
    title: typeof item.title === 'string' ? item.title : '',
    revision: typeof item.revision === 'number' ? item.revision : 0,
    currentRevisionId:
      typeof item.currentRevisionId === 'string' ? item.currentRevisionId : undefined,
    updatedAt: typeof item.updatedAt === 'string' ? item.updatedAt : '',
  }));
}

export function normalizeLessonList(value: unknown): LessonSummaryPage {
  const items = normalizeSummaries(value);
  const total = isRecord(value) && typeof value.total === 'number' ? value.total : items.length;
  return { items, total, offset: 0, limit: items.length };
}

/* ------------------------------------------------------------------ 端点 */

export function listLessonPlans(signal?: AbortSignal): Promise<LessonSummaryPage> {
  return apiRequest<unknown>('/lesson-plans', { signal }).then(normalizeLessonList);
}

export function getLessonPlan(lessonPlanId: string, signal?: AbortSignal): Promise<LessonView> {
  return apiRequest<unknown>(`/lesson-plans/${key(lessonPlanId)}`, { signal }).then(normalizeLessonView);
}

export function createLessonPlan(body: LessonCreateRequest, signal?: AbortSignal): Promise<LessonView> {
  return apiRequest<unknown>('/lesson-plans', jsonInit('POST', body, signal)).then(normalizeLessonView);
}

/**
 * 彻底删除教案（`expectedRevision` 走查询参数）：清掉该教案自身的全部历史，不可恢复。
 * 乐观锁不符 → 409 `REVISION_CONFLICT`；不存在 → 404；被教案范围之外的引用挡住 → 409 `LESSON_IN_USE`。
 * **不做归档**：界面只提供删除（归档端点保留为历史数据兼容）。
 */
export function deleteLessonPlan(
  lessonPlanId: string,
  expectedRevision: number,
  signal?: AbortSignal,
): Promise<LessonDeleteResult> {
  return apiRequest<LessonDeleteResult>(
    `/lesson-plans/${key(lessonPlanId)}?expectedRevision=${expectedRevision}`,
    { method: 'DELETE', signal },
  );
}

/** autosave（CAS）：409 时 `ApiError.details.currentRevision` 是服务器当前修订号。 */
export function patchLessonPlanDraft(
  lessonPlanId: string,
  body: LessonDraftPatchRequest,
  signal?: AbortSignal,
): Promise<LessonView> {
  return apiRequest<unknown>(
    `/lesson-plans/${key(lessonPlanId)}/draft`,
    jsonInit('PATCH', body, signal),
  ).then(normalizeLessonView);
}

export function exportLessonPlan(
  lessonPlanId: string,
  body: LessonExportRequest,
  signal?: AbortSignal,
): Promise<LessonExportReceipt> {
  return apiRequest<LessonExportReceipt>(
    `/lesson-plans/${key(lessonPlanId)}/export`,
    jsonInit('POST', body, signal),
  );
}

export function downloadLessonExport(artifactId: string, signal?: AbortSignal): Promise<BlobDownload> {
  return apiRequestBlob(`/export-artifacts/${key(artifactId)}/download`, { signal });
}

/**
 * 上传学情文件 → `assetRef`。端点名与返回字段以 R7-BE 定稿为准（见交付「未决问题」）；
 * 这里只做 multipart 编码与归一，失败照实抛出。
 */
export function uploadLessonSource(file: File, signal?: AbortSignal): Promise<LessonSourceUpload> {
  const form = new FormData();
  form.append('file', file);
  return apiRequest<unknown>('/lesson-plans/source-uploads', {
    method: 'POST',
    body: form,
    signal,
  }).then((value) => {
    if (!isRecord(value) || typeof value.assetRef !== 'string' || !value.assetRef) {
      throw new Error('学情文件上传失败：响应缺少 assetRef。');
    }
    return {
      assetRef: value.assetRef,
      fileName: typeof value.fileName === 'string' ? value.fileName : file.name,
    };
  });
}

/** 导出为对象，便于页面注入测试替身（`services` prop）。 */
export const lessonPlansApi = {
  listLessonPlans,
  getLessonPlan,
  createLessonPlan,
  patchLessonPlanDraft,
  deleteLessonPlan,
  exportLessonPlan,
  downloadLessonExport,
  uploadLessonSource,
};

export type LessonPlansApi = typeof lessonPlansApi;
