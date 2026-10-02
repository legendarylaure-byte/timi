'use client';

import { motion } from 'framer-motion';
import { ReactNode } from 'react';
import { useGlassPointer } from '@/hooks/useGlassPointer';
import { LIGHT_THEME, DARK_THEME } from '@/lib/brand';

interface GradientCardProps {
  children: ReactNode;
  gradient?: 'primary' | 'warm' | 'cool' | 'success' | 'info';
  className?: string;
  hover?: boolean;
  delay?: number;
}

const gradients: Record<string, string> = {
  primary: 'from-light-primary to-light-secondary',
  warm: 'from-light-primary to-light-accent',
  cool: 'from-light-secondary to-light-info',
  success: 'from-light-success to-light-info',
  info: 'from-light-info to-light-secondary',
};

// Glow colour per variant, from the palette rather than retyped. These were
// retired crimson/teal rgba() triples (invisible to the old hex-only drift
// test) and are now brand ramp stops with the alpha appended.
const glowColors: Record<string, string> = {
  primary: LIGHT_THEME.primary,
  warm: LIGHT_THEME.accent,
  cool: LIGHT_THEME.secondary,
  success: LIGHT_THEME.success,
  info: LIGHT_THEME.info,
};

const hexToRgba = (hex: string, alpha: number) => {
  const h = hex.replace('#', '');
  const [r, g, b] = [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16));
  return `rgba(${r},${g},${b},${alpha})`;
};

const glowShadows: Record<string, string> = Object.fromEntries(
  Object.entries(glowColors).map(([k, hex]) => [k, `0 8px 32px ${hexToRgba(hex, 0.22)}`]),
);

export function GradientCard({ children, gradient = 'primary', className = '', hover = true, delay = 0 }: GradientCardProps) {
  const { ref, onPointerMove } = useGlassPointer<HTMLDivElement>();
  return (
    <motion.div
      ref={ref}
      onPointerMove={onPointerMove}
      // `glass-specular` supplies the cursor-tracked highlight; the layout class
      // supplies the light/dark surface. Both are needed -- specular alone is a
      // highlight on an invisible card.
      className={`glass-specular relative rounded-2xl overflow-hidden ${className}`}
    >
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ delay, duration: 0.4 }}
        whileHover={hover ? { y: -4, boxShadow: glowShadows[gradient] } : undefined}
        className="relative rounded-2xl"
      >
        <div className={`absolute inset-0 bg-gradient-to-br ${gradients[gradient]} opacity-[0.08] dark:opacity-[0.12]`} />
        {/* Light mode needs the inner fill to be the *card* surface, not the
            page surface, or the gradient rim has nothing to sit against and
            the whole thing reads as a tinted rectangle. */}
        <div className="absolute inset-[1px] rounded-2xl bg-light-card dark:bg-dark-card" />
        <div className="relative z-10 p-5 sm:p-6">{children}</div>
      </motion.div>
    </motion.div>
  );
}
