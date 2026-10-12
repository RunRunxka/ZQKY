/**
 * 施测与成绩模块（`/assessments/**`）的**公共最小契约**（重建期最小解耦，R5-FE 2026-10-11）。
 *
 * 归档实现在冻结契约 `@/contracts/teaching-loop`：模块的班级/学生/原卷契约从那里取
 * `AssetRef`，原卷知识点建议从 `@/services/workflow-jobs-api` 观察 `teaching` 域任务
 * （`JobView` / `isJobTerminal`）。重建期该共享契约尚未回归（教学闭环其余模块仍在按需取回），
 * 而本模块只用到其中极小一部分，因此这里按后端 `app/contracts/teaching_loop.py` 的
 * `AssetRef` 与 `app/contracts/workflow_jobs.py` 的 `JobView` **逐字段同构**地声明最小子集，
 * **不新增字段、不发明语义**：服务端多返回的字段前端忽略。
 *
 * 待 `@/contracts/teaching-loop`（与 `@/services/workflow-jobs-api`）回归后，本文件应删除，
 * `@/contracts/roster`、`@/contracts/papers` 与 `features/assessments/jobs.ts` 改回从那里导入，
 * 避免长期存在第二份任务契约（与 R3-FE 的 `@/contracts/knowledge`、R4-FE 的
 * `@/contracts/question-bank` 顶部同一条说明一致）。
 */

/* ------------------------------------------------------------------ 受管资产 */

/** 资产业务域：本模块只用名单（`roster`）与试卷（`paper`），其余取值保留给后续模块。 */
export type AssetKind = 'roster' | 'score_sheet' | 'paper' | 'export' | 'attachment';

/** 受管资产引用（与后端 `AssetRef` 逐字段一致；`originalName` 用于显示上传原文件名）。 */
export interface AssetRef {
  assetId: string;
  kind: AssetKind;
  blobKey: string;
  sha256: string;
  mediaType: string;
  byteSize: number;
  originalName: string;
}

/* ------------------------------------------------------------------ 后台任务视图 */

/** 任务所属业务域（本模块只观察 `teaching`；其余取值保留给后续模块）。 */
export type TeachingJobDomain = 'knowledge' | 'question' | 'teaching';

/** 任务状态机六态（与后端 `JobState` 一致）。 */
export type TeachingJobState =
  | 'queued'
  | 'running'
  | 'succeeded'
  | 'failed'
  | 'cancelled'
  | 'interrupted';

export const TEACHING_JOB_TERMINAL_STATES: readonly TeachingJobState[] = [
  'succeeded',
  'failed',
  'cancelled',
  'interrupted',
];

export function isTeachingJobTerminal(state: TeachingJobState): boolean {
  return TEACHING_JOB_TERMINAL_STATES.includes(state);
}

/** 任务错误信封（后端 `ApiErrorEnvelope` 子集：只缺 `details`，服务端可不返回）。 */
export interface TeachingJobError {
  code: string;
  message: string;
  requestId?: string;
  retryable?: boolean;
}

/** 后台任务视图（与后端 `JobView` 逐字段一致）。 */
export interface TeachingJobView {
  jobId: string;
  domain: TeachingJobDomain;
  kind: string;
  attempt: number;
  state: TeachingJobState;
  result: Record<string, unknown> | null;
  error: TeachingJobError | null;
}
