import type { AnalysisContextInput, DraftEnvelope, LessonPlanData, LessonSaveRequest, LessonView } from '@/contracts/lesson-plans';
import { stablePayloadKey, type FrozenSubmission } from '@/features/assessments/hooks';
import { validateData } from '../services/drafts';
import { ApiError } from '@/services/api-client';

export const SERVER_SESSION_PREFIX = 'zhiqikeyuan:lesson-plan:server-session:v1:';
export const LEGACY_KEY = 'zhiqikeyuan:lesson-plan:v1';
export type LessonOperationKind = 'save' | 'generate' | 'apply' | 'reject';
export interface ServerLessonCache {
  schemaVersion: 1; documentId: string; editRevision: number; acknowledgedEditRevision: number;
  serverRevision: number; serverRevisionId: string; data: LessonPlanData;
  context: AnalysisContextInput | null; source: 'manual' | 'rule';
  operations: Record<LessonOperationKind, FrozenSubmission<unknown> | null>;
}
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const integer = (value: unknown, minimum = 0): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= minimum;
export const serverSessionKey = (id: string) => `${SERVER_SESSION_PREFIX}${encodeURIComponent(id)}`;
export function assertWriteSize(body: unknown) { if (new TextEncoder().encode(stablePayloadKey(body)).length > 2 * 1024 * 1024) throw new ApiError('PAYLOAD_TOO_LARGE', '后台教案请求超过2MiB，当前输入与旧稿保持；请先备份并缩短内容。', 422, false); }
export function validateEnvelope(raw: unknown): asserts raw is DraftEnvelope {
  if (!record(raw) || Object.keys(raw).sort().join('|') !== 'data|revision|schemaVersion|updatedAt' ||
      raw.schemaVersion !== 1 || !integer(raw.revision) || typeof raw.updatedAt !== 'string' ||
      !/^\d{4}-\d\d-\d\dT.*(?:Z|[+-]\d\d:\d\d)$/.test(raw.updatedAt) || !Number.isFinite(Date.parse(raw.updatedAt))) throw new Error('旧稿完整信封不合法，原件保持');
  validateExactData(raw.data);
}
export function validateExactData(raw: unknown): asserts raw is LessonPlanData {
  validateData(raw);
  if (Object.keys(raw).sort().join('|') !== 'coreCompetencies|currentLessonNo|exercises|keyPoints|lessonTypes|otherTypeText|process|reflection|teachingDesign|title|totalLessons' ||
      raw.process.some((item) => Object.keys(item).sort().join('|') !== 'design|id|secondary|stage')) throw new Error('教案包含不兼容字段，原件保持');
}
export function validateContext(value: unknown): asserts value is AnalysisContextInput | null {
  if (value === null) return;
  if (!record(value) || Object.keys(value).sort().join('|') !== 'analysisRunId|selectedKnowledgePointIds' ||
      typeof value.analysisRunId !== 'string' || !value.analysisRunId.trim() || !Array.isArray(value.selectedKnowledgePointIds) ||
      !value.selectedKnowledgePointIds.length || value.selectedKnowledgePointIds.length > 50 ||
      value.selectedKnowledgePointIds.some((id) => typeof id !== 'string' || !id.trim()) ||
      new Set(value.selectedKnowledgePointIds).size !== value.selectedKnowledgePointIds.length) throw new Error('固定学情来源不合法');
}
export function validateOperation(value: unknown, contextKey: string): asserts value is FrozenSubmission<unknown> {
  if (!record(value) || typeof value.submissionId !== 'string' || !value.submissionId || value.operationId !== value.submissionId ||
      value.payloadKey !== stablePayloadKey(value.payload) || !record(value.metadata) || value.metadata.contextKey !== contextKey ||
      !integer(value.metadata.originalEditGeneration) || typeof value.metadata.loadGeneration !== 'string' || !value.metadata.loadGeneration) throw new Error('原操作恢复包身份或载荷不合法');
}
export function initialServerCache(view: LessonView): ServerLessonCache {
  const analysis = view.currentRevision.contextSnapshot.analysis;
  return { schemaVersion: 1, documentId: view.lessonPlanId, editRevision: 0, acknowledgedEditRevision: 0,
    serverRevision: view.revision, serverRevisionId: view.currentRevisionId, data: structuredClone(view.currentRevision.data),
    context: analysis ? { analysisRunId: analysis.analysisRunId, selectedKnowledgePointIds: analysis.knowledgePoints.map((point) => point.knowledgePointId) } : null,
    source: 'manual', operations: { save: null, generate: null, apply: null, reject: null } };
}
export function readServerCache(storage: Storage, id: string): ServerLessonCache | null {
  const raw = storage.getItem(serverSessionKey(id));
  if (raw === null) return null;
  const cache: unknown = JSON.parse(raw);
  if (!record(cache) || cache.schemaVersion !== 1 || cache.documentId !== id || !integer(cache.editRevision) ||
      !integer(cache.acknowledgedEditRevision) || cache.acknowledgedEditRevision > cache.editRevision ||
      !integer(cache.serverRevision, 1) || typeof cache.serverRevisionId !== 'string' || !cache.serverRevisionId ||
      !['manual', 'rule'].includes(String(cache.source)) || !record(cache.operations) ||
      Object.keys(cache.operations).sort().join('|') !== 'apply|generate|reject|save') throw new Error('后台教案恢复缓存结构不合法');
  validateExactData(cache.data); validateContext(cache.context);
  for (const kind of ['save', 'generate', 'apply', 'reject'] as const) {
    const operation = cache.operations[kind];
    if (operation !== null) validateOperation(operation, `lesson|${id}|${kind}`);
  }
  if (cache.operations.save) {
    const payload = (cache.operations.save as FrozenSubmission<unknown>).payload;
    if (!record(payload) || !integer(payload.expectedRevision, 1)) throw new Error('原保存包版本不合法');
    validateExactData(payload.data); validateContext(payload.context);
  }
  return cache as unknown as ServerLessonCache;
}
export function writeServerCache(storage: Storage, cache: ServerLessonCache) {
  const raw = JSON.stringify(cache);
  if (raw.length > 12 * 1024 * 1024) throw new Error('教案恢复包过大，请先备份');
  storage.setItem(serverSessionKey(cache.documentId), raw);
}
export function loadLegacyRaw(storage: Storage): { raw: string; envelope: DraftEnvelope } | null {
  const raw = storage.getItem(LEGACY_KEY);
  if (raw === null) return null;
  const envelope: unknown = JSON.parse(raw); validateEnvelope(envelope);
  if (new TextEncoder().encode(JSON.stringify(envelope)).length > 2 * 1024 * 1024) throw new Error('旧稿超过后台导入2MiB门槛，原件保持，请导出备份');
  return { raw, envelope: structuredClone(envelope) };
}
export type SaveContent = Omit<LessonSaveRequest, 'submissionId'>;
