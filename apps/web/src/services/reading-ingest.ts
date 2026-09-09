/**
 * 材料解析显式模拟（R32.2）：真实 PDF/EPUB/网页/媒体解析依赖服务端，未接入。
 * 此处以结构化样例 + 明确标识模拟导入→排队→解析→就绪/失败/取消的完整前端流程，
 * 保留服务接口与状态语义（对照参考 queued/processing/ready + extractor），
 * 不伪装真实解析成功；解析产物一律标注【模拟解析产物】。
 */
import {
  completeMaterialIngest,
  readMaterials,
  updateMaterialStatus,
  type ReadingSourceKind,
} from './reading-store';

export const READING_EXTRACTORS: Record<Exclude<ReadingSourceKind, 'text'>, string> = {
  pdf: 'pdf-text（模拟）',
  epub: 'epub-chapters（模拟）',
  webpage: 'web-markdown（模拟）',
  video: 'youtube-transcript（模拟）',
  audio: 'audio-transcript（模拟）',
};

/** 各类型的结构化样例文本（# 行按标题渲染；视频/音频为带时间戳的转录形态） */
export function simulatedExtractText(input: {
  sourceKind: Exclude<ReadingSourceKind, 'text'>;
  title: string;
  filename: string;
}): string {
  const { sourceKind, title, filename } = input;
  const header = `【模拟解析产物】来源：${filename}（本地样例，未读取真实文件内容）`;
  switch (sourceKind) {
    case 'pdf':
      return [
        `# ${title}（模拟 PDF 解析）`,
        '',
        header,
        '',
        '## 第 1 页',
        '',
        '本页为模拟解析样例：真实 PDF 文本层提取未接入，此处以结构化段落占位，保留阅读、批注与书签流程。',
        '',
        '## 第 2 页',
        '',
        '解析产物按页组织（unit=page）；翻页与阅读位置保存在本地，与文本材料行为一致。',
      ].join('\n');
    case 'epub':
      return [
        `# ${title}（模拟 EPUB 解析）`,
        '',
        header,
        '',
        '## 第一章',
        '',
        '模拟样例：EPUB 按章节切分（unit=chapter），章节标题生成大纲，可从导航跳转。',
        '',
        '## 第二章',
        '',
        '真实电子书解析未接入；本样例仅用于演示导入后的阅读闭环。',
      ].join('\n');
    case 'webpage':
      return [
        `# ${title}（模拟网页抓取）`,
        '',
        header,
        '',
        '## 摘要',
        '',
        '模拟样例：网页正文抓取未接入，此处以 markdown 段落占位（unit=section）。',
        '',
        '## 正文',
        '',
        '来源链接保留在材料信息中，真实抓取接入后将按正文清洗规则替换本样例。',
      ].join('\n');
    case 'video':
      return [
        `# ${title}（模拟视频转录）`,
        '',
        header,
        '',
        '## 字幕转录',
        '',
        '[00:00] 模拟样例：视频转录（unit=segment）按时间戳分段展示。',
        '',
        '[00:12] 真实字幕/语音识别未接入；播放器视图未实现，先以转录文本进入阅读流程。',
        '',
        '[00:30] 后续接入后，本区域将替换为真实转录并支持来源跳转。',
      ].join('\n');
    case 'audio':
      return [
        `# ${title}（模拟音频转录）`,
        '',
        header,
        '',
        '## 转录',
        '',
        '[00:00] 模拟样例：音频语音识别未接入，以时间戳分段占位。',
        '',
        '[00:45] 转录文本支持选中、高亮与问 AI，行为与文本材料一致。',
      ].join('\n');
  }
}

export interface IngestHandle {
  /** 取消未完成的模拟解析（清理定时器，不改变状态） */
  cancel(): void;
}

/** 进行中的模拟解析注册表：供材料库卡片随时取消 */
const activeIngests = new Map<string, IngestHandle>();

/** 取消材料的模拟解析：停止定时推进并显式标记取消（failed + 说明），可重试 */
export function cancelMaterialIngest(materialId: string): void {
  activeIngests.get(materialId)?.cancel();
  const material = readMaterials().find((item) => item.id === materialId);
  if (material && (material.status === 'queued' || material.status === 'processing')) {
    updateMaterialStatus(materialId, 'failed', '【模拟】已取消解析（演示取消路径，可重试）。');
  }
}

/**
 * 推进一个材料的模拟解析：queued → processing → ready（写入结构化样例）；
 * options.fail = true 时以 failed 收尾（显式模拟失败，可重试）。
 * 注册到 activeIngests，完成后移除；重复调用先取消旧流程。
 */
export function simulateMaterialIngest(
  materialId: string,
  options?: { fail?: boolean; firstDelayMs?: number; secondDelayMs?: number },
): IngestHandle {
  activeIngests.get(materialId)?.cancel();
  const firstDelay = options?.firstDelayMs ?? 500;
  const secondDelay = options?.secondDelayMs ?? 900;
  const timers: number[] = [];
  let cancelled = false;
  const schedule = (fn: () => void, ms: number) => {
    timers.push(window.setTimeout(fn, ms));
  };
  const handle: IngestHandle = {
    cancel() {
      cancelled = true;
      for (const timer of timers) window.clearTimeout(timer);
    },
  };
  activeIngests.set(materialId, handle);
  const finish = () => activeIngests.delete(materialId);
  schedule(() => {
    if (cancelled) {
      finish();
      return;
    }
    const material = readMaterials().find((item) => item.id === materialId);
    if (!material || material.status !== 'queued') {
      finish();
      return;
    }
    updateMaterialStatus(materialId, 'processing', '【模拟】解析进行中（本地样例，非真实解析）。');
    schedule(() => {
      finish();
      if (cancelled) return;
      const current = readMaterials().find((item) => item.id === materialId);
      if (!current || current.status !== 'processing') return;
      if (options?.fail) {
        updateMaterialStatus(materialId, 'failed', '【模拟】解析失败：解析器不可用（演示失败路径，可重试）。');
        return;
      }
      completeMaterialIngest(
        materialId,
        simulatedExtractText({
          sourceKind: current.sourceKind as Exclude<ReadingSourceKind, 'text'>,
          title: current.title,
          filename: current.filename ?? current.title,
        }),
        '【模拟】解析完成：内容为本地结构化样例，未读取真实文件。',
      );
    }, secondDelay);
  }, firstDelay);
  return handle;
}
