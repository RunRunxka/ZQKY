import { describe, expect, it, vi } from 'vitest';
import { createMemoryChatRepository } from '@/services/chat-repository';
import { conversationProjection } from './context-budget';
import type { AskUserInteraction } from '@/contracts/chat';
import type { ChatService, ChatServiceEvent, ChatServiceRequest } from './chat-service';
import { createChatStore } from './store';

const selection = {
  gradeId: 'g1',
  subjectId: 's1',
  editionId: 'e1',
  documentIds: ['d1'],
};
const extensions = { mcps: [], skills: [], capability: { value: 'rag', label: 'RAG 模式' } };

function card(): AskUserInteraction {
  return {
    interactionId: 'i1',
    status: 'waiting',
    questions: [
      {
        questionId: 'q1',
        prompt: '定位是否符合题意？',
        options: [{ label: '细讲解题思路' }, { label: '重新核对知识点' }],
        multiSelect: false,
        allowFreeText: true,
      },
      {
        questionId: 'q2',
        prompt: '还需要补充什么？',
        options: [{ label: '补充条件' }],
        multiSelect: false,
        allowFreeText: false,
      },
    ],
    drafts: {},
  };
}

/** 可脚本化的教材服务：run 停在上一步等待，submitReply 由用例控制 */
function scripted() {
  let emitRef: ((event: ChatServiceEvent) => void) | null = null;
  let requestRef: ChatServiceRequest | null = null;
  const submitted: { submissionId: string; answers: unknown }[] = [];
  let mode: 'ok' | 'network-error' | 'pending' = 'ok';
  const service: ChatService = {
    kind: 'real',
    run: (request, emit) => {
      requestRef = request;
      emitRef = emit;
      emit({ sessionId: request.sessionId, turnId: request.turnId, type: 'turn-start', eventId: 1 });
      emit({
        sessionId: request.sessionId,
        turnId: request.turnId,
        type: 'wait-user',
        interaction: card(),
        eventId: 2,
      });
      return new Promise<void>((resolve) => request.signal.addEventListener('abort', () => resolve(), { once: true }));
    },
    submitReply: async (reply) => {
      submitted.push({ submissionId: reply.submissionId, answers: reply.answers });
      if (mode === 'network-error') throw new Error('连接中断');
      if (mode === 'pending') return new Promise(() => undefined);
      return { accepted: true };
    },
  };
  return {
    service,
    submitted,
    setMode: (next: typeof mode) => {
      mode = next;
    },
    accepted() {
      const turn = requestRef!;
      emitRef!({
        sessionId: turn.sessionId,
        turnId: turn.turnId,
        type: 'reply-accepted',
        interactionId: 'i1',
        submissionId: submitted.at(-1)!.submissionId,
        answers: submitted.at(-1)!.answers as never,
        eventId: 3,
      });
    },
  };
}

async function waitingStore(h = scripted()) {
  const store = createChatStore({ repository: createMemoryChatRepository(), service: h.service });
  store.getState().setRagScopeSelection(selection);
  await store.getState().init();
  const running = store.getState().send('原题', null, extensions);
  await vi.waitFor(() => expect(store.getState().waitingInteractionId).toBe('i1'));
  return { store, running, ...h };
}

describe('追问卡 v2 状态机（store）', () => {
  it('单选不自动跳题；「继续」逐题推进，最后一题才提交，确认后才写已答', async () => {
    const { store, submitted, accepted } = await waitingStore();
    store.getState().setAskFocus('i1', 'q1');
    // 选中选项只写草稿，不改变聚焦题、不提交
    store.getState().setAskDraft('i1', 'q1', {
      labels: ['细讲解题思路'],
      freeText: '',
      disposition: 'unanswered',
    });
    expect(store.getState().askFocus).toMatchObject({ interactionId: 'i1', questionId: 'q1' });
    expect(submitted).toHaveLength(0);
    // 继续：确认当前题并前进到下一题（未提交）
    expect(await store.getState().continueAsk('i1')).toBe(false);
    expect(submitted).toHaveLength(0);
    expect(store.getState().askFocus).toMatchObject({ questionId: 'q2' });
    expect(store.getState().messages[1]!.asks![0]!.drafts.q1?.disposition).toBe('answered');
    // 最后一题作答后继续：真正提交
    store.getState().setAskDraft('i1', 'q2', {
      labels: ['补充条件'],
      freeText: '',
      disposition: 'unanswered',
    });
    store.getState().setAskFocus('i1', 'q2');
    expect(await store.getState().continueAsk('i1')).toBe(true);
    expect(submitted).toHaveLength(1);
    expect(submitted[0]!.answers).toEqual([
      { questionId: 'q1', labels: ['细讲解题思路'], freeText: '' },
      { questionId: 'q2', labels: ['补充条件'], freeText: '' },
    ]);
    // reply.accepted 到达后才确认已答（此前不假装成功）
    accepted();
    await vi.waitFor(() =>
      expect(store.getState().messages[1]!.asks![0]!.status).toBe('answered'),
    );
    expect(store.getState().waitingInteractionId).toBeNull();
    store.getState().dispose();
  });

  it('未确认的题存在时跳回该题并提示「还有问题尚未确认」，不提交', async () => {
    const { store, submitted } = await waitingStore();
    // 先答最后一题，第一题仍未确认
    store.getState().setAskDraft('i1', 'q2', {
      labels: ['补充条件'],
      freeText: '',
      disposition: 'unanswered',
    });
    store.getState().setAskFocus('i1', 'q2');
    expect(await store.getState().continueAsk('i1')).toBe(false);
    expect(submitted).toHaveLength(0);
    expect(store.getState().askFocus).toMatchObject({ questionId: 'q1' });
    expect(store.getState().askNotice).toMatchObject({
      interactionId: 'i1',
      questionId: 'q1',
      text: '还有问题尚未确认',
    });
    store.getState().dismissAskNotice();
    expect(store.getState().askNotice).toBeNull();
    store.getState().dispose();
  });

  it('「忽略」只把当前题标记 skipped 后前进；最后一题忽略才按同一语义提交', async () => {
    const { store, submitted } = await waitingStore();
    expect(await store.getState().skipAskQuestion('i1')).toBe(false);
    expect(submitted).toHaveLength(0);
    const first = store.getState().messages[1]!.asks![0]!;
    expect(first.drafts.q1).toMatchObject({ labels: [], freeText: '', disposition: 'skipped' });
    expect(store.getState().askFocus).toMatchObject({ questionId: 'q2' });
    expect(await store.getState().skipAskQuestion('i1')).toBe(true);
    expect(submitted).toHaveLength(1);
    expect(submitted[0]!.answers).toEqual([
      { questionId: 'q1', labels: [], freeText: '', skipped: true },
      { questionId: 'q2', labels: [], freeText: '', skipped: true },
    ]);
    store.getState().dispose();
  });

  it('提交结果未确认时锁定编辑：忽略被拒，继续只做同幂等键同载荷重试', async () => {
    const harness = scripted();
    const { store, submitted } = await waitingStore(harness);
    store.getState().setAskDraft('i1', 'q1', {
      labels: [],
      freeText: 'x>0',
      disposition: 'unanswered',
    });
    store.getState().setAskFocus('i1', 'q1');
    expect(await store.getState().continueAsk('i1')).toBe(false); // 前进到 q2
    store.getState().setAskFocus('i1', 'q2');
    store.getState().setAskDraft('i1', 'q2', { labels: ['补充条件'], freeText: '', disposition: 'unanswered' });
    harness.setMode('network-error');
    expect(await store.getState().continueAsk('i1')).toBe(false);
    expect(submitted).toHaveLength(1);
    const card = store.getState().messages[1]!.asks![0]!;
    expect(card.pendingSubmission).toBeTruthy();
    expect(card.status).toBe('failed');
    // 锁定：忽略被拒；改答不同内容不会被消费（continue 走精确重试）
    expect(await store.getState().skipAskQuestion('i1')).toBe(false);
    harness.setMode('ok');
    expect(await store.getState().continueAsk('i1')).toBe(true);
    expect(submitted).toHaveLength(2);
    expect(submitted[1]!.submissionId).toBe(submitted[0]!.submissionId);
    expect(submitted[1]!.answers).toEqual(submitted[0]!.answers);
    store.getState().dispose();
  });

  it('主输入框补充回答：填当前题并确认，不自动跳过其余题；投影包含已确认交流', async () => {
    const { store, submitted, accepted } = await waitingStore();
    expect(await store.getState().submitComposerReply('定义域 x>0')).toBe(false);
    expect(submitted).toHaveLength(0);
    const card = store.getState().messages[1]!.asks![0]!;
    expect(card.drafts.q1).toMatchObject({ labels: [], freeText: '定义域 x>0', disposition: 'answered' });
    expect(store.getState().askFocus).toMatchObject({ questionId: 'q2' });
    store.getState().setAskDraft('i1', 'q2', { labels: ['补充条件'], freeText: '', disposition: 'unanswered' });
    store.getState().setAskFocus('i1', 'q2');
    expect(await store.getState().continueAsk('i1')).toBe(true);
    accepted();
    await vi.waitFor(() => expect(store.getState().messages[1]!.asks![0]!.status).toBe('answered'));
    expect(conversationProjection(store.getState().messages[1]!)).toContain('定义域 x>0');
    store.getState().dispose();
  });
});
