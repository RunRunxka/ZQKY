/**
 * 班级管理页（`/assessments/roster`，参考图布局，R5-FE 2026-10-11）。
 *
 * 覆盖参考图要求的版面与不可回退的行为：
 * 操作行（新增学生 / 批量导入 / 批量删除）/ 搜索框 / 表格列（复选框 / 姓名 / 学号 / 性别 / 操作）/
 * 底部「共 N 条记录」+ 页码；读取失败显示错误码与重试而**不是**空名单；
 * 删除走归档接口（POST /students/{id}/archive），批量删除逐人归档并把失败原因原样列出。
 */

import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import type { ClassView, StudentView } from '@/contracts/roster';
import { RosterWorkspacePage } from './RosterWorkspacePage';

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

const CLASS: ClassView = {
  id: 'cls-1',
  code: 'G7-01',
  name: '七年一班',
  schoolYear: '2026',
  gradeId: 'g7',
  status: 'active',
  revision: 2,
  studentCount: 12,
  createdAt: '2026-09-01T00:00:00Z',
};

function student(overrides: Partial<StudentView> = {}): StudentView {
  return {
    id: 'st-1',
    studentNo: '0001',
    name: '张三',
    status: 'active',
    revision: 1,
    memberships: [],
    createdAt: '2026-09-01T00:00:00Z',
    ...overrides,
  };
}

function roster(count: number): StudentView[] {
  return Array.from({ length: count }, (_, index) =>
    student({
      id: `st-${index + 1}`,
      name: `学生${String(index + 1).padStart(2, '0')}`,
      studentNo: String(index + 1).padStart(4, '0'),
    }),
  );
}

function defaultHandler(options: { students?: StudentView[]; studentsStatus?: number } = {}): Handler {
  const list = options.students ?? roster(3);
  return (url) => {
    if (url.includes('/textbook-taxonomy')) {
      return jsonResponse(true, 200, {
        stages: [{ id: 'stage-j', label: '初中' }],
        grades: [{ id: 'g7', label: '七年级', stageId: 'stage-j' }],
        subjects: [{ id: 'math', label: '数学' }],
        editions: [{ id: 'rj', label: '人教版' }],
      });
    }
    if (url.includes('/classes/cls-1/students')) {
      if (options.studentsStatus && options.studentsStatus >= 400) {
        return jsonResponse(false, options.studentsStatus, {
          code: 'SERVICE_UNAVAILABLE',
          message: '后端服务不可用。',
          retryable: true,
        });
      }
      return jsonResponse(true, 200, { items: list, total: list.length, offset: 0, limit: 50 });
    }
    if (url.includes('/classes')) {
      return jsonResponse(true, 200, { items: [CLASS], total: 1, offset: 0, limit: 200 });
    }
    return jsonResponse(false, 404, { code: 'NOT_FOUND', message: `未 mock：${url}` });
  };
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

describe('班级管理页：学生列表版面（参考图）', () => {
  it('渲染标题、班级选择、操作行、搜索框与表头列', async () => {
    stubApi(defaultHandler());
    render(<RosterWorkspacePage />);
    expect(screen.getByRole('heading', { level: 1, name: '班级管理' })).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole('combobox', { name: '当前班级' })).toHaveValue('cls-1'),
    );

    expect(screen.getByTestId('assessments-student-add')).toHaveTextContent('新增学生');
    expect(screen.getByTestId('assessments-student-import')).toHaveTextContent('批量导入');
    expect(screen.getByTestId('assessments-student-batch-delete')).toHaveTextContent('批量删除');
    // 未选中任何学生时批量删除不可用（避免误伤整班）
    expect(screen.getByTestId('assessments-student-batch-delete')).toBeDisabled();
    expect(screen.getByPlaceholderText('搜索学生姓名')).toBeInTheDocument();

    const table = await screen.findByRole('table');
    for (const column of ['姓名', '学号', '性别', '操作']) {
      expect(within(table).getByRole('columnheader', { name: column })).toBeInTheDocument();
    }
    expect(within(table).getByRole('checkbox', { name: '全选本页学生' })).toBeInTheDocument();
  });

  it('性别列在后端未提供时显示「未记录」，不猜造', async () => {
    stubApi(defaultHandler({ students: [student({ name: '张三' })] }));
    render(<RosterWorkspacePage />);
    await waitFor(() => expect(screen.getByText('张三')).toBeInTheDocument());
    const row = screen.getByTestId('assessments-student-st-1');
    expect(within(row).getByText('未记录')).toBeInTheDocument();
    expect(within(row).getByText('0001')).toBeInTheDocument();
  });

  it('底部「共 N 条记录」+ 翻页：每页 10 条', async () => {
    stubApi(defaultHandler({ students: roster(12) }));
    render(<RosterWorkspacePage />);
    await waitFor(() =>
      expect(screen.getByTestId('assessments-students-total')).toHaveTextContent('共 12 条记录'),
    );
    expect(screen.getByTestId('assessments-students-page')).toHaveTextContent('第 1 / 2 页');
    expect(screen.getByText('学生10')).toBeInTheDocument();
    expect(screen.queryByText('学生11')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '下一页' }));
    expect(screen.getByTestId('assessments-students-page')).toHaveTextContent('第 2 / 2 页');
    expect(screen.getByText('学生11')).toBeInTheDocument();
    expect(screen.queryByText('学生10')).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: '上一页' }));
    expect(screen.getByTestId('assessments-students-page')).toHaveTextContent('第 1 / 2 页');
  });

  it('搜索按姓名过滤并回到第 1 页；无命中给出说明', async () => {
    stubApi(defaultHandler({ students: roster(12) }));
    render(<RosterWorkspacePage />);
    await waitFor(() => expect(screen.getByText('学生01')).toBeInTheDocument());
    fireEvent.click(screen.getByRole('button', { name: '下一页' }));

    fireEvent.change(screen.getByPlaceholderText('搜索学生姓名'), {
      target: { value: '学生03' },
    });
    expect(screen.getByTestId('assessments-students-total')).toHaveTextContent('共 1 条记录');
    expect(screen.getByTestId('assessments-students-page')).toHaveTextContent('第 1 / 1 页');
    expect(screen.getByText('学生03')).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText('搜索学生姓名'), {
      target: { value: '不存在的人' },
    });
    expect(screen.getByTestId('assessments-students-no-match')).toHaveTextContent('没有姓名匹配');
  });
});

describe('班级管理页：失败与空态不能互相伪装', () => {
  it('学生名单读取失败：显示错误码与重试，不显示空名单', async () => {
    stubApi(defaultHandler({ studentsStatus: 503 }));
    render(<RosterWorkspacePage />);
    await waitFor(() =>
      expect(screen.getByTestId('assessments-students-error')).toHaveTextContent(
        'SERVICE_UNAVAILABLE',
      ),
    );
    expect(screen.getByTestId('assessments-students-error')).toHaveTextContent('这不是空名单');
    expect(screen.queryByTestId('assessments-students-empty')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: '重试读取名单' })).toBeInTheDocument();
  });

  it('班级为空：给出新建提示，不显示学生表', async () => {
    stubApi((url) => {
      if (url.includes('/textbook-taxonomy')) {
        return jsonResponse(true, 200, {
          stages: [],
          grades: [],
          subjects: [],
          editions: [],
        });
      }
      if (url.includes('/classes')) {
        return jsonResponse(true, 200, { items: [], total: 0, offset: 0, limit: 200 });
      }
      return jsonResponse(false, 404, { code: 'NOT_FOUND', message: url });
    });
    render(<RosterWorkspacePage />);
    await waitFor(() =>
      expect(screen.getByTestId('assessments-classes-empty')).toHaveTextContent('还没有班级'),
    );
    expect(screen.getByTestId('assessments-students-no-class')).toBeInTheDocument();
    expect(screen.queryByRole('table')).not.toBeInTheDocument();
  });
});

describe('班级管理页：删除是归档（可恢复）而不是抹除历史', () => {
  it('行「删除」二次确认后调用归档接口并刷新名单', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const fetchMock = stubApi((url, init) => {
      if (url.includes('/students/st-2/archive')) {
        expect(init.method).toBe('POST');
        expect(JSON.parse(String(init.body))).toEqual({ expectedRevision: 1 });
        return jsonResponse(true, 200, student({ id: 'st-2', status: 'archived' }));
      }
      return defaultHandler({ students: roster(2) })(url, init);
    });
    render(<RosterWorkspacePage />);
    await waitFor(() => expect(screen.getByText('学生02')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('assessments-student-delete-st-2'));
    await waitFor(() =>
      expect(calls(fetchMock, '/students/st-2/archive', 'POST')).toHaveLength(1),
    );
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('归档'));
    await waitFor(() =>
      expect(screen.getByTestId('assessments-roster-notice')).toHaveTextContent('已删除（归档）'),
    );
    // 归档成功后重新读取名单（真实状态来自后端）
    await waitFor(() =>
      expect(calls(fetchMock, '/classes/cls-1/students').length).toBeGreaterThan(1),
    );
  });

  it('批量删除对选中行逐人归档，「未全部完成」时按人列出失败原因', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const fetchMock = stubApi((url, init) => {
      if (url.includes('/students/st-1/archive')) {
        return jsonResponse(true, 200, student({ id: 'st-1', status: 'archived' }));
      }
      if (url.includes('/students/st-2/archive')) {
        return jsonResponse(false, 409, {
          code: 'STUDENT_IN_USE',
          message: '该学生已被施测参测记录引用。',
        });
      }
      return defaultHandler({ students: roster(2) })(url, init);
    });
    render(<RosterWorkspacePage />);
    await waitFor(() => expect(screen.getByText('学生01')).toBeInTheDocument());

    fireEvent.click(screen.getByRole('checkbox', { name: '全选本页学生' }));
    const batch = screen.getByTestId('assessments-student-batch-delete');
    expect(batch).toHaveTextContent('批量删除（2）');
    fireEvent.click(batch);

    await waitFor(() =>
      expect(screen.getByTestId('assessments-roster-write-error')).toHaveTextContent(
        '批量删除未全部完成',
      ),
    );
    const error = screen.getByTestId('assessments-roster-write-error');
    expect(error).toHaveTextContent('学生02（STUDENT_IN_USE：该学生已被施测参测记录引用。）');
    expect(error.textContent).toContain('成功 1 人；失败 1 人');
    expect(calls(fetchMock, '/students/st-1/archive', 'POST')).toHaveLength(1);
    expect(calls(fetchMock, '/students/st-2/archive', 'POST')).toHaveLength(1);
  });
});
