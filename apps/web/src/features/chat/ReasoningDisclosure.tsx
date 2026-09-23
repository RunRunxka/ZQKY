'use client';
import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';
import { AnswerMarkdown } from './AnswerMarkdown';

/**
 * DeepTutor 42fab3c AssistantActivity：阶段自动展开，手动选择固定在本消息。
 *
 * UX-PERF-CLOSEOUT v1（长推理流卡顿）：推理正文不再在**每次增量**上重跑
 * Markdown/数学/高亮解析——活跃流期间与折叠未展开时以等宽换行的纯文本轻量呈现，
 * 仅在"已结束且用户正看着"时做一次完整的 Markdown/KaTeX 渲染。
 * 原文逐字保留、折叠与自动滚动语义不变；公式在展开后照常正确渲染。
 */
export function ReasoningDisclosure({
  text,
  working,
  streaming = false,
  children,
}: {
  text?: string;
  working: boolean;
  /** 本轮是否仍在流式：true 时只做轻量呈现，避免对增长中的全文反复解析 */
  streaming?: boolean;
  children: ReactNode;
}) {
  const [userOpen, setUserOpen] = useState<boolean | null>(null);
  const open = !!text && (userOpen ?? working);
  const id = useId();
  const viewport = useRef<HTMLDivElement>(null);
  const following = useRef(true);
  /** 只有"已结束 + 正在展开"才值得付完整解析成本；其余情况轻量呈现 */
  const renderRich = open && !streaming;
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
            {text &&
              (renderRich ? (
                <AnswerMarkdown text={text} />
              ) : (
                <p className="chat-reasoning-raw">{text}</p>
              ))}
          </div>
        </div>
      </div>
    </div>
  );
}
