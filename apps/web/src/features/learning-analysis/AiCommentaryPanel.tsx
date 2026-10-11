'use client';
import { useState } from 'react';
import { LoaderCircle, Sparkles } from 'lucide-react';
import { AnswerMarkdown } from '@/features/chat/AnswerMarkdown';
import { useModelCatalog } from '@/features/model-settings/useModelCatalog';
import { b4Api, generateAnalysisCommentary } from '@/services/teaching-loop-b4-api';
import { asApiError } from '@/features/assessments/hooks';

/**
 * AI 学情评价（C2-3）：读已就绪报告的匿名聚合，调 LLM 生成评价（候选文本不落库）。
 * 教师可「存为教师备注」（走既有 notes 追加，教师确认红线不变）。
 */
export function AiCommentaryPanel({
  runId,
  services = b4Api,
}: {
  runId: string;
  /** 可注入测试替身；默认走真实 API。 */
  services?: typeof b4Api;
}) {
  const { catalog, error: catalogError } = useModelCatalog();
  const [profileId, setProfileId] = useState<string>('');
  const [commentary, setCommentary] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<{ code: string; message: string } | null>(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  const profiles = catalog?.profiles ?? [];
  const defaultChatProfileId = catalog?.defaultChatProfileId ?? '';
  const effectiveProfile = profileId || defaultChatProfileId;

  async function generate() {
    if (!effectiveProfile || generating) return;
    setGenerating(true);
    setError(null);
    setSaved(false);
    try {
      const text = await generateAnalysisCommentary(runId, effectiveProfile);
      setCommentary(text);
    } catch (e) {
      const apiError = asApiError(e);
      setError({ code: apiError.code, message: apiError.message });
    } finally {
      setGenerating(false);
    }
  }

  async function save() {
    if (!commentary || saving) return;
    setSaving(true);
    try {
      await services.createAnalysisNote(runId, { submissionId: crypto.randomUUID(), note: commentary });
      setSaved(true);
    } catch (e) {
      const apiError = asApiError(e);
      setError({ code: apiError.code, message: apiError.message });
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="analysis-ai-commentary" data-testid="analysis-ai-commentary">
      <h4>
        <Sparkles size={14} aria-hidden /> AI 评价
      </h4>
      <p className="analysis-ai-note">
        结合小题得分与知识点聚合生成班级学情评价（学生以代称进模型，不传姓名/学号）；评价是候选文本，确认后才会存为教师备注。
      </p>
      <div className="analysis-ai-actions">
        {profiles.length > 0 && (
          <select
            className="space-select"
            aria-label="AI 评价用模型"
            value={profileId}
            onChange={(e) => setProfileId(e.target.value)}
            disabled={generating}
          >
            <option value="">默认对话模型</option>
            {profiles.map((p) => (
              <option key={p.id} value={p.id}>
                {p.displayName}
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
          {generating ? <LoaderCircle size={13} className="chat-tool-spin" aria-hidden /> : <Sparkles size={13} aria-hidden />}
          {commentary ? '重新生成' : '生成 AI 评价'}
        </button>
      </div>
      {catalogError && <p className="b4-meta" role="note">模型目录读取失败：{catalogError}</p>}
      {error && (
        <p className="analysis-ai-error" role="alert">
          {error.message}（{error.code}）
        </p>
      )}
      {commentary && (
        <div className="analysis-ai-body">
          <AnswerMarkdown text={commentary} />
          <div className="analysis-ai-save">
            <button type="button" className="space-button" disabled={saving || saved} onClick={() => void save()}>
              {saved ? '已存为教师备注' : saving ? '保存中…' : '存为教师备注'}
            </button>
            {saved && <span className="b4-meta">可到「教师备注」页签查看。</span>}
          </div>
        </div>
      )}
    </div>
  );
}
