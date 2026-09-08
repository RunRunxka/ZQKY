'use client';
import { ArrowUpRight, Check, Sparkles, Info, ArrowRight, LoaderCircle } from 'lucide-react';
import { useLessonEditor } from '../model/EditorContext';
import { Field } from '@/components/ui/Field';
import { lessonTypeLabels } from '../model/types';
import { labels } from '../model/field-labels';
import { requirementExample } from '../model/defaults';
import { validateData } from '../services/drafts';
import { mergeProposal } from '../services/fill';
export function NlFillPanel() {
  const {
    data,
    replace,
    busy,
    input,
    setInput,
    proposal,
    setProposal,
    mode,
    setMode,
    notice,
    parse,
  } = useLessonEditor();
  return (
    <>
      <div className="fill-panel">
        <div className="fill-intro-icon">
          <Sparkles size={22} />
        </div>
        <h2>把已有要求，整理成教案</h2>
        <p>
          粘贴备课内容，按“字段：内容”识别。
          <br />
          先预览结果，再决定填入哪些内容。
        </p>
        <div className="fill-label">
          <span>你的备课要求</span>
          <button
            onClick={() => {
              setInput(requirementExample);
              setProposal(null);
            }}
          >
            插入示例
            <ArrowUpRight size={13} />
          </button>
        </div>
        <textarea
          aria-label="备课要求"
          rows={13}
          placeholder={
            '课题：荷塘月色\n总课时：2\n核心素养：…\n教学过程：\n情境导入 | 教学设计 | 二次备课'
          }
          value={input}
          onChange={(e) => {
            setInput(e.target.value);
            setProposal(null);
          }}
        />
        <div className="fill-disclaimer">
          <Info size={14} />
          <span>当前使用本地规则解析，未连接 AI 模型。自由描述仅提取明确字段。</span>
        </div>
        <button
          className="button primary full-width"
          disabled={!input.trim() || busy}
          onClick={parse}
        >
          {busy ? <LoaderCircle size={16} className="spin" /> : <Sparkles size={16} />}识别填充内容
          <ArrowRight size={16} />
        </button>
        {proposal && (
          <div className="proposal">
            <div className="proposal-title">
              <Check size={17} />
              <h3>识别到 {Object.keys(proposal.patch).length} 个字段</h3>
            </div>
            {Object.entries(proposal.patch).map(([k, v]) => (
              <div className="proposal-field" key={k}>
                <strong>{labels[k] ?? k}</strong>
                <p>
                  {k === 'process'
                    ? (v as typeof data.process)
                        .map(
                          (p) =>
                            `${p.stage}：${p.design}${p.secondary ? `（二次备课：${p.secondary}）` : ''}`,
                        )
                        .join('\n')
                    : Array.isArray(v)
                      ? v
                          .map((t) => lessonTypeLabels[t as keyof typeof lessonTypeLabels] ?? t)
                          .join('、')
                      : String(v)}
                </p>
              </div>
            ))}
            {proposal.warnings.length > 0 && (
              <div className="fill-warnings">
                <strong>以下内容需要检查</strong>
                {proposal.warnings.map((w, i) => (
                  <p key={i}>{w}</p>
                ))}
              </div>
            )}
            <Field label="填入方式">
              <select value={mode} onChange={(e) => setMode(e.target.value as typeof mode)}>
                <option value="overwrite">替换已识别字段，保留其他内容</option>
                <option value="append">追加长文本与教学环节</option>
              </select>
            </Field>
            <button
              className="button primary full-width"
              disabled={!Object.keys(proposal.patch).length}
              onClick={() => {
                try {
                  const next = mergeProposal(data, proposal.patch, mode);
                  validateData(next);
                  replace(next);
                  setProposal(null);
                  notice('内容已填入，可以通过撤销恢复');
                } catch (e) {
                  notice((e as Error).message);
                }
              }}
            >
              <Check size={16} />
              确认填入教案
            </button>
          </div>
        )}
      </div>
    </>
  );
}
