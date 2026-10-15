'use client';
import { MeshGradient } from '@paper-design/shaders-react';
import { useMotionPreference } from '@/components/layout/MotionPreference';
import { useResolvedThemeKey } from '@/components/charts/chart-theme';
import './styles/chat-hero-backdrop.css';

/** 深色主题下的首页氛围背景：深海军蓝底 + 品牌蓝光斑。浅色不挂载，不占 WebGL 上下文。 */
const HERO_COLORS = ['#0b1220', '#1d4ed8', '#2563eb', '#172a52'];

export function ChatHeroBackdrop() {
  const { reduced } = useMotionPreference();
  const themeKey = useResolvedThemeKey();
  if (themeKey !== 'dark') return null;
  return (
    <div className="chat-hero-backdrop" aria-hidden="true">
      {/* 减少动画时速度为 0：只渲染静止一帧，不持续重绘 */}
      <MeshGradient
        style={{ width: '100%', height: '100%' }}
        colors={HERO_COLORS}
        distortion={0.55}
        swirl={0.25}
        speed={reduced ? 0 : 0.12}
      />
    </div>
  );
}
