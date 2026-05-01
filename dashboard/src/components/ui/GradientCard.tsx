'use client';

import { motion } from 'framer-motion';
import { ReactNode } from 'react';

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

const glowShadows: Record<string, string> = {
  primary: '0 8px 32px rgba(255, 77, 109, 0.15)',
  warm: '0 8px 32px rgba(251, 191, 36, 0.15)',
  cool: '0 8px 32px rgba(124, 58, 237, 0.15)',
  success: '0 8px 32px rgba(16, 185, 129, 0.15)',
  info: '0 8px 32px rgba(59, 130, 246, 0.15)',
};

export function GradientCard({ children, gradient = 'primary', className = '', hover = true, delay = 0 }: GradientCardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      whileHover={hover ? { y: -4, boxShadow: glowShadows[gradient] } : undefined}
      className={`relative rounded-2xl overflow-hidden ${className}`}
    >
      <div className={`absolute inset-0 bg-gradient-to-br ${gradients[gradient]} opacity-[0.08] dark:opacity-[0.12]`} />
      <div className={`absolute inset-[1px] rounded-2xl bg-gradient-to-br ${gradients[gradient]} opacity-20 dark:opacity-30`} />
      <div className="absolute inset-[2px] rounded-2xl bg-light-bg dark:bg-dark-card" />
      <div className="relative z-10 p-5 sm:p-6">{children}</div>
    </motion.div>
  );
}
