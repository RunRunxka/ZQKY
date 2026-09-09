import { beforeEach, describe, expect, it } from 'vitest';
import {
  appendWhisperMessage,
  closeRoom,
  crisisRedirectFor,
  createRoom,
  readRoom,
} from './whisper-store';

beforeEach(() => window.localStorage.clear());

describe('whisper-store（S5-E，双席位密室）', () => {
  it('房间创建/消息分席保存/结束房间', () => {
    const room = createRoom();
    appendWhisperMessage(room.roomId, 'visitor', { role: 'user', content: '访客的问题' });
    appendWhisperMessage(room.roomId, 'trainee', { role: 'user', content: '学员的问题' });
    const stored = readRoom()!;
    expect(stored.messages.visitor).toHaveLength(1);
    expect(stored.messages.trainee).toHaveLength(1);
    expect(stored.messages.visitor[0]!.seat).toBe('visitor');
    const closed = closeRoom(room.roomId)!;
    expect(closed.closed).toBe(true);
  });

  it('危机表述触发系统引导卡（含援助热线），普通表述不触发', () => {
    expect(crisisRedirectFor('我最近不想活了')).toContain('12356');
    expect(crisisRedirectFor('这道题不会做')).toBeNull();
    const room = createRoom();
    const redirect = crisisRedirectFor('伤害自己');
    appendWhisperMessage(room.roomId, 'trainee', { role: 'system', content: redirect! });
    expect(readRoom()!.messages.trainee[0]!.role).toBe('system');
  });

  it('错误 roomId 拒绝写入', () => {
    createRoom();
    expect(appendWhisperMessage('ghost', 'visitor', { role: 'user', content: 'x' })).toBeNull();
    expect(closeRoom('ghost')).toBeNull();
  });
});
