'use client';
import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';
import { StreamingMarkdown } from './StreamingMarkdown';

/**
 * DeepTutor 42fab3c AssistantActivity：阶段自动展开，手动选择固定在本消息。
 *
 * 流式 Markdown 使用安全切分：已结束的块复用解析结果，未闭合（或过长）的尾段暂按原文
 * 显示，定界符闭合后即时转为 Markdown/公式。推理流仍活动时，用户重开折叠区继续跟随；
 * 手动上滚后保留阅读位置，原文逐字保留。
 */
export function ReasoningDisclosure({
  text,
  working,
  autoExpand = working,
  children,
}: {
  text?: string;
  working: boolean;
  autoExpand?: boolean;
  children: ReactNode;
}) {
  const [userOpen, setUserOpen] = useState<boolean | null>(null);
  const open = !!text && (userOpen ?? autoExpand);
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
  const lastText = useRef(text);
  const manualScroll = useRef(false);
  const scrollIntentExpires = useRef(0);
  const previousScrollTop = useRef<number | null>(null);
  const touchStartY = useRef<number | null>(null);

  useEffect(() => {
    if (lastText.current !== text) {
      lastText.current = text;
      following.current = !manualScroll.current;
    }
  }, [text]);

  useEffect(() => {
    if (!open || !working || !following.current) return;
    const el = viewport.current;
    if (!el) return;
    // 同一帧内合并滚动写入；回调再次检查跟随与节点身份，避免抢回用户阅读位置。
    const frame = requestAnimationFrame(() => {
      if (!following.current || viewport.current !== el || !el.isConnected) return;
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
            manualScroll.current = false;
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
              const previousTop = previousScrollTop.current;
              previousScrollTop.current = el.scrollTop;
              if (previousTop === null || previousTop === el.scrollTop) return;
              const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 32;
              const intentActive = performance.now() < scrollIntentExpires.current;
              if (!intentActive || atBottom) {
                following.current = atBottom;
                manualScroll.current = !atBottom;
              }
            }}
            onWheel={(event) => {
              if (event.deltaY < 0) {
                following.current = false;
                manualScroll.current = true;
                scrollIntentExpires.current = performance.now() + 500;
              }
            }}
            onTouchStart={(event) => {
              touchStartY.current = event.touches[0]?.clientY ?? null;
            }}
            onTouchMove={(event) => {
              const y = event.touches[0]?.clientY;
              if (y !== undefined && touchStartY.current !== null && y > touchStartY.current) {
                following.current = false;
                manualScroll.current = true;
                scrollIntentExpires.current = performance.now() + 500;
              } else if (
                y !== undefined &&
                touchStartY.current !== null &&
                y < touchStartY.current
              ) {
                scrollIntentExpires.current = performance.now() + 500;
              }
            }}
            onKeyDown={(event) => {
              if (['ArrowUp', 'PageUp', 'Home'].includes(event.key)) {
                following.current = false;
                manualScroll.current = true;
                scrollIntentExpires.current = performance.now() + 500;
              } else if (['ArrowDown', 'PageDown', 'End'].includes(event.key)) {
                scrollIntentExpires.current = performance.now() + 500;
              }
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
