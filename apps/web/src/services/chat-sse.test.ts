import { describe, expect, it } from 'vitest';
import { createSseParser } from './chat-sse';

function collect() {
  const events: { name: string; data: string }[] = [];
  const parser = createSseParser((event) => events.push(event));
  return { events, parser };
}

describe('SSE 解析器', () => {
  it('按空行分发事件并解析 event/data 字段', () => {
    const { events, parser } = collect();
    parser.push('event: text.delta\ndata: {"text":"你好"}\n\nevent: message.end\ndata: {}\n\n');
    expect(events).toEqual([
      { name: 'text.delta', data: '{"text":"你好"}' },
      { name: 'message.end', data: '{}' },
    ]);
  });

  it('事件跨多次 push 分块到达仍能正确组装', () => {
    const { events, parser } = collect();
    parser.push('event: message.start\nda');
    parser.push('ta: {"requestId":"abc"}\n\n');
    parser.push('event: text.delta\ndata: {"text":"片段"}\n');
    parser.end();
    expect(events).toEqual([
      { name: 'message.start', data: '{"requestId":"abc"}' },
      { name: 'text.delta', data: '{"text":"片段"}' },
    ]);
  });

  it('多行 data 以换行合并，注释行被忽略', () => {
    const { events, parser } = collect();
    parser.push(': 心跳\ndata: 第一行\ndata: 第二行\n\n');
    expect(events).toEqual([{ name: 'message', data: '第一行\n第二行' }]);
  });

  it('处理 CRLF 行尾', () => {
    const { events, parser } = collect();
    parser.push('event: text.delta\r\ndata: {"text":"ok"}\r\n\r\n');
    expect(events).toEqual([{ name: 'text.delta', data: '{"text":"ok"}' }]);
  });

  it('没有 event 字段时缺省为 message', () => {
    const { events, parser } = collect();
    parser.push('data: 任意\n\n');
    expect(events).toEqual([{ name: 'message', data: '任意' }]);
  });
});
