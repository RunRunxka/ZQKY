import { describe, expect, it, vi } from 'vitest';
import { createMemoryChatRepository, type ChatRepository } from '@/services/chat-repository';
import type { ChatService, ChatServiceEvent } from './chat-service';
import { createMockChatService } from '../../../../../../tests/fixtures/scripted-chat-service';

import { createScriptedChatStore as createChatStore } from '../../../../../../tests/fixtures/scripted-chat-store';

function gateService() {
  const events: ChatServiceEvent[] = [];
  const emitRef: { emit: (event: ChatServiceEvent) => void } = { emit: () => undefined };
  let finish!: () => void;
  const gate = new Promise<void>((r) => (finish = r));
  const service: ChatService = {
    kind: 'real',
    run: async (request, emit) => {
      const t = { sessionId: request.sessionId, turnId: request.turnId };
      events.push({ ...t, type: 'turn-start' });
      void emit({ ...t, type: 'turn-start' });
      emitRef.emit = emit;
      await gate;
    },
  };
  return { service, events, emitRef, finish: () => finish() };
}

function storeOf(repo: ChatRepository, service: ChatService) {
  return createChatStore({ mode: 'mock', repository: repo, services: { mock: service as never } });
}

describe('S3 结果工作区：artifact 事件消费', () => {
  it('按 id 幂等更新：新 id 追加、同 id 覆盖内容且 createdAt 保留', async () => {
    const repo = createMemoryChatRepository();
    const { service, events, emitRef, finish } = gateService();
    const store = storeOf(repo, service);
    await store.getState().init();
    const run = store.getState().send('出题', null);
    await vi.waitFor(() => expect(events.length).toBeGreaterThan(0));
    const emit = emitRef.emit;
    const t = { sessionId: events[0]!.sessionId, turnId: events[0]!.turnId };
    emit({ ...t, type: 'artifact', artifact: { id: 'a1', kind: 'markdown', title: '结果 A', content: 'v1' } });
    emit({ ...t, type: 'artifact', artifact: { id: 'a2', kind: 'svg', title: '结果 B', content: '<svg/>' } });
    emit({ ...t, type: 'artifact', artifact: { id: 'a1', kind: 'markdown', title: '结果 A', content: 'v2 完成版' } });
    const message = store.getState().messages[1]!;
    expect(message.artifacts).toHaveLength(2);
    expect(message.artifacts?.[0].content).toBe('v2 完成版'); // 同 id 覆盖=增量/完成
    expect(message.artifacts?.[1].content).toBe('<svg/>');
    const createdAt = message.artifacts?.[0].createdAt;
    expect(createdAt).toBeTruthy();
    finish();
    await run;
    store.getState().dispose();
  });

  it('终态后迟到的 artifact 事件被拒绝，不建产物', async () => {
    const repo = createMemoryChatRepository();
    const { service, events, emitRef, finish } = gateService();
    const store = storeOf(repo, service);
    await store.getState().init();
    const run = store.getState().send('出题', null);
    await vi.waitFor(() => expect(events.length).toBeGreaterThan(0));
    const emit = emitRef.emit;
    const t = { sessionId: events[0]!.sessionId, turnId: events[0]!.turnId };
    emit({ ...t, type: 'end', finishReason: 'stop' });
    emit({ ...t, type: 'artifact', artifact: { id: 'late', kind: 'text', title: '迟到产物', content: 'x' } });
    finish();
    await run;
    expect(store.getState().messages[1]!.artifacts).toBeUndefined();
    store.getState().dispose();
  });

  it('产物随会话持久化：刷新恢复记录、不重放执行', async () => {
    const repo = createMemoryChatRepository();
    const { service, events, emitRef, finish } = gateService();
    const store = storeOf(repo, service);
    await store.getState().init();
    const run = store.getState().send('出题', null);
    await vi.waitFor(() => expect(events.length).toBeGreaterThan(0));
    const emit = emitRef.emit;
    const t = { sessionId: events[0]!.sessionId, turnId: events[0]!.turnId };
    emit({ ...t, type: 'artifact', artifact: { id: 'a1', kind: 'markdown', title: '结果 A', content: '正文' } });
    emit({ ...t, type: 'end', finishReason: 'stop' });
    finish();
    await run;
    await store.getState().flush();

    const restored = createChatStore({ mode: 'mock', repository: repo, services: { mock: { kind: 'mock', run: vi.fn(async () => undefined), armFailure: () => undefined, armAskUser: () => undefined, armReplyFailure: () => undefined } } });
    await restored.getState().init();
    expect(restored.getState().messages[1]!.artifacts?.[0]).toMatchObject({
      id: 'a1',
      kind: 'markdown',
      title: '结果 A',
      content: '正文',
    });
    expect(restored.getState().sending).toBe(false); // 恢复不重放
    restored.getState().dispose();
    store.getState().dispose();
  });
});

describe('S4 能力模拟闭环：阶段序列与结构化产物', () => {
  it('deep_question 成功轮：阶段序列完整、quiz 产物按题数增量生成', async () => {
    const store = createChatStore({
      mode: 'mock',
      repository: createMemoryChatRepository(),
      services: { mock: createMockChatService({ chunkDelayMs: 0 }) },
    });
    await store.getState().init();
    await store.getState().send('开始', null, {
      mcps: [],
      skills: [],
      capability: { value: 'deep_question', label: '智能出题', config: { topic: '光合作用' } },
    });
    const message = store.getState().messages[1]!;
    // 阶段序列：exploring→planning→quizzing 全部完成（对照参考 manifest）
    expect(message.stages?.map((s) => s.stageId)).toEqual(['exploring', 'planning', 'quizzing']);
    expect(message.stages?.every((s) => s.status === 'done')).toBe(true);
    // quiz 产物：默认 3 题（config 未给 num_questions）、结构化 data 与 content 同源
    const artifacts = message.artifacts ?? [];
    expect(artifacts).toHaveLength(1);
    expect(artifacts[0]!.kind).toBe('quiz');
    expect(artifacts[0]!.title).toBe('出题结果（模拟）');
    const data = artifacts[0]!.data as { topic: string; questions: { question_id: string }[] };
    expect(data.questions).toHaveLength(3);
    expect(data.topic).toBe('光合作用');
    expect(artifacts[0]!.content).toContain('模拟');
    expect(artifacts[0]!.content).toContain('参考答案');
    store.getState().dispose();
  });

  it('两阶段：能力轮 + 追问确认 → 同轮续答 → 产出产物（S3 组合流，通用管线覆盖）', async () => {
    // 原 deep_research 用例随“更多能力”一并移除；这里用保留的“可视化”能力 +
    // S3 组合流（armAskUser）保住同一条通用管线：同 sessionId/turnId 挂起→回答→继续→产物。
    const service = createMockChatService({ chunkDelayMs: 0 });
    const store = createChatStore({
      mode: 'mock',
      repository: createMemoryChatRepository(),
      services: { mock: service },
    });
    service.armAskUser();
    await store.getState().init();
    const run = store.getState().send('画一张演示图', null, {
      mcps: [],
      skills: [],
      capability: {
        value: 'visualize',
        label: '可视化',
        config: { render_mode: 'chartjs', quality: 'medium', style_hint: '' },
      },
    });
    // 两段式：先挂起追问卡，确认后在同一轮内继续
    await vi.waitFor(() => expect(store.getState().waitingInteractionId).toBeTruthy());
    const ok = await store.getState().submitReply([
      { questionId: 'q-focus', labels: ['侧重示例'], freeText: '' },
    ]);
    expect(ok).toBe(true);
    await run;
    const message = store.getState().messages[1]!;
    // 追问卡之后的正文按既有语义进入最近一张卡的续写（不重复并入 content）
    expect(message.asks?.at(-1)?.followUp ?? '').toContain('已记录产出侧重');
    // 同轮继续后仍按冻结配置产出产物（能力轮未被追问截断）
    expect(message.artifacts?.[0]?.title).toBe('可视化结果（模拟）');
    store.getState().dispose();
  });

  it('visualize auto 路由：mermaid/chartjs 解析与产物 kind 对应', async () => {
    const make = () =>
      createChatStore({
        mode: 'mock',
        repository: createMemoryChatRepository(),
        services: { mock: createMockChatService({ chunkDelayMs: 0 }) },
      });
    const flow = make();
    await flow.getState().init();
    await flow.getState().send('梳理这个流程的关系', null, {
      mcps: [],
      skills: [],
      capability: { value: 'visualize', label: '可视化', config: { render_mode: 'auto' } },
    });
    const flowArtifacts = flow.getState().messages[1]!.artifacts ?? [];
    expect(flowArtifacts[0]!.kind).toBe('mermaid');
    expect(flowArtifacts[0]!.content).toContain('flowchart');
    flow.getState().dispose();

    const chart = make();
    await chart.getState().init();
    await chart.getState().send('给我一张数据占比图表', null, {
      mcps: [],
      skills: [],
      capability: { value: 'visualize', label: '可视化', config: { render_mode: 'auto' } },
    });
    const chartArtifacts = chart.getState().messages[1]!.artifacts ?? [];
    expect(chartArtifacts[0]!.kind).toBe('chart');
    chart.getState().dispose();
  });

  it('visualize 数学动画路由：六阶段 + Manim 代码产物 + 演示媒体如实标识', async () => {
    const store = createChatStore({
      mode: 'mock',
      repository: createMemoryChatRepository(),
      services: { mock: createMockChatService({ chunkDelayMs: 0 }) },
    });
    await store.getState().init();
    await store.getState().send('做一段动画', null, {
      mcps: [],
      skills: [],
      capability: {
        value: 'visualize',
        label: '可视化',
        config: { render_mode: 'manim_video', quality: 'medium', style_hint: '' },
      },
    });
    const message = store.getState().messages[1]!;
    expect(message.stages?.map((s) => s.stageId)).toEqual([
      'concept_analysis',
      'concept_design',
      'code_generation',
      'code_retry',
      'summary',
      'render_output',
    ]);
    const artifacts = message.artifacts ?? [];
    expect(artifacts[0]!.title).toBe('数学动画（模拟）');
    expect(artifacts[0]!.content).toContain('未真实执行');
    expect(artifacts[0]!.content).toContain('不生成真实视频文件');
    store.getState().dispose();
  });

  it('visualize svg 显式模式与阶段（analyzing→generating→reviewing）；普通对话轮无产物', async () => {
    const store = createChatStore({
      mode: 'mock',
      repository: createMemoryChatRepository(),
      services: { mock: createMockChatService({ chunkDelayMs: 0 }) },
    });
    await store.getState().init();
    await store.getState().send('画图', null, {
      mcps: [],
      skills: [],
      capability: { value: 'visualize', label: '可视化', config: { render_mode: 'svg' } },
    });
    const message = store.getState().messages[1]!;
    expect(message.stages?.map((s) => s.stageId)).toEqual([
      'analyzing',
      'generating',
      'reviewing',
    ]);
    const artifacts = message.artifacts ?? [];
    expect(artifacts[0]!.kind).toBe('svg');
    expect(artifacts[0]!.content.startsWith('<svg')).toBe(true);
    store.getState().dispose();

    const plain = createChatStore({
      mode: 'mock',
      repository: createMemoryChatRepository(),
      services: { mock: createMockChatService({ chunkDelayMs: 0 }) },
    });
    await plain.getState().init();
    await plain.getState().send('普通问题', null);
    expect(plain.getState().messages[1]!.artifacts).toBeUndefined();
    plain.getState().dispose();
  });

  it('deep_question 部分失败→重试：阶段收口 cancelled，重试沿用冻结配置成功', async () => {
    const service = createMockChatService({ chunkDelayMs: 0 });
    const store = createChatStore({
      mode: 'mock',
      repository: createMemoryChatRepository(),
      services: { mock: service },
    });
    await store.getState().init();
    const snapshot = {
      mcps: [],
      skills: [],
      capability: { value: 'deep_question', label: '智能出题', config: { topic: '电磁感应' } },
    };
    service.armFailure();
    await store.getState().send('出题', null, structuredClone(snapshot));
    const failed = store.getState().messages[1]!;
    expect(failed.status).toBe('error');
    expect(failed.error?.code).toBe('MOCK_CAPABILITY_ERROR');
    // 失败发生在阶段中：运行中的阶段收口为 cancelled，不产生产物
    expect(failed.stages?.every((s) => s.status !== 'running')).toBe(true);
    expect(failed.artifacts).toBeUndefined();

    // 重试：沿用原快照（不读取最新表单），失败占位移除后新消息生成成功（R12）
    await store.getState().retry(failed.id, null);
    const retried = store.getState().messages[1]!;
    expect(retried.status).toBe('done');
    expect(retried.error).toBeUndefined();
    expect(retried.artifacts?.[0]?.kind).toBe('quiz');
    const data = retried.artifacts?.[0]?.data as { topic: string };
    expect(data.topic).toBe('电磁感应'); // 冻结快照复现
    store.getState().dispose();
  });

  it('ask_questions 能力：发送后进入同轮追问等待，不直接给终稿', async () => {
    const store = createChatStore({
      mode: 'mock',
      repository: createMemoryChatRepository(),
      services: { mock: createMockChatService({ chunkDelayMs: 0 }) },
    });
    await store.getState().init();
    const run = store.getState().send('讲讲这个主题', null, {
      mcps: [],
      skills: [],
      capability: { value: 'ask_questions', label: '追问澄清' },
    });
    run.catch(() => undefined);
    // 第一卡：讲解方式 + 内容偏好（同卡两题）
    await vi.waitFor(() => expect(store.getState().waitingInteractionId).toBeTruthy());
    expect(
      await store.getState().submitReply([
        { questionId: 'q-style', labels: ['按知识点讲解'], freeText: '' },
        { questionId: 'q-materials', labels: ['结合课标'], freeText: '' },
      ]),
    ).toBe(true);
    // 第二卡：收尾方式（同轮第二张追问卡）
    await vi.waitFor(() => expect(store.getState().waitingInteractionId).toBeTruthy());
    expect(
      await store.getState().submitReply([
        { questionId: 'q-summary', labels: ['需要小结'], freeText: '' },
      ]),
    ).toBe(true);
    await run;
    const message = store.getState().messages[1]!;
    expect(message.asks).toHaveLength(2);
    // 首卡之后的正文增量路由到最近一张卡的 followUp（同轮顺序正确）
    expect(message.asks![1]!.followUp).toContain('本轮续答完成');
    store.getState().dispose();
  });
});
