'use client';

/**
 * AI 学情评价 + 导出分析报告（取回自归档 `features/learning-analysis/AiCommentaryPanel.tsx`，R6-FE）。
 *
 * 归档语义保留：
 * - 评价读已就绪报告的匿名聚合（学生由**后端**脱敏为代称，前端不传姓名/学号）；
 * - AI 文本只是候选，不落库；教师确认后才「存为教师备注」（走 notes 追加，`submissionId` 幂等）；
 * - 生成失败原样显示 code/message，不伪装成功。
 *
 * 本卡新增：`POST /analysis-runs/{run_id}/report` 生成导出产物后，
 * 经 `GET /export-artifacts/{artifactId}/download` 下载后端给出的 `fileName`。
 */

import { useState } from 'react';
import { Download, LoaderCircle, Sparkles } from 'lucide-react';
import { AnswerMarkdown } from '@/features/chat/AnswerMarkdown';
import { useModelCatalog } from '@/features/model-settings/useModelCatalog';
import { learningAnalysisApi, type LearningAnalysisApi } from '@/services/learning-analysis-api';
import { ApiError } from '@/services/api-client';
import { asApiError } from './score-hooks';

/** 触发浏览器下载；环境不支持（或返回空）时返回 false，由调用方按「已生成但未下载」提示。 */
export function triggerBlobDownload(blob: Blob, fileName: string): boolean {
  if (typeof document === 'undefined' || typeof URL.createObjectURL !== 'function') return false;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  return true;
}

export function AiCommentaryPanel({
  runId,
  services = learningAnalysisApi,
}: {
  runId: string;
  /** 可注入测试替身；默认走真实 API。 */
  services?: LearningAnalysisApi;
}) {
  const { catalog, error: catalogError } = useModelCatalog();
  const [profileId, setProfileId] = useState<string>('');
  const [commentary, setCommentary] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  /** 服务端降级（模型未返回/不可用）：不是错误状态码，显式提示并可重试。 */
  const [degraded, setDegraded] = useState<string | null>(null);
  /** 存备注的逻辑确认：失败后重试必须复用同一 submissionId（不重复写入）。 */
  const [pendingNote, setPendingNote] = useState<{ submissionId: string; note: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const [report, setReport] = useState<{ artifactId: string; fileName: string; byteSize: number } | null>(
    null,
  );
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<{ code: string; message: string } | null>(null);
  const [exportNotice, setExportNotice] = useState<string | null>(null);

  const profiles = catalog?.profiles ?? [];
  const defaultChatProfileId = catalog?.defaultChatProfileId ?? '';
  const effectiveProfile = profileId || defaultChatProfileId;

  async function generate() {
    if (!effectiveProfile || generating) return;
    setGenerating(true);
    setError(null);
    setDegraded(null);
    setSaved(false);
    setPendingNote(null);
    try {
      const result = await services.generateAnalysisCommentary(runId, effectiveProfile);
      if (result.commentary.trim()) {
        setCommentary(result.commentary);
      } else {
        setDegraded(result.reason ?? '模型未返回可用评价，可稍后重试。');
      }
    } catch (cause) {
      const apiError = asApiError(cause);
      setError({ code: apiError.code, message: apiError.message });
    } finally {
      setGenerating(false);
    }
  }

  async function save() {
    if (!commentary || saving) return;
    // 逻辑确认：点第一次即冻结 submissionId + 原样文本；重试复用同一个标识。
    const pending = pendingNote ?? { submissionId: crypto.randomUUID(), note: commentary };
    if (!pendingNote) setPendingNote(pending);
    setSaving(true);
    setError(null);
    try {
      await services.createAnalysisNote(runId, { submissionId: pending.submissionId, note: pending.note });
      setSaved(true);
      setPendingNote(null);
    } catch (cause) {
      const apiError = asApiError(cause);
      setError({ code: apiError.code, message: apiError.message });
    } finally {
      setSaving(false);
    }
  }

  /** 生成报告产物并下载；失败保留重试入口，产物落库与否由后端决定。 */
  async function exportReport() {
    if (exporting) return;
    setExporting(true);
    setExportError(null);
    setExportNotice(null);
    try {
      const receipt = await services.createAnalysisReport(runId);
      const artifact = receipt.artifact;
      if (!artifact?.artifactId || !artifact.fileName) {
        throw new ApiError('EXPORT_RECEIPT_INVALID', '导出回执缺少产物标识，未下载任何文件。', 500, false);
      }
      setReport(artifact);
      const download = await services.downloadExportArtifact(artifact.artifactId);
      const fileName = download.fileName ?? artifact.fileName;
      if (triggerBlobDownload(download.blob, fileName)) {
        setExportNotice(`已导出「${fileName}」（${artifact.byteSize} 字节）。`);
      } else {
        setExportNotice(`报告已生成「${fileName}」（${artifact.byteSize} 字节），但当前环境不支持自动下载；可点「再次下载」。`);
      }
    } catch (cause) {
      const apiError = asApiError(cause);
      setExportError({ code: apiError.code, message: apiError.message });
    } finally {
      setExporting(false);
    }
  }

  /** 再次下载已生成的产物（不重复生成报告）。 */
  async function downloadAgain() {
    if (!report || exporting) return;
    setExporting(true);
    setExportError(null);
    try {
      const download = await services.downloadExportArtifact(report.artifactId);
      const fileName = download.fileName ?? report.fileName;
      if (triggerBlobDownload(download.blob, fileName)) {
        setExportNotice(`已下载「${fileName}」。`);
      } else {
        setExportNotice('当前环境不支持自动下载。');
      }
    } catch (cause) {
      const apiError = asApiError(cause);
      setExportError({ code: apiError.code, message: apiError.message });
    } finally {
      setExporting(false);
    }
  }

  return (
    <section className="analysis-ai-commentary" data-testid="analysis-ai-commentary" aria-label="AI 评价">
      <h3>
        <Sparkles size={15} aria-hidden /> AI 评价
      </h3>
      <p className="analysis-ai-note">
        结合小题得分与知识点聚合生成班级学情评价（学生以代称进模型，不传姓名/学号）；
        评价是候选文本，确认后才会存为教师备注。
      </p>
      <div className="analysis-ai-actions">
        {profiles.length > 0 && (
          <select
            className="space-select"
            aria-label="AI 评价用模型"
            value={profileId}
            onChange={(event) => setProfileId(event.target.value)}
            disabled={generating}
          >
            <option value="">默认对话模型</option>
            {profiles.map((profile) => (
              <option key={profile.id} value={profile.id}>
                {profile.displayName}
              </option>
            ))}
          </select>
        )}
        <button
          type="button"
          className="space-button"
          disabled={generating || (!effectiveProfile && profiles.length > 0)}
          onClick={() => void generate()}
        >
          {generating ? (
            <LoaderCircle size={13} className="chat-tool-spin" aria-hidden />
          ) : (
            <Sparkles size={13} aria-hidden />
          )}
          {commentary ? '重新生成' : '生成 AI 评价'}
        </button>
      </div>
      {catalogError && (
        <p className="la-hint" role="note">
          模型目录读取失败：{catalogError}
        </p>
      )}
      {error && (
        <p className="analysis-ai-error" role="alert">
          {error.message}（{error.code}）
        </p>
      )}
      {degraded && (
        <p className="analysis-ai-error" role="alert" data-testid="analysis-ai-degraded">
          AI 评价生成未成功：{degraded}
        </p>
      )}
      {commentary && (
        <div className="analysis-ai-body">
          <AnswerMarkdown text={commentary} />
          <div className="analysis-ai-save">
            <button
              type="button"
              className="space-button"
              disabled={saving || saved}
              onClick={() => void save()}
            >
              {saved ? '已存为教师备注' : saving ? '保存中…' : '存为教师备注'}
            </button>
            {saved && <span className="la-hint">已追加到该报告的教师备注；固定成绩与报告结论不变。</span>}
          </div>
        </div>
      )}

      <div className="analysis-export" aria-label="导出分析报告">
        <p className="analysis-ai-note">
          导出按后端冻结的报告数据生成文件（含五图口径的聚合数据）；下载文件名以后端回执为准。
        </p>
        <div className="la-actions">
          <button
            type="button"
            className="space-button"
            data-testid="analysis-export-report"
            disabled={exporting}
            onClick={() => void exportReport()}
          >
            {exporting ? (
              <LoaderCircle size={13} className="chat-tool-spin" aria-hidden />
            ) : (
              <Download size={13} aria-hidden />
            )}
            {report ? '重新生成并导出' : '导出分析报告'}
          </button>
          {report && (
            <button
              type="button"
              className="space-button"
              data-testid="analysis-download-again"
              disabled={exporting}
              onClick={() => void downloadAgain()}
            >
              再次下载
            </button>
          )}
        </div>
        {exportError && (
          <p className="analysis-ai-error" role="alert" data-testid="analysis-export-error">
            导出失败（{exportError.code}）：{exportError.message} 未下载任何文件，可重试。
          </p>
        )}
        {exportNotice && (
          <p className="la-hint" role="status" data-testid="analysis-export-notice">
            {exportNotice}
          </p>
        )}
      </div>
    </section>
  );
}
