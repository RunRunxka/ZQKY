/**
 * 探针反转（CHAT-CONTEXT-BUDGET v1）：把 `probe.test.ts` 的两条缺陷场景改从**产品路径**断言。
 *
 * 与原探针的差别与理由：
 * - 原探针第 1 条直接调用 `services/course-session.ts` 的 `courseContextMessage`（那是当时的
 *   产品路径）；修复后产品路径改经 `features/chat/model/request-budget.ts` 的受限渲染，
 *   课程块上限在那里生效。因此反转探针断言**真实请求报文**（store → service.run 的 messages），
 *   而不是断言那个已不在产品路径上的孤立函数。
 * - 原探针第 2 条断言"总字符 > 预算"（缺陷成立）；反转后断言"总字符 ≤ 预算"。
 *
 * 修复前这两条都会失败（D1：32088 字 system 消息；D2：2040 > 2000），修复后通过。
 */
import { expect, it } from 'vitest';
import { contextBudgetChars } from '@/contracts/chat';
import type { ChatServiceRequest } from '@/features/chat/model/chat-service';
import { createChatStore } from '@/features/chat/model/store';
import { BACKEND_REQUEST_LIMITS } from '@/features/chat/model/request-budget';
import { createMemoryChatRepository } from '@/services/chat-repository';
import {
  createCourse,
  parseSyllabusText,
  readCourses,
  setCourseSyllabus,
} from '@/services/courses-store';

/** 与 `_work/course-gate-20260922/probe.test.ts` 相同的隔离档案（内联注入服务，不发真实请求） */
const profile = {
  id: 'probe',
  modelLabel: 'isolated injected service',
  contextTokens: 4000,
  maxOutputTokens: 2000,
};
const COURSE_LIMIT = 2400;
/** 免责句：课程块未被整体丢弃时必须出现 */
const DISCLAIMER = '内容未解析、未检索、未随本请求发送';

function probeStore(requests: ChatServiceRequest[]) {
  return createChatStore({
    repository: createMemoryChatRepository(),
    service: {
      kind: 'real',
      run: async (request, emit) => {
        requests.push(request);
        emit({ sessionId: request.sessionId, turnId: request.turnId, type: 'end', finishReason: 'stop' });
      },
    },
  });
}

it('reversal D1: UI 可输入的超长大纲标题在真实请求中不再超课程/后端上限', async () => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  const course = createCourse('课程', '');
  setCourseSyllabus(course.id, parseSyllabusText('单'.repeat(32001)));
  const requests: ChatServiceRequest[] = [];
  const store = probeStore(requests);
  await store.getState().init();
  store.getState().newConversation({ courseId: course.id });
  await store.getState().send('这个单元怎么讲？', profile);

  const block = requests[0]!.messages[0]!;
  console.info(
    JSON.stringify({
      kind: 'course-message',
      chars: block.content.length,
      courseLimit: COURSE_LIMIT,
      apiSingleMessageLimit: BACKEND_REQUEST_LIMITS.maxMessageChars,
    }),
  );
  expect(requests).toHaveLength(1);
  expect(block.role).toBe('system');
  expect(block.content.length).toBeLessThanOrEqual(COURSE_LIMIT);
  expect(block.content.length).toBeLessThanOrEqual(BACKEND_REQUEST_LIMITS.maxMessageChars);
  expect(block.content).toContain(DISCLAIMER);
  // 渲染期防御裁剪不回写课程原始数据
  expect(readCourses().find((item) => item.id === course.id)!.syllabus[0]!.title).toBe(
    '单'.repeat(32001),
  );
});

it('reversal D2: 课程块在选中总预算之内（不再追加到预算之外）', async () => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  const course = createCourse('课程', '');
  const requests: ChatServiceRequest[] = [];
  const store = probeStore(requests);
  await store.getState().init();
  store.getState().newConversation({ courseId: course.id });
  await store.getState().send('问'.repeat(1990), profile);

  const total = requests[0]!.messages.reduce((sum, item) => sum + item.content.length, 0);
  const budget = contextBudgetChars(profile.contextTokens, profile.maxOutputTokens);
  console.info(JSON.stringify({ kind: 'request-budget', chars: total, budget }));
  expect(total).toBeLessThanOrEqual(budget);
  expect(total).toBeLessThanOrEqual(BACKEND_REQUEST_LIMITS.maxTotalChars);
  expect(store.getState().messages.at(-1)!.requestBudget?.totalChars).toBe(total);
});

it('reversal: 课程块存在时位于最前、免责句在，且整条历史不拼接半条', async () => {
  window.localStorage.clear();
  window.sessionStorage.clear();
  const course = createCourse('课程', '每次课前先复习上一单元错题。');
  const requests: ChatServiceRequest[] = [];
  const store = probeStore(requests);
  await store.getState().init();
  store.getState().newConversation({ courseId: course.id });
  await store.getState().send('第一问', profile);
  await store.getState().send('第二问', profile);

  const second = requests[1]!;
  console.info(
    JSON.stringify({
      kind: 'second-turn-shape',
      roles: second.messages.map((item) => item.role),
      chars: second.messages.map((item) => item.content.length),
    }),
  );
  expect(second.messages[0]!.role).toBe('system');
  expect(second.messages[0]!.content).toContain('课程名称：课程');
  expect(second.messages[0]!.content).toContain(DISCLAIMER);
  // 历史按整条参与（第一问原文 + 当前问题），不重复当前问题、不拼接半条
  expect(second.messages.map((item) => item.role)).toEqual(['system', 'user', 'user']);
  expect(second.messages.slice(1).map((item) => item.content)).toEqual(['第一问', '第二问']);
});
