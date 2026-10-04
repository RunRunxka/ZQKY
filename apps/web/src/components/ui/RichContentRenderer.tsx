'use client';

import { createElement, useEffect, useState, type ReactNode } from 'react';
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import remarkMath from 'remark-math';
import rehypeKatex from 'rehype-katex';
import type { ContentBlock, RichContentV2, TableCell } from '@/contracts/teaching-loop';
import 'katex/dist/katex.min.css';
import './rich-content.css';

export type RichAssetLoader = (assetId: string, signal: AbortSignal) => Promise<Blob>;

/** 同一受控 Markdown 渲染路径；不执行 HTML，不向外部图片地址发请求。 */
export function ContentMarkdown({ text }: { text: string }) {
  return <ReactMarkdown remarkPlugins={[remarkGfm, remarkMath]}
    rehypePlugins={[[rehypeKatex, { trust: false, throwOnError: false, maxExpand: 1000 }]]}
    components={{ img: () => <span>〔图片请从受管原件审阅〕</span> }}>
    {text}
  </ReactMarkdown>;
}

const OMML_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/math';

/** 原始 OMML 保持原样；白名单结构只生成 MathML 节点，不插入 XML/HTML。 */
function OmmlFormula({ xml }: { xml: string }) {
  const [result, setResult] = useState<{ xml: string; node: ReactNode } | null>(null);
  useEffect(() => {
    let count = 0;
    try {
      if (xml.length > 200_000 || /<!DOCTYPE|<!ENTITY/i.test(xml)) throw new Error('unsupported');
      const document = new DOMParser().parseFromString(xml, 'application/xml');
      if (document.getElementsByTagName('parsererror').length) throw new Error('invalid');
      const convert = (element: Element, depth = 0): ReactNode => {
        if (++count > 1000 || depth > 32 || element.namespaceURI !== OMML_NS) throw new Error('unsupported');
        const tag = element.localName;
        if (tag.endsWith('Pr')) return null; // 只取结构，格式元数据不执行。
        const children = Array.from(element.children).filter((child) => !child.localName.endsWith('Pr'));
        const group = (name: string) => {
          const child = children.find((candidate) => candidate.localName === name);
          return child ? convert(child, depth + 1) : createElement('mrow');
        };
        if (tag === 't') return createElement('mtext', null, element.textContent ?? '');
        if (['oMath', 'oMathPara', 'r', 'e', 'num', 'den', 'sub', 'sup', 'deg', 'fName', 'lim'].includes(tag)) {
          // MathML 的子节点也用 MathML mrow，避免 HTML span 混入数学布局。
          return createElement('mrow', null, ...children.map((child, index) =>
            createElement('mrow', { key: index }, convert(child, depth + 1))));
        }
        if (tag === 'f') return createElement('mfrac', null, group('num'), group('den'));
        if (tag === 'sSup') return createElement('msup', null, group('e'), group('sup'));
        if (tag === 'sSub') return createElement('msub', null, group('e'), group('sub'));
        if (tag === 'sSubSup') return createElement('msubsup', null, group('e'), group('sub'), group('sup'));
        if (tag === 'rad') return children.some((child) => child.localName === 'deg' && child.textContent?.trim())
          ? createElement('mroot', null, group('e'), group('deg')) : createElement('msqrt', null, group('e'));
        if (tag === 'd') {
          const property = Array.from(element.children).find((child) => child.localName === 'dPr');
          const delimiter = (name: string, fallback: string) => property?.getElementsByTagNameNS(OMML_NS, name)[0]?.getAttributeNS(OMML_NS, 'val') ?? fallback;
          const expressions = children.filter((child) => child.localName === 'e');
          if (expressions.length === 0 || expressions.length !== children.length) throw new Error('unsupported');
          const separator = delimiter('sepChr', '|');
          return createElement('mrow', null,
            createElement('mo', null, delimiter('begChr', '(')),
            ...expressions.flatMap((child, index) => [
              ...(index > 0 ? [createElement('mo', { key: `separator-${index}` }, separator)] : []),
              createElement('mrow', { key: `expression-${index}` }, convert(child, depth + 1)),
            ]),
            createElement('mo', null, delimiter('endChr', ')')));
        }
        if (tag === 'func') return createElement('mrow', null, group('fName'), group('e'));
        if (tag === 'limLow') return createElement('munder', null, group('e'), group('lim'));
        if (tag === 'limUpp') return createElement('mover', null, group('e'), group('lim'));
        // 未支持结构必须明确提示，不把数学结构压成失真的纯文本。
        throw new Error('unsupported');
      };
      setResult({ xml, node: convert(document.documentElement) });
    } catch {
      setResult({ xml, node: null });
    }
  }, [xml]);
  return <div className="rich-formula">
    {result?.xml === xml && result.node ? createElement('math', { display: 'block', 'aria-label': '原始公式' }, result.node)
      : <p role="status">{result?.xml === xml ? '此公式结构暂不能直接显示，请核对下方原始公式 XML。' : '公式读取中…'}</p>}
    <details><summary>查看原始公式 XML</summary><pre>{xml}</pre></details>
  </div>;
}

function ManagedImage({ block, loadAsset, assetScope }: {
  block: Extract<ContentBlock, { kind: 'image' }>;
  loadAsset?: RichAssetLoader;
  assetScope?: string;
}) {
  const [state, setState] = useState<{ key: string; url?: string; error?: string }>({ key: '' });
  const key = `${assetScope ?? ''}|${block.assetId}`;
  useEffect(() => {
    if (!loadAsset) return;
    const controller = new AbortController();
    let alive = true;
    let url: string | undefined;
    loadAsset(block.assetId, controller.signal).then((blob) => {
      if (!alive) return;
      if (!/^image\/(png|jpeg|gif|webp|bmp)$/.test(blob.type)) throw new Error('资产不是可显示的图片');
      url = URL.createObjectURL(blob);
      setState({ key, url });
    }).catch((error: unknown) => {
      if (alive) setState({ key, error: error instanceof Error ? error.message : '读取失败' });
    });
    return () => { alive = false; controller.abort(); if (url) URL.revokeObjectURL(url); };
  }, [block.assetId, loadAsset, key]);
  if (!loadAsset) return <p role="status">图片 {block.assetId}：未提供受控读取入口</p>;
  if (state.key !== key || (!state.url && !state.error)) return <p role="status">图片读取中…</p>;
  if (state.error) return <p role="alert">图片读取失败：{state.error}</p>;
  // 受管字节生成的 object URL；尺寸只用于提示，实际显示受容器限制。
  // eslint-disable-next-line @next/next/no-img-element
  return <img src={state.url} alt={`原文图片 ${block.id}`} width={block.width || undefined} height={block.height || undefined} />;
}

/** 按行优先的起始单元格重建网格，跳过跨行占位，保留合并跨度。 */
export function tableRows(cells: TableCell[], columnCount?: number | null): TableCell[][] {
  const width = Math.max(1, columnCount ?? cells.reduce((sum, cell) => sum + Math.max(1, cell.colSpan), 0));
  const occupied: boolean[][] = [];
  const rows: TableCell[][] = [];
  let row = 0;
  let col = 0;
  for (const cell of cells) {
    while (occupied[row]?.[col] || col >= width) {
      if (col >= width) { row += 1; col = 0; } else col += 1;
    }
    (rows[row] ??= []).push(cell);
    const rowSpan = Math.max(1, cell.rowSpan);
    const colSpan = Math.max(1, cell.colSpan);
    for (let y = row; y < row + rowSpan; y += 1) {
      const taken = (occupied[y] ??= []);
      for (let x = col; x < col + colSpan; x += 1) taken[x] = true;
    }
    col += colSpan;
  }
  // 一整行被 rowspan 占据时仍保留空 tr，后面的起始格才落在正确物理行。
  return Array.from({ length: occupied.length }, (_, index) => rows[index] ?? []);
}

export function RichBlocks({ blocks, loadAsset, assetScope }: {
  blocks: ContentBlock[];
  loadAsset?: RichAssetLoader;
  assetScope?: string;
}) {
  return <div className="rich-content">{blocks.map((block) => <div key={block.id} data-block-id={block.id}>
    {block.kind === 'paragraph' && <ContentMarkdown text={block.text} />}
    {block.kind === 'formula' && (block.latex
      ? <ContentMarkdown text={`$$\n${block.latex}\n$$`} />
      : block.ommlXml ? <OmmlFormula xml={block.ommlXml} /> : <p role="alert">公式内容缺失</p>)}
    {block.kind === 'image' && <ManagedImage block={block} loadAsset={loadAsset} assetScope={assetScope} />}
    {block.kind === 'table' && <div className="rich-table-scroll" tabIndex={0} role="region" aria-label="原文表格">
      <table><tbody>{tableRows(block.cells, block.columnCount).map((row, i) => <tr key={i}>
        {row.map((cell, j) => cell.isHeader
          ? <th key={j} rowSpan={cell.rowSpan} colSpan={cell.colSpan}><ContentMarkdown text={cell.text} /></th>
          : <td key={j} rowSpan={cell.rowSpan} colSpan={cell.colSpan}><ContentMarkdown text={cell.text} /></td>)}
      </tr>)}</tbody></table>
    </div>}
  </div>)}</div>;
}

export function RichContentRenderer({ content, loadAsset, assetScope }: {
  content: RichContentV2;
  loadAsset?: RichAssetLoader;
  assetScope?: string;
}) {
  return <div className="rich-content">
    {content.sharedMaterials.map((material) => <section key={material.id} aria-label="共同材料">
      <h4>共同材料</h4><RichBlocks blocks={material.blocks} loadAsset={loadAsset} assetScope={assetScope} />
    </section>)}
    <RichBlocks blocks={content.stemBlocks} loadAsset={loadAsset} assetScope={assetScope} />
  </div>;
}
