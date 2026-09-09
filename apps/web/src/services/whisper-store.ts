/**
 * Whisper 密室聊天本地仓储（S5-E，用途以固定源码为准：双席位密室对话，
 * 访客/学员分席、房间结束态、危机引导；参考经 UnifiedTurnClient 流式，
 * 目标为统一事件模型的显式模拟）。存储采用严格读取 + 回滚加固。
 */

export type WhisperSeat = 'visitor' | 'trainee';

export interface WhisperMessage {
  id: string;
  seat: WhisperSeat;
  role: 'user' | 'assistant' | 'system';
  content: string;
  at: string;
}

export interface WhisperRoom {
  roomId: string;
  closed: boolean;
  createdAt: string;
  updatedAt: string;
  /** 分席消息（访客/学员各自会话线；参考 filterMessagesForSeat 的本地形态） */
  messages: Record<WhisperSeat, WhisperMessage[]>;
}

const KEY = 'zhiqikeyuan:whisper-room';
const EVENT = 'zqky:whisper';

export class WhisperStorageError extends Error {}

function uid(prefix: string): string {
  return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
}

export function readRoom(): WhisperRoom | null {
  if (typeof window === 'undefined') return null;
  let raw: string | null;
  try {
    raw = window.localStorage.getItem(KEY);
  } catch (cause) {
    throw new WhisperStorageError('Whisper 房间数据读取被拒绝，原数据未修改。', { cause });
  }
  if (raw === null) return null;
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new WhisperStorageError('Whisper 房间数据已损坏；为保护原数据未做修改。');
  }
  if (!parsed || typeof parsed !== 'object' || typeof (parsed as WhisperRoom).roomId !== 'string') {
    throw new WhisperStorageError('Whisper 房间数据格式异常；为保护原数据未做修改。');
  }
  return parsed as WhisperRoom;
}

function commit(room: WhisperRoom | null): void {
  if (typeof window === 'undefined') return;
  const original = window.localStorage.getItem(KEY);
  try {
    if (room === null) window.localStorage.removeItem(KEY);
    else window.localStorage.setItem(KEY, JSON.stringify(room));
  } catch (cause) {
    if (original !== null) {
      try {
        window.localStorage.setItem(KEY, original);
      } catch {
        // 保留现场
      }
    }
    throw new WhisperStorageError('写入 Whisper 房间失败；本次修改已回滚，原数据保留。', { cause });
  }
  notify();
}

function notify(): void {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(EVENT));
}

export function subscribeWhisper(listener: () => void): () => void {
  window.addEventListener(EVENT, listener);
  return () => window.removeEventListener(EVENT, listener);
}

export function createRoom(): WhisperRoom {
  const now = new Date().toISOString();
  const room: WhisperRoom = {
    roomId: uid('room'),
    closed: false,
    createdAt: now,
    updatedAt: now,
    messages: { visitor: [], trainee: [] },
  };
  commit(room);
  return room;
}

export function closeRoom(roomId: string): WhisperRoom | null {
  const room = readRoom();
  if (!room || room.roomId !== roomId) return null;
  const next = { ...room, closed: true, updatedAt: new Date().toISOString() };
  commit(next);
  return next;
}

export function appendWhisperMessage(
  roomId: string,
  seat: WhisperSeat,
  message: Omit<WhisperMessage, 'id' | 'at' | 'seat'>,
): WhisperRoom | null {
  const room = readRoom();
  if (!room || room.roomId !== roomId) return null;
  const entry: WhisperMessage = {
    ...message,
    seat,
    id: uid('wmsg'),
    at: new Date().toISOString(),
  };
  const next = {
    ...room,
    messages: { ...room.messages, [seat]: [...room.messages[seat], entry] },
    updatedAt: new Date().toISOString(),
  };
  commit(next);
  return next;
}

/** 危机关键词引导（对照参考 crisis redirect 的本地形态）：返回引导文案；不命中返回 null */
export function crisisRedirectFor(text: string): string | null {
  const hit = ['自杀', '自残', '不想活', '伤害自己'].some((word) => text.includes(word));
  if (!hit) return null;
  return [
    '【系统引导】你提到的内容让我们很担心。如果你此刻有伤害自己的念头，请立即联系身边可信任的人，或拨打当地心理援助热线（如全国 24 小时心理援助热线 12356）。',
    '在这里可以继续聊聊你的感受，我们陪你把问题梳理清楚。',
  ].join('\n');
}
