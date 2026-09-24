import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { ReasoningDisclosure } from './ReasoningDisclosure';
afterEach(cleanup);
it('推理阶段展开，回答开始后自动折叠，用户手动选择优先', () => {
  const ui = render(
    <ReasoningDisclosure text="逐步分析" working>
      正在推理
    </ReasoningDisclosure>,
  );
  const toggle = screen.getByRole('button', { name: '推理过程' });
  expect(toggle).toHaveAttribute('aria-expanded', 'true');
  ui.rerender(
    <ReasoningDisclosure text="逐步分析完毕" working={false}>
      正在回答
    </ReasoningDisclosure>,
  );
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  fireEvent.click(toggle);
  expect(toggle).toHaveAttribute('aria-expanded', 'true');
  ui.rerender(
    <ReasoningDisclosure text="逐步分析完毕" working={false}>
      已完成
    </ReasoningDisclosure>,
  );
  expect(toggle).toHaveAttribute('aria-expanded', 'true');
});
it('推理时手动收起后，新增增量不会强制展开', () => {
  const ui = render(
    <ReasoningDisclosure text="分析" working>
      正在推理
    </ReasoningDisclosure>,
  );
  fireEvent.click(screen.getByRole('button', { name: '推理过程' }));
  ui.rerender(
    <ReasoningDisclosure text="分析第二步" working>
      正在推理
    </ReasoningDisclosure>,
  );
  expect(screen.getByRole('button', { name: '推理过程' })).toHaveAttribute(
    'aria-expanded',
    'false',
  );
  expect(screen.queryByRole('region', { name: '推理内容' })).toBeNull();
});

it('正文出现后自动折叠时，流仍活动；手动重开后跟随持续推理', () => {
  const ui = render(
    <ReasoningDisclosure text={'推理内容\n'.repeat(20)} working autoExpand>
      正在推理
    </ReasoningDisclosure>,
  );
  const toggle = screen.getByRole('button', { name: '推理过程' });
  expect(toggle).toHaveAttribute('aria-expanded', 'true');
  ui.rerender(
    <ReasoningDisclosure text={'推理内容\n'.repeat(30)} working autoExpand={false}>
      正在回答
    </ReasoningDisclosure>,
  );
  expect(toggle).toHaveAttribute('aria-expanded', 'false');
  fireEvent.click(toggle);
  expect(toggle).toHaveAttribute('aria-expanded', 'true');
  expect(ui.container.querySelector('.chat-reasoning-body')?.textContent).toContain('推理内容');
});

it('折叠过渡期间内容仍在 DOM（折叠动画可见），从未展开的历史消息不渲染内容', () => {
  // 从未展开（working=false 且用户未展开）：不渲染正文，避免无谓解析
  const ui = render(
    <ReasoningDisclosure text="历史推理" working={false}>
      已完成
    </ReasoningDisclosure>,
  );
  expect(ui.container.querySelector('.chat-reasoning-body')?.textContent).toBe('');

  // 流式中（自动展开）：渲染正文
  ui.rerender(
    <ReasoningDisclosure text="正在推理 $a^2$" working>
      正在推理
    </ReasoningDisclosure>,
  );
  expect(ui.container.querySelector('.chat-reasoning-body')?.textContent).toContain('正在推理');
  expect(ui.container.querySelectorAll('.chat-reasoning-body .katex').length).toBeGreaterThan(0);

  // 折叠（正文出现 → 自动收起）：内容保留到过渡结束，动画不会变成空框收缩
  ui.rerender(
    <ReasoningDisclosure text="正在推理 $a^2$" working={false}>
      已完成
    </ReasoningDisclosure>,
  );
  expect(ui.container.querySelector('.chat-reasoning-body')?.textContent).toContain('正在推理');
});
