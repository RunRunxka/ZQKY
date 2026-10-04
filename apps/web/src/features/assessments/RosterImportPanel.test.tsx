import { StrictMode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
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
