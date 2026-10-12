/**
 * 学情分析契约（R6-FE 2026-10-11）。
 *
 * 视图类型与后端 `apps/api/app/contracts/b4.py` / `scores.py` 及本卡冻结的新端点
 * （knowledge-stats / student-knowledge / distribution / report）逐字段镜像；
 * 服务端多返回的字段前端忽略，字段缺失时按调用处的显式兜底处理，不猜造数据。
 *
 * 与归档（`archive-full-v1-20261011`）的差异：归档把学情报告契约放在 `@/contracts/b4`、
 * 成绩契约放在 `@/contracts/scores`，两者分别依赖 `teaching-loop` 的任务/资产/状态类型。
 * 重建期这些共享契约尚未回归，这里按后端契约**同构**声明学情分析实际用到的最小集合，
 * 不新增字段、不发明语义；待共享契约回归后应改为从那里导入并删除重复声明。
 */

import type { ErrorIssue } from '@/contracts/api';

/* ================================================================ 通用 */

export interface Page<T> {
  items: T[];
  total: number;
  offset: number;
  limit: number;
}

/* ================================================================ 学情报告（analysis-runs） */

/** 成绩四态：有效记录 / 空白 / 缺考 / 免考（绝不把后三者补成 0）。 */
export type ScoreStatus = 'recorded' | 'missing' | 'absent' | 'exempt';

export const SCORE_STATUSES: readonly ScoreStatus[] = ['recorded', 'missing', 'absent', 'exempt'];

/** 受管资产的最小视图（对照归档 `teaching-loop.AssetRef`；这里只用到文件名与大小）。 */
export interface AssetRef {
  assetId: string;
  sha256: string;
  mediaType: string;
  byteSize: number;
  originalName: string;
}

/** 报告冻结人次（学生姓名只用于本机展示；AI 评价由后端脱敏后进模型）。 */
export interface FrozenParticipant {
  participantId: string;
  studentId: string;
  studentNo: string | null;
  name: string;
  classId: string;
  className: string | null;
  attemptNo: number;
  attendance: 'present' | 'absent' | 'exempt';
}

/** 报告冻结知识点。 */
export interface FixedKnowledge {
  knowledgePointId: string;
  knowledgeRevisionId: string;
  name: string;
  role: 'primary' | 'secondary';
}

export interface SelectionSnapshot {
  selectedParticipantIds: string[];
  uniqueStudentCount: number;
  participantCount: number;
  leafCount: number;
  stateCounts: Record<ScoreStatus, number>;
}

export interface AnalysisRunView {
  runId: string;
  assessmentId: string;
  scoreRevisionId: string;
  paperRevisionId: string;
  /** 原卷标题；缺失（null）时界面回落报告短号，不伪造名称。 */
  paperTitle?: string | null;
  reportReady: boolean;
  archivedAt?: string | null;
  createdAt: string;
  /** 冻结人次快照：报告列表的班级筛选据此过滤（服务端事实，不做姓名推断）。 */
  participants?: FrozenParticipant[];
  knowledgePoints?: FixedKnowledge[];
  selectionSnapshot?: SelectionSnapshot;
}

export type AnalysisRunList = Page<AnalysisRunView>;

/** 小题得分聚合（`GET /analysis-runs/{run_id}/item-stats`）：题号 × 全班得分率。 */
export interface ItemStatView {
  itemId: string;
  itemPath: string;
  maxScoreUnits: number;
  recordedCount: number;
  totalScoreUnits: number;
  /** 0–1；null = 无有效作答（界面显示「无有效作答」，不补 0）。 */
  scoreRate: number | null;
}

/** 知识点得分率（`GET /analysis-runs/{run_id}/knowledge-stats`，冻结形状，按 scoreRate 降序）。 */
export interface KnowledgeStatItem {
  knowledgePointId: string;
  name: string;
  path: string | null;
  scoreRate: number;
  questionCount: number;
}

export interface KnowledgeStatsResponse {
  items: KnowledgeStatItem[];
}

/** 学生 × 知识点矩阵（`GET /analysis-runs/{run_id}/student-knowledge`，冻结形状）。 */
export interface StudentKnowledgeCell {
  knowledgePointId: string;
  /** 0–1；null = 尚无有效依据（界面显示「尚无」，不显示 0）。 */
  scoreRate: number | null;
  questionCount: number;
}

export interface StudentKnowledgeRow {
  /** 一律展示后端给出的 label，前端不做姓名推断。 */
  label: string;
  cells: StudentKnowledgeCell[];
}

export interface StudentKnowledgeResponse {
  knowledgePoints: { knowledgePointId: string; name: string }[];
  students: StudentKnowledgeRow[];
}

/** 得分率分数段分布（`GET /analysis-runs/{run_id}/distribution`，冻结形状）。 */
export interface DistributionBucket {
  label: string;
  count: number;
}

export interface DistributionResponse {
  buckets: DistributionBucket[];
}

/* ---------------------------------------------------------------- AI 评价与教师备注 */

export interface NoteRequest {
  submissionId: string;
  participantId?: string | null;
  knowledgePointId?: string | null;
  note: string;
}

export interface NoteView {
  noteId: string;
  runId: string;
  participantId: string | null;
  knowledgePointId: string | null;
  note: string;
  createdAt: string;
  replayed: boolean;
}

/* ---------------------------------------------------------------- 导出分析报告 */

/** 导出产物标识（`POST /analysis-runs/{run_id}/report` → 201 的 `artifact`）。 */
export interface ExportArtifactRef {
  artifactId: string;
  fileName: string;
  byteSize: number;
}

export interface AnalysisReportReceipt {
  artifact: ExportArtifactRef;
}

/* ================================================================ 施测与班级（筛选与导入目标） */

export interface AssessmentSummaryView {
  assessmentId: string;
  paperId: string;
  paperRevisionId: string;
  paperTitle: string;
  title: string;
  heldOn: string;
  revision: number;
  participantCount: number;
  classIds: string[];
  activeScoreRevisionId?: string | null;
}

export interface AssessmentList {
  items: AssessmentSummaryView[];
  total: number;
  offset: number;
  limit: number;
}

export interface AssessmentParticipantView {
  participantId: string;
  studentId: string;
  studentNoSnapshot?: string | null;
  nameSnapshot: string;
  classId: string;
  attemptNo: number;
  attendance: 'present' | 'absent' | 'exempt';
}

export interface AssessmentDetailView {
  assessment: AssessmentSummaryView;
  participants: AssessmentParticipantView[];
}

export interface ClassView {
  id: string;
  name: string;
  code?: string | null;
}

export interface ClassList {
  items: ClassView[];
  total: number;
  offset: number;
  limit: number;
}

/* ---------------------------------------------------------------- 原卷修订内容（列映射的计分叶） */

export interface PaperItemView {
  itemId: string;
  parentItemId: string | null;
  questionNo: string;
  ordinal: number;
  isScored: boolean;
  maxScoreUnits: number | null;
  content?: Record<string, unknown>;
}

export interface PaperRevisionContentView {
  paperId: string;
  paperRevisionId: string;
  items: PaperItemView[];
}

/* ================================================================ 小题分成绩单导入（成绩 v1） */

export type ScoreImportState = 'uploaded' | 'reviewing' | 'confirmed' | 'failed' | 'cancelled';
export type ScoreRevisionState = 'draft' | 'confirmed';

export interface ScoreItemColumn {
  itemId: string;
  /** 原表列字母，如 "D" */
  column: string;
}

export interface ScoreColumnMapping {
  workSheet: string;
  /** 仅用于原表表头定位展示；0 = 无表头 */
  headerRow?: number;
  studentNoColumn?: string | null;
  nameColumn?: string | null;
  totalColumn?: string | null;
  attendanceColumn?: string | null;
  itemColumns: ScoreItemColumn[];
}

export interface ScoreRawCellView {
  row: number;
  column: string;
  /** 公式视图文本（公式单元格为公式文本） */
  text?: string;
  /** data_only 缓存值文本 */
  cachedText?: string;
  isFormula?: boolean;
  originalText?: string;
  originalCachedText?: string;
  correctedText?: string | null;
  effectiveStatus?: ScoreStatus | null;
  scoreUnits?: number | null;
}

export interface ScoreImportRowView {
  rowNo: number;
  participantId?: string | null;
  participantName?: string | null;
  /** 教师显式标记「不属于本次施测」并已忽略的行（可撤销；不参与矩阵与阻断） */
  ignored?: boolean;
  /** 歧义/未匹配行的可选取人次（供教师显式消歧） */
  candidates?: string[];
  cells?: ScoreRawCellView[];
  issues?: ErrorIssue[];
}

export interface ScoreCellPatch {
  /** 原表物理坐标（与题目映射无关） */
  row: number;
  column: string;
  text?: string;
}

export interface ScoreImportRowPatch {
  rowNo: number;
  participantId?: string | null;
  ignored?: boolean;
  cells?: ScoreCellPatch[];
}

export interface ScoreImportRefreshRequest {
  expectedImportRevision: number;
  expectedAssessmentRevision: number;
  baseScoreRevisionId: string | null;
}

export interface ScoreAbsenceAcknowledgement {
  classId: string;
  participantIds: string[];
}

export interface ScoreMissingAcknowledgement {
  participantIds: string[];
  cellCount: number;
}

export interface ScoreImportView {
  importId: string;
  assessmentId: string;
  assessmentTitle: string;
  state: ScoreImportState;
  revision: number;
  previewVersion: number;
  fileAsset: AssetRef;
  mapping?: ScoreColumnMapping | null;
  baseScoreRevisionId?: string | null;
  warnings?: string[];
  issues?: ErrorIssue[];
  rowCount: number;
  resolvedRowCount: number;
  /** 教师显式忽略（「不属于本次施测」）的行数；不参与矩阵、阻断与承认 */
  ignoredRowCount?: number;
  missingCellCount: number;
  /** 当前 previewVersion 有效矩阵的服务端权威范围；缺失时不能确认。 */
  requiredAcknowledgements?: {
    absences: ScoreAbsenceAcknowledgement[];
    missing: ScoreMissingAcknowledgement | null;
  };
  createdAt: string;
  updatedAt: string;
}

export interface ScoreImportRowList {
  items: ScoreImportRowView[];
  total: number;
  offset: number;
  limit: number;
}

export interface ScoreImportSummary {
  importId: string;
  assessmentId: string;
  /** 只读派生：上传成绩表的原文件名；关联缺失时服务端给 null（不伪造名称）。 */
  uploadedFileName: string | null;
  state: ScoreImportState;
  revision: number;
  rowCount: number;
  createdAt: string;
  updatedAt: string;
}

export interface ScoreImportList {
  items: ScoreImportSummary[];
  total: number;
  offset: number;
  limit: number;
}

/** 一次生效的导入校对补丁；`mapping`/`rows` 至少提供一项。 */
export interface ScoreImportPatchRequest {
  expectedRevision: number;
  mapping?: ScoreColumnMapping | null;
  rows?: ScoreImportRowPatch[];
}

export interface ScoreImportDiscardRequest {
  expectedRevision: number;
}

export interface ScoreImportConfirmRequest {
  expectedImportRevision: number;
  expectedAssessmentRevision: number;
  baseScoreRevisionId?: string | null;
  previewVersion: number;
  submissionId: string;
  absences?: ScoreAbsenceAcknowledgement[];
  missing?: ScoreMissingAcknowledgement | null;
}

export interface ScoreImportConfirmResult {
  importId: string;
  state: ScoreImportState;
  revisionId: string;
  assessmentRevision: number;
  activeScoreRevisionId: string;
  replayed?: boolean;
}

export interface ScoreImportDeleteResult {
  deleted: boolean;
  importId: string;
}

export interface ScoreRevisionView {
  revisionId: string;
  assessmentId: string;
  paperRevisionId?: string;
  version: number;
  state: ScoreRevisionState;
  confirmedAt?: string | null;
  createdAt: string;
}

export interface ScoreRevisionList {
  items: ScoreRevisionView[];
  total: number;
}
