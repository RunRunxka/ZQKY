import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    include: ['docs/qa/main-review-20260922/book-probe.test.ts'],
  },
});
