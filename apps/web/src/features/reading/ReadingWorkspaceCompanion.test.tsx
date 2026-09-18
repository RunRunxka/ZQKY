import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';

/**
 * READ-RETRY / READ-END 有界补测（B-R05-READ-BOUNDED v1）：
 * 用可控伴生服务替身驱动 CompanionPane 的事件流，验证：
 * - READ-RETRY：错误态"重试"按钮实际可发起新轮（未修复代码上首败）；
 * - READ-END：重复/迟到 end 的落库幂等与旧轮收尾不夺新轮取消能力。
 * 替身经 vi.mock 注入模块工厂，不向生产代码加测试接口。
 */

interface EmitInput {
  sessionId: string;
  turnId: string;
  userText: string;
  signal: AbortSignal;
}

type Emit = (event: Record<string, unknown>) => void;

interface RunCall {
  input: EmitInput;
  emit: Emit;
  /** 手动结束 run() promise 的方式；不调用则挂起 */
  resolve: () => void;
}

const runCalls: RunCall[] = [];

vi.mock('@/features/reading/companion-service', () => {
  return {
    createReadingCompanionService: () => ({
      kind: 'stub',
      armFailure: () => {},
      run(_input: EmitInput, emit: Emit) {
        return new Promise<void>((resolve, reject) => {
          runCalls.push({
            input: _input,
            emit: emit as Emit,
            resolve,
          });
          // 与真实服务一致：abort 使 run 以 AbortError 拒绝（组件 catch 走取消收尾）
          _input.signal.addEventListener(
            'abort',
            () => reject(new DOMException('aborted', 'AbortError')),
            { once: true },
          );
        });
      },
    }),
  };
});

/** useParams 需要真实存在的集合 id；由 setup() 建集合后回填 */
const routeState = vi.hoisted(() => ({ workspaceId: '' }));

vi.mock('next/navigation', () => ({
  useParams: () => ({ workspaceId: routeState.workspaceId }),
  useRouter: () => ({ push: vi.fn(), replace: vi.fn() }),
}));

vi.mock('@/services/reading-store', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/services/reading-store')>();
  return { ...actual };
});

import { ReadingWorkspaceView } from './ReadingWorkspace';
import { createWorkspace, getSession } from '@/services/reading-store';
import type { ChatServiceEvent } from '@/features/chat/model/chat-service';

function emitTyped(emit: Emit, event: ChatServiceEvent) {
  emit(event as unknown as Record<string, unknown>);
}

/** 桌面宽度（CompanionPane 仅 ≥1280px 渲染）——普通工具函数，避免 react-hooks 命名误判 */
function stubDesktopMedia() {
  vi.stubGlobal(
    'matchMedia',
    vi.fn().mockImplementation((query: string) => ({
      matches: query.includes('1280'),
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
    })),
  );
}

async function setup() {
  stubDesktopMedia();
  window.localStorage.clear();
  runCalls.length = 0;
  const workspace = createWorkspace('补测集合');
  routeState.workspaceId = workspace.id;
  const { container } = render(<ReadingWorkspaceView />);
  await waitFor(() => expect(screen.getByLabelText('向伴生助手提问')).toBeTruthy());
  return { workspace, container };
}

async function sendQuestion(text: string) {
  const input = screen.getByLabelText('向伴生助手提问') as HTMLTextAreaElement;
  fireEvent.change(input, { target: { value: text } });
  fireEvent.click(screen.getByLabelText('发送提问'));
  await waitFor(() => expect(runCalls.length).toBe(1));
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
  window.localStorage.clear();
});

describe('READ-RETRY：错误态重试', () => {
  it('错误态点击重试发起第二轮回合（未修复代码上首败）', async () => {
    await setup();
    await sendQuestion('讲讲这一段');
    expect(runCalls.length).toBe(1);
    const first = runCalls[0]!;
    emitTyped(first.emit, { type: 'turn-start', sessionId: first.input.sessionId, turnId: first.input.turnId });
    emitTyped(first.emit, {
      type: 'error',
      sessionId: first.input.sessionId,
      turnId: first.input.turnId,
      error: { code: 'MOCK', message: '已按要求模拟一次伴生回复失败，可直接重试。', retryable: true },
    });
    // 错误横幅与重试按钮出现
    const retry = await screen.findByLabelText('重试伴生回复');
    expect(retry).toBeTruthy();
    fireEvent.click(retry);
    // 期望：发起第二轮（run 第二次调用）；修复前 turn 非空守卫挡住，仍是 1 次 → 首败
    await waitFor(() => expect(runCalls.length).toBe(2));
    const second = runCalls[1]!;
    expect(second.input.userText).toBe('讲讲这一段');
    expect(second.input.turnId).not.toBe(first.input.turnId);
    // 新轮开始后错误清空
    await waitFor(() => expect(screen.queryByLabelText('重试伴生回复')).toBeNull());
  });
});

describe('READ-END：终态幂等与旧轮收尾', () => {
  it('a) 同一 turnId 重复 end 只落库一次', async () => {
    await setup();
    await sendQuestion('总结');
    const call = runCalls[0]!;
    emitTyped(call.emit, { type: 'turn-start', sessionId: call.input.sessionId, turnId: call.input.turnId });
    emitTyped(call.emit, { type: 'text', sessionId: call.input.sessionId, turnId: call.input.turnId, delta: '内容甲' });
    emitTyped(call.emit, { type: 'end', sessionId: call.input.sessionId, turnId: call.input.turnId, finishReason: 'stop' });
    emitTyped(call.emit, { type: 'end', sessionId: call.input.sessionId, turnId: call.input.turnId, finishReason: 'stop' });
    call.resolve();
    await waitFor(() => {
      const session = getSession(call.input.sessionId);
      expect(session?.messages.filter((m) => m.role === 'assistant')).toHaveLength(1);
    });
  });

  it('b) 已取消收尾后迟到的 end 不重复落库', async () => {
    await setup();
    await sendQuestion('慢慢回答');
    const call = runCalls[0]!;
    emitTyped(call.emit, { type: 'turn-start', sessionId: call.input.sessionId, turnId: call.input.turnId });
    emitTyped(call.emit, { type: 'text', sessionId: call.input.sessionId, turnId: call.input.turnId, delta: '部分内容' });
    // 取消：abort 触发 catch → finalizeTurn(…, cancelled=true) 落"部分内容（已取消）"
    call.input.signal.dispatchEvent(new Event('abort'));
    await waitFor(() => {
      const session = getSession(call.input.sessionId);
      expect(session?.messages.some((m) => m.role === 'assistant' && m.content.includes('（已取消）'))).toBe(true);
    });
    const cancelledCount = getSession(call.input.sessionId)!.messages.filter(
      (m) => m.role === 'assistant' && m.content.includes('（已取消）'),
    ).length;
    // 迟到的 end 到达（服务在取消后仍 emit end）
    emitTyped(call.emit, { type: 'end', sessionId: call.input.sessionId, turnId: call.input.turnId, finishReason: 'stop' });
    const after = getSession(call.input.sessionId)!.messages.filter((m) => m.role === 'assistant');
    expect(after.filter((m) => m.content.includes('部分内容'))).toHaveLength(cancelledCount);
    // 迟到 end 不得复活轮次块
    expect(screen.queryByTestId('companion-turn')).toBeNull();
  });

  it('c) 新轮已开始后旧轮 end 不清新轮、不夺取消能力，内容归旧会话', async () => {
    await setup();
    await sendQuestion('第一问');
    const old = runCalls[0]!;
    emitTyped(old.emit, { type: 'turn-start', sessionId: old.input.sessionId, turnId: old.input.turnId });
    emitTyped(old.emit, { type: 'text', sessionId: old.input.sessionId, turnId: old.input.turnId, delta: '旧内容' });
    // 旧轮挂起时直接点"停止"→ abort → catch 收尾旧轮（旧内容落库、轮次块清理）
    fireEvent.click(screen.getByLabelText('停止生成'));
    await waitFor(() => {
      const session = getSession(old.input.sessionId);
      expect(session?.messages.some((m) => m.role === 'assistant' && m.content.includes('旧内容'))).toBe(true);
    });
    expect(screen.queryByTestId('companion-turn')).toBeNull();
    // 同一会话再发第二问，形成"旧轮 run 未 resolve、新轮已开始"的格局
    const input = screen.getByLabelText('向伴生助手提问') as HTMLTextAreaElement;
    fireEvent.change(input, { target: { value: '第二问' } });
    fireEvent.click(screen.getByLabelText('发送提问'));
    await waitFor(() => expect(runCalls.length).toBe(2));
    const fresh = runCalls[1]!;
    expect(fresh.input.turnId).not.toBe(old.input.turnId);
    // 旧轮迟到的 end：turnId 守卫保证不动新轮块；旧轮内容只落一次
    emitTyped(old.emit, { type: 'end', sessionId: old.input.sessionId, turnId: old.input.turnId, finishReason: 'stop' });
    const msgs = getSession(old.input.sessionId)!.messages.filter((m) => m.role === 'assistant' && m.content.includes('旧内容'));
    expect(msgs).toHaveLength(1);
    // 新轮仍在进行
    expect(screen.getByTestId('companion-turn')).toBeTruthy();
    fresh.resolve();
  });

  it('d) error 后 lastSend 保留：修复后重试以同文本开新轮', async () => {
    await setup();
    await sendQuestion('再来一次');
    const call = runCalls[0]!;
    emitTyped(call.emit, { type: 'turn-start', sessionId: call.input.sessionId, turnId: call.input.turnId });
    emitTyped(call.emit, {
      type: 'error',
      sessionId: call.input.sessionId,
      turnId: call.input.turnId,
      error: { code: 'MOCK', message: '模拟失败', retryable: true },
    });
    call.resolve();
    const retry = await screen.findByLabelText('重试伴生回复');
    fireEvent.click(retry);
    await waitFor(() => expect(runCalls.length).toBe(2));
    expect(runCalls[1]!.input.userText).toBe('再来一次');
  });
});
