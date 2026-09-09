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
