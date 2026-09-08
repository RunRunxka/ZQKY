/**
 * 聊天附件分类与校验（S2 输入区）。
 *
 * 规则对照参考仓库 v1.6.5 `web/lib/doc-attachments.ts` 与
 * `web/features/chat/controllers/pending-attachments.ts`：
 * - Office 二进制格式 + 大类文本/代码格式可接受；SVG 按 doc 处理（视觉模型
 *   拒绝 SVG，发送 XML 源码更利于推理——同参考 classifyFile 注释）；
 * - 校验顺序：类型 → 单文件大小 → 总量配额，先到先停（quota 即 break）；
 * - 默认上限：单文件 20MB、总量 25MB（参考 DEFAULT_*_ATTACHMENT_BYTES）。
 * 目标项目无文件解析/上传服务：附件内容只在本组件内预览（base64/对象URL），
 * 发送时仅随快照携带元数据并明确“未读取文件内容”。
 */
import {
  FileCode2,
  FileImage,
  FileJson,
  FileSpreadsheet,
  FileText,
  FileType2,
  Paperclip,
  Presentation,
  type LucideIcon,
} from 'lucide-react';

export const OFFICE_EXTS = ['.pdf', '.docx', '.xlsx', '.pptx'] as const;

export const TEXT_LIKE_EXTS = [
  '.txt', '.text', '.log', '.md', '.markdown', '.rst', '.html', '.htm', '.xml', '.svg',
  '.json', '.jsonc', '.yaml', '.yml', '.toml', '.csv', '.tsv', '.ini', '.cfg', '.conf',
  '.env', '.properties', '.tex', '.bib', '.css', '.scss', '.sass', '.less',
  '.js', '.mjs', '.cjs', '.ts', '.mts', '.cts', '.jsx', '.tsx', '.vue', '.svelte',
  '.py', '.java', '.kt', '.scala', '.groovy', '.gradle',
  '.c', '.h', '.cpp', '.hpp', '.cs', '.go', '.rs', '.swift', '.m', '.mm',
  '.rb', '.php', '.pl', '.lua', '.r', '.jl', '.dart', '.hs', '.erl', '.ex',
  '.sol', '.sh', '.bash', '.zsh', '.fish', '.ps1', '.vim', '.sql', '.graphql', '.gql',
  '.proto', '.cmake', '.mk', '.tf', '.dockerfile',
] as const;

export const SUPPORTED_DOC_EXTS = [...OFFICE_EXTS, ...TEXT_LIKE_EXTS] as const;

export const SUPPORTED_DOC_MIMES = new Set<string>([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'text/plain', 'text/markdown', 'text/html', 'text/xml', 'application/xml',
  'application/json', 'text/csv', 'text/tab-separated-values', 'text/yaml',
  'application/yaml', 'text/x-python', 'text/javascript', 'application/javascript',
  'application/typescript', 'text/css', 'application/sql', 'application/toml',
]);

export const DEFAULT_MAX_ATTACHMENT_BYTES = 20 * 1024 * 1024;
export const DEFAULT_MAX_TOTAL_ATTACHMENT_BYTES = 25 * 1024 * 1024;

/** 文件选择器 accept 属性（同参考：MIME + 扩展名并列，兼容 Windows 空 MIME） */
export const ATTACHMENT_ACCEPT = [
  'image/*',
  ...SUPPORTED_DOC_EXTS,
  ...Array.from(SUPPORTED_DOC_MIMES),
].join(',');

export type FileKind = 'image' | 'doc';

export function extOf(filename: string): string {
  const idx = filename.lastIndexOf('.');
  return idx >= 0 ? filename.slice(idx).toLowerCase() : '';
}

/** SVG 按 doc 分类（同参考）；MIME 优先，扩展名兜底（浏览器常报空 MIME） */
export function classifyFile(file: File): FileKind | null {
  const ext = extOf(file.name);
  if (ext === '.svg' || file.type === 'image/svg+xml') return 'doc';
  if (file.type && file.type.startsWith('image/')) return 'image';
  if (file.type && SUPPORTED_DOC_MIMES.has(file.type)) return 'doc';
  if (ext && (SUPPORTED_DOC_EXTS as readonly string[]).includes(ext)) return 'doc';
  return null;
}

export function isSvgFilename(filename: string): boolean {
  return extOf(filename) === '.svg';
}

export function formatBytes(n: number): string {
  if (!Number.isFinite(n) || n < 0) return '';
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / (1024 * 1024)).toFixed(1)} MB`;
}

export interface AttachmentLimits {
  maxFileBytes: number;
  maxTotalBytes: number;
}

export const DEFAULT_ATTACHMENT_LIMITS: AttachmentLimits = {
  maxFileBytes: DEFAULT_MAX_ATTACHMENT_BYTES,
  maxTotalBytes: DEFAULT_MAX_TOTAL_ATTACHMENT_BYTES,
};

export type AttachmentRejectionReason = 'unsupported' | 'too_large' | 'quota';
export interface AttachmentRejection {
  name: string;
  reason: AttachmentRejectionReason;
}

/** 逐文件校验（对照参考 selectAttachmentFiles：unsupported/too_large/quota，quota 即中断） */
export function selectAttachmentFiles(
  files: File[],
  existingBytes: number,
  limits: AttachmentLimits = DEFAULT_ATTACHMENT_LIMITS,
): { accepted: File[]; rejected: AttachmentRejection[] } {
  let runningTotal = existingBytes;
  const accepted: File[] = [];
  const rejected: AttachmentRejection[] = [];
  for (const file of files) {
    if (!classifyFile(file)) {
      rejected.push({ name: file.name, reason: 'unsupported' });
      continue;
    }
    if (file.size > limits.maxFileBytes) {
      rejected.push({ name: file.name, reason: 'too_large' });
      continue;
    }
    if (runningTotal + file.size > limits.maxTotalBytes) {
      rejected.push({ name: file.name, reason: 'quota' });
      break;
    }
    runningTotal += file.size;
    accepted.push(file);
  }
  return { accepted, rejected };
}

export interface PendingAttachment {
  filename: string;
  kind: FileKind;
  base64?: string;
  /** 图片/SVG 的本地预览地址（仅本组件内使用，不持久化） */
  previewUrl?: string;
  size: number;
  mimeType?: string;
  /**
   * R23：文件内容仍在读取中的占位标记。
   * 占位一旦插入即计入附件总量配额（预留），读取完成后原地补内容；
   * 读取失败/发送/移除时删除占位并同步释放额度。
   */
  reading?: boolean;
}

export function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result ?? ''));
    reader.onerror = () => reject(reader.error ?? new Error('读取文件失败。'));
    reader.readAsDataURL(file);
  });
}

export function extractBase64FromDataUrl(dataUrl: string): string | undefined {
  const idx = dataUrl.indexOf(',');
  return idx >= 0 ? dataUrl.slice(idx + 1) : undefined;
}

/** File → 待发送附件（图片/SVG 生成预览；同参考 fileToPendingAttachment） */
export async function fileToPendingAttachment(file: File): Promise<PendingAttachment> {
  const raw = await readFileAsDataUrl(file);
  const svg = isSvgFilename(file.name) || file.type === 'image/svg+xml';
  const isImage = !svg && file.type.startsWith('image/');
  return {
    filename: file.name,
    kind: isImage ? 'image' : 'doc',
    base64: extractBase64FromDataUrl(raw),
    previewUrl: isImage || svg ? raw : undefined,
    size: file.size,
    mimeType: file.type || undefined,
  };
}

export interface DocIconSpec {
  Icon: LucideIcon;
  label: string;
}

/** 扩展名 → 图标/类别标签（对照参考 docIconFor 的分组思路，取常用类别） */
export function docIconFor(filename: string): DocIconSpec {
  const ext = extOf(filename);
  if (ext === '.pdf') return { Icon: FileText, label: 'PDF' };
  if (['.docx', '.doc'].includes(ext)) return { Icon: FileType2, label: 'Word' };
  if (['.xlsx', '.xls', '.csv', '.tsv'].includes(ext))
    return { Icon: FileSpreadsheet, label: '表格' };
  if (['.pptx', '.ppt'].includes(ext)) return { Icon: Presentation, label: '演示' };
  if (ext === '.json' || ext === '.yaml' || ext === '.yml' || ext === '.toml')
    return { Icon: FileJson, label: '数据' };
  if (
    ['.js', '.ts', '.tsx', '.jsx', '.py', '.java', '.go', '.rs', '.c', '.cpp', '.sh', '.sql'].includes(ext)
  )
    return { Icon: FileCode2, label: '代码' };
  if (['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg', '.bmp'].includes(ext))
    return { Icon: FileImage, label: '图片' };
  return { Icon: Paperclip, label: '文件' };
}
