'use client';
import { useEffect, useId, useRef, useState, type ReactNode } from 'react';
import { ChevronDown } from 'lucide-react';
import { AnswerMarkdown } from './AnswerMarkdown';

/** DeepTutor 42fab3c AssistantActivity：阶段自动展开，手动选择固定在本消息。 */
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
  const id = useId();
  const viewport = useRef<HTMLDivElement>(null);
  const following = useRef(true);
  useEffect(() => {
    if (open && working && following.current && viewport.current) {
      viewport.current.scrollTop = viewport.current.scrollHeight;
    }
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
            {text && <AnswerMarkdown text={text} />}
          </div>
        </div>
      </div>
    </div>
  );
}
