'use client';

import { useEffect, useRef, useState } from 'react';
import type { ApiError } from '@/services/api-client';
import type {
  RosterDecision,
  RosterImportConfirmResult,
  RosterImportRowPatch,
  RosterImportState,
  RosterImportSummary,
  RosterImportView,
} from '@/contracts/roster';
import {
  confirmRosterImport,
  createRosterImport,
  discardRosterImport,
  getRosterImport,
  listRosterImports,
  listStudents,
  patchRosterImport,
} from '@/services/assessments-api';
import { asApiError, useAsyncResource, useFrozenSubmission } from './hooks';

interface Props {
  classId: string;
  onChanged: () => void;
}
interface ConfirmPayload {
  importId: string;
  expectedRevision: number;
  identityMatches: { rowNo: number; action: RosterDecision; studentId: string | null }[];
}

const STATE_LABELS = {
  uploaded: '已上传',
  reviewing: '校对中',
  confirmed: '已确认',
  failed: '失败',
  cancelled: '已取消',
};
/** 未确认批次可放弃；`confirmed` 已应用（服务端 409），`cancelled` 已放弃。 */
const DISCARDABLE_STATES: readonly RosterImportState[] = ['uploaded', 'reviewing', 'failed'];
const SUGGESTIONS = {
  link: '建议关联已有学生',
  create: '建议新建学生',
  name_mismatch: '学号命中但姓名不符',
  no_student_no: '无学号，需人工核对',
  duplicate: '同批重复行',
  conflict: '同名存在多个身份',
};

/** A class switch remounts the session and invalidates all old writes. */
export function RosterImportPanel(props: Props) {
  return <RosterImportSession key={props.classId} {...props} />;
}

function RosterImportSession({ classId, onChanged }: Props) {
  const [file, setFile] = useState<File | null>(null);
  const [sheetName, setSheetName] = useState('');
  const [uploadNameHeader, setUploadNameHeader] = useState('');
  const [uploadNumberHeader, setUploadNumberHeader] = useState('');
  const [view, setView] = useState<RosterImportView | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [mappingTouched, setMappingTouched] = useState(false);
  const [rows, setRows] = useState<Record<number, RosterImportRowPatch>>({});
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [studentQuery, setStudentQuery] = useState('');
  const [appliedStudentQuery, setAppliedStudentQuery] = useState('');
  /** 放弃批次的写操作身份（禁用按钮防重入）。 */
  const [discardBusyId, setDiscardBusyId] = useState<string | null>(null);
  const mounted = useRef(true);
  const epoch = useRef(0);
  const busyRef = useRef(false);
  const submission = useFrozenSubmission<ConfirmPayload, RosterImportConfirmResult>();
  const batches = useAsyncResource(
    (signal) => listRosterImports({ classId, limit: 100 }, signal),
    `roster-batches|${classId}`,
  );
  const students = useAsyncResource(
    (signal) => listStudents({ q: appliedStudentQuery || undefined, limit: 100 }, signal),
    `roster-link-students|${appliedStudentQuery}`,
  );

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
      epoch.current += 1;
    };
  }, []);

  function adopt(next: RosterImportView, preserveEdits = false) {
    setView(next);
    if (!preserveEdits) {
      setMapping(next.mapping);
      setMappingTouched(false);
      setRows({});
    }
  }

  async function run<T>(request: () => Promise<T>): Promise<T | null> {
    if (busyRef.current) return null;
    const token = epoch.current;
    busyRef.current = true;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const result = await request();
      return mounted.current && token === epoch.current ? result : null;
    } catch (cause) {
      if (mounted.current && token === epoch.current) setError(asApiError(cause));
      return null;
    } finally {
      if (mounted.current && token === epoch.current) {
        busyRef.current = false;
        setBusy(false);
      }
    }
  }

  async function upload() {
    if (!file) {
      setNotice('请先选择 CSV 或 XLSX 名单文件。');
      return;
    }
    const manual = uploadNameHeader.trim()
      ? {
          name: uploadNameHeader.trim(),
          ...(uploadNumberHeader.trim() ? { studentNo: uploadNumberHeader.trim() } : {}),
        }
      : undefined;
    const result = await run(() =>
      createRosterImport(classId, file, {
        sheetName: sheetName.trim() || undefined,
        mapping: manual,
      }),
    );
    if (result) {
      submission.release();
      adopt(result);
      batches.reload();
      setNotice('名单已上传，建议不会自动成为行决定；请逐行选择处理方式。');
    }
  }

  async function openBatch(importId: string, preserveEdits = false) {
    const result = await run(() => getRosterImport(importId));
    if (result) {
      if (!preserveEdits) submission.release();
      adopt(result, preserveEdits);
      setNotice(
        preserveEdits
          ? '已读取最新版本，映射和行校对输入保留，请对照后再提交。'
          : '已恢复服务端名单批次。',
      );
    }
  }

  /**
   * 放弃未确认批次：只置 `cancelled`，记录/原始文件/预览行保留（不能再校对/确认）。
   * 成功刷新批次列表；若当前打开的正是该批次，同步读回它的 `cancelled` 状态。
   */
  async function discardBatch(batch: RosterImportSummary) {
    if (locked) return;
    if (!window.confirm('放弃后批次保留记录但不能再校对/确认。确认放弃该名单批次？')) return;
    const token = epoch.current;
    setDiscardBusyId(batch.importId);
    try {
      const result = await run(() =>
        discardRosterImport(batch.importId, { expectedRevision: batch.revision }),
      );
      if (!result || !mounted.current || token !== epoch.current) return;
      if (view?.importId === result.importId) {
        submission.release();
        adopt(result);
      }
      batches.reload();
      setNotice(`批次 ${result.importId} 已放弃（已取消）；批次记录与原始文件保留，不能再校对/确认。`);
    } finally {
      if (mounted.current && token === epoch.current) setDiscardBusyId(null);
    }
  }

  async function save() {
    if (!view) return;
    const result = await run(() =>
      patchRosterImport(view.importId, {
        expectedRevision: view.revision,
        mapping: mappingTouched
          ? {
              name: mapping.name ?? '',
              ...(mapping.studentNo ? { studentNo: mapping.studentNo } : {}),
            }
          : undefined,
        rows: Object.values(rows).length ? Object.values(rows) : undefined,
      }),
    );
    if (result) {
      adopt(result);
      submission.release();
      batches.reload();
      setNotice(`已保存映射与行决策（版本 ${result.revision}）。`);
    }
  }

  const decisionOf = (row: RosterImportView['rows'][number]) =>
    rows[row.rowNo]?.decision ?? row.decision;
  const studentOf = (row: RosterImportView['rows'][number]) =>
    rows[row.rowNo] ? (rows[row.rowNo].studentId ?? null) : row.matchedStudentId;
  const unknown = submission.phase === 'unknown';
  const locked = busy || submission.busy || unknown;
  const editable = view !== null && (view.state === 'uploaded' || view.state === 'reviewing');
  const resolved =
    !!view?.rows.length &&
    view.rows.every((row) => {
      const decision = decisionOf(row);
      return decision !== null && (decision !== 'link' || Boolean(studentOf(row)));
    });

  async function confirm() {
    if (!view) return;
    const payload: ConfirmPayload =
      unknown && submission.frozen
        ? submission.frozen.payload
        : {
            importId: view.importId,
            expectedRevision: view.revision,
            identityMatches: view.rows.map((row) => ({
              rowNo: row.rowNo,
              action: decisionOf(row)!,
              studentId: decisionOf(row) === 'link' ? studentOf(row) : null,
            })),
          };
    const token = epoch.current;
    const result = await submission.submit(payload, (frozen) =>
      confirmRosterImport(frozen.payload.importId, {
        expectedRevision: frozen.payload.expectedRevision,
        identityMatches: frozen.payload.identityMatches,
        submissionId: frozen.submissionId,
      }),
    );
    if (!result || !mounted.current || token !== epoch.current) return;
    setView((current) => (current ? { ...current, state: 'confirmed' } : current));
    batches.reload();
    onChanged();
  }

  function decide(row: RosterImportView['rows'][number], decision: RosterDecision) {
    setRows((current) => ({
      ...current,
      [row.rowNo]: {
        rowNo: row.rowNo,
        decision,
        studentId: decision === 'link' ? studentOf(row) : null,
      },
    }));
  }

  const displayedError = error ?? submission.error;
  const issues = displayedError?.details?.issues ?? [];
  const confirmedResult =
    submission.phase === 'succeeded' &&
    submission.result &&
    submission.result.importId === view?.importId
      ? submission.result
      : null;
  return (
    <section
      className="assessments-subpanel"
      aria-label="名单导入与校对"
      data-testid="roster-import-panel"
    >
      <h3>导入名单</h3>
      <p className="assessments-hint">
        学号按文本保存，保留前导零；姓名不是主键。名单里未出现的学生不会自动退班。
      </p>
      <div className="assessments-form">
        <label className="assessments-field">
          名单文件
          <input
            aria-label="名单文件"
            type="file"
            accept=".xlsx,.csv"
            disabled={locked}
            onChange={(event) => setFile(event.target.files?.[0] ?? null)}
          />
        </label>
        <label className="assessments-field">
          工作表名（XLSX 可选）
          <input
            className="assessments-input"
            aria-label="名单工作表名"
            value={sheetName}
            disabled={locked}
            onChange={(event) => setSheetName(event.target.value)}
          />
        </label>
        <label className="assessments-field">
          上传时姓名表头（自动识别失败时填写）
          <input
            className="assessments-input"
            aria-label="上传时姓名表头"
            value={uploadNameHeader}
            disabled={locked}
            onChange={(event) => setUploadNameHeader(event.target.value)}
          />
        </label>
        <label className="assessments-field">
          上传时学号表头（可选）
          <input
            className="assessments-input"
            aria-label="上传时学号表头"
            value={uploadNumberHeader}
            disabled={locked}
            onChange={(event) => setUploadNumberHeader(event.target.value)}
          />
        </label>
        <button className="space-button" disabled={locked || !file} onClick={() => void upload()}>
          上传名单
        </button>
      </div>
      <div className="assessments-subpanel-head">
        <h4>已有名单批次</h4>
        <button className="space-button" onClick={batches.reload}>
          刷新名单批次
        </button>
      </div>
      {batches.state.phase === 'failed' && (
        <p role="alert" className="assessments-error">
          批次读取失败（{batches.state.error.code}）：{batches.state.error.message}{' '}
          已读取的列表仍保留。
        </p>
      )}
      <ul className="assessments-list" aria-label="名单批次列表">
        {(batches.lastData?.items ?? []).map((batch) => (
          <li key={batch.importId}>
            <div className="assessments-actions">
              <button
                className="assessments-list-item"
                data-testid={`roster-batch-${batch.importId}`}
                disabled={locked}
                onClick={() => void openBatch(batch.importId)}
              >
                {batch.importId} · {STATE_LABELS[batch.state]} · {batch.rowCount} 行 · r
                {batch.revision}
              </button>
              {DISCARDABLE_STATES.includes(batch.state) && (
                <button
                  className="space-button danger"
                  data-testid={`roster-batch-discard-${batch.importId}`}
                  disabled={locked || discardBusyId !== null}
                  onClick={() => void discardBatch(batch)}
                >
                  {discardBusyId === batch.importId ? '放弃中…' : '放弃'}
                </button>
              )}
            </div>
          </li>
        ))}
      </ul>
      {view && (
        <>
          <p className="assessments-meta">
            原件：{view.fileAsset.originalName} · {view.className} · 版本 {view.revision} ·{' '}
            {STATE_LABELS[view.state]}
          </p>
          {view.warnings.map((warning) => (
            <p className="assessments-hint" key={warning}>
              {warning}
            </p>
          ))}
          <div className="assessments-form">
            <label className="assessments-field">
              姓名列
              <select
                className="assessments-input"
                aria-label="名单姓名列"
                value={mapping.name ?? ''}
                disabled={locked || !editable}
                onChange={(event) => {
                  setMapping((current) => ({ ...current, name: event.target.value }));
                  setMappingTouched(true);
                }}
              >
                <option value="">请选择姓名列</option>
                {view.headers.map((header) => (
                  <option value={header} key={header}>
                    {header}
                  </option>
                ))}
              </select>
            </label>
            <label className="assessments-field">
              学号列
              <select
                className="assessments-input"
                aria-label="名单学号列"
                value={mapping.studentNo ?? ''}
                disabled={locked || !editable}
                onChange={(event) => {
                  setMapping((current) => ({ ...current, studentNo: event.target.value }));
                  setMappingTouched(true);
                }}
              >
                <option value="">不映射学号</option>
                {view.headers.map((header) => (
                  <option value={header} key={header}>
                    {header}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <form
            className="assessments-form"
            onSubmit={(event) => {
              event.preventDefault();
              setAppliedStudentQuery(studentQuery.trim());
            }}
          >
            <label className="assessments-field">
              搜索已有学生（关联用）
              <input
                className="assessments-input"
                aria-label="搜索已有学生"
                value={studentQuery}
                onChange={(event) => setStudentQuery(event.target.value)}
              />
            </label>
            <button className="space-button" type="submit">
              搜索学生
            </button>
          </form>
          {students.state.phase === 'failed' && (
            <p role="alert" className="assessments-error">
              学生身份读取失败（{students.state.error.code}），请重试；不能把读取失败当作没有学生。
              <button className="space-button" onClick={students.reload}>
                重试学生身份
              </button>
            </p>
          )}
          <ul className="assessments-list" aria-label="名单行校对">
            {view.rows.map((row) => (
              <li
                key={row.rowNo}
                className="assessments-list-static"
                data-testid={`roster-row-${row.rowNo}`}
              >
                <strong>
                  数据第 {row.rowNo} 行：{row.name} · 学号 {row.studentNo ?? '（无）'}
                </strong>
                <p className="assessments-hint">
                  {row.suggestion ? SUGGESTIONS[row.suggestion] : '请人工核对身份'}
                  ；建议不是确认决定。
                </p>
                {row.issues.map((issue, index) => (
                  <p className="assessments-error" key={index}>
                    {issue.field ? `${issue.field}：` : ''}
                    {issue.message}
                  </p>
                ))}
                <label className="assessments-field">
                  处理方式
                  <select
                    aria-label={`第 ${row.rowNo} 行处理`}
                    value={decisionOf(row) ?? ''}
                    disabled={locked || !editable}
                    onChange={(event) => decide(row, event.target.value as RosterDecision)}
                  >
                    <option value="" disabled>
                      请选择处理方式
                    </option>
                    <option value="link">关联已有学生</option>
                    <option value="create">新建学生</option>
                    <option value="ignore">忽略本行</option>
                  </select>
                </label>
                {decisionOf(row) === 'link' && (
                  <label className="assessments-field">
                    关联学生
                    <select
                      aria-label={`第 ${row.rowNo} 行关联学生`}
                      value={studentOf(row) ?? ''}
                      disabled={locked || !editable}
                      onChange={(event) =>
                        setRows((current) => ({
                          ...current,
                          [row.rowNo]: {
                            rowNo: row.rowNo,
                            decision: 'link',
                            studentId: event.target.value || null,
                          },
                        }))
                      }
                    >
                      <option value="">请选择明确身份</option>
                      {studentOf(row) &&
                        !(students.lastData?.items ?? []).some(
                          (student) => student.id === studentOf(row),
                        ) && (
                          <option value={studentOf(row)!}>
                            {row.matchedStudentName ?? '已指定身份'}（{studentOf(row)}）
                          </option>
                        )}
                      {(students.lastData?.items ?? []).map((student) => (
                        <option key={student.id} value={student.id}>
                          {student.name} · {student.studentNo ?? '无学号'} · {student.id}
                        </option>
                      ))}
                    </select>
                  </label>
                )}
              </li>
            ))}
          </ul>
          <div className="assessments-actions">
            <button
              className="space-button"
              disabled={locked || !editable || (!mappingTouched && !Object.keys(rows).length)}
              onClick={() => void save()}
            >
              保存映射与行决策
            </button>
            <button
              className="space-button"
              disabled={locked}
              onClick={() => void openBatch(view.importId, true)}
            >
              刷新版本对照（保留校对）
            </button>
            <button
              className="space-button primary"
              disabled={
                busy || submission.busy || (!unknown && (!editable || !resolved || mappingTouched))
              }
              onClick={() => void confirm()}
            >
              {submission.busy ? '确认中…' : '确认名单'}
            </button>
          </div>
          {mappingTouched && (
            <p className="assessments-hint">
              列映射有未保存修改，请先保存映射，再核对重新提取的每行身份。
            </p>
          )}
        </>
      )}
      {notice && (
        <p role="status" className="assessments-hint">
          {notice}
        </p>
      )}
      {displayedError && (
        <div className="assessments-error" role="alert">
          名单操作失败（{displayedError.code}）：{displayedError.message} 输入已保留。
          {displayedError.status === 409 && (
            <p>版本冲突，请刷新版本对照后重试，不会静默覆盖校对。</p>
          )}
          {issues.map((issue, index) => (
            <p key={index}>
              数据第 {issue.row ?? '未定位'} 行 {issue.column ?? issue.field ?? ''}：{issue.message}
            </p>
          ))}
        </div>
      )}
      {submission.unknownNotice && (
        <p role="alert" className="assessments-error">
          {submission.unknownNotice} 校对已冻结，请点「确认名单」重放原请求。
        </p>
      )}
      {confirmedResult && (
        <p role="status" data-testid="roster-import-result" className="space-banner info">
          名单已确认：处理 {confirmedResult.applied.length} 行，忽略{' '}
          {confirmedResult.ignored.length} 行。
        </p>
      )}
    </section>
  );
}
