// @vitest-environment jsdom
import { describe, expect, it } from 'vitest';
import { fluidToneColors, HUE_BASE } from './fluid-tones';

const hex = (value: string): [number, number, number] => {
  const n = parseInt(value.slice(1), 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
};

const luminance = (value: string): number => {
  const [r, g, b] = hex(value);
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};

describe('流体色调表（自研实现）', () => {
  it('三档都输出合法 #rrggbb', () => {
    for (const dark of [true, false]) {
      const tones = fluidToneColors(dark, 0, 25);
      for (const value of [tones.color1, tones.color2, tones.color3]) {
        expect(value).toMatch(/^#[0-9a-f]{6}$/);
      }
    }
  });

  it('深色下底色近黑：R 分量明显低于 G/B（不整体提亮）', () => {
    const { color3 } = fluidToneColors(true, 0, 0);
    const [r, g, b] = hex(color3);
    expect(r).toBeLessThanOrEqual(12);
    expect(b).toBeGreaterThanOrEqual(r);
    expect(g).toBeGreaterThanOrEqual(r);
  });

  it('色相基准 217° 时 0° 已是蓝色（B 最大）', () => {
    const [r, g, b] = hex(fluidToneColors(true, 0, 42).color1);
    expect(b).toBeGreaterThan(g);
    expect(b).toBeGreaterThan(r);
    expect(HUE_BASE).toBe(217);
  });

  it('深浅单调：越深亮度越低', () => {
    const deep = luminance(fluidToneColors(true, 0, 0).color1);
    const mid = luminance(fluidToneColors(true, 0, 50).color1);
    const pale = luminance(fluidToneColors(true, 0, 100).color1);
    expect(deep).toBeLessThan(mid);
    expect(mid).toBeLessThan(pale);
  });

  it('浅色底色留出加法余量：不再近白，但仍是浅色主题', () => {
    // 流体用 lighter 叠加，底色越白越快饱和成纯白（曾出现平均亮度 246 的"发白"画面）
    const base = luminance(fluidToneColors(false, 0, 25).color3);
    expect(base).toBeLessThan(238);
    expect(base).toBeGreaterThan(200);
  });

  it('浅色 bloom 明显比底色深，加法后才落得下颜色', () => {
    const tones = fluidToneColors(false, 0, 25);
    expect(luminance(tones.color1)).toBeLessThan(luminance(tones.color3) - 40);
    expect(luminance(tones.color2)).toBeLessThan(luminance(tones.color3));
  });

  it('浅色底色亮度随"深浅"单调：0 最深、100 最浅', () => {
    const deep = luminance(fluidToneColors(false, 0, 0).color3);
    const pale = luminance(fluidToneColors(false, 0, 100).color3);
    expect(deep).toBeLessThan(pale);
  });

  it('同输入同输出（确定性，无随机）', () => {
    expect(fluidToneColors(true, 30, 40)).toEqual(fluidToneColors(true, 30, 40));
  });

  it('越界输入被夹紧，不产生非法色值', () => {
    for (const tones of [
      fluidToneColors(true, -400, -50),
      fluidToneColors(false, 9999, 9999),
    ]) {
      for (const value of [tones.color1, tones.color2, tones.color3]) {
        expect(value).toMatch(/^#[0-9a-f]{6}$/);
      }
    }
  });
});
