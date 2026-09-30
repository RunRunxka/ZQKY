/**
 * 教学闭环 v1 跨模块冻结契约（TEACHING-LOOP B0，2026-09-30）。
 *
 * 与后端 `apps/api/app/contracts/teaching_loop.py` 逐字段对应；外部 JSON 一律
 * camelCase。业务模块（知识点、题库关联、原卷、成绩、学情、练习、教案）从这里
 * 导入这些类型，**不得各自复制**。
 *
 * 冻结口径：
 * - `RevisionIdentity.revision` 是可变实体的乐观锁整数；`revisionId` 是固定内容
 *   修订身份（不可变）。两者不得混用。
 * - 任务状态机 `queued → running → succeeded|failed|cancelled|interrupted`；
 *   重启遗留 `running` 一律转 `interrupted`，不自动重新调用模型。
 * - 提交幂等身份是 `(ownerId, operation, submissionId)`；同键同 `requestHash`
 *   重放返回原结果，同键不同 hash 报 409 `SUBMISSION_CONFLICT`。
 * - 分数一律用整数 `scoreUnits`（分数 × 100）；空白/缺考/免考与有效 0 分严格区分。
 */

import type { ApiErrorEnvelope, ApiErrorDetails, ErrorIssue } from '@/contracts/api';

export type { ApiErrorDetails, ErrorIssue };

/** 任务所属业务库。 */
export type JobDomain = 'knowledge' | 'question' | 'teaching';

export const JOB_DOMAINS: readonly JobDomain[] = ['knowledge', 'question', 'teaching'];

export type JobState =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'cancelled'
  | 'interrupted';

export const JOB_TERMINAL_STATES: readonly JobState[] = [
  'succeeded',
  'failed',
  'cancelled',
  'interrupted',
];

export function isJobTerminal(state: JobState): boolean {
  return JOB_TERMINAL_STATES.includes(state);
}

/** 任务对外视图；`202` 只代表接受任务，不代表生成完成。 */
export interface JobView {
  jobId: string;
  domain: JobDomain;
  kind: string;
  attempt: number;
  state: JobState;
  result: Record<string, unknown> | null;
  error: ApiErrorEnvelope | null;
}

/** 稳定业务身份 + 乐观锁 + 固定内容修订身份。 */
export interface RevisionIdentity {
  id: string;
  revision: number;
  revisionId: string;
}

/** 成绩单元格状态：有效记录 / 空白 / 缺考 / 免考（绝不把后三者补成 0）。 */
export type ScoreStatus = 'recorded' | 'missing' | 'absent' | 'exempt';

export interface ScoreCell {
  participantId: string;
  itemId: string;
  status: ScoreStatus;
  scoreUnits: number | null;
}

/** 学情观察值（any_loss_v1）；不建立掌握概率或自动评分。 */
export type Observation = 'needs_consolidation' | 'full_credit' | 'incomplete' | 'no_evidence';

/** 教学库文件资产类别。 */
export type AssetKind = 'roster' | 'score_sheet' | 'paper' | 'export' | 'attachment';

/** 受管文件资产的对外引用；`blobKey` 只能是 `blobs/<sha256>` 形式的受管相对键。 */
export interface AssetRef {
  assetId: string;
  kind: AssetKind;
  blobKey: string;
  sha256: string;
  mediaType: string;
  byteSize: number;
  originalName: string;
}

/** 富内容 v2 结构化块；存在时它是内容权威，Markdown 是派生展示。 */
export interface TableCell {
  text: string;
  isHeader: boolean;
  rowSpan: number;
  colSpan: number;
}

export type ContentBlock =
  | { id: string; kind: 'paragraph'; text: string }
  | {
      id: string;
      kind: 'table';
      /** 行优先单元格序列；rowSpan/colSpan 占位（与 HTML 网格一致） */
      cells: TableCell[];
      /** 网格宽度；用于把扁平序列精确还原成行（旧数据可能缺失，需回退启发式） */
      columnCount?: number | null;
    }
  | { id: string; kind: 'formula'; latex?: string | null; ommlXml?: string | null }
  | { id: string; kind: 'image'; assetId: string; width: number; height: number };

export interface SharedMaterial {
  id: string;
  blocks: ContentBlock[];
}

export interface RichAsset {
  assetId: string;
  sha256: string;
  mediaType: string;
}

export interface RichOrigin {
  originalAssetId: string;
  originalSha256: string;
  sourceLocator: Record<string, unknown>;
}

export interface RichContentV2 {
  version: 2;
  sharedMaterials: SharedMaterial[];
  stemBlocks: ContentBlock[];
  optionBlocks: Record<string, ContentBlock[]>;
  answerBlocks: ContentBlock[];
  explanationBlocks: ContentBlock[];
  assets: RichAsset[];
  origin: RichOrigin;
}
