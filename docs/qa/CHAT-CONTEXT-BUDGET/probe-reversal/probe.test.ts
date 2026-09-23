import { beforeEach, expect, it } from 'vitest';
import { createCourse, setCourseSyllabus, parseSyllabusText, readCourses } from '../../apps/web/src/services/courses-store';
import { buildCourseSnapshot, courseContextMessage } from '../../apps/web/src/services/course-session';
import { createChatStore } from '../../apps/web/src/features/chat/model/store';
import { createMemoryChatRepository } from '../../apps/web/src/services/chat-repository';
import { contextBudgetChars } from '../../apps/web/src/contracts/chat';
import type { ChatServiceRequest } from '../../apps/web/src/features/chat/model/chat-service';
beforeEach(() => { window.localStorage.clear(); window.sessionStorage.clear(); });

// Defect assertions: passing is evidence of a defect, not product acceptance.
it('defect: a UI-compatible long syllabus title exceeds course and API message limits', () => {
  const c = createCourse('课程', '');
  setCourseSyllabus(c.id, parseSyllabusText('单'.repeat(32001)));
  const text = courseContextMessage(buildCourseSnapshot(readCourses().find(x => x.id === c.id)!));
  console.info(JSON.stringify({kind:'course-message',chars:text.length,courseLimit:2400,apiSingleMessageLimit:32000}));
  expect(text.length).toBeGreaterThan(32000);
});

it('defect: normal course metadata is appended outside the selected total request budget', async () => {
  const c = createCourse('课程', '');
  const requests: ChatServiceRequest[] = [];
  const store = createChatStore({repository:createMemoryChatRepository(),service:{kind:'real',run:async(request,emit) => {
    requests.push(request);
    emit({sessionId:request.sessionId,turnId:request.turnId,type:'end',finishReason:'stop'});
  }}});
  await store.getState().init();
  store.getState().newConversation({courseId:c.id});
  const profile = {id:'probe',modelLabel:'isolated injected service',contextTokens:4000,maxOutputTokens:2000};
  await store.getState().send('问'.repeat(1990),profile);
  const total = requests[0]!.messages.reduce((n,m) => n+m.content.length,0);
  const budget = contextBudgetChars(profile.contextTokens,profile.maxOutputTokens);
  console.info(JSON.stringify({kind:'request-budget',chars:total,budget}));
  expect(requests[0]!.messages[0]!.role).toBe('system');
  expect(total).toBeGreaterThan(budget);
});
