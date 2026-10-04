import type { PracticeConstraints, PracticeDraftItem, PracticeDraftPatch, PracticeReviewRequest, PracticeSetView } from '@/contracts/b4';
import type { FrozenSubmission } from '@/features/assessments/hooks';

export const PRACTICE_RECOVERY_PREFIX = 'zhiqikeyuan:practice-session:v1:';
export type PracticeSaveContent = Omit<PracticeDraftPatch, 'submissionId'>;
export interface PracticeSession {
  schemaVersion: 1;
  practiceSetId: string;
  serverRevision: number;
  serverRevisionId: string;
  editGeneration: number;
  dirty: boolean;
  items: PracticeDraftItem[];
  constraints: PracticeConstraints;
  saveOperation: FrozenSubmission<PracticeSaveContent> | null;
  reviewOperation: FrozenSubmission<PracticeReviewRequest> | null;
  identityConflict: { revision: number; knownRevisionId: string; receivedRevisionId: string } | null;
}
export interface PracticeEditingHandle {
  practiceSetId: string;
  dirty: boolean;
  busy: boolean;
  unknown: boolean;
  save: () => Promise<boolean>;
  keep: () => boolean;
  discard: () => boolean;
}
export function recoveryKey(id: string) { return `${PRACTICE_RECOVERY_PREFIX}${encodeURIComponent(id)}`; }
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === 'string' && value.length <= 100_000;
const integer = (value: unknown): value is number => Number.isSafeInteger(value) && (value as number) >= 0;
const strings = (value: unknown): boolean => Array.isArray(value) && value.length <= 10_000 && value.every(text);
function validItems(value: unknown): boolean {
  return Array.isArray(value) && value.length <= 1000 && value.every((item: unknown) => record(item) &&
    text(item.itemKey) && text(item.questionRevisionId) && integer(item.ordinal) && text(item.maxScore) && strings(item.selectedKnowledgePointIds) &&
    record(item.itemStructure) && Array.isArray(item.itemStructure.nodes) && item.itemStructure.nodes.length <= 1000 && item.itemStructure.nodes.every((node: unknown) =>
      record(node) && text(node.nodeKey) && (node.parentNodeKey === null || text(node.parentNodeKey)) && text(node.questionNo) && integer(node.ordinal) &&
      typeof node.isScored === 'boolean' && (node.maxScore === undefined || node.maxScore === null || text(node.maxScore)) &&
      (node.knowledgePointIds === undefined || strings(node.knowledgePointIds)) && (node.sourceBlockIds === undefined || strings(node.sourceBlockIds))));
}
function validConstraints(value: unknown): boolean {
  return record(value) && typeof value.count === 'number' && Number.isFinite(value.count) &&
    ['questionTypes', 'difficulties'].every((key) => value[key] === undefined || strings(value[key])) &&
    ['includeUnknownDifficulty', 'excludeOriginal', 'deduplicate'].every((key) => value[key] === undefined || typeof value[key] === 'boolean');
}
function validOperation(value: unknown, id: string, kind: 'save' | 'review'): boolean {
  if (value === null) return true;
  if (!record(value) || value.operationId !== value.submissionId || !text(value.submissionId) || !value.submissionId || value.submissionId.length > 128 || !(typeof value.payloadKey === 'string' && value.payloadKey.length <= 8_000_000) || !record(value.payload) || !record(value.metadata)) return false;
  if (value.metadata.contextKey !== `practice|${id}` || !integer(value.metadata.originalEditGeneration) || !text(value.metadata.loadGeneration) || !value.metadata.loadGeneration) return false;
  return integer(value.payload.expectedRevision) && (kind === 'save'
    ? validItems(value.payload.items) && validConstraints(value.payload.constraints)
    : text(value.payload.submissionId));
}
export function readPracticeSession(storage: Storage, id: string): PracticeSession | null {
  const raw = storage.getItem(recoveryKey(id));
  if (raw === null) return null;
  if (raw.length > 8_000_000) throw new Error('练习恢复稿过大，原缓存未覆盖。');
  const value: unknown = JSON.parse(raw);
  if (!record(value) || value.schemaVersion !== 1 || value.practiceSetId !== id || !integer(value.serverRevision) || !text(value.serverRevisionId) ||
    !integer(value.editGeneration) || typeof value.dirty !== 'boolean' || !validItems(value.items) || !validConstraints(value.constraints) ||
    !validOperation(value.saveOperation, id, 'save') || !validOperation(value.reviewOperation, id, 'review') ||
    !(value.identityConflict === undefined || value.identityConflict === null || (record(value.identityConflict) && integer(value.identityConflict.revision) && text(value.identityConflict.knownRevisionId) && text(value.identityConflict.receivedRevisionId)))) throw new Error('练习恢复稿结构损坏或身份不符，原缓存未覆盖。');
  value.identityConflict ??= null;
  return value as unknown as PracticeSession;
}
export function writePracticeSession(storage: Storage, session: PracticeSession) {
  const raw = JSON.stringify(session);
  if (raw.length > 8_000_000) throw new Error('练习恢复稿过大，请先保存或备份。');
  storage.setItem(recoveryKey(session.practiceSetId), raw);
}
export function initialPracticeSession(view: PracticeSetView): PracticeSession {
  return { schemaVersion: 1, practiceSetId: view.practiceSetId, serverRevision: view.revision, serverRevisionId: view.currentRevision.practiceRevisionId,
    editGeneration: 0, dirty: false, items: structuredClone(view.currentRevision.draftItems), constraints: structuredClone(view.currentRevision.constraints), saveOperation: null, reviewOperation: null, identityConflict: null };
}
