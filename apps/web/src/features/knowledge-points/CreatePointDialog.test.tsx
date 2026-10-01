import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { CreatePointDialog } from './CreatePointDialog';

function json(ok: boolean, status: number, body: unknown): Response {
  return { ok, status, json: async () => body } as Response;
}

function stubApi(handler: (url: string, init: RequestInit) => Response | Promise<Response>) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(handler(typeof input === 'string' ? input : input.toString(), init ?? {})),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

beforeAll(() => {
  HTMLDialogElement.prototype.showModal = function showModal() {
    this.open = true;
  };
  HTMLDialogElement.prototype.close = function close() {
    this.open = false;
  };
});

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('新建知识点对话框', () => {
  it('表单控件的可访问名称互不相同（编码 与 父级编码 必须可区分）', async () => {
    stubApi(() => json(true, 201, {}));
    render(
      <CreatePointDialog
        subjects={[{ id: 'math', label: '数学' }]}
        taxonomyReady
        defaultSubjectId="math"
        onClose={vi.fn()}
        onCreated={vi.fn()}
      />,
    );

    const dialog = await screen.findByRole('dialog', { name: '新建知识点' });
    // e2e 用 name 子串匹配定位，这里锁定「每个控件恰好一个可访问名称、且 编码 ≠ 父级编码」
    const code = within(dialog).getByRole('textbox', { name: '编码' });
    const parentCode = within(dialog).getByRole('textbox', { name: '父级编码' });
    expect(code).toHaveAccessibleName('编码');
    expect(parentCode).toHaveAccessibleName('父级编码');
    expect(code).not.toBe(parentCode);
    expect(within(dialog).getByRole('textbox', { name: '名称' })).toHaveAccessibleName('名称');
    expect(within(dialog).getByRole('combobox', { name: '学科' })).toHaveAccessibleName('学科');
  });

  it('建立请求只带填写的字段；成功后把新对象交给调用方', async () => {
    const created = {
      id: 'kp-9',
      subjectId: 'math',
      code: 'M.7.5',
      name: '绝对值',
      description: '',
      parentId: null,
      parentCode: null,
      sortOrder: 0,
      status: 'active',
      revision: 1,
      revisionId: 'kr-9',
      version: 1,
      aliases: [],
      createdAt: '2026-09-30T00:00:00Z',
    };
    const fetchMock = stubApi(() => json(true, 201, created));
    const onCreated = vi.fn();
    render(
      <CreatePointDialog
        subjects={[{ id: 'math', label: '数学' }]}
        taxonomyReady
        defaultSubjectId="math"
        onClose={vi.fn()}
        onCreated={onCreated}
      />,
    );

    const dialog = await screen.findByRole('dialog', { name: '新建知识点' });
    fireEvent.change(within(dialog).getByRole('textbox', { name: '编码' }), {
      target: { value: 'M.7.5' },
    });
    fireEvent.change(within(dialog).getByRole('textbox', { name: '名称' }), {
      target: { value: '绝对值' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: /建立知识点/ }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith(created));
    const init = fetchMock.mock.calls[0]?.[1] as RequestInit;
    expect(JSON.parse(String(init.body))).toEqual({
      subjectId: 'math',
      code: 'M.7.5',
      name: '绝对值',
    });
  });

  it('409 编码冲突原样显示并保留输入，不静默改写编码', async () => {
    stubApi(() =>
      json(false, 409, {
        code: 'KNOWLEDGE_CODE_CONFLICT',
        message: '该学科内编码已存在。',
        retryable: false,
      }),
    );
    render(
      <CreatePointDialog
        subjects={[{ id: 'math', label: '数学' }]}
        taxonomyReady
        defaultSubjectId="math"
        onClose={vi.fn()}
        onCreated={vi.fn()}
      />,
    );

    const dialog = await screen.findByRole('dialog', { name: '新建知识点' });
    fireEvent.change(within(dialog).getByRole('textbox', { name: '编码' }), {
      target: { value: 'M.7.1' },
    });
    fireEvent.change(within(dialog).getByRole('textbox', { name: '名称' }), {
      target: { value: '有理数' },
    });
    fireEvent.click(within(dialog).getByRole('button', { name: /建立知识点/ }));

    const alert = await screen.findByRole('alert');
    expect(alert).toHaveTextContent('KNOWLEDGE_CODE_CONFLICT');
    expect(alert).toHaveTextContent('编码已存在');
    expect(within(dialog).getByRole('textbox', { name: '编码' })).toHaveValue('M.7.1');
  });
});
