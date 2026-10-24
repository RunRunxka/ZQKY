/**
 * 教案工作台契约镜像（R7-FE，2026-10-12）。
 *
 * 与后端 `apps/api/app/contracts/lesson_plans.py`（归档 R7-BE 忠实取回）逐字段对应；
 * 修改任一侧必须同步另一侧。本文件只声明工作台用到的子集：
 *
 * - **冻结端点**（本卡）：`POST /lesson-plans`、`GET /lesson-plans/{id}`、
 *   `PATCH /lesson-plans/{id}/draft`（CAS/版本冲突语义沿用归档）、`GET /lesson-plans`、
 *   `POST /lesson-plans/generation-stream`（SSE，事件协议沿用归档 lesson_streaming）、
 *   `POST /lesson-plans/{id}/export` → 202 `{artifact:{artifactId,fileName}}`、
 *   `GET /api/v1/export-artifacts/{artifactId}/download`；
 * - 数据正文 `LessonPlanData` / `ProcessItemV2` 与归档 `apps/web/src/contracts/lesson-plans.ts`
 *   完全一致：旧字段（title/totalLessons/currentLessonNo/lessonTypes/otherTypeText/process）
 *   一律保留，只增不减，缺省向后兼容；
 * - **导出装配请求**（`LessonExportRequest` 的 `style` / `modules`）是本卡新增的前端→后端装配
 *   载荷：后端导出为「后端组装」（前端只触发+下载），预览所见的字体/间距/模块顺序必须随导出
 *   一起送达，否则导出的 docx 与预览不一致。R7-BE 需据此定稿（见交付「未决问题」）。
 */

/* ------------------------------------------------------------------ 正文数据（冻结） */

export type LessonType = 'new' | 'review' | 'exercise' | 'experiment' | 'other';

export interface ProcessItem {
  id: string;
  stage: string;
  design: string;
  secondary: string;
}

/** 基本信息表（一）：课程名称/授课教师/授课对象/授课学时/授课时间/授课地点/教学章节。 */
export interface LessonBasicInfo {
  courseName: string;
  teacher: string;
  audience: string;
  hours: string;
  teachingTime: string;
  location: string;
  chapter: string;
}

/** 教学分析表（二）。 */
export interface LessonTeachingAnalysis {
  learning: string;
  textbook: string;
  content: string;
  ideological: string;
}

/** 教学策略表（四）。 */
export interface LessonTeachingStrategy {
  designThinking: string;
  teachingFlow: string;
  methods: string;
}

/** 评价反馈表（六）。 */
export interface LessonEvaluationFeedback {
  afterClassTest: string;
  homework: string;
}

export type ProcessPhase = 'warmup' | 'introduction' | 'exploration' | 'practice' | 'conclusion';

/** 教学过程行（五）：三列 + 阶段小标题（`phaseLabel`）。 */
export interface ProcessItemV2 {
  id: string;
  phase: ProcessPhase;
  phaseLabel: string;
  title: string;
  teacherActivity: string;
  studentActivity: string;
  intent: string;
}

export interface LessonPlanData {
  /** 课题名称（封面标题与页眉同名）。 */
  title: string;
  /** 旧字段：本课题总课时（v2 模板不显示，保留兼容，不丢数据）。 */
  totalLessons: string;
  /** 旧字段：本节课时（同上）。 */
  currentLessonNo: string;
  /** 旧字段：课型（同上）。 */
  lessonTypes: LessonType[];
  /** 旧字段：其它课型说明（同上）。 */
  otherTypeText: string;
  /** 三、教学目标（知识/能力/思政 由工作台 codec 编码进本字段，见 model/objectives.ts）。 */
  coreCompetencies: string;
  /** 三、教学目标 · 教学重点/难点。 */
  keyPoints: string;
  /** 四、教学策略 · 教学设计（板书/思路）。 */
  teachingDesign: string;
  /** 旧字段：教学过程（v1 两列）；`processV2` 为空时由它映射展示。 */
  process: ProcessItem[];
  /** 六、评价反馈 · 练习与作业。 */
  exercises: string;
  /** 七、教学反思。 */
  reflection: string;
  basic?: LessonBasicInfo | null;
  analysis?: LessonTeachingAnalysis | null;
  strategy?: LessonTeachingStrategy | null;
  evaluation?: LessonEvaluationFeedback | null;
  /** 五、教学过程：三列 + 阶段。 */
  processV2?: ProcessItemV2[];
}

/** 本地草稿信封（`schemaVersion=1` 与归档一致，旧草稿可继续读取）。 */
export interface DraftEnvelope {
  schemaVersion: 1;
  revision: number;
  updatedAt: string;
  data: LessonPlanData;
  /** R7 新增：排版偏好与模块布局（缺省时取工作台默认值，旧草稿不受影响）。 */
  style?: LessonWorkbenchStyleWire;
  modules?: LessonWorkbenchModuleWire[];
  removedModules?: LessonWorkbenchModuleWire[];
}

/* ------------------------------------------------------------------ 服务端视图（冻结子集） */

export interface LessonRevisionView {
  protocolVersion?: number;
  lessonPlanId: string;
  revisionId: string;
  version: number;
  data: LessonPlanData;
  contentHash?: string;
  source?: 'manual' | 'rule' | 'import_local' | 'ai_applied';
  reviewState?: 'unreviewed' | 'reviewed';
  createdAt?: string;
}

export interface LessonView {
  protocolVersion?: number;
  lessonPlanId: string;
  subjectId?: string;
  classId?: string;
  /** CAS 修订号：PATCH draft 的 `expectedRevision` 取这里。 */
  revision: number;
  currentRevisionId: string;
  currentRevision: LessonRevisionView;
  replayed?: boolean;
}

export interface LessonSummary {
  lessonPlanId: string;
  title: string;
  revision: number;
  currentRevisionId?: string;
  source?: 'manual' | 'rule' | 'import_local' | 'ai_applied';
  updatedAt: string;
}

export interface LessonSummaryPage {
  items: LessonSummary[];
  total: number;
  offset: number;
  limit: number;
}

/**
 * 教案删除回执（`DELETE /lesson-plans/{id}?expectedRevision=N` 的 200 体）。
 *
 * 删除只清教案自身的历史（修订 / 生成输入 / AI 候选 / 校对 / 决定），不动学生、班级、
 * 成绩与学情报告；教案不存在 → 404，乐观锁不符 → 409，被教案五表之外的引用挡住 → 409
 * `LESSON_IN_USE`（当前无外部引用表，属结构性防线）。
 */
export interface LessonDeleteResult {
  deleted: boolean;
  lessonPlanId: string;
  removedRevisions: number;
  removedProposals: number;
  removedInputs: number;
}

/**
 * `POST /lesson-plans`：教案必须属于**某班某科**（后端 `LessonCreateRequest` 要求
 * `subjectId`/`classId` 非空，且 `classId` 是真班级），因此创建前要在「本地教案」对话框里
 * 选好归属；缺它们后端 422 `LESSON_INVALID`（"教案请求字段不符合契约"）。
 */
export interface LessonCreateRequest {
  submissionId: string;
  /** 学科 id（来自 `GET /textbook-taxonomy` 的 subjects）。 */
  subjectId: string;
  /** 班级 id（来自 `GET /classes`；教案随班级归档/删除守卫一起被引用）。 */
  classId: string;
  /**
   * 学情来源上下文：手工新建显式送 `null`（后端 `LessonCreateRequest.context` 是**必填键**，
   * 只是允许为 null；缺键会 422 "教案请求字段不符合契约"——2026-10-13 修）。
   */
  context: null;
  data: LessonPlanData;
}

/** PATCH `/lesson-plans/{id}/draft`：字段与归档 `LessonSaveRequest` 同构（幂等 + CAS）。 */
export interface LessonDraftPatchRequest {
  submissionId: string;
  expectedRevision: number;
  data: LessonPlanData;
  context: null;
  source: 'manual';
}

/* ------------------------------------------------------------------ 工作台排版与模块（装配载荷） */

export type LessonFontId = 'puhuiti' | 'misans' | 'noto-sans-sc' | 'source-han-serif';

/** 左栏「排版」「间距」的受控值；预览与导出都必须使用同一份。 */
export interface LessonWorkbenchStyleWire {
  fontId: LessonFontId;
  /** 正文基础字号（px）。 */
  baseSize: number;
  /** 模块标题字号（px）。 */
  headingSize: number;
  /** 字段标签字号（px）。 */
  labelSize: number;
  /** 行高（1–2）。 */
  lineHeight: number;
  /** 页边距（px，四边同值）。 */
  pageMargin: number;
  /** 模块间距（px）。 */
  moduleGap: number;
  /** 段落间距（px）。 */
  paragraphGap: number;
}

/** 模块布局条目（内置模块或自定义模块）。 */
export interface LessonWorkbenchModuleWire {
  id: string;
  kind: 'builtin' | 'custom';
  /** 内置模块键（kind=builtin 时必有）。 */
  builtinId?: string;
  label: string;
  hidden?: boolean;
  /** 自定义模块正文。 */
  body?: string;
}

/** 导出装配请求：正文 + 预览排版 + 模块顺序/显隐（后端据此组装 docx，前端只触发+下载）。 */
export interface LessonExportRequest {
  data: LessonPlanData;
  style: LessonWorkbenchStyleWire;
  modules: LessonWorkbenchModuleWire[];
  /**
   * 各模块在**正文**中的起始页码（1 起），由预览分页算出。
   * 后端据此写 docx 目录，避免预览与导出各用一套估算。
   */
  sectionPages?: Record<string, number>;
}

export interface ExportArtifactRef {
  artifactId: string;
  fileName: string;
}

/** `POST /lesson-plans/{id}/export` → 202 接受任务，不代表文件已生成。 */
export interface LessonExportReceipt {
  artifact: ExportArtifactRef;
}

/**
 * 上传学情文件回执（`POST /lesson-plans/source-uploads`，2026-10-13 补齐后端实现）。
 *
 * 只接受可提取文本的文档（.docx/.pdf/.txt/.md）；成绩表类（.xlsx/.xls/.csv）由服务端 422
 * 并给出「去学情分析生成报告、用『分析报告』来源」的指引（含姓名的原始表格不进模型）。
 */
export interface LessonSourceUpload {
  /** 受管资产 id；生成流以它为 `sourceAssetRef` 读回材料文本。 */
  assetRef: string;
  fileName: string;
  mediaType?: string;
  byteSize?: number;
  sha256?: string;
}

/* ------------------------------------------------------------------ 生成流（归档协议） */

export type LessonStreamModuleKey =
  | 'analysis'
  | 'objectives'
  | 'strategy'
  | 'process'
  | 'exercises'
  | 'evaluation'
  | 'reflection';

export const LESSON_STREAM_MODULE_KEYS: readonly LessonStreamModuleKey[] = [
  'analysis',
  'objectives',
  'strategy',
  'process',
  'exercises',
  'evaluation',
  'reflection',
];

/** 知识点选择（`GET /knowledge-points?scope=subject`）后的最小投影。 */
export interface LessonKnowledgePointRef {
  id: string;
  name: string;
}
