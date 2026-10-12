/**
 * 小题分成绩单导入（R6-FE）：上传 → 列映射人工确认 → 行校对四态（0/空白/缺考/免考）不补零。
 *
 * 与归档测试的差异（已在交付说明报告）：归档的 ScorePanel 长流程测试绑定施测工作区的
 * 历史页签与工作流任务观察，本 feature 只取回导入所需面板，测试相应聚焦上传/映射校验与四态呈现。
 */

import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import type { ScoreImportView } from '@/contracts/learning-analysis';
import { ApiError } from '@/services/api-client';
import { ScoreImportPanel } from './ScoreImportPanel';

const mocks = vi.hoisted(() => ({ api: {} as Record<string, unknown> }));

vi.mock('@/services/learning-analysis-api', () => ({
  learningAnalysisApi: mocks.api,
  COLUMN_PATTERN: /^[A-Za-z]{1,3}$/,
}));

const VIEW: ScoreImportView = {
  importId: 'imp-1',
  assessmentId: 'asm-1',
  assessmentTitle: '第一次月考',
  state: 'reviewing',
  revision: 4,
  previewVersion: 2,
  fileAsset: {
    assetId: 'asset-1',
    sha256: 'sha',
    mediaType: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    byteSize: 2048,
    originalName: '小题分.xlsx',
  },
  mapping: {
    workSheet: '成绩',
    headerRow: 1,
    studentNoColumn: 'A',
    nameColumn: 'B',
    itemColumns: [{ itemId: 'i1', column: 'C' }],
  },
  rowCount: 2,
  resolvedRowCount: 1,
  missingCellCount: 1,
  requiredAcknowledgements: { absences: [], missing: null },
  createdAt: '2026-10-05T08:00:00Z',
  updatedAt: '2026-10-05T08:00:00Z',
};

const ROWS = {
  items: [
    {
      rowNo: 2,
      participantId: 'p1',
      participantName: '甲',
      cells: [
        { row: 2, column: 'C', text: '0' },
        { row: 2, column: 'D', text: '' },
        { row: 2, column: 'E', text: '缺考' },
        { row: 2, column: 'F', text: '免考' },
        { row: 2, column: 'G', text: '看到这行说明没识别' },
      ],
    },
  ],
  total: 1,
  offset: 0,
  limit: 50,
};

function baseApi() {
  return {
    listClasses: vi.fn(async () => ({
      items: [{ id: 'class-a', name: '七一班' }],
      total: 1,
      offset: 0,
      limit: 200,
    })),
    getAssessment: vi.fn(async () => ({
      assessment: {
        assessmentId: 'asm-1',
        paperId: 'paper-1',
        paperRevisionId: 'paper-1',
        paperTitle: '第一次月考原卷',
        title: '第一次月考',
        heldOn: '2026-09-30',
        revision: 3,
        participantCount: 1,
        classIds: ['class-a'],
      },
      participants: [
        {
          participantId: 'p1',
          studentId: 's1',
          nameSnapshot: '甲',
          classId: 'class-a',
          attemptNo: 1,
          attendance: 'absent' as const,
        },
      ],
    })),
    listScoreImports: vi.fn(async () => ({
      items: [
        {
          importId: 'imp-1',
          assessmentId: 'asm-1',
          uploadedFileName: '小题分.xlsx',
          state: 'reviewing' as const,
          revision: 4,
          rowCount: 2,
          createdAt: '2026-10-05T08:00:00Z',
          updatedAt: '2026-10-05T08:00:00Z',
        },
      ],
      total: 1,
      offset: 0,
      limit: 50,
    })),
    getScoreImport: vi.fn(async () => VIEW),
    listScoreImportRows: vi.fn(async () => ROWS),
    listScoreRevisions: vi.fn(async () => ({ items: [], total: 0 })),
    getPaperRevisionContent: vi.fn(async () => ({
      paperId: 'paper-1',
      paperRevisionId: 'paper-1',
      items: [
        // 服务端分数为 ×100 整数单位：10000 = 100 分
        { itemId: 'i1', parentItemId: null, questionNo: '1', ordinal: 1, isScored: true, maxScoreUnits: 10000 },
        { itemId: 'i2', parentItemId: null, questionNo: '2', ordinal: 2, isScored: true, maxScoreUnits: 5000 },
      ],
    })),
    createScoreImport: vi.fn(async () => VIEW),
    patchScoreImport: vi.fn(async () => VIEW),
    confirmScoreImport: vi.fn(),
    discardScoreImport: vi.fn(),
    deleteScoreImport: vi.fn(),
    refreshScoreImport: vi.fn(),
  };
}

function installApi(overrides: Record<string, unknown> = {}) {
  const api = baseApi();
  Object.assign(mocks.api, api, overrides);
  return mocks.api as unknown as Record<string, ReturnType<typeof vi.fn>>;
}

beforeEach(() => {
  for (const key of Object.keys(mocks.api)) delete mocks.api[key];
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe('小题分成绩单导入面板', () => {
  it('上传只送原始文件 + 工作表名；未选文件时提交按钮禁用', async () => {
    const api = installApi();
    render(<ScoreImportPanel assessmentId="asm-1" onClose={vi.fn()} onChanged={vi.fn()} />);

    const submit = await screen.findByRole('button', { name: '上传并创建待校对批次' });
    expect(submit).toBeDisabled();

    const file = new File(['a,b'], '小题分.xlsx', {
      type: 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
    });
    fireEvent.change(screen.getByLabelText('成绩表格文件'), { target: { files: [file] } });
    fireEvent.change(screen.getByLabelText('工作表名'), { target: { value: '成绩' } });
    fireEvent.click(submit);

    await waitFor(() =>
      expect(api.createScoreImport).toHaveBeenCalledWith('asm-1', file, {
        workSheet: '成绩',
        baseScoreRevisionId: null,
      }),
    );
  });

  it('列映射：计分叶来自原卷修订；缺少工作表名时不发保存请求', async () => {
    const api = installApi({
      // 已保存映射的工作表名从草稿里清掉，模拟教师手工清空
      getScoreImport: vi.fn(async () => ({ ...VIEW, mapping: { ...VIEW.mapping, workSheet: '' } })),
    });
    render(<ScoreImportPanel assessmentId="asm-1" onClose={vi.fn()} onChanged={vi.fn()} />);

    expect(await screen.findByTestId('assessments-leaf-label-i1')).toHaveTextContent('1（满分 100）');
    expect(screen.getByTestId('assessments-leaf-label-i2')).toHaveTextContent('2（满分 50）');

    fireEvent.click(screen.getByRole('button', { name: '保存映射并重算' }));
    expect(await screen.findByTestId('assessments-mapping-error')).toHaveTextContent('工作表名必填');
    expect(api.patchScoreImport).not.toHaveBeenCalled();
  });

  it('行校对：0 / 空白 / 缺考 / 免考 / 未识别五态显著区分，空白明示不补 0', async () => {
    installApi();
    render(<ScoreImportPanel assessmentId="asm-1" onClose={vi.fn()} onChanged={vi.fn()} />);

    const row = await screen.findByTestId('score-row-2');
    // 显式 0 分是有效记录
    const zero = within(row).getByTestId('score-cell-status-2-C');
    expect(zero).toHaveAttribute('data-status', 'recorded');
    expect(zero).toHaveTextContent('0');
    expect(zero).toHaveAttribute('title', '有效分数（recorded）');
    expect(within(row).getByText('显式 0 分（有效记录）')).toBeInTheDocument();

    // 空白 → missing，不补 0
    const blank = within(row).getByTestId('score-cell-status-2-D');
    expect(blank).toHaveAttribute('data-status', 'missing');
    expect(blank).toHaveTextContent('（空白）');
    expect(within(row).getByText('空白单元格按 missing 处理，不补 0')).toBeInTheDocument();

    // 缺考 / 免考
    expect(within(row).getByTestId('score-cell-status-2-E')).toHaveAttribute('data-status', 'absent');
    expect(within(row).getByTestId('score-cell-status-2-F')).toHaveAttribute('data-status', 'exempt');

    // 未知文本不猜成 0
    const unparsed = within(row).getByTestId('score-cell-status-2-G');
    expect(unparsed).toHaveAttribute('data-status', 'unparsed');
    expect(within(row).getByText('无法本地判读，以服务端为准')).toBeInTheDocument();

    // 四态图例（颜色之外还有文案）
    const legend = screen.getByTestId('score-status-legend');
    expect(within(legend).getByText('表格里的 0 是有效 0 分，不等于空白')).toBeInTheDocument();
    expect(within(legend).getByText('空白单元格：不补 0，需逐类承认后确认')).toBeInTheDocument();
    expect(within(legend).getByText('缺考：按人次出勤状态登记，不计 0')).toBeInTheDocument();
    expect(within(legend).getByText('免考：不计 0，不参与总分核对')).toBeInTheDocument();
  });

  it('行校对保存失败（422）：保留编辑并定位到行/列，可直接重试', async () => {
    const patch = vi.fn(async () => {
      throw new ApiError('SCORE_CELL_INVALID', '第 2 行列 C 不是有效分数', 422, false, 'r1', {
        issues: [{ row: 2, column: 'C', code: 'SCORE_CELL_INVALID', message: '不是有效分数' }],
      });
    });
    installApi({ patchScoreImport: patch });
    render(<ScoreImportPanel assessmentId="asm-1" onClose={vi.fn()} onChanged={vi.fn()} />);

    const input = await screen.findByLabelText('第 2 行 列 C 校正');
    fireEvent.change(input, { target: { value: '99' } });
    expect(input).toHaveValue('99');
    fireEvent.click(screen.getByTestId('score-save-drafts'));

    await waitFor(() => expect(patch).toHaveBeenCalledTimes(1));
    const cell = await screen.findByTestId('score-cell-2-C');
    expect(cell).toHaveAttribute('data-issue', 'true');
    expect(screen.getByTestId('score-issue-list')).toHaveTextContent('第 2 行 列 C');
    // 编辑保留，重试仍可再发
    expect(input).toHaveValue('99');
    fireEvent.click(screen.getByTestId('score-save-drafts'));
    await waitFor(() => expect(patch).toHaveBeenCalledTimes(2));
  });

  it('未选试卷时不发任何导入请求，提示先选试卷', async () => {
    const api = installApi();
    render(<ScoreImportPanel assessmentId={null} onClose={vi.fn()} onChanged={vi.fn()} />);
    expect(await screen.findByTestId('score-import-no-assessment')).toBeInTheDocument();
    expect(api.listScoreImports).not.toHaveBeenCalled();
    expect(api.createScoreImport).not.toHaveBeenCalled();
  });
});
