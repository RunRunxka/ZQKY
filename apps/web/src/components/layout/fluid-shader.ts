/**
 * fluid-shader.ts —— 原创流体背景（**本项目自研，不含任何第三方代码**）
 *
 * 背景（AGPL-OUT v1，2026-09-23）：本文件此前是 DSH-Transparent-UI-Plugin
 * （AGPL-3.0）的逐行移植版，且其中 GLSL 源码字面量抄自 deepseek.com 线上包
 * （无任何许可）。为消除分发风险，本文件已整份替换为自研实现：
 * 对外接口保持不变（函数名 / 参数名 / 句柄形状），因此调用方
 * `GlassBackdrop.tsx` 只需改掉 WebGL 预检，算法与上游零共享代码。
 * 详见 docs/licenses/deeptutor-chat/README.md。
 *
 * —— 算法（约 200 行）——
 *   1. 低分辨率画布（视口的 1/10），只画若干个软光斑；
 *   2. 光斑中心由**正弦叠加**驱动（确定性、无随机数），获得平滑且长时间不重复的漂移；
 *   3. 画布放大到全屏 → 天然低频模糊，不需要额外的模糊通道；
 *   4. 光斑以 'lighter' 叠加：深色底 + 只在 G/B 上累加，得到「近黑深蓝 + 蓝色辉光」；
 *   5. 指针提供轻微视差；stir() 提供一次性扰动。
 *
 * —— 参数 ——
 * FluidParams 的字段与原接口保持一致以便直接替换。其中本实现真正使用：
 *   color1 / color2 / color3、speed、scale、softness、offsetX、offsetY、
 *   mouseRadius、mouseStrength；
 * 其余字段（decay / distortBoost / noiseBoost / swirlBoost / distortion / swirl /
 * swirlIterations / shapeScale / rotation / proportion）为接口兼容而保留，
 * **本实现不读取**。
 *
 * —— 减少动画 ——
 * 系统 `prefers-reduced-motion: reduce` 或本地 `html[data-motion="reduced"]`
 * 任一命中时只绘制一帧静态画面，不启动帧循环（与原移植版行为一致，并补齐了
 * 本地开关这一路）。
 */

export interface FluidParams {
  mouseRadius: number;
  mouseStrength: number;
  decay: number;
  distortBoost: number;
  noiseBoost: number;
  swirlBoost: number;
  speed: number;
  distortion: number;
  swirl: number;
  swirlIterations: number;
  scale: number;
  rotation: number;
  proportion: number;
  softness: number;
  shapeScale: number;
  offsetX: number;
  offsetY: number;
  color1: string;
  color2: string;
  color3: string;
}

/** 站点默认参数（色值会被 fluid-tones 覆盖）。 */
export const SITE_FLUID_PARAMS: FluidParams = {
  mouseRadius: 0.22,
  mouseStrength: 1.1,
  decay: 0.96,
  distortBoost: 1.35,
  noiseBoost: 0,
  swirlBoost: 0.45,
  speed: 14,
  distortion: 20,
  swirl: 12,
  swirlIterations: 8,
  scale: 0.5,
  rotation: -5,
  proportion: 50,
  softness: 100,
  shapeScale: 10,
  offsetX: 0,
  offsetY: 65,
  color1: '#8AA3D6',
  color2: '#FFFFFF',
  color3: '#FFFFFF',
};

export interface FluidShaderHandle {
  /** 热更新参数（例如换色调）而不重新挂载。 */
  setParams: (params: FluidParams) => void;
  /** 在归一化坐标处给光斑一个速度扰动（指针唤醒）。 */
  stir: (x: number, y: number, vx: number, vy: number) => void;
  /** 停止绘制并释放监听。 */
  dispose: () => void;
}

/** 低分辨率倍率：越小越柔和、开销越低。 */
const LOW_RES_DIVISOR = 10;
const TAU = Math.PI * 2;

interface Blob {
  /** 基准位置（0-1） */
  bx: number;
  by: number;
  /** 半径（以视口长边为基准的比例） */
  r: number;
  /** 权重（决定颜色与不透明度） */
  w: number;
  /** 漂移周期（秒）与相位 */
  px: number;
  py: number;
  phx: number;
  phy: number;
  /** 漂移幅度 */
  ax: number;
  ay: number;
  /** 取哪一档颜色：0=bloom, 1=mid, 2=base */
  tone: number;
}

/**
 * 光斑布局：两块主辉光（左下 / 上右）+ 中部铺底 + 一个高光点。
 * 位置由实测标定：深色下流体最亮处集中在左侧会话列与主区右上。
 *
 * 2026-09-23 调整（用户反馈"流动效果不明显"）：只加漂移幅度 ax/ay（约 ×1.4），
 * 光斑位置与周期不变——位移变大而节奏不变，观感更"流动"但不会变躁。
 */
const BLOBS: Blob[] = [
  { bx: 0.24, by: 0.7, r: 0.86, w: 1.0, px: 34, py: 41, phx: 0.0, phy: 1.7, ax: 0.2, ay: 0.11, tone: 0 },
  { bx: 0.74, by: 0.05, r: 0.82, w: 1.0, px: 47, py: 29, phx: 2.1, phy: 0.4, ax: 0.2, ay: 0.1, tone: 0 },
  { bx: 0.55, by: 0.42, r: 0.74, w: 0.44, px: 53, py: 37, phx: 4.3, phy: 3.1, ax: 0.17, ay: 0.14, tone: 1 },
  { bx: 0.62, by: 0.2, r: 0.3, w: 0.34, px: 23, py: 19, phx: 1.2, phy: 5.6, ax: 0.13, ay: 0.07, tone: 3 },
];

/** #rrggbb → [r,g,b]；解析失败时回退到中性灰。 */
function parseHex(hex: string): [number, number, number] {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return [128, 128, 128];
  const n = parseInt(m[1]!, 16);
  return [(n >> 16) & 255, (n >> 8) & 255, n & 255];
}

/**
 * 减少动画：系统偏好或本地设置任一命中即为真。
 * 本地设置由 `MotionPreference` 写到 `<html data-motion>`。
 */
function prefersReducedMotion(): boolean {
  return (
    window.matchMedia('(prefers-reduced-motion: reduce)').matches ||
    document.documentElement.dataset.motion === 'reduced'
  );
}

export function attachFluidShader(
  canvas: HTMLCanvasElement,
  initial: FluidParams,
): FluidShaderHandle {
  const maybeCtx = canvas.getContext('2d');
  if (maybeCtx === null) {
    // 2D 上下文不可用：返回空句柄，由调用方回落 CSS 环境光，绝不抛错拖垮主题
    return { setParams: () => {}, stir: () => {}, dispose: () => {} };
  }
  // 收窄一次后固定为具体类型：闭包内不再有 null 判定
  const ctx: CanvasRenderingContext2D = maybeCtx;

  let params: FluidParams = { ...initial };
  let palette: [number, number, number][] = [
    parseHex(params.color1),
    parseHex(params.color2),
    parseHex(params.color3),
  ];
  let disposed = false;
  let rafId = 0;
  let lowW = 1;
  let lowH = 1;

  /** 指针状态：目标值与插值后的当前值（避免跟随突变）。 */
  const pointer = { x: 0.5, y: 0.5, tx: 0.5, ty: 0.5 };
  /** stir() 产生的瞬时扰动（会自然衰减）。 */
  const stir = { x: 0.5, y: 0.5, rx: 0, ry: 0 };

  function refreshPalette(): void {
    palette = [
      parseHex(params.color1),
      parseHex(params.color2),
      parseHex(params.color3),
    ];
  }

  function resize(): void {
    const vw = Math.max(1, window.innerWidth);
    const vh = Math.max(1, window.innerHeight);
    lowW = Math.max(8, Math.round(vw / LOW_RES_DIVISOR));
    lowH = Math.max(8, Math.round(vh / LOW_RES_DIVISOR));
    canvas.width = lowW;
    canvas.height = lowH;
  }

  function onPointerMove(event: PointerEvent): void {
    pointer.tx = Math.min(1, Math.max(0, event.clientX / Math.max(1, window.innerWidth)));
    pointer.ty = Math.min(1, Math.max(0, event.clientY / Math.max(1, window.innerHeight)));
  }
  /** 正弦叠加：确定性准周期漂移（无随机数、无状态累积）。 */
  function offsetOf(blob: Blob, t: number): { x: number; y: number } {
    const speed = Math.max(0.05, params.speed / 14);
    const tt = t * speed;
    return {
      x:
        blob.bx +
        blob.ax * 0.5 * Math.sin(TAU * (tt / blob.px) + blob.phx) +
        blob.ax * 0.5 * Math.sin(TAU * (tt / (blob.px * 0.37)) + blob.phy),
      y:
        blob.by +
        blob.ay * 0.5 * Math.sin(TAU * (tt / blob.py) + blob.phy) +
        blob.ay * 0.5 * Math.cos(TAU * (tt / (blob.py * 0.43)) + blob.phx),
    };
  }

  function frame(): void {
    if (disposed) return;
    const t = performance.now() / 1000;

    pointer.x += (pointer.tx - pointer.x) * 0.045;
    pointer.y += (pointer.ty - pointer.y) * 0.045;
    stir.rx *= 0.94;
    stir.ry *= 0.94;

    // 深色底：用 color3 铺满（深色模式下接近黑蓝，避免出现"整体提亮"）
    ctx.globalCompositeOperation = 'source-over';
    ctx.fillStyle = params.color3;
    ctx.fillRect(0, 0, lowW, lowH);
    ctx.globalCompositeOperation = 'lighter';

    // scale 控制光斑整体大小；softness 控制边缘衰减位置
    const scaleRef = Math.max(0.2, params.scale) * Math.max(lowW, lowH) * 0.5;
    const softness = Math.min(1, Math.max(0.05, params.softness / 100));
    const centerBias = {
      x: (params.offsetX ?? 0) / 100,
      y: ((params.offsetY ?? 0) - 50) / 100,
    };

    for (const blob of BLOBS) {
      const o = offsetOf(blob, t);
      const par = 0.06 * (1 - blob.w) + 0.02;
      const cx =
        (o.x + centerBias.x * 0.05 + stir.x * (stir.rx / 100) + (pointer.x - 0.5) * par * 2) *
        lowW;
      const cy =
        (o.y + centerBias.y * 0.05 + stir.y * (stir.ry / 100) + (pointer.y - 0.5) * par * 2) *
        lowH;
      const rr = Math.max(4, blob.r * scaleRef);
      const color = palette[Math.min(3, blob.tone)] ?? palette[0]!;
      // 0.38 → 0.42（2026-09-23）：整体再明显一档。浅色端的底色已同步加深，
      // 因此这里提高不透明度不会重新把画面推回"发白"。
      const alpha = 0.42 * blob.w;

      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, rr);
      const rgb = `${color[0]},${color[1]},${color[2]}`;
      g.addColorStop(0, `rgba(${rgb},${alpha})`);
      g.addColorStop(softness * 0.55, `rgba(${rgb},${alpha * 0.45})`);
      g.addColorStop(1, `rgba(${rgb},0)`);
      ctx.fillStyle = g;
      ctx.beginPath();
      ctx.arc(cx, cy, rr, 0, TAU);
      ctx.fill();
    }

    rafId = requestAnimationFrame(frame);
  }

  resize();
  refreshPalette();
  window.addEventListener('resize', resize);
  // 触摸/粗指针不接入指针视差：这类设备的 pointermove 在滚动时频繁触发，
  // 收益低且会持续改写光斑位置（沿用既有移植版的指针策略）。
  if (!window.matchMedia('(hover: none), (pointer: coarse)').matches) {
    window.addEventListener('pointermove', onPointerMove, { passive: true });
  }

  frame();
  if (prefersReducedMotion()) {
    // 减少动画：保留这一帧静态画面，退出帧循环
    cancelAnimationFrame(rafId);
    rafId = 0;
  }

  return {
    setParams(next: FluidParams) {
      params = { ...params, ...next };
      refreshPalette();
    },
    stir(x: number, y: number, vx: number, vy: number) {
      stir.x = Math.min(1, Math.max(0, x));
      stir.y = Math.min(1, Math.max(0, y));
      stir.rx = Math.max(-100, Math.min(100, vx * 100 * params.mouseStrength));
      stir.ry = Math.max(-100, Math.min(100, vy * 100 * params.mouseStrength));
    },
    dispose() {
      disposed = true;
      if (rafId) cancelAnimationFrame(rafId);
      window.removeEventListener('resize', resize);
      window.removeEventListener('pointermove', onPointerMove);
    },
  };
}
