import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import type {
  EmbeddingModelList,
  EmbeddingProbeView,
  EmbeddingProfileList,
  EmbeddingProfileView,
  IndexStatusView,
  JobView,
} from '@/contracts/textbook';
import { EmbeddingPanel } from './EmbeddingPanel';

const MODELS: EmbeddingModelList = {
  baseUrl: 'http://127.0.0.1:11434',
  available: true,
  reason: null,
  models: [
    {
      name: 'bge-m3',
      digest: 'abcdef1234567890',
      sizeBytes: 1200,
      family: 'bert',
      parameterSize: '568M',
      isEmbeddingCapable: true,
    },
    {
      name: 'qwen2.5:7b',
      digest: 'f0f0f0f0f0f0f0f0',
      sizeBytes: 4400,
      family: 'qwen2',
      parameterSize: '7B',
      isEmbeddingCapable: false,
    },
  ],
};

const PROFILE: EmbeddingProfileView = {
  profileId: 'profile-1',
  fingerprint: 'fingerprint-123456',
  adapter: 'ollama',
  nativeBaseUrl: 'http://127.0.0.1:11434',
  modelName: 'bge-m3',
  modelManifestDigest: 'abcdef1234567890',
  dimensions: 1024,
  distance: 'cosine',
  queryPrefix: '',
  documentPrefix: '',
  normalization: 'none',
  verifiedAt: '2026-09-27T00:00:00Z',
  retiredAt: null,
  isActive: true,
  installed: true,
};

const PROFILES: EmbeddingProfileList = { profiles: [PROFILE], activeProfileId: 'profile-1' };

const PROBE: EmbeddingProbeView = {
  modelName: 'bge-m3',
  modelManifestDigest: 'abcdef1234567890',
  dimensions: 1024,
  distance: 'cosine',
  sampleCount: 2,
  nonZero: true,
  finite: true,
  stableDigest: true,
  alreadyConfigured: false,
  existingProfileId: null,
};

function job(overrides: Partial<JobView> = {}): JobView {
  return {
    jobId: 'rebuild-1',
    kind: 'rebuild',
    state: 'running',
    targetGenerationId: 'gen-2',
    baseGenerationId: 'gen-1',
    documentId: null,
    inputRevisionId: null,
    attempt: 1,
    progress: {
      documentsDone: 1,
      documentsTotal: 4,
      chunksDone: 30,
      chunksTotal: 120,
      currentTitle: null,
    },
    errorCode: null,
    errorMessage: null,
    retryable: false,
    createdAt: '2026-09-28T00:00:00Z',
    updatedAt: '2026-09-28T00:01:00Z',
    ...overrides,
  };
}

function status(overrides: Partial<IndexStatusView> = {}): IndexStatusView {
  return {
    activeGenerationId: 'gen-1',
    activeProfileId: 'profile-1',
    activeProfileName: 'bge-m3',
    activeProfileDimensions: 1024,
    generation: {
      generationId: 'gen-1',
      collectionName: 'zqky_textbook_v1',
      profileId: 'profile-1',
      state: 'ready',
      chunkTotal: 120,
      documentTotal: 4,
      createdAt: '2026-09-27T00:00:00Z',
      publishedAt: '2026-09-27T00:05:00Z',
    },
    rebuildJob: null,
    generationCount: 2,
    qdrantAvailable: true,
    qdrantReason: null,
    scopeReady: true,
    scopeReason: null,
    ...overrides,
  };
}

const ok = (body: unknown) => ({ ok: true, status: 200, json: async () => body }) as Response;
const failed = (status: number, body: unknown) =>
  ({ ok: false, status, json: async () => body }) as Response;

function stubApi(handler: (url: string, init: RequestInit) => Response) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(handler(typeof input === 'string' ? input : input.toString(), init ?? {})),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function postsTo(fetchMock: ReturnType<typeof stubApi>, fragment: string) {
  return fetchMock.mock.calls.filter(
    ([url, init]) =>
      String(url).includes(fragment) && (init as RequestInit | undefined)?.method === 'POST',
  );
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('Embedding 面板', () => {
  it('展示当前模型、索引代与候选模型能力标注', async () => {
    stubApi((url) => {
      if (url.includes('/textbook-index/status')) return ok(status());
      if (url.includes('/embedding-models')) return ok(MODELS);
      if (url.includes('/embedding-profiles')) return ok(PROFILES);
      throw new Error(`未预期的请求 ${url}`);
    });
    render(<EmbeddingPanel />);

    expect(await screen.findByText('模型：bge-m3')).toBeInTheDocument();
    expect(screen.getByText('实测维度：1024')).toBeInTheDocument();
    expect(screen.getByText('索引代：gen-1')).toBeInTheDocument();
    expect(screen.getByText('块 120')).toBeInTheDocument();
    expect(screen.getByText('可用')).toBeInTheDocument();

    expect(screen.getByText('Embedding 模型')).toBeInTheDocument();
    expect(screen.getByText('非 Embedding 模型')).toBeInTheDocument();
    expect(screen.getByText(/本机地址：http:\/\/127\.0\.0\.1:11434/)).toBeInTheDocument();
    expect(await screen.findByRole('radio', { name: /bge-m3 · 1024 维/ })).toBeChecked();
  });

  it('Qdrant 不可用如实显示原因，不显示为可用', async () => {
    stubApi((url) => {
      if (url.includes('/textbook-index/status')) {
        return ok(status({ qdrantAvailable: false, qdrantReason: '连接 127.0.0.1:6333 被拒绝' }));
      }
      if (url.includes('/embedding-models')) return ok(MODELS);
      return ok(PROFILES);
    });
    render(<EmbeddingPanel />);

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('向量库（Qdrant）不可用：连接 127.0.0.1:6333 被拒绝');
    expect(screen.getByText('不可用')).toBeInTheDocument();
    expect(screen.queryByText('可用')).not.toBeInTheDocument();
  });

  it('检测调用真实探测接口，保存配置带前缀与归一化', async () => {
    const fetchMock = stubApi((url, init) => {
      if (url.includes('/textbook-index/status')) return ok(status());
      if (url.includes('/embedding-models')) return ok(MODELS);
      if (url.includes('/embedding-probes')) return ok(PROBE);
      if (url.includes('/embedding-profiles')) {
        return init.method === 'POST' ? ok(PROFILE) : ok(PROFILES);
      }
      throw new Error(`未预期的请求 ${url}`);
    });
    render(<EmbeddingPanel />);

    await screen.findByText('bge-m3 · 568M');
    fireEvent.click(screen.getAllByRole('button', { name: '检测' })[0]);

    expect(await screen.findByText('实测维度 1024')).toBeInTheDocument();
    expect(screen.getByText('身份稳定')).toBeInTheDocument();
    expect(screen.getByText(/检测通过只代表该模型的接口能力/)).toBeInTheDocument();

    fireEvent.change(screen.getByLabelText('归一化'), { target: { value: 'l2' } });
    fireEvent.click(screen.getByRole('button', { name: '保存配置' }));

    expect(
      await screen.findByText(/已保存 Embedding 配置（bge-m3 · 1024 维）/),
    ).toBeInTheDocument();
    const probes = postsTo(fetchMock, '/embedding-probes');
    expect(JSON.parse(String((probes[0][1] as RequestInit).body))).toEqual({ modelName: 'bge-m3' });
    const saves = postsTo(fetchMock, '/embedding-profiles');
    expect(JSON.parse(String((saves[0][1] as RequestInit).body))).toEqual({
      modelName: 'bge-m3',
      queryPrefix: '',
      documentPrefix: '',
      normalization: 'l2',
    });
  });

  it('重建提交失败时保留同一幂等键，成功后按索引状态显示进度并可取消', async () => {
    let rebuildCalls = 0;
    let currentStatus = status();
    const fetchMock = stubApi((url) => {
      if (url.includes('/textbook-index/status')) return ok(currentStatus);
      if (url.includes('/embedding-models')) return ok(MODELS);
      if (url.includes('/embedding-profiles')) return ok(PROFILES);
      if (url.includes('/textbook-index/rebuilds')) {
        rebuildCalls += 1;
        if (rebuildCalls === 1) {
          return failed(503, {
            code: 'SERVICE_UNAVAILABLE',
            message: '后端服务不可用。',
            retryable: true,
          });
        }
        currentStatus = status({ rebuildJob: job() });
        return ok(job());
      }
      if (url.includes('/textbook-jobs/rebuild-1/cancel')) {
        currentStatus = status({ rebuildJob: job({ state: 'cancelled' }) });
        return ok(job({ state: 'cancelled' }));
      }
      throw new Error(`未预期的请求 ${url}`);
    });
    render(<EmbeddingPanel />);

    const startButton = await screen.findByRole('button', { name: '开始重建' });
    await waitFor(() => expect(startButton).toBeEnabled());
    fireEvent.click(startButton);

    expect(await screen.findByText(/后端服务不可用/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /重试提交（同一提交键）/ })).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /重试提交（同一提交键）/ }));

    expect(await screen.findByText('阶段：执行中')).toBeInTheDocument();
    expect(screen.getByText('已完成教材 1/4')).toBeInTheDocument();
    expect(screen.getByText('已完成块 30/120')).toBeInTheDocument();

    const rebuilds = postsTo(fetchMock, '/textbook-index/rebuilds');
    expect(rebuilds).toHaveLength(2);
    const first = JSON.parse(String((rebuilds[0][1] as RequestInit).body));
    const second = JSON.parse(String((rebuilds[1][1] as RequestInit).body));
    expect(first).toEqual({ submissionId: expect.any(String), profileId: 'profile-1' });
    expect(second.submissionId).toBe(first.submissionId);

    fireEvent.click(screen.getByRole('button', { name: '取消重建' }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url]) =>
          String(url).includes('/textbook-jobs/rebuild-1/cancel'),
        ),
      ).toBe(true),
    );
  });

  it('重建失败显示原因与重新发起入口', async () => {
    let currentStatus = status({
      rebuildJob: job({
        state: 'failed',
        errorCode: 'EMBEDDING_MODEL_CHANGED',
        errorMessage: '模型身份变化，已终止。',
        retryable: false,
      }),
    });
    let rebuildCalls = 0;
    const fetchMock = stubApi((url) => {
      if (url.includes('/textbook-index/status')) return ok(currentStatus);
      if (url.includes('/embedding-models')) return ok(MODELS);
      if (url.includes('/embedding-profiles')) return ok(PROFILES);
      if (url.includes('/textbook-index/rebuilds')) {
        rebuildCalls += 1;
        currentStatus = status({ rebuildJob: job({ state: 'queued', attempt: 2 }) });
        return ok(job({ state: 'queued', attempt: 2 }));
      }
      throw new Error(`未预期的请求 ${url}`);
    });
    render(<EmbeddingPanel />);

    expect(await screen.findByText(/EMBEDDING_MODEL_CHANGED/)).toBeInTheDocument();
    expect(screen.getByText(/模型身份变化，已终止/)).toBeInTheDocument();
    // 等配置列表就绪并自动选中，避免在未选中配置时点击（那是另一条错误路径）
    expect(await screen.findByRole('radio', { name: /bge-m3 · 1024 维/ })).toBeChecked();

    fireEvent.click(screen.getByRole('button', { name: '重新发起' }));
    await waitFor(() => expect(rebuildCalls).toBe(1));
    expect(await screen.findByText('阶段：排队中')).toBeInTheDocument();
    expect(postsTo(fetchMock, '/textbook-index/rebuilds')).toHaveLength(1);
  });
});
