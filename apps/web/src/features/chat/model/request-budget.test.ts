import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ChatMessage, TurnCourseSnapshot } from '@/contracts/chat';
import { createMemoryChatRepository } from '@/services/chat-repository';
import { buildCourseSnapshot, courseContextMessage } from '@/services/course-session';
import {
  createCourse,
  loadDemoCourses,
  readCourses,
  setCourseSyllabus,
  parseSyllabusText,
  updateCourse,
} from '@/services/courses-store';
import type { ChatService, ChatServiceEvent, ChatServiceRequest } from './chat-service';
import { createChatStore, type ChatProfileSelection } from './store';
import {
  BACKEND_REQUEST_LIMITS,
  COURSE_CONTEXT_DISCLAIMER,
  buildChatRequest,
  renderCourseContextBlock,
} from './request-budget';

/**
 * CHAT-CONTEXT-BUDGET v1：请求构建（课程块 + 历史 + 当前问题同一预算）。
 *
 * 断言的是**构建器产物与 state 事实**——账目（requestBudget）必须与实际发送的消息逐字段一致，
 * 失败路径必须无副作用（不占位、不清草稿、不置 sending、不留未处理 Promise）。
 * 浏览器报文级证据见 tests/e2e/chat-context-budget.spec.ts。
 */

/** 预算 2000 字符：contextBudgetChars(4000, 2000) = max(2000, 8000 - 6000) = 2000 */
const PROFILE: ChatProfileSelection = {
  id: 'budget-profile',
  modelLabel: '预算测试模型',
  contextTokens: 4000,
  maxOutputTokens: 2000,
};
const BUDGET = 2000;
/** 预算 80000 字符（受后端总上限 120000 约束仍有余量） */
const BIG_PROFILE: ChatProfileSelection = {
  id: 'big-profile',
  modelLabel: '大预算模型',
  contextTokens: 40000,
  maxOutputTokens: 0,
};

function message(
  role: ChatMessage['role'],
  content: string,
  status: ChatMessage['status'] = 'done',
): ChatMessage {
  return { id: `m-${Math.random().toString(36).slice(2)}`, role, content, status };
}

function snapshot(overrides: Partial<TurnCourseSnapshot> = {}): TurnCourseSnapshot {
  return {
    courseId: 'c1',
    name: '七年级数学',
    conventions: '每次课前先复习上一单元错题。',
    syllabus: { total: 3, covered: 1, nextTitle: '分数的意义' },
    resources: [
      { kind: 'knowledge_base', label: '分数知识库', availability: 'available' },
      { kind: 'notebook', label: '错题本', availability: 'unknown' },
    ],
    frozenAt: '2026-09-22T00:00:00.000Z',
    ...overrides,
  };
}

/** 注入式服务：记录每次请求，按脚本给 end/error（不发真实网络请求） */
function scriptedService(script: Array<'ok' | 'error'>): {
  service: ChatService;
  requests: ChatServiceRequest[];
} {
  const requests: ChatServiceRequest[] = [];
  const service: ChatService = {
    kind: 'real',
    async run(request, emit: (event: ChatServiceEvent) => void) {
      requests.push(request);
      const outcome = script[requests.length - 1] ?? 'ok';
      if (outcome === 'error') {
        emit({
          sessionId: request.sessionId,
          turnId: request.turnId,
          type: 'error',
          error: { code: 'UPSTREAM_ERROR', message: '上游失败（测试脚本）' },
        });
        return;
      }
      emit({ sessionId: request.sessionId, turnId: request.turnId, type: 'end', finishReason: 'stop' });
    },
  };
  return { service, requests };
}

function buildScriptedStore(script: Array<'ok' | 'error'> = ['ok', 'ok', 'ok', 'ok']) {
  const { service, requests } = scriptedService(script);
  const store = createChatStore({ repository: createMemoryChatRepository(), service });
  return { store, requests };
}

const totalChars = (built: Extract<ReturnType<typeof buildChatRequest>, { ok: true }>) =>
  built.messages.reduce((total, item) => total + item.content.length, 0);

beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  loadDemoCourses();
});

describe('buildChatRequest：预算与裁剪顺序', () => {
  it('§4：中文/Unicode 长课程名与超长大纲标题按上限渲染，且不改写快照/课程原始数据', () => {
    const huge: TurnCourseSnapshot = snapshot({
      name: '课'.repeat(200),
      conventions: '约定'.repeat(1000), // 2000 字符
      syllabus: { total: 3, covered: 1, nextTitle: '单'.repeat(32001) },
      resources: Array.from({ length: 40 }, (_, index) => ({
        kind: 'book',
        label: `资料${index}`.repeat(40),
        availability: 'unknown' as const,
      })),
    });
    const frozen = structuredClone(huge);
    const built = buildChatRequest({
      history: [message('user', '上一轮问题')],
      question: '这题怎么理解？',
      courseSnapshot: huge,
      contextTokens: BIG_PROFILE.contextTokens,
      maxOutputTokens: BIG_PROFILE.maxOutputTokens,
    });
    expect(built.ok).toBe(true);
    if (!built.ok) return;
    const block = built.messages[0]!;
    expect(block.role).toBe('system');
    // 整体 ≤ 2400 且 ≤ maxMessageChars - 1
    expect(block.content.length).toBeLessThanOrEqual(2400);
    expect(block.content.length).toBeLessThanOrEqual(BACKEND_REQUEST_LIMITS.maxMessageChars - 1);
    const lines = block.content.split('\n');
    const nameLine = lines.find((line) => line.startsWith('课程名称：'))!;
    expect(nameLine.length - '课程名称：'.length).toBe(80); // 79 + 省略号
    const syllabusLine = lines.find((line) => line.includes('下一个未完成单元：'))!;
    expect(syllabusLine.length - (syllabusLine.indexOf('单元：') + '单元：'.length)).toBe(120);
    const conventions = block.content.split('<<<\n')[1]!.split('\n>>>')[0]!;
    expect(conventions.length).toBeLessThanOrEqual(1200);
    // 免责句在受限渲染后依然存在
    expect(block.content).toContain(COURSE_CONTEXT_DISCLAIMER);
    // 被裁剪的动态字段如实列出（name/conventions/syllabus/resourceLabels/resourceItems）
    expect([...built.record.courseTrimmedFields].sort()).toEqual([
      'conventions',
      'name',
      'resourceItems',
      'resourceLabels',
      'syllabus',
    ]);
    expect(built.notes).toContainEqual({
      kind: 'course-trimmed',
      fields: built.record.courseTrimmedFields,
    });
    // 入参未被改写（不得回写课程原始数据或历史正文）
    expect(huge).toEqual(frozen);
  });

  it('§6.2：超过 32000 字的旧快照经同一构建器安全构建（预算够则受限渲染，不够则整体丢弃并标注）', () => {
    const legacy: TurnCourseSnapshot = snapshot({
      name: '旧课程',
      conventions: '约定'.repeat(4000), // 8000 字符
      syllabus: { total: 40, covered: 2, nextTitle: '单元'.repeat(16000) }, // 32000 字符
      resources: Array.from({ length: 40 }, (_, index) => ({
        kind: 'knowledge_base',
        label: `资料${index}`.repeat(30),
        availability: 'available' as const,
      })),
    });
    const frozen = structuredClone(legacy);
    // 路 1：大预算 → 课程块受限保留，免责句仍在
    const kept = buildChatRequest({
      history: [message('user', '旧'.repeat(900))],
      question: '继续',
      courseSnapshot: legacy,
      contextTokens: BIG_PROFILE.contextTokens,
      maxOutputTokens: BIG_PROFILE.maxOutputTokens,
    });
    expect(kept.ok).toBe(true);
    if (!kept.ok) return;
    expect(kept.record.courseDropped).toBe(false);
    expect(kept.messages[0]!.role).toBe('system');
    expect(kept.messages[0]!.content).toContain(COURSE_CONTEXT_DISCLAIMER);
    expect(totalChars(kept)).toBeLessThanOrEqual(
      Math.min(kept.record.inputBudgetChars, BACKEND_REQUEST_LIMITS.maxTotalChars),
    );
    expect(kept.messages.every((m) => m.content.length <= BACKEND_REQUEST_LIMITS.maxMessageChars)).toBe(
      true,
    );

    // 路 2：小预算（2000）放不下受限课程块 → 整体丢弃课程上下文并如实标注
    const dropped = buildChatRequest({
      history: [message('user', '旧'.repeat(900))],
      question: '继续',
      courseSnapshot: legacy,
      contextTokens: PROFILE.contextTokens,
      maxOutputTokens: PROFILE.maxOutputTokens,
    });
    expect(dropped.ok).toBe(true);
    if (!dropped.ok) return;
    expect(dropped.record.courseDropped).toBe(true);
    expect(dropped.record.courseTrimmedFields).toEqual([]);
    expect(dropped.notes).toContainEqual({ kind: 'course-dropped' });
    expect(dropped.messages.some((m) => m.role === 'system')).toBe(false);
    expect(totalChars(dropped)).toBeLessThanOrEqual(BUDGET);
    expect(legacy).toEqual(frozen); // 旧快照与课程数据同样不被改写
  });

  it('正常课程块 + 接近预算的历史 + 接近预算的当前问题：总量不超预算，历史整条丢弃计数正确', () => {
    const question = '问'.repeat(1200);
    const history = [
      message('user', '旧'.repeat(700)),
      message('assistant', '答'.repeat(700)),
      message('user', '近'.repeat(50)),
    ];
    const built = buildChatRequest({
      history,
      question,
      courseSnapshot: snapshot(),
      contextTokens: PROFILE.contextTokens,
      maxOutputTokens: PROFILE.maxOutputTokens,
    });
    expect(built.ok).toBe(true);
    if (!built.ok) return;
    expect(built.record.inputBudgetChars).toBe(BUDGET);
    // 总字符 ≤ min(预算, 后端总上限)，每条 ≤ 后端单条上限
    expect(totalChars(built)).toBeLessThanOrEqual(Math.min(BUDGET, BACKEND_REQUEST_LIMITS.maxTotalChars));
    expect(built.messages.every((m) => m.content.length <= BACKEND_REQUEST_LIMITS.maxMessageChars)).toBe(
      true,
    );
    // 当前问题逐字不裁剪、位于最后
    expect(built.messages.at(-1)).toEqual({ role: 'user', content: question });
    // 历史按「整条」取舍：保留的与新问题相邻的最近一条完全一致，更旧的两条整条丢弃
    expect(built.record.historyDroppedMessages).toBe(2);
    expect(built.notes).toContainEqual({ kind: 'history-dropped', messages: 2 });
    expect(built.messages.map((m) => m.role)).toEqual(['system', 'user', 'user']);
    expect(built.messages[1]!.content).toBe('近'.repeat(50));
    // 账目与实际发送逐字段一致
    expect(built.record.totalChars).toBe(totalChars(built));
  });

  it('条数上限（200）与单条上限（32000）都是硬约束：超出者整条丢弃/不发送', () => {
    const many = Array.from({ length: 250 }, (_, index) => message('user', `问题${index}`.repeat(3)));
    const built = buildChatRequest({
      history: many,
      question: '最后一个问题',
      contextTokens: BIG_PROFILE.contextTokens,
      maxOutputTokens: BIG_PROFILE.maxOutputTokens,
    });
    expect(built.ok).toBe(true);
    if (!built.ok) return;
    expect(built.messages.length).toBe(BACKEND_REQUEST_LIMITS.maxMessages);
    expect(built.record.historyDroppedMessages).toBe(51);
    // 超长单条历史（>32000）：整条丢弃，不截断、不发送
    const overLong = buildChatRequest({
      history: [message('assistant', '答'.repeat(40000)), message('user', '保留的近况')],
      question: '新问题',
      contextTokens: BIG_PROFILE.contextTokens,
      maxOutputTokens: BIG_PROFILE.maxOutputTokens,
    });
    expect(overLong.ok).toBe(true);
    if (!overLong.ok) return;
    expect(overLong.messages.map((m) => m.content)).toEqual(['保留的近况', '新问题']);
    expect(overLong.record.historyDroppedMessages).toBe(1);
    expect(overLong.messages.every((m) => m.content.length <= BACKEND_REQUEST_LIMITS.maxMessageChars)).toBe(
      true,
    );
  });

  it('当前问题放不下：ok:false、allowedChars 可读、文案为字符估算（不含精确 token 表述）', () => {
    const built = buildChatRequest({
      history: [],
      question: '问'.repeat(2001),
      contextTokens: PROFILE.contextTokens,
      maxOutputTokens: PROFILE.maxOutputTokens,
    });
    expect(built.ok).toBe(false);
    if (built.ok) return;
    expect(built.reason).toBe('question-too-large');
    expect(built.questionChars).toBe(2001);
    expect(built.allowedChars).toBe(BUDGET);
    expect(built.message).toContain('2001');
    expect(built.message).toContain('2000');
    expect(built.message).toContain('字符估算');
    expect(built.message).not.toContain('token');

    // 单条上限同样作用于当前问题：32000 可发、32001 明确失败
    const boundary = buildChatRequest({
      history: [],
      question: 'q'.repeat(BACKEND_REQUEST_LIMITS.maxMessageChars),
      contextTokens: BIG_PROFILE.contextTokens,
      maxOutputTokens: BIG_PROFILE.maxOutputTokens,
    });
    expect(boundary.ok).toBe(true);
    const tooLarge = buildChatRequest({
      history: [],
      question: 'q'.repeat(BACKEND_REQUEST_LIMITS.maxMessageChars + 1),
      contextTokens: BIG_PROFILE.contextTokens,
      maxOutputTokens: BIG_PROFILE.maxOutputTokens,
    });
    expect(tooLarge.ok).toBe(false);
    if (tooLarge.ok) return;
    expect(tooLarge.allowedChars).toBe(BACKEND_REQUEST_LIMITS.maxMessageChars);
  });

  it('免责句在任何裁剪/收缩路径下都保留（课程块未被整体丢弃时）', () => {
    const variants: TurnCourseSnapshot[] = [
      snapshot({ resources: [] }), // 无登记资源也必须带免责句
      snapshot({ name: '课'.repeat(500) }),
      snapshot({ syllabus: { total: 3, covered: 0, nextTitle: null } }),
      snapshot({ resources: [{ kind: 'notebook', label: '标'.repeat(500), availability: 'missing' }] }),
      snapshot({ resources: Array.from({ length: 30 }, () => ({ kind: 'book', label: '资料'.repeat(60), availability: 'unknown' as const })) }),
      snapshot({ conventions: '约定'.repeat(2000) }),
    ];
    for (const variant of variants) {
      const built = buildChatRequest({
        history: [],
        question: '问题',
        courseSnapshot: variant,
        contextTokens: BIG_PROFILE.contextTokens,
        maxOutputTokens: BIG_PROFILE.maxOutputTokens,
      });
      expect(built.ok, '构建应成功').toBe(true);
      if (!built.ok) continue;
      expect(built.record.courseDropped).toBe(false);
      const block = built.messages[0]!;
      expect(block.role).toBe('system');
      expect(block.content).toContain(COURSE_CONTEXT_DISCLAIMER);
      expect(block.content.length).toBeLessThanOrEqual(2400);
    }
    // 单条上限被压到极小（< 固定行与免责句的最小长度）时整体丢弃，而不是砍掉免责句
    const tight = buildChatRequest({
      history: [],
      question: '问题',
      courseSnapshot: snapshot(),
      contextTokens: BIG_PROFILE.contextTokens,
      maxOutputTokens: BIG_PROFILE.maxOutputTokens,
      limits: { ...BACKEND_REQUEST_LIMITS, maxMessageChars: 60 },
    });
    expect(tight.ok).toBe(true);
    if (!tight.ok) return;
    expect(tight.record.courseDropped).toBe(true);
    expect(tight.messages.some((m) => m.role === 'system')).toBe(false);
    // 直接渲染：极小上限返回 null（调用方必须整体丢弃）
    expect(renderCourseContextBlock(snapshot(), { ...BACKEND_REQUEST_LIMITS, maxMessageChars: 60 })).toBeNull();
  });

  it('历史尾部若就是当前问题（重试路径传入的完整历史），不重复发送同一条用户消息', () => {
    const history = [message('user', '第一问'), message('user', '第二问')];
    const built = buildChatRequest({
      history,
      question: '第二问',
      contextTokens: PROFILE.contextTokens,
      maxOutputTokens: PROFILE.maxOutputTokens,
    });
    expect(built.ok).toBe(true);
    if (!built.ok) return;
    expect(built.messages.map((m) => m.content)).toEqual(['第一问', '第二问']);
    expect(built.record.historyDroppedMessages).toBe(0);
  });
});

describe('store：预检失败无副作用、账目随轮次持久化、旧轮重试沿用旧快照', () => {
  it('当前问题放不下：不发请求、不清草稿、不入库用户消息、不建占位、sending=false、无未处理拒绝，改短后可发送', async () => {
    const { store, requests } = buildScriptedStore();
    await store.getState().init();
    const course = createCourse('预算课程', '先复习再提问');
    store.getState().newConversation({ courseId: course.id });
    const longQuestion = '长'.repeat(4000);
    store.getState().setDraft(longQuestion);

    const rejections: unknown[] = [];
    const onRejection = (reason: unknown) => rejections.push(reason);
    process.on('unhandledRejection', onRejection);
    try {
      await expect(store.getState().send(longQuestion, PROFILE)).resolves.toBeUndefined();
    } finally {
      process.off('unhandledRejection', onRejection);
    }
    await new Promise((resolve) => setTimeout(resolve, 0));
    await new Promise((resolve) => setTimeout(resolve, 0));

    expect(requests).toHaveLength(0); // 没有发往服务层的请求
    expect(rejections).toEqual([]); // 无未处理 Promise
    expect(store.getState().sending).toBe(false);
    expect(store.getState().messages).toEqual([]); // 不入库用户消息、不建助手占位
    expect(store.getState().draft).toBe(longQuestion); // 草稿保留可改
    expect(store.getState().budgetNotice).toContain('字符估算');

    // 改短后正常发送成功，提示清除，账目随助手消息持久化
    await store.getState().send('短问题', PROFILE);
    expect(store.getState().budgetNotice).toBeNull();
    expect(requests).toHaveLength(1);
    const last = store.getState().messages.at(-1)!;
    expect(last.role).toBe('assistant');
    expect(last.requestBudget?.totalChars).toBe(
      requests[0]!.messages.reduce((total, item) => total + item.content.length, 0),
    );
    expect(last.requestBudget?.courseDropped).toBe(false);
  });

  it('旧轮重试用冻结的旧快照、新轮用新快照、普通会话不带课程块；账目与实际发送一致', async () => {
    const course = createCourse('预算课程', '（演示描述）');
    updateCourse(course.id, { instructions: '旧约定：先复习错题' });
    const { store, requests } = buildScriptedStore(['error', 'ok', 'ok', 'ok']);
    await store.getState().init();
    store.getState().newConversation({ courseId: course.id });
    await store.getState().send('第一轮问题', PROFILE);
    expect(store.getState().messages.at(-1)!.status).toBe('error');
    const failedId = store.getState().messages.at(-1)!.id;

    // 课程改名 + 改约定（模拟"课程修改"）
    updateCourse(course.id, { name: '预算课程（改名后）', instructions: '新约定：先做小测' });

    await store.getState().retry(failedId, PROFILE);
    const retried = requests[1]!;
    expect(retried.messages[0]!.role).toBe('system');
    expect(retried.messages[0]!.content).toContain('预算课程');
    expect(retried.messages[0]!.content).not.toContain('改名后');
    expect(retried.messages[0]!.content).toContain('旧约定：先复习错题');
    // 账目随助手消息持久化，并与实际发送逐字段一致
    const record = store.getState().messages.at(-1)!.requestBudget!;
    expect(record.totalChars).toBe(
      retried.messages.reduce((total, item) => total + item.content.length, 0),
    );
    expect(record.inputBudgetChars).toBe(Math.min(BUDGET, BACKEND_REQUEST_LIMITS.maxTotalChars));
    expect(record.maxMessageChars).toBe(BACKEND_REQUEST_LIMITS.maxMessageChars);
    expect(record.maxTotalChars).toBe(BACKEND_REQUEST_LIMITS.maxTotalChars);

    // 新轮：用新快照
    await store.getState().send('第二轮问题', PROFILE);
    expect(requests[2]!.messages[0]!.content).toContain('改名后');
    expect(requests[2]!.messages[0]!.content).toContain('新约定：先做小测');

    // 普通会话（无课程）：不带课程块，路径不回退
    store.getState().newConversation();
    await store.getState().send('普通问题', PROFILE);
    expect(requests[3]!.messages.some((m) => m.role === 'system')).toBe(false);
    expect(store.getState().messages.at(-1)!.courseContext).toBeUndefined();
    expect(store.getState().messages.at(-1)!.requestBudget?.courseDropped).toBe(false);
  });

  it('旧轮重试遇到放不下的历史问题时：保留失败态与重试入口（不改动消息、不占位），换回大预算后重试成功', async () => {
    const { store, requests } = buildScriptedStore(['error', 'ok']);
    await store.getState().init();
    store.getState().newConversation();
    const longQuestion = '问'.repeat(5000);
    await store.getState().send(longQuestion, BIG_PROFILE); // 大预算可发，第 1 轮失败
    const failedId = store.getState().messages.at(-1)!.id;
    expect(store.getState().messages.at(-1)!.status).toBe('error');
    const messagesBeforeRetry = store.getState().messages.map((m) => ({ id: m.id, status: m.status }));

    await store.getState().retry(failedId, PROFILE); // 小预算：当前问题放不下
    expect(requests).toHaveLength(1); // 没有新请求
    expect(store.getState().sending).toBe(false);
    expect(store.getState().budgetNotice).toContain('字符估算');
    expect(store.getState().messages.map((m) => ({ id: m.id, status: m.status }))).toEqual(
      messagesBeforeRetry,
    ); // 失败态与重试入口原样保留（未被 superseded、未新增占位）

    await store.getState().retry(failedId, BIG_PROFILE); // 换回大预算：重试成功
    expect(requests).toHaveLength(2);
    expect(store.getState().budgetNotice).toBeNull();
    expect(store.getState().messages.at(-1)!.status).toBe('done');
  });

  it('UI 可输入的超长大纲标题：真实请求里的课程块合规，课程原始数据不被改写', async () => {
    const hugeTitle = '单'.repeat(32001);
    const course = createCourse('预算课程', '');
    setCourseSyllabus(course.id, parseSyllabusText(hugeTitle));
    const stored = readCourses().find((item) => item.id === course.id)!;
    const { store, requests } = buildScriptedStore(['ok']);
    await store.getState().init();
    store.getState().newConversation({ courseId: course.id });
    await store.getState().send('这个单元怎么讲？', PROFILE);

    const request = requests[0]!;
    const total = request.messages.reduce((sum, item) => sum + item.content.length, 0);
    expect(request.messages[0]!.role).toBe('system');
    expect(request.messages[0]!.content).toContain(COURSE_CONTEXT_DISCLAIMER);
    expect(request.messages[0]!.content.length).toBeLessThanOrEqual(2400);
    expect(request.messages.every((m) => m.content.length <= BACKEND_REQUEST_LIMITS.maxMessageChars)).toBe(
      true,
    );
    expect(total).toBeLessThanOrEqual(Math.min(BUDGET, BACKEND_REQUEST_LIMITS.maxTotalChars));
    expect(store.getState().messages.at(-1)!.requestBudget?.courseDropped).toBe(false);
    // 课程原始数据未被改写：大纲标题仍是原文，快照冻结的是受限后的渲染输入（不写回课程）
    expect(readCourses().find((item) => item.id === course.id)!.syllabus[0]!.title).toBe(hugeTitle);
    expect(stored.syllabus[0]!.title).toBe(hugeTitle);
  });

  it('课程块整体放不下时：本轮不带课程上下文，账目与说明如实标注（不伪造残缺上下文）', async () => {
    const course = createCourse('预算课程', '约定'.repeat(600)); // 约定 1200 字符
    setCourseSyllabus(course.id, parseSyllabusText('单元'.repeat(4000))); // 大纲标题 8000 字符
    const { store, requests } = buildScriptedStore(['ok']);
    await store.getState().init();
    store.getState().newConversation({ courseId: course.id });
    // 问题本身占满预算的绝大部分：课程块（含固定行与免责句）放不下 → 整体丢弃
    await store.getState().send('问'.repeat(1900), PROFILE);

    const request = requests[0]!;
    expect(request.messages.some((m) => m.role === 'system')).toBe(false);
    const record = store.getState().messages.at(-1)!.requestBudget!;
    expect(record.courseDropped).toBe(true);
    expect(record.courseTrimmedFields).toEqual([]);
    expect(record.totalChars).toBeLessThanOrEqual(BUDGET);
  });

  it('课程目录读取失败时仍走预检：按普通问答发送并如实提示（不回落到其他课程）', async () => {
    const { store, requests } = buildScriptedStore(['ok']);
    await store.getState().init();
    store.getState().newConversation({ courseId: 'demo-course-math' });
    const original = Storage.prototype.getItem;
    const spy = vi.spyOn(Storage.prototype, 'getItem').mockImplementation(function (
      this: Storage,
      name: string,
    ) {
      if (name === 'zhiqikeyuan:courses') throw new Error('denied');
      return original.call(this, name);
    });
    try {
      await store.getState().send('目录坏了还问', PROFILE);
    } finally {
      spy.mockRestore();
    }
    expect(requests[0]!.messages.every((m) => m.role !== 'system')).toBe(true);
    expect(store.getState().courseContextWarning).toContain('课程目录读取失败');
    expect(store.getState().messages.at(-1)!.requestBudget?.courseDropped).toBe(false);
  });

  it('课程删除后不注入上下文：预算账目仍随轮次持久化', async () => {
    const course = createCourse('即将删除的课程', '约定');
    const { store, requests } = buildScriptedStore(['ok']);
    await store.getState().init();
    store.getState().newConversation({ courseId: course.id });
    window.localStorage.setItem(
      'zhiqikeyuan:courses',
      JSON.stringify(readCourses().filter((item) => item.id !== course.id)),
    );
    await store.getState().send('课程没了还问', PROFILE);
    expect(requests[0]!.messages.every((m) => m.role !== 'system')).toBe(true);
    expect(store.getState().courseContextWarning).toContain('所属课程已删除或不可用');
    expect(store.getState().messages.at(-1)!.requestBudget?.totalChars).toBe(
      requests[0]!.messages.reduce((total, item) => total + item.content.length, 0),
    );
  });

  it('课程块输出与既有渲染保持同一文案契约（正常快照逐字符一致）', () => {
    // 正常快照：受限渲染不改变任何字段，输出与 services/course-session.ts 的既有渲染完全一致
    // （避免出现两套课程块文案；超限快照的收缩由本模块负责并如实记录字段）
    const normal = snapshot();
    expect(renderCourseContextBlock(normal)!.text).toBe(courseContextMessage(normal));
    expect(renderCourseContextBlock(normal)!.trimmedFields).toEqual([]);

    // 真实演示课程快照走产品路径：课程名、约定与免责句都如实出现
    const course = readCourses().find((item) => item.id === 'demo-course-math')!;
    const frozen = buildCourseSnapshot(course, '2026-09-22T00:00:00.000Z');
    const built = buildChatRequest({
      history: [],
      question: '这个单元怎么讲？',
      courseSnapshot: frozen,
      contextTokens: BIG_PROFILE.contextTokens,
      maxOutputTokens: BIG_PROFILE.maxOutputTokens,
    });
    expect(built.ok).toBe(true);
    if (!built.ok) return;
    expect(built.messages[0]!.content).toContain('课程名称：七年级数学（演示课程）');
    expect(built.messages[0]!.content).toContain('每次课前先复习上一单元错题（演示约定）。');
    expect(built.messages[0]!.content).toContain(COURSE_CONTEXT_DISCLAIMER);
    expect(built.record.courseDropped).toBe(false);
  });

  it('脏历史快照（类型系统之外的 null 资源条目/缺失字段）不抛错：失败仍可重试，且不伪造内容', () => {
    const corrupt = {
      courseId: 'cs-legacy',
      name: undefined,
      conventions: null,
      syllabus: null,
      resources: [null, { kind: null, label: null, availability: null }, 'broken'],
      frozenAt: '2026-01-01T00:00:00.000Z',
    } as unknown as TurnCourseSnapshot;

    // 渲染层：不得抛错；非对象条目被丢弃，剩余项以 unknown 兜底，免责句仍在
    const block = renderCourseContextBlock(corrupt);
    expect(block).not.toBeNull();
    expect(block!.text).toContain(COURSE_CONTEXT_DISCLAIMER);

    // 构建层：ok:true（不因脏数据阻断发送），账目与实际一致，且不含任何编造的资源名
    const built = buildChatRequest({
      history: [],
      question: '这一题怎么解？',
      courseSnapshot: corrupt,
      contextTokens: 8000,
      maxOutputTokens: 512,
    });
    expect(built.ok).toBe(true);
    if (!built.ok) return;
    expect(built.record.totalChars).toBe(
      built.messages.reduce((total, message) => total + message.content.length, 0),
    );
    expect(built.messages[0]!.content).toContain(COURSE_CONTEXT_DISCLAIMER);
    expect(built.messages[0]!.content).not.toContain('null');
    expect(built.messages[0]!.content).not.toContain('不可用');
  });
});
