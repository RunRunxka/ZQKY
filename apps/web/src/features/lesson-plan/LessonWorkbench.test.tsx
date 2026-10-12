/**
 * 教案工作台集成测试（R7-FE）：三栏交互、模块增删实时进预览、第 3 页起分页、
 * 字体切换、流式候选 → 采用才进草稿、导出触发、本地草稿与坏稿保护。
 *
 * 依赖注入：`api` / `uploadSource` / `generateServices` 全部走替身，不触网、不写真实数据。
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { LessonWorkbench } from './LessonWorkbench';
import { LOCAL_DRAFT_KEY } from './model/draft-storage';
import type { LessonPlansApi } from '@/services/lesson-plans-api';
import type { LessonStreamInput, LessonStreamHandlers } from '@/services/lesson-stream';
import type { LessonPlanData, LessonView } from '@/contracts/lesson-plans';
import { emptyLessonData } from './model/lesson-data';
import { DEFAULT_LESSON_STYLE } from './model/modules';

function viewOf(data: LessonPlanData, revision = 3): LessonView {
  return {
    lessonPlanId: 'plan-1',
    revision,
    currentRevisionId: 'rev-1',
    currentRevision: {
      lessonPlanId: 'plan-1',
      revisionId: 'rev-1',
      version: revision,
      data,
    },
  };
}

function fakeApi(overrides: Partial<LessonPlansApi> = {}): LessonPlansApi {
  return {
    listLessonPlans: vi.fn(async () => ({ items: [], total: 0, offset: 0, limit: 0 })),
    getLessonPlan: vi.fn(async () => viewOf(emptyLessonData())),
    createLessonPlan: vi.fn(async () => viewOf(emptyLessonData(), 1)),
    patchLessonPlanDraft: vi.fn(async () => viewOf(emptyLessonData(), 4)),
    exportLessonPlan: vi.fn(async () => ({ artifact: { artifactId: 'art-1', fileName: '荷塘月色.docx' } })),
    downloadLessonExport: vi.fn(async () => ({ blob: new Blob(['docx']), fileName: '荷塘月色.docx' })),
    uploadLessonSource: vi.fn(async (file: File) => ({ assetRef: 'asset-1', fileName: file.name })),
    ...overrides,
  } as LessonPlansApi;
}

/** 生成流替身：按归档协议分发事件（不触网）。 */
function fakeStream(script: Array<{ module: string; label: string; text: string; error?: string }>) {
  return vi.fn(async (_input: LessonStreamInput, handlers: LessonStreamHandlers) => {
    for (const step of script) {
      handlers.onModuleStart?.(step.module, step.label);
      if (step.error) handlers.onModuleError?.(step.module, step.error);
      else {
        handlers.onModuleDelta?.(step.module, step.text);
        handlers.onModuleDone?.(step.module);
      }
    }
    handlers.onEnd?.('stop');
  });
}

function generateServices(stream = fakeStream([])) {
  return {
    streamModules: stream,
    loadCatalog: vi.fn(async () => ({
      revision: 1,
      defaultChatProfileId: 'profile-1',
      connections: [],
      profiles: [],
    })) as never,
    listPoints: vi.fn(async () => ({ items: [{ id: 'kp-1', name: '荷塘月色' }], total: 1, offset: 0, limit: 50 })) as never,
    listRuns: vi.fn(async () => ({ items: [], total: 0, offset: 0, limit: 20 })) as never,
    uploadSource: vi.fn(async (file: File) => ({ assetRef: 'asset-1', fileName: file.name })),
  };
}

function renderWorkbench(options: {
  api?: LessonPlansApi;
  stream?: ReturnType<typeof fakeStream>;
} = {}) {
  const api = options.api ?? fakeApi();
  const stream = options.stream ?? fakeStream([]);
  const utils = render(
    <LessonWorkbench api={api} generateServices={generateServices(stream)} />,
  );
  return { api, stream, ...utils };
}

/** jsdom 未实现 dialog 的 showModal/close（公共 Modal 依赖），这里只补最小实现。 */
beforeAll(() => {
  if (typeof HTMLDialogElement !== 'undefined' && !HTMLDialogElement.prototype.showModal) {
    HTMLDialogElement.prototype.showModal = function showModal(this: HTMLDialogElement) {
      this.setAttribute('open', '');
    };
    HTMLDialogElement.prototype.close = function close(this: HTMLDialogElement) {
      this.removeAttribute('open');
    };
  }
});

beforeEach(() => {
  window.localStorage.clear();
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  window.localStorage.clear();
});

describe('教案工作台 · 三栏与预览', () => {
  it('默认渲染三栏、七模块列表与第 3 页起的预览提示', async () => {
    renderWorkbench();
    expect(screen.getByTestId('lw-col-left')).toBeTruthy();
    expect(screen.getByTestId('lw-col-mid')).toBeTruthy();
    expect(screen.getByTestId('lw-col-right')).toBeTruthy();
    expect(screen.getByTestId('lw-module-list').querySelectorAll('li')).toHaveLength(7);
    expect(screen.getByTestId('lw-preview-hint').textContent).toContain('封面与目录将在导出时自动补齐');

    const paper = await screen.findByTestId('lw-paper-3');
    expect(within(paper).getByTestId('lw-block-basic.band').textContent).toContain('一、基本信息');
    expect(within(paper).getByTestId('lw-block-analysis.band').textContent).toContain('二、教学分析');
    expect(screen.getByTestId('lw-page-end-3').textContent).toContain('第 3 页结束');
    expect(screen.queryByTestId('lw-paper-1')).toBeNull();
    expect(screen.queryByTestId('lw-paper-2')).toBeNull();
  });

  it('添加自定义模块：预览立即出现新表格（标题 + 正文）', async () => {
    renderWorkbench();
    fireEvent.change(screen.getByTestId('lw-module-add-input'), {
      target: { value: '课前测试安排' },
    });
    fireEvent.click(screen.getByTestId('lw-module-add-button'));

    const bandId = screen
      .getAllByTestId(/^lw-block-custom-.*\.band$/)
      .map((node) => node.getAttribute('data-testid'))[0];
    expect(bandId).toBeTruthy();
    expect(screen.getByTestId(bandId!).textContent).toContain('课前测试安排');

    const body = screen.getByTestId(bandId!.replace(/\.band$/, '.body'));
    fireEvent.change(screen.getByTestId('lw-field-lw-custom-body'), {
      target: { value: '10 分钟小测。' },
    });
    expect(body.textContent).toContain('10 分钟小测。');
  });

  it('隐藏与删除：隐藏模块从预览消失，删除的自定义模块可还原', () => {
    renderWorkbench();
    fireEvent.click(screen.getByTestId('lw-module-hide-analysis'));
    expect(screen.queryByTestId('lw-block-analysis.band')).toBeNull();

    fireEvent.change(screen.getByTestId('lw-module-add-input'), { target: { value: '补充说明' } });
    fireEvent.click(screen.getByTestId('lw-module-add-button'));
    const custom = screen
      .getAllByTestId(/^lw-module-item-custom-/)
      .map((node) => node.getAttribute('data-testid')!)[0];
    const customId = custom.replace('lw-module-item-', '');
    fireEvent.click(screen.getByTestId(`lw-module-remove-${customId}`));
    expect(screen.queryByTestId(`lw-module-item-${customId}`)).toBeNull();
    fireEvent.click(screen.getByTestId(`lw-module-restore-${customId}`));
    expect(screen.getByTestId(`lw-module-item-${customId}`)).toBeTruthy();
  });

  it('上移/下移改变预览顺序（模块顺序即内容流顺序）', () => {
    renderWorkbench();
    fireEvent.click(screen.getByTestId('lw-module-down-basic'));
    const bands = screen
      .getAllByTestId(/^lw-block-.*\.band$|^lw-block-reflection$/)
      .map((node) => node.getAttribute('data-testid'));
    expect(bands[0]).toBe('lw-block-analysis.band');
  });

  it('字体切换：预览纸张的字体族随选择变化（默认阿里巴巴普惠体）', () => {
    const { container } = renderWorkbench();
    const paper = container.querySelector('.lw-paper') as HTMLElement;
    expect(paper.style.getPropertyValue('--lp-font')).toContain('Alibaba PuHuiTi');
    fireEvent.change(screen.getByTestId('lw-font-select'), { target: { value: 'source-han-serif' } });
    expect(paper.style.getPropertyValue('--lp-font')).toContain('Source Han Serif SC');
  });

  it('排版与间距：滑杆、行高、页边距实时写进纸张 CSS 变量', () => {
    const { container } = renderWorkbench();
    const paper = container.querySelector('.lw-paper') as HTMLElement;
    fireEvent.change(screen.getByTestId('lw-size-base'), { target: { value: '17' } });
    fireEvent.change(screen.getByTestId('lw-line-height'), { target: { value: '1.9' } });
    fireEvent.change(screen.getByTestId('lw-page-margin'), { target: { value: '64' } });
    expect(paper.style.getPropertyValue('--lp-base')).toBe('17px');
    expect(paper.style.getPropertyValue('--lp-line')).toBe('1.9');
    expect(paper.style.getPropertyValue('--lp-page-margin')).toBe('64px');
  });

  it('三栏分栏：拖拽分隔条（键盘 ←/→）改变列宽百分比并被夹取在限内', () => {
    const { container } = renderWorkbench();
    const columns = container.querySelector('.lw-columns') as HTMLElement;
    const splitter = screen.getByTestId('lw-splitter-left');
    expect(splitter.getAttribute('role')).toBe('separator');
    expect(columns.style.getPropertyValue('--lw-left')).toBe('20%');
    fireEvent.keyDown(splitter, { key: 'ArrowRight' });
    expect(columns.style.getPropertyValue('--lw-left')).toBe('21%');
    fireEvent.keyDown(splitter, { key: 'ArrowLeft' });
    fireEvent.keyDown(splitter, { key: 'ArrowLeft' });
    expect(columns.style.getPropertyValue('--lw-left')).toBe('19%');
  });

  it('中栏模块表单：教学设计内容写入草稿并出现在预览（表格行）', async () => {
    renderWorkbench();
    await screen.findByTestId('lw-paper-3');
    fireEvent.click(screen.getByTestId('lw-module-select-objectives'));
    fireEvent.change(screen.getByTestId('lw-field-lw-objectives-knowledge'), {
      target: { value: '梳理游踪' },
    });
    const row = await screen.findByTestId('lw-block-objectives.knowledge');
    expect(row.textContent).toContain('梳理游踪');
    // 预览中教学目标三行 + 合并标签
    expect(screen.getByTestId('lw-block-objectives.ability')).toBeTruthy();
    expect(screen.getByTestId('lw-block-objectives.ideological')).toBeTruthy();
  });
});

describe('教案工作台 · 生成流（候选 → 采用）', () => {
  it('流式文本逐格填入预览并标记候选；未采用时草稿不变', async () => {
    const stream = fakeStream([
      { module: 'analysis', label: '教学分析', text: '【学情分析】学生对通感句不熟悉。\n【教材分析】写景散文单元。' },
    ]);
    renderWorkbench({ stream });
    fireEvent.click(screen.getByTestId('lw-generate-button'));

    await waitFor(() => expect(stream).toHaveBeenCalledTimes(1));
    const candidates = await screen.findAllByTestId('lw-block-analysis.learning');
    expect(candidates.at(-1)!.getAttribute('data-candidate')).toBe('true');
    expect(candidates.at(-1)!.textContent).toContain('学生对通感句不熟悉。');

    // 草稿（表单字段）在采用前保持为空
    fireEvent.click(screen.getByTestId('lw-module-select-analysis'));
    expect((screen.getByTestId('lw-field-lw-analysis-learning') as HTMLTextAreaElement).value).toBe('');

    fireEvent.click(screen.getByTestId('lw-candidate-adopt-all'));
    await waitFor(() =>
      expect((screen.getByTestId('lw-field-lw-analysis-learning') as HTMLTextAreaElement).value).toContain(
        '学生对通感句不熟悉。',
      ),
    );
    expect(screen.queryByTestId('lw-candidate-analysis')).toBeNull();
  });

  it('中断：保留已收到的内容为候选，不写草稿', async () => {
    const stream = vi.fn(async (_input: LessonStreamInput, handlers: LessonStreamHandlers) => {
      handlers.onModuleStart?.('reflection', '教学反思');
      handlers.onModuleDelta?.('reflection', '目标基本达成。');
      throw new DOMException('aborted', 'AbortError');
    });
    renderWorkbench({ stream: stream as never });
    fireEvent.click(screen.getByTestId('lw-generate-button'));
    await waitFor(() => expect(stream).toHaveBeenCalled());
    expect(await screen.findByTestId('lw-candidate-reflection')).toBeTruthy();
    expect(screen.getByTestId('lw-generate-panel').textContent).toContain('已中断生成');
  });

  it('模型目录缺少默认档位时如实报错，不发起流', async () => {
    const stream = fakeStream([]);
    render(
      <LessonWorkbench
        api={fakeApi()}
        generateServices={{
          ...generateServices(stream),
          loadCatalog: vi.fn(async () => ({ revision: 1, defaultChatProfileId: null, connections: [], profiles: [] })) as never,
        }}
      />,
    );
    fireEvent.click(screen.getByTestId('lw-generate-button'));
    await waitFor(() =>
      expect(screen.getByTestId('lw-generate-panel').textContent).toContain('未配置可用的对话模型档位'),
    );
    expect(stream).not.toHaveBeenCalled();
  });

  it('知识点与学情报告读取失败时显示原因，不假装空列表', async () => {
    render(
      <LessonWorkbench
        api={fakeApi()}
        generateServices={{
          ...generateServices(),
          listPoints: vi.fn(async () => {
            throw new Error('后端端点尚未上线');
          }) as never,
          listRuns: vi.fn(async () => {
            throw new Error('学情服务未装配');
          }) as never,
        }}
      />,
    );
    await waitFor(() => expect(screen.getByTestId('lw-kp-error').textContent).toContain('后端端点尚未上线'));
    fireEvent.click(screen.getByTestId('lw-source-run'));
    await waitFor(() => expect(screen.getByTestId('lw-analysis-run-error').textContent).toContain('学情服务未装配'));
  });
});

describe('教案工作台 · 导出与云端', () => {
  it('导出：无云端 id 时先创建再导出 + 下载', async () => {
    const createObjectURL = vi.fn(() => 'blob:lesson');
    vi.stubGlobal('URL', Object.assign(URL, { createObjectURL, revokeObjectURL: vi.fn() }));
    const api = fakeApi();
    renderWorkbench({ api });
    fireEvent.click(screen.getByTestId('lw-export-button'));
    await waitFor(() => expect(api.exportLessonPlan).toHaveBeenCalledWith('plan-1', expect.anything()));
    expect(api.createLessonPlan).toHaveBeenCalledTimes(1);
    expect(api.downloadLessonExport).toHaveBeenCalledWith('art-1');
    expect(createObjectURL).toHaveBeenCalled();
    await waitFor(() => expect(screen.getByTestId('lw-notice-export').textContent).toContain('荷塘月色.docx'));
  });

  it('导出失败如实提示（不宣称已导出）', async () => {
    const api = fakeApi({
      exportLessonPlan: vi.fn(async () => {
        throw new Error('后端组装未就绪');
      }),
    });
    renderWorkbench({ api });
    fireEvent.click(screen.getByTestId('lw-export-button'));
    await waitFor(() => expect(screen.getByTestId('lw-notice-export').textContent).toContain('导出失败'));
    expect(screen.getByTestId('lw-notice-export').textContent).toContain('后端组装未就绪');
  });

  it('云端教案对话框：列表读取失败显示原因并可重试；空列表提示新建', async () => {
    const api = fakeApi({
      listLessonPlans: vi.fn(async () => {
        throw new Error('SERVICE_UNAVAILABLE：后端服务未运行');
      }),
    });
    renderWorkbench({ api });
    fireEvent.click(screen.getByTestId('lw-cloud-button'));
    await waitFor(() => expect(screen.getByTestId('lw-dialog-error').textContent).toContain('SERVICE_UNAVAILABLE'));

    (api.listLessonPlans as ReturnType<typeof vi.fn>).mockResolvedValueOnce({ items: [], total: 0, offset: 0, limit: 0 });
    fireEvent.click(screen.getByRole('button', { name: '刷新列表' }));
    await waitFor(() => expect(screen.getByTestId('lw-dialog-empty')).toBeTruthy());
  });
});

describe('教案工作台 · 本地草稿', () => {
  it('编辑后自动落本地草稿（600ms 防抖），刷新可恢复', async () => {
    const first = renderWorkbench();
    fireEvent.change(screen.getByTestId('lw-name-input'), { target: { value: '荷塘月色' } });
    await waitFor(
      () => {
        const raw = window.localStorage.getItem(LOCAL_DRAFT_KEY);
        expect(raw).toBeTruthy();
        expect(JSON.parse(raw!).data.title).toBe('荷塘月色');
        expect(JSON.parse(raw!).style).toEqual(DEFAULT_LESSON_STYLE);
      },
      { timeout: 3000 },
    );
    first.unmount();

    renderWorkbench();
    await waitFor(() =>
      expect((screen.getByTestId('lw-name-input') as HTMLInputElement).value).toBe('荷塘月色'),
    );
  });

  it('坏草稿：显示原因、暂停自动写入、原字节不被覆盖', async () => {
    window.localStorage.setItem(LOCAL_DRAFT_KEY, '{broken json');
    renderWorkbench();
    expect((await screen.findByTestId('lw-notice-local-draft')).textContent).toContain('自动保存已暂停');
    fireEvent.change(screen.getByTestId('lw-name-input'), { target: { value: '新标题' } });
    await new Promise((resolve) => setTimeout(resolve, 900));
    expect(window.localStorage.getItem(LOCAL_DRAFT_KEY)).toBe('{broken json');
  });

  it('云端 409 冲突：停在冲突态并提供「载入服务器版本 / 保持本地」', async () => {
    const api = fakeApi({
      listLessonPlans: vi.fn(async () => ({
        items: [{ lessonPlanId: 'plan-9', title: '云端教案', revision: 2, updatedAt: '2026-10-12T00:00:00Z' }],
        total: 1,
        offset: 0,
        limit: 1,
      })),
      getLessonPlan: vi.fn(async () => viewOf(emptyLessonData(), 2)),
      patchLessonPlanDraft: vi.fn(async () => {
        const { ApiError } = await import('@/services/api-client');
        throw new ApiError('REVISION_CONFLICT', '版本冲突', 409, false, undefined, { currentRevision: 5 });
      }),
    });
    renderWorkbench({ api });
    fireEvent.click(screen.getByTestId('lw-cloud-button'));
    await screen.findByTestId('lw-dialog-open-plan-9');
    fireEvent.click(screen.getByTestId('lw-dialog-open-plan-9'));
    await waitFor(() => expect(screen.getByTestId('lw-sync-state').textContent).toContain('已同步'));

    fireEvent.change(screen.getByTestId('lw-name-input'), { target: { value: '本地改动' } });
    await waitFor(() => expect(screen.getByTestId('lw-notice-server-conflict')).toBeTruthy(), { timeout: 4000 });
    expect(screen.getByTestId('lw-conflict-reload')).toBeTruthy();
    fireEvent.click(screen.getByTestId('lw-conflict-keep-local'));
    await waitFor(() => expect(screen.getByTestId('lw-sync-state').textContent).toContain('本地草稿'));
  });
});
