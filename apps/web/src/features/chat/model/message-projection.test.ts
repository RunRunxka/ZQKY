import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { ChatMessage } from '@/contracts/chat';
import type { RagResultV2, TextbookEvidence } from './rag-v2';
import { isRagResultV2 } from './rag-v2';
import {
  buildSourcePreview,
  mapResultNotice,
  projectCompactRag,
  projectMessage,
  renderCompactText,
  selectCompactDisplayPoints,
  splitCitationMarkers,
  type CompactSource,
} from './message-projection';

const scope = {
  schemaVersion: 2 as const,
  selection: { gradeId: 'g1', subjectId: 's1', editionId: 'e1', documentIds: ['d1'] },
  documents: [{ documentId: 'd1', documentRevisionId: 'r1', metadataRevisionId: 'm1' }],
  embeddingGenerationId: 'gen-1',
  scopeHash: 'a'.repeat(64),
};

const RAW_ONE =
  '空间向量的数量积定义为两向量模长与夹角余弦的乘积。空间向量的数量积定义为两向量模长与夹角余弦的乘积。';
const RAW_TWO = '两个非零向量垂直的充要条件是数量积等于零，这一结论可用于判定垂直关系与求解夹角。';

function evidence(over: Partial<TextbookEvidence> = {}): TextbookEvidence {
  return {
    evidenceId: 'ev-1',
    documentRevisionId: 'r1',
    normalizedTextSha256: 'b'.repeat(64),
    charStart: 0,
    charEnd: 100,
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
    evidence: [evidence(), evidence({ evidenceId: 'ev-2', text: RAW_TWO, readable: { version: 'rag-readable-v1', text: RAW_TWO, removedImageCount: 0 } })],
    reason: null,
    presentation: { version: 'compact-v1', answerStyle: 'brief', bodyCharCount: 96 },
    ...over,
  };
}

function assistant(over: Partial<ChatMessage> = {}): ChatMessage {
  return {
    id: 'a1',
    role: 'assistant',
    content: '### 教材知识点\n\n1. **空间向量数量积**\n   a·b = |a||b|cosθ，可用于求夹角及判断垂直。[1]\n',
    status: 'done',
    modelLabel: '本地教材引擎',
    ...over,
  };
}

beforeEach(() => {
  vi.restoreAllMocks();
});

describe('单一消息投影（PLAN §4.1）', () => {
  it('结构化首答走紧凑视图：只含知识点与紧凑出处，不含教材原文', () => {
    const message = assistant({ ragResult: compactResult(), ragEvidence: compactResult().evidence });
    const view = projectMessage(message);
    expect(view.kind).toBe('rag');
    if (view.kind !== 'rag') return;
    expect(view.points).toHaveLength(2);
    expect(view.points[0]!.citations).toEqual([1]);
    expect(view.points[1]!.citations).toEqual([1, 2]);
    expect(view.sources.map((item) => item.index)).toEqual([1, 2]);
    expect(view.copyText).toContain('1. 空间向量数量积');
    expect(view.copyText).toContain('a·b = |a||b|cosθ，可用于求夹角及判断垂直。[1]');
    expect(view.copyText).toContain('出处：[1] 普通高中教科书·数学（A版）选择性必修 第一册 · 人教A版 · 第 10–12 行');
    // 默认复制 / 后续历史都不含封存原文
    expect(view.copyText).not.toContain(RAW_ONE);
    expect(view.copyText).not.toContain(RAW_TWO);
    expect(view.historyText).toBe(view.copyText);
    expect(view.sourcePanelInitiallyExpanded).toBe(false);
    // partial 结果：复制与历史都带上状态说明，不把部分结果当完整回答
    const partial = projectCompactRag(compactResult({ status: 'partial', reasonCode: 'SUMMARY_PARTIAL' }));
    expect(partial.copyText).toContain('不是完整回答');
  });

  it('普通回答、详解回答、旧 v1 保持原正文且不截断', () => {
    const long = `${'这是一段很长的普通回答。'.repeat(200)}结尾`;
    const plain = projectMessage(assistant({ content: long }));
    expect(plain).toMatchObject({ kind: 'markdown', markdown: long, copyText: long, historyText: long });
    const explain = projectMessage(
      assistant({ content: long, ragExplain: { turnId: 't', modelProfileId: 'p', modelLabel: 'm', followUp: '细讲', status: 'done', originalQuestion: 'q', scopeSnapshot: scope, evidenceRefs: [], history: [], maxOutputTokens: null } }),
    );
    expect(explain.kind).toBe('markdown');
    expect(explain.historyText).toBe(long);
    const legacyV1 = projectMessage(assistant({ content: '旧 v1 正文（含教材定位与讲解）' }));
    expect(legacyV1.kind).toBe('markdown');
    expect(legacyV1.copyText).toBe('旧 v1 正文（含教材定位与讲解）');
  });

  it('旧 v2 首答（无 presentation）：装入预算的点展示，其余放「展开旧答」且不伪造摘要', () => {
    const legacy = compactResult({ presentation: undefined, points: [
      { pointId: 'p1', title: '短点', summary: '短说明。[1]', evidenceIds: ['ev-1'] },
      { pointId: 'p2', title: '长点', summary: '很长的旧答说明。'.repeat(20), evidenceIds: ['ev-1'] },
    ] });
    const view = projectCompactRag(legacy);
    expect(view.compactPresentation).toBe(false);
    expect(view.points[0]).toMatchObject({ summary: '短说明。[1]', overflowSummary: null });
    expect(view.points[1]!.summary).toBe('');
    expect(view.points[1]!.overflowSummary).toBe('很长的旧答说明。'.repeat(20));
  });

  it('单个旧知识点无法装入预算时只保留标题（不伪造新摘要）', () => {
    const legacy = compactResult({ presentation: undefined, points: [
      { pointId: 'p1', title: '超长旧点', summary: '旧说明。'.repeat(60), evidenceIds: [] },
    ] });
    const view = projectCompactRag(legacy);
    expect(view.points[0]!.summary).toBe('');
    expect(view.points[0]!.overflowSummary).toBe('旧说明。'.repeat(60));
  });

  it('旧 v2 与旧 v1 走投影只读，不写入任何仓储字段（投影是纯函数）', () => {
    const legacyV2 = assistant({ ragResult: compactResult({ presentation: undefined }) });
    const legacyV1 = assistant({ content: '旧 v1 正文', rag: { sessionId: 's', turnId: 't', question: 'q', lastEventId: 3, status: 'terminal' } });
    const before = JSON.stringify([legacyV2, legacyV1]);
    projectMessage(legacyV2);
    projectMessage(legacyV1);
    expect(JSON.stringify([legacyV2, legacyV1])).toBe(before);
    expect(legacyV2.content).toBe(assistant().content);
  });

  it('readable 缺失：展示降级为本地清洗结果（隐藏图片语法），并标记未清洗历史原文', () => {
    const legacy = compactResult({
      evidence: [
        evidence({
          readable: undefined,
          text: '浮力实验说明。\n\n![浮力实验装置图](images/buoyancy.png)\n\n公式 $F = \\rho g V$ 成立。',
        }),
      ],
      points: [{ pointId: 'p1', title: '浮力', summary: '看实验。[1]', evidenceIds: ['ev-1'] }],
    });
    const view = projectCompactRag(legacy);
    const source = view.sources[0]!;
    expect(source.legacyRaw).toBe(true);
    expect(source.readableText).toContain('浮力实验装置图');
    expect(source.readableText).not.toContain('images/buoyancy.png');
    expect(source.readableText).toContain('$F = \\rho g V$');
    expect(source.removedImageCount).toBe(1);
  });
});

describe('结果说明映射（不把 partial 说成成功）', () => {
  it('reasonCode 映射更具体提示，ok 不追加尾注', () => {
    expect(mapResultNotice(compactResult())).toBeNull();
    expect(mapResultNotice(compactResult({ status: 'partial', reasonCode: 'EVIDENCE_UNIT_TOO_LARGE' }))).toContain(
      '有教材命中，但其内容过长无法完整引用',
    );
    expect(mapResultNotice(compactResult({ status: 'partial', reasonCode: 'SUMMARY_PARTIAL' }))).toContain(
      '不是完整回答',
    );
    const noEvidence = mapResultNotice(compactResult({ status: 'no_evidence', reasonCode: 'NO_MATCH' }));
    expect(noEvidence).toContain('没有找到足够依据');
    expect(noEvidence).not.toContain('已定位');
    expect(mapResultNotice(compactResult({ status: 'uncertain', reasonCode: 'EVIDENCE_TEXT_EMPTY' }))).toContain(
      '清洗后没有可引用的正文',
    );
  });

  it('无 reasonCode 的旧结果按状态给可读说明', () => {
    expect(mapResultNotice(compactResult({ status: 'partial', reason: '本地概括未完成。' }))).toContain(
      '未完整完成',
    );
    expect(mapResultNotice(compactResult({ status: 'uncertain' }))).toContain('证据不确定');
  });
});

describe('来源预览（PLAN §4.2）', () => {
  it('在完整句边界结束，不截半个公式', () => {
    const text = `第一句话很短。第二句话也不长。${'第三句接着展开叙述。'.repeat(20)}`;
    const preview = buildSourcePreview(text, 20);
    // 上限内最后一个完整句边界（20 字上限 → 到 16 字处结束，不切进第三句）
    expect(preview).toBe('第一句话很短。第二句话也不长。');
    expect(Array.from(preview ?? '').length).toBeLessThanOrEqual(20);
  });

  it('公式跨越上限时不在公式中间截断（整体前移到上一个句边界）', () => {
    const formula = `$\\frac{a}{b} = \\frac{\\sin\\alpha}{\\cos\\beta}$`;
    const preview = buildSourcePreview(`公式说明到这里。${formula}后面还有更多说明文字。`, 20);
    expect(preview).toBe('公式说明到这里。');
  });

  it('找不到合适短预览时返回 null（只显示标题与展开摘录）', () => {
    expect(buildSourcePreview('没有句号的一长串文字'.repeat(30), 40)).toBeNull();
    expect(buildSourcePreview('   ', 40)).toBeNull();
  });

  it('短文本整体作为预览（不截断）', () => {
    expect(buildSourcePreview('短摘录。', 160)).toBe('短摘录。');
  });
});

describe('引用编号切分', () => {
  it('只把已存在的编号当引用，公式内字面量不切', () => {
    expect(splitCitationMarkers('说明[1][2]。', new Set([1, 2]))).toEqual([
      { kind: 'text', text: '说明' },
      { kind: 'citation', text: '[1]', index: 1 },
      { kind: 'citation', text: '[2]', index: 2 },
      { kind: 'text', text: '。' },
    ]);
    expect(splitCitationMarkers('说明[9]。', new Set([1]))).toEqual([{ kind: 'text', text: '说明[9]。' }]);
    expect(splitCitationMarkers('公式 $x^{[1]}$ 结束', new Set([1]))).toEqual([
      { kind: 'text', text: '公式 $x^{[1]}$ 结束' },
    ]);
  });
});

describe('运行时校验兼容新字段', () => {
  it('旧载荷（无 presentation/readable）仍可用，新载荷被接受', () => {
    const legacy = compactResult({ presentation: undefined, evidence: [evidence({ readable: undefined })] });
    expect(isRagResultV2(legacy)).toBe(true);
    expect(isRagResultV2(compactResult())).toBe(true);
  });

  it('readable 结构损坏时整条结果拒绝（不静默套用新规则）', () => {
    const broken = { ...compactResult(), evidence: [{ ...evidence(), readable: { version: 'rag-readable-v2', text: 1 } }] };
    expect(isRagResultV2(broken)).toBe(false);
  });

  it('未知 presentation 版本如实保留（不按新格式套用）', () => {
    const unknown = { ...compactResult(), presentation: { version: 'compact-v9' } };
    expect(isRagResultV2(unknown)).toBe(true);
    const view = projectCompactRag(unknown as RagResultV2);
    expect(view.compactPresentation).toBe(false);
  });
});

describe('紧凑文本渲染', () => {
  it('无知识点时回退到说明文案（失败不伪装成功）', () => {
    const sources: CompactSource[] = [];
    expect(renderCompactText([], sources, '没有找到足够依据。')).toBe('没有找到足够依据。');
  });

  it('预算选择遵循 3 点 / 90 字 / 250 字上限（仅旧结果）', () => {
    const points = Array.from({ length: 5 }, (_, index) => ({
      pointId: `p${index}`,
      title: `点${index}`,
      summary: '说'.repeat(20),
      evidenceIds: [],
    }));
    const selected = selectCompactDisplayPoints(points, true, new Map());
    expect(selected).toHaveLength(5); // 新结果由后端保证预算，前端不再裁剪
    const legacy = selectCompactDisplayPoints(points, false, new Map());
    expect(legacy.filter((point) => point.summary).length).toBeLessThanOrEqual(3);
    expect(legacy.filter((point) => point.overflowSummary).length).toBeGreaterThan(0);
  });
});
