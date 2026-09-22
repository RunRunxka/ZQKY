import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { createMemoryChatRepository, type ChatRepository } from '@/services/chat-repository';
import {
  createCourse,
  loadDemoCourses,
  readCourses,
  updateCourse,
} from '@/services/courses-store';
import type { ChatServiceEvent, ChatServiceRequest } from './chat-service';
import { createScriptedChatStore as createChatStore } from '../../../../../../tests/fixtures/scripted-chat-store';

/**
 * H1-COURSE-SESSIONS v1：课程上下文进入**真实请求链路**的轮次契约（store 层）。
 *
 * 断言的是"发给服务层的请求 messages"——真实服务把 `messages` 原样 POST 到
 * `/api/v1/chat/stream`（`chat-service.ts` → `chat-stream.ts`），后端逐条转 `LLMMessage`
 * 交给供应商适配器（`apps/api/app/api/v1/chat.py`），因此这里断言 system 消息即断言真实链路内容。
 */

type Emit = (event: ChatServiceEvent) => void;
type ScriptedRun = (emit: Emit, request: ChatServiceRequest) => Promise<void>;

function turn(request: ChatServiceRequest) {
  return { sessionId: request.sessionId, turnId: request.turnId };
}

function scriptedService(script: ScriptedRun[]) {
  const requests: ChatServiceRequest[] = [];
  const service = {
    kind: 'mock' as const,
    armFailure: () => undefined,
    armAskUser: () => undefined,
    armReplyFailure: () => undefined,
    run: (request: ChatServiceRequest, emit: Emit) => {
      requests.push(request);
      return script[requests.length - 1]!(emit, request);
    },
  };
  return { service, requests };
}

function mockStore(repo: ChatRepository, script: ScriptedRun[]) {
  const { service, requests } = scriptedService(script);
  const store = createChatStore({ mode: 'mock', repository: repo, services: { mock: service } });
  return { store, requests };
}

const okTurn: ScriptedRun = async (emit, request) => {
  emit({ ...turn(request), type: 'end', finishReason: 'stop' });
};

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  loadDemoCourses();
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe('课程上下文随轮次冻结并进入请求', () => {
  it('课程会话发送：请求最前是一条 system 课程上下文（含课程名与约定），且快照随本轮持久化', async () => {
    updateCourse('demo-course-math', { instructions: '每次课前先复习上一单元错题。' });
    const { store, requests } = mockStore(createMemoryChatRepository(), [okTurn, okTurn]);
    await store.getState().init();
    store.getState().newConversation({ courseId: 'demo-course-math' });
    await store.getState().send('什么是分数？', null);

    const request = requests[0]!;
    expect(request.messages[0]!.role).toBe('system');
    expect(request.messages[0]!.content).toContain('课程名称：七年级数学（演示课程）');
    expect(request.messages[0]!.content).toContain('每次课前先复习上一单元错题。');
    expect(request.messages[0]!.content).toMatch(/未解析|未检索/);
    // 用户消息紧随其后（课程块不吞掉用户轮次）
    expect(request.messages[1]).toMatchObject({ role: 'user', content: '什么是分数？' });

    // 快照随本轮冻结并持久化（重试沿用）
    const assistant = store.getState().messages.at(-1)!;
    expect(assistant.courseContext?.courseId).toBe('demo-course-math');
    expect(assistant.courseContext?.name).toBe('七年级数学（演示课程）');
    expect(store.getState().activeCourseId).toBe('demo-course-math');
  });

  it('课程修改后：新轮用新快照；旧轮重试仍用冻结时的旧快照', async () => {
    updateCourse('demo-course-math', { instructions: '旧约定：先复习错题。' });
    const { store, requests } = mockStore(createMemoryChatRepository(), [
      // 第 1 轮失败（可重试）
      async (emit, request) => {
        emit({ ...turn(request), type: 'error', error: { code: 'UPSTREAM', message: '上游失败' } });
      },
      okTurn, // 旧轮重试
      okTurn, // 新轮
    ]);
    await store.getState().init();
    store.getState().newConversation({ courseId: 'demo-course-math' });
    await store.getState().send('第一轮问题', null);
    const firstAssistantId = store.getState().messages.at(-1)!.id;

    // 课程改名 + 改约定（模拟"课程修改"）
    updateCourse('demo-course-math', { name: '七年级数学（改名后）', instructions: '新约定：先做小测。' });

    // 旧轮重试：必须沿用旧快照（不读最新课程）
    await store.getState().retry(firstAssistantId, null);
    expect(requests[1]!.messages[0]!.content).toContain('七年级数学（演示课程）');
    expect(requests[1]!.messages[0]!.content).toContain('旧约定：先复习错题。');
    expect(requests[1]!.messages[0]!.content).not.toContain('改名后');

    // 新轮：用新快照
    store.getState().newConversation({ courseId: 'demo-course-math' });
    await store.getState().send('第二轮问题', null);
    expect(requests[2]!.messages[0]!.content).toContain('七年级数学（改名后）');
    expect(requests[2]!.messages[0]!.content).toContain('新约定：先做小测。');
  });

  it('未归属会话：不发课程上下文、不产生提示', async () => {
    const { store, requests } = mockStore(createMemoryChatRepository(), [okTurn]);
    await store.getState().init();
    store.getState().newConversation(); // 普通会话（无课程）
    await store.getState().send('普通问题', null);

    expect(requests[0]!.messages.every((message) => message.role !== 'system')).toBe(true);
    expect(store.getState().activeCourseId).toBeNull();
    expect(store.getState().courseContextWarning).toBeNull();
    expect(store.getState().messages.at(-1)!.courseContext).toBeUndefined();
  });

  it('课程已删除：会话与消息保留、归属不被改写；本轮不注入上下文并如实提示', async () => {
    const course = createCourse('临时课程', '');
    const { store, requests } = mockStore(createMemoryChatRepository(), [okTurn]);
    await store.getState().init();
    store.getState().newConversation({ courseId: course.id });
    // 删除课程（本批契约：不级联删除会话、不清空归属）
    window.localStorage.setItem(
      'zhiqikeyuan:courses',
      JSON.stringify(readCourses().filter((item) => item.id !== course.id)),
    );
    await store.getState().send('课程没了还问', null);

    expect(requests[0]!.messages.every((message) => message.role !== 'system')).toBe(true);
    expect(store.getState().courseContextWarning).toContain('所属课程已删除或不可用');
    // 归属保留（可追溯），历史消息保留
    expect(store.getState().activeCourseId).toBe(course.id);
    expect(store.getState().messages.some((message) => message.role === 'user')).toBe(true);

    // 提示可关闭，且不改变任何数据
    store.getState().dismissCourseContextWarning();
    expect(store.getState().courseContextWarning).toBeNull();
    expect(store.getState().activeCourseId).toBe(course.id);
  });

  it('课程目录读取失败：不注入上下文、按普通问答发送并如实提示（不回落其他课程）', async () => {
    const { store, requests } = mockStore(createMemoryChatRepository(), [okTurn]);
    await store.getState().init();
    store.getState().newConversation({ courseId: 'demo-course-math' });

    const original = Storage.prototype.getItem;
    const spy = vi
      .spyOn(Storage.prototype, 'getItem')
      .mockImplementation(function (this: Storage, name: string) {
        if (name === 'zhiqikeyuan:courses') throw new Error('denied');
        return original.call(this, name);
      });
    await store.getState().send('目录坏了', null);
    spy.mockRestore();

    expect(requests[0]!.messages.every((message) => message.role !== 'system')).toBe(true);
    expect(store.getState().courseContextWarning).toContain('课程目录读取失败');
    expect(store.getState().activeCourseId).toBe('demo-course-math');
  });
});
