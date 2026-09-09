/**
 * 阅读伴生 AI 服务（R32.1）：实现与主聊天一致的 ChatService 事件模型
 * （turn-start/process/stage/text/usage/end/error），以显式模拟事件驱动
 * 流式、过程、取消、失败与重试；不再一次性 append 模板字符串。
 * 内容为本地确定性模板（显式【模拟回复】），不访问模型、检索或外部工具；
 * 取消经 AbortSignal 语义（对照主聊天 mock 服务的 abort 行为）。
 */
import type { ChatServiceEvent } from '@/features/chat/model/chat-service';

export interface CompanionServiceRequest {
  sessionId: string;
  turnId: string;
  materialTitle: string | null;
  /** 问 AI 时携带的选中文本 */
  quote?: string;
  userText: string;
  signal: AbortSignal;
}

export interface CompanionService {
  readonly kind: 'mock';
  /** 布防一次模拟失败：下一轮在正文输出前以可重试错误收尾 */
  armFailure(): void;
  run(request: CompanionServiceRequest, emit: (event: ChatServiceEvent) => void): Promise<void>;
}

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve, reject) => {
    const timer = setTimeout(resolve, ms);
    const onAbort = () => {
      clearTimeout(timer);
      reject(new DOMException('aborted', 'AbortError'));
    };
    if (signal.aborted) {
      onAbort();
      return;
    }
    signal.addEventListener('abort', onAbort, { once: true });
  });
}

function chunkText(text: string, size = 14): string[] {
  const chars = [...text];
  const chunks: string[] = [];
  for (let index = 0; index < chars.length; index += size) {
    chunks.push(chars.slice(index, index + size).join(''));
  }
  return chunks;
}

/** 伴生回复模板（与 reading-store 的本地模板一致，显式模拟标注） */
export function composeCompanionReply(input: {
  materialTitle: string | null;
  userText: string;
  quote?: string;
}): string {
  const materialPart = input.materialTitle ? `关于《${input.materialTitle}》` : '关于当前阅读内容';
  const quotePart = input.quote
    ? `，你选中的「${input.quote.slice(0, 40)}${input.quote.length > 40 ? '…' : ''}」已作为上下文`
    : '';
  return [
    `【模拟回复】${materialPart}${quotePart}：伴生助手尚未接入模型服务，本回复为本地模板生成，不执行真实检索或推理。`,
    '建议动作：',
    '- 用自己的话概括本段要点；',
    '- 对不懂的句子使用「选中 → 问 AI」或添加批注；',
    '- 完成后用「发到笔记本」沉淀记录。',
  ].join('\n');
}

export function createReadingCompanionService(options?: { chunkDelayMs?: number }): CompanionService {
  const chunkDelay = options?.chunkDelayMs ?? 60;
  let failNext = false;
  return {
    kind: 'mock',
    armFailure() {
      failNext = true;
    },
    async run(request, emit) {
      const turn = { sessionId: request.sessionId, turnId: request.turnId };
      emit({ ...turn, type: 'turn-start' });
      emit({
        ...turn,
        type: 'process',
        delta: '[模拟] 结合当前材料与选区整理回答线索，不访问模型、检索或外部工具。',
      });
      emit({ ...turn, type: 'stage', stageId: 'organize', label: '正在组织回答', phase: 'start' });
      await sleep(chunkDelay, request.signal);
      if (failNext) {
        failNext = false;
        emit({ ...turn, type: 'error', error: { code: 'MOCK_COMPANION_ERROR', message: '已按要求模拟一次伴生回复失败，可直接重试。', retryable: true } });
        return;
      }
      emit({ ...turn, type: 'stage', stageId: 'organize', label: '正在组织回答', phase: 'end' });
      const reply = composeCompanionReply({
        materialTitle: request.materialTitle,
        userText: request.userText,
        quote: request.quote,
      });
      for (const chunk of chunkText(reply)) {
        await sleep(chunkDelay, request.signal);
        emit({ ...turn, type: 'text', delta: chunk });
      }
      emit({ ...turn, type: 'usage', usage: { outputTokens: Math.ceil(reply.length / 2) } });
      emit({ ...turn, type: 'end', finishReason: 'stop' });
    },
  };
}
