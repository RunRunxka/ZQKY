/**
 * 试题导入文件的前端前置校验（类型 / 大小），与后端 `MAX_UPLOAD_BYTES`、
 * 支持后缀同源（`@/contracts/textbook`）。这里只做「早失败」提示；
 * 服务端仍会独立校验，前端不得据此宣称已通过。
 */

import { MAX_UPLOAD_BYTES, SUPPORTED_SUFFIXES } from '@/contracts/textbook';

export const QUESTION_IMPORT_ACCEPT = SUPPORTED_SUFFIXES.join(',');

export const QUESTION_IMPORT_SUFFIX_HINT = SUPPORTED_SUFFIXES.join(' / ');

export const QUESTION_IMPORT_MAX_MIB = Math.round(MAX_UPLOAD_BYTES / 1024 / 1024);

export function fileSuffix(name: string): string {
  const index = name.lastIndexOf('.');
  return index < 0 ? '' : name.slice(index).toLowerCase();
}

/** 返回明确的拒绝原因；通过校验返回 null。 */
export function questionImportFileError(file: { name: string; size: number }): string | null {
  const suffix = fileSuffix(file.name);
  if (!(SUPPORTED_SUFFIXES as readonly string[]).includes(suffix)) {
    return `不支持的文件类型「${suffix || file.name}」：试题文件仅支持 ${QUESTION_IMPORT_SUFFIX_HINT}。`;
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return `文件过大：${file.name} 超过 ${QUESTION_IMPORT_MAX_MIB} MiB 上限，请拆分或压缩后再导入。`;
  }
  return null;
}
