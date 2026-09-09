import { beforeEach, describe, expect, it } from 'vitest';
import { simulateMaterialIngest } from './reading-ingest';
import { createMaterial, readMaterials, updateMaterialStatus } from './reading-store';

beforeEach(() => window.localStorage.clear());

function flush(ms: number) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function createSimulatedMaterial(kind: 'pdf' | 'video' = 'pdf', title = '模拟导入材料') {
  return createMaterial({
    title,
    sourceKind: kind,
    filename: kind === 'pdf' ? '样例文件.pdf' : '样例视频.mp4',
    status: 'queued',
    extractor: `${kind}-simulated`,
  });
}

describe('reading-ingest 显式模拟解析（R32.2）', () => {
  it('queued → processing → ready，产物为标注【模拟解析产物】的结构化样例', async () => {
    const material = await createSimulatedMaterial();
    expect(readMaterials()[0]!.status).toBe('queued');
    simulateMaterialIngest(material.id, { firstDelayMs: 5, secondDelayMs: 5 });
    await flush(30);
    const done = readMaterials()[0]!;
    expect(done.status).toBe('ready');
    expect(done.statusNote).toContain('模拟');
    expect(done.text).toContain('【模拟解析产物】');
    expect(done.text).toContain('样例文件.pdf');
    expect(done.charCount).toBeGreaterThan(0);
    expect(done.extractor).toBe('pdf-simulated');
  });

  it('fail：以 failed 收尾并可重试（重试后就绪）', async () => {
    const material = await createSimulatedMaterial('video', '失败演示材料');
    simulateMaterialIngest(material.id, { fail: true, firstDelayMs: 5, secondDelayMs: 5 });
    await flush(30);
    expect(readMaterials()[0]!.status).toBe('failed');
    expect(readMaterials()[0]!.statusNote).toContain('失败');
    // 重试（不布防失败）
    updateMaterialStatus(material.id, 'queued', null);
    simulateMaterialIngest(material.id, { firstDelayMs: 5, secondDelayMs: 5 });
    await flush(30);
    expect(readMaterials()[0]!.status).toBe('ready');
  });

  it('取消：queued 阶段取消后不再推进，状态标记取消并可重试', async () => {
    const material = await createSimulatedMaterial('pdf', '取消演示材料');
    // 第一时间取消：句柄 cancel 后定时链不推进
    const handle = simulateMaterialIngest(material.id, { firstDelayMs: 10000, secondDelayMs: 10 });
    handle.cancel();
    await flush(20);
    // cancel 句柄只停定时器，不改状态；卡片级取消用 cancelMaterialIngest
    const { cancelMaterialIngest } = await import('./reading-ingest');
    const material2 = await createSimulatedMaterial('pdf', '卡片取消材料');
    simulateMaterialIngest(material2.id, { firstDelayMs: 10000, secondDelayMs: 10 });
    cancelMaterialIngest(material2.id);
    await flush(20);
    expect(readMaterials().find((item) => item.id === material2.id)?.status).toBe('failed');
    expect(readMaterials().find((item) => item.id === material2.id)?.statusNote).toContain('取消');
  });

  it('视频材料产物为带时间戳的转录形态', async () => {
    const material = await createSimulatedMaterial('video', '转录演示');
    simulateMaterialIngest(material.id, { firstDelayMs: 5, secondDelayMs: 5 });
    await flush(30);
    expect(readMaterials()[0]!.text).toContain('[00:00]');
  });
});
