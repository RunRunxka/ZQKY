import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ContentMarkdown, RichBlocks, tableRows, type RichAssetLoader } from './RichContentRenderer';
import type { ContentBlock } from '@/contracts/teaching-loop';

afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
describe('受控富内容审阅', () => {
  it.each(['|', ',', ''])('OMML delimiter完整显示三个参数与显式分隔符%s', async (separator) => {
    const ns = 'http://schemas.openxmlformats.org/officeDocument/2006/math';
    const xml = `<m:oMath xmlns:m="${ns}"><m:d><m:dPr><m:sepChr m:val="${separator}"/></m:dPr><m:e><m:r><m:t>x</m:t></m:r></m:e><m:e/><m:e><m:f><m:num><m:r><m:t>y</m:t></m:r></m:num><m:den><m:r><m:t>2</m:t></m:r></m:den></m:f></m:e></m:d></m:oMath>`;
    const ui = render(<RichBlocks blocks={[{ id:'delimiter', kind:'formula', ommlXml:xml }]} />);
    await waitFor(() => expect(ui.container.querySelector('math mfrac')).not.toBeNull());
    expect(ui.container.querySelector('math')?.textContent).toBe(`(x${separator}${separator}y2)`);
    expect(ui.queryByRole('status')).toBeNull();
    expect(ui.container.querySelector('pre')).toHaveTextContent(xml);
  });
  it('OMML默认分隔符和单个空参数不省略，混入未知结构明确失败', async () => {
    const ns = 'http://schemas.openxmlformats.org/officeDocument/2006/math';
    const ui = render(<RichBlocks blocks={[{ id:'default', kind:'formula', ommlXml:`<m:oMath xmlns:m="${ns}"><m:d><m:e><m:r><m:t>x</m:t></m:r></m:e><m:e><m:r><m:t>y</m:t></m:r></m:e></m:d></m:oMath>` }]} />);
    await waitFor(() => expect(ui.container.querySelector('math')?.textContent).toBe('(x|y)'));
    ui.rerender(<RichBlocks blocks={[{ id:'empty',kind:'formula',ommlXml:`<m:oMath xmlns:m="${ns}"><m:d><m:e/></m:d></m:oMath>` }]} />);
    await waitFor(() => expect(ui.container.querySelector('math')?.textContent).toBe('()'));
    ui.rerender(<RichBlocks blocks={[{ id:'bad',kind:'formula',ommlXml:`<m:oMath xmlns:m="${ns}"><m:d><m:e/><m:unknown/></m:d></m:oMath>` }]} />);
    await waitFor(() => expect(ui.getByRole('status')).toHaveTextContent('暂不能直接显示'));
    expect(ui.container.querySelector('math')).toBeNull();
  });
  it('OMML分式和上下标以受控MathML显示，未知结构保留原文并明确提示', async () => {
    const ns = 'http://schemas.openxmlformats.org/officeDocument/2006/math';
    const xml = `<m:oMath xmlns:m="${ns}"><m:f><m:num><m:sSup><m:e><m:r><m:t>x</m:t></m:r></m:e><m:sup><m:r><m:t>2</m:t></m:r></m:sup></m:sSup></m:num><m:den><m:r><m:t>3</m:t></m:r></m:den></m:f></m:oMath>`;
    const ui = render(<RichBlocks blocks={[{ id:'omml', kind:'formula', ommlXml:xml }]} />);
    await waitFor(() => expect(ui.container.querySelector('math mfrac msup')).not.toBeNull());
    expect(ui.container.querySelector('math')).toHaveTextContent('x23');
    expect(ui.container.querySelector('pre')).toHaveTextContent(xml);
    ui.rerender(<RichBlocks blocks={[{id:'unknown',kind:'formula',ommlXml:`<m:oMath xmlns:m="${ns}"><m:unknown/></m:oMath>`}]} />);
    await waitFor(() => expect(screen.getByRole('status')).toHaveTextContent('暂不能直接显示'));
    expect(ui.container.querySelector('math')).toBeNull();
  });
  it('渲染公式与合并表格，HTML和外部图片不会执行或请求', () => {
    const blocks: ContentBlock[] = [
      { id: 'p', kind: 'paragraph', text: '题面 **加粗** <script>alert(1)</script> ![外部](https://example.org/a.png)' },
      { id: 'f', kind: 'formula', latex: 'x^2+1' },
      { id: 't', kind: 'table', columnCount: 2, cells: [
        { text: '跨行', isHeader: true, rowSpan: 2, colSpan: 1 },
        { text: '一', isHeader: false, rowSpan: 1, colSpan: 1 },
        { text: '二', isHeader: false, rowSpan: 1, colSpan: 1 },
      ] },
    ];
    const ui = render(<RichBlocks blocks={blocks} />);
    expect(ui.container.querySelector('script')).toBeNull();
    expect(ui.container.querySelector('img')).toBeNull();
    expect(ui.container.querySelector('.katex')).not.toBeNull();
    expect(screen.getByRole('columnheader', { name: '跨行' })).toHaveAttribute('rowspan', '2');
    expect(screen.getAllByRole('row')).toHaveLength(2);
    expect(tableRows((blocks[2] as Extract<ContentBlock, {kind:'table'}>).cells, 2).map((row) => row.length)).toEqual([2, 1]);
  });
  it('旧修订迟到图片不会替换当前资产，退出时释放object URL', async () => {
    let resolveOld!: (blob: Blob) => void;
    const oldLoader = vi.fn<RichAssetLoader>(() => new Promise<Blob>((resolve) => { resolveOld = resolve; }));
    const nextLoader = vi.fn(async () => new Blob(['next'], { type: 'image/png' }));
    const create = vi.fn().mockReturnValue('blob:next');
    const revoke = vi.fn();
    vi.stubGlobal('URL', class extends URL { static createObjectURL = create; static revokeObjectURL = revoke; });
    const image: ContentBlock = { id: 'picture', kind: 'image', assetId: 'blobs/test', width: 100, height: 60 };
    const ui = render(<RichBlocks blocks={[image]} loadAsset={oldLoader} assetScope="old" />);
    ui.rerender(<RichBlocks blocks={[image]} loadAsset={nextLoader} assetScope="next" />);
    await waitFor(() => expect(screen.getByRole('img')).toHaveAttribute('src', 'blob:next'));
    resolveOld(new Blob(['old'], { type: 'image/png' }));
    await Promise.resolve();
    expect(create).toHaveBeenCalledTimes(1);
    expect(oldLoader.mock.calls[0][1].aborted).toBe(true);
    ui.unmount();
    expect(revoke).toHaveBeenCalledWith('blob:next');
  });
  it('Markdown保留数学与代码，不把HTML转成DOM', () => {
    const ui = render(<ContentMarkdown text={'$x+1$\n\n`<img src=x onerror=alert(1)>`'} />);
    expect(ui.container.querySelector('.katex')).not.toBeNull();
    expect(ui.container.querySelector('img')).toBeNull();
    expect(ui.container.querySelector('code')).toHaveTextContent('<img');
  });
});
