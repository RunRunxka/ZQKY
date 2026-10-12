'use client';

/**
 * 校对页左侧原文面板：
 * - 「未归属原文」区域逐块展示服务端返回的未归属原文块（文本 + 可读定位），永不隐藏；
 * - 「当前草稿的原文来源」列出所选草稿的 sourceSpans（可读序号与字符区间）。
 * 已归属块的正文不由 `GET /question-imports/{id}` 返回，这里如实标注，不伪造原文。
 *
 * ID 降级（设计 2.x）：主文案用可读序号（`原文块 N`），完整 `blockId` 只放在 `title`
 * 与定位提示里；序号取不到时明确写「序号未返回」，不编造。
 */

import type { DraftView, SourceBlockView } from '@/contracts/question-bank';
import { LOCATOR_KIND_LABEL, blockLabel, locatorLabel } from './labels';

export function SourcePane({
  draft,
  unassignedBlocks,
}: {
  draft: DraftView | null;
  unassignedBlocks: SourceBlockView[];
}) {
  const blockById = new Map(unassignedBlocks.map((block) => [block.blockId, block]));

  return (
    <aside className="qb-source" aria-label="原文与定位">
      <section className="qb-source-section">
        <header className="qb-source-head">
          <h2>未归属原文</h2>
          <span className={unassignedBlocks.length > 0 ? 'space-chip amber' : 'space-chip'}>
            {unassignedBlocks.length} 块
          </span>
        </header>
        <p className="qb-hint">
          这些原文块没有被任何草稿引用。它们仍然保留在批次里，可据此新增或合并草稿；
          系统不会因为拆题结果而丢弃原文。
        </p>
        {unassignedBlocks.length === 0 ? (
          <p className="qb-hint" role="status">
            本批次没有未归属原文块：服务端返回的原文块都已归属到草稿。
          </p>
        ) : (
          <ol className="qb-block-list">
            {unassignedBlocks.map((block) => (
              <li key={block.blockId} className="qb-block">
                <div className="qb-block-head">
                  <span className="qb-block-ordinal" title={block.blockId}>
                    {blockLabel(block.ordinal)}
                  </span>
                  <span className="qb-block-locator">
                    {LOCATOR_KIND_LABEL[block.locator.kind]}
                    {locatorLabel(block.locator) ? ` · ${locatorLabel(block.locator)}` : ''}
                  </span>
                  <span className="space-chip amber">未归属</span>
                </div>
                <p className="qb-block-text">{block.text}</p>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="qb-source-section">
        <header className="qb-source-head">
          <h2>当前草稿的原文来源</h2>
          {draft && <span className="space-chip">{draft.sourceSpans.length} 个区间</span>}
        </header>
        {!draft ? (
          <p className="qb-hint">先在右侧选择一道草稿，这里会显示它引用的原文块与字符区间。</p>
        ) : draft.sourceSpans.length === 0 ? (
          <p className="qb-hint">该草稿没有可定位的原文区间（可能由人工新建或拆分产生）。</p>
        ) : (
          <ul className="qb-span-list">
            {draft.sourceSpans.map((span) => {
              const block = blockById.get(span.blockId);
              return (
                <li key={`${span.blockId}-${span.charStart}`} className="qb-span">
                  <div className="qb-block-head">
                    <span className="qb-block-ordinal" title={span.blockId}>
                      {blockLabel(block?.ordinal ?? null)}
                    </span>
                    <span className="qb-block-locator">
                      字符 {span.charStart}–{span.charEnd}
                    </span>
                    {block && (
                      <span className="space-chip">{LOCATOR_KIND_LABEL[block.locator.kind]}</span>
                    )}
                  </div>
                  {block ? (
                    <p className="qb-block-text">{block.text}</p>
                  ) : (
                    <p className="qb-hint">
                      该原文块已被草稿引用，不在「未归属原文」列表中，正文不在此接口返回。
                    </p>
                  )}
                </li>
              );
            })}
          </ul>
        )}
        {draft && draft.warnings.length > 0 && (
          <ul className="qb-warning-list">
            {draft.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        )}
        {draft?.duplicateOfQuestionId && (
          <p className="qb-hint" role="status">
            服务端判定该草稿与已有题目 {draft.duplicateOfQuestionId}{' '}
            内容相同（指纹不含答案与解析）。 入库前请在「确认入库」里选择处理方式。
          </p>
        )}
      </section>
    </aside>
  );
}
