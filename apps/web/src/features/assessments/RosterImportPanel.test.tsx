/**
 * 名单导入与校对面板（R5-FE 取回）的关键红线单测：
 *
 * - 上传只产生批次与预览行，**不写学生**；确认前每一行都必须有明确处理方式；
 * - 确认是逻辑确认（冻结 `submissionId` + 原样载荷）：结果未知时重试复用同一标识，
 *   不会因为重试而重复入库；
 * - 读取/确认失败原样显示 `code` / `message` / `details.issues`（含行号），不吞原因。
 */

import { afterEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { RosterImportView } from '@/contracts/roster';
import { RosterImportPanel } from './RosterImportPanel';

type Handler = (url: string, init: RequestInit) => Response | Promise<Response>;

function jsonResponse(ok: boolean, status: number, body: unknown): Response {
  return { ok, status, json: async () => body } as Response;
}

function stubApi(handler: Handler) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(handler(typeof input === 'string' ? input : input.toString(), init ?? {})),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function calls(fetchMock: ReturnType<typeof stubApi>, fragment: string, method?: string) {
  return fetchMock.mock.calls.filter(([url, init]) => {
    const request = init as RequestInit | undefined;
    return (
      String(url).includes(fragment) &&
      (method === undefined || (request?.method ?? 'GET').toUpperCase() === method)
    );
  });
}

/** 两行名单：第 1 行自动新建；第 2 行同名冲突，必须人工选择。 */
const IMPORT: RosterImportView = {
  importId: 'imp-1',
  classId: 'cls-1',
  className: '七年一班',
  state: 'reviewing',
  revision: 3,
  fileAsset: {
    assetId: 'asset-1',
    kind: 'roster',
    blobKey: 'blob-1',
    sha256: 'sha',
    mediaType: 'text/csv',
    byteSize: 10,
    originalName: '七年一班名单.csv',
  },
  headers: ['姓名', '学号'],
  mapping: { name: '姓名', studentNo: '学号' },
  warnings: [],
  issues: [],
  rows: [
    {
      rowNo: 2,
      name: '张三',
      studentNo: '0001',
      matchedStudentId: null,
      matchedStudentName: null,
      suggestion: 'create',
      decision: null,
      issues: [],
    },
    {
      rowNo: 3,
      name: '李四',
      studentNo: '0002',
      matchedStudentId: null,
      matchedStudentName: null,
      suggestion: 'conflict',
      decision: null,
      issues: [{ code: 'ROSTER_NAME_CONFLICT', message: '同名命中多个学生，需要人工选择。' }],
    },
  ],
  createdAt: '2026-10-01T00:00:00Z',
  updatedAt: '2026-10-01T00:00:00Z',
};

function baseHandler(onConfirm?: Handler): Handler {
  return (url, init) => {
    const method = (init.method ?? 'GET').toUpperCase();
    if (url.includes('/roster-imports/imp-1/confirm')) {
      return onConfirm ? onConfirm(url, init) : jsonResponse(true, 200, {
        importId: 'imp-1',
        state: 'confirmed',
        applied: [{ rowNo: 2, studentId: 'st-1', membershipId: 'm-1', createdStudent: true, createdMembership: true }],
        ignored: [],
        replayed: false,
      });
    }
    if (url.includes('/roster-imports') && method === 'POST' && url.includes('/classes/')) {
      return jsonResponse(true, 201, IMPORT);
    }
    if (url.includes('/roster-imports')) {
      return jsonResponse(true, 200, { items: [], total: 0, offset: 0, limit: 100 });
    }
    if (url.includes('/students')) {
      return jsonResponse(true, 200, { items: [], total: 0, offset: 0, limit: 100 });
    }
    return jsonResponse(false, 404, { code: 'NOT_FOUND', message: `未 mock：${url}` });
  };
}

async function uploadAndOpen() {
  const file = new File(['姓名,学号\n张三,0001\n'], '七年一班名单.csv', { type: 'text/csv' });
  fireEvent.change(screen.getByLabelText('名单文件'), { target: { files: [file] } });
  fireEvent.click(screen.getByRole('button', { name: '上传名单' }));
  await waitFor(() => expect(screen.getByTestId('roster-row-3')).toBeInTheDocument());
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe('名单导入：上传 → 审阅行 → 确认落库', () => {
  it('上传后逐行给出处理计划；异常行未选择前不能确认', async () => {
    const fetchMock = stubApi(baseHandler());
    render(<RosterImportPanel classId="cls-1" onChanged={vi.fn()} />);
    await uploadAndOpen();

    expect(screen.getByTestId('roster-row-2-decision')).toHaveTextContent('将新建学生');
    expect(screen.getByTestId('roster-row-3-decision')).toHaveTextContent('需要你选择');
    expect(screen.getByTestId('roster-pending-hint')).toHaveTextContent('还有 1 行需要先选择处理方式：第 3 行');

    const confirmButton = screen.getByRole('button', { name: '确认名单' });
    expect(confirmButton).toBeDisabled();
    // 上传不写学生：没有任何 /students POST
    expect(calls(fetchMock, '/students', 'POST')).toHaveLength(0);

    fireEvent.change(screen.getByLabelText('第 3 行处理'), { target: { value: 'ignore' } });
    await waitFor(() =>
      expect(screen.getByRole('button', { name: '确认名单' })).not.toBeDisabled(),
    );
  });

  it('确认携带 submissionId 与逐行人工决定；成功后回调刷新', async () => {
    const onChanged = vi.fn();
    const fetchMock = stubApi(baseHandler());
    render(<RosterImportPanel classId="cls-1" onChanged={onChanged} />);
    await uploadAndOpen();

    fireEvent.change(screen.getByLabelText('第 3 行处理'), { target: { value: 'ignore' } });
    await waitFor(() =>
      expect(screen.getByRole('button', { name: '确认名单' })).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByRole('button', { name: '确认名单' }));

    await waitFor(() => expect(calls(fetchMock, '/roster-imports/imp-1/confirm', 'POST')).toHaveLength(1));
    const body: {
      submissionId: string;
      expectedRevision: number;
      identityMatches: unknown;
    } = JSON.parse(
      String(calls(fetchMock, '/roster-imports/imp-1/confirm', 'POST')[0]?.[1]?.body),
    );
    expect(typeof body.submissionId).toBe('string');
    expect(body.expectedRevision).toBe(3);
    expect(body.identityMatches).toEqual([{ rowNo: 3, action: 'ignore', studentId: null }]);
    await waitFor(() => expect(onChanged).toHaveBeenCalled());
  });

  it('结果未知（拿不到响应）后重试复用同一 submissionId', async () => {
    let attempt = 0;
    const seen: string[] = [];
    const fetchMock = stubApi((url, init) => {
      if (url.includes('/roster-imports/imp-1/confirm')) {
        attempt += 1;
        seen.push(JSON.parse(String(init.body)).submissionId);
        if (attempt === 1) throw new Error('network down');
        return jsonResponse(true, 200, {
          importId: 'imp-1',
          state: 'confirmed',
          applied: [],
          ignored: [3],
          replayed: false,
        });
      }
      return baseHandler()(url, init);
    });
    render(<RosterImportPanel classId="cls-1" onChanged={vi.fn()} />);
    await uploadAndOpen();

    fireEvent.change(screen.getByLabelText('第 3 行处理'), { target: { value: 'ignore' } });
    await waitFor(() =>
      expect(screen.getByRole('button', { name: '确认名单' })).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByRole('button', { name: '确认名单' }));
    await waitFor(() =>
      expect(screen.getByText(/可能已写入也可能未写入/)).toBeInTheDocument(),
    );
    // 结果未知时冻结校对，按钮改为「确认名单」（重试同一逻辑确认）
    expect(screen.getByRole('button', { name: '确认名单' })).not.toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: '确认名单' }));
    await waitFor(() => expect(calls(fetchMock, '/confirm', 'POST')).toHaveLength(2));
    expect(seen[1]).toBe(seen[0]);
  });

  it('行级 422：逐行显示错误码与行号，输入保留', async () => {
    stubApi((url, init) => {
      if (url.includes('/roster-imports/imp-1') && (init.method ?? 'GET') === 'PATCH') {
        return jsonResponse(false, 422, {
          code: 'ROSTER_ROW_INVALID',
          message: '第 3 行的姓名超过长度上限。',
          details: {
            issues: [{ row: 3, column: '姓名', code: 'ROSTER_ROW_INVALID', message: '姓名超过 120 字。' }],
          },
        });
      }
      return baseHandler()(url, init);
    });
    render(<RosterImportPanel classId="cls-1" onChanged={vi.fn()} />);
    await uploadAndOpen();

    fireEvent.change(screen.getByLabelText('第 3 行处理'), { target: { value: 'create' } });
    await waitFor(() =>
      expect(screen.getByRole('button', { name: '保存映射与行决策' })).not.toBeDisabled(),
    );
    fireEvent.click(screen.getByRole('button', { name: '保存映射与行决策' }));

    const error = await screen.findByTestId('roster-import-error');
    expect(error).toHaveTextContent('ROSTER_ROW_INVALID');
    expect(error).toHaveTextContent('数据第 3 行 姓名：姓名超过 120 字。');
    expect(error).toHaveTextContent('输入已保留');
  });
});
