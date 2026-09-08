/** SSE 文本解析：按空行分发事件，支持多行 data 与注释行；调用方负责字节→文本解码。 */

export interface SseEvent {
  name: string;
  data: string;
}

export interface SseParser {
  /** 追加一段文本（可能从任意字符边界切断） */
  push(text: string): void;
  /** 流结束：处理残留行与未收尾事件 */
  end(): void;
}

export function createSseParser(onEvent: (event: SseEvent) => void): SseParser {
  let buffer = '';
  let eventName: string | null = null;
  let dataLines: string[] = [];

  function dispatch() {
    if (dataLines.length > 0) {
      onEvent({ name: eventName ?? 'message', data: dataLines.join('\n') });
    }
    eventName = null;
    dataLines = [];
  }

  function handleLine(line: string) {
    if (line === '') {
      dispatch();
    } else if (line.startsWith(':')) {
      // 注释/心跳
    } else if (line.startsWith('event:')) {
      eventName = line.slice(6).trim();
    } else if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trim());
    }
    // 其他 SSE 字段（id:/retry:）忽略
  }

  return {
    push(text: string) {
      buffer += text;
      let index = buffer.indexOf('\n');
      while (index >= 0) {
        const line = buffer.slice(0, index).replace(/\r$/, '');
        buffer = buffer.slice(index + 1);
        handleLine(line);
        index = buffer.indexOf('\n');
      }
    },
    end() {
      if (buffer !== '') {
        handleLine(buffer.replace(/\r$/, ''));
        buffer = '';
      }
      dispatch();
    },
  };
}
