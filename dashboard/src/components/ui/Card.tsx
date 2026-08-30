'use client';

import { motion } from 'framer-motion';
import type { ComponentType } from 'react';

interface CardProps {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  /** Render an animated crimson→teal gradient hairline border on hover */
  accent?: boolean;
  /** Optional icon rendered in a colored glass chip at the top */
  icon?: ComponentType<{ className?: string }>;
  /** Tailwind text-color class for the icon chip glyph */
  iconColor?: string;
  /** Tailwind bg-color class for the icon chip */
  iconBgClass?: string;
}

export function Card({
  children,
  className = '',
  delay = 0,
  accent = false,
  icon: Icon,
  iconColor = 'text-light-primary dark:text-dark-primary',
  iconBgClass = 'bg-light-primary/10 dark:bg-dark-primary/10',
}: CardProps) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay, duration: 0.4 }}
      whileHover={{ y: -4, transition: { duration: 0.2 } }}
      className={`glass-panel glass-noise card-hover p-6 ${accent ? 'gradient-border' : ''} ${className}`}
    >
      {Icon && (
        <div className={`w-10 h-10 rounded-xl flex items-center justify-center mb-4 ${iconBgClass}`}>
          <Icon className={`w-5 h-5 ${iconColor}`} />
        </div>
      )}
      {children}
    </motion.div>
  );
}
