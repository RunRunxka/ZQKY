'use client';
import { useCallback, useEffect, useRef, useState } from 'react';
import { DoorClosed, DoorOpen, Send, Unplug } from 'lucide-react';
import {
  appendWhisperMessage,
  closeRoom,
  crisisRedirectFor,
  createRoom,
  readRoom,
  subscribeWhisper,
  type WhisperMessage,
  type WhisperSeat,
} from '@/services/whisper-store';
import { AnswerMarkdown } from '@/features/chat/AnswerMarkdown';
import '@/features/space/styles/space.css';

const SEAT_LABELS: Record<WhisperSeat, string> = { visitor: '访客席', trainee: '学员席' };

/** /whisper 密室（对照参考 whisper/page.tsx：双席位、房间结束态、危机引导；回复为显式模拟流式） */
export function WhisperRoomView() {
  const [room, setRoom] = useState<ReturnType<typeof readRoom>>(null);
  const [seat, setSeat] = useState<WhisperSeat>('visitor');
  const [draft, setDraft] = useState('');
  const [streaming, setStreaming] = useState<{ seat: WhisperSeat; text: string } | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);
  const bodyRef = useRef<HTMLDivElement>(null);
  const timersRef = useRef<number[]>([]);

  const refresh = useCallback(() => {
    try {
      setRoom(readRoom());
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : '房间数据无法读取，原数据未修改。');
    }
  }, []);

  useEffect(() => {
    refresh();
    return subscribeWhisper(refresh);
  }, [refresh]);

  useEffect(
    () => () => {
      abortRef.current?.abort();
      for (const timer of timersRef.current) window.clearTimeout(timer);
    },
    [],
  );

  const messages: WhisperMessage[] = room ? room.messages[seat] : [];
  useEffect(() => {
    const el = bodyRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length, streaming?.text]);

  function send() {
    const content = draft.trim();
    if (!content || !room || room.closed || streaming) return;
    const redirect = crisisRedirectFor(content);
    appendWhisperMessage(room.roomId, seat, { role: 'user', content });
    setDraft('');
    if (redirect) {
      appendWhisperMessage(room.roomId, seat, { role: 'system', content: redirect });
      return;
    }
    // 显式模拟流式回复（统一事件模型形态：turn-start → 增量 → end）
    const controller = new AbortController();
    abortRef.current = controller;
    let text = '';
    setStreaming({ seat, text: '' });
    const timers: number[] = [];
    const reply = `【模拟回复】已收到${SEAT_LABELS[seat]}的消息。whisper 后端通道未接入，本回复为本地显式模拟，可随时结束房间。`;
    const chunks = reply.match(/.{1,10}/gs) ?? [reply];
    chunks.forEach((chunk, index) => {
      timers.push(
        window.setTimeout(() => {
          text += chunk;
          setStreaming({ seat, text });
          if (index === chunks.length - 1) {
            timersRef.current = timersRef.current.filter((timer) => !timers.includes(timer));
            appendWhisperMessage(room.roomId, seat, { role: 'assistant', content: text });
            setStreaming(null);
            abortRef.current = null;
          }
        }, 60 * (index + 1)),
      );
    });
    timersRef.current.push(...timers);
  }

  return (
    <div className="space-page">
      <header className="space-header">
        <div className="space-header-row">
          <h1>Whisper 密室</h1>
          <div className="space-card-actions">
            {room ? (
              <>
                <span className="space-chip" aria-label="房间号">
                  房间 {room.roomId}
                </span>
                {!room.closed ? (
                  <button
                    className="space-button"
                    aria-label="结束房间"
                    onClick={() => {
                      closeRoom(room.roomId);
                    }}
                  >
                    <DoorClosed size={14} />
                    结束房间
                  </button>
                ) : (
                  <button
                    className="space-button primary"
                    aria-label="新建房间"
                    onClick={() => {
                      createRoom();
                    }}
                  >
                    <DoorOpen size={14} />
                    新建房间
                  </button>
                )}
              </>
            ) : (
              <button className="space-button primary" aria-label="开始密室" onClick={() => createRoom()}>
                <DoorOpen size={14} />
                开始密室
              </button>
            )}
          </div>
        </div>
        <p className="space-description">
          双席位密室对话（访客/学员分席，各自独立会话线）；危机表述自动触发系统引导卡。后端通道未接入：回复为显式模拟（【模拟回复】）。
        </p>
      </header>
      <main className="space-content">
        {error && (
          <div className="space-banner error" role="alert">
            {error}
          </div>
        )}
        <div className="space-tabs" role="tablist" aria-label="席位切换" style={{ marginBottom: 12 }}>
          {(['visitor', 'trainee'] as WhisperSeat[]).map((value) => (
            <button key={value} role="tab" aria-selected={seat === value} className={seat === value ? 'current' : ''} onClick={() => setSeat(value)}>
              {SEAT_LABELS[value]}
            </button>
          ))}
        </div>
        {!room ? (
          <div className="space-empty">
            <strong>还没有开启密室</strong>
            <span>点击「开始密室」创建房间；参考 whisper 能力由服务端控制，此处保留可演示前端路径（显式模拟）。</span>
          </div>
        ) : (
          <div className="reading-companion" style={{ minHeight: 360 }}>
            {room.closed && (
              <div className="space-banner" role="status" style={{ margin: '10px 12px 0' }}>
                本房间已结束，发送已停用；可新建房间继续。
              </div>
            )}
            <div className="reading-companion-body" ref={bodyRef} aria-label="密室消息">
              {messages.length === 0 && !streaming ? (
                <p className="space-footnote" style={{ margin: 0 }}>
                  {SEAT_LABELS[seat]}暂无消息。发送第一条消息开始对话。
                </p>
              ) : (
                <>
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`reading-msg ${message.role === 'system' ? 'assistant' : message.role}`}
                      style={message.role === 'system' ? { border: '1px solid rgba(37,99,235,0.4)', background: 'rgba(37,99,235,0.06)', maxWidth: '100%' } : undefined}
                    >
                      <AnswerMarkdown text={message.content} />
                    </div>
                  ))}
                  {streaming && streaming.seat === seat && (
                    <div className="reading-msg assistant" aria-label="回复生成中">
                      <AnswerMarkdown text={streaming.text} />
                    </div>
                  )}
                </>
              )}
            </div>
            <div className="reading-composer">
              <textarea
                aria-label="密室消息输入"
                value={draft}
                disabled={room.closed}
                placeholder={room.closed ? '房间已结束' : `以${SEAT_LABELS[seat]}身份发言…`}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === 'Enter' && !event.shiftKey && !event.nativeEvent.isComposing) {
                    event.preventDefault();
                    send();
                  }
                }}
              />
              <button
                className="space-button primary"
                onClick={send}
                aria-label="发送密室消息"
                disabled={room.closed || !draft.trim() || Boolean(streaming)}
              >
                {streaming ? <Unplug size={14} /> : <Send size={14} />}
                {streaming ? '回复中' : '发送'}
              </button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
