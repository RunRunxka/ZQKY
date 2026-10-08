import { StrictMode } from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import type { RosterImportView, StudentView } from '@/contracts/roster';
import { RosterImportPanel } from './RosterImportPanel';
import { RosterPanel } from './RosterPanel';

const CLASSES = [
  {
    id: 'class-a',
    code: 'A',
    name: '七一班',
    schoolYear: '2026',
    gradeId: 'grade-7',
    revision: 1,
    status: 'active',
    studentCount: 1,
    createdAt: '2026-10-02',
  },
  {
    id: 'class-b',
    code: 'B',
    name: '七二班',
    schoolYear: '2026',
    gradeId: 'grade-7',
    revision: 1,
    status: 'active',
    studentCount: 0,
    createdAt: '2026-10-02',
  },
];
const STUDENT: StudentView = {
  id: 'student-old',
  name: '甲',
  studentNo: '0012',
  revision: 4,
  status: 'active',
  createdAt: '2026-01-01',
  memberships: [
    {
      membershipId: 'membership-old',
      classId: 'class-a',
      className: '七一班',
      joinedOn: '2026-09-01',
      leftOn: null,
    },
  ],
};

function batch(overrides: Partial<RosterImportView> = {}): RosterImportView {
  return {
    importId: 'import-1',
    classId: 'class-a',
    className: '七一班',
    state: 'reviewing',
    revision: 1,
    fileAsset: {
      assetId: 'asset-1',
      kind: 'roster',
      blobKey: `blobs/${'a'.repeat(64)}`,
      sha256: 'a'.repeat(64),
      mediaType: 'text/csv',
      byteSize: 20,
      originalName: '名单.csv',
    },
    headers: ['学号', '姓名', '别名'],
    mapping: { studentNo: '学号', name: '姓名' },
    warnings: [],
    issues: [],
    rows: [
      {
        rowNo: 1,
        name: '甲',
        studentNo: '0012',
        matchedStudentId: 'student-old',
        matchedStudentName: '甲',
        suggestion: 'link',
        decision: null,
        issues: [],
      },
      {
        rowNo: 2,
        name: '乙',
        studentNo: '0013',
        matchedStudentId: null,
        matchedStudentName: null,
        suggestion: 'create',
        decision: null,
        issues: [],
      },
      {
        rowNo: 3,
        name: '同名',
        studentNo: null,
        matchedStudentId: null,
        matchedStudentName: null,
        suggestion: 'no_student_no',
        decision: null,
        issues: [],
      },
    ],
    createdAt: '2026-10-02',
    updatedAt: '2026-10-02',
    ...overrides,
  };
}

function response(body: unknown, status = 200): Response {
  return { ok: status < 400, status, json: async () => body } as Response;
}
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((finish) => {
    resolve = finish;
  });
  return { promise, resolve };
}
function stub(handler?: (url: string, init: RequestInit) => Response | Promise<Response> | null) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL, request?: RequestInit) => {
    const url = String(input);
    const init = request ?? {};
    const handled = handler?.(url, init);
    if (handled) return handled;
    if (url.includes('/roster-imports?'))
      return response({
        items: [
          {
            importId: 'import-1',
            classId: 'class-a',
            state: 'reviewing',
            revision: 1,
            rowCount: 3,
            blockingIssueCount: 0,
          },
        ],
        total: 1,
        offset: 0,
        limit: 100,
      });
    if (url.includes('/roster-imports/import-1') && !init.method) return response(batch());
    if (url.includes('/students'))
      return response({ items: [STUDENT], total: 1, offset: 0, limit: 100 });
    if (url.includes('/classes'))
      return response({ items: CLASSES, total: 2, offset: 0, limit: 100 });
    if (url.endsWith('/textbook-taxonomy'))
      return response({ stages: [], grades: [], subjects: [], editions: [] });
    return response({ code: 'UNEXPECTED_REQUEST', message: url }, 500);
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}
function requests(fetchMock: ReturnType<typeof stub>, method: string) {
  return fetchMock.mock.calls.filter(([, init]) => init?.method === method);
}
function formFile(name = '名单.csv') {
  fireEvent.change(screen.getByLabelText('名单文件'), {
    target: {
      files: [new File(['学号,姓名\n0012,甲'], name)],
    },
  });
}
async function restore() {
  fireEvent.click(await screen.findByTestId('roster-batch-import-1'));
  await screen.findByLabelText('第 1 行处理');
}
function chooseRows() {
  fireEvent.change(screen.getByLabelText('第 1 行处理'), { target: { value: 'link' } });
  fireEvent.change(screen.getByLabelText('第 2 行处理'), { target: { value: 'create' } });
  fireEvent.change(screen.getByLabelText('第 3 行处理'), { target: { value: 'ignore' } });
}
const CONFIRMED = {
  importId: 'import-1',
  state: 'confirmed',
  applied: [{ rowNo: 1 }, { rowNo: 2 }],
  ignored: [3],
  replayed: false,
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe('名单导入的真实客户端与人工身份选择', () => {
  it('CSV 上传→显式link/create/ignore→保存→幂等确认；学号保留前导零', async () => {
    let current = batch();
    const fetchMock = stub((url, init) => {
      if (init.method === 'POST' && url.endsWith('/roster-imports')) return response(current, 201);
      if (init.method === 'PATCH') {
        const payload = JSON.parse(String(init.body));
        current = batch({
          revision: 2,
          rows: current.rows.map((row) => ({
            ...row,
            decision: payload.rows.find((item: { rowNo: number }) => item.rowNo === row.rowNo)
              .decision,
          })),
        });
        return response(current);
      }
      if (url.endsWith('/confirm')) return response(CONFIRMED);
      return null;
    });
    const changed = vi.fn();
    render(
      <StrictMode>
        <RosterImportPanel classId="class-a" onChanged={changed} />
      </StrictMode>,
    );
    formFile();
    fireEvent.click(screen.getByRole('button', { name: '上传名单' }));
    await screen.findByLabelText('第 1 行处理');
    const uploaded = requests(fetchMock, 'POST')[0][1]!.body as FormData;
    expect(uploaded.get('file')).toBeInstanceOf(File);
    expect(screen.getByTestId('roster-row-1')).toHaveTextContent('学号 0012');
    expect(screen.getByRole('button', { name: '确认名单' })).toBeDisabled();
    chooseRows();
    fireEvent.click(screen.getByRole('button', { name: '保存映射与行决策' }));
    await screen.findByText('已保存映射与行决策（版本 2）。');
    expect(JSON.parse(String(requests(fetchMock, 'PATCH')[0][1]!.body))).toMatchObject({
      expectedRevision: 1,
      rows: [
        { rowNo: 1, decision: 'link', studentId: 'student-old' },
        { rowNo: 2, decision: 'create' },
        { rowNo: 3, decision: 'ignore' },
      ],
    });
    fireEvent.click(screen.getByRole('button', { name: '确认名单' }));
    await screen.findByTestId('roster-import-result');
    const confirmation = JSON.parse(String(requests(fetchMock, 'POST').at(-1)![1]!.body));
    expect(confirmation).toMatchObject({
      expectedRevision: 2,
      identityMatches: [
        { rowNo: 1, action: 'link', studentId: 'student-old' },
        { rowNo: 2, action: 'create', studentId: null },
        { rowNo: 3, action: 'ignore', studentId: null },
      ],
    });
    expect(confirmation.submissionId).toMatch(/^[a-f0-9-]{36}$/);
    expect(changed).toHaveBeenCalledTimes(1);
  });

  it('XLSX 工作表和人工表头随multipart上传；读取既有批次不重复上传', async () => {
    const fetchMock = stub((url, init) =>
      init.method === 'POST' && url.endsWith('/roster-imports') ? response(batch(), 201) : null,
    );
    render(<RosterImportPanel classId="class-a" onChanged={() => {}} />);
    formFile('名单.xlsx');
    fireEvent.change(screen.getByLabelText('名单工作表名'), { target: { value: '七年级' } });
    fireEvent.change(screen.getByLabelText('上传时姓名表头'), { target: { value: '学生称呼' } });
    fireEvent.change(screen.getByLabelText('上传时学号表头'), { target: { value: '身份代号' } });
    fireEvent.click(screen.getByRole('button', { name: '上传名单' }));
    await screen.findByLabelText('第 1 行处理');
    const form = requests(fetchMock, 'POST')[0][1]!.body as FormData;
    expect(form.get('sheetName')).toBe('七年级');
    expect(JSON.parse(String(form.get('mappingJson')))).toEqual({
      name: '学生称呼',
      studentNo: '身份代号',
    });
    await restore();
    expect(requests(fetchMock, 'POST')).toHaveLength(1);
    expect(screen.getByLabelText('第 2 行处理')).toHaveValue('');
  });

  it.each([409, 422])('保存遇%d保留映射与行编辑，并可刷新版本对照后重试', async (status) => {
    let reads = 0;
    const fetchMock = stub((url, init) => {
      if (init.method === 'PATCH')
        return response(
          {
            code: status === 409 ? 'REVISION_CONFLICT' : 'ROSTER_ROW_INVALID',
            message: '请核对',
            details: {
              currentRevision: 7,
              issues: [
                {
                  row: 2,
                  field: 'name',
                  code: 'ROSTER_ROW_INVALID',
                  message: '姓名需核对',
                  severity: 'blocking',
                },
              ],
            },
          },
          status,
        );
      if (url.includes('/roster-imports/import-1') && !init.method) {
        reads += 1;
        return response(batch({ revision: reads > 1 ? 7 : 1 }));
      }
      return null;
    });
    render(<RosterImportPanel classId="class-a" onChanged={() => {}} />);
    await restore();
    chooseRows();
    fireEvent.change(screen.getByLabelText('名单姓名列'), { target: { value: '别名' } });
    fireEvent.click(screen.getByRole('button', { name: '保存映射与行决策' }));
    await screen.findByRole('alert');
    expect(screen.getByLabelText('名单姓名列')).toHaveValue('别名');
    expect(screen.getByLabelText('第 2 行处理')).toHaveValue('create');
    expect(screen.getByRole('alert')).toHaveTextContent('数据第 2 行 name：姓名需核对');
    fireEvent.click(screen.getByRole('button', { name: '刷新版本对照（保留校对）' }));
    await screen.findByText('已读取最新版本，映射和行校对输入保留，请对照后再提交。');
    fireEvent.click(screen.getByRole('button', { name: '保存映射与行决策' }));
    await waitFor(() => expect(requests(fetchMock, 'PATCH')).toHaveLength(2));
    expect(JSON.parse(String(requests(fetchMock, 'PATCH')[1][1]!.body)).expectedRevision).toBe(7);
  });

  it('确认网络结果未知时冻结校对，重放原submissionId及原payload', async () => {
    let confirms = 0;
    const fetchMock = stub((url) => {
      if (url.endsWith('/confirm')) {
        confirms += 1;
        return confirms === 1
          ? Promise.reject(new TypeError('network disconnected'))
          : response({ ...CONFIRMED, replayed: true });
      }
      return null;
    });
    const changed = vi.fn();
    render(<RosterImportPanel classId="class-a" onChanged={changed} />);
    await restore();
    chooseRows();
    fireEvent.click(screen.getByRole('button', { name: '确认名单' }));
    await screen.findByText(/校对已冻结/);
    expect(screen.getByLabelText('第 2 行处理')).toBeDisabled();
    fireEvent.click(screen.getByRole('button', { name: '确认名单' }));
    await screen.findByTestId('roster-import-result');
    expect(requests(fetchMock, 'POST')[1][1]!.body).toBe(requests(fetchMock, 'POST')[0][1]!.body);
    expect(changed).toHaveBeenCalledTimes(1);
  });

  it.each(['success', 'failure'] as const)('切班后上传迟到%s不带入新班批次', async (outcome) => {
    const gate = deferred<Response>();
    stub((url, init) =>
      init.method === 'POST' && url.endsWith('/roster-imports') ? gate.promise : null,
    );
    const changed = vi.fn();
    const ui = render(<RosterImportPanel classId="class-a" onChanged={changed} />);
    formFile();
    fireEvent.click(screen.getByRole('button', { name: '上传名单' }));
    ui.rerender(<RosterImportPanel classId="class-b" onChanged={changed} />);
    await act(async () =>
      gate.resolve(
        outcome === 'success'
          ? response(batch(), 201)
          : response({ code: 'OLD_ERROR', message: '旧班失败' }, 422),
      ),
    );
    expect(screen.queryByLabelText('第 1 行处理')).not.toBeInTheDocument();
    expect(screen.queryByText(/旧班失败/)).not.toBeInTheDocument();
    expect(changed).not.toHaveBeenCalled();
  });

  it.each(['success', 'failure'] as const)('卸载后确认迟到%s不通知父级', async (outcome) => {
    const gate = deferred<Response>();
    stub((url) => (url.endsWith('/confirm') ? gate.promise : null));
    const changed = vi.fn();
    const ui = render(<RosterImportPanel classId="class-a" onChanged={changed} />);
    await restore();
    chooseRows();
    fireEvent.click(screen.getByRole('button', { name: '确认名单' }));
    ui.unmount();
    await act(async () =>
      gate.resolve(
        outcome === 'success'
          ? response(CONFIRMED)
          : response({ code: 'OLD_ERROR', message: '旧确认失败' }, 422),
      ),
    );
    expect(changed).not.toHaveBeenCalled();
  });
});

describe('名单手建与转班的上下文保护', () => {
  it.each([
    ['class', 'success'],
    ['class', 'failure'],
    ['student', 'success'],
    ['student', 'failure'],
  ] as const)('切班后旧%s创建迟到%s不清空新表单或选择旧班', async (kind, outcome) => {
    const gate = deferred<Response>();
    stub((url, init) =>
      init.method === 'POST' && url.endsWith(kind === 'class' ? '/classes' : '/students')
        ? gate.promise
        : null,
    );
    const select = vi.fn();
    const ui = render(
      <RosterPanel selectedClassId="class-a" onSelectClass={select} refreshToken={0} />,
    );
    if (kind === 'class') {
      fireEvent.click(screen.getByRole('button', { name: '新建班级' }));
      fireEvent.change(screen.getByLabelText('班级编码'), { target: { value: 'old' } });
      fireEvent.change(screen.getByLabelText('班级名称'), { target: { value: '旧班' } });
      fireEvent.submit(screen.getByRole('form', { name: '新建班级' }));
    } else {
      fireEvent.change(screen.getByLabelText('学生姓名'), { target: { value: '旧姓名' } });
      fireEvent.submit(screen.getByRole('form', { name: '添加学生' }));
    }
    ui.rerender(<RosterPanel selectedClassId="class-b" onSelectClass={select} refreshToken={0} />);
    const label = kind === 'class' ? '班级名称' : '学生姓名';
    fireEvent.change(screen.getByLabelText(label), { target: { value: '新输入' } });
    await act(async () =>
      gate.resolve(
        outcome === 'success'
          ? response(kind === 'class' ? CLASSES[0] : STUDENT, 201)
          : response({ code: 'OLD_ERROR', message: '旧手建失败' }, 422),
      ),
    );
    expect(screen.getByLabelText(label)).toHaveValue('新输入');
    expect(select).not.toHaveBeenCalled();
    expect(screen.queryByText(/旧手建失败/)).not.toBeInTheDocument();
  });

  it('转班发送真实学生版本和日期，展示旧结束归属与新归属', async () => {
    const result = {
      ...STUDENT,
      revision: 5,
      memberships: [
        { ...STUDENT.memberships[0], leftOn: '2026-10-02' },
        {
          membershipId: 'membership-new',
          classId: 'class-b',
          className: '七二班',
          joinedOn: '2026-10-02',
          leftOn: null,
        },
      ],
    };
    const fetchMock = stub((url, init) =>
      init.method === 'POST' && url.endsWith('/transfer') ? response(result) : null,
    );
    render(<RosterPanel selectedClassId="class-a" onSelectClass={() => {}} refreshToken={0} />);
    await waitFor(() =>
      expect(screen.getByLabelText('转班学生').querySelectorAll('option')).toHaveLength(2),
    );
    fireEvent.change(screen.getByLabelText('转班学生'), { target: { value: 'student-old' } });
    fireEvent.change(screen.getByLabelText('转入班级'), { target: { value: 'class-b' } });
    fireEvent.change(screen.getByLabelText('转班日期'), { target: { value: '2026-10-02' } });
    fireEvent.click(screen.getByRole('button', { name: '确认转班' }));
    const history = await screen.findByTestId('roster-transfer-result');
    expect(history).toHaveTextContent('七一班：2026-09-01 — 2026-10-02');
    expect(history).toHaveTextContent('七二班：2026-10-02 — 当前归属');
    expect(JSON.parse(String(requests(fetchMock, 'POST')[0][1]!.body))).toEqual({
      expectedStudentRevision: 4,
      fromClassId: 'class-a',
      toClassId: 'class-b',
      movedOn: '2026-10-02',
    });
  });

  it('转班409保留日期和身份选择，提示对照最新版本', async () => {
    stub((url, init) =>
      init.method === 'POST' && url.endsWith('/transfer')
        ? response({ code: 'REVISION_CONFLICT', message: '学生版本已变' }, 409)
        : null,
    );
    render(<RosterPanel selectedClassId="class-a" onSelectClass={() => {}} refreshToken={0} />);
    await waitFor(() =>
      expect(screen.getByLabelText('转班学生').querySelectorAll('option')).toHaveLength(2),
    );
    fireEvent.change(screen.getByLabelText('转班学生'), { target: { value: 'student-old' } });
    fireEvent.change(screen.getByLabelText('转入班级'), { target: { value: 'class-b' } });
    fireEvent.change(screen.getByLabelText('转班日期'), { target: { value: '2026-10-02' } });
    fireEvent.click(screen.getByRole('button', { name: '确认转班' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('学生最新版本');
    expect(screen.getByLabelText('转班日期')).toHaveValue('2026-10-02');
    expect(screen.getByLabelText('转班学生')).toHaveValue('student-old');
    expect(screen.getByLabelText('转入班级')).toHaveValue('class-b');
    expect(screen.queryByTestId('roster-transfer-result')).not.toBeInTheDocument();
  });

  it.each(['success', 'failure'] as const)(
    '切班后转班迟到%s不显示旧结果或失败',
    async (outcome) => {
      const gate = deferred<Response>();
      stub((url, init) =>
        init.method === 'POST' && url.endsWith('/transfer') ? gate.promise : null,
      );
      const ui = render(
        <RosterPanel selectedClassId="class-a" onSelectClass={() => {}} refreshToken={0} />,
      );
      await waitFor(() =>
        expect(screen.getByLabelText('转班学生').querySelectorAll('option')).toHaveLength(2),
      );
      fireEvent.change(screen.getByLabelText('转班学生'), { target: { value: 'student-old' } });
      fireEvent.change(screen.getByLabelText('转入班级'), { target: { value: 'class-b' } });
      fireEvent.click(screen.getByRole('button', { name: '确认转班' }));
      ui.rerender(
        <RosterPanel selectedClassId="class-b" onSelectClass={() => {}} refreshToken={0} />,
      );
      await act(async () =>
        gate.resolve(
          outcome === 'success'
            ? response({ ...STUDENT, revision: 5 })
            : response({ code: 'OLD_ERROR', message: '旧转班失败' }, 409),
        ),
      );
      expect(screen.queryByTestId('roster-transfer-result')).not.toBeInTheDocument();
      expect(screen.queryByText(/旧转班失败/)).not.toBeInTheDocument();
    },
  );
});

/* ------------------------------------------------------------------ 归档 / 恢复 / 放弃 */

const ARCHIVED_CLASS = { ...CLASSES[1], name: '七二班', revision: 3, status: 'archived' as const };
const ARCHIVED_STUDENT: StudentView = {
  id: 'student-archived',
  name: '丙',
  studentNo: '0013',
  revision: 2,
  status: 'archived',
  createdAt: '2026-01-01',
  memberships: [],
};

describe('班级与学生的归档、恢复与已归档开关', () => {
  it('班级默认只取活跃：归档二次确认后刷新，开关显示已归档并可恢复', async () => {
    const writes: { url: string; body: unknown }[] = [];
    const reads: string[] = [];
    stub((url, init) => {
      if (init.method === 'POST') {
        if (url.endsWith('/classes/class-a/archive')) {
          writes.push({ url, body: JSON.parse(String(init.body)) });
          return response({ ...CLASSES[0], status: 'archived', revision: 2 });
        }
        if (url.endsWith('/classes/class-b/restore')) {
          writes.push({ url, body: JSON.parse(String(init.body)) });
          return response({ ...ARCHIVED_CLASS, status: 'active', revision: 4 });
        }
        return null;
      }
      if (url.includes('/classes?')) {
        reads.push(url);
        const items = url.includes('status=active') ? [CLASSES[0]] : [CLASSES[0], ARCHIVED_CLASS];
        return response({ items, total: items.length, offset: 0, limit: 100 });
      }
      return null;
    });
    const confirmSpy = vi.fn(() => true);
    vi.stubGlobal('confirm', confirmSpy);
    render(<RosterPanel selectedClassId="class-a" onSelectClass={() => {}} refreshToken={0} />);
    await screen.findByTestId('assessments-class-class-a');
    expect(reads[0]).toContain('status=active');
    expect(screen.queryByTestId('assessments-class-class-b')).not.toBeInTheDocument();
    expect(screen.getByTestId('assessments-class-archive-class-a')).toBeInTheDocument();

    const before = reads.length;
    fireEvent.click(screen.getByTestId('assessments-class-archive-class-a'));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(writes[0]).toEqual({
      url: '/api/v1/classes/class-a/archive',
      body: { expectedRevision: 1 },
    });
    await waitFor(() => expect(reads.length).toBeGreaterThan(before));
    expect(reads.at(-1)).toContain('status=active');

    fireEvent.click(screen.getByLabelText('显示已归档班级'));
    await screen.findByTestId('assessments-class-class-b');
    expect(screen.getByTestId('assessments-class-archived-class-b')).toHaveTextContent('已归档');
    expect(reads.at(-1)).not.toContain('status=active');
    fireEvent.click(screen.getByTestId('assessments-class-restore-class-b'));
    await waitFor(() => expect(writes).toHaveLength(2));
    expect(writes[1]).toEqual({
      url: '/api/v1/classes/class-b/restore',
      body: { expectedRevision: 3 },
    });
  });

  it('取消确认不发请求；归档失败显示服务端 message 且列表保留', async () => {
    const writes: string[] = [];
    stub((url, init) => {
      if (init.method === 'POST') {
        writes.push(url);
        return response({ code: 'REVISION_CONFLICT', message: '班级版本已变' }, 409);
      }
      if (url.includes('/classes?')) {
        return response({ items: [CLASSES[0]], total: 1, offset: 0, limit: 100 });
      }
      return null;
    });
    const confirmSpy = vi.fn().mockReturnValueOnce(false).mockReturnValueOnce(true);
    vi.stubGlobal('confirm', confirmSpy);
    render(<RosterPanel selectedClassId="class-a" onSelectClass={() => {}} refreshToken={0} />);
    await screen.findByTestId('assessments-class-archive-class-a');
    fireEvent.click(screen.getByTestId('assessments-class-archive-class-a'));
    expect(writes).toHaveLength(0);
    fireEvent.click(screen.getByTestId('assessments-class-archive-class-a'));
    expect(await screen.findByTestId('assessments-class-write-error')).toHaveTextContent(
      '班级版本已变',
    );
    expect(writes).toHaveLength(1);
    expect(screen.getByTestId('assessments-class-class-a')).toBeInTheDocument();
  });

  it('成员默认只取活跃：开关带 includeArchived 且归档学生可恢复', async () => {
    const writes: { url: string; body: unknown }[] = [];
    const reads: string[] = [];
    stub((url, init) => {
      if (init.method === 'POST') {
        if (url.endsWith('/students/student-old/archive')) {
          writes.push({ url, body: JSON.parse(String(init.body)) });
          return response({ ...STUDENT, status: 'archived', revision: 5 });
        }
        if (url.endsWith('/students/student-archived/restore')) {
          writes.push({ url, body: JSON.parse(String(init.body)) });
          return response({ ...ARCHIVED_STUDENT, status: 'active', revision: 3 });
        }
        return null;
      }
      if (url.includes('/students')) {
        reads.push(url);
        const items = url.includes('includeArchived=true')
          ? [STUDENT, ARCHIVED_STUDENT]
          : [STUDENT];
        return response({ items, total: items.length, offset: 0, limit: 100 });
      }
      return null;
    });
    const confirmSpy = vi.fn(() => true);
    vi.stubGlobal('confirm', confirmSpy);
    render(<RosterPanel selectedClassId="class-a" onSelectClass={() => {}} refreshToken={0} />);
    await screen.findByTestId('assessments-student-student-old');
    expect(reads[0]).not.toContain('includeArchived');
    expect(screen.queryByTestId('assessments-student-student-archived')).not.toBeInTheDocument();

    const before = reads.length;
    fireEvent.click(screen.getByTestId('assessments-student-archive-student-old'));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(writes[0]).toEqual({
      url: '/api/v1/students/student-old/archive',
      body: { expectedRevision: 4 },
    });
    await waitFor(() => expect(reads.length).toBeGreaterThan(before));
    expect(reads.at(-1)).not.toContain('includeArchived');

    fireEvent.click(screen.getByLabelText('显示已归档成员'));
    await screen.findByTestId('assessments-student-student-archived');
    expect(screen.getByTestId('assessments-student-archived-student-archived')).toHaveTextContent(
      '已归档',
    );
    expect(reads.at(-1)).toContain('includeArchived=true');
    // 归档学生不进入转班候选项（占位 + 仅活跃学生）
    await waitFor(() =>
      expect(screen.getByLabelText('转班学生').querySelectorAll('option')).toHaveLength(2),
    );
    fireEvent.click(screen.getByTestId('assessments-student-restore-student-archived'));
    await waitFor(() => expect(writes).toHaveLength(2));
    expect(writes[1]).toEqual({
      url: '/api/v1/students/student-archived/restore',
      body: { expectedRevision: 2 },
    });
  });
});

describe('名单批次的放弃', () => {
  const summary = (importId: string, state: RosterImportView['state'], revision = 1) => ({
    importId,
    classId: 'class-a',
    state,
    revision,
    rowCount: 3,
    blockingIssueCount: 0,
    createdAt: '2026-10-02',
    updatedAt: '2026-10-02',
  });

  it('只有未确认批次显示放弃；已取消照常显示为已取消', async () => {
    stub((url) =>
      url.includes('/roster-imports?')
        ? response({
            items: [
              summary('imp-up', 'uploaded'),
              summary('imp-reviewing', 'reviewing'),
              summary('imp-failed', 'failed'),
              summary('imp-confirmed', 'confirmed', 4),
              summary('imp-cancelled', 'cancelled', 2),
            ],
            total: 5,
            offset: 0,
            limit: 100,
          })
        : null,
    );
    render(<RosterImportPanel classId="class-a" onChanged={() => {}} />);
    await screen.findByTestId('roster-batch-discard-imp-up');
    expect(screen.getByTestId('roster-batch-discard-imp-reviewing')).toBeInTheDocument();
    expect(screen.getByTestId('roster-batch-discard-imp-failed')).toBeInTheDocument();
    expect(screen.queryByTestId('roster-batch-discard-imp-confirmed')).not.toBeInTheDocument();
    expect(screen.queryByTestId('roster-batch-discard-imp-cancelled')).not.toBeInTheDocument();
    expect(screen.getByTestId('roster-batch-imp-cancelled')).toHaveTextContent('已取消');
  });

  it('放弃二次确认后置为已取消、刷新列表并冻结已打开的批次', async () => {
    const confirmSpy = vi.fn(() => true);
    vi.stubGlobal('confirm', confirmSpy);
    const writes: { url: string; body: unknown }[] = [];
    let cancelled = false;
    const fetchMock = stub((url, init) => {
      if (init.method === 'POST' && url.endsWith('/roster-imports/import-1/discard')) {
        writes.push({ url, body: JSON.parse(String(init.body)) });
        cancelled = true;
        return response(batch({ state: 'cancelled', revision: 2 }));
      }
      if (url.includes('/roster-imports?')) {
        return response({
          items: [
            summary('import-1', cancelled ? 'cancelled' : 'reviewing', cancelled ? 2 : 1),
            summary('import-2', 'confirmed', 4),
          ],
          total: 2,
          offset: 0,
          limit: 100,
        });
      }
      return null;
    });
    render(<RosterImportPanel classId="class-a" onChanged={() => {}} />);
    await restore();
    fireEvent.click(screen.getByTestId('roster-batch-discard-import-1'));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(confirmSpy).toHaveBeenCalledTimes(1);
    expect(writes[0]).toEqual({
      url: '/api/v1/roster-imports/import-1/discard',
      body: { expectedRevision: 1 },
    });
    await screen.findByText(/批次 import-1 已放弃（已取消）/);
    await waitFor(() =>
      expect(screen.getByTestId('roster-batch-import-1')).toHaveTextContent('已取消'),
    );
    // 当前打开的批次同步冻结：不再能改行决策/确认
    await waitFor(() => expect(screen.getByLabelText('第 1 行处理')).toBeDisabled());
    expect(screen.getByRole('button', { name: '确认名单' })).toBeDisabled();
    expect(
      fetchMock.mock.calls.filter(([input]) => String(input).includes('/roster-imports?')).length,
    ).toBeGreaterThanOrEqual(2);
  });
});


/* ------------------------------------------------------------------ 班级彻底删除与批量添加学生 */

/** jsdom 26 没有实现 <dialog> 的 showModal/close；对话框用例自行补上并在用例后还原。 */
function stubDialog() {
  Object.defineProperties(HTMLDialogElement.prototype, {
    showModal: {
      configurable: true,
      value: function (this: HTMLDialogElement) { this.setAttribute('open', ''); },
    },
    close: {
      configurable: true,
      value: function (this: HTMLDialogElement) { this.removeAttribute('open'); },
    },
  });
}

describe('班级彻底删除（受引用守卫的三态）', () => {
  it('删除成功：二次确认后 DELETE 带列表 revision，刷新班级并取消被删班级的选择', async () => {
    const writes: { url: string; method: string }[] = [];
    let alive = true;
    vi.stubGlobal('confirm', vi.fn(() => true));
    const select = vi.fn();
    stub((url, init) => {
      if (init.method === 'DELETE' && url.includes('/classes/class-a')) {
        writes.push({ url, method: 'DELETE' });
        alive = false;
        return response({ deleted: true, classId: 'class-a' });
      }
      if (url.includes('/classes?')) {
        return response({
          items: alive ? CLASSES : CLASSES.filter((item) => item.id !== 'class-a'),
          total: alive ? 2 : 1,
          offset: 0,
          limit: 100,
        });
      }
      return null;
    });
    render(<RosterPanel selectedClassId="class-a" onSelectClass={select} refreshToken={0} />);
    fireEvent.click(await screen.findByTestId('assessments-class-delete-class-a'));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0].url).toBe('/api/v1/classes/class-a?expectedRevision=1');
    // 成功回执 + 已删除行消失 + 被删班级的选择被清空（避免继续读已不存在的班级）
    expect(await screen.findByTestId('assessments-class-delete-notice')).toHaveTextContent('已彻底删除班级「七一班」');
    await waitFor(() => expect(screen.queryByTestId('assessments-class-class-a')).not.toBeInTheDocument());
    expect(select).toHaveBeenCalledWith('', '');
    expect(screen.queryByTestId('assessments-class-delete-guard')).not.toBeInTheDocument();
  });

  it('被引用 409：逐项列出 details.counts（0 不显示），「改为归档」走归档端点', async () => {
    const message = '班级仍被引用，不能删除（班级归属记录 2 条、名单导入批次 1 条）；请先处理相关数据。';
    const writes: { url: string; body: unknown }[] = [];
    vi.stubGlobal('confirm', vi.fn(() => true));
    stub((url, init) => {
      if (init.method === 'DELETE' && url.includes('/classes/class-a')) {
        return response({
          code: 'CLASS_IN_USE',
          message,
          details: { counts: { memberships: 2, rosterImports: 1, assessments: 0, lessonPlans: 0 } },
        }, 409);
      }
      if (init.method === 'POST' && url.endsWith('/classes/class-a/archive')) {
        writes.push({ url, body: JSON.parse(String(init.body)) });
        return response({ ...CLASSES[0], status: 'archived', revision: 2 });
      }
      return null;
    });
    render(<RosterPanel selectedClassId="class-a" onSelectClass={() => {}} refreshToken={0} />);
    fireEvent.click(await screen.findByTestId('assessments-class-delete-class-a'));
    const guard = await screen.findByTestId('assessments-class-delete-guard');
    expect(guard).toHaveTextContent(message);
    expect(guard).toHaveTextContent('班级归属记录 2 条');
    expect(guard).toHaveTextContent('名单导入批次 1 条');
    expect(guard).not.toHaveTextContent('参测范围引用');
    expect(guard).not.toHaveTextContent('教案引用');
    // 被拒绝不改列表
    expect(screen.getByTestId('assessments-class-class-a')).toBeInTheDocument();

    fireEvent.click(screen.getByTestId('assessments-class-delete-guard-archive'));
    await waitFor(() => expect(writes).toHaveLength(1));
    expect(writes[0]).toEqual({
      url: '/api/v1/classes/class-a/archive',
      body: { expectedRevision: 1 },
    });
  });

  it('乐观锁冲突按既有错误区呈现（不伪装成引用原因）', async () => {
    vi.stubGlobal('confirm', vi.fn(() => true));
    stub((url, init) =>
      init.method === 'DELETE' && url.includes('/classes/class-b')
        ? response({ code: 'REVISION_CONFLICT', message: '班级版本已变化' }, 409)
        : null,
    );
    render(<RosterPanel selectedClassId="class-a" onSelectClass={() => {}} refreshToken={0} />);
    fireEvent.click(await screen.findByTestId('assessments-class-delete-class-b'));
    expect(await screen.findByTestId('assessments-class-write-error')).toHaveTextContent('班级版本已变化');
    expect(screen.queryByTestId('assessments-class-delete-guard')).not.toBeInTheDocument();
  });
});

describe('批量添加学生（本地预览 + 幂等提交）', () => {
  beforeEach(() => { stubDialog(); });
  afterEach(() => {
    // 先卸载（Modal 的清理会调用 dialog.close()），再还原原型，避免卸载期 TypeError。
    cleanup();
    Reflect.deleteProperty(HTMLDialogElement.prototype, 'showModal');
    Reflect.deleteProperty(HTMLDialogElement.prototype, 'close');
  });

  const created = (name: string, studentNo: string) => ({
    id: `new-${studentNo}`, name, studentNo, status: 'active', revision: 1, memberships: [], createdAt: '2026-10-08',
  });

  async function openDialog() {
    render(<RosterPanel selectedClassId="class-a" onSelectClass={() => {}} refreshToken={0} />);
    fireEvent.click(await screen.findByTestId('assessments-batch-open'));
    return screen.findByLabelText('批量学生文本');
  }

  function paste(lines: string[]) {
    fireEvent.change(screen.getByLabelText('批量学生文本'), { target: { value: lines.join('\n') } });
  }

  it('预览区分新建/行内重复/需处理；提交只带可提交行，结果逐行按原文行号报告', async () => {
    const bodies: Record<string, unknown>[] = [];
    const fetchMock = stub((url, init) => {
      if (init.method === 'POST' && url.endsWith('/students/batch')) {
        bodies.push(JSON.parse(String(init.body)));
        return response({
          created: [created('沈予安', 'T260031')],
          skipped: [{
            index: 1,
            reason: '学号 T260032 已存在（学生「顾时雨」），未重复创建。',
            code: 'STUDENT_NO_CONFLICT',
            existingStudentId: 'student-old',
            existingName: '顾时雨',
          }],
          replayed: false,
        });
      }
      return null;
    });
    await openDialog();
    // 第 3 行识别不到学号（需处理）；第 5 行与第 1 行学号相同（本批重复）
    paste(['T260031, 沈予安', 'T260032\t顾时雨', '只有姓名', '', 'T260031 沈予安']);
    expect(screen.getByTestId('roster-batch-row-1')).toHaveTextContent('新建');
    expect(screen.getByTestId('roster-batch-row-2')).toHaveTextContent('新建');
    expect(screen.getByTestId('roster-batch-row-3')).toHaveTextContent('未识别到学号');
    expect(screen.getByTestId('roster-batch-row-5')).toHaveTextContent('本批重复');
    expect(screen.getByTestId('roster-batch-fresh')).toHaveTextContent('可建立 2 名');
    expect(screen.getByTestId('roster-batch-problems')).toHaveTextContent('需处理 1 行');
    const submit = screen.getByTestId('roster-batch-submit');
    expect(submit).toHaveTextContent('一次建立 2 名学生');
    expect(submit).toHaveTextContent('另 1 行需处理，不提交');

    fireEvent.click(submit);
    await screen.findByTestId('roster-batch-result');
    expect(bodies).toHaveLength(1);
    expect(typeof bodies[0].submissionId).toBe('string');
    expect(bodies[0].items).toEqual([
      { studentNo: 'T260031', name: '沈予安' },
      { studentNo: 'T260032', name: '顾时雨' },
      { studentNo: 'T260031', name: '沈予安' },
    ]);
    // skipped 的 0 基下标映射回原文行号（items[1] 是第 2 行），并给出既有学生姓名
    const skippedRow = screen.getByTestId('roster-batch-skipped-1');
    expect(skippedRow).toHaveTextContent('第 2 行');
    expect(skippedRow).toHaveTextContent('顾时雨');
    expect(screen.getByTestId('roster-batch-result')).toHaveTextContent('新建 1 名学生，跳过 1 行');
    // 已提交行出输入框，需处理行留在原位；成员列表被刷新
    await waitFor(() => expect(screen.getByLabelText('批量学生文本')).toHaveValue('只有姓名'));
    expect(
      fetchMock.mock.calls.filter(([input]) => String(input).includes('/classes/class-a/students')).length,
    ).toBeGreaterThanOrEqual(2);
  });

  it('结果未知后重试复用同一 submissionId 与原包，重放结果照常展示', async () => {
    const bodies: Record<string, unknown>[] = [];
    let calls = 0;
    stub((url, init) => {
      if (init.method === 'POST' && url.endsWith('/students/batch')) {
        bodies.push(JSON.parse(String(init.body)));
        if (++calls === 1) throw new TypeError('network lost');
        return response({ created: [created('沈予安', 'T260031')], skipped: [], replayed: true });
      }
      return null;
    });
    await openDialog();
    paste(['T260031, 沈予安']);
    fireEvent.click(screen.getByTestId('roster-batch-submit'));
    await screen.findByTestId('roster-batch-unknown');
    expect(screen.getByTestId('roster-batch-submit')).toHaveTextContent('重试同一提交（1 行）');
    fireEvent.click(screen.getByTestId('roster-batch-submit'));
    await screen.findByTestId('roster-batch-result');
    expect(bodies).toHaveLength(2);
    expect(bodies[1]).toEqual(bodies[0]);
    expect(screen.getByTestId('roster-batch-result')).toHaveTextContent('已批量添加（幂等重放）');
  });

  it('超过 200 行先提示并禁用提交（后端同样拒绝）', async () => {
    stub(() => null);
    await openDialog();
    paste(Array.from({ length: 201 }, (_, index) => `T${index}, 学生${index}`));
    expect(screen.getByTestId('roster-batch-over-limit')).toBeInTheDocument();
    expect(screen.getByTestId('roster-batch-submit')).toBeDisabled();
  });
});

