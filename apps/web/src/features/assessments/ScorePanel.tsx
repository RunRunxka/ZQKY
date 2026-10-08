'use client';

/**
 * 第四步「成绩」（重点）：上传 → 列映射 → 行校对 → 预览承认 → 确认入库。
 *
 * - 上传只送教师原始 XLSX/CSV（multipart）；原件为受管资产，服务端读表保留物理行列；
 * - 列映射固定到原卷的**计分叶**（未映射的叶在确认时按 missing 处理，必须被承认覆盖）；
 * - 行校对在原表物理坐标上做（行号 + 列字母），明细见 `ScoreImportReview`；
 * - 确认是逻辑确认：`submissionId` + 原样载荷冻结，结果未知时原样重试；
 * - 409/422 的处理在 review 组件里：保留编辑/校对并显式刷新对照。
 */

import { useEffect, useRef, useState } from 'react';
import { RefreshCw, Upload } from 'lucide-react';
import type { ErrorIssue } from '@/contracts/api';
import type {
  ScoreColumnMapping,
  ScoreImportState,
  ScoreImportSummary,
  ScoreImportView,
  ScoreItemColumn,
} from '@/contracts/scores';
import {
  createScoreImport,
  discardScoreImport,
  getAssessment,
  getPaperRevisionContent,
  getScoreImport,
  listScoreImports,
  listScoreRevisions,
  patchScoreImport,
  refreshScoreImport,
} from '@/services/assessments-api';
import { asApiError, useAsyncResource } from './hooks';
import { issueLocationLabel, leafLabel, scoreImportStateChipClass, scoreImportStateLabel, scoredLeafItems, shortId } from './labels';
import { ScoreImportReview } from './ScoreImportReview';
import { ScoreStatusLegend } from './ScoreStatusBadge';

const COLUMN_PATTERN = /^[A-Za-z]{1,3}$/;

/** 未确认批次可放弃；`confirmed` 已入库（服务端 409），`cancelled` 已放弃。 */
const DISCARDABLE_IMPORT_STATES: readonly ScoreImportState[] = ['uploaded', 'reviewing', 'failed'];

interface MappingDraft {
  workSheet: string;
  headerRow: number;
  studentNoColumn: string;
  nameColumn: string;
  attendanceColumn: string;
  totalColumn: string;
  itemColumns: Record<string, string>;
}

const EMPTY_MAPPING: MappingDraft = {
  workSheet: '',
  headerRow: 1,
  studentNoColumn: '',
  nameColumn: '',
  attendanceColumn: '',
  totalColumn: '',
  itemColumns: {},
};

function mappingFromView(view: ScoreImportView | null): MappingDraft {
  if (!view?.mapping) return EMPTY_MAPPING;
  return {
    workSheet: view.mapping.workSheet,
    headerRow: view.mapping.headerRow ?? 0,
    studentNoColumn: view.mapping.studentNoColumn ?? '',
    nameColumn: view.mapping.nameColumn ?? '',
    attendanceColumn: view.mapping.attendanceColumn ?? '',
    totalColumn: view.mapping.totalColumn ?? '',
    itemColumns: Object.fromEntries(
      view.mapping.itemColumns.map((entry) => [entry.itemId, entry.column]),
    ),
  };
}

export function ScorePanel({
  assessmentId,
  onOpenHistory,
  refreshToken,
  onChanged,
}: {
  assessmentId: string | null;
  onOpenHistory: () => void;
  refreshToken: number;
  onChanged: () => void;
}) {
  const [localRefresh, setLocalRefresh] = useState(0);
  /** 只刷新原表行（同一批次，不清空校对草稿）。 */
  const [rowsRefresh, setRowsRefresh] = useState(0);
  const [selectedImportId, setSelectedImportId] = useState<string | null>(null);
  const [mappingDraft, setMappingDraft] = useState<MappingDraft>(EMPTY_MAPPING);
  const [mappingBusy, setMappingBusy] = useState(false);
  const [mappingError, setMappingError] = useState<string | null>(null);
  const [mappingNotice, setMappingNotice] = useState<string | null>(null);
  const [mappingIssues, setMappingIssues] = useState<ErrorIssue[]>([]);
  const mappingDirty = useRef(false);
  const [mappingHasEdits, setMappingHasEdits] = useState(false);
  const [savedMappingPreview, setSavedMappingPreview] = useState<{ revision: number; previewVersion: number } | null>(null);
  const mappingGeneration = useRef(0);
  const mappingBusyRef = useRef(false);
  const [previewBusy, setPreviewBusy] = useState(false);
  const [previewError, setPreviewError] = useState<string | null>(null);
  const [previewNotice, setPreviewNotice] = useState<string | null>(null);
  const operation = useRef({ mounted: false, epoch: 0 });
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [workSheet, setWorkSheet] = useState('');
  const [baseSelection, setBaseSelection] = useState('');
  /** 放弃批次的写操作身份（禁用按钮防重入）与错误提示。 */
  const [discardBusyId, setDiscardBusyId] = useState<string | null>(null);
  const [discardError, setDiscardError] = useState<string | null>(null);
  const discardBusyRef = useRef(false);

  const detail = useAsyncResource(
    (signal) => (assessmentId ? getAssessment(assessmentId, signal) : Promise.resolve(null)),
    `assessments-score-assessment|${assessmentId ?? 'none'}`,
  );

  const imports = useAsyncResource(
    (signal) =>
      assessmentId
        ? listScoreImports({ assessmentId, limit: 50 }, signal)
        : Promise.resolve({ items: [], total: 0, offset: 0, limit: 50 }),
    `assessments-score-imports|${assessmentId ?? 'none'}|${refreshToken}|${localRefresh}`,
  );

  const importSummaries: ScoreImportSummary[] = imports.lastData?.items ?? [];

  // 选中批次：用户选择优先（列表刷新期间不丢选择，避免校对面板被卸载）；否则用最新批次
  const defaultImportId = importSummaries[0]?.importId ?? null;
  const activeImportId = selectedImportId ?? defaultImportId;
  useEffect(() => {
    // 首次自动选择也固定身份：列表刷新不应短暂变成 none，误清在途后的新编辑。
    if (selectedImportId === null && defaultImportId) setSelectedImportId(defaultImportId);
  }, [selectedImportId, defaultImportId]);

  useEffect(() => {
    const operationState = operation.current;
    operationState.mounted = true;
    operationState.epoch += 1;
    setMappingBusy(false);
    mappingBusyRef.current = false;
    mappingGeneration.current += 1;
    setMappingHasEdits(false);
    setSavedMappingPreview(null);
    setMappingError(null);
    setMappingIssues([]);
    setMappingNotice(null);
    setUploadBusy(false);
    setPreviewBusy(false);
    setPreviewError(null);
    setPreviewNotice(null);
    mappingDirty.current = false;
    return () => {
      operationState.mounted = false;
      operationState.epoch += 1;
    };
  }, [assessmentId, activeImportId]);

  function current(token: number): boolean {
    return operation.current.mounted && operation.current.epoch === token;
  }

  const importView = useAsyncResource(
    (signal) =>
      activeImportId ? getScoreImport(activeImportId, signal) : Promise.resolve(null),
    `assessments-score-import|${activeImportId ?? 'none'}`,
  );
  const view = importView.lastData;
  const mappingPreviewPending = savedMappingPreview !== null && (!view ||
    view.revision < savedMappingPreview.revision || view.previewVersion < savedMappingPreview.previewVersion);

  const revisions = useAsyncResource(
    (signal) =>
      assessmentId
        ? listScoreRevisions(assessmentId, signal)
        : Promise.resolve({ items: [], total: 0 }),
    `assessments-score-revisions|${assessmentId ?? 'none'}|${refreshToken}|${localRefresh}`,
  );
  const confirmedRevisions = (revisions.lastData?.items ?? []).filter(
    (revision) => revision.state === 'confirmed',
  );

  const paperContent = useAsyncResource(
    (signal) => {
      const assessment = detail.lastData?.assessment;
      if (!assessment) return Promise.resolve(null);
      return getPaperRevisionContent(assessment.paperId, assessment.paperRevisionId, signal);
    },
    `assessments-score-paper|${detail.lastData?.assessment.paperRevisionId ?? 'none'}`,
  );
  const leaves = paperContent.lastData ? scoredLeafItems(paperContent.lastData.items) : [];
  const leafCount = leaves.length;

  useEffect(() => {
    if (!mappingDirty.current && !mappingPreviewPending) setMappingDraft(mappingFromView(importView.lastData ?? null));
  }, [importView.lastData, mappingPreviewPending]);

  function editMapping(update: (previous: MappingDraft) => MappingDraft) {
    mappingDirty.current = true;
    mappingGeneration.current += 1;
    setMappingHasEdits(true);
    setMappingDraft(update);
  }

  function reloadAll() {
    setLocalRefresh((value) => value + 1);
  }

  /**
   * 显式刷新对照：批次视图与施测读回最新（**同一 key 的 reload**，不清空校对草稿），
   * 原表行按 `rowsRefresh` 在原组件内重读。
   */
  function reloadForCompare() {
    importView.reload();
    detail.reload();
    setRowsRefresh((value) => value + 1);
  }

  async function submitUpload() {
    if (!assessmentId || !file) {
      setUploadError('请选择要上传的成绩表格文件（XLSX/CSV）。');
      return;
    }
    setUploadBusy(true);
    const token = operation.current.epoch;
    setUploadError(null);
    try {
      const created = await createScoreImport(assessmentId, file, {
        workSheet: workSheet.trim() || null,
        baseScoreRevisionId: baseSelection || null,
      });
      if (!current(token)) return;
      setFile(null);
      setWorkSheet('');
      setBaseSelection('');
      setSelectedImportId(created.importId);
      reloadAll();
      onChanged();
    } catch (cause) {
      if (!current(token)) return;
      const error = cause as { code?: string; message?: string; details?: { currentRevision?: number } };
      setUploadError(
        `上传失败（${error.code ?? 'UNKNOWN'}）：${error.message ?? '请求失败'}${
          error.details?.currentRevision ? `（当前版本 ${error.details.currentRevision}）` : ''
        } 已选文件保留，可直接重试。`,
      );
    } finally {
      if (current(token)) setUploadBusy(false);
    }
  }

  async function saveMapping() {
    if (!view || mappingBusyRef.current) return;
    const editGeneration = mappingGeneration.current;
    setMappingBusy(true);
    const token = operation.current.epoch;
    setMappingError(null);
    setMappingIssues([]);
    setMappingNotice(null);
    const itemColumns: ScoreItemColumn[] = Object.entries(mappingDraft.itemColumns)
      .filter(([, column]) => column.trim() !== '')
      .map(([itemId, column]) => ({ itemId, column: column.trim().toUpperCase() }));
    const invalidLeaf = itemColumns.find((entry) => !COLUMN_PATTERN.test(entry.column));
    const identities = [mappingDraft.studentNoColumn, mappingDraft.nameColumn]
      .map((value) => value.trim().toUpperCase())
      .filter((value) => value !== '');
    if (!mappingDraft.workSheet.trim()) {
      setMappingBusy(false);
      setMappingError('工作表名必填（多工作表 XLSX 必须显式指定）。');
      return;
    }
    if (identities.length === 0) {
      setMappingBusy(false);
      setMappingError('学号列与姓名列至少提供一项（服务端口径）。');
      return;
    }
    const optionalColumns = [mappingDraft.attendanceColumn, mappingDraft.totalColumn]
      .map((value) => value.trim().toUpperCase()).filter(Boolean);
    if ([...identities, ...optionalColumns].some((column) => !COLUMN_PATTERN.test(column)) || invalidLeaf) {
      setMappingBusy(false);
      setMappingError('列必须写成原表列字母（如 A、D、AA），最多 3 个字符。');
      return;
    }
    if (itemColumns.length === 0) {
      setMappingBusy(false);
      setMappingError('至少映射一个计分叶列；未映射的叶会在确认时按 missing 处理。');
      return;
    }
    const mapping: ScoreColumnMapping = {
      ...(view.mapping ?? {}),
      workSheet: mappingDraft.workSheet.trim(),
      headerRow: mappingDraft.headerRow,
      studentNoColumn: mappingDraft.studentNoColumn.trim().toUpperCase() || null,
      nameColumn: mappingDraft.nameColumn.trim().toUpperCase() || null,
      attendanceColumn: mappingDraft.attendanceColumn.trim().toUpperCase() || null,
      totalColumn: mappingDraft.totalColumn.trim().toUpperCase() || null,
      itemColumns,
    };
    mappingBusyRef.current = true;
    try {
      const next = await patchScoreImport(view.importId, {
        expectedRevision: view.revision,
        mapping,
      });
      if (!current(token)) return;
      const savedCurrentEdits = editGeneration === mappingGeneration.current;
      setSavedMappingPreview({ revision: next.revision, previewVersion: next.previewVersion });
      if (savedCurrentEdits) {
        mappingDirty.current = false;
        setMappingHasEdits(false);
        setMappingDraft(mappingFromView(next));
      }
      setMappingNotice(`已保存映射并重算行（批次 r${next.revision}，预览 v${next.previewVersion}）。${
        savedCurrentEdits ? '' : '请求开始后的新映射编辑已保留，仍需另行保存。'
      }`);
      reloadAll();
      // 读回权威视图（同 key）：后续校对/确认必须用重算后的 revision 与 previewVersion
      importView.reload();
    } catch (cause) {
      if (!current(token)) return;
      const error = cause as { code?: string; message?: string; status?: number; details?: { currentRevision?: number; issues?: ErrorIssue[] } };
      setMappingIssues(error.details?.issues ?? []);
      if (error.status === 409) {
        setMappingError(
          `数据已变化，请刷新对照（当前版本 ${
            error.details?.currentRevision ?? '未知'
          }）：${error.message ?? ''} 你的映射编辑已保留。`,
        );
      } else {
        setMappingError(`保存映射失败（${error.code ?? 'UNKNOWN'}）：${error.message ?? '请求失败'}`);
      }
    } finally {
      if (current(token)) {
        mappingBusyRef.current = false;
        setMappingBusy(false);
      }
    }
  }

  async function rebuildPreview() {
    const assessment = detail.lastData?.assessment;
    if (!view || !assessment) return;
    const token = operation.current.epoch;
    setPreviewBusy(true);
    setPreviewError(null);
    setPreviewNotice(null);
    try {
      const next = await refreshScoreImport(view.importId, {
        expectedImportRevision: view.revision,
        expectedAssessmentRevision: assessment.revision,
        baseScoreRevisionId: view.baseScoreRevisionId ?? null,
      });
      if (!current(token)) return;
      setPreviewNotice(`已明确刷新预览（批次 r${next.revision}，预览 v${next.previewVersion}）；请重新核对并承认。`);
      reloadForCompare();
    } catch (cause) {
      if (!current(token)) return;
      const error = asApiError(cause);
      setPreviewError(`刷新预览失败（${error.code}）：${error.message}${error.status === 409
        ? ` 当前版本 ${error.details?.currentRevision ?? '未知'}，请刷新对照；当前编辑已保留。`
        : '当前编辑已保留。'}`);
    } finally {
      if (current(token)) setPreviewBusy(false);
    }
  }

  /**
   * 放弃未确认批次（守卫式 `expectedRevision`）：只置 `cancelled`，批次记录/原件/预览行保留；
   * 已确认批次不可放弃（服务端 409）。成功后刷新批次列表并读回取消状态。
   */
  async function discardImport(summary: ScoreImportSummary) {
    if (discardBusyRef.current) return;
    if (!window.confirm('放弃后批次保留记录但不能再校对/确认。确认放弃该成绩批次？')) return;
    const token = operation.current.epoch;
    discardBusyRef.current = true;
    setDiscardBusyId(summary.importId);
    setDiscardError(null);
    try {
      await discardScoreImport(summary.importId, { expectedRevision: summary.revision });
      if (!current(token)) return;
      if (summary.importId === activeImportId) importView.reload();
      reloadAll();
      onChanged();
    } catch (cause) {
      if (!current(token)) return;
      const error = asApiError(cause);
      setDiscardError(`放弃批次失败（${error.code}）：${error.message}`);
    } finally {
      discardBusyRef.current = false;
      if (current(token)) setDiscardBusyId(null);
    }
  }

  if (!assessmentId) {
    return (
      <div className="assessments-panel" data-testid="assessments-score-panel">
        <p className="space-empty" data-testid="assessments-score-no-assessment">
          <strong>未选择施测</strong>
          <span>先在「施测」步骤创建或选择一个施测，再导入成绩。</span>
        </p>
      </div>
    );
  }

  return (
    <div className="assessments-panel" data-testid="assessments-score-panel">
      <section className="assessments-subpanel" aria-label="上传成绩表">
        <div className="assessments-subpanel-head">
          <h3>
            <Upload size={15} aria-hidden /> 上传成绩表（教师原始 XLSX/CSV）
          </h3>
          <button className="space-button" onClick={reloadAll}>
            <RefreshCw size={13} aria-hidden /> 刷新
          </button>
        </div>

        {detail.state.phase === 'failed' && (
          <div className="space-banner error" role="alert" data-testid="assessments-score-assessment-error">
            施测详情读取失败（{detail.state.error.code}）：{detail.state.error.message}
          </div>
        )}
        {detail.lastData && (
          <p className="assessments-hint">
            施测「{detail.lastData.assessment.title}」· 原卷「
            {detail.lastData.assessment.paperTitle
              || shortId(detail.lastData.assessment.paperRevisionId)}
            」 · 参测 {detail.lastData.assessment.participantCount} 人次 · 固定计分叶{' '}
            {leafCount || '读取中'}
          </p>
        )}

        <form
          className="assessments-form"
          aria-label="上传成绩表"
          onSubmit={(event) => {
            event.preventDefault();
            void submitUpload();
          }}
        >
          <label className="assessments-field">
            <span>成绩表格文件（.xlsx / .csv）</span>
            <input
              className="assessments-input"
              type="file"
              aria-label="成绩表格文件"
              accept=".xlsx,.csv,text/csv,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>
          <label className="assessments-field">
            <span>工作表名（多表 XLSX 必填）</span>
            <input
              className="assessments-input"
              aria-label="工作表名"
              value={workSheet}
              onChange={(event) => setWorkSheet(event.target.value)}
            />
          </label>
          <label className="assessments-field">
            <span>基于正式成绩版本（首个版本留空）</span>
            <select
              className="space-select"
              aria-label="基于正式成绩版本"
              value={baseSelection}
              onChange={(event) => setBaseSelection(event.target.value)}
            >
              <option value="">（首版，无基准）</option>
              {confirmedRevisions.map((revision) => (
                <option key={revision.revisionId} value={revision.revisionId}>
                  v{revision.version} · {revision.revisionId}
                </option>
              ))}
            </select>
          </label>
          <button className="space-button primary" type="submit" disabled={uploadBusy || !file}>
            {uploadBusy ? '上传中…' : '上传并创建待校对批次'}
          </button>
        </form>
        {uploadError && (
          <p className="space-banner error" role="alert" data-testid="assessments-upload-error">
            {uploadError}
          </p>
        )}
      </section>

      <section className="assessments-subpanel" aria-label="导入批次">
        <div className="assessments-subpanel-head">
          <h3>导入批次</h3>
          <span className="assessments-hint">共 {imports.lastData?.total ?? 0} 个批次</span>
        </div>
        {imports.state.phase === 'failed' && !imports.lastData && (
          <div className="space-banner error" role="alert" data-testid="assessments-imports-error">
            批次列表读取失败（{imports.state.error.code}）：{imports.state.error.message}
          </div>
        )}
        {importSummaries.length === 0 && imports.state.phase === 'ready' && (
          <p className="assessments-hint" data-testid="assessments-imports-empty">
            还没有导入批次；上传成绩表后会出现在这里。
          </p>
        )}
        <ul className="assessments-list" aria-label="导入批次列表">
          {importSummaries.map((summary) => (
            <li key={summary.importId}>
              <div className="assessments-actions">
                <button
                  type="button"
                  className={
                    summary.importId === activeImportId
                      ? 'assessments-list-item current'
                      : 'assessments-list-item'
                  }
                  aria-pressed={summary.importId === activeImportId}
                  data-testid={`assessments-import-${summary.importId}`}
                  onClick={() => setSelectedImportId(summary.importId)}
                >
                  <strong>{summary.uploadedFileName || `批次 ${shortId(summary.importId)}`}</strong>
                  <span className="assessments-meta">
                    <span className={scoreImportStateChipClass(summary.state)}>
                      {scoreImportStateLabel(summary.state)}
                    </span>{' '}
                    · r{summary.revision} · 行 {summary.rowCount}
                    <span title={summary.importId}> · 批次 {shortId(summary.importId)}</span>
                  </span>
                </button>
                {DISCARDABLE_IMPORT_STATES.includes(summary.state) && (
                  <button
                    className="space-button danger"
                    data-testid={`assessments-discard-import-${summary.importId}`}
                    disabled={discardBusyId !== null}
                    onClick={() => void discardImport(summary)}
                  >
                    {discardBusyId === summary.importId ? '放弃中…' : '放弃'}
                  </button>
                )}
              </div>
            </li>
          ))}
        </ul>
        {discardError && (
          <p className="space-banner error" role="alert" data-testid="assessments-discard-error">
            {discardError}
          </p>
        )}
      </section>

      {importView.state.phase === 'failed' && !importView.lastData && activeImportId && (
        <div className="space-banner error" role="alert" data-testid="assessments-import-error">
          批次读取失败（{importView.state.error.code}）：{importView.state.error.message}
          <button className="space-button" onClick={importView.reload}>
            重试
          </button>
        </div>
      )}

      {view && (
        <>
          <section className="assessments-subpanel" aria-label="列映射">
            <div className="assessments-subpanel-head">
              <h3>列映射（固定到原卷计分叶）</h3>
              <span className="assessments-hint">
                批次 r{view.revision} · 预览 v{view.previewVersion} · 未映射叶按 missing
              </span>
            </div>
            {paperContent.state.phase === 'failed' && (
              <p className="space-banner error" role="alert" data-testid="assessments-leaves-error">
                原卷修订内容读取失败（{paperContent.state.error.code}）：
                {paperContent.state.error.message}
                可手填题目 id 与列字母继续映射。
              </p>
            )}
            <div className="assessments-mapping-grid">
              <label className="assessments-field">
                <span>工作表名</span>
                <input
                  className="assessments-input"
                  aria-label="映射工作表名"
                  value={mappingDraft.workSheet}
                  onChange={(event) =>
                    editMapping((prev) => ({ ...prev, workSheet: event.target.value }))
                  }
                />
              </label>
              <label className="assessments-field">
                <span>表头行（0 = 无表头）</span>
                <input
                  className="assessments-input assessments-input-narrow"
                  type="number"
                  min={0}
                  aria-label="表头行"
                  value={mappingDraft.headerRow}
                  onChange={(event) =>
                    editMapping((prev) => ({
                      ...prev,
                      headerRow: Number(event.target.value) || 0,
                    }))
                  }
                />
              </label>
              <label className="assessments-field">
                <span>学号列</span>
                <input
                  className="assessments-input assessments-input-narrow"
                  aria-label="学号列"
                  value={mappingDraft.studentNoColumn}
                  onChange={(event) =>
                    editMapping((prev) => ({ ...prev, studentNoColumn: event.target.value }))
                  }
                />
              </label>
              <label className="assessments-field">
                <span>姓名列</span>
                <input
                  className="assessments-input assessments-input-narrow"
                  aria-label="姓名列"
                  value={mappingDraft.nameColumn}
                  onChange={(event) =>
                    editMapping((prev) => ({ ...prev, nameColumn: event.target.value }))
                  }
                />
              </label>
              <label className="assessments-field">
                <span>出勤列（可选）</span>
                <input className="assessments-input assessments-input-narrow" aria-label="出勤列"
                  value={mappingDraft.attendanceColumn} onChange={(event) =>
                    editMapping((prev) => ({ ...prev, attendanceColumn: event.target.value }))} />
              </label>
              <label className="assessments-field">
                <span>总分列（可选）</span>
                <input className="assessments-input assessments-input-narrow" aria-label="总分列"
                  value={mappingDraft.totalColumn} onChange={(event) =>
                    editMapping((prev) => ({ ...prev, totalColumn: event.target.value }))} />
              </label>
            </div>

            <fieldset className="assessments-leaf-map" aria-label="计分叶列映射">
              <legend>计分叶 → 原表列字母</legend>
              {leaves.length === 0 && (
                <p className="assessments-hint">
                  没有读到计分叶（原卷修订内容读取中或失败）；可刷新后重试。
                </p>
              )}
              {leaves.map((leaf) => (
                <label key={leaf.itemId} className="assessments-field assessments-field-inline">
                  <span data-testid={`assessments-leaf-label-${leaf.itemId}`}>
                    {leafLabel(leaf)}
                  </span>
                  <input
                    className="assessments-input assessments-input-narrow"
                    aria-label={`${leaf.questionNo} 列字母`}
                    value={mappingDraft.itemColumns[leaf.itemId] ?? ''}
                    onChange={(event) =>
                      editMapping((prev) => ({
                        ...prev,
                        itemColumns: { ...prev.itemColumns, [leaf.itemId]: event.target.value },
                      }))
                    }
                  />
                </label>
              ))}
            </fieldset>

            <div className="assessments-actions">
              <button className="space-button" disabled={mappingBusy} onClick={() => void saveMapping()}>
                {mappingBusy ? '保存中…' : '保存映射并重算'}
              </button>
              <button
                className="space-button"
                onClick={() => {
                  importView.reload();
                  setMappingNotice(null);
                  setMappingError(null);
                }}
              >
                刷新对照
              </button>
            </div>
            {mappingError && (
              <p className="space-banner error" role="alert" data-testid="assessments-mapping-error">
                {mappingError}
              </p>
            )}
            {mappingIssues.length > 0 && <ul className="assessments-issue-list" data-testid="assessments-mapping-issues">
              {mappingIssues.map((issue, index) => <li key={index}>{issueLocationLabel(issue)}{issue.code}：{issue.message}</li>)}
            </ul>}
            {mappingNotice && (
              <p className="space-banner info" role="status" data-testid="assessments-mapping-notice">
                {mappingNotice}
              </p>
            )}
            {mappingHasEdits && <p className="assessments-hint" data-testid="assessments-mapping-dirty">
              映射有未保存修改，请先保存并读回权威预览，再确认成绩。
            </p>}
            {mappingPreviewPending && <p className="assessments-hint" data-testid="assessments-mapping-waiting-preview">
              映射已保存，等待读回重算后的权威预览；读取失败时请刷新对照，再承认并确认成绩。
            </p>}
          </section>

          <section className="assessments-subpanel" aria-label="明确刷新成绩预览">
            <p className="assessments-hint">
              出勤或参测人次校正后，先刷新对照读取当前施测，再明确刷新本预览并重新承认。
              若正式成绩基准已变化，请新建导入批次；刷新不替换基准，也不清空未保存校对。
            </p>
            <button className="space-button" disabled={previewBusy || view.state === 'confirmed' || !detail.lastData}
              onClick={() => void rebuildPreview()}>{previewBusy ? '刷新预览中…' : '明确刷新成绩预览'}</button>
            {previewError && <p className="space-banner error" role="alert" data-testid="assessments-preview-error">{previewError}</p>}
            {previewNotice && <p className="space-banner info" role="status" data-testid="assessments-preview-notice">{previewNotice}</p>}
          </section>

          <ScoreStatusLegend />

          <ScoreImportReview
            key={view.importId}
            view={view}
            reloadToken={rowsRefresh}
            leaves={leaves.map((leaf) => ({ itemId: leaf.itemId, questionNo: leaf.questionNo }))}
            participants={(detail.lastData?.participants ?? []).map((participant) => ({
              participantId: participant.participantId,
              classId: participant.classId,
              name: participant.nameSnapshot,
              attendance: participant.attendance,
            }))}
            assessmentRevision={detail.lastData?.assessment.revision ?? null}
            mappingPending={mappingHasEdits || mappingBusy || mappingPreviewPending}
            onReload={reloadForCompare}
            onReloadAssessment={detail.reload}
            onChanged={onChanged}
            onOpenHistory={onOpenHistory}
          />
        </>
      )}

      <section className="assessments-subpanel" aria-label="修订历史入口">
        <div className="assessments-subpanel-head">
          <h3>修订历史</h3>
          <button className="space-button" onClick={onOpenHistory} data-testid="assessments-open-history">
            打开只读矩阵与修正
          </button>
        </div>
        {confirmedRevisions.length === 0 ? (
          <p className="assessments-hint" data-testid="assessments-revisions-empty">
            还没有已确认成绩版本；确认一个导入批次后会生成不可变修订。
          </p>
        ) : (
          <ul className="assessments-list" aria-label="成绩修订列表">
            {confirmedRevisions.map((revision) => (
              <li key={revision.revisionId} className="assessments-list-static">
                <strong>v{revision.version}</strong>
                <span className="assessments-meta">
                  {revision.revisionId} · 人次 {revision.participantSnapshot?.length ?? 0} · 叶{' '}
                  {revision.itemSnapshot?.length ?? 0}
                  {revision.baseRevisionId ? ` · 基于 ${revision.baseRevisionId}` : ' · 首版'}
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
