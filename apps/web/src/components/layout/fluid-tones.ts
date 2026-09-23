/**
 * fluid-tones.ts —— 流体色调表（**本项目自研，不含任何第三方代码**）
 *
 * 背景（AGPL-OUT v1，2026-09-23）：本文件此前是 DSH-Transparent-UI-Plugin
 * （AGPL-3.0）的移植版，为消除分发风险已整份替换为自研实现；对外接口
 * （`FluidToneColors` / `HUE_BASE` / `fluidToneColors`）保持不变。
 * 详见 docs/licenses/deeptutor-chat/README.md。
 *
 * 目标：给定色相(0-360)与深浅(0-100)输出三档颜色，供流体层使用。
 * 实现：HSL 分段插值（deep → mid → pale），色相基准 217°。
 *
 * 与玻璃深色方案对齐（实测标定）：色相 217°、饱和度 0.85、亮度 0.42
 * 正好落在深色背景需要的「近黑深蓝 + 只往 G/B 加的蓝色辉光」上，
 * 即 R 分量天然很低 —— 这是深色下玻璃背景像不像的关键。
 */

export interface FluidToneColors {
  /** 亮部 / 辉光色 */
  color1: string;
  /** 中间过渡色 */
  color2: string;
  /** 深色底（深色模式下近黑，浅色模式下近白） */
  color3: string;
}

/** 色相基准：0/360 落在蓝色上，与玻璃主题的蓝色基准一致。 */
export const HUE_BASE = 217;

/** hsl(h, s, l) → #rrggbb（标准 HSL→RGB 换算）。 */
function hsl(h: number, s: number, l: number): string {
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
  const m = l - c / 2;
  let r = 0;
  let g = 0;
  let b = 0;
  if (h < 60) {
    r = c;
    g = x;
  } else if (h < 120) {
    r = x;
    g = c;
  } else if (h < 180) {
    g = c;
    b = x;
  } else if (h < 240) {
    g = x;
    b = c;
  } else if (h < 300) {
    r = x;
    b = c;
  } else {
    r = c;
    b = x;
  }
  const hex = (v: number): string =>
    Math.round(Math.min(1, Math.max(0, v + m)) * 255)
      .toString(16)
      .padStart(2, '0');
  return `#${hex(r)}${hex(g)}${hex(b)}`;
}

/**
 * 按色相与深浅给出三档颜色。
 * 深浅 0 = 最深端（深色模式近黑 / 浅色模式为鲜艳深色），100 = 最浅端。
 */
export function fluidToneColors(dark: boolean, hue: number, depth: number): FluidToneColors {
  const h = (((hue + HUE_BASE) % 360) + 360) % 360;
  const d = Math.min(1, Math.max(0, depth / 100));
  /** 分段线性：0→0.5 从 deep 走到 mid，0.5→1 从 mid 走到 pale。 */
  const ramp = (deep: number, mid: number, pale: number): number =>
    d < 0.5 ? deep + ((mid - deep) * d) / 0.5 : mid + ((pale - mid) * (d - 0.5)) / 0.5;

  if (dark) {
    return {
      color1: hsl(h, 0.85, ramp(0.28, 0.42, 0.58)),
      color2: hsl(h, 0.85, ramp(0.18, 0.3, 0.44)),
      color3: hsl(h, 0.55, ramp(0.0, 0.075, 0.1)),
    };
  }
  return {
    color1: hsl(h, 0.95, ramp(0.3, 0.52, 0.9)),
    color2: hsl(h, 0.55, 0.86),
    color3: hsl(h, 0.25, 0.955),
  };
}
