import { defineConfig } from 'vitest/config';
import path from 'node:path';
export default defineConfig({resolve:{alias:{'@':path.resolve('apps/web/src')}},test:{environment:'jsdom',include:['_work/course-gate-20260922/probe.test.ts','apps/web/src/services/course-session.test.ts','apps/web/src/features/chat/model/course-context.test.ts']}});
