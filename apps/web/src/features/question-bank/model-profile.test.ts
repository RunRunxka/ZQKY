import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  DEFAULT_ORGANIZER_UNAVAILABLE_REASON,
  fetchLocalOrganizerModel,
  organizerModelLabel,
  parseLocalOrganizerModel,
} from './model-profile';

const FULL = {
  retrieval: { available: true, reason: null },
  summarization: {
    available: true,
    reason: null,
    model: 'qwen2.5:7b',
    providerUrl: 'http://127.0.0.1:11434',
  },
  sourceAccess: { available: true, reason: null },
  scope: { ready: true, reason: null, selection: null },
};

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('本机整理模型解析（/rag/status.summarization）', () => {
  it('可用时取本机模型名与地址', () => {
    expect(parseLocalOrganizerModel(FULL)).toEqual({
      modelName: 'qwen2.5:7b',
      available: true,
      reason: null,
      providerUrl: 'http://127.0.0.1:11434',
    });
  });

  it('可用但未报告模型名时传空串（服务端默认），不猜模型名', () => {
    const model = parseLocalOrganizerModel({
      ...FULL,
      summarization: { available: true, reason: null, model: null, providerUrl: null },
    });
    expect(model.available).toBe(true);
    expect(model.modelName).toBe('');
    expect(organizerModelLabel(model)).toBe('使用本机默认模型（服务端默认）');
  });

  it('不可用时保留服务端原因', () => {
    const model = parseLocalOrganizerModel({
      ...FULL,
      summarization: {
        available: false,
        reason: '本机概括模型不可用：未在本机 Ollama 找到 qwen2.5:7b。',
        model: null,
        providerUrl: null,
      },
    });
    expect(model.available).toBe(false);
    expect(model.modelName).toBe('');
    expect(model.reason).toBe('本机概括模型不可用：未在本机 Ollama 找到 qwen2.5:7b。');
  });

  it('缺少 summarization 分区或形状不认识时按不可用处理，不猜造可用性', () => {
    expect(parseLocalOrganizerModel(null).available).toBe(false);
    expect(parseLocalOrganizerModel({ available: true }).available).toBe(false);
    expect(parseLocalOrganizerModel({ summarization: 'x' }).reason).toContain(
      '未报告本机概括模型状态',
    );
    expect(organizerModelLabel(null)).toBe('正在读取本机模型状态…');
  });

  it('不可用且无原因时给出默认可读原因', () => {
    const model = parseLocalOrganizerModel({ summarization: { available: false } });
    expect(model.reason).toBe(DEFAULT_ORGANIZER_UNAVAILABLE_REASON);
  });

  it('状态请求失败时如实报告错误码，不返回可用', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(() =>
        Promise.resolve({
          ok: false,
          status: 503,
          json: async () => ({
            code: 'SERVICE_UNAVAILABLE',
            message: '教材 RAG v2 服务未装配。',
            retryable: true,
          }),
        } as Response),
      ),
    );

    const model = await fetchLocalOrganizerModel();
    expect(model.available).toBe(false);
    expect(model.modelName).toBe('');
    expect(model.reason).toContain('读取本机模型状态失败（SERVICE_UNAVAILABLE）');
  });
});
