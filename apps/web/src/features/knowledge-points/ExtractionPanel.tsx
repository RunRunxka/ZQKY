'use client';

/**
 * 「从教材提取知识点」面板（知识点页签族的第四个页签）。
 *
 * 落点说明：AI 候选面板处理的是「教师给资料 → 候选」，本面板是「教材书册 → 候选」，
 * 输入、预览与预算校验完全不同；放进 AI 候选面板会把两套状态混在一个 476 行的组件里。
 * 因此独立成页签，与「表格导入」相邻：两者产物都是待确认批次，确认链共用。
 *
 * 流程与纪律：
 * - 学科 → `GET /knowledge-extraction/preview?subjectId=`（只读）展示书册表；
 *   **默认只勾选就绪书册**，未就绪书册置灰并显示服务端给的原因（不伪造就绪）；
 * - 发起：`POST /knowledge-extraction-jobs`（202 只代表受理），**每个书册一个任务**，
 *   按书册逐任务观察六态（观察语义复用既有 `useKnowledgeJob`，每任务一个组件实例）；
 * - 未就绪书册被选中 → 服务端 409 `KNOWLEDGE_EXTRACTION_NOT_READY`，逐册列出原因；
 *   该学科没有就绪书册 → 422（不建空任务）——两种情况都如实展示，不前移到「成功」；
 * - 候选只进 `source="ai"` 的待确认批次，必须去「表格导入」页签逐行校对、整批确认。
 */

import { useEffect, useRef, useState } from 'react';
import Link from 'next/link';
import { CheckCircle2, FileStack, RefreshCw, Sparkles, Square, StopCircle } from 'lucide-react';
import type { KnowledgeExtractionPreview } from '@/contracts/knowledge';
import type { JobView } from '@/contracts/teaching-loop';
import { isJobTerminal } from '@/contracts/teaching-loop';
import { loadModelCatalog } from '@/services/model-settings-api';
import {
  createKnowledgeExtractionJobs,
  previewKnowledgeExtraction,
} from '@/services/knowledge-points-api';
import type { ObserveJobOptions } from '@/services/workflow-jobs-api';
import { asApiError, useAsyncResource, useKnowledgeJob } from './hooks';
import {
  KNOWLEDGE_EXTRACTION_NOT_READY_CODE,
  jobStateLabel,
  parseExtractionNotReadyDocuments,
} from './labels';
import {
  SUGGESTION_CLOUD_NOTICE,
  SUGGESTION_NO_DEFAULT_REASON,
  pickSuggestionChatModel,
  suggestionCatalogErrorReason,
  unavailableSuggestionModel,
  type SuggestionChatModel,
} from './model-profile';

/** 模型设置入口（设置页的「模型与连接」段：连接、模型目录与默认模型）。 */
const MODEL_SETTINGS_HREF = '/settings#models';

function formatCount(value: number): string {
  return value.toLocaleString('zh-CN');
}

/** 预览表里的可勾选行：只对就绪书册开放勾选。 */
function PreviewTable({
  preview,
  selected,
  disabled,
  gradeLabelOf,
  onToggle,
}: {
  preview: KnowledgeExtractionPreview;
  selected: string[];
  disabled: boolean;
  gradeLabelOf: (gradeId: string) => string;
  onToggle: (documentId: string, checked: boolean) => void;
}) {
  if (preview.documents.length === 0) {
    return (
      <p className="kp-hint" role="status" data-testid="kp-extract-empty">
        该学科在教材库里还没有已入库书册（服务端返回 0 册）；先去「教材资料库」导入教材后再提取。
      </p>
    );
  }
  return (
    <ul className="kp-extract-list" data-testid="kp-extract-documents">
      {preview.documents.map((document) => (
        <li
          key={document.documentId}
          className={document.indexReady ? 'kp-extract-row' : 'kp-extract-row blocked'}
          data-testid={`kp-extract-row-${document.documentId}`}
        >
          <label className="kp-extract-pick">
            <input
              type="checkbox"
              checked={selected.includes(document.documentId)}
              disabled={disabled || !document.indexReady}
              aria-label={`选择书册 ${document.title}`}
              data-testid={`kp-extract-pick-${document.documentId}`}
              onChange={(event) => onToggle(document.documentId, event.target.checked)}
            />
            {/* 同名书册可能多册（不同修订）：完整 documentId 只放 title，避免把 uuid 当主文案 */}
            <span className="kp-extract-title" title={document.documentId}>
              {document.title}
            </span>
          </label>
          <span className="space-meta-row">
            {document.gradeIds.length > 0 ? (
              document.gradeIds.map((gradeId) => (
                <span key={gradeId} className="space-chip blue" title={gradeId}>
                  年级 {gradeLabelOf(gradeId)}
                </span>
              ))
            ) : (
              <span className="space-chip">年级未标注</span>
            )}
            <span className={document.indexReady ? 'space-chip green' : 'space-chip amber'}>
              {document.indexReady ? '索引就绪' : '未就绪'}
            </span>
            <span className="space-chip">分块 {formatCount(document.chunkCount)}</span>
            <span className="space-chip">约 {formatCount(document.approxChars)} 字</span>
          </span>
          {!document.indexReady && (
            <span className="kp-extract-reason" data-testid={`kp-extract-reason-${document.documentId}`}>
              {document.reason ?? '服务端未给出未就绪原因；该册不会被提取。'}
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}

/**
 * 单个提取任务的卡片：**每册一个任务**，各自用 `useKnowledgeJob` 观察六态
 * （守卫 jobId/attempt/代次与卸载 abort 的语义都在该 hook 内，已单独测试）。
 *
 * `receipt` 在父级保持对象身份稳定（只由受理结果决定），因此 adopt 只跑一次；
 * 终态只经 `onTerminal` 汇报给父级做汇总，不回写父级的收据对象。
 */
function ExtractionJobCard({
  receipt,
  polling,
  onTerminal,
}: {
  receipt: JobView;
  polling?: Pick<ObserveJobOptions, 'sleep' | 'now'>;
  onTerminal: (view: JobView) => void;
}) {
  const job = useKnowledgeJob({ polling, onTerminal });
  const { adopt } = job;
  useEffect(() => {
    adopt(receipt);
  }, [adopt, receipt]);

  const view = job.view ?? receipt;
  const terminal = isJobTerminal(view.state);
  const importId = typeof view.result?.importId === 'string' ? view.result.importId : null;
  const candidateCount =
    typeof view.result?.candidateCount === 'number' ? view.result.candidateCount : null;

  return (
    <li className="kp-extract-job" data-testid={`kp-extract-job-${view.jobId}`}>
      <div className="space-meta-row">
        <span className="space-chip">任务 {view.jobId}</span>
        <span className="space-chip">第 {view.attempt} 次尝试</span>
        <span className="space-chip blue" data-testid={`kp-extract-state-${view.jobId}`}>
          {jobStateLabel(view.state)}
        </span>
        {job.observing && <span className="space-chip amber">观察中…</span>}
        {candidateCount !== null && <span className="space-chip">候选 {candidateCount} 条</span>}
      </div>

      {!terminal && (
        <p className="kp-hint" role="status">
          任务在后台执行（{jobStateLabel(view.state)}）；排队中不等于成功，离开本页只停止观察、
          不会取消任务。
        </p>
      )}
      {(view.state === 'failed' || view.state === 'interrupted') && (
        <p className="space-banner error" role="alert">
          该册提取{view.state === 'failed' ? '失败' : '被中断'}
          {view.error ? `（${view.error.code}）` : ''}：{view.error?.message ?? '服务端未提供说明。'}
          {importId ? ` 已生成的候选仍在批次 ${importId} 里。` : ' 没有候选被写入。'}
        </p>
      )}
      {view.state === 'cancelled' && (
        <p className="space-banner info" role="status">
          该册提取已取消：已完成的候选保留在批次里，未完成的不再写入。
        </p>
      )}
      {view.state === 'succeeded' && (
        <p className="space-banner info" role="status">
          该册提取完成{candidateCount !== null ? `（${candidateCount} 条候选）` : ''}
          {importId ? `：批次 ${importId}` : '：服务端没有返回批次 id'}。候选必须人工校对后确认。
        </p>
      )}

      {job.actionError && (
        <p className="space-banner error" role="alert">
          任务操作失败（{job.actionError.code}）：{job.actionError.message}
        </p>
      )}
      {job.observationNotice && (
        <p className="space-banner info" role="status">
          {job.observationNotice}
        </p>
      )}

      <div className="kp-actions">
        {(view.state === 'queued' || view.state === 'running') && (
          <button className="space-button danger" disabled={job.pending !== null} onClick={job.cancel}>
            {job.pending === 'cancel' ? (
              '正在取消…'
            ) : (
              <>
                <StopCircle size={13} aria-hidden />
                取消该册
              </>
            )}
          </button>
        )}
        {(view.state === 'failed' || view.state === 'interrupted' || view.state === 'cancelled') && (
          <button
            className="space-button"
            disabled={job.pending !== null || job.observing}
            onClick={job.retry}
          >
            {job.pending === 'retry' ? (
              '正在重试…'
            ) : (
              <>
                <RefreshCw size={13} aria-hidden />
                重试该册（沿用冻结输入与模型）
              </>
            )}
          </button>
        )}
        {importId && (
          <span className="kp-hint">候选批次 {importId}</span>
        )}
      </div>
    </li>
  );
}

export function ExtractionPanel({
  subjects,
  grades = [],
  taxonomyReady,
  defaultSubjectId,
  onOpenBatch,
  polling,
}: {
  subjects: { id: string; label: string }[];
  /** 年级字典（`GET /textbook-taxonomy`）；不可用时为空数组，界面回退显示服务端返回的年级 id。 */
  grades?: { id: string; label: string }[];
  taxonomyReady: boolean;
  defaultSubjectId: string;
  onOpenBatch: (importId: string) => void;
  /** 测试注入点：透传给每个任务的 `observeJob`。 */
  polling?: Pick<ObserveJobOptions, 'sleep' | 'now'>;
}) {
  const catalog = useAsyncResource(() => loadModelCatalog(), 'kp-extract-model-catalog');
  const catalogData = catalog.state.phase === 'ready' ? catalog.state.data : null;
  const chatModel: SuggestionChatModel =
    catalog.state.phase === 'failed'
      ? unavailableSuggestionModel(
          suggestionCatalogErrorReason(catalog.state.error.code, catalog.state.error.message),
        )
      : pickSuggestionChatModel(catalogData);

  const [subjectId, setSubjectId] = useState(defaultSubjectId);
  useEffect(() => {
    if (defaultSubjectId) setSubjectId(defaultSubjectId);
  }, [defaultSubjectId]);

  const trimmedSubject = subjectId.trim();
  const [previewSubject, setPreviewSubject] = useState(trimmedSubject);
  const preview = useAsyncResource(
    (signal) =>
      previewSubject
        ? previewKnowledgeExtraction(previewSubject, signal)
        : Promise.resolve<KnowledgeExtractionPreview | null>(null),
    `kp-extract-preview|${previewSubject}`,
  );
  const previewData = preview.state.phase === 'ready' ? preview.state.data : null;

  const [selected, setSelected] = useState<string[]>([]);
  const [selectionFor, setSelectionFor] = useState<string | null>(null);
  // 预览数据变化（换学科/重新读取）时默认勾选全部「就绪」书册；未就绪一律不勾选
  useEffect(() => {
    if (!previewData) return;
    const key = `${previewData.subjectId}|${previewData.documents
      .map((item) => `${item.documentId}:${item.indexReady ? 1 : 0}:${item.revisionId ?? ''}`)
      .join(',')}`;
    if (selectionFor === key) return;
    setSelected(previewData.documents.filter((item) => item.indexReady).map((item) => item.documentId));
    setSelectionFor(key);
  }, [previewData, selectionFor]);

  const [startError, setStartError] = useState<string | null>(null);
  const [notReady, setNotReady] = useState<
    { documentId: string; title: string; reason: string }[] | null
  >(null);
  const [busy, setBusy] = useState(false);
  /** 受理收据：对象身份只由受理结果决定（终态经 summary 单独记录），adopt 因此只跑一次。 */
  const [receipts, setReceipts] = useState<JobView[]>([]);
  const [summary, setSummary] = useState<Record<string, JobView>>({});
  const submissionRef = useRef<string | null>(null);

  const ready = previewData ? previewData.documents.filter((item) => item.indexReady) : [];
  const selectedReady = selected.filter((id) => ready.some((item) => item.documentId === id));
  const gradeLabelOf = (gradeId: string) =>
    grades.find((grade) => grade.id === gradeId)?.label ?? gradeId;
  const terminalStates = receipts.map((receipt) => summary[receipt.jobId]?.state ?? receipt.state);
  const allTerminal = receipts.length > 0 && terminalStates.every((state) => isJobTerminal(state));
  const succeededJobs = receipts.filter((receipt) => summary[receipt.jobId]?.state === 'succeeded');
  const successfulImportIds = succeededJobs
    .map((receipt) => summary[receipt.jobId]?.result?.importId)
    .filter((value): value is string => typeof value === 'string');

  function rememberTerminal(view: JobView) {
    setSummary((prev) => {
      const current = prev[view.jobId];
      if (
        current &&
        current.state === view.state &&
        current.attempt === view.attempt &&
        current.result?.importId === view.result?.importId
      ) {
        return prev; // 无变化：保持对象身份，避免子组件重复 adopt
      }
      return { ...prev, [view.jobId]: view };
    });
  }

  function toggleDocument(documentId: string, checked: boolean) {
    setSelected((prev) =>
      checked ? [...prev.filter((item) => item !== documentId), documentId] : prev.filter((item) => item !== documentId),
    );
  }

  async function start() {
    if (!previewData) {
      setStartError('请先选择学科并读取提取预览（无预览就不发起任务）。');
      return;
    }
    if (!chatModel.available) {
      setStartError(chatModel.reason ?? SUGGESTION_NO_DEFAULT_REASON);
      return;
    }
    if (selectedReady.length === 0) {
      setStartError('至少勾选一册就绪教材：未就绪书册不能提取，也不会被自动跳过。');
      return;
    }
    setBusy(true);
    setStartError(null);
    setNotReady(null);
    setReceipts([]);
    setSummary({});
    submissionRef.current = crypto.randomUUID();
    try {
      const created = await createKnowledgeExtractionJobs({
        submissionId: submissionRef.current,
        modelProfileId: chatModel.profileId,
        subjectId: previewData.subjectId,
        documentIds: selectedReady,
      });
      setReceipts(created);
      setSummary({});
    } catch (cause) {
      const error = asApiError(cause);
      const documents = parseExtractionNotReadyDocuments(error.details);
      if (error.code === KNOWLEDGE_EXTRACTION_NOT_READY_CODE && documents) {
        setNotReady(documents);
      }
      setStartError(
        `发起提取失败（${error.code}）：${error.message} 没有创建任务，也没有写入候选。`,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="kp-extract" aria-label="从教材提取知识点">
      <header className="kp-subpanel-head">
        <h3>
          <FileStack size={14} aria-hidden />
          从教材提取知识点（AI 候选 · 需人工确认）
        </h3>
        <button className="space-button" onClick={catalog.reload}>
          <RefreshCw size={13} aria-hidden />
          重新读取模型配置
        </button>
      </header>

      <p className="kp-hint">
        按学科取已入库教材的正文切片交给模型归纳知识点；结果只进 source=「ai」的待确认批次，
        逐行校对、整批确认后才写入正式知识点表，<strong>不会</strong>自动发布。
      </p>

      {chatModel.available ? (
        <p className="kp-hint" data-testid="kp-extract-model">
          使用<strong>{chatModel.modelLabel}</strong>提取候选。
        </p>
      ) : (
        <p
          className="kp-hint kp-warn-text"
          role={catalog.state.phase === 'failed' ? 'alert' : 'status'}
          data-testid="kp-extract-model"
        >
          {chatModel.reason ?? SUGGESTION_NO_DEFAULT_REASON}
          <Link className="space-button" href={MODEL_SETTINGS_HREF}>
            去设置默认问答模型
          </Link>
        </p>
      )}
      {chatModel.available &&
        (chatModel.cloud ? (
          <p className="kp-dataflow-note" data-testid="kp-extract-dataflow">
            云端模型：{SUGGESTION_CLOUD_NOTICE}（只发送所选书册的正文切片）。
          </p>
        ) : (
          <p className="kp-hint" data-testid="kp-extract-dataflow">
            本机模型：教材正文不会发送到外部模型服务。
          </p>
        ))}

      <div className="kp-subpanel">
        <h4>取材范围</h4>
        <div className="kp-form-row">
          <label className="kp-field kp-field-inline">
            <span className="kp-field-label">学科</span>
            {taxonomyReady ? (
              <select
                className="space-select"
                value={subjectId}
                aria-label="提取学科"
                disabled={busy}
                onChange={(event) => setSubjectId(event.target.value)}
              >
                <option value="">请选择学科</option>
                {subjects.map((subject) => (
                  <option key={subject.id} value={subject.id}>
                    {subject.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                className="space-search"
                value={subjectId}
                placeholder="学科 id"
                aria-label="提取学科"
                disabled={busy}
                onChange={(event) => setSubjectId(event.target.value)}
              />
            )}
          </label>
          <button
            className="space-button"
            disabled={busy || !trimmedSubject}
            onClick={() => setPreviewSubject(trimmedSubject)}
          >
            <Sparkles size={13} aria-hidden />
            读取提取预览
          </button>
          {previewSubject && (
            <button className="space-button" disabled={busy} onClick={preview.reload}>
              <RefreshCw size={13} aria-hidden />
              重新读取预览
            </button>
          )}
        </div>
        <p className="kp-hint">
          预览按学科取<strong>全部已入库教材</strong>（含其他版本）；未就绪书册置灰并给出原因，
          不会被自动跳过，也不会把「读不到」当成「没有教材」。
        </p>

        {!previewSubject && (
          <p className="kp-hint" role="status">
            先选择学科并点「读取提取预览」：不读取预览就不会发起任务。
          </p>
        )}

        {previewSubject && preview.state.phase === 'loading' && (
          <div aria-busy="true" aria-label="正在读取提取预览">
            <div className="space-skeleton" style={{ height: 72 }} aria-hidden />
            <div className="space-skeleton" style={{ height: 72 }} aria-hidden />
          </div>
        )}

        {previewSubject && preview.state.phase === 'failed' && (
          <div className="space-banner error" role="alert" data-testid="kp-extract-preview-error">
            <div className="space-banner-row">
              <span>
                提取预览读取失败（{preview.state.error.code}）：{preview.state.error.message}
              </span>
              <button className="space-button" onClick={preview.reload}>
                重试
              </button>
            </div>
            <span>这不代表该学科没有教材；没有预览时不会发起提取任务。</span>
          </div>
        )}

        {previewData && preview.state.phase === 'ready' && (
          <>
            <div className="space-meta-row" data-testid="kp-extract-totals">
              <span className="space-chip">书册 {formatCount(previewData.totalDocuments)}</span>
              <span className="space-chip green">
                就绪 {formatCount(previewData.readyDocuments)}
              </span>
              <span className="space-chip">分块 {formatCount(previewData.totalChunks)}</span>
              <span className="space-chip">约 {formatCount(previewData.approxChars)} 字</span>
              <span className="space-chip">已勾选 {selectedReady.length} 册</span>
            </div>
            <PreviewTable
              preview={previewData}
              selected={selected}
              disabled={busy}
              gradeLabelOf={gradeLabelOf}
              onToggle={toggleDocument}
            />
            <div className="kp-actions">
              <button
                className="space-button"
                disabled={busy || ready.length === 0}
                onClick={() => setSelected(ready.map((item) => item.documentId))}
              >
                <CheckCircle2 size={13} aria-hidden />
                全选就绪书册
              </button>
              <button
                className="space-button"
                disabled={busy || selected.length === 0}
                onClick={() => setSelected([])}
              >
                <Square size={13} aria-hidden />
                清空勾选
              </button>
            </div>
          </>
        )}
      </div>

      <div className="kp-subpanel">
        <h4>发起提取</h4>
        <p className="kp-hint">
          每册一个任务（202 只代表受理）；候选生成后需到「表格导入」页签逐行校对并整批确认，
          与人工表格导入共用同一套确认流程。
        </p>
        {notReady && (
          <div className="space-banner error" role="alert" data-testid="kp-extract-not-ready">
            <strong>以下书册尚未就绪，本次没有受理任何任务</strong>
            <ul className="kp-issue-list">
              {notReady.map((document) => (
                <li key={document.documentId}>
                  {document.title || document.documentId}：{document.reason || '服务端未给出原因。'}
                </li>
              ))}
            </ul>
            <span>未就绪书册需要先在「教材资料库」完成入库与索引；取消勾选后重新发起。</span>
          </div>
        )}
        {startError && (
          <p className="space-banner error" role="alert" data-testid="kp-extract-error">
            {startError}
          </p>
        )}
        <div className="kp-actions">
          <button
            className="space-button primary"
            data-testid="kp-extract-start"
            disabled={busy || !previewData || !chatModel.available || selectedReady.length === 0}
            onClick={() => void start()}
          >
            <Sparkles size={14} aria-hidden />
            {busy ? '提交中…' : `开始提取（${selectedReady.length} 册 → AI 候选）`}
          </button>
        </div>

        {receipts.length > 0 && (
          <ul className="kp-extract-jobs" aria-label="提取任务清单">
            {receipts.map((receipt) => (
              <ExtractionJobCard
                key={receipt.jobId}
                receipt={receipt}
                polling={polling}
                onTerminal={rememberTerminal}
              />
            ))}
          </ul>
        )}

        {receipts.length > 0 && (
          <div className="space-banner info" role="status" data-testid="kp-extract-summary">
            <span>
              本批共 {receipts.length} 个任务：已完成 {succeededJobs.length} 个
              {allTerminal ? '（全部结束）' : '（仍在进行，页面持续观察）'}。
            </span>
            {succeededJobs.length > 0 && (
              <span>
                候选已进待确认批次，去「表格导入」页签校对入库；AI 候选不会自动入库。
              </span>
            )}
            {successfulImportIds.map((importId) => (
              <button
                key={importId}
                className="space-button"
                data-testid={`kp-extract-open-${importId}`}
                onClick={() => onOpenBatch(importId)}
              >
                打开候选批次 {importId}
              </button>
            ))}
          </div>
        )}
      </div>
    </section>
  );
}
