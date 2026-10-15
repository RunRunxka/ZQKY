'use client';

/**
 * 「添加题目」面板（R4-FE 2026-10-11）。
 *
 * 参考图顶部主按钮的落点：题目**没有**直接写库的接口——题库的唯一写入口是
 * 「导入草稿 → 人工校对 → 确认入库」（红线：AI 与自动结果只进候选，教师确认才落库）。
 * 因此本面板提供两条真实通道：
 *
 * 1. **手动录入**：教师填写题干/选项/答案/解析，前端拼成 Markdown 文档后走
 *    `POST /question-imports`（multipart）落地为导入草稿，随后进入校对页；
 * 2. **AI 补题**：`GenerationPanel`（按知识点生成候选，产物同样是待校对草稿）。
 *
 * 提交失败保留已填内容（不清空、不重复提交）；成功后由父级跳到校对页。
 */

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { PenLine, Sparkles, Upload } from 'lucide-react';
import { Modal } from '@/components/ui/Modal';
import { QUESTION_TYPE_LABEL, type QuestionType } from '@/contracts/question-bank';
import { createQuestionImport } from '@/services/question-bank-api';
import { GenerationPanel } from './GenerationPanel';
import { asApiError, errorText } from './hooks';
import { composeManualQuestion, MANUAL_QUESTION_FILE_NAME } from './manual-question';
import type { TaxonomyIndex } from './taxonomy';
import { SlidingGroup } from '@/components/ui/SlidingGroup';

type Mode = 'manual' | 'generation';

const CHOICE_TYPES: QuestionType[] = ['single_choice', 'multiple_choice'];

export function AddQuestionPanel({
  taxonomy,
  onClose,
  onImported,
  onPublished,
}: {
  taxonomy: TaxonomyIndex;
  onClose: () => void;
  /** 导入草稿创建成功：父级跳到校对页（`/question-bank/imports/{id}`）。 */
  onImported: (importId: string) => void;
  /** AI 补题发布候选批次后通知父级刷新批次列表。 */
  onPublished: () => void;
}) {
  const router = useRouter();
  const [mode, setMode] = useState<Mode>('manual');

  const [type, setType] = useState<QuestionType>('single_choice');
  const [stem, setStem] = useState('');
  const [optionsText, setOptionsText] = useState('');
  const [answer, setAnswer] = useState('');
  const [explanation, setExplanation] = useState('');
  const [subjectId, setSubjectId] = useState('');
  const [gradeId, setGradeId] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const usesOptions = CHOICE_TYPES.includes(type);

  async function submitManual() {
    const composed = composeManualQuestion({
      stem,
      optionsText: usesOptions ? optionsText : '',
      answer,
      explanation,
    });
    if (!composed) {
      setError('请先填写题干。');
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const file = new File([composed], MANUAL_QUESTION_FILE_NAME, { type: 'text/markdown' });
      const detail = await createQuestionImport(file, { subjectId, gradeId });
      onImported(detail.importId);
    } catch (cause) {
      const apiError = asApiError(cause);
      // 失败保留全部已填内容，可直接重试（不重新渲染、不清空）
      setError(
        `提交失败（${apiError.code}）：${errorText(cause)} 已填写的内容保留，可直接重试。`,
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title="添加题目" onClose={onClose}>
      <div className="qb-panel" data-testid="qb-add-question">
        <SlidingGroup activeKey={mode} className="space-tabs" role="tablist" aria-label="添加题目方式">
          <button
            role="tab"
            id="qb-add-tab-manual"
            aria-selected={mode === 'manual'}
            aria-controls="qb-add-panel-manual"
            className={mode === 'manual' ? 'current' : ''}
            onClick={() => setMode('manual')}
          >
            手动录入
          </button>
          <button
            role="tab"
            id="qb-add-tab-generation"
            aria-selected={mode === 'generation'}
            aria-controls="qb-add-panel-generation"
            data-testid="qb-generation-open"
            className={mode === 'generation' ? 'current' : ''}
            onClick={() => setMode('generation')}
          >
            AI 补题
          </button>
        </SlidingGroup>

        {mode === 'manual' ? (
          <div
            id="qb-add-panel-manual"
            role="tabpanel"
            aria-labelledby="qb-add-tab-manual"
            className="qb-manual"
          >
            <p className="qb-hint">
              录入内容会先成为「导入草稿」，必须到校对页人工校对并确认后才入库；
              题干支持 Markdown 与 $LaTeX$ 公式。
            </p>

            <label className="qb-field" htmlFor="qb-manual-type">
              题型
              <select
                id="qb-manual-type"
                className="space-select"
                value={type}
                disabled={busy}
                onChange={(event) => setType(event.target.value as QuestionType)}
              >
                {(Object.keys(QUESTION_TYPE_LABEL) as QuestionType[]).map((item) => (
                  <option key={item} value={item}>
                    {QUESTION_TYPE_LABEL[item]}
                  </option>
                ))}
              </select>
            </label>

            <label className="qb-field" htmlFor="qb-manual-stem">
              题干
              <textarea
                id="qb-manual-stem"
                rows={4}
                value={stem}
                disabled={busy}
                placeholder="例：计算 $2^3 + \sqrt{9}$ 的值。"
                onChange={(event) => setStem(event.target.value)}
              />
            </label>

            {usesOptions && (
              <label className="qb-field" htmlFor="qb-manual-options">
                选项（每行一个，按 A/B/C… 自动编号）
                <textarea
                  id="qb-manual-options"
                  rows={4}
                  value={optionsText}
                  disabled={busy}
                  placeholder={'约 2\n约 3\n约 4'}
                  onChange={(event) => setOptionsText(event.target.value)}
                />
              </label>
            )}

            <label className="qb-field" htmlFor="qb-manual-answer">
              答案
              <input
                id="qb-manual-answer"
                value={answer}
                disabled={busy}
                placeholder={usesOptions ? '例：A（多选写 A、C）' : '例：对 / 2'}
                onChange={(event) => setAnswer(event.target.value)}
              />
            </label>

            <label className="qb-field" htmlFor="qb-manual-explanation">
              解析（可选）
              <textarea
                id="qb-manual-explanation"
                rows={3}
                value={explanation}
                disabled={busy}
                onChange={(event) => setExplanation(event.target.value)}
              />
            </label>

            <div className="qb-form-grid">
              <label className="qb-field" htmlFor="qb-manual-subject">
                学科（可选）
                <select
                  id="qb-manual-subject"
                  className="space-select"
                  value={subjectId}
                  disabled={busy || !taxonomy.ready}
                  onChange={(event) => setSubjectId(event.target.value)}
                >
                  <option value="">未设置</option>
                  {taxonomy.subjects.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
              <label className="qb-field" htmlFor="qb-manual-grade">
                年级（可选）
                <select
                  id="qb-manual-grade"
                  className="space-select"
                  value={gradeId}
                  disabled={busy || !taxonomy.ready}
                  onChange={(event) => setGradeId(event.target.value)}
                >
                  <option value="">未设置</option>
                  {taxonomy.grades.map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.label}
                    </option>
                  ))}
                </select>
              </label>
            </div>
            {!taxonomy.ready && (
              <p className="qb-hint">分类字典未读取成功：可先留空提交，稍后在校对页补齐分类。</p>
            )}

            {error && (
              <p className="space-banner error" role="alert">
                {error}
              </p>
            )}

            <div className="qb-actions">
              <button
                className="space-button primary"
                type="button"
                disabled={busy}
                onClick={() => void submitManual()}
              >
                <Upload size={14} aria-hidden />
                {busy ? '提交中…' : '提交为导入草稿'}
              </button>
              <button className="space-button" type="button" disabled={busy} onClick={onClose}>
                取消
              </button>
            </div>

            <p className="qb-hint">
              <PenLine size={12} aria-hidden /> 想要纯手工整理？也可以先「批量导入」上传自己的
              Markdown 试题文件，流程与手动录入一致。
            </p>
          </div>
        ) : (
          <div
            id="qb-add-panel-generation"
            role="tabpanel"
            aria-labelledby="qb-add-tab-generation"
          >
            <p className="qb-hint">
              <Sparkles size={12} aria-hidden /> AI 补题按知识点生成候选题目，产物同样是待校对草稿。
            </p>
            <GenerationPanel
              taxonomy={taxonomy}
              onClose={onClose}
              onPublished={onPublished}
              onOpenImport={(importId) => {
                onClose();
                router.push(`/question-bank/imports/${encodeURIComponent(importId)}`);
              }}
            />
          </div>
        )}
      </div>
    </Modal>
  );
}
