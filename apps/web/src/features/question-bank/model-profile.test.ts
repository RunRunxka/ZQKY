import { describe, expect, it } from 'vitest';
import type {
  ModelCatalog,
  ModelConnectionView,
  ModelProfileView,
} from '@/contracts/model-settings';
import {
  isLocalQuestionModel,
  isLoopbackBaseUrl,
  ORGANIZER_CLOUD_NOTICE,
  ORGANIZER_MODEL_LOADING,
  QUESTION_AI_LOCAL_MODEL_REASON,
  QUESTION_MODEL_NOT_CLOUD_CODE,
  pickOrganizerChatModel,
  resolveOrganizerChatModel,
} from './model-profile';

/* ---------------------------------------------------------------- 夹具（冻结契约形状） */

/**
 * 默认夹具 = **云端**档案：题库 AI 在 2026-10-07 起只允许云端模型，
 * 本机档案（`LOCAL_PROVIDER_IDS`）会被前端 gate 与后端 422 一并拒绝，
 * 因此「可用」的基准场景必须是云端；本机场景单独用 `localCatalog()` 构造。
 */
function connection(overrides: Partial<ModelConnectionView> = {}): ModelConnectionView {
  return {
    id: 'conn-1',
    displayName: 'DeepSeek 云端',
    providerId: 'deepseek',
    providerLabel: 'DeepSeek',
    protocol: 'openai-chat',
    apiFormat: 'auto',
    apiVersion: null,
    baseUrl: '',
    resolvedBaseUrl: 'https://api.deepseek.com/v1',
    hasCredential: true,
    hasManagedCredential: false,
    callable: true,
    callableReason: null,
    credentialScope: 'process',
    extraHeaderNames: [],
    createdAt: '2026-09-29T00:00:00Z',
    updatedAt: '2026-09-29T00:00:00Z',
    ...overrides,
  };
}

function profile(overrides: Partial<ModelProfileView> = {}): ModelProfileView {
  return {
    id: 'p-chat-1',
    connectionId: 'conn-1',
    displayName: '云端问答',
    modelId: 'deepseek-chat',
    purpose: 'chat',
    contextTokens: 8192,
    maxOutputTokens: 2048,
    supportedParams: [],
    reasoningEnabled: null,
    reasoningEffort: null,
    reasoningStyle: null,
    capabilities: {},
    connection: {
      displayName: 'DeepSeek 云端',
      providerId: 'deepseek',
      providerLabel: 'DeepSeek',
      protocol: 'openai-chat',
      apiFormat: 'auto',
      hasCredential: true,
    },
    createdAt: '2026-09-29T00:00:00Z',
    updatedAt: '2026-09-29T00:00:00Z',
    ...overrides,
  };
}

function catalog(overrides: Partial<ModelCatalog> = {}): ModelCatalog {
  return {
    revision: 1,
    defaultChatProfileId: 'p-chat-1',
    connections: [connection()],
    profiles: [profile()],
    ...overrides,
  };
}

/** 本机 Ollama 档案（后端 `is_local=True`）：题库 AI 一律拒绝。 */
function localCatalog(): ModelCatalog {
  return {
    revision: 1,
    defaultChatProfileId: 'p-local-1',
    connections: [
      connection({
        id: 'conn-local',
        displayName: '本机 Ollama',
        providerId: 'ollama',
        providerLabel: 'Ollama',
        resolvedBaseUrl: 'http://localhost:11434/v1',
        hasCredential: false,
      }),
    ],
    profiles: [
      profile({
        id: 'p-local-1',
        connectionId: 'conn-local',
        displayName: '本机问答',
        modelId: 'qwen2.5:7b',
        connection: {
          displayName: '本机 Ollama',
          providerId: 'ollama',
          providerLabel: 'Ollama',
          protocol: 'openai-chat',
          apiFormat: 'auto',
          hasCredential: false,
        },
      }),
    ],
  };
}

/* ---------------------------------------------------------------- 解析规则 */

describe('AI 整理模型：来自聊天模型来源（/model-catalog）', () => {
  it('取默认聊天模型的 profile id，展示名与 /chat 一致（显示名 · 模型 id）', () => {
    const model = pickOrganizerChatModel(catalog());
    expect(model.available).toBe(true);
    expect(model.profileId).toBe('p-chat-1');
    expect(model.profileId).not.toBe('deepseek-chat');
    expect(model.modelLabel).toBe('云端问答 · deepseek-chat');
    expect(model.reason).toBeNull();
  });

  it('本机档案在受理期即被拒绝：文案含「题库 AI 不使用本机模型」，且不自动换模型', () => {
    const local = pickOrganizerChatModel(localCatalog());
    expect(local.available).toBe(false);
    expect(local.profileId).toBe('');
    expect(local.reason).toContain(QUESTION_AI_LOCAL_MODEL_REASON);
    expect(local.reason).toContain('云端档案');
    expect(local.reason).toContain('不会自动改用其他模型');
    expect(QUESTION_MODEL_NOT_CLOUD_CODE).toBe('QUESTION_MODEL_NOT_CLOUD');

    // 本机供应商清单与后端 registry 的 is_local 一致（任一本机 id 都不放行）
    for (const providerId of ['vllm', 'ollama', 'lm_studio', 'llama_cpp', 'lemonade', 'ovms']) {
      expect(isLocalQuestionModel(providerId, 'https://api.example.com/v1')).toBe(true);
    }
    expect(isLocalQuestionModel('deepseek', 'http://localhost:11434/v1')).toBe(false);
  });

  it('云端档案标注「发送至该模型服务」', () => {
    const cloud = pickOrganizerChatModel(catalog());
    expect(cloud.available).toBe(true);
    expect(cloud.cloud).toBe(true);
    expect(ORGANIZER_CLOUD_NOTICE).toBe('将所选题目文本发送至该模型服务');
  });

  it('地址判定与降级：回环视为本机；地址缺失或无法解析按云端处理（宁可多提示一次数据外发）', () => {
    expect(isLoopbackBaseUrl('http://localhost:11434/v1')).toBe(true);
    expect(isLoopbackBaseUrl('http://127.0.0.1:8000/v1')).toBe(true);
    expect(isLoopbackBaseUrl('http://[::1]:11434/v1')).toBe(true);
    expect(isLoopbackBaseUrl('http://ollama.localhost:11434')).toBe(true);
    expect(isLoopbackBaseUrl('https://api.example.com/v1')).toBe(false);
    expect(isLoopbackBaseUrl('')).toBe(false);
    expect(isLoopbackBaseUrl(null)).toBe(false);
    expect(isLoopbackBaseUrl('不是地址')).toBe(false);

    // providerId 缺失（旧连接/未知供应商）时退回地址判定
    expect(isLocalQuestionModel(null, 'http://localhost:11434/v1')).toBe(true);
    expect(isLocalQuestionModel(undefined, '')).toBe(false);

    const missing = pickOrganizerChatModel(
      catalog({ connections: [connection({ resolvedBaseUrl: '' })] }),
    );
    expect(missing.cloud).toBe(true);
  });

  it('目录还没读到时给出加载中文案，不猜模型', () => {
    const model = pickOrganizerChatModel(null);
    expect(model.available).toBe(false);
    expect(model.reason).toBe(ORGANIZER_MODEL_LOADING);
    expect(model.profileId).toBe('');
  });
});

describe('AI 整理模型：失效时提示修复，绝不静默换模型', () => {
  it('没有默认聊天模型时禁用入口并指向「模型设置」', () => {
    const model = pickOrganizerChatModel(catalog({ defaultChatProfileId: null }));
    expect(model.available).toBe(false);
    expect(model.profileId).toBe('');
    expect(model.reason).toContain('「模型设置」');
  });

  it('默认 profile 已不存在时不退回其他可用模型', () => {
    const model = pickOrganizerChatModel(
      catalog({
        defaultChatProfileId: 'p-chat-gone',
        // 目录里还有一个可用聊天模型：仍不得自动改用它
        profiles: [profile({ id: 'p-chat-other' })],
      }),
    );
    expect(model.available).toBe(false);
    expect(model.profileId).toBe('');
    expect(model.reason).toContain('p-chat-gone');
    expect(model.reason).toContain('不会自动改用其他模型');
  });

  it('用途不是聊天时拒绝', () => {
    const model = pickOrganizerChatModel(
      catalog({ profiles: [profile({ purpose: 'embedding' })] }),
    );
    expect(model.available).toBe(false);
    expect(model.reason).toContain('embedding');
    expect(model.reason).toContain('不会自动改用其他模型');
  });

  it('连接不可调用时带上服务端原因，并要求修复而不是换模型', () => {
    const model = pickOrganizerChatModel(
      catalog({
        connections: [
          connection({
            callable: false,
            callableReason: '该连接未保存凭证，请先填写 API Key。',
          }),
        ],
      }),
    );
    expect(model.available).toBe(false);
    expect(model.reason).toContain('该连接未保存凭证');
    expect(model.reason).toContain('不会自动改用其他模型');
  });

  it('目录缺少连接视图时退回与 /chat 相同的凭证判定', () => {
    // 摘要里 hasCredential=false（缺凭证的云连接）→ 与 /chat 一致判为不可用，而不是放行
    const withoutConnection = pickOrganizerChatModel(
      catalog({
        connections: [],
        profiles: [
          profile({
            connection: {
              displayName: 'DeepSeek 云端',
              providerId: 'deepseek',
              providerLabel: 'DeepSeek',
              protocol: 'openai-chat',
              apiFormat: 'auto',
              hasCredential: false,
            },
          }),
        ],
      }),
    );
    expect(withoutConnection.available).toBe(false);

    const withCredential = pickOrganizerChatModel(
      catalog({
        connections: [],
        profiles: [
          profile({
            connection: {
              displayName: '云端',
              providerId: 'deepseek',
              providerLabel: 'DeepSeek',
              protocol: 'openai-chat',
              apiFormat: 'auto',
              hasCredential: true,
            },
          }),
        ],
      }),
    );
    expect(withCredential.available).toBe(true);
  });

  it('按冻结的 profile id 解析（重试沿用同一个模型，与当前默认无关）', () => {
    const frozen = resolveOrganizerChatModel(
      catalog({ defaultChatProfileId: 'p-chat-2' }),
      'p-chat-1',
    );
    expect(frozen.available).toBe(true);
    expect(frozen.profileId).toBe('p-chat-1');

    const gone = resolveOrganizerChatModel(catalog(), 'p-chat-gone');
    expect(gone.available).toBe(false);
    expect(gone.reason).toContain('不会自动改用其他模型');
  });
});
