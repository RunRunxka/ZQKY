/**
 * 班级管理页（`/assessments/roster`，参考图布局，R5-FE 2026-10-11；R10-FE 2026-10-12 去归档）。
 *
 * 覆盖参考图要求的版面与不可回退的行为：
 * 操作行（新增学生 / 批量导入 / 批量删除）/ 搜索框 / 表格列（复选框 / 姓名 / 学号 / 性别 / 操作）/
 * 底部「共 N 条记录」+ 页码；读取失败显示错误码与重试而**不是**空名单；
 * 删除走 `DELETE /students/{id}?expectedRevision=N`：200 回执两模式（`deleted` 中性 /
 * `removed_with_history` info 提示「已移除并保留历史」）都原样展示，409 原样报错，
 * 删除后**班级列表与学生列表同时刷新**（人数即时正确）；
 * 编辑学生是模态表单 + 显式「保存」按钮（输入不即时提交、取消放弃修改）；
 * 页面没有归档/恢复入口，也不请求 archive/restore 端点。
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

describe('班级管理页：删除学生（DELETE 回执两模式，R10-FE）', () => {
  it('deleted 回执：DELETE 带 expectedRevision，展示服务端 message，并刷新班级与学生列表（人数即时正确）', async () => {
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    let deleted = false;
    let classCalls = 0;
    const fetchMock = stubApi((url, init) => {
      if (url.includes('/students/st-2') && (init.method ?? 'GET').toUpperCase() === 'DELETE') {
        expect(url).toContain('expectedRevision=1');
        deleted = true;
        return jsonResponse(true, 200, {
          mode: 'deleted',
          message: '学生已删除，班级归属记录一并移除。',
        });
      }
      if (url.includes('/classes/cls-1/students')) {
        const list = roster(2).filter((entry) => !(deleted && entry.id === 'st-2'));
        return jsonResponse(true, 200, { items: list, total: list.length, offset: 0, limit: 50 });
      }
      if (url.includes('/classes')) {
        classCalls += 1;
        return jsonResponse(true, 200, {
          items: [{ ...CLASS, studentCount: deleted ? 1 : 2 }],
          total: 1,
          offset: 0,
          limit: 200,
        });
      }
      return defaultHandler({ students: roster(2) })(url, init);
    });
    render(<RosterWorkspacePage />);
    await waitFor(() => expect(screen.getByText('学生02')).toBeInTheDocument());
    expect(screen.getByText('2 名学生')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('assessments-student-delete-st-2'));
    expect(confirmSpy).toHaveBeenCalledWith('删除学生「学生02」？若其有历史成绩将保留历史数据。');
    await waitFor(() =>
      expect(calls(fetchMock, '/students/st-2', 'DELETE')).toHaveLength(1),
    );
    const receipt = await screen.findByTestId('assessments-student-delete-receipt');
    expect(receipt).toHaveTextContent('学生已删除，班级归属记录一并移除。');
    expect(receipt).not.toHaveClass('info');

    // 删除后班级人数即时正确（班级列表与学生列表都被重新读取）
    await waitFor(() => expect(screen.getByText('1 名学生')).toBeInTheDocument());
    await waitFor(() => expect(screen.queryByText('学生02')).not.toBeInTheDocument());
    expect(calls(fetchMock, '/classes/cls-1/students').length).toBeGreaterThan(1);
    expect(classCalls).toBeGreaterThan(1);
  });

  it('removed_with_history 回执：info 样式提示「有历史成绩，已移除并保留历史」', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const fetchMock = stubApi((url, init) => {
      if (url.includes('/students/st-2') && (init.method ?? 'GET').toUpperCase() === 'DELETE') {
        return jsonResponse(true, 200, {
          mode: 'removed_with_history',
          message: '学生已从名单移除，历史成绩数据保留。',
        });
      }
      return defaultHandler({ students: roster(2) })(url, init);
    });
    render(<RosterWorkspacePage />);
    await waitFor(() => expect(screen.getByText('学生02')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('assessments-student-delete-st-2'));
    await waitFor(() =>
      expect(calls(fetchMock, '/students/st-2', 'DELETE')).toHaveLength(1),
    );
    const receipt = await screen.findByTestId('assessments-student-delete-receipt');
    expect(receipt).toHaveClass('info');
    expect(receipt).toHaveTextContent('有历史成绩，已移除并保留历史');
    expect(receipt).toHaveTextContent('学生已从名单移除，历史成绩数据保留。');
    // 历史模式也是成功：不显示错误区
    expect(screen.queryByTestId('assessments-roster-write-error')).not.toBeInTheDocument();
  });

  it('失败（409 REVISION_CONFLICT）：原样展示错误码与 message，不伪装成成功', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    stubApi((url, init) => {
      if (url.includes('/students/st-2') && (init.method ?? 'GET').toUpperCase() === 'DELETE') {
        return jsonResponse(false, 409, {
          code: 'REVISION_CONFLICT',
          message: '数据已被其他操作更新，请刷新后重试。',
        });
      }
      return defaultHandler({ students: roster(2) })(url, init);
    });
    render(<RosterWorkspacePage />);
    await waitFor(() => expect(screen.getByText('学生02')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('assessments-student-delete-st-2'));
    await waitFor(() =>
      expect(screen.getByTestId('assessments-roster-write-error')).toHaveTextContent(
        '删除学生失败（REVISION_CONFLICT）：数据已被其他操作更新，请刷新后重试。',
      ),
    );
    expect(screen.queryByTestId('assessments-student-delete-receipt')).not.toBeInTheDocument();
    expect(screen.getByText('学生02')).toBeInTheDocument();
  });

  it('批量删除逐人 DELETE，「未全部完成」时按人列出失败原因并保留未成功的选中', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const fetchMock = stubApi((url, init) => {
      if (url.includes('/students/st-1') && (init.method ?? 'GET').toUpperCase() === 'DELETE') {
        return jsonResponse(true, 200, { mode: 'deleted', message: '学生已删除。' });
      }
      if (url.includes('/students/st-2') && (init.method ?? 'GET').toUpperCase() === 'DELETE') {
        return jsonResponse(false, 409, {
          code: 'REVISION_CONFLICT',
          message: '数据已被其他操作更新，请刷新后重试。',
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
    expect(error).toHaveTextContent(
      '学生02（REVISION_CONFLICT：数据已被其他操作更新，请刷新后重试。）',
    );
    expect(error.textContent).toContain('成功 1 人；失败 1 人');
    // 成功者的回执照常展示；失败者保持选中（便于重试），不回显成"全部成功"
    expect(screen.getByTestId('assessments-student-delete-receipt')).toHaveTextContent(
      '学生已删除。',
    );
    // 刷新是异步的：等名单回来后核对失败者仍被选中
    await waitFor(() =>
      expect(screen.getByRole('checkbox', { name: '选择学生 学生02' })).toBeChecked(),
    );
    expect(calls(fetchMock, '/students/st-1', 'DELETE')).toHaveLength(1);
    expect(calls(fetchMock, '/students/st-2', 'DELETE')).toHaveLength(1);
  });
});

describe('班级管理页：编辑学生是显式保存（R10-FE）', () => {
  it('输入后不自动提交；点「保存」才 PATCH，成功后刷新名单并给出成功提示', async () => {
    const fetchMock = stubApi((url, init) => {
      if (url.includes('/students/st-1') && (init.method ?? 'GET').toUpperCase() === 'PATCH') {
        expect(JSON.parse(String(init.body))).toEqual({
          expectedRevision: 1,
          name: '张三三',
          studentNo: '0001',
        });
        return jsonResponse(true, 200, student({ name: '张三三' }));
      }
      return defaultHandler({ students: [student({ name: '张三' })] })(url, init);
    });
    render(<RosterWorkspacePage />);
    await waitFor(() => expect(screen.getByText('张三')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('assessments-student-edit-st-1'));
    const nameInput = await screen.findByLabelText('学生姓名');
    fireEvent.change(nameInput, { target: { value: '张三三' } });
    // 显式保存：输入与失焦都不提交
    expect(calls(fetchMock, '/students/st-1', 'PATCH')).toHaveLength(0);
    expect(screen.getByTestId('assessments-student-form-save')).toHaveTextContent('保存');

    fireEvent.click(screen.getByTestId('assessments-student-form-save'));
    await waitFor(() => expect(calls(fetchMock, '/students/st-1', 'PATCH')).toHaveLength(1));
    await waitFor(() =>
      expect(screen.getByTestId('assessments-roster-notice')).toHaveTextContent(
        '已保存学生「张三三」的信息。',
      ),
    );
    await waitFor(() =>
      expect(calls(fetchMock, '/classes/cls-1/students').length).toBeGreaterThan(1),
    );
  });

  it('取消放弃修改：不提交，重新打开显示服务端原值', async () => {
    const fetchMock = stubApi(defaultHandler({ students: [student({ name: '张三' })] }));
    render(<RosterWorkspacePage />);
    await waitFor(() => expect(screen.getByText('张三')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('assessments-student-edit-st-1'));
    fireEvent.change(await screen.findByLabelText('学生姓名'), {
      target: { value: '不该被保存' },
    });
    fireEvent.click(screen.getByRole('button', { name: '取消' }));
    expect(calls(fetchMock, '/students/st-1', 'PATCH')).toHaveLength(0);

    fireEvent.click(screen.getByTestId('assessments-student-edit-st-1'));
    expect(await screen.findByLabelText('学生姓名')).toHaveValue('张三');
  });
});

describe('班级管理页：没有归档/恢复入口（R10-FE 舍弃归档）', () => {
  it('不渲染已归档开关、归档/恢复按钮，也不请求 archive/restore 端点', async () => {
    const fetchMock = stubApi(defaultHandler());
    render(<RosterWorkspacePage />);
    await waitFor(() => expect(screen.getByText('学生01')).toBeInTheDocument());

    expect(screen.queryByLabelText('显示已归档班级')).not.toBeInTheDocument();
    expect(screen.queryByLabelText('显示已归档学生')).not.toBeInTheDocument();
    expect(screen.queryByTestId('assessments-class-archive-cls-1')).not.toBeInTheDocument();
    expect(screen.queryByTestId('assessments-class-restore-cls-1')).not.toBeInTheDocument();
    expect(screen.queryByText('归档班级')).not.toBeInTheDocument();
    expect(screen.queryByText('恢复')).not.toBeInTheDocument();
    expect(screen.queryByText('改为归档（不删除历史）')).not.toBeInTheDocument();
    expect(
      fetchMock.mock.calls.every(([url]) => {
        const text = String(url);
        return !text.includes('/archive') && !text.includes('/restore');
      }),
    ).toBe(true);
  });

  it('彻底删除班级 409 CLASS_IN_USE：逐项列出引用原因，且没有「改为归档」兜底', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const fetchMock = stubApi((url, init) => {
      if (url.includes('/classes/cls-1') && (init.method ?? 'GET').toUpperCase() === 'DELETE') {
        return jsonResponse(false, 409, {
          code: 'CLASS_IN_USE',
          message: '班级仍被施测或教案引用，不能删除。',
          details: { counts: { memberships: 12, assessments: 1 } },
        });
      }
      return defaultHandler()(url, init);
    });
    render(<RosterWorkspacePage />);
    await waitFor(() => expect(screen.getByText('学生01')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('assessments-class-delete-cls-1'));
    const guard = await screen.findByTestId('assessments-class-delete-guard');
    expect(guard).toHaveTextContent('CLASS_IN_USE');
    expect(guard).toHaveTextContent('班级归属记录 12 条');
    expect(guard).toHaveTextContent('参测范围引用 1 条');
    expect(within(guard).queryByText('改为归档（不删除历史）')).not.toBeInTheDocument();
    expect(calls(fetchMock, '/classes/cls-1', 'DELETE')).toHaveLength(1);
  });

  it('409 的引用清单分成两组：阻断项先说去处，随删级联项写明无需处理（R10-FE 2026-10-13）', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    stubApi((url, init) => {
      if (url.includes('/classes/cls-1') && (init.method ?? 'GET').toUpperCase() === 'DELETE') {
        return jsonResponse(false, 409, {
          code: 'CLASS_IN_USE',
          message: '班级仍被成绩链或教案引用，不能删除（班级教案 1 条）。',
          details: { counts: { memberships: 26, rosterImports: 1, lessonPlans: 1 } },
        });
      }
      return defaultHandler()(url, init);
    });
    render(<RosterWorkspacePage />);
    await waitFor(() => expect(screen.getByText('学生01')).toBeInTheDocument());

    fireEvent.click(screen.getByTestId('assessments-class-delete-cls-1'));
    const guard = await screen.findByTestId('assessments-class-delete-guard');
    // 阻断组：教案（并写明去教案工作台删）
    expect(guard).toHaveTextContent('必须先处置（它们挡住删除，且不随删除清掉）：');
    expect(guard).toHaveTextContent('班级教案（到教案工作台删除该教案后重试） 1 条');
    // 级联组：归属与名单批次（无需处理）
    expect(guard).toHaveTextContent('随删除一起清掉（无需先处理）：');
    expect(guard).toHaveTextContent('班级归属记录 26 条');
    expect(guard).toHaveTextContent('名单导入批次 1 条');
    expect(within(guard).getByLabelText('阻断删除的引用')).toBeInTheDocument();
    expect(within(guard).getByLabelText('随删除清掉的引用')).toBeInTheDocument();
  });
});
