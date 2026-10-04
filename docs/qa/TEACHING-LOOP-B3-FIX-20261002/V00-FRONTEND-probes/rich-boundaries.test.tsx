import { StrictMode, useState } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ContentMarkdown, RichBlocks, RichContentRenderer } from '@/components/ui/RichContentRenderer';
import { ContentForm, type QuestionFormValue } from '@/features/question-bank/ContentForm';
import { QuestionPreview } from '@/features/question-bank/QuestionPreview';
import { buildTaxonomyIndex } from '@/features/question-bank/taxonomy';
import type { ContentBlock, RichContentV2 } from '@/contracts/teaching-loop';

function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>((done) => { resolve = done; }); return { promise, resolve }; }
const metadata = { stageId: 'junior', gradeId: 'grade-1', subjectId: 'math', editionId: 'rj', knowledgeTags: ['legacy'], difficulty: 'easy' as const };
const paragraph: ContentBlock = { id: 'authoritative-stem', kind: 'paragraph', text: '富内容唯一题干' };
const rich: RichContentV2 = { version: 2, sharedMaterials: [{ id: 'material-1', blocks: [{ id: 'material-p', kind: 'paragraph', text: '必要共同材料' }] }], stemBlocks: [paragraph], optionBlocks: { A: [{ id: 'option-a', kind: 'paragraph', text: '富选项A' }] }, answerBlocks: [{ id: 'answer-p', kind: 'paragraph', text: '富答案' }], explanationBlocks: [{ id: 'explanation-p', kind: 'paragraph', text: '富解析' }], assets: [], origin: { originalAssetId: 'origin', originalSha256: '1'.repeat(64), sourceLocator: {} } };
const content = { type: 'single_choice' as const, stemMarkdown: '旧Markdown题干', options: [{ key: 'A', textMarkdown: '旧选项A' }, { key: 'B', textMarkdown: 'fallback-B' }], answer: { choiceKeys: ['A'], accepted: null, textMarkdown: '旧答案' }, explanationMarkdown: '旧解析', assetIds: [], richContent: rich };
let created = 0;
let create: ReturnType<typeof vi.fn>;
let revoke: ReturnType<typeof vi.fn>;
beforeEach(() => {
  created = 0; create = vi.fn(() => `blob:independent-${++created}`); revoke = vi.fn();
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: create });
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: revoke });
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('Independent rich authority and safe render', () => {
  it('all rich areas and common material win over old Markdown; per-key legacy option fallback is preserved', () => {
    render(<QuestionPreview content={content} />);
    expect(screen.getByText('富内容唯一题干')).toBeInTheDocument(); expect(screen.getByText('必要共同材料')).toBeInTheDocument();
    expect(screen.getByText('富选项A')).toBeInTheDocument(); expect(screen.getByText('fallback-B')).toBeInTheDocument(); expect(screen.getByText('富答案')).toBeInTheDocument(); expect(screen.getByText('富解析')).toBeInTheDocument();
    for (const old of ['旧Markdown题干', '旧选项A', '旧答案', '旧解析']) expect(screen.queryByText(old)).not.toBeInTheDocument();
  });
  it('explicit conversion clears rich authority before editable text can replace the derived projection', () => {
    const changes = vi.fn();
    function Form() { const [value, set] = useState<QuestionFormValue>({ content, metadata }); return <ContentForm value={value} taxonomy={buildTaxonomyIndex(null)} idPrefix="independent-rich" onChange={(next) => { changes(next); set(next); }} />; }
    render(<Form />);
    expect(screen.getByLabelText('题干')).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '明确转为 Markdown 编辑' }));
    expect(changes.mock.calls[0][0].content.richContent).toBeNull(); expect(screen.getByLabelText('题干')).toBeEnabled();
    fireEvent.change(screen.getByLabelText('题干'), { target: { value: '新文本权威' } });
    expect(changes.mock.calls.at(-1)?.[0].content).toMatchObject({ richContent: null, stemMarkdown: '新文本权威' });
    expect(content.richContent).toBe(rich); // old revision input is not mutated.
  });
  it('Markdown HTML, remote images and javascript links do not create executable or externally loaded DOM', () => {
    const ui = render(<ContentMarkdown text={'<script>globalThis.stolen=1</script>\n\n<img src="https://external.invalid/pixel">\n\n![remote](https://external.invalid/pixel)\n\n[bad](javascript:alert(1))\n\n$\\frac{1}{2}$'} />);
    expect(ui.container.querySelector('script')).toBeNull(); expect(ui.container.querySelector('img')).toBeNull();
    expect(ui.container.querySelector('a[href^="javascript:"]')).toBeNull(); expect(ui.container.querySelector('.katex')).not.toBeNull();
  });
  it('rowspan and colspan preserve physical merged grid, including occupied rows', () => {
    const ui = render(<RichBlocks blocks={[{ id: 'merged', kind: 'table', columnCount: 3, cells: [{ text: '左跨行', rowSpan: 2, colSpan: 1, isHeader: true }, { text: '顶双列', rowSpan: 1, colSpan: 2, isHeader: true }, { text: '第二行甲', rowSpan: 1, colSpan: 1, isHeader: false }, { text: '第二行乙', rowSpan: 1, colSpan: 1, isHeader: false }]}]} />);
    const rows = ui.container.querySelectorAll('tr'); expect(rows).toHaveLength(2);
    expect(rows[0].children).toHaveLength(2); expect(rows[1].children).toHaveLength(2);
    expect(rows[0].children[0]).toHaveAttribute('rowspan', '2'); expect(rows[0].children[1]).toHaveAttribute('colspan', '2');
    expect(rows[1]).toHaveTextContent('第二行甲第二行乙');
  });
  it('OMML fraction creates only MathML and always retains source XML', async () => {
    const xml = '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"><m:f><m:num><m:r><m:t>1</m:t></m:r></m:num><m:den><m:r><m:t>2</m:t></m:r></m:den></m:f></m:oMath>';
    const ui = render(<RichBlocks blocks={[{ id: 'omml', kind: 'formula', latex: null, ommlXml: xml }]} />);
    await waitFor(() => expect(ui.container.querySelector('math mfrac')).not.toBeNull());
    expect(ui.container.querySelector('pre')).toHaveTextContent(xml); expect(ui.container.querySelector('math span')).toBeNull();
  });
  for (const xml of ['<!DOCTYPE evil [<!ENTITY payload SYSTEM "file:///secret">]><m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math">&payload;</m:oMath>', '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"><script xmlns="http://www.w3.org/1999/xhtml">steal()</script></m:oMath>']) {
    it(`unsupported XML is shown as escaped evidence without math or HTML execution (${xml.startsWith('<!') ? 'DTD' : 'foreign namespace'})`, async () => {
      const ui = render(<RichBlocks blocks={[{ id: 'evil-omml', kind: 'formula', latex: null, ommlXml: xml }]} />);
      await screen.findByText(/此公式结构暂不能直接显示/); expect(ui.container.querySelector('math')).toBeNull(); expect(ui.container.querySelector('script')).toBeNull(); expect(ui.container.querySelector('pre')).toHaveTextContent(xml);
    });
  }
});

describe('Independent managed asset identity, abort and lifetime', () => {
  const image: ContentBlock = { id: 'same-image-block', kind: 'image', assetId: 'same-asset-id', width: 2, height: 3 };
  it('same asset ID in a different revision aborts the old fetch; late old byte success cannot create/reuse an object URL', async () => {
    const first = deferred<Blob>(); const second = deferred<Blob>(); const calls: AbortSignal[] = [];
    const load = vi.fn((_id: string, signal: AbortSignal) => { calls.push(signal); return calls.length === 1 ? first.promise : second.promise; });
    const ui = render(<RichBlocks blocks={[image]} loadAsset={load} assetScope="question-A|r1" />);
    ui.rerender(<RichBlocks blocks={[image]} loadAsset={load} assetScope="question-B|r1" />);
    expect(calls[0].aborted).toBe(true); expect(calls[1].aborted).toBe(false);
    await act(async () => first.resolve(new Blob(['old'], { type: 'image/png' })));
    expect(create).not.toHaveBeenCalled(); expect(ui.container.querySelector('img')).toBeNull();
    await act(async () => second.resolve(new Blob(['new'], { type: 'image/png' })));
    expect(screen.getByRole('img')).toHaveAttribute('src', 'blob:independent-1'); expect(create).toHaveBeenCalledTimes(1);
    ui.unmount(); expect(calls[1].aborted).toBe(true); expect(revoke).toHaveBeenCalledExactlyOnceWith('blob:independent-1');
  });
  it('loaded current URL is revoked on revision change and new bytes get a different URL', async () => {
    const load = vi.fn(() => Promise.resolve(new Blob(['png'], { type: 'image/png' })));
    const ui = render(<RichBlocks blocks={[image]} loadAsset={load} assetScope="same-question|r1" />);
    await screen.findByRole('img'); ui.rerender(<RichBlocks blocks={[image]} loadAsset={load} assetScope="same-question|r2" />);
    expect(revoke).toHaveBeenCalledWith('blob:independent-1'); await waitFor(() => expect(screen.getByRole('img')).toHaveAttribute('src', 'blob:independent-2'));
    ui.unmount(); expect(revoke).toHaveBeenCalledWith('blob:independent-2');
  });
  it('unmount and StrictMode discarded effect cannot create an URL from later bytes', async () => {
    const gate = deferred<Blob>(); const signals: AbortSignal[] = [];
    const load = vi.fn((_id: string, signal: AbortSignal) => { signals.push(signal); return gate.promise; });
    const ui = render(<StrictMode><RichContentRenderer content={{ ...rich, stemBlocks: [image] }} loadAsset={load} assetScope="strict-asset" /></StrictMode>);
    ui.unmount(); expect(signals.every((signal) => signal.aborted)).toBe(true);
    await act(async () => gate.resolve(new Blob(['late'], { type: 'image/png' })));
    expect(create).not.toHaveBeenCalled(); expect(revoke).not.toHaveBeenCalled();
  });
  it('SVG bytes are explicitly rejected and never become an image object URL', async () => {
    const ui = render(<RichBlocks blocks={[image]} loadAsset={async () => new Blob(['<svg onload="steal()"/>'], { type: 'image/svg+xml' })} assetScope="mime-probe" />);
    await screen.findByRole('alert'); expect(screen.getByRole('alert')).toHaveTextContent('资产不是可显示的图片'); expect(create).not.toHaveBeenCalled(); expect(ui.container.querySelector('img')).toBeNull();
  });
});
