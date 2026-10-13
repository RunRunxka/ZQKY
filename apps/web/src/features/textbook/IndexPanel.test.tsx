/**
 * 索引与嵌入面板（R10-FE 2026-10-13）：首次建设路径与状态呈现。
 *
 * 覆盖：无索引代时的醒目提示与「建立档案 → 发布起始代」全流程（探针/保存/重建/刷新/提示）、
 * 已有索引代时的状态渲染、嵌入服务不可达时不假可用、探针失败原样报错。
 * 服务全部注入替身，不触网。
 */
import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import type { EmbeddingModelList, EmbeddingProfileList, IndexStatusView } from '@/contracts/textbook';
import { ApiError } from '@/services/api-client';
import { IndexPanel, type IndexPanelServices } from './IndexPanel';

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

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

function status(overrides: Partial<IndexStatusView> = {}): IndexStatusView {
  return {
    activeGenerationId: null,
    activeProfileId: null,
    activeProfileName: null,
    activeProfileDimensions: null,
    generation: null,
    rebuildJob: null,
    generationCount: 0,
    qdrantAvailable: true,
    qdrantReason: null,
    scopeReady: false,
    scopeReason: '尚未创建任何索引代。',
    ...overrides,
  };
}

const MODELS: EmbeddingModelList = {
  baseUrl: 'http://127.0.0.1:11434',
  available: true,
  reason: null,
  models: [
    { name: 'qwen2.5:7b', digest: 'd1', sizeBytes: 1, family: 'qwen2', parameterSize: '7B', isEmbeddingCapable: false },
    { name: 'bge-m3', digest: 'd2', sizeBytes: 1, family: 'bert', parameterSize: '568M', isEmbeddingCapable: true },
  ],
};

const PROFILES: EmbeddingProfileList = { profiles: [], activeProfileId: null };

function services(overrides: Partial<IndexPanelServices> = {}): IndexPanelServices {
  return {
    getIndexStatus: vi.fn(async () => status()),
    listEmbeddingModels: vi.fn(async () => MODELS),
    listEmbeddingProfiles: vi.fn(async () => PROFILES),
    createEmbeddingProfile: vi.fn(async () => ({
      profileId: 'profile-1',
      fingerprint: 'fp',
      adapter: 'ollama' as const,
      nativeBaseUrl: 'http://127.0.0.1:11434',
      modelName: 'bge-m3',
      modelManifestDigest: 'd2',
      dimensions: 1024,
      distance: 'cosine' as const,
      queryPrefix: '',
      documentPrefix: '',
      normalization: 'none',
      verifiedAt: '2026-10-13T00:00:00Z',
      retiredAt: null,
      isActive: false,
      installed: true,
    })),
    startRebuild: vi.fn(async () => ({
      jobId: 'job-rebuild-1',
      kind: 'rebuild' as const,
      state: 'queued' as const,
      targetGenerationId: 'gen-1',
      baseGenerationId: null,
      documentId: null,
      inputRevisionId: null,
      attempt: 1,
      progress: { documentsDone: 0, documentsTotal: 0, chunksDone: 0, chunksTotal: 0, currentTitle: null },
      errorCode: null,
      errorMessage: null,
      retryable: false,
      createdAt: '2026-10-13T00:00:00Z',
      updatedAt: '2026-10-13T00:00:00Z',
    })),
    ...overrides,
  };
}


/** 保存键在模型列表加载完成前是禁用的：先等可用再点，避免全量套件下空点。 */
async function clickSaveWhenEnabled() {
  const save = await screen.findByTestId('textbook-embedding-save', undefined, { timeout: 8000 });
  await waitFor(() => expect(save).not.toBeDisabled(), { timeout: 8000 });
  fireEvent.click(save);
}

describe('索引与嵌入面板', () => {
  it('无索引代：醒目提示 + 建立档案（探针/保存）→ 发起受控重建 → 刷新出已发布索引代', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const published = status({
      activeGenerationId: 'gen-1',
      activeProfileId: 'profile-1',
      activeProfileName: 'bge-m3',
      activeProfileDimensions: 1024,
      generation: {
        generationId: 'gen-1',
        collectionName: 'textbooks_x',
        profileId: 'profile-1',
        state: 'ready',
        chunkTotal: 0,
        documentTotal: 0,
        createdAt: '2026-10-13T00:00:00Z',
        publishedAt: '2026-10-13T00:00:05Z',
      },
      generationCount: 1,
      scopeReady: true,
      scopeReason: null,
    });
    // 状态以"是否已发起重建"为界（不数读取次数：挂载期读取次数受渲染环境影响）：
    // 发起重建前一律"还没有代"（覆盖保存后的即时判断），发起后轮询即读到已发布。
    let rebuilt = false;
    const api = services({
      getIndexStatus: vi.fn(async () => (rebuilt ? published : status())),
      startRebuild: vi.fn(async () => {
        rebuilt = true;
        return {
          jobId: 'job-rebuild-1',
          kind: 'rebuild' as const,
          state: 'queued' as const,
          targetGenerationId: 'gen-1',
          baseGenerationId: null,
          documentId: null,
          inputRevisionId: null,
          attempt: 1,
          progress: {
            documentsDone: 0,
            documentsTotal: 0,
            chunksDone: 0,
            chunksTotal: 0,
            currentTitle: null,
          },
          errorCode: null,
          errorMessage: null,
          retryable: false,
          createdAt: '2026-10-13T00:00:00Z',
          updatedAt: '2026-10-13T00:00:00Z',
        };
      }),
    });

    render(<IndexPanel services={api} onClose={() => {}} />);
    expect(await screen.findByTestId('textbook-index-no-generation', undefined, { timeout: 8000 })).toHaveTextContent('提交入库');
    // 默认选中 bge-m3（跳过非 embedding 能力的模型）
    expect((screen.getByTestId('textbook-embedding-model') as HTMLSelectElement).value).toBe('bge-m3');

    await clickSaveWhenEnabled();

    await waitFor(() =>
      expect(api.createEmbeddingProfile).toHaveBeenCalledWith({ modelName: 'bge-m3' }),
    );
    await waitFor(
      () =>
        expect(api.startRebuild).toHaveBeenCalledWith({
          submissionId: expect.any(String),
          profileId: 'profile-1',
        }),
      { timeout: 8000 },
    );
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('还没有已发布的教材索引代'));
    // 轮询读到已发布 → 提示可以导入；醒目提示消失、状态区显示索引代与可检索
    await waitFor(
      () => expect(screen.getByTestId('textbook-index-notice')).toHaveTextContent('索引代已发布'),
      { timeout: 15000 },
    );
    await waitFor(() => expect(screen.queryByTestId('textbook-index-no-generation')).toBeNull(), {
      timeout: 8000,
    });
    expect(screen.getByTestId('textbook-index-status')).toHaveTextContent('gen-1…');
    expect(screen.getByTestId('textbook-index-status')).toHaveTextContent('已就绪');
  });

  it('已有索引代：渲染状态（代/档案/Qdrant/可检索），不显示"没有代"提示', async () => {
    const api = services({
      getIndexStatus: vi.fn(async () =>
        status({
          activeGenerationId: 'gen-9',
          activeProfileId: 'profile-9',
          activeProfileName: 'bge-m3',
          activeProfileDimensions: 1024,
          generation: {
            generationId: 'gen-9',
            collectionName: 'textbooks_9',
            profileId: 'profile-9',
            state: 'ready',
            chunkTotal: 427,
            documentTotal: 1,
            createdAt: '2026-10-13T00:00:00Z',
            publishedAt: '2026-10-13T00:01:00Z',
          },
          generationCount: 1,
          scopeReady: true,
          scopeReason: null,
        }),
      ),
    });
    render(<IndexPanel services={api} onClose={() => {}} />);

    const block = await screen.findByTestId('textbook-index-status', undefined, { timeout: 8000 });
    expect(block).toHaveTextContent('书册 1');
    expect(block).toHaveTextContent('切块 427');
    expect(block).toHaveTextContent('bge-m3 · 1024 维');
    expect(block).toHaveTextContent('可达');
    expect(block).toHaveTextContent('已就绪');
    expect(screen.queryByTestId('textbook-index-no-generation')).toBeNull();
  });

  it('本机嵌入服务不可达：如实显示原因，不提供保存（不假可用）', async () => {
    const api = services({
      listEmbeddingModels: vi.fn(async () => ({
        baseUrl: 'http://127.0.0.1:11434',
        available: false,
        reason: '连接被拒绝',
        models: [],
      })),
    });
    render(<IndexPanel services={api} onClose={() => {}} />);

    expect(await screen.findByTestId('textbook-embedding-unavailable', undefined, { timeout: 8000 })).toHaveTextContent(
      '连接被拒绝',
    );
    expect(screen.queryByTestId('textbook-embedding-save')).toBeNull();
  });

  it('探针/保存失败：原样显示服务端 code 与 message', async () => {
    const api = services({
      createEmbeddingProfile: vi.fn(async () => {
        throw new ApiError('EMBEDDING_MODEL_CHANGED', '模型清单 digest 与配置不一致。', 409, false);
      }),
    });
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<IndexPanel services={api} onClose={() => {}} />);

    await clickSaveWhenEnabled();
    const error = await screen.findByTestId('textbook-index-error', undefined, { timeout: 8000 });
    expect(error).toHaveTextContent('建立嵌入档案失败（EMBEDDING_MODEL_CHANGED）');
    expect(error).toHaveTextContent('模型清单 digest 与配置不一致。');
    expect(screen.queryByTestId('textbook-index-notice')).toBeNull();
  });
});
