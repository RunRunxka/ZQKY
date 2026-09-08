'use client';
import { useRef, useState } from 'react';
import { Check, ChevronDown, CircleAlert, LoaderCircle, Minus, Wrench } from 'lucide-react';
import type { ToolCallRecord } from '@/contracts/chat';
import { AnswerMarkdown } from './AnswerMarkdown';

const STATUS_LABEL: Record<ToolCallRecord['status'], string> = {
  running: '运行中',
  done: '已完成',
  error: '失败',
  cancelled: '已取消',
};

/**
 * 消息内工具/技能过程面板（对照 DeepTutor 原版 TracePresentation 的行内活动行）：
 * - 按 callId 去重更新，同一张卡片原地变化，不产生重复卡片；
 * - 手动展开/收起由卡片自身状态固定，正文流式增量不会重置；
 * - 展开动画使用与原版一致的 300ms + Tailwind ease-out（cubic-bezier(0,0,0.2,1)，
 *   motion.css --ease-standard）grid 参数；减少动画由全局机制接管，不在正文增量时重播；
 * - 收起的详情通过 inert 移出焦点顺序与可访问树（R7），收起时若焦点在详情内则移回头部，
 *   保留退出动画与快速开关能力。详情内容以安全 Markdown 渲染，不执行扩展返回的 HTML。
 */
function ToolCard({ record }: { record: ToolCallRecord }) {
  // null = 跟随默认（收起）；手动点击后固定，不随正文更新变化
  const [userOpen, setUserOpen] = useState<boolean | null>(null);
  const headRef = useRef<HTMLButtonElement>(null);
  const detailRef = useRef<HTMLDivElement>(null);
  const open = userOpen ?? false;
  const hasDetail = Boolean(record.detail);
  function toggle() {
    if (!hasDetail) return;
    if (open && detailRef.current?.contains(document.activeElement)) {
      // R7：收起时焦点落在详情内（链接/复制按钮等），先移回头部再折叠
      headRef.current?.focus();
    }
    setUserOpen(!open);
  }
  return (
    <li className={`chat-tool-card ${record.status}`}>
      <button
        ref={headRef}
        type="button"
        className="chat-tool-head"
        aria-expanded={hasDetail ? open : undefined}
        aria-label={`${record.name}：${STATUS_LABEL[record.status]}${hasDetail ? '，点击展开详情' : ''}`}
        onClick={toggle}
        disabled={!hasDetail}
      >
        <span className="chat-tool-icon" aria-hidden="true">
          {record.status === 'running' ? (
            <LoaderCircle size={13} className="chat-tool-spin" />
          ) : record.status === 'done' ? (
            <Check size={13} />
          ) : record.status === 'error' ? (
            <CircleAlert size={13} />
          ) : (
            <Minus size={13} />
          )}
        </span>
        <span className="chat-tool-kind">{record.kind === 'mcp' ? 'MCP' : 'Skill'}</span>
        <span className="chat-tool-name">{record.name}</span>
        <span className={`chat-tool-status ${record.status}`}>
          {STATUS_LABEL[record.status]}
        </span>
        {hasDetail && (
          <ChevronDown size={13} className={`chat-tool-chevron ${open ? 'open' : ''}`} />
        )}
      </button>
      {record.note && <p className="chat-tool-note">{record.note}</p>}
      {hasDetail && (
        <div ref={detailRef} className={`chat-tool-detail ${open ? 'open' : ''}`} inert={!open}>
          <div className="chat-tool-detail-inner">
            <AnswerMarkdown text={record.detail!} />
          </div>
        </div>
      )}
    </li>
  );
}

export function ToolProcessPanel({ toolCalls }: { toolCalls?: ToolCallRecord[] }) {
  if (!toolCalls?.length) return null;
  return (
    <div className="chat-tools">
      <p className="chat-tools-title">
        <Wrench size={12} />
        执行过程（本地模拟）
      </p>
      <ul className="chat-tool-list">
        {toolCalls.map((record) => (
          <ToolCard key={record.callId} record={record} />
        ))}
      </ul>
    </div>
  );
}
