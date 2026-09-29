import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { ChatMessage } from '@/contracts/chat';
import { createMemoryChatRepository } from '@/services/chat-repository';
import { Message } from './Message';
import { conversationProjection } from './model/context-budget';
import { createChatStore } from './model/store';
import type { ChatService } from './model/chat-service';
import type { RagResultV2, ScopeSnapshot, TextbookEvidence } from './model/rag-v2';

vi.mock('./vendor/thinking-orbs', () => ({ ThinkingOrb: () => null }));
afterEach(cleanup);

const scope: ScopeSnapshot = {
  schemaVersion: 2,
  selection: { gradeId: 'g1', subjectId: 's1', editionId: 'e1', documentIds: ['d1'] },
  documents: [{ documentId: 'd1', documentRevisionId: 'r1', metadataRevisionId: 'm1' }],
  embeddingGenerationId: 'gen-1',
  scopeHash: 'a'.repeat(64),
};

const RAW_ONE =
  '空间向量的数量积定义为两向量模长与夹角余弦的乘积。它可以用来求两个向量的夹角，也可以判断两条直线是否垂直。';
const RAW_TWO =
  '两个非零向量垂直的充要条件是它们的数量积等于零。这一结论常用于证明线线垂直与求解空间角问题。';
const RAW_LEGACY =
  '浮力的大小等于物体排开液体所受的重力。\n\n![浮力实验装置图](images/buoyancy.png)\n\n公式 $F = \\rho g V$ 给出定量关系。';

function evidence(over: Partial<TextbookEvidence> = {}): TextbookEvidence {
  return {
    evidenceId: 'ev-1',
    documentRevisionId: 'r1',
    normalizedTextSha256: 'b'.repeat(64),
    charStart: 0,
    charEnd: RAW_ONE.length,
    documentId: 'd1',
    title: '普通高中教科书·数学（A版）选择性必修 第一册',
    editionLabel: '人教A版',
    subjectLabel: '数学',
    chapterPath: ['第一章 空间向量与立体几何', '1.1 空间向量及其运算'],
    text: RAW_ONE,
    originalFileSha256: 'c'.repeat(64),
    locator: {
      kind: 'markdown',
      lineStart: 10,
      lineEnd: 12,
      pageStart: null,
      pageEnd: null,
      blockStart: null,
      blockEnd: null,
    },
    isSuperseded: false,
    readable: { version: 'rag-readable-v1', text: RAW_ONE, removedImageCount: 0 },
    ...over,
  };
}

/** 真实 presenter 输出形状：正文只含编号 + 标题 + 说明 + [n]，不再拼接教材原文摘录 */
const presenterBody =
  '\n\n### 教材知识点\n\n' +
  '1. **空间向量数量积**\n   a·b = |a||b|cosθ，可用于求夹角及判断垂直。[1]\n\n' +
  '2. **垂直判定**\n   对两个非零向量，a·b = 0 时二者垂直。[1][2]\n';

function compactResult(over: Partial<RagResultV2> = {}): RagResultV2 {
  return {
    contractVersion: 2,
    resultId: 'res-1',
    status: 'ok',
    scopeSnapshot: scope,
    points: [
      {
        pointId: 'p1',
        title: '空间向量数量积',
        summary: 'a·b = |a||b|cosθ，可用于求夹角及判断垂直。[1]',
        evidenceIds: ['ev-1'],
      },
      {
        pointId: 'p2',
        title: '垂直判定',
        summary: '对两个非零向量，a·b = 0 时二者垂直。[1][2]',
        evidenceIds: ['ev-1', 'ev-2'],
      },
    ],
    evidence: [
      evidence(),
      evidence({
        evidenceId: 'ev-2',
        text: RAW_TWO,
        readable: { version: 'rag-readable-v1', text: RAW_TWO, removedImageCount: 0 },
      }),
      evidence({
        evidenceId: 'ev-3',
        isSuperseded: true,
        text: '![](images/fig-3.png)\n实验装置示意图如下。',
        readable: { version: 'rag-readable-v1', text: '实验装置示意图如下。', removedImageCount: 1 },
      }),
    ],
    reason: null,
    presentation: { version: 'compact-v1', answerStyle: 'brief', bodyCharCount: 96 },
    ...over,
  };
}

function assistant(over: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: 'a1',
    role: 'assistant',
    content: presenterBody,
    status: 'done',
    modelLabel: '本地教材引擎',
    ...over,
  };
}

const scopeLabelFor = () => '高二 · 数学 · 人教A版';
const noop = () => undefined;

function renderMessage(message: ChatMessage, over: { onCopy?: () => void } = {}) {
  return render(
    <Message
      message={message}
      copied={false}
      onCopy={over.onCopy ?? noop}
      onReuse={noop}
      scopeLabelFor={scopeLabelFor}
    />,
  );
}

/** 复制文本里是否出现超过 chunk 字的原文片段（默认复制不得含整段教材原文） */
function containsRawChunk(copyText: string, raw: string, chunk = 24): boolean {
  for (let index = 0; index + chunk <= raw.length; index += 1) {
    if (copyText.includes(raw.slice(index, index + chunk))) return true;
  }
  return false;
}

const clipboardWrite = vi.fn(async () => undefined);

beforeEach(() => {
  clipboardWrite.mockClear();
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText: clipboardWrite },
    configurable: true,
  });
});

describe('Q1 重复展示回归（真实 presenter 形状）', () => {
  it('知识点只出现一次，教材原文正文默认不出现在消息流里', () => {
    const result = compactResult();
    const { container } = renderMessage(
      assistant({ ragResult: result, ragEvidence: result.evidence }),
    );
    const text = container.textContent ?? '';
    // 知识点标题与说明各只出现一次
    expect(screen.getAllByText('空间向量数量积')).toHaveLength(1);
    expect(screen.getAllByText('对两个非零向量，a·b = 0 时二者垂直。')).toHaveLength(1);
    const occurrences = text.split('a·b = |a||b|cosθ，可用于求夹角及判断垂直。').length - 1;
    expect(occurrences).toBe(1);
    // content（含 Markdown 标题与加粗）完全不参与显示：既没有第二遍知识点，也没有原文摘录
    expect(text).not.toContain('### 教材知识点');
    expect(text).not.toContain('**空间向量数量积**');
    expect(text).not.toContain('教材原文摘录');
    expect(text).not.toContain(RAW_ONE);
    expect(text).not.toContain(RAW_TWO);
    // 教材原文只在折叠的来源面板里，默认不展开
    expect(container.querySelector('.chat-rag-body')).toBeNull();
    expect(screen.getByText(/查看教材依据（3 条）/)).toBeInTheDocument();
  });

  it('[1][2] 编号渲染正确，点击 [n] 展开来源面板并把焦点移到对应条目', async () => {
    const result = compactResult();
    const { container } = renderMessage(
      assistant({ ragResult: result, ragEvidence: result.evidence }),
    );
    expect(screen.getAllByRole('button', { name: '查看教材依据 1' })).toHaveLength(2);
    expect(screen.getAllByRole('button', { name: '查看教材依据 2' })).toHaveLength(1);
    const toggle = screen.getByRole('button', { name: /查看教材依据（3 条）/ });
    expect(toggle).toHaveAttribute('aria-expanded', 'false');
    fireEvent.click(screen.getAllByRole('button', { name: '查看教材依据 2' })[0]!);
    await waitFor(() => expect(toggle).toHaveAttribute('aria-expanded', 'true'));
    const entry = container.querySelector(
      '[data-evidence-id="ev-2"] [data-evidence-entry]',
    ) as HTMLElement;
    expect(entry).toHaveTextContent('展开摘录');
    await waitFor(() => expect(document.activeElement).toBe(entry));
  });
});

describe('来源面板两级展开（PLAN §4.2）', () => {
  it('预览在句边界结束；「展开摘录」显示清洗后摘录；「复制摘录」写入同一文本', async () => {
    const result = compactResult();
    const { container } = renderMessage(
      assistant({ ragResult: result, ragEvidence: result.evidence }),
    );
    fireEvent.click(screen.getByRole('button', { name: /查看教材依据（3 条）/ }));
    const preview = container.querySelector('[data-evidence-id="ev-1"] .chat-rag-preview')!;
    expect(preview.textContent).toBe(RAW_ONE);
    expect(Array.from(preview.textContent ?? '').length).toBeLessThanOrEqual(160);
    // 第二级默认折叠
    expect(container.querySelector('[data-evidence-id="ev-1"] .chat-rag-excerpt')).toBeNull();
    fireEvent.click(
      container.querySelector('[data-evidence-id="ev-1"] [data-evidence-entry]') as HTMLElement,
    );
    const excerpt = container.querySelector('[data-evidence-id="ev-1"] .chat-rag-excerpt')!;
    expect(excerpt.textContent).toContain('空间向量的数量积定义为两向量模长与夹角余弦的乘积。');
    fireEvent.click(screen.getByRole('button', { name: '复制摘录 [1]' }));
    await waitFor(() => expect(clipboardWrite).toHaveBeenCalledWith(RAW_ONE));
  });

  it('长文本预览在完整句处结束，不截半个公式', () => {
    const longText = `${'第一句话很短。第二句话也不长。'.repeat(6)}公式 $$\\frac{a}{b} = \\frac{c}{d}$$ 之后还有正文。`;
    const result = compactResult({
      evidence: [evidence({ readable: { version: 'rag-readable-v1', text: longText, removedImageCount: 0 } })],
    });
    const { container } = renderMessage(assistant({ ragResult: result, ragEvidence: result.evidence }));
    fireEvent.click(screen.getByRole('button', { name: /查看教材依据（1 条）/ }));
    const preview = container.querySelector('.chat-rag-preview')!;
    expect(preview.textContent).toMatch(/。$/);
    expect(preview.textContent).not.toContain('$$');
    expect(Array.from(preview.textContent ?? '').length).toBeLessThanOrEqual(160);
  });

  it('找不到合适短预览时只显示标题与「展开摘录」，不截半句', () => {
    const longSentence = `没有句号的一长串文字${'继续延长'.repeat(40)}`;
    const result = compactResult({
      evidence: [
        evidence({ readable: { version: 'rag-readable-v1', text: longSentence, removedImageCount: 0 } }),
      ],
    });
    const { container } = renderMessage(assistant({ ragResult: result, ragEvidence: result.evidence }));
    fireEvent.click(screen.getByRole('button', { name: /查看教材依据（1 条）/ }));
    expect(container.querySelector('.chat-rag-preview')).toBeNull();
    expect(screen.getByText('普通高中教科书·数学（A版）选择性必修 第一册')).toBeInTheDocument();
    const entry = container.querySelector('[data-evidence-entry]') as HTMLElement;
    expect(entry).toHaveTextContent('展开摘录');
    fireEvent.click(entry);
    expect(container.querySelector('.chat-rag-excerpt')!.textContent).toContain('没有句号的一长串文字');
  });

  it('isSuperseded 提示保留在对应来源上，图片清洗提示在展开区只出现一次', () => {
    const result = compactResult();
    const { container } = renderMessage(
      assistant({ ragResult: result, ragEvidence: result.evidence }),
    );
    // 折叠时不显示任何提示
    expect(container.querySelectorAll('.chat-rag-image-note')).toHaveLength(0);
    expect(screen.queryByText(/教材已更新，此引用为历史修订/)).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /查看教材依据（3 条）/ }));
    expect(screen.getAllByText(/教材已更新，此引用为历史修订/)).toHaveLength(1);
    const notes = container.querySelectorAll('.chat-rag-image-note');
    expect(notes).toHaveLength(1);
    expect(notes[0]!.textContent).toBe('已省略图片，未识别图中内容。');
    // 图片地址不显示、也不加载图片
    expect(container.textContent).not.toContain('images/fig-3.png');
    expect(container.querySelectorAll('img')).toHaveLength(0);
    // 展开该条摘录后提示仍然只有一处
    fireEvent.click(container.querySelector('[data-evidence-id="ev-3"] [data-evidence-entry]')!);
    expect(container.querySelectorAll('.chat-rag-image-note')).toHaveLength(1);
    expect(container.querySelector('[data-evidence-id="ev-3"] .chat-rag-excerpt')!.textContent).toContain(
      '实验装置示意图如下。',
    );
  });
});

describe('默认复制与后续历史（PLAN §4.1 / §4.6 复制与上下文）', () => {
  it('无追问卡：复制按钮走统一投影，复制文本为简短知识点 + 紧凑出处，不含整段原文', () => {
    const result = compactResult();
    const message = assistant({ ragResult: result, ragEvidence: result.evidence });
    const onCopy = vi.fn();
    renderMessage(message, { onCopy });
    fireEvent.click(screen.getByRole('button', { name: '复制回答' }));
    expect(onCopy).toHaveBeenCalledTimes(1);
    // ChatWorkspace 的复制写入 `conversationProjection(message)`（= 同一投影的 historyText）
    const copied = conversationProjection(message);
    expect(copied).toContain('空间向量数量积');
    expect(copied).toContain('出处：[1] 普通高中教科书·数学（A版）选择性必修 第一册 · 人教A版 · 第 10–12 行');
    expect(containsRawChunk(copied, RAW_ONE)).toBe(false);
    expect(containsRawChunk(copied, RAW_TWO)).toBe(false);
  });

  it('有追问卡：追问回答与续写进入投影，教材原文仍不进入', () => {
    const result = compactResult();
    const message = assistant({
      ragResult: result,
      ragEvidence: result.evidence,
      asks: [
        {
          interactionId: 'i1',
          status: 'answered',
          intro: '可继续追问细节，或跳过结束本轮。',
          questions: [
            {
              questionId: 'q1',
              header: '继续追问',
              prompt: '定位是否符合题意？',
              options: [{ label: '细讲解题思路' }],
              multiSelect: false,
              allowFreeText: true,
            },
          ],
          drafts: {},
          answers: [{ questionId: 'q1', labels: [], freeText: '定义域 x>0' }],
          followUp: '据此给出的最终解释。',
        },
      ],
    });
    const projection = conversationProjection(message);
    expect(projection).toContain('定义域 x>0');
    expect(projection).toContain('据此给出的最终解释。');
    expect(projection).toContain('空间向量数量积');
    expect(containsRawChunk(projection, RAW_ONE)).toBe(false);
    expect(containsRawChunk(projection, RAW_TWO)).toBe(false);
  });
});

describe('历史兼容六行（PLAN §4.3）', () => {
  it('旧 v2 首答即时用新投影：长点进「展开旧答」，不伪造摘要', () => {
    const legacy = compactResult({
      presentation: undefined,
      points: [
        { pointId: 'p1', title: '空间向量数量积', summary: 'a·b = |a||b|cosθ。[1]', evidenceIds: ['ev-1'] },
        { pointId: 'p2', title: '超长旧点', summary: '旧答说明。'.repeat(40), evidenceIds: ['ev-1'] },
      ],
    });
    const { container } = renderMessage(assistant({ ragResult: legacy, ragEvidence: legacy.evidence }));
    expect(screen.getByText('超长旧点')).toBeInTheDocument();
    // 装不下预算的点只展示标题（不伪造摘要）：可见的紧凑说明只剩第一个点
    expect(container.querySelectorAll('.chat-rag-point-summary')).toHaveLength(1);
    const legacyBlock = container.querySelector('.chat-rag-legacy-answer') as HTMLDetailsElement;
    expect(legacyBlock.querySelector('summary')!.textContent).toBe('展开旧答');
    expect(legacyBlock.open).toBe(false);
    fireEvent.click(legacyBlock.querySelector('summary')!);
    expect(legacyBlock.open).toBe(true);
    expect(legacyBlock.textContent).toContain('旧答说明。');
  });

  it('旧 v2 投影不改库（假仓储断言无写入，原记录保持旧正文）', async () => {
    const legacy = compactResult({ presentation: undefined });
    const repo = createMemoryChatRepository();
    await repo.save(
      {
        schemaVersion: 1,
        revision: 1,
        id: 'legacy-v2',
        title: '旧 v2 会话',
        createdAt: '2026-09-01T00:00:00.000Z',
        updatedAt: '2026-09-01T00:05:00.000Z',
        messages: [
          { id: 'u1', role: 'user', content: '旧题', status: 'done' },
          assistant({ id: 'a1', ragResult: legacy, ragEvidence: legacy.evidence }),
        ],
      } as never,
      0,
    );
    const service: ChatService = { kind: 'real', run: vi.fn() };
    const store = createChatStore({ repository: repo, service });
    await store.getState().init();
    const saveSpy = vi.spyOn(repo, 'save');
    const message = store.getState().messages[1]!;
    renderMessage(message);
    expect(screen.getAllByText('空间向量数量积').length).toBeGreaterThan(0);
    expect(saveSpy).not.toHaveBeenCalled();
    const stored = await repo.load('legacy-v2');
    expect(JSON.stringify(stored)).toContain('### 教材知识点');
    store.getState().dispose();
  });

  it('无结构化结果的旧 v1 保持原正文（不靠标题猜删）', () => {
    const legacyBody =
      '\n\n### 教材知识点\n\n1. 旧版知识点\n\n### 教材原文摘录\n\n> 旧原文第一段\n\n旧 v1 讲解正文。';
    const { container } = renderMessage(assistant({ content: legacyBody }));
    const text = container.textContent ?? '';
    expect(text).toContain('旧版知识点');
    expect(text).toContain('教材原文摘录');
    expect(text).toContain('旧原文第一段');
    expect(container.querySelector('.chat-rag-answer')).toBeNull();
  });

  it('只有孤立 ragEvidence：附加折叠来源，正文不被推断改写', () => {
    const { container } = renderMessage(
      assistant({ content: '旧记录正文。', ragEvidence: [evidence()] }),
    );
    expect(container.querySelector('.chat-rag-answer')).toBeNull();
    expect(screen.getByText('旧记录正文。')).toBeInTheDocument();
    expect(container.querySelector('.chat-rag-body')).toBeNull();
    fireEvent.click(screen.getByRole('button', { name: /查看教材依据（1 条）/ }));
    expect(container.querySelector('.chat-rag-body')!.textContent).toContain('普通高中教科书·数学（A版）选择性必修 第一册');
  });

  it('普通回答与详解回答保持原正文，不做任何截断', () => {
    const long = `${'这是一段很长的普通回答，需要完整保留。'.repeat(120)}结尾标记`;
    const plain = renderMessage(assistant({ content: long }));
    expect(plain.container.textContent).toContain('结尾标记');
    cleanup();
    const explain = renderMessage(
      assistant({
        content: long,
        ragExplain: {
          turnId: 't1',
          modelProfileId: 'p1',
          modelLabel: '测试模型',
          followUp: '细讲',
          status: 'done',
          originalQuestion: 'q',
          scopeSnapshot: scope,
          evidenceRefs: [],
          history: [],
          maxOutputTokens: null,
        },
      }),
    );
    expect(explain.container.textContent).toContain('结尾标记');
    expect(explain.container.querySelector('.chat-rag-answer')).toBeNull();
  });

  it('readable 缺失：降级为封存原文的本地清洗结果，并明确标注未清洗历史原文', () => {
    const legacyEvidence = evidence({
      evidenceId: 'ev-old',
      text: RAW_LEGACY,
      readable: undefined,
      charEnd: RAW_LEGACY.length,
    });
    const legacy = compactResult({
      presentation: undefined,
      points: [{ pointId: 'p1', title: '浮力', summary: '看实验。[1]', evidenceIds: ['ev-old'] }],
      evidence: [legacyEvidence],
    });
    const { container } = renderMessage(assistant({ ragResult: legacy, ragEvidence: legacy.evidence }));
    fireEvent.click(screen.getByRole('button', { name: /查看教材依据（1 条）/ }));
    fireEvent.click(container.querySelector('[data-evidence-entry]')!);
    const excerpt = container.querySelector('.chat-rag-excerpt')!;
    expect(excerpt.textContent).toContain('未清洗历史原文');
    expect(excerpt.textContent).toContain('浮力实验装置图');
    expect(excerpt.textContent).toContain('定量关系');
    expect(excerpt.querySelector('.katex')).not.toBeNull();
    expect(excerpt.textContent).not.toContain('images/buoyancy.png');
    expect(container.querySelectorAll('img')).toHaveLength(0);
  });
});

describe('图片策略（不发起图片请求）', () => {
  it('RAG 渲染省略图片且不请求网络；普通聊天的既有文字占位行为不变', () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
    const legacyEvidence = evidence({
      evidenceId: 'ev-old',
      text: RAW_LEGACY,
      readable: undefined,
      charEnd: RAW_LEGACY.length,
    });
    const legacy = compactResult({
      presentation: undefined,
      points: [{ pointId: 'p1', title: '浮力', summary: '看实验。[1]', evidenceIds: ['ev-old'] }],
      evidence: [legacyEvidence],
    });
    const { container } = renderMessage(assistant({ ragResult: legacy, ragEvidence: legacy.evidence }));
    fireEvent.click(screen.getByRole('button', { name: /查看教材依据（1 条）/ }));
    fireEvent.click(container.querySelector('[data-evidence-entry]')!);
    expect(container.querySelectorAll('img')).toHaveLength(0);
    expect(fetchSpy).not.toHaveBeenCalled();
    cleanup();
    // 普通聊天：仍按既有行为显示文字占位（同样不请求图片）
    const plain = renderMessage(assistant({ content: '普通回答 ![示意图](images/plain.png) 结尾' }));
    expect(plain.container.querySelectorAll('img')).toHaveLength(0);
    expect(plain.container.textContent).toContain('[图片：示意图]');
    expect(fetchSpy).not.toHaveBeenCalled();
    vi.unstubAllGlobals();
  });
});
