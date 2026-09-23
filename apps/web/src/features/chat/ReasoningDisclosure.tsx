'use client';
import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';
import { StreamingMarkdown } from './StreamingMarkdown';

/**
 * DeepTutor 42fab3c AssistantActivity：阶段自动展开，手动选择固定在本消息。
 *
 * UX-PERF-CLOSEOUT v1（长推理流卡顿）：推理正文不再在**每次增量**上重跑整段增长文本的
 * Markdown/数学/高亮解析。
 * UX-REGRESSION-FIX v1（公式回归）：改为**流式安全切分**——已完整结束的块逐块渲染并复用
 * 解析结果，未完成的尾段在定界符闭合时同样用 Markdown 渲染，因此**流式过程中公式即时可见**；
 * 只有未闭合（或过长）的尾段暂以原文显示，补齐后自动转为公式。折叠时不渲染正文内容，
 * 展开后再一次性渲染（解析结果按块复用）。
 * 原文逐字保留、折叠与自动滚动语义不变。
 */
export function ReasoningDisclosure({
  text,
  working,
  children,
}: {
  text?: string;
  working: boolean;
  children: ReactNode;
}) {
  const [userOpen, setUserOpen] = useState<boolean | null>(null);
  const open = !!text && (userOpen ?? working);
  /**
   * 折叠时先把内容留在 DOM 里覆盖 300ms 折叠过渡（否则内容会在过渡开始时瞬间消失，
   * 折叠动画变成"空框收缩"）；从未展开过的历史消息不渲染内容（不做无谓解析）。
   */
  const [keepMounted, setKeepMounted] = useState(false);
  useEffect(() => {
    if (open) {
      setKeepMounted(true);
      return;
    }
    const timer = window.setTimeout(() => setKeepMounted(false), 320);
    return () => window.clearTimeout(timer);
  }, [open]);
  const id = useId();
  const viewport = useRef<HTMLDivElement>(null);
  const following = useRef(true);

  useEffect(() => {
    if (!open || !working || !following.current) return;
    const el = viewport.current;
    if (!el) return;
    // 同一帧内的多次增量合并为一次滚动写入，避免每次提交都做同步布局读写。
    // 关键：写入前**在回调内再次**确认用户仍选择跟随最新——排入 rAF 与执行之间有
    // 一个窗口，用户在这段时间上滚时不得被拉回底部（独立验收 A1 实测首帧被写回
    // 2095→4052；原实现"判断即同步写入"的窗口小得多，此处不得扩大）。
    const frame = requestAnimationFrame(() => {
      if (!following.current) return;
      el.scrollTop = el.scrollHeight;
    });
    return () => cancelAnimationFrame(frame);
  }, [text, open, working]);
  return (
    <div className="chat-activity">
      {text ? (
        <button
          type="button"
          className="chat-assistant-label chat-activity-toggle"
          aria-label="推理过程"
          aria-expanded={open}
          aria-controls={id}
          onClick={() => {
            following.current = true;
            setUserOpen(!open);
          }}
        >
          {children}
          <ChevronDown
            size={14}
            className={open ? 'chat-activity-chevron open' : 'chat-activity-chevron'}
          />
        </button>
      ) : (
        <div className="chat-assistant-label">{children}</div>
      )}
      <div
        className={`chat-reasoning-fold ${open ? 'open' : ''}`}
        inert={!open}
        aria-hidden={!open}
      >
        <div className="chat-reasoning-clip">
          <div
            id={id}
            ref={viewport}
            className="chat-reasoning-body"
            tabIndex={open ? 0 : -1}
            role="region"
            aria-label="推理内容"
            onScroll={(event) => {
              const el = event.currentTarget;
              following.current = el.scrollHeight - el.scrollTop - el.clientHeight < 32;
            }}
          >
            {/* 展开时渲染（流式期间也渲染，公式即时可见）；折叠后保留 320ms 覆盖折叠过渡，
                之后再卸载（历史消息从未展开时不渲染，展开时按块复用解析结果） */}
            {text && keepMounted && <StreamingMarkdown text={text} />}
          </div>
        </div>
      </div>
    </div>
  );
}
