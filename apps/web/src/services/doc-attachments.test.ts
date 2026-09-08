import { describe, expect, it } from 'vitest';
import {
  classifyFile,
  docIconFor,
  formatBytes,
  isSvgFilename,
  selectAttachmentFiles,
  DEFAULT_ATTACHMENT_LIMITS,
} from './doc-attachments';

function file(name: string, size: number, type = ''): File {
  // jsdom 无真实文件系统：构造 File 验证分类与配额逻辑
  const f = new File(['x'.repeat(Math.max(size, 1))], name, { type });
  Object.defineProperty(f, 'size', { value: size });
  return f;
}

describe('附件分类（对照参考 classifyFile）', () => {
  it('图片为 image；SVG 按 doc 处理（视觉模型拒绝 SVG，发送 XML 源码）', () => {
    expect(classifyFile(file('a.png', 10, 'image/png'))).toBe('image');
    expect(classifyFile(file('a.svg', 10, 'image/svg+xml'))).toBe('doc');
    expect(classifyFile(file('a.svg', 10))).toBe('doc'); // 扩展名兜底
    expect(isSvgFilename('A.SVG')).toBe(true);
  });

  it('Office 与文本/代码格式为 doc；MIME 优先、扩展名兜底；未知类型拒绝', () => {
    expect(classifyFile(file('a.pdf', 10))).toBe('doc'); // Windows 常报空 MIME
    expect(classifyFile(file('a.py', 10))).toBe('doc');
    expect(classifyFile(file('a.txt', 10, 'text/plain'))).toBe('doc');
    expect(classifyFile(file('a.xyz', 10))).toBeNull();
    expect(classifyFile(file('a.exe', 10, 'application/octet-stream'))).toBeNull();
  });

  it('图标类别：PDF/表格/代码/图片/兜底', () => {
    expect(docIconFor('a.pdf').label).toBe('PDF');
    expect(docIconFor('a.csv').label).toBe('表格');
    expect(docIconFor('a.ts').label).toBe('代码');
    expect(docIconFor('a.png').label).toBe('图片');
    expect(docIconFor('a.xyz').label).toBe('文件');
  });

  it('字节数可读格式', () => {
    expect(formatBytes(512)).toBe('512 B');
    expect(formatBytes(2048)).toBe('2.0 KB');
    expect(formatBytes(5 * 1024 * 1024)).toBe('5.0 MB');
  });
});

describe('附件校验（对照参考 selectAttachmentFiles：类型→单文件→配额）', () => {
  const limits = { maxFileBytes: 100, maxTotalBytes: 250 };

  it('类型不支持即拒绝且不影响后续文件', () => {
    const { accepted, rejected } = selectAttachmentFiles(
      [file('a.xyz', 10), file('b.txt', 10)],
      0,
      limits,
    );
    expect(accepted.map((f) => f.name)).toEqual(['b.txt']);
    expect(rejected).toEqual([{ name: 'a.xyz', reason: 'unsupported' }]);
  });

  it('单文件超限拒绝；总量配额超出时中断（quota 即 break，同参考）', () => {
    const limits = { maxFileBytes: 100, maxTotalBytes: 200 };
    const { accepted, rejected } = selectAttachmentFiles(
      [file('big.txt', 150), file('ok1.txt', 100), file('ok2.txt', 95), file('never.txt', 10)],
      0,
      limits,
    );
    expect(accepted.map((f) => f.name)).toEqual(['ok1.txt', 'ok2.txt']); // ok1+ok2=195
    expect(rejected).toEqual([
      { name: 'big.txt', reason: 'too_large' },
      { name: 'never.txt', reason: 'quota' }, // 195+10>200：中断
    ]);
  });

  it('已有附件占用配额：新文件按剩余空间接受', () => {
    const { accepted, rejected } = selectAttachmentFiles(
      [file('fits.txt', 50), file('rest.txt', 100)],
      200,
      limits,
    );
    expect(accepted.map((f) => f.name)).toEqual(['fits.txt']);
    expect(rejected).toEqual([{ name: 'rest.txt', reason: 'quota' }]);
  });

  it('默认上限：单文件 20MB、总量 25MB（对照参考 DEFAULT_*_BYTES）', () => {
    expect(DEFAULT_ATTACHMENT_LIMITS.maxFileBytes).toBe(20 * 1024 * 1024);
    expect(DEFAULT_ATTACHMENT_LIMITS.maxTotalBytes).toBe(25 * 1024 * 1024);
  });
});
