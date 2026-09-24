'use client';
import { memo, useMemo } from 'react';
import { AnswerMarkdown } from './AnswerMarkdown';
import { splitMarkdownSegments } from './model/markdown-segments';

/**
 * 流式推理与助手正文（UX-REGRESSION-FIX v1 / CHAT-CONTENT-MATH-AND-FOLLOW v1）。
 *
 * 既要**流式过程中就显示公式**，又不能对每个 delta 重跑整段增长文本的解析：
 * - 已完整结束的块（空行边界、且不在未闭合围栏/块级公式内）逐块交给 memo 化的
 *   `AnswerMarkdown`；块内容不再变化 → 解析结果复用，整轮解析量回到 O(n)；
 * - 未完成的尾段：定界符闭合且长度受控时用 Markdown 渲染（公式即时可见）；否则
 *   按原文显示（`chat-reasoning-raw`），补齐后自动转为公式。
 *
 * 原始文本逐字保留（只做展示切分），复制与落库仍用供应商原文。
 */
export const StreamingMarkdown = memo(function StreamingMarkdown({
  text,
  rawClassName = 'chat-reasoning-raw',
}: {
  text: string;
  /** 尾段原文呈现所用的类名（推理与正文可各自复用样式） */
  rawClassName?: string;
}) {
  const segments = useMemo(() => splitMarkdownSegments(text), [text]);
  return (
    <>
      {segments.blocks.map((block, index) => (
        // 块只追加不修改：index 作为 key 稳定，配合 AnswerMarkdown 的 memo 复用解析结果
        <AnswerMarkdown key={index} text={block} />
      ))}
      {segments.tail
        ? segments.tailSafe
          ? <AnswerMarkdown key="tail" text={segments.tail} />
          : <p className={rawClassName}>{segments.tail}</p>
        : null}
    </>
  );
});
