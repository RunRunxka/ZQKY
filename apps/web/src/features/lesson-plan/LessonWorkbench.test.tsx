/**
 * 教案工作台集成测试（R7-FE）：三栏交互、模块增删实时进预览、第 3 页起分页、
 * 字体切换、流式候选 → 采用才进草稿、导出触发、本地草稿与坏稿保护。
 *
 * 依赖注入：`api` / `uploadSource` / `generateServices` 全部走替身，不触网、不写真实数据。
 */
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within, act } from '@testing-library/react';
import { LessonWorkbench } from './LessonWorkbench';
import { LESSON_OWNERSHIP_KEY, LOCAL_DRAFT_KEY } from './model/draft-storage';
import { ApiError } from '@/services/api-client';
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
  /** 生成面板的服务替身覆盖（如只替换 uploadSource 验证上传口径）。 */
  generate?: Partial<ReturnType<typeof generateServices>>;
} = {}) {
  const api = options.api ?? fakeApi();
  const stream = options.stream ?? fakeStream([]);
  const utils = render(
    <LessonWorkbench
      api={api}
      generateServices={{ ...generateServices(stream), ...options.generate }}
    />,
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

describe('教案工作台 · 上传学情文件（2026-10-13 补齐后端端点）', () => {
  it('上传成功：走上传口、候选文件名进面板，并写明「文本发给模型」的口径', async () => {
    const uploadSource = vi.fn(async (file: File) => ({
      assetRef: 'asset-1',
      fileName: file.name,
    }));
    renderWorkbench({ generate: { uploadSource } });

    fireEvent.click(screen.getByTestId('lw-source-file'));
    const input = screen.getByTestId('lw-source-upload');
    // accept 与服务端口径一致：只收文档类；成绩表走「分析报告」来源
    expect(input.getAttribute('accept')).toBe('.docx,.pdf,.txt,.md');
    expect(screen.getByTestId('lw-source-upload-hint').textContent).toContain('成绩表');
    expect(screen.getByTestId('lw-source-upload-hint').textContent).toContain('分析报告');

    fireEvent.change(input, {
      target: { files: [new File(['# 学情说明'], '学情说明.md', { type: 'text/markdown' })] },
    });
    await waitFor(() => expect(uploadSource).toHaveBeenCalledTimes(1));
    expect(await screen.findByTestId('lw-source-file-chip')).toHaveTextContent('学情说明.md');
  });

  it('成绩表被服务端拒绝：原样显示 code 与指引，不降级成「上传成功」', async () => {
    const uploadSource = vi.fn(async () => {
      throw new ApiError(
        'LESSON_SOURCE_UNSUPPORTED',
        '成绩表类文件（.xlsx）不直接接收：避免把含学号/姓名的原始表格发给模型。请先在「学情分析」导入并确认成绩、生成学情报告，再回到本面板把来源选成「分析报告」。',
        422,
        false,
      );
    });
    renderWorkbench({ generate: { uploadSource } });

    fireEvent.click(screen.getByTestId('lw-source-file'));
    fireEvent.change(screen.getByTestId('lw-source-upload'), {
      target: { files: [new File(['x'], '小题分.xlsx')] },
    });

    const error = await screen.findByTestId('lw-source-upload-error');
    expect(error).toHaveTextContent('LESSON_SOURCE_UNSUPPORTED');
    expect(error).toHaveTextContent('学情分析');
    // 失败不留候选文件名（不假装已导入）
    expect(screen.queryByTestId('lw-source-file-chip')).toBeNull();
  });
});

describe('教案工作台 · 导出与本地教案', () => {
  /** 归属（学科 + 班级）存在本机记忆里；导出/新建复用。 */
  const seedOwnership = () =>
    window.localStorage.setItem(
      LESSON_OWNERSHIP_KEY,
      JSON.stringify({ subjectId: 'math', classId: 'class-1' }),
    );

  it('导出：无教案 id 时先创建再导出 + 下载', async () => {
    seedOwnership();
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
    seedOwnership();
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

  it('未选教案归属时导出：打开「本地教案」并如实提示，不静默猜班级', async () => {
    const api = fakeApi();
    renderWorkbench({ api });
    fireEvent.click(screen.getByTestId('lw-export-button'));
    await waitFor(() =>
      expect(screen.getByTestId('lw-notice-export').textContent).toContain('先在「本地教案」里选择学科与班级'),
    );
    expect(api.createLessonPlan).not.toHaveBeenCalled();
    expect(api.exportLessonPlan).not.toHaveBeenCalled();
    expect(screen.getByTestId('lw-lessons-dialog')).toBeTruthy();
  });

  it('本地教案对话框：列表读取失败显示原因并可重试；空列表提示新建', async () => {
    const api = fakeApi({
      listLessonPlans: vi.fn(async () => {
        throw new Error('SERVICE_UNAVAILABLE：后端服务未运行');
      }),
    });
    renderWorkbench({ api });
    fireEvent.click(screen.getByTestId('lw-library-button'));
    await waitFor(() => expect(screen.getByTestId('lw-dialog-error').textContent).toContain('SERVICE_UNAVAILABLE'));

    (api.listLessonPlans as ReturnType<typeof vi.fn>).mockResolvedValueOnce({ items: [], total: 0, offset: 0, limit: 0 });
    fireEvent.click(screen.getByRole('button', { name: '刷新列表' }));
    await waitFor(() => expect(screen.getByTestId('lw-dialog-empty')).toBeTruthy());
  });

  it('对话里教案写操作成功的事件会触发列表重载', async () => {
    const api = fakeApi();
    renderWorkbench({ api });
    fireEvent.click(screen.getByTestId('lw-library-button'));
    await waitFor(() => expect(api.listLessonPlans).toHaveBeenCalledTimes(1));

    const { LESSON_PLANS_CHANGED_EVENT } = await import('@/services/lesson-plans-events');
    act(() => {
      window.dispatchEvent(new Event(LESSON_PLANS_CHANGED_EVENT));
    });
    await waitFor(() => expect(api.listLessonPlans).toHaveBeenCalledTimes(2));
  });
});

describe('教案工作台 · 本地教案删除（不归档）', () => {
  const listWith = (id: string, title: string, revision = 2) => ({
    items: [{ lessonPlanId: id, title, revision, updatedAt: '2026-10-13T02:00:00Z' }],
    total: 1,
    offset: 0,
    limit: 1,
  });

  it('删除成功：二次确认点名后果 → DELETE 带列表修订号 → 行消失并留回执（不关闭对话框）', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const api = fakeApi({
      listLessonPlans: vi.fn(async () => listWith('plan-9', '荷塘月色', 4)),
      deleteLessonPlan: vi.fn(async () => ({
        deleted: true,
        lessonPlanId: 'plan-9',
        removedRevisions: 3,
        removedProposals: 0,
        removedInputs: 0,
      })),
    });
    renderWorkbench({ api });
    fireEvent.click(screen.getByTestId('lw-library-button'));
    await screen.findByTestId('lw-dialog-list');

    fireEvent.click(screen.getByTestId('lw-dialog-delete-plan-9'));
    await waitFor(() => expect(api.deleteLessonPlan).toHaveBeenCalledWith('plan-9', 4));
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('不可恢复'));
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('学生、班级、成绩、学情报告与试卷不受影响'));

    // 已删行不留在列表里；对话框仍开着（便于继续处理其它教案）
    await waitFor(() => expect(screen.queryByTestId('lw-dialog-delete-plan-9')).toBeNull());
    expect(screen.getByTestId('lw-dialog-empty')).toBeTruthy();
    // 工作台回执（关掉对话框后可见；这里直接在通知条断言）
    expect(screen.getByTestId('lw-notice-lesson-deleted').textContent).toContain('已彻底删除教案「荷塘月色」');
    expect(screen.getByTestId('lw-notice-lesson-deleted').textContent).toContain('3 个修订');
  });

  it('删除失败（409 乐观锁）：原样显示服务端 code 与 message，行仍在', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const api = fakeApi({
      listLessonPlans: vi.fn(async () => listWith('plan-8', '故都的秋')),
      deleteLessonPlan: vi.fn(async () => {
        const { ApiError } = await import('@/services/api-client');
        throw new ApiError('REVISION_CONFLICT', '数据已被其他操作更新，请刷新后重试。', 409, false, undefined, {
          currentRevision: 7,
        });
      }),
    });
    renderWorkbench({ api });
    fireEvent.click(screen.getByTestId('lw-library-button'));
    await screen.findByTestId('lw-dialog-list');

    fireEvent.click(screen.getByTestId('lw-dialog-delete-plan-8'));
    await waitFor(() =>
      expect(screen.getByTestId('lw-dialog-action-error').textContent).toContain(
        '删除教案失败（REVISION_CONFLICT）',
      ),
    );
    expect(screen.getByTestId('lw-dialog-delete-plan-8')).toBeTruthy();
    expect(screen.queryByTestId('lw-notice-lesson-deleted')).toBeNull();
  });

  it('取消删除不发起请求', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false);
    const api = fakeApi({
      listLessonPlans: vi.fn(async () => listWith('plan-7', '背影')),
      deleteLessonPlan: vi.fn(),
    });
    renderWorkbench({ api });
    fireEvent.click(screen.getByTestId('lw-library-button'));
    await screen.findByTestId('lw-dialog-list');

    fireEvent.click(screen.getByTestId('lw-dialog-delete-plan-7'));
    expect(api.deleteLessonPlan).not.toHaveBeenCalled();
    expect(screen.getByTestId('lw-dialog-delete-plan-7')).toBeTruthy();
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

  it('后端 409 冲突：停在冲突态并提供「载入服务器版本 / 保持本地」', async () => {
    const api = fakeApi({
      listLessonPlans: vi.fn(async () => ({
        items: [{ lessonPlanId: 'plan-9', title: '本地教案', revision: 2, updatedAt: '2026-10-12T00:00:00Z' }],
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
    fireEvent.click(screen.getByTestId('lw-library-button'));
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

describe('教案工作台 · 离开守卫注册稳定（导航不被锁死）', () => {
  /**
   * 回归（2026-10-13 真机 bug「进入教案工作台后点导航栏无法切换模块」）：
   * 守卫若跟着**每次渲染都换身份**的 flushAll 重新注册，导航守卫会把"决策期间守卫集合
   * 被增删"判为不安全而拒绝该次导航。这里断言多次 re-render 后守卫只注册一次、
   * 且注册的回调放行（返回 true）。
   */
  it('多次渲染只注册一次守卫，注册的回调返回放行', async () => {
    vi.resetModules();
    const guards: Array<{ key: string; guard: () => Promise<boolean> }> = [];
    const register = vi.fn((key: string, guard: () => Promise<boolean>) => {
      guards.push({ key, guard });
      return vi.fn();
    });
    // 真实 provider 的 controller 是 memo 过的稳定对象（每次渲染同引用）；替身必须同形，
    // 否则抖动来自替身而不是被测的注册逻辑。
    const controller = {
      hasProvider: true,
      register,
      requestNavigation: vi.fn(async () => true),
    };
    vi.doMock('@/services/navigation-guard', () => ({
      useNavigationGuard: () => controller,
    }));
    const { LessonWorkbench: Isolated } = await import('./LessonWorkbench');
    render(<Isolated api={fakeApi()} generateServices={generateServices(fakeStream([]))} />);

    // 连续改名制造多次 re-render（每次都会刷新 store 与自动保存状态）
    for (const value of ['第一次', '第二次', '第三次']) {
      fireEvent.change(screen.getByTestId('lw-name-input'), { target: { value } });
    }
    await waitFor(() => expect(register).toHaveBeenCalled());

    expect(register).toHaveBeenCalledTimes(1);
    expect(guards[0].key).toBe('lesson-plan:draft');
    await expect(guards[0].guard()).resolves.toBe(true);
    vi.doUnmock('@/services/navigation-guard');
    vi.resetModules();
  });
});
