import '@testing-library/jest-dom/vitest';
import { beforeEach, vi } from 'vitest';

const realConsoleError = console.error;
const realAnchorClick = HTMLAnchorElement.prototype.click;

beforeEach(() => {
  // jsdom 没有 canvas 实现：统一模拟「拿不到 2D 上下文」，避免 not-implemented 噪声；
  // 依赖图形的组件须走「无上下文」的降级分支（如 KnowledgeDonut 的图例兜底）。
  vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(null);
  // Chart.js 在无上下文时会打一条已知日志；只过滤这一条，其余错误照常输出。
  vi.spyOn(console, 'error').mockImplementation((...args: unknown[]) => {
    if (String(args[0]).includes('Failed to create chart')) return;
    realConsoleError(...args);
  });
  // 下载导出会对 blob: 链接调用 a.click()；jsdom 不实现导航，这里拦截，文件保存由各测试的 createObjectURL 断言覆盖。
  vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(function (
    this: HTMLAnchorElement,
  ) {
    if (this.href.startsWith('blob:')) return;
    realAnchorClick.call(this);
  });
});
