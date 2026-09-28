import { afterEach, beforeAll, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom/vitest';
import { MAX_UPLOAD_BYTES, type TextbookTaxonomy } from '@/contracts/textbook';
import { ImportQuestionPanel } from './ImportQuestionPanel';
import { buildTaxonomyIndex } from './taxonomy';

const TAXONOMY: TextbookTaxonomy = {
  stages: [{ id: 'stage-j', label: '初中' }],
  grades: [{ id: 'grade-7', label: '七年级', stageId: 'stage-j' }],
  subjects: [{ id: 'math', label: '数学' }],
  editions: [{ id: 'renjiao', label: '人教版' }],
};
const index = buildTaxonomyIndex(TAXONOMY);

const ok = (body: unknown) => ({ ok: true, status: 201, json: async () => body }) as Response;
const failed = (status: number, body: unknown) =>
  ({ ok: false, status, json: async () => body }) as Response;

type Handler = (url: string, init: RequestInit) => Response | Promise<Response>;

function stubApi(handler: Handler) {
  const fetchMock = vi.fn((input: RequestInfo | URL, init?: RequestInit) =>
    Promise.resolve(handler(typeof input === 'string' ? input : input.toString(), init ?? {})),
  );
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function postCalls(fetchMock: ReturnType<typeof stubApi>, fragment: string) {
  return fetchMock.mock.calls.filter(
    ([url, init]) =>
      String(url).includes(fragment) && (init as RequestInit | undefined)?.method === 'POST',
  );
}

beforeAll(() => {
  // jsdom 未实现 <dialog> 的方法；补最小实现以驱动 Modal
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
});

describe('导入试题面板', () => {
  it('拒绝不支持的文件类型并给出明确提示，且不发起上传', async () => {
    const fetchMock = stubApi(() => {
      throw new Error('不应发起请求');
    });
    render(<ImportQuestionPanel taxonomy={index} onClose={() => {}} onImported={() => {}} />);

    fireEvent.change(screen.getByLabelText('试题文件'), {
      target: { files: [new File(['x'], '试题.txt', { type: 'text/plain' })] },
    });

    expect(await screen.findByRole('alert')).toHaveTextContent('不支持的文件类型');
    expect(postCalls(fetchMock, '/question-imports')).toHaveLength(0);
  });

  it('超过 100 MiB 时提示文件过大，且不发起上传', async () => {
    const fetchMock = stubApi(() => {
      throw new Error('不应发起请求');
    });
    render(<ImportQuestionPanel taxonomy={index} onClose={() => {}} onImported={() => {}} />);
    const file = new File(['x'], '大题集.pdf', { type: 'application/pdf' });
    Object.defineProperty(file, 'size', { value: MAX_UPLOAD_BYTES + 1 });

    fireEvent.change(screen.getByLabelText('试题文件'), { target: { files: [file] } });

    expect(await screen.findByRole('alert')).toHaveTextContent('文件过大');
    expect(postCalls(fetchMock, '/question-imports')).toHaveLength(0);
  });

  it('合法文件以 multipart 上传并带回导入 id', async () => {
    const onImported = vi.fn();
    const fetchMock = stubApi(() => ok({ importId: 'imp-9' }));
    render(<ImportQuestionPanel taxonomy={index} onClose={() => {}} onImported={onImported} />);

    fireEvent.change(screen.getByLabelText('试题文件'), {
      target: { files: [new File(['题干'], '七年级数学.md', { type: 'text/markdown' })] },
    });
    fireEvent.change(screen.getByLabelText('学科（可选）'), { target: { value: 'math' } });
    fireEvent.click(screen.getByRole('button', { name: /上传并解析/ }));

    await waitFor(() => expect(onImported).toHaveBeenCalledWith('imp-9'));
    const [, init] = postCalls(fetchMock, '/question-imports')[0] as [string, RequestInit];
    const form = init.body as FormData;
    expect(form.get('file')).toBeInstanceOf(File);
    expect(form.get('subjectId')).toBe('math');
    expect(form.get('gradeId')).toBeNull();
  });

  it('上传失败时显示错误码并保留已选文件，可直接重试', async () => {
    let attempt = 0;
    const fetchMock = stubApi(() => {
      attempt += 1;
      if (attempt === 1) {
        return failed(422, {
          code: 'DOCUMENT_NEEDS_OCR',
          message: '扫描件缺少文本层。',
          retryable: false,
        });
      }
      return ok({ importId: 'imp-10' });
    });
    render(<ImportQuestionPanel taxonomy={index} onClose={() => {}} onImported={() => {}} />);

    fireEvent.change(screen.getByLabelText('试题文件'), {
      target: { files: [new File(['x'], '扫描.pdf', { type: 'application/pdf' })] },
    });
    fireEvent.click(screen.getByRole('button', { name: /上传并解析/ }));

    expect(await screen.findByRole('alert')).toHaveTextContent('DOCUMENT_NEEDS_OCR');
    expect(screen.getByText(/已选择：扫描.pdf/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: /上传并解析/ }));
    await waitFor(() => expect(postCalls(fetchMock, '/question-imports')).toHaveLength(2));
  });
});
