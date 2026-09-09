/**
 * 写作 AI 修改服务（S5-E）：与主聊天/伴生一致的 ChatService 事件模型，
 * 显式模拟——改写/润色/扩写/全文生成为本地确定性模板流式输出，不访问模型。
 * 取消经 AbortSignal；armFailure 布防一次可重试失败。
 */

export type WritingAiMode = 'rewrite' | 'polish' | 'expand' | 'generate';

export interface WritingAiRequest {
  docId: string;
  turnId: string;
  mode: WritingAiMode;
  instruction: string;
  /** 改写对象：选中文本（rewrite/polish/expand）或当前全文/标题（generate） */
  sourceText: string;
  signal: AbortSignal;
}

export interface WritingAiService {
  readonly kind: 'mock';
  armFailure(): void;
  run(request: WritingAiRequest, emit: (event: { type: 'turn-start' | 'text' | 'error' | 'end'; delta?: string; message?: string; retryable?: boolean }) => void): Promise<void>;
}

const MODE_LABELS: Record<WritingAiMode, string> = {
  rewrite: '改写',
  polish: '润色',
  expand: '扩写',
  generate: '生成',
};

export function writingAiModeLabel(mode: WritingAiMode): string {
  return MODE_LABELS[mode];
}

/** 本地确定性转换（显式【模拟生成】标注；不访问模型） */
export function composeWritingAiResult(request: Pick<WritingAiRequest, 'mode' | 'instruction' | 'sourceText'>): string {
  const note = `（【模拟生成】本地模板转换，未接入模型${request.instruction.trim() ? `；已参考指令：${request.instruction.trim()}` : ''}）`;
  const source = request.sourceText.trim();
  if (request.mode === 'generate') {
    return [
      `# ${request.instruction.trim() || '新文稿'}（模拟生成提纲）`,
      '',
      '- 目标：明确本节要解决的学习问题；',
      '- 主线：例子 → 概念 → 练习；',
      '- 小结：用自己的话复述要点。',
      '',
      note,
    ].join('\n');
  }
  if (request.mode === 'rewrite') {
    return `${source.replace(/\s+/g, ' ').trim()}${note}`;
  }
  if (request.mode === 'polish') {
    return `${source}${source.endsWith('。') || !source ? '' : '。'}表述更清晰、衔接更自然，逻辑重点已突出${note}`;
  }
  return `${source}${source ? '\n\n' : ''}补充展开：进一步说明该要点的适用条件与常见误区，并给出一个可操作的教学示例${note}`;
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

function chunkText(text: string, size = 12): string[] {
  const chars = [...text];
  const chunks: string[] = [];
  for (let index = 0; index < chars.length; index += size) {
    chunks.push(chars.slice(index, index + size).join(''));
  }
  return chunks;
}

export function createWritingAiService(options?: { chunkDelayMs?: number }): WritingAiService {
  const chunkDelay = options?.chunkDelayMs ?? 40;
  let failNext = false;
  return {
    kind: 'mock',
    armFailure() {
      failNext = true;
    },
    async run(request, emit) {
      emit({ type: 'turn-start' });
      await sleep(chunkDelay, request.signal);
      if (failNext) {
        failNext = false;
        emit({ type: 'error', message: '已按要求模拟一次 AI 修改失败，可直接重试。', retryable: true });
        return;
      }
      const result = composeWritingAiResult(request);
      for (const chunk of chunkText(result)) {
        await sleep(chunkDelay, request.signal);
        emit({ type: 'text', delta: chunk });
      }
      emit({ type: 'end' });
    },
  };
}
