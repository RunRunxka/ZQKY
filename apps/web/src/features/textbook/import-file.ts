/**
 * 导入文件的前端前置校验（类型/大小），与后端 `MAX_UPLOAD_BYTES` / `SUPPORTED_SUFFIXES` 同源。
 * 这里只做「早失败」提示；服务端仍会独立校验，前端不得据此宣称已通过。
 */

import { MAX_UPLOAD_BYTES, SUPPORTED_SUFFIXES } from '@/contracts/textbook';

/** 文件选择框的 accept 值（单一来源）。 */
export const IMPORT_ACCEPT = SUPPORTED_SUFFIXES.join(',');

/** 支持的后缀说明文案（错误提示复用）。 */
export const IMPORT_SUFFIX_HINT = SUPPORTED_SUFFIXES.join(' / ');

export function fileSuffix(name: string): string {
  const index = name.lastIndexOf('.');
  return index < 0 ? '' : name.slice(index).toLowerCase();
}

/** 返回明确的拒绝原因；通过校验返回 null。 */
export function importFileError(file: { name: string; size: number }): string | null {
  const suffix = fileSuffix(file.name);
  if (!SUPPORTED_SUFFIXES.includes(suffix as (typeof SUPPORTED_SUFFIXES)[number])) {
    return `不支持的文件类型「${suffix || file.name}」：仅支持 ${IMPORT_SUFFIX_HINT}。`;
  }
  if (file.size > MAX_UPLOAD_BYTES) {
    return `文件过大：${file.name} 超过 ${Math.round(MAX_UPLOAD_BYTES / 1024 / 1024)} MiB 上限，请拆分或压缩后再导入。`;
  }
  return null;
}
