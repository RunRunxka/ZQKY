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

import { useEffect, useState } from 'react';
import { RefreshCw, Upload } from 'lucide-react';
import type {
  ScoreColumnMapping,
  ScoreImportSummary,
  ScoreImportView,
  ScoreItemColumn,
} from '@/contracts/scores';
import {
  createScoreImport,
  getAssessment,
  getPaperRevisionContent,
  getScoreImport,
  listScoreImports,
  listScoreRevisions,
  patchScoreImport,
} from '@/services/assessments-api';
import { useAsyncResource } from './hooks';
import { leafLabel, scoreImportStateChipClass, scoreImportStateLabel, scoredLeafItems } from './labels';
import { ScoreImportReview } from './ScoreImportReview';
import { ScoreStatusLegend } from './ScoreStatusBadge';

const COLUMN_PATTERN = /^[A-Za-z]{1,3}$/;

interface MappingDraft {
  workSheet: string;
  headerRow: number;
  studentNoColumn: string;
  nameColumn: string;
  itemColumns: Record<string, string>;
}

const EMPTY_MAPPING: MappingDraft = {
  workSheet: '',
  headerRow: 1,
  studentNoColumn: '',
  nameColumn: '',
  itemColumns: {},
};

function mappingFromView(view: ScoreImportView | null): MappingDraft {
  if (!view?.mapping) return EMPTY_MAPPING;
  return {
    workSheet: view.mapping.workSheet,
    headerRow: view.mapping.headerRow ?? 0,
    studentNoColumn: view.mapping.studentNoColumn ?? '',
    nameColumn: view.mapping.nameColumn ?? '',
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
  const [uploadBusy, setUploadBusy] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [workSheet, setWorkSheet] = useState('');
  const [baseSelection, setBaseSelection] = useState('');

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
  const activeImportId = selectedImportId ?? importSummaries[0]?.importId ?? null;

  const importView = useAsyncResource(
    (signal) =>
      activeImportId ? getScoreImport(activeImportId, signal) : Promise.resolve(null),
    `assessments-score-import|${activeImportId ?? 'none'}`,
  );
  const view = importView.lastData;

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
    setMappingDraft(mappingFromView(importView.lastData ?? null));
  }, [importView.lastData]);

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
    setUploadError(null);
    try {
      const created = await createScoreImport(assessmentId, file, {
        workSheet: workSheet.trim() || null,
        baseScoreRevisionId: baseSelection || null,
      });
      setFile(null);
      setWorkSheet('');
      setBaseSelection('');
      setSelectedImportId(created.importId);
      reloadAll();
      onChanged();
    } catch (cause) {
      const error = cause as { code?: string; message?: string; details?: { currentRevision?: number } };
      setUploadError(
        `上传失败（${error.code ?? 'UNKNOWN'}）：${error.message ?? '请求失败'}${
          error.details?.currentRevision ? `（当前版本 ${error.details.currentRevision}）` : ''
        } 已选文件保留，可直接重试。`,
      );
    } finally {
      setUploadBusy(false);
    }
  }

  async function saveMapping() {
    if (!view) return;
    setMappingBusy(true);
    setMappingError(null);
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
    if (identities.some((column) => !COLUMN_PATTERN.test(column)) || invalidLeaf) {
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
      workSheet: mappingDraft.workSheet.trim(),
      headerRow: mappingDraft.headerRow,
      studentNoColumn: mappingDraft.studentNoColumn.trim().toUpperCase() || null,
      nameColumn: mappingDraft.nameColumn.trim().toUpperCase() || null,
      itemColumns,
    };
    try {
      const next = await patchScoreImport(view.importId, {
        expectedRevision: view.revision,
        mapping,
      });
      setMappingNotice(`已保存映射并重算行（批次 r${next.revision}，预览 v${next.previewVersion}）。`);
      reloadAll();
      // 读回权威视图（同 key）：后续校对/确认必须用重算后的 revision 与 previewVersion
      importView.reload();
    } catch (cause) {
      const error = cause as { code?: string; message?: string; status?: number; details?: { currentRevision?: number } };
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
      setMappingBusy(false);
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
            施测「{detail.lastData.assessment.title}」· 原卷修订{' '}
            {detail.lastData.assessment.paperRevisionId} · 参测{' '}
            {detail.lastData.assessment.participantCount} 人次 · 固定计分叶{' '}
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
                <strong>{summary.importId}</strong>
                <span className="assessments-meta">
                  <span className={scoreImportStateChipClass(summary.state)}>
                    {scoreImportStateLabel(summary.state)}
                  </span>{' '}
                  · r{summary.revision} · 行 {summary.rowCount}
                </span>
              </button>
            </li>
          ))}
        </ul>
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
                    setMappingDraft((prev) => ({ ...prev, workSheet: event.target.value }))
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
                    setMappingDraft((prev) => ({
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
                    setMappingDraft((prev) => ({ ...prev, studentNoColumn: event.target.value }))
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
                    setMappingDraft((prev) => ({ ...prev, nameColumn: event.target.value }))
                  }
                />
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
                      setMappingDraft((prev) => ({
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
            {mappingNotice && (
              <p className="space-banner info" role="status" data-testid="assessments-mapping-notice">
                {mappingNotice}
              </p>
            )}
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
