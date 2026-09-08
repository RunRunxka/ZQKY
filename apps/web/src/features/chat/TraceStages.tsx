'use client';
import { Check, CircleDashed, Loader2, X } from 'lucide-react';
import type { TraceStageRecord } from '@/contracts/chat';

/**
 * S4 轮内阶段时间线（对照参考 TracePresentation 的阶段流水/研究阶段卡）：
 * running=旋转、done=对勾、cancelled/error=叉；完成的阶段默认折叠为紧凑行，
 * 有进行中阶段时整列展开。重复 stage 事件按 stageId 原地更新（store 保证）。
 */
export function TraceStages({ stages }: { stages?: TraceStageRecord[] }) {
  if (!stages?.length) return null;
  const hasRunning = stages.some((s) => s.status === 'running');
  if (!hasRunning) return null; // 终态消息只保留过程/工具与正文，不渲染静态阶段流水
  return (
    <ol className="chat-stages" aria-label="本轮阶段">
      {stages.map((stage) => (
        <li key={stage.stageId} className={`chat-stage ${stage.status}`}>
          <span className="chat-stage-icon" aria-hidden>
            {stage.status === 'running' ? (
              <Loader2 size={12} className="chat-stage-spin" />
            ) : stage.status === 'done' ? (
              <Check size={12} />
            ) : (
              <X size={12} />
            )}
          </span>
          <span className="chat-stage-label">{stage.label}</span>
          {stage.status === 'running' && <CircleDashed size={11} className="chat-stage-pulse" />}
        </li>
      ))}
    </ol>
  );
}
