import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { projectReadableText, TEXT_PROJECTION_VERSION } from './text-projection';

/**
 * 跨语言样例对照（RAG-QUALITY v1.1 · B0 交付）。
 *
 * `tests/fixtures/text-projection-samples.json` 是**唯一对照集**（前后端共用，24 组）。
 * 本地清洗只服务旧历史展示；新结果一律以后端 `readable` 为准，因此这里逐组断言
 * 清洗文本、图片计数与原文/清洗映射的完整一致（含 `expectedSegments`）。
 */

interface SampleCase {
  name: string;
  raw: string;
  expectedText: string;
  expectedRemovedImageCount: number;
  expectedSegments: { cleanStart: number; cleanEnd: number; rawStart: number; rawEnd: number; kind: string }[];
}

/** 仓库根 `tests/fixtures/text-projection-samples.json`（vitest 根为仓库根；兼容从 apps/web 运行） */
function resolveSamplePath(): string {
  for (const candidate of [
    resolve(process.cwd(), 'tests/fixtures/text-projection-samples.json'),
    resolve(process.cwd(), '../../tests/fixtures/text-projection-samples.json'),
  ]) {
    if (existsSync(candidate)) return candidate;
  }
  throw new Error('未找到 tests/fixtures/text-projection-samples.json');
}

const fixture = JSON.parse(readFileSync(resolveSamplePath(), 'utf8')) as {
  version: string;
  cases: SampleCase[];
};

const IMAGE_ADDRESS_MARKERS = ['images/', '.png', '.jpg', '.jpeg', '.webp', '.gif', '<img', '<picture'];

describe('本地可读投影：与 tests/fixtures/text-projection-samples.json 逐组一致', () => {
  it('样例集版本是已知清洗版本，且覆盖全部 24 组', () => {
    // 后端清洗版本会随规则演进（v1 → v2 新增"被截断标签残片"处理）；本 TS 投影只承担
    // **旧历史展示回退**，实现 v1 语义。二者真正的对齐判据是下面逐组相等（24 组期望在 v1/v2 下相同），
    // 因此这里只校验"fixture 版本是已知的"，不要求等于前端常量——否则会迫使前端假称实现了 v2。
    expect(['rag-readable-v1', 'rag-readable-v2']).toContain(fixture.version);
    expect(TEXT_PROJECTION_VERSION).toBe('rag-readable-v1');
    expect(fixture.cases).toHaveLength(24);
  });

  it.each(fixture.cases.map((item) => [item.name, item] as const))(
    '样例 %s：清洗文本、图片计数与映射一致',
    (_name, sample) => {
      const projection = projectReadableText(sample.raw);
      expect(projection.version).toBe(TEXT_PROJECTION_VERSION);
      expect(projection.text).toBe(sample.expectedText);
      expect(projection.removedImageCount).toBe(sample.expectedRemovedImageCount);
      expect(
        projection.sourceSegments.map((segment) => ({
          cleanStart: segment.cleanStart,
          cleanEnd: segment.cleanEnd,
          rawStart: segment.rawStart,
          rawEnd: segment.rawEnd,
          kind: segment.kind,
        })),
      ).toEqual(sample.expectedSegments);
    },
  );

  it.each(fixture.cases.map((item) => [item.name, item] as const))(
    '样例 %s：图片地址不进入清洗文本（保护区字面示例与保留的文字链接定义除外）',
    (_name, sample) => {
      const { text } = projectReadableText(sample.raw);
      for (const marker of IMAGE_ADDRESS_MARKERS) {
        if (sample.expectedText.includes(marker)) continue;
        expect(text).not.toContain(marker);
      }
      if (sample.expectedRemovedImageCount > 0 && sample.expectedText !== sample.raw) {
        // 有图片被清除的样例必须真的发生了清洗（不是原样返回）
        expect(Array.from(text).length).toBeLessThan(Array.from(sample.raw).length);
      }
    },
  );

  it.each(fixture.cases.map((item) => [item.name, item] as const))(
    '样例 %s：映射铺满原文与清洗文本（可回原、可回填）',
    (_name, sample) => {
      const projection = projectReadableText(sample.raw);
      const rawChars = Array.from(sample.raw);
      const cleanChars = Array.from(projection.text);
      let rawCursor = 0;
      let cleanCursor = 0;
      for (const segment of projection.sourceSegments) {
        expect(segment.rawStart).toBe(rawCursor);
        expect(segment.cleanStart).toBe(cleanCursor);
        if (segment.kind === 'removed') {
          expect(segment.cleanEnd).toBe(segment.cleanStart);
        } else {
          expect(
            rawChars.slice(segment.rawStart, segment.rawEnd).join(''),
          ).toBe(cleanChars.slice(segment.cleanStart, segment.cleanEnd).join(''));
        }
        rawCursor = segment.rawEnd;
        cleanCursor = segment.cleanEnd;
      }
      expect(rawCursor).toBe(rawChars.length);
      expect(cleanCursor).toBe(cleanChars.length);
    },
  );

  it('幂等：清洗结果再次清洗不再变化（旧历史二次渲染稳定）', () => {
    for (const sample of fixture.cases) {
      const once = projectReadableText(sample.raw);
      const twice = projectReadableText(once.text);
      expect(twice.text).toBe(once.text);
      expect(twice.removedImageCount).toBe(0);
    }
  });

  it('空输入与纯图片输入不抛错（旧历史为空时如实返回空串）', () => {
    expect(projectReadableText('').text).toBe('');
    expect(projectReadableText('![](images/a.png)').text).toBe('');
  });
});
