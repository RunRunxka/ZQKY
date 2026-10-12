/** 触发浏览器下载（环境不支持时返回 false，由调用方按「已生成但未下载」如实提示）。 */
export function triggerBlobDownload(blob: Blob, fileName: string): boolean {
  if (typeof document === 'undefined' || typeof URL.createObjectURL !== 'function') return false;
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement('a');
  anchor.href = url;
  anchor.download = fileName;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(url);
  return true;
}
