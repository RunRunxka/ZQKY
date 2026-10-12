/**
 * 练习编辑态的本机恢复稿（R8-FE 2026-10-12，取自归档 `features/practices/session.ts`）。
 *
 * 语义（与归档一致）：
 * - 未保存稿按练习集独立保留在本机；刷新/关闭/返回后可恢复，绝不自动保存或自动审核；
 * - 结构损坏或身份不符的旧稿**原字节保留**并暂停写入（上层显示原因，不覆盖、不当作空稿）；
 * - 结果未知（拿不到响应）的保存/审核会连同冻结的 `submissionId` 与原样载荷一起留在恢复稿里，
 *   重试必须重放原包，不能换标识重做。
 *
 * 重建期最小解耦：归档的冻结提交记录带 `metadata`（上下文键、编辑代次、加载代次）；
 * 重建期的 `useFrozenSubmission`（`@/features/assessments/hooks`，R5-FE 取回）只冻结
 * `operationId/submissionId/payloadKey/payload`。这里按该形状保存与校验，
 * 上下文（practiceSetId）由恢复稿自身的 `practiceSetId` 字段保证，不新增协议字段。
 */

import type {
  PracticeConstraints,
  PracticeDraftItem,
  PracticeDraftPatch,
  PracticeReviewRequest,
  PracticeSetView,
} from '@/contracts/b4';
import type { FrozenSubmission } from '@/features/assessments/hooks';

export const PRACTICE_RECOVERY_PREFIX = 'zhiqikeyuan:practice-session:v1:';

/** 保存载荷：`PracticeDraftPatch` 去掉每次重新冻结的 `submissionId`。 */
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

export function recoveryKey(id: string): string {
  return `${PRACTICE_RECOVERY_PREFIX}${encodeURIComponent(id)}`;
}

const record = (value: unknown): value is Record<string, unknown> =>
  !!value && typeof value === 'object' && !Array.isArray(value);
const text = (value: unknown): value is string => typeof value === 'string' && value.length <= 100_000;
const integer = (value: unknown): value is number => Number.isSafeInteger(value) && (value as number) >= 0;
const strings = (value: unknown): boolean => Array.isArray(value) && value.length <= 10_000 && value.every(text);

function validItems(value: unknown): boolean {
  return (
    Array.isArray(value) &&
    value.length <= 1000 &&
    value.every(
      (item: unknown) =>
        record(item) &&
        text(item.itemKey) &&
        text(item.questionRevisionId) &&
        integer(item.ordinal) &&
        text(item.maxScore) &&
        strings(item.selectedKnowledgePointIds) &&
        record(item.itemStructure) &&
        Array.isArray(item.itemStructure.nodes) &&
        item.itemStructure.nodes.length <= 1000 &&
        item.itemStructure.nodes.every(
          (node: unknown) =>
            record(node) &&
            text(node.nodeKey) &&
            (node.parentNodeKey === null || text(node.parentNodeKey)) &&
            text(node.questionNo) &&
            integer(node.ordinal) &&
            typeof node.isScored === 'boolean' &&
            (node.maxScore === undefined || node.maxScore === null || text(node.maxScore)) &&
            (node.knowledgePointIds === undefined || strings(node.knowledgePointIds)) &&
            (node.sourceBlockIds === undefined || strings(node.sourceBlockIds)),
        ),
    )
  );
}

function validConstraints(value: unknown): boolean {
  return (
    record(value) &&
    typeof value.count === 'number' &&
    Number.isFinite(value.count) &&
    ['questionTypes', 'difficulties'].every((key) => value[key] === undefined || strings(value[key])) &&
    ['includeUnknownDifficulty', 'excludeOriginal', 'deduplicate'].every(
      (key) => value[key] === undefined || typeof value[key] === 'boolean',
    )
  );
}

function validOperation<T>(value: unknown, kind: 'save' | 'review'): value is FrozenSubmission<T> | null {
  if (value === null) return true;
  if (
    !record(value) ||
    !text(value.operationId) ||
    !value.operationId ||
    value.operationId !== value.submissionId ||
    !text(value.submissionId) ||
    !value.submissionId ||
    !(typeof value.payloadKey === 'string' && value.payloadKey.length <= 8_000_000) ||
    !record(value.payload)
  ) {
    return false;
  }
  return kind === 'save'
    ? integer(value.payload.expectedRevision) &&
        validItems(value.payload.items) &&
        validConstraints(value.payload.constraints)
    : text(value.payload.submissionId) && integer(value.payload.expectedRevision);
}

/** 读取恢复稿：结构损坏或身份不符抛出明确错误（调用方保留原字节并暂停写入）。 */
export function readPracticeSession(storage: Storage, id: string): PracticeSession | null {
  const raw = storage.getItem(recoveryKey(id));
  if (raw === null) return null;
  if (raw.length > 8_000_000) throw new Error('练习恢复稿过大，原缓存未覆盖。');
  const value: unknown = JSON.parse(raw);
  if (
    !record(value) ||
    value.schemaVersion !== 1 ||
    value.practiceSetId !== id ||
    !integer(value.serverRevision) ||
    !text(value.serverRevisionId) ||
    !integer(value.editGeneration) ||
    typeof value.dirty !== 'boolean' ||
    !validItems(value.items) ||
    !validConstraints(value.constraints) ||
    !validOperation<PracticeSaveContent>(value.saveOperation, 'save') ||
    !validOperation<PracticeReviewRequest>(value.reviewOperation, 'review') ||
    !(
      value.identityConflict === undefined ||
      value.identityConflict === null ||
      (record(value.identityConflict) &&
        integer(value.identityConflict.revision) &&
        text(value.identityConflict.knownRevisionId) &&
        text(value.identityConflict.receivedRevisionId))
    )
  ) {
    throw new Error('练习恢复稿结构损坏或身份不符，原缓存未覆盖。');
  }
  value.identityConflict ??= null;
  return value as unknown as PracticeSession;
}

export function writePracticeSession(storage: Storage, session: PracticeSession): void {
  const raw = JSON.stringify(session);
  if (raw.length > 8_000_000) throw new Error('练习恢复稿过大，请先保存或备份。');
  storage.setItem(recoveryKey(session.practiceSetId), raw);
}

/** 与服务端基线对齐的新会话：不含恢复稿、不含未知操作。 */
export function initialPracticeSession(view: PracticeSetView): PracticeSession {
  return {
    schemaVersion: 1,
    practiceSetId: view.practiceSetId,
    serverRevision: view.revision,
    serverRevisionId: view.currentRevision.practiceRevisionId,
    editGeneration: 0,
    dirty: false,
    items: structuredClone(view.currentRevision.draftItems),
    constraints: structuredClone(view.currentRevision.constraints),
    saveOperation: null,
    reviewOperation: null,
    identityConflict: null,
  };
}
